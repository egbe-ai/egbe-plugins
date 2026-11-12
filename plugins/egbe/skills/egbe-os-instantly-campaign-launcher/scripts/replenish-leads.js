#!/usr/bin/env node
"use strict";

/**
 * replenish-leads — Check lead utilization in an Instantly campaign.
 * When utilization reaches the run's explicit threshold, source new leads via
 * OS Apollo, then import them into the campaign.
 *
 * Usage:
 *   node replenish-leads.js --run-dir <path> [--env-file <path>] [--force] [--verbose]
 *
 * Flags:
 *   --force     Skip utilization check and replenish immediately
 *   --verbose   Print extra debug info
 */

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const {
  InstantlyClient,
  contactedForUtilization,
} = require("./lib/instantly-client");
const { leadsNotInCampaign } = require("./lib/create-once");
const { replenishmentConfig, metricNumber } = require("./lib/run-config");
const { readOptOutHistory, filterConfirmedOptOuts } = require("./lib/confirmed-opt-outs");
const {
  readJson,
  writeJson,
  parseArgs,
  isoNow,
  loadRunEnv,
  readEnvFile,
  sha256,
  getOsConfig,
  assertCampaignNotForeign,
  normalizeEmail,
  buildImportLead,
  ensureDir,
  findLeadNameProblems,
  findLeadVariableProblems,
  leadNameChecksForSteps,
} = require("./lib/helpers");
const {
  initDb,
  upsertRun,
  upsertLead,
  upsertRunLead,
  insertLeadEvent,
} = require("./lib/outreach-db");

function fail(msg) {
  console.error(`FATAL: ${msg}`);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Lead sourcing: Apollo (primary)
// ---------------------------------------------------------------------------

async function sourceFromApollo(
  envFile,
  searchConfig,
  batchSize,
  outputPath,
  verbose,
) {
  const root = path.resolve(__dirname, "..");
  const apollo = path.basename(root).startsWith("egbe-os-") ? "egbe-os-apollo-lead-finder" : "apollo-lead-finder";
  const apolloScript = path.resolve(root, "..", apollo, "scripts/find-leads.js");
  if (!fs.existsSync(apolloScript)) throw new Error("Apollo sourcing script is unavailable");

  const env = envFile && fs.existsSync(envFile) ? readEnvFile(envFile) : {};
  const os = getOsConfig({ ...env, ...process.env });
  if (os.missing.length) {
    throw new Error(`Apollo: missing ${os.missing.join(" and ")}`);
  }

  // Write search config to temp file
  const configPath = path.join(
    path.dirname(outputPath),
    ".apollo-search-config.json",
  );
  writeJson(configPath, { search: searchConfig });

  const args = [
    apolloScript,
    "--config",
    configPath,
    "--max-results",
    String(batchSize),
    "--output",
    outputPath,
    "--time-budget-ms",
    "90000",
  ];
  if (envFile) args.push("--env-file", envFile);
  if (verbose) args.push("--verbose");

  let failure = null;
  try {
    if (verbose)
      console.error(
        `Apollo: running find-leads.js with max-results=${batchSize}`,
      );
    execFileSync(process.execPath, args, {
      stdio: ["ignore", "pipe", "pipe"],
      timeout: 120_000,
      env: { ...env, ...process.env },
    });

  } catch (err) {
    failure = err;
  }
  // Exit 2 and a parent timeout may still leave usable, atomically checkpointed
  // partial results. Do not call them an empty successful search or delete them.
  const result = readJson(outputPath);
  if (!Array.isArray(result?.leads) || typeof result?.meta?.complete !== "boolean"
      || typeof result.meta.stop_reason !== "string")
    throw new Error(`Apollo sourcing has no valid result checkpoint${failure ? `: ${failure.message}` : ""}`);
  if (failure) {
    result.meta = { ...result.meta, complete: false,
      stop_reason: result.meta.complete ? "child_process_failed" : result.meta.stop_reason,
      child_exit_code: failure.status ?? null, child_signal: failure.signal || null };
    writeJson(outputPath, result);
    console.error(`Apollo sourcing incomplete (${result.meta.stop_reason}); retained ${result.leads.length} leads and source checkpoint at ${outputPath}`);
  }
  return result;
}

function pendingApolloSource(directory) {
  if (!fs.existsSync(directory)) return null;
  for (const filename of fs.readdirSync(directory).filter((name) => /^leads-.*\.json$/.test(name)).sort()) {
    const file = path.join(directory, filename);
    const result = readJson(file);
    if (!Array.isArray(result?.leads) || result?.meta?.complete !== true)
      return { path: file, complete: false, stop_reason: result?.meta?.stop_reason || "checkpoint_incomplete",
        retained_leads: Array.isArray(result?.leads) ? result.leads.length : null,
        not_enriched: result?.meta?.not_enriched ?? null };
  }
  return null;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv);
  const runDir = args["run-dir"] ? path.resolve(args["run-dir"]) : null;
  if (!runDir) fail("Missing --run-dir");
  const connectionEnvFile = loadRunEnv(runDir, args["env-file"]);

  const manifest = readJson(path.join(runDir, "manifest.json"));
  const spec = readJson(path.join(runDir, "run-spec.json"));
  if (!spec) fail("Run spec missing");
  const replenishConfig = replenishmentConfig(spec);
  if (!replenishConfig) {
    console.log(JSON.stringify({ skipped: true, reason: "lead_replenishment.enabled is not true" }));
    return;
  }
  const optOutHistory = readOptOutHistory(runDir);
  const ownership = readJson(
    path.join(runDir, "state", "ownership.json"),
    manifest?.ownership || {},
  );
  if (!manifest?.campaign?.id) fail("Run manifest missing campaign ID");

  const os = getOsConfig();
  if (os.missing.length) fail(`Missing ${os.missing.join(" and ")}`);
  const client = new InstantlyClient({
    connectionEnvFile,
    osApiKey: os.osApiKey,
    osUrl: os.osUrl,
    verbose: !!args.verbose,
  });

  const campaignId = manifest.campaign.id;

  // Verify ownership
  const campaign = await client.getCampaign(campaignId);
  if (!(campaign.status >= 200 && campaign.status < 300)) {
    fail(
      `Campaign lookup failed: ${campaign.status} ${JSON.stringify(campaign.body)}`,
    );
  }
  assertCampaignNotForeign(campaign.body, ownership, `campaign ${campaignId}`);
  const dbPath = initDb(runDir);

  // --- Read replenishment config ---
  const threshold = replenishConfig.utilization_threshold;
  const batchSize = replenishConfig.batch_size;
  const maxReplenishments = replenishConfig.max_replenishments;
  const maxTotalLeads = replenishConfig.max_total_leads;
  const cooldownMinutes = replenishConfig.cooldown_minutes;
  const apolloSearch = replenishConfig.apollo_search || null;
  const envFile = args["env-file"]
    ? path.resolve(args["env-file"])
    : path.join(runDir, ".env");

  // --- Check replenishment history ---
  const historyPath = path.join(runDir, "state", "replenishment-history.json");
  const history = readJson(historyPath, []);
  if (!Array.isArray(history)) fail("Replenishment history is malformed; restore it before sourcing");

  if (history.length >= maxReplenishments) {
    console.log(
      JSON.stringify({
        skipped: true,
        reason: `Max replenishments reached (${maxReplenishments})`,
      }),
    );
    return;
  }

  // Cooldown: don't replenish too frequently
  if (history.length > 0) {
    const lastReplenishment = new Date(
      history[history.length - 1].completed_at || 0,
    );
    const elapsedMinutes = (Date.now() - lastReplenishment.getTime()) / 60_000;
    if (!Number.isFinite(elapsedMinutes) || !history[history.length - 1].completed_at)
      fail("Replenishment completion time is unknown; inspect history before sourcing");
    if (elapsedMinutes < cooldownMinutes) {
      console.log(
        JSON.stringify({
          skipped: true,
          reason: `Cooldown: ${Math.round(cooldownMinutes - elapsedMinutes)} minutes remaining`,
        }),
      );
      return;
    }
  }

  // --- Check lead utilization ---
  // Primary: use analytics contacted_count vs lead_stats.total
  const analytics = await client.campaignAnalytics(campaignId);
  const details = campaign.body || {};
  const leadStats = details.lead_stats || {};
  const totalLeads = metricNumber(leadStats.total);
  const contactedCount =
    analytics.status >= 200 && analytics.status < 300
      ? metricNumber(analytics.body?.contacted_count)
      : null;

  // If analytics does not give us contacted_count — or lead_stats is null
  // (degraded read surface, #3790) — count via the leads API before treating
  // the campaign as empty. A null lead_stats used to zero the utilization
  // and silently disable replenishment for the rest of the run.
  let utilization = 0;
  let utilizationSource = "analytics";
  let effectiveTotalLeads = totalLeads;
  let effectiveContacted = contactedCount;
  if (totalLeads > 0 && contactedCount !== null && contactedCount <= totalLeads * 1.5) {
    effectiveContacted = Math.min(totalLeads, contactedCount);
    utilization = effectiveContacted / totalLeads;
  } else {
    const counts = await client.countLeads(campaignId);
    if (counts.ok && counts.partial) {
      // A partial count is a floor — using it would let the import blow past
      // max_total_leads. Treat as unreadable.
      utilizationSource = "unavailable";
    } else if (counts.ok && metricNumber(counts.total) !== null) {
      effectiveTotalLeads = Math.max(totalLeads || 0, counts.total);
      effectiveContacted = contactedForUtilization(contactedCount, counts);
      utilization = effectiveTotalLeads ? effectiveContacted / effectiveTotalLeads : 0;
      utilizationSource = "leads-api";
    } else {
      utilizationSource = "unavailable";
    }
  }

  if (args.verbose) {
    console.error(
      `Utilization: ${(utilization * 100).toFixed(1)}% (source: ${utilizationSource}, total: ${effectiveTotalLeads}, contacted: ${effectiveContacted})`,
    );
  }

  if (utilizationSource === "unavailable") {
    console.log(
      JSON.stringify({
        skipped: true,
        reason:
          "Lead read surfaces degraded — cannot compute utilization or enforce the total lead cap. Restore complete reads; --force cannot bypass this guard.",
      }),
    );
    return;
  }
  if (effectiveContacted > 0 && !optOutHistory.runs.some((run) =>
    run.run_key === manifest.run_key && run.campaign_id === campaignId))
    fail("Opt-out history unavailable: provider shows prior sending but this run is absent from outreach.db; restore history before replenishing");

  if (utilization < threshold && !args.force) {
    console.log(
      JSON.stringify({
        skipped: true,
        reason:
          effectiveTotalLeads === 0
            ? "No leads visible on any read surface — campaign may have failed import; investigate before replenishing."
            : `Utilization ${(utilization * 100).toFixed(1)}% < threshold ${(threshold * 100).toFixed(0)}%`,
        utilization: Math.round(utilization * 1000) / 10,
        total_leads: effectiveTotalLeads,
        utilization_source: utilizationSource,
      }),
    );
    return;
  }

  // Max total leads guard
  if (effectiveTotalLeads >= maxTotalLeads) {
    console.log(
      JSON.stringify({
        skipped: true,
        reason: `Max total leads reached (${effectiveTotalLeads} >= ${maxTotalLeads})`,
      }),
    );
    return;
  }

  // --- Source new leads ---
  const effectiveBatch = Math.min(
    batchSize,
    maxTotalLeads - effectiveTotalLeads,
  );
  const tempDir = path.join(runDir, "state", "replenish-temp");
  ensureDir(tempDir);
  const outputPath = path.join(tempDir, `leads-${Date.now()}.json`);

  let newLeads = null;
  let leadSource = "none";
  let sourceMeta = null;
  let optedOutCount = 0;

  // Strategy: drain carry-over from initial-launch first, then OS Apollo.
  // Carry-over comes from launch-campaign.js capping the
  // initial import at batch_size — extras land in state/carry-over-leads.json
  // so they're not wasted (and so we don't re-pay Apollo for the same query).
  const carryOverPath = path.join(runDir, "state", "carry-over-leads.json");
  let carryOverRemainder = null;
  if (fs.existsSync(carryOverPath)) {
    const savedCarryOver = readJson(carryOverPath, []);
    if (!Array.isArray(savedCarryOver)) fail("Carry-over leads are malformed; restore before replenishing");
    const filtered = filterConfirmedOptOuts(runDir, savedCarryOver);
    const carryOver = filtered.leads;
    optedOutCount += filtered.excluded.length;
    if (Array.isArray(carryOver) && carryOver.length > 0) {
      const taken = carryOver.slice(0, effectiveBatch);
      const remainder = carryOver.slice(effectiveBatch);
      // Keep the selected batch queued until the provider read/import and
      // local hash checkpoint have succeeded. An uncertain import can then
      // reconcile the same batch against the campaign on the next run.
      carryOverRemainder = remainder;
      newLeads = taken;
      leadSource = "carry-over";
      if (args.verbose) {
        console.error(
          `Carry-over: selected ${taken.length} leads, ${remainder.length} remaining after successful reconciliation.`,
        );
      }
    }
  }

  if (!newLeads && apolloSearch) {
    const unfinished = pendingApolloSource(tempDir);
    if (unfinished) {
      console.log(JSON.stringify({ skipped: true,
        reason: "Prior Apollo source checkpoint is incomplete; review/resume it explicitly before another paid search",
        source_meta: unfinished, source_file: path.relative(runDir, unfinished.path) }));
      process.exitCode = 1;
      return;
    }
    const sourced = await sourceFromApollo(
      envFile,
      apolloSearch,
      effectiveBatch,
      outputPath,
      !!args.verbose,
    );
    newLeads = sourced.leads;
    // Raw unprocessed people remain in source_file, not duplicated into every
    // summary/history record. The counts and completeness stay visible here.
    const { not_enriched_people, ...observation } = sourced.meta;
    sourceMeta = observation;
    leadSource = "apollo";
  }

  if (!newLeads || !newLeads.length) {
    const result = {
      skipped: true,
      reason: sourceMeta?.complete === false ? "Apollo sourcing incomplete; checkpoint retained for review" : "No leads sourced from the configured source",
      utilization: Math.round(utilization * 1000) / 10,
      apollo_available: !!apolloSearch,
      source_meta: sourceMeta,
      source_file: sourceMeta ? path.relative(runDir, outputPath) : null,
      leads_excluded_opt_out: optedOutCount,
    };
    console.log(JSON.stringify(result));
    if (sourceMeta?.complete === false) process.exitCode = 2;
    return;
  }

  // --- Deduplicate against already-imported leads ---
  const importedLeadsPath = path.join(runDir, "state", "imported-leads.json");
  const existingHashes = new Set(readJson(importedLeadsPath, []));
  const sourcedCount = newLeads.length;

  // Missing substitutions are hard errors. Cosmetic name heuristics stay
  // warnings; do not quietly discard usable contacts for style preferences.
  const eligible = filterConfirmedOptOuts(runDir, newLeads);
  newLeads = eligible.leads;
  optedOutCount += eligible.excluded.length;
  const nameChecks = leadNameChecksForSteps(spec.sequence?.steps);
  const nameProblems = new Map();
  const nameWarnings = [];
  if (nameChecks.checkFirstName || nameChecks.checkCompanyName) {
    for (const problem of findLeadNameProblems(newLeads, nameChecks)) {
      if (problem.severity !== "error") { nameWarnings.push(problem); continue; }
      if (!nameProblems.has(problem.email)) nameProblems.set(problem.email, []);
      nameProblems.get(problem.email).push({
        field: problem.field,
        value: problem.value,
        problem: problem.problem,
      });
    }
  }
  for (const problem of findLeadVariableProblems(spec.sequence?.steps, newLeads)) {
    if (!nameProblems.has(problem.email)) nameProblems.set(problem.email, []);
    nameProblems.get(problem.email).push(problem);
  }
  const rejected = [];

  const deduped = [];
  const seenEmails = new Set();
  for (const lead of newLeads) {
    const email = normalizeEmail(lead.email);
    if (!email || seenEmails.has(email)) continue;
    seenEmails.add(email);
    const leadHash = sha256(JSON.stringify({ campaignId, email }));
    if (existingHashes.has(leadHash)) continue;
    if (nameProblems.has(email)) {
      rejected.push({
        ...lead,
        email,
        first_name: lead.firstName || lead.first_name || "",
        company_name: lead.companyName || lead.company_name || "",
        problems: nameProblems.get(email),
        lead_source: leadSource,
        rejected_at: isoNow(),
      });
      continue;
    }
    upsertLead(dbPath, lead);
    deduped.push(buildImportLead({ ...lead, email }));
    if (deduped.length >= effectiveBatch) break;
  }

  const rejectedPath = path.join(runDir, "state", "rejected-leads.json");
  const rejectedReport = {};
  if (rejected.length) {
    const byEmail = new Map(
      readJson(rejectedPath, []).map((entry) => [entry.email, entry]),
    );
    for (const entry of rejected) byEmail.set(entry.email, entry);
    writeJson(rejectedPath, Array.from(byEmail.values()));
    const warning =
      `${rejected.length} sourced lead(s) skipped for invalid or missing values used by the copy and NOT imported: ` +
      rejected
        .slice(0, 20)
        .map((r) => `${r.email} (${r.problems.map((p) => `${p.field} ${JSON.stringify(p.value)}`).join(", ")})`)
        .join("; ") +
      (rejected.length > 20 ? `; … ${rejected.length - 20} more` : "") +
      `. Full lead records and reasons remain in state/rejected-leads.json. Fix the referenced values or copy and add those ` +
      `leads to state/carry-over-leads.json to import them on the next replenishment.`;
    console.error(`WARNING: ${warning}`);
    rejectedReport.leads_rejected_names = rejected.length;
    rejectedReport.rejected_leads_file = "state/rejected-leads.json";
    rejectedReport.warning = warning;
  }

  if (!deduped.length) {
    if (carryOverRemainder !== null) writeJson(carryOverPath, carryOverRemainder);
    console.log(
      JSON.stringify({
        skipped: true,
        reason: rejected.length
          ? "No sourced lead left to import: the rest were already imported or have invalid or missing copy substitutions"
          : optedOutCount ? "No eligible sourced leads remain after confirmed opt-outs and duplicates" : "All sourced leads already imported (duplicates)",
        lead_source: leadSource,
        source_meta: sourceMeta,
        source_file: sourceMeta ? path.relative(runDir, outputPath) : null,
        lead_name_warnings: nameWarnings,
        leads_excluded_opt_out: optedOutCount,
        ...rejectedReport,
      }),
    );
    return;
  }

  // --- Import into campaign ---
  const verifyOnImport =
    spec.campaign?.verify_leads_on_import ?? spec.campaign?.verify_leads ?? true;
  // An earlier import answered with a 5xx may have landed: send only leads
  // that are not in the campaign yet.
  const freshEligible = filterConfirmedOptOuts(runDir, deduped);
  optedOutCount += freshEligible.excluded.length;
  const currentMembers = await client.listLeadEmails(campaignId);
  const leadsToAdd = leadsNotInCampaign(freshEligible.leads, currentMembers);
  const freshTotal = Math.max(effectiveTotalLeads, currentMembers.emails.size);
  if (freshTotal + leadsToAdd.length > maxTotalLeads) {
    console.log(JSON.stringify({ skipped: true, reason: "Fresh lead count would exceed max_total_leads; selected batch retained for reconciliation",
      total_leads: freshTotal, max_total_leads: maxTotalLeads, source_meta: sourceMeta,
      source_file: sourceMeta ? path.relative(runDir, outputPath) : null }));
    return;
  }
  const importRes = leadsToAdd.length
    ? await client.addLeadsToCampaign({
        campaign_id: campaignId,
        leads: leadsToAdd,
        verify_leads_on_import: verifyOnImport,
      })
    : { status: 200, body: { skipped_count: freshEligible.leads.length } };

  if (!(importRes.status >= 200 && importRes.status < 300)) {
    fail(
      `Lead import failed: ${importRes.status} ${JSON.stringify(importRes.body)}` +
        (importRes.status >= 500
          ? ". The batch may have landed; the next run sends only leads not yet in the campaign."
          : ""),
    );
  }

  const importBody = importRes.body || {};
  const imported = Number(
    importBody.leads_uploaded || importBody.created_leads?.length || 0,
  );
  const importSkipped =
    Number(importBody.skipped_count || 0) +
    Number(importBody.duplicated_leads || 0) +
    Number(importBody.in_blocklist || 0) +
    Number(importBody.duplicate_email_count || 0) +
    (leadsToAdd.length ? freshEligible.leads.length - leadsToAdd.length : 0);

  // Persist new lead hashes
  for (const lead of freshEligible.leads) existingHashes.add(sha256(JSON.stringify({ campaignId, email: lead.email })));
  writeJson(importedLeadsPath, Array.from(existingHashes));
  if (carryOverRemainder !== null) writeJson(carryOverPath, carryOverRemainder);

  const importedAt = isoNow();
  for (const lead of freshEligible.leads) {
    upsertRunLead(dbPath, {
      run_key: manifest.run_key,
      email: lead.email,
      campaign_id: campaignId,
      imported_at: importedAt,
      verification_status: verifyOnImport ? "pending" : "skipped",
      last_known_status: "imported",
      ownership_tag: ownership.run_tag_label,
    });
    insertLeadEvent(dbPath, {
      run_key: manifest.run_key,
      email: lead.email,
      event_type: "imported",
      event_at: importedAt,
      payload_json: {
        source: leadSource,
        replenishment: true,
        campaign_id: campaignId,
      },
    });
  }

  // --- Record replenishment event ---
  const event = {
    replenishment_number: history.length + 1,
    lead_source: leadSource,
    source_meta: sourceMeta,
    source_file: sourceMeta ? path.relative(runDir, outputPath) : null,
    lead_name_warnings: nameWarnings,
    leads_excluded_opt_out: optedOutCount,
    utilization_at_trigger: Math.round(utilization * 1000) / 10,
    utilization_source: utilizationSource,
    leads_sourced: sourcedCount,
    leads_deduped: freshEligible.leads.length,
    leads_imported: imported,
    leads_skipped: importSkipped,
    total_leads_before: freshTotal,
    total_leads_after: freshTotal + imported,
    leads_rejected_names: rejected.length,
    ...rejectedReport,
    completed_at: isoNow(),
  };
  history.push(event);
  writeJson(historyPath, history);

  upsertRun(dbPath, {
    run_key: manifest.run_key,
    product_name: spec.product?.name || spec.product_name,
    segment_name:
      spec.segment?.name || spec.segment?.description || spec.segment,
    offer_headline:
      spec.offer?.headline ||
      spec.offer?.name ||
      spec.offer?.description ||
      spec.offer,
    campaign_id: campaignId,
    campaign_name: manifest.campaign?.name || spec.campaign?.name,
    status: "launched",
    created_at: manifest.created_at || spec.created_at || importedAt,
  });

  // Source checkpoints include unresolved people and completeness evidence.
  // Keep them for explicit recovery; a retry may incur additional provider cost.

  console.log(JSON.stringify(event, null, 2));
  if (sourceMeta?.complete === false) process.exitCode = 2;
}

if (require.main === module) main().catch((err) => fail(err.stack || err.message));
module.exports = { sourceFromApollo, pendingApolloSource };
