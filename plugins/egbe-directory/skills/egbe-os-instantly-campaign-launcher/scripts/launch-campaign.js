#!/usr/bin/env node
const { assessCampaignOptOuts } = require("./lib/recipient-exclusion");
const fs = require("fs");
const path = require("path");
const { InstantlyClient } = require("./lib/instantly-client");
const { leadsNotInCampaign } = require("./lib/create-once");
const { selectSenders } = require("./lib/sender-selection");
const { validateLaunchConfig, initialBatchLimit } = require("./lib/run-config");
const { readOptOutHistory, filterConfirmedOptOuts, campaignSafetyReadback, stopConfirmedRecipient } = require("./lib/confirmed-opt-outs");
const {
  initDb,
  upsertRun,
  upsertLead,
  upsertRunLead,
  insertLeadEvent,
} = require("./lib/outreach-db");
const {
  ensureDir,
  readJson,
  writeJson,
  sha256,
  stableStringify,
  normalizeEmail,
  parseArgs,
  isoNow,
  ymd,
  slugify,
  deriveSenderName,
  replaceSenderNameToken,
  buildImportLead,
  findLeadNameProblems,
  leadNameChecksForSteps,
  findLeadVariableProblems,
  loadRunEnv,
  ensureRunEnv,
  getOsConfig,
  campaignOwnershipStatus,
  assertCampaignNotForeign,
} = require("./lib/helpers");
const {
  reconcileRunIdentity,
  reconcileInstantlyAttribution,
} = require("./lib/gtm-identity");

function fail(message) {
  console.error(`ERROR: ${message}`);
  process.exit(1);
}

// Instantly's per-lead `verification_status` (GET /leads?campaign_id=…):
// 1 = valid, -1 = invalid, 11 / 12 = pending. Every other code (-2 risky,
// -3 catch-all, -4 job change, anything unknown) is counted as "risky": it is
// not known how campaign lead_stats counts those, so for the threshold they
// count as invalid (fail safe) and are listed separately.
const LEAD_VERIFICATION_VALID = new Set([1]);
const LEAD_VERIFICATION_INVALID = new Set([-1]);
const LEAD_VERIFICATION_PENDING = new Set([11, 12]);

/**
 * Every lead in a campaign, paging GET /leads 100 at a time. ok=false: the
 * listing could not be read completely (error status, unexpected body, or a
 * cursor the gateway ignores).
 */
async function listCampaignLeads(client, campaignId) {
  const leads = [];
  const cursors = new Set();
  let cursor;
  let status = null;
  for (let page = 0; page < 1000; page++) {
    const res = await client.listLeads(campaignId, {
      limit: 100,
      starting_after: cursor,
    });
    status = res.status;
    if (!(res.status >= 200 && res.status < 300)) return { ok: false, status, leads };
    const items = Array.isArray(res.body) ? res.body : res.body?.items;
    if (!Array.isArray(items)) return { ok: false, status, leads };
    leads.push(...items);
    if (items.length < 100) return { ok: true, status, leads };
    const lastId = items[items.length - 1]?.id;
    // Same page again: the cursor was ignored and the list cannot be trusted.
    if (!lastId || cursors.has(lastId)) return { ok: false, status, leads };
    cursors.add(lastId);
    cursor = lastId;
  }
  return { ok: false, status, leads };
}

/**
 * Per-lead verification counts for the WHOLE campaign — the fallback when
 * campaign lead_stats is null/empty (#3790). fileEmails only measures how
 * many of this run's leads are visible yet (file_visible). has_status=false:
 * no lead carried a verification_status field, i.e. this surface exposes no
 * verification data either. bad = invalid + risky, the numerator of the
 * invalid-lead threshold.
 */
async function readLeadVerification(client, campaignId, fileEmails = null) {
  const listing = await listCampaignLeads(client, campaignId);
  const out = {
    ok: false,
    status: listing.status,
    has_status: false,
    total: 0,
    file_visible: 0,
    valid: 0,
    invalid: 0,
    risky: 0,
    bad: 0,
    pending: 0,
    invalid_leads: [],
  };
  if (!listing.ok) return out;
  let unassigned = 0;
  for (const lead of listing.leads) {
    const email = String(lead?.email || "").trim().toLowerCase();
    if (!email) continue;
    out.total += 1;
    if (fileEmails && fileEmails.has(email)) out.file_visible += 1;
    if (
      lead.verification_status === undefined ||
      lead.verification_status === null
    ) {
      // Next to leads that have a status: not picked up by the job yet.
      unassigned += 1;
      continue;
    }
    out.has_status = true;
    const code = Number(lead.verification_status);
    if (LEAD_VERIFICATION_VALID.has(code)) out.valid += 1;
    else if (LEAD_VERIFICATION_PENDING.has(code)) out.pending += 1;
    else {
      const kind = LEAD_VERIFICATION_INVALID.has(code) ? "invalid" : "risky";
      out[kind] += 1;
      out.invalid_leads.push({
        email,
        id: lead.id ?? null,
        verification_status: lead.verification_status,
        kind,
      });
    }
  }
  out.pending += unassigned;
  out.bad = out.invalid + out.risky;
  out.ok = true;
  return out;
}

/**
 * Rerun after a failed gate: every lead listed in state/invalid-leads.json
 * whose email is no longer in the leads file is deleted from the campaign —
 * dropping it from the file alone would leave it in the campaign, where it
 * gets mailed on activation. Ids are re-read from the live campaign (a lead
 * already gone counts as removed). Deletes are not retried on 5xx. Returns
 * { ok, deleted, already_absent, failed, kept_in_file, reason }.
 */
async function removeDroppedInvalidLeads(client, campaignId, invalidRecord, fileEmails) {
  const result = {
    ok: true,
    deleted: [],
    already_absent: [],
    failed: [],
    kept_in_file: [],
    reason: null,
  };
  const listed = Array.isArray(invalidRecord?.leads) ? invalidRecord.leads : [];
  const dropped = [];
  for (const entry of listed) {
    const email = String(entry?.email || "").trim().toLowerCase();
    if (!email) continue;
    if (fileEmails.has(email)) result.kept_in_file.push(email);
    else dropped.push({ ...entry, email });
  }
  if (!dropped.length) return result;
  const live = await listCampaignLeads(client, campaignId);
  if (!live.ok) {
    result.ok = false;
    result.reason =
      `the campaign's leads could not be read (status ${live.status}) to remove ` +
      `${dropped.length} lead(s) dropped from the leads file after the last failed verification gate`;
    result.failed = dropped.map((d) => ({ email: d.email, id: d.id ?? null, status: live.status }));
    return result;
  }
  const idsByEmail = new Map();
  for (const lead of live.leads) {
    const email = String(lead?.email || "").trim().toLowerCase();
    if (!email || !lead?.id) continue;
    if (!idsByEmail.has(email)) idsByEmail.set(email, []);
    idsByEmail.get(email).push(lead.id);
  }
  for (const entry of dropped) {
    const ids = idsByEmail.get(entry.email) || [];
    if (!ids.length) {
      result.already_absent.push(entry.email);
      continue;
    }
    for (const id of ids) {
      const res = await client.deleteLead(id);
      if (res.status >= 200 && res.status < 300) {
        result.deleted.push({
          email: entry.email,
          id,
          verification_status: entry.verification_status ?? null,
          kind: entry.kind ?? null,
        });
      } else {
        result.ok = false;
        result.failed.push({ email: entry.email, id, status: res.status });
      }
    }
  }
  if (!result.ok) {
    result.reason = `${result.failed.length} delete(s) failed`;
  }
  return result;
}

async function waitForVerification(client, campaignId, spec, opts = {}) {
  const importedCount = opts.importedCount ?? null;
  const skippedCount = opts.skippedCount ?? null;
  // This run's leads (the leads file) and a lower bound of how many of them
  // must be visible in the campaign: a lagging leads listing showing 10 of
  // 50 must not pass as "0 pending". The counts themselves cover the whole
  // campaign.
  const fileEmails = opts.fileEmails ?? null;
  const expectedLeads = Math.max(0, Number(opts.expectedLeads) || 0);
  // Defaults raised after observing ~20m verification windows in production
  // for 50–100 lead batches. Stuck-detect breaks early when Instantly's
  // verification queue stops making progress (pending count stable across
  // N polls), so we don't burn the full timeout on a hung backlog.
  const maxWaitMs =
    (spec.campaign.verification_timeout_minutes || 45) * 60 * 1000;
  const pollIntervalMs = 15_000;
  const maxInvalidPct = spec.campaign.max_invalid_lead_pct ?? 5;
  const stuckPollLimit = Math.max(
    3,
    spec.campaign.verification_stuck_polls || 8,
  );
  const started = Date.now();

  let lastPending = null;
  let stuckCount = 0;
  let lastPerLeadPending = null;
  let perLeadStuckCount = 0;
  let lastSeenTotal = 0;
  let nullStatsPolls = 0;
  // Last readable observation, for the "still pending" result at the end of
  // the wait budget.
  let lastObserved = null;

  // A 2xx from the bulk add is not proof the batch landed: 0 uploaded and
  // 0 already-present means every lead was rejected, and on a reused
  // campaign the leads API showing OLD leads must not mask that. Counters
  // are null for callers that did not supply them (legacy behavior).
  const batchLanded =
    importedCount == null || importedCount > 0 || (skippedCount ?? 0) > 0;

  // The invalid-rate gate failed: the caller writes the invalid addresses to
  // the run dir and aborts before activation.
  const gateFailure = async (reason, counts, perLead = null) => {
    let invalidLeads = perLead?.ok ? perLead.invalid_leads : null;
    if (!invalidLeads) {
      // lead_stats has counts only — read the per-lead listing for the
      // addresses (whole campaign, like lead_stats).
      const listing = await readLeadVerification(client, campaignId, fileEmails);
      invalidLeads = listing.ok ? listing.invalid_leads : [];
    }
    return {
      gate_failed: true,
      failure_reason: reason,
      invalid_leads: invalidLeads,
      max_invalid_lead_pct: maxInvalidPct,
      ...counts,
    };
  };

  // Read-surface triage, run when neither lead_stats nor the per-lead
  // verification_status yields numbers for stuckPollLimit polls: cross-check
  // the leads API once, reconcile the add-leads counters, and either report a
  // failed import or a degraded read surface (#3790) — instead of burning the
  // whole timeout on identical broken polls. A degraded result means the
  // invalid-lead gate was NOT enforced; the caller does not activate unless
  // campaign.allow_unverified_activation is true.
  const triageDegradedReads = async (detailsSummary, perLead) => {
    if (!batchLanded) {
      return {
        import_failed: true,
        import_failure_reason:
          `${detailsSummary} after ${nullStatsPolls} polls, and the add-leads call reported ` +
          `0 uploaded and 0 already-present — the new batch never landed (all leads ` +
          `invalid/incomplete?). Campaign was NOT activated.`,
      };
    }
    const perLeadSummary = !perLead
      ? "the per-lead verification_status was not read"
      : perLead.ok
        ? "the leads list exposes no per-lead verification_status"
        : `the leads list is unreadable for per-lead verification_status (status ${perLead.status})`;
    const counts = await client.countLeads(campaignId);
    if (counts.ok && counts.total > 0) {
      const skippedReason =
        `${detailsSummary} after ${nullStatsPolls} polls and ${perLeadSummary}, but the leads API ` +
        `reports ${counts.total} leads in the campaign` +
        (importedCount != null
          ? ` and the add-leads call reported ${importedCount} uploaded`
          : "") +
        `. Both verification read surfaces are unavailable (#3790): the max_invalid_lead_pct ` +
        `(${maxInvalidPct}%) gate was NOT enforced for this launch.`;
      console.error(`WARNING: ${skippedReason}`);
      return {
        verifiedLeads: 0,
        invalidLeads: 0,
        totalLeads: counts.total,
        invalidPct: 0,
        degraded_read_surface: true,
        verification_unread: true,
        stuck_reason: skippedReason,
      };
    }
    if (counts.ok) {
      return {
        import_failed: true,
        import_failure_reason:
          `No leads visible (${detailsSummary}) AND the leads API returns zero after ` +
          `${nullStatsPolls} polls` +
          (importedCount != null
            ? ` (the add-leads call reported ${importedCount} uploaded)`
            : "") +
          `. The lead import most likely failed silently — inspect the add-leads response in the ` +
          `launch log and confirm the payload used the {"payload": {...}} gateway wrapper. ` +
          `Campaign was NOT activated.`,
      };
    }
    const skippedReason =
      `${detailsSummary} and the leads list (status ${counts.status}) is unreadable after ` +
      `${nullStatsPolls} polls` +
      (importedCount != null
        ? `; the add-leads call reported ${importedCount} uploaded`
        : "") +
      `. Both verification read surfaces are unavailable (#3790): the max_invalid_lead_pct ` +
      `(${maxInvalidPct}%) gate was NOT enforced for this launch.`;
    console.error(`WARNING: ${skippedReason}`);
    return {
      verifiedLeads: 0,
      invalidLeads: 0,
      totalLeads: importedCount ?? 0,
      invalidPct: 0,
      degraded_read_surface: true,
      verification_unread: true,
      stuck_reason: skippedReason,
    };
  };

  console.log("Waiting for lead verification to complete...");
  while (Date.now() - started < maxWaitMs) {
    await new Promise((r) => setTimeout(r, pollIntervalMs));

    // The analytics response is not used below — it existed only as a
    // reachability gate, and a down analytics route (#3790: campaigns/
    // analytics 404s) short-circuited the poll so the degraded-read triage
    // never ran. Log and continue with campaign details instead.
    const res = await client.campaignAnalytics(campaignId);
    if (!(res.status >= 200 && res.status < 300)) {
      console.log(
        `Analytics unreadable (status ${res.status}); continuing with campaign details.`,
      );
    }

    // Instantly exposes verification stats through campaign analytics
    // after verify_leads_on_import completes. We use the campaign details
    // endpoint to check if leads have been processed.
    const details = await client.getCampaign(campaignId);
    const detailsReadable = details.status >= 200 && details.status < 300;
    const body = detailsReadable ? details.body || {} : {};
    const leadStats = body.lead_stats || {};
    const totalLeads = leadStats.total || 0;
    const verifiedLeads = leadStats.verified || 0;
    const invalidLeads = leadStats.invalid || 0;
    const pendingVerification = leadStats.pending_verification || 0;

    // Diagnostic poll log: live runs surfaced `lead_stats: null` from the API,
    // which left the gate working semi-blind. Logging the raw stats object on
    // every poll lets us see whether Instantly is filling lead_stats at all.
    console.log(
      detailsReadable
        ? `Verification poll: lead_stats=${JSON.stringify(body.lead_stats ?? null)} totalLeads=${totalLeads}`
        : `Verification poll: campaign details unreadable (status ${details.status})`,
    );

    if (totalLeads === 0) {
      // lead_stats null/empty or details unreadable (#3790). A production run
      // once burned a 60-minute timeout on 29 identical null polls, and a
      // later one skipped the gate entirely after 8 — while the per-lead
      // verification_status showed 12.7% invalid. Read the per-lead status
      // instead of giving up on the gate. Skipped when the batch never
      // landed: old leads on a reused campaign must not mask that.
      const perLead = batchLanded
        ? await readLeadVerification(client, campaignId, fileEmails)
        : null;
      if (perLead?.ok && perLead.has_status && perLead.total > 0) {
        nullStatsPolls = 0;
        // Leads of this run not visible yet count as pending, and in the
        // denominator.
        const notVisible = Math.max(0, expectedLeads - perLead.file_visible);
        const denominator = perLead.total + notVisible;
        const pendingLeads = perLead.pending + notVisible;
        const counts = {
          verifiedLeads: perLead.valid,
          invalidLeads: perLead.bad,
          riskyLeads: perLead.risky,
          pendingLeads,
          totalLeads: denominator,
          invalidPct: (perLead.bad / denominator) * 100,
          source: "per_lead_verification_status",
        };
        lastObserved = counts;
        console.log(
          `Verification progress (per-lead verification_status; lead_stats unavailable): ` +
            `valid=${perLead.valid} invalid=${perLead.invalid} risky=${perLead.risky} ` +
            `pending=${perLead.pending} total=${perLead.total}` +
            (expectedLeads
              ? ` (this run's leads visible: ${perLead.file_visible} of >=${expectedLeads})`
              : ""),
        );
        // Pending (or not yet visible) leads can only add to the invalid
        // count, so a rate already over the threshold is final.
        if (counts.invalidPct > maxInvalidPct) {
          return await gateFailure(
            `Lead verification failed: ${counts.invalidPct.toFixed(1)}% invalid (threshold: ${maxInvalidPct}%) — ` +
              `${perLead.bad} of ${denominator} leads are invalid` +
              (perLead.risky
                ? ` (${perLead.invalid} invalid + ${perLead.risky} risky / catch-all, counted as invalid)`
                : "") +
              (pendingLeads
                ? ` and ${pendingLeads} are still pending (the rate can only go up)`
                : "") +
              ` [source: per-lead verification_status; campaign lead_stats was unavailable]. ` +
              `Campaign was NOT activated.`,
            counts,
            perLead,
          );
        }
        if (pendingLeads > 0) {
          // Same stuck rule as the lead_stats path: a pending count that does
          // not move for verification_stuck_polls polls is a hung queue.
          if (lastPerLeadPending !== null && pendingLeads === lastPerLeadPending) {
            perLeadStuckCount += 1;
            if (perLeadStuckCount >= stuckPollLimit) {
              const pendingReason =
                `Verification appears stuck: ${pendingLeads} leads still pending after ` +
                `${perLeadStuckCount} consecutive polls (~${Math.round((perLeadStuckCount * pollIntervalMs) / 60000)}m ` +
                `no progress); ${perLead.valid} valid + ${perLead.bad} invalid/risky observed so far ` +
                `(${counts.invalidPct.toFixed(1)}% invalid, under the ${maxInvalidPct}% threshold) ` +
                `[source: per-lead verification_status]. Campaign was NOT activated. Rerun the same launch ` +
                `command later (the gate is re-checked), raise verification_stuck_polls / ` +
                `verification_timeout_minutes, or set campaign.allow_unverified_activation: true to activate ` +
                `on the partial result.`;
              console.error(`WARNING: ${pendingReason}`);
              return {
                ...counts,
                stuck: true,
                verification_pending: true,
                pending_reason: pendingReason,
              };
            }
          } else {
            perLeadStuckCount = 0;
          }
          lastPerLeadPending = pendingLeads;
          continue;
        }
        console.log(
          `Verification complete (per-lead verification_status): ${perLead.valid} valid, ` +
            `${perLead.invalid} invalid, ${perLead.risky} risky ` +
            `(${counts.invalidPct.toFixed(1)}% invalid+risky — within ${maxInvalidPct}% threshold)`,
        );
        return counts;
      }
      nullStatsPolls += 1;
      if (nullStatsPolls >= stuckPollLimit) {
        return await triageDegradedReads(
          detailsReadable
            ? "campaign details never exposed lead_stats"
            : `campaign details unreadable (status ${details.status})`,
          perLead,
        );
      }
      continue;
    }
    nullStatsPolls = 0;
    lastSeenTotal = totalLeads;
    lastObserved = {
      verifiedLeads,
      invalidLeads,
      pendingLeads: pendingVerification,
      totalLeads,
      invalidPct: (invalidLeads / totalLeads) * 100,
      source: "lead_stats",
    };

    console.log(
      `Verification progress: verified=${verifiedLeads} invalid=${invalidLeads} pending=${pendingVerification} total=${totalLeads}`,
    );

    if (pendingVerification > 0) {
      // Stuck-detect: if pending count hasn't moved for stuckPollLimit polls,
      // treat the verification queue as hung and surface a degraded result
      // instead of waiting out the full timeout.
      if (lastPending !== null && pendingVerification === lastPending) {
        stuckCount += 1;
        if (stuckCount >= stuckPollLimit) {
          // SKILL.md step 4a: "If invalid leads exceed the threshold, the
          // launcher aborts." Stuck-detect must honour the same contract on
          // partial data — a stuck queue with 30% invalid is still a bad
          // launch and we'd rather pause it than activate quietly.
          const partialInvalidPct =
            totalLeads > 0 ? (invalidLeads / totalLeads) * 100 : 0;
          if (partialInvalidPct > maxInvalidPct) {
            return await gateFailure(
              `Lead verification stuck AND invalid rate already exceeds threshold: ` +
                `${partialInvalidPct.toFixed(1)}% invalid (threshold: ${maxInvalidPct}%). ` +
                `${invalidLeads} of ${totalLeads} processed leads are invalid; ${pendingVerification} ` +
                `still pending after ${stuckCount} polls. Refusing to activate. Review lead source.`,
              lastObserved,
            );
          }
          // A hung queue is "still pending", not a pass: no activation
          // (unless campaign.allow_unverified_activation), rerun later.
          const pendingReason =
            `Verification appears stuck: ${pendingVerification} leads still pending after ` +
            `${stuckCount} consecutive polls (~${Math.round((stuckCount * pollIntervalMs) / 60000)}m no progress); ` +
            `${verifiedLeads} verified + ${invalidLeads} invalid observed so far (${partialInvalidPct.toFixed(1)}% ` +
            `invalid, under the ${maxInvalidPct}% threshold) [source: campaign lead_stats]. Campaign was NOT ` +
            `activated. Rerun the same launch command later (the gate is re-checked), raise ` +
            `verification_stuck_polls / verification_timeout_minutes, or set ` +
            `campaign.allow_unverified_activation: true to activate on the partial result.`;
          console.error(`WARNING: ${pendingReason}`);
          return {
            ...lastObserved,
            invalidPct: partialInvalidPct,
            stuck: true,
            verification_pending: true,
            pending_reason: pendingReason,
          };
        }
      } else {
        stuckCount = 0;
      }
      lastPending = pendingVerification;
      continue;
    }

    // All leads processed — check quality
    const invalidPct = (invalidLeads / totalLeads) * 100;
    if (invalidPct > maxInvalidPct) {
      return await gateFailure(
        `Lead verification failed: ${invalidPct.toFixed(1)}% invalid (threshold: ${maxInvalidPct}%). ` +
          `${invalidLeads} of ${totalLeads} leads are invalid [source: campaign lead_stats]. ` +
          `Campaign was NOT activated.`,
        lastObserved,
      );
    }

    console.log(
      `Verification complete: ${verifiedLeads} verified, ${invalidLeads} invalid (${invalidPct.toFixed(1)}% — within ${maxInvalidPct}% threshold)`,
    );
    return { verifiedLeads, invalidLeads, totalLeads, invalidPct, source: "lead_stats" };
  }

  // Wait budget spent with leads still pending: not a crash and not an
  // activation — the caller records the state and asks for a rerun.
  const minutes = Math.round(maxWaitMs / 60000);
  const observed = lastObserved
    ? `last seen: valid=${lastObserved.verifiedLeads} invalid=${lastObserved.invalidLeads} ` +
      `pending=${lastObserved.pendingLeads} total=${lastObserved.totalLeads}, source ${lastObserved.source}`
    : `last seen total=${lastSeenTotal}, pending=${lastPending}`;
  return {
    ...(lastObserved || {}),
    verification_pending: true,
    pending_reason:
      `Lead verification still pending after ${minutes} minutes (${observed}). ` +
      `Campaign was NOT activated. Rerun the same launch command later: the verification gate is ` +
      `re-checked before activation and leads already in the campaign are not re-sent. Raise ` +
      `campaign.verification_timeout_minutes to wait longer in one run.`,
  };
}

// Activation needs a verification gate that ran to completion (or a gate
// switched off in the spec). Returns { blocked, warning }: blocked is the
// launch_status to report instead of activating (the launcher then exits 2),
// warning the reason printed in the NOT ENFORCED banner.
//   - pending after the wait budget: always blocked, rerun later
//   - stuck lead_stats queue / both stat sources unreadable: blocked unless
//     campaign.allow_unverified_activation is true
function verificationActivationBlock(result, allowUnverified) {
  if (!result) return { blocked: null, warning: null };
  if (result.verification_pending && result.stuck) {
    return {
      blocked: allowUnverified ? null : "verification_pending",
      warning: result.pending_reason,
    };
  }
  if (result.verification_pending) {
    return { blocked: "verification_pending", warning: null };
  }
  if (result.verification_unread) {
    return {
      blocked: allowUnverified ? null : "verification_unread",
      warning: result.stuck_reason,
    };
  }
  return { blocked: null, warning: null };
}

// Instantly's campaign_schedule.timezone enum rejects several IANA names that
// look obviously valid (e.g. America/New_York). Documenting the workaround in
// references/instantly-ops.md was not enough — every fresh agent re-discovers
// the rejection through a 400 from /api/v2/campaigns. Translate in code and
// warn so the run-spec author sees what we did to their input.
const TIMEZONE_ALIASES = {
  "America/New_York": "America/Detroit",
};

function resolveTimezone(tz) {
  if (typeof tz !== "string" || !tz) return tz;
  const aliased = TIMEZONE_ALIASES[tz];
  if (aliased && aliased !== tz) {
    console.error(
      `WARNING: campaign.schedule.timezone "${tz}" is rejected by Instantly's enum; ` +
        `using alias "${aliased}" (same effective offset). See references/instantly-ops.md.`,
    );
    return aliased;
  }
  return tz;
}

function mapDays(days) {
  if (!days) return undefined;
  // Numeric keys ("0" = Sunday … "6" = Saturday), in any subset: {"2": true}
  // used to fall through to the name lookup and come out as all false.
  if (Object.keys(days).some((key) => /^[0-6]$/.test(key))) {
    return Object.fromEntries(
      [0, 1, 2, 3, 4, 5, 6].map((d) => [d, !!days[String(d)]]),
    );
  }
  return {
    0: !!days.sunday,
    1: !!days.monday,
    2: !!days.tuesday,
    3: !!days.wednesday,
    4: !!days.thursday,
    5: !!days.friday,
    6: !!days.saturday,
  };
}

function compactLabel(value, fallback) {
  const raw = String(value || "").trim();
  if (!raw) return fallback;
  return raw.replace(/\s+/g, " ").slice(0, 42);
}

function buildCampaignName(spec) {
  const datePart = spec.created_at
    ? String(spec.created_at).slice(0, 10)
    : ymd();
  const product = compactLabel(
    spec.product?.name || spec.product_name,
    "Product",
  );
  const segment = compactLabel(
    spec.segment?.name || spec.segment?.description || spec.segment,
    "Segment",
  );
  const offer = compactLabel(
    spec.offer?.headline ||
      spec.offer?.name ||
      spec.offer?.description ||
      spec.offer,
    "Offer",
  );
  return `${product} | ${segment} | ${offer} | ${datePart}`;
}

function escapeHtml(s) {
  // Escape `"` and `'` too — bodies are wrapped in `<a href="...">` and could
  // otherwise be embedded in attribute context, where unescaped quotes break
  // out of the attribute and form a tiny XSS vector if a lead-supplied token
  // ever ends up rendered server-side. Cheap to escape, no downside.
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Append UTM tracking params to a URL so traffic from cold-email lands as
// (source=instantly, medium=email, campaign=<run_key>) in product analytics.
// per-run attribution including purchase signals via Stripe metadata.
//   - `utm_source=instantly`        — distinguishes cold email from organic / Reddit / ads
//   - `utm_medium=email`            — canonical medium for outbound email
//   - `utm_campaign=<run_key>`      — distinguishes runs of the same product
// Existing UTM values are replaced so live URLs match the immutable binding
// persisted in manifest.json and conclusion.json.
function addUtmTags(url, runKey) {
  if (!runKey || typeof url !== "string") return url;
  try {
    const parsed = new URL(url);
    parsed.searchParams.set("utm_source", "instantly");
    parsed.searchParams.set("utm_medium", "email");
    parsed.searchParams.set("utm_campaign", runKey);
    return parsed.toString();
  } catch {
    const hashIndex = url.indexOf("#");
    const base = hashIndex >= 0 ? url.slice(0, hashIndex) : url;
    const fragment = hashIndex >= 0 ? url.slice(hashIndex) : "";
    const sep = base.includes("?") ? "&" : "?";
    return `${base}${sep}utm_source=instantly&utm_medium=email&utm_campaign=${encodeURIComponent(runKey)}${fragment}`;
  }
}

/**
 * Auto-convert a plain-text body (with `\n\n` paragraph breaks and bare URLs)
 * into HTML so Instantly delivers consistent rendering across email clients.
 *
 * Rules (Instantly editor-native markup — the CREATE endpoint rewrites
 * `<p>` blocks into margin-less `<div>`s, collapsing paragraph spacing in
 * the delivered mail, while PATCH keeps `<p>` verbatim; emitting the editor's
 * own format renders identically on both API paths):
 *   - every line → its own `<div>...</div>`
 *   - `\n\n` (blank line) → explicit `<div><br /></div>` separator
 *   - markdown links `[anchor](url)` → `<a href="url+UTMs">anchor</a>` so
 *     marketologist controls the visible CTA wording per product
 *     (e.g. `[try Rolloo free](https://rolloo.app/)`)
 *   - bare http(s):// URLs → `<a href="url+UTMs">url</a>` (display = clean URL,
 *     UTMs hidden in href so the email body stays human-looking)
 *   - merge tokens like `{{firstName}}` are preserved intact (HTML-safe by
 *     virtue of escaping happening before token substitution on Instantly's
 *     side; we never escape the braces themselves).
 *
 * Idempotent: if the body already contains HTML, preserve its markup while
 * reconciling HTTP(S) anchor hrefs to the canonical UTM tuple.
 */
function plainToHtmlBody(body, runKey) {
  if (typeof body !== "string" || !body.trim()) return body;
  // Detect any HTML tag, not just the original short list — `<strong>`, `<em>`,
  // `<ul>`/`<ol>`/`<li>`, `<h1>..<h6>`, `<blockquote>` etc. all signal that the
  // body was authored as HTML on purpose. Pre-fix this regex only matched the
  // original 6 tags and silently re-wrapped richer HTML in extra `<p>`/`<br>`,
  // which double-escaped the body on send.
  if (/<\s*\/?\s*[a-zA-Z][\w-]*(\s|\/?\s*>)/.test(body)) {
    return body.replace(
      /(<a\b[^>]*\bhref\s*=\s*)(["'])(https?:\/\/[^"']+)\2/gi,
      (_, prefix, quote, url) =>
        `${prefix}${quote}${addUtmTags(url, runKey)}${quote}`,
    );
  }

  // Two-pass extraction so escapeHtml doesn't corrupt the link markup.
  // Pass 1: pull markdown links out of body, replace with sentinels we can
  //         reinsert AFTER escapeHtml runs (so the anchor + href bypass
  //         escaping). Sentinel uses a private-use Unicode char so no
  //         possible body content collides.
  const linkRegistry = [];
  const SENTINEL_OPEN = "OCLINK";
  const SENTINEL_CLOSE = "OCLINK";
  const withSentinels = body.replace(
    /\[([^\]\n]+)\]\(([^)\s]+)\)/g,
    (_, anchor, url) => {
      const idx = linkRegistry.length;
      linkRegistry.push({ url: addUtmTags(url, runKey), anchor });
      return `${SENTINEL_OPEN}${idx}${SENTINEL_CLOSE}`;
    },
  );

  // Pass 2: paragraphs + escapeHtml + raw-URL linkify (bare URLs stay
  // displayed as the clean original URL but href carries UTMs).
  const linkifyBare = (s) =>
    s.replace(/(https?:\/\/[^\s<>"]+)/g, (url) => {
      const utmUrl = addUtmTags(url, runKey);
      // Don't double-escape — escapeHtml already ran on `s`. UTMs were added
      // after escape so amp/equals stay safe in href context (they are
      // URL-safe characters that don't need HTML escaping in href values).
      return `<a href="${utmUrl}">${url}</a>`;
    });

  const lines = withSentinels
    .replace(/^\n+/, "")
    .replace(/\n+$/, "")
    .replace(/\n{2,}/g, "\n\n")
    .split("\n");
  const rendered = lines
    .map((line) => {
      if (line.trim() === "") return "<div><br /></div>";
      return `<div>${linkifyBare(escapeHtml(line))}</div>`;
    })
    .join("");

  // Pass 3: substitute markdown-link sentinels back in. escapeHtml turned
  // SENTINEL_OPEN/CLOSE into themselves (private-use chars are passthrough),
  // so the regex still matches.
  return rendered.replace(
    new RegExp(`${SENTINEL_OPEN}(\\d+)${SENTINEL_CLOSE}`, "g"),
    (_, idx) => {
      const entry = linkRegistry[Number(idx)];
      if (!entry) return "";
      return `<a href="${entry.url}">${escapeHtml(entry.anchor)}</a>`;
    },
  );
}

// Map run-spec step semantics to Instantly's `delay` semantics:
//   run-spec  step.delay_days[N] = days to wait BEFORE step N is sent
//   Instantly step.delay[N]      = days to wait AFTER step N before step N+1
// Instantly therefore needs the *next* step's delay attached to the
// current step. Step 1's run-spec delay drops off the front (Instantly
// activates the first step at lead-import time, not on a schedule); the
// last step's `delay` is unused by Instantly's runtime. We warn loudly
// if step 1 carries a non-zero delay, so a "wait 2 days before the
// first email" intent doesn't silently disappear into the shift.
function instantlyStepDelays(steps) {
  if (!Array.isArray(steps) || steps.length === 0) {
    // The main() validator catches empty sequences upstream, but defending
    // here too means a future caller (or a refactor that bypasses main)
    // gets a clear error instead of a silent empty payload that Instantly
    // rejects with a generic 400.
    fail(
      "sequence.steps is empty — Instantly will reject the campaign with a 400. " +
        "Generate at least one email step before calling launch-campaign.js.",
    );
  }
  if (steps.length > 0) {
    const firstDelay = steps[0].delay_days ?? steps[0].delay ?? 0;
    if (firstDelay > 0) {
      console.error(
        `WARNING: step 1 delay_days=${firstDelay} will be ignored — Instantly fires the first step on lead import, not on a delay. ` +
          `If you need a wait before the first email, configure it at the campaign-schedule level instead.`,
      );
    }
  }
  return steps.map((_, i) => {
    const next = steps[i + 1];
    if (!next) return 0;
    return next.delay_days ?? next.delay ?? 0;
  });
}

function sequenceFingerprint(spec, emailList, senderName) {
  const delays = instantlyStepDelays(spec.sequence.steps);
  const steps = spec.sequence.steps.map((step, i) => ({
    delay: delays[i],
    delay_unit: step.delay_unit || "days",
    subject: step.subject,
    // Fingerprint over the *delivered* HTML body so a plain-text vs HTML
    // change in the source actually produces a different fingerprint.
    // Includes UTM tags (per run_key) — same run_key produces stable hashes;
    // different run_keys (different campaigns) get distinct fingerprints
    // which is correct.
    body: plainToHtmlBody(
      replaceSenderNameToken(step.body, senderName),
      spec.run_key,
    ),
  }));
  return sha256(stableStringify({ steps, emailList }));
}

function buildCampaignPayload(spec, emailList, senderName) {
  const delays = instantlyStepDelays(spec.sequence.steps);
  // Tracking is an explicit run choice; launch defaults do not add trackers.
  const seq = spec.sequence.steps.map((step, i) => ({
    type: "email",
    delay: delays[i],
    delay_unit: step.delay_unit || "days",
    variants: [
      {
        subject: replaceSenderNameToken(step.subject, senderName),
        body: plainToHtmlBody(
          replaceSenderNameToken(step.body, senderName),
          spec.run_key,
        ),
      },
    ],
  }));
  return {
    name: spec.campaign.name,
    campaign_schedule: {
      schedules: [
        {
          name: spec.campaign.schedule.name,
          timing: spec.campaign.schedule.timing,
          days: mapDays(spec.campaign.schedule.days),
          timezone: resolveTimezone(spec.campaign.schedule.timezone),
        },
      ],
    },
    sequences: [{ steps: seq }],
    email_gap: spec.campaign.email_gap_minutes,
    daily_limit: spec.campaign.daily_limit,
    daily_max_leads: spec.campaign.daily_max_new_leads,
    stop_on_reply: spec.campaign.stop_on_reply ?? true,
    stop_on_auto_reply: spec.campaign.stop_on_auto_reply ?? true,
    insert_unsubscribe_header: spec.campaign.insert_unsubscribe_header ?? true,
    open_tracking: spec.campaign.open_tracking ?? false,
    link_tracking: spec.campaign.link_tracking ?? false,
    email_list: emailList,
    email_tag_list: spec.campaign.email_tag_list,
  };
}

async function findTagByLabel(client, label) {
  // Shared fleet workspaces accumulate hundreds of ownership tags; a single
  // limit=100 page misses older tags and the subsequent create 409s. Page
  // through the full list (bounded) before concluding the tag is absent.
  let cursor;
  let prevFirstId = null;
  for (let page = 0; page < 50; page++) {
    const res = await client.listCustomTags(100, cursor);
    if (!(res.status >= 200 && res.status < 300)) return null;
    const items = Array.isArray(res.body?.items) ? res.body.items : [];
    // A gateway that drops the starting_after param re-serves page 1 forever
    // — detect the repeated page and stop instead of scanning 50 copies.
    const firstId = items[0]?.id ?? null;
    if (firstId != null && firstId === prevFirstId) return null;
    prevFirstId = firstId;
    const found = items.find((tag) => tag.label === label);
    if (found) return found;
    if (items.length < 100) return null;
    const nextCursor =
      res.body?.next_starting_after || items[items.length - 1]?.id;
    if (!nextCursor || nextCursor === cursor) return null;
    cursor = nextCursor;
  }
  return null;
}

async function ensureTag(client, label, description) {
  const found = await findTagByLabel(client, label);
  if (found) return found;
  const created = await client.createCustomTag({ label, description });
  if (created.status >= 200 && created.status < 300) return created.body;
  // 409: lost the existence race. 5xx: the tag may have been created before
  // the gateway gave up (creating calls are not repeated).
  if (created.status === 409 || created.status >= 500) {
    // Lost the existence race (or the list read is degraded): the tag exists
    // upstream — fetch it instead of failing the launch.
    const existing = await findTagByLabel(client, label);
    if (existing) return existing;
  }
  // Tags are best-effort labels on a shared workspace with 10k+ of them —
  // manifest.json is the authoritative ownership record, so an unresolvable
  // tag must not kill the launch.
  console.error(
    `WARNING: could not create or resolve tag ${label}: ${created.status} ${JSON.stringify(created.body)}. ` +
      `Continuing without it — manifest.json remains the authoritative ownership record.`,
  );
  return null;
}

async function assignCampaignTags(client, campaignId, tagIds) {
  const ids = (tagIds || []).filter(Boolean);
  if (!ids.length) {
    console.error(
      "WARNING: no ownership tag ids resolved; skipping tag assignment (manifest.json records ownership).",
    );
    return false;
  }
  const res = await client.toggleTagResource({
    tag_ids: ids,
    resource_type: 2,
    resource_ids: [campaignId],
    assign: true,
  });
  if (!(res.status >= 200 && res.status < 300)) {
    console.error(
      `WARNING: failed to assign campaign tags: ${res.status} ${JSON.stringify(res.body)}. ` +
        `Tag assignment is best-effort; manifest.json remains the authoritative ownership record.`,
    );
    return false;
  }
  return true;
}

async function resolveReusableCampaign(
  client,
  manifestCampaignId,
  campaignName,
  ownership,
) {
  if (manifestCampaignId) {
    const current = await client.getCampaign(manifestCampaignId);
    if (current.status >= 200 && current.status < 300) {
      assertCampaignNotForeign(
        current.body,
        ownership,
        `campaign ${manifestCampaignId}`,
      );
      return { campaignId: manifestCampaignId, reused: true };
    }
  }

  const list = await client.listCampaigns(100);
  if (
    !(list.status >= 200 && list.status < 300) ||
    !Array.isArray(list.body?.items)
  ) {
    return { campaignId: null, reused: false };
  }

  const matches = list.body.items.filter(
    (campaign) => campaign?.name === campaignName && campaign?.id,
  );
  for (const match of matches) {
    const details = await client.getCampaign(match.id);
    if (!(details.status >= 200 && details.status < 300)) continue;
    if (campaignOwnershipStatus(details.body, ownership) === "owned") {
      return { campaignId: match.id, reused: true };
    }
  }

  return { campaignId: null, reused: false };
}

function computeExpectedDailyCapacity(spec) {
  return spec.campaign.daily_limit;
}

// CTA URL placeholders the launcher refuses to ship live. These come from
// agents copying run-spec-template.json or PROFILE-template.md verbatim
// without substituting their product's real domain. We've seen all of these
// in production:
//   - `<instance-id>` / `<slug>` / `<product>` — angle-bracket template tokens
//   - `.instance-id.` / `.<slug>.` subdomain leftovers (no brackets, but the
//     literal placeholder word survives in the URL)
//   - example.com / example.org / *.example — RFC test/example domains
const URL_PLACEHOLDER_PATTERNS = [
  {
    re: /<[a-z][a-z0-9_-]{0,40}>/i,
    label:
      "angle-bracket placeholder like <instance-id> / <slug> / <your-...> in body",
  },
  {
    re: /\.instance-id\b|\binstance-id\.[pn]\.egbe\.app/i,
    label:
      "literal '.instance-id.' subdomain — replace with the real instance public_id",
  },
  {
    re: /\bexample\.(?:com|org|net)\b|\bhttps?:\/\/[a-z0-9-]+\.example\b/i,
    label: "example.com / example.org / *.example placeholder domain",
  },
  {
    re: /\byour-(?:product|domain|slug|landing|site)\b/i,
    label: "literal 'your-product' / 'your-domain' placeholder",
  },
];

function preflightCtaUrls(spec) {
  const steps = spec.sequence?.steps || [];
  if (!steps.length) return;
  const offenses = [];
  for (const [idx, step] of steps.entries()) {
    const haystack = `${step.subject || ""}\n${step.body || ""}`;
    for (const pat of URL_PLACEHOLDER_PATTERNS) {
      const m = haystack.match(pat.re);
      if (m) {
        offenses.push(`step ${idx + 1}: ${pat.label} (matched "${m[0]}")`);
        break; // one offense per step is enough — operator gets the idea
      }
    }
  }
  if (offenses.length) {
    fail(
      `Copy preflight failed: CTA URLs contain unfilled template placeholders. ` +
        `These would ship live emails pointing at non-existent landing pages, ` +
        `producing real sends that recipients can't act on. ` +
        `Fix the run-spec body so each link points at the real product URL ` +
        `(e.g. https://rolloo.app/, not https://<slug>.<instance-id>.n.egbe.app ` +
        `and not https://example.com/demo). Detected: ${offenses.join("; ")}.`,
    );
  }
}

// Cosmetic source-data concerns are warnings, not universal copy policy.
// Missing values actually referenced by the sequence remain a payload error.
function preflightLeadNames(spec, leads, leadsFileLabel, opts = {}) {
  const checks = leadNameChecksForSteps(spec.sequence?.steps);
  const problems = findLeadNameProblems(leads, {
    ...checks, skipEmails: opts.alreadyImportedEmails || null,
  });
  const warnings = problems.filter(p => p.severity === "warning");
  if (warnings.length) console.error("WARNING: Review sourced names: " +
    warnings.map(p => p.email + ": " + p.field + " " + JSON.stringify(p.value) + " (" + p.problem + ")").join("; "));
  const missing = findLeadVariableProblems(spec.sequence?.steps, leads, {
    skipEmails: opts.alreadyImportedEmails || null,
  });
  if (missing.length) fail("Unresolved sequence variables in " + leadsFileLabel + ": " +
    missing.map(p => p.email + ": " + p.field).join("; "));
}

// Cold outreach must never send from a trust-reputation domain. @egbe.app and
// @egbe.dev carry verification/onboarding links and relationship mail; running
// cold campaigns or warmup through them poisons the deliverability of that mail
// (GH #752). Cold sending belongs on a dedicated cold domain (e.g.
// smartcreateinc.org). See docs/email-reputation-surfaces.md. This guard is the
// code-level enforcement — it holds even if an agent hand-supplies an egbe.app
// address in the run spec.
const BLOCKED_SENDER_DOMAINS = ["egbe.app", "egbe.dev"];

function senderEmailOf(entry) {
  return normalizeEmail(typeof entry === "string" ? entry : entry && entry.email);
}

function isBlockedSender(entry) {
  const email = senderEmailOf(entry);
  const at = email.lastIndexOf("@");
  const domain = at >= 0 ? email.slice(at + 1) : "";
  return BLOCKED_SENDER_DOMAINS.includes(domain);
}

// Drop any trust-domain mailbox from a candidate sender list. Logs what it
// removed and hard-fails (never silently proceeds) if nothing else remains,
// pointing the operator at the dedicated cold domain. Accepts either bare
// email strings or account objects with an `email` field.
function excludeProtectedSenders(entries) {
  const blocked = entries.filter(isBlockedSender);
  const allowed = entries.filter((entry) => !isBlockedSender(entry));
  if (blocked.length) {
    console.error(
      `Excluded ${blocked.length} trust-domain sender(s) from this cold campaign: ` +
        `${blocked.map(senderEmailOf).join(", ")}. @egbe.app / @egbe.dev are reserved for ` +
        `verification and relationship mail (docs/email-reputation-surfaces.md, GH #752).`,
    );
  }
  if (!allowed.length) {
    fail(
      "No eligible cold-outreach sending accounts remain after excluding trust-domain " +
        "(@egbe.app / @egbe.dev) mailboxes. Cold outreach must send from a dedicated cold " +
        "domain (e.g. smartcreateinc.org). Add cold-domain mailboxes in Instantly and retry.",
    );
  }
  return allowed;
}

async function listAllAccounts(client) {
  // Accounts have no status filter here: a mailbox named in the run spec but
  // paused in Instantly must be reported as inactive, not as missing.
  const all = [];
  let cursor;
  let prevFirst = null;
  for (let page = 0; page < 20; page++) {
    const res = await client.listAccounts(100, cursor ? { starting_after: cursor } : {});
    if (!(res.status >= 200 && res.status < 300))
      fail(`List accounts failed: ${res.status} ${JSON.stringify(res.body)}`);
    const items = Array.isArray(res.body?.items) ? res.body.items : [];
    // A gateway that drops starting_after re-serves page 1: stop there.
    const first = items[0]?.email ?? null;
    if (first != null && first === prevFirst) break;
    prevFirst = first;
    all.push(...items);
    const next = res.body?.next_starting_after;
    if (items.length < 100 || !next || next === cursor) break;
    cursor = next;
  }
  return all;
}

async function pickEmailAccounts(client, spec) {
  const { senders, error } = selectSenders(spec.campaign, await listAllAccounts(client));
  if (error) fail(error);
  // Enforce the trust-domain boundary on the chosen senders (GH #752).
  return excludeProtectedSenders(senders);
}

async function main() {
  const args = parseArgs(process.argv);
  const runSpecPath = args["run-spec"];
  if (!runSpecPath) fail("Missing --run-spec");
  const resolvedRunSpecPath = path.resolve(runSpecPath);
  const runDir = path.dirname(resolvedRunSpecPath);
  ensureDir(runDir);
  const spec = readJson(resolvedRunSpecPath);
  if (!spec) fail("Run spec file not found or invalid JSON");
  if (!spec.run_key) fail("run_key is required");
  if (!spec.sequence?.steps?.length) fail("sequence.steps is required");
  if (!spec.leads_file) fail("leads_file is required");

  const manifestPath = path.join(runDir, "manifest.json");
  const manifest = readJson(manifestPath, {
    run_key: spec.run_key,
    agent_id: spec.agent_id || "unknown-agent",
    created_at: isoNow(),
    campaign: {},
    ownership: {},
    state_files: {},
  });
  reconcileRunIdentity(manifest, spec);
  reconcileInstantlyAttribution(manifest, {
    runKey: spec.run_key,
    campaignId: manifest.campaign?.id,
    label: "manifest",
  });
  validateLaunchConfig(spec);
  // Read before initDb: an absent history after earlier sends is not a clean project.
  readOptOutHistory(runDir);

  // Materialize OS creds from process.env into the run-scoped .env so cron
  // jobs (which run with their own environment) can find them. This is also
  // what stops the agent from falling back to send-email when it can't see the
  // creds in the run directory.
  const envInit = ensureRunEnv(runDir);
  loadRunEnv(runDir);
  const os = getOsConfig();
  if (os.missing.length) {
    fail(
      `Cold-outbound preflight failed: ${os.missing.join(" and ")} not found in process.env or ${envInit.envFilePath}. ` +
        `This skill talks to Instantly through the OS outreach capability; it does NOT use a personal Instantly API key. ` +
        `Set OS_URL and OS_API_KEY in the project credentials (or run .env). ` +
        `Do NOT fall back to send-email/Mailu for cold outbound — that is for manual 1:1 only. ` +
        `Report the missing credential; do not continue with an unrelated sending service.`,
    );
  }
  const stateDir = path.join(runDir, "state");
  ensureDir(stateDir);
  const dbPath = initDb(runDir);

  spec.created_at = spec.created_at || isoNow();
  spec.campaign = spec.campaign || {};
  // An explicitly authored campaign.name wins; the product|segment|offer|date
  // formula is only the fallback. (Two same-day runs sharing product+segment+
  // offer used to collide onto one auto-built name and reuse the wrong
  // campaign via the name-based lookup.)
  const explicitCampaignName =
    typeof spec.campaign.name === "string" && spec.campaign.name.trim();
  spec.campaign.name = explicitCampaignName || buildCampaignName(spec);
  spec.campaign.instance_count = 1;

  // campaign.verify_leads used to drive BOTH verification-on-import and the
  // blocking wait gate; disabling it to bypass a hung wait also silently
  // skipped verification itself. Two flags now, with the legacy one honored
  // as a fallback for existing run-specs.
  const verifyOnImport =
    spec.campaign.verify_leads_on_import ?? spec.campaign.verify_leads ?? true;
  const waitForVerify =
    spec.campaign.wait_for_verification ?? spec.campaign.verify_leads ?? true;

  const summaryPath = path.join(runDir, "launch-summary.json");
  const importedLeadsPath = path.join(stateDir, "imported-leads.json");
  const sequenceStatePath = path.join(stateDir, "sequence-state.json");
  const ownershipPath = path.join(stateDir, "ownership.json");
  const client = new InstantlyClient({
    connectionEnvFile: envInit.envFilePath,
    osApiKey: os.osApiKey,
    osUrl: os.osUrl,
    verbose: !!args.verbose,
  });
  const optOutStopResults = [];
  const readMembers = async (campaignId) => {
    try { return await client.listLeadEmails(campaignId); }
    catch { return { ok: false, emails: new Set() }; }
  };
  const containOptOuts = async (emails) => {
    for (const email of emails) {
      const result = await stopConfirmedRecipient(client, runDir, email);
      optOutStopResults.push({ email, ...result, checked_at: isoNow() });
      // Keep the outcome even if a later import/read gate aborts this attempt.
      // Do not turn the earlier launch's counts/timestamp into a new observation.
      writeJson(summaryPath, {
        ...readJson(summaryPath, {}),
        run_key: spec.run_key,
        campaign_id: manifest.campaign.id,
        opt_out_stop_results: optOutStopResults,
      });
      if (!result.ok) console.error(`WARNING: Refusal saved but stopping ${email} is not confirmed; inspect opt_out_stop_results.`);
    }
  };
  const requireMembers = async (campaignId) => {
    const members = await readMembers(campaignId);
    if (!members.ok) {
      // Blocking an import/activation does not stop an already-active run.
      // Every membership gate must still reach the scoped refusal stop path.
      await containOptOuts(readOptOutHistory(runDir).emails);
      fail("Cannot establish campaign membership; no import or activation attempted." +
        (optOutStopResults.length ? " Known-refusal stop results are recorded in launch-summary.json." : ""));
    }
    return members;
  };
  const chosenAccounts = await pickEmailAccounts(client, spec);
  const emailList = chosenAccounts
    .map((acc) => (typeof acc === "string" ? acc : acc.email))
    .filter(Boolean);
  if (!emailList.length)
    fail(
      "No sending accounts resolved. Cannot launch a campaign without at least one sending account.",
    );

  const throughputPreflight = { expected_daily_capacity: computeExpectedDailyCapacity(spec) };
  preflightCtaUrls(spec);

  // The leads file is read and checked before anything is written to
  // Instantly (tags, campaign, leads), so a bad lead fails the run clean.
  let leadsPath = path.isAbsolute(spec.leads_file)
    ? spec.leads_file
    : path.resolve(path.dirname(resolvedRunSpecPath), spec.leads_file);
  if (!fs.existsSync(leadsPath) && !path.isAbsolute(spec.leads_file)) {
    // Relative leads_file resolves against the run-spec's directory (so cron
    // jobs and reruns agree on the location), but operators invoking the CLI
    // from elsewhere routinely keep leads.json next to their CWD — accept
    // that with a warning instead of failing on a doubled path.
    const cwdLeadsPath = path.resolve(process.cwd(), spec.leads_file);
    if (cwdLeadsPath !== leadsPath && fs.existsSync(cwdLeadsPath)) {
      console.error(
        `WARNING: leads_file not found next to the run-spec (${leadsPath}); ` +
          `using ${cwdLeadsPath} from the current directory. The canonical ` +
          `location is relative to the run-spec's directory.`,
      );
      leadsPath = cwdLeadsPath;
    }
  }
  if (!fs.existsSync(leadsPath)) {
    fail(
      `Leads file not found: ${spec.leads_file} (tried ${leadsPath}` +
        (path.isAbsolute(spec.leads_file)
          ? ""
          : ` and ${path.resolve(process.cwd(), spec.leads_file)}`) +
        `). Relative leads_file paths resolve against the run-spec's directory.`,
    );
  }
  const leadsRaw = JSON.parse(fs.readFileSync(leadsPath, "utf8"));
  const inputLeads = Array.isArray(leadsRaw) ? leadsRaw : leadsRaw.leads || [];
  const optOutFilter = filterConfirmedOptOuts(runDir, inputLeads);
  const leads = optOutFilter.leads;
  // Leads already imported into the manifest campaign (rerun) are skipped.
  const priorCampaignId = manifest.campaign?.id || null;
  const alreadyImportedEmails = new Set();
  if (priorCampaignId) {
    const priorHashes = new Set(
      readJson(path.join(stateDir, "imported-leads.json"), []),
    );
    for (const lead of leads) {
      const email = normalizeEmail(lead?.email);
      if (
        email &&
        priorHashes.has(
          sha256(JSON.stringify({ campaignId: priorCampaignId, email })),
        )
      ) {
        alreadyImportedEmails.add(email);
      }
    }
  }
  preflightLeadNames(spec, leads, spec.leads_file, {
    campaignId: priorCampaignId,
    alreadyImportedEmails,
  });

  const primaryAccount =
    typeof chosenAccounts[0] === "string"
      ? { email: chosenAccounts[0] }
      : chosenAccounts[0];
  const inferredSenderName =
    spec.reply_policy?.sender_name ||
    spec.sender_name ||
    deriveSenderName({
      email: primaryAccount.email,
      firstName: primaryAccount.first_name,
      lastName: primaryAccount.last_name,
    }) ||
    null;

  // {{senderName}} is resolved at build time to ONE name, but the campaign
  // rotates sends across every mailbox in email_list — a real run shipped
  // follow-ups signed with the wrong person's name before this warning.
  const usesSenderNameToken = spec.sequence.steps.some((step) =>
    /{{\s*senderName\s*}}/.test(`${step.subject || ""}\n${step.body || ""}`),
  );
  if (usesSenderNameToken && !inferredSenderName)
    fail("{{senderName}} requires an explicit sender name or a verified account name; email addresses are not names.");
  if (usesSenderNameToken && emailList.length > 1) {
    console.error(
      `WARNING: {{senderName}} is a launcher build-time token and ${emailList.length} sending mailboxes ` +
        `rotate on this campaign — every send will be signed "${inferredSenderName}" (the primary ` +
        `mailbox's name) regardless of which mailbox sends. Prefer a name-less sign-off ("Thanks,") ` +
        `or set campaign.max_sending_accounts: 1 when the signature name matters.`,
    );
  }

  spec.reply_policy = spec.reply_policy || {};
  spec.reply_policy.sender_name = inferredSenderName;
  spec.reply_policy.reply_from_email =
    spec.reply_policy.reply_from_email || primaryAccount.email;
  spec.campaign.email_list = emailList;
  // Derived values (campaign name, sender identity, chosen mailboxes) used to
  // be written back into the operator's run-spec file, destroying the
  // authored input. They land in state/resolved-run-spec.json instead;
  // post-launch readers (reply-worker) overlay it when present.
  const resolvedSpecPath = path.join(stateDir, "resolved-run-spec.json");
  writeJson(resolvedSpecPath, spec);

  const ownership = {
    run_tag_label: `oc-run-${slugify(spec.run_key, 48)}`,
    agent_tag_label: `oc-agent-${slugify(spec.agent_id || "unknown-agent", 48)}`,
    run_tag_description: `Owned by OpenClaw run ${spec.run_key}`,
    agent_tag_description: `Owned by OpenClaw agent ${spec.agent_id || "unknown-agent"}`,
  };

  // Rerun path: reuse tag ids recorded by a previous successful launch of
  // this run. Shared fleet workspaces hold thousands of tags, so re-resolving
  // by label is unreliable (and a create retries into a 409).
  const storedOwnership = readJson(ownershipPath, null);
  if (
    storedOwnership &&
    storedOwnership.run_tag_label === ownership.run_tag_label &&
    storedOwnership.agent_tag_label === ownership.agent_tag_label &&
    storedOwnership.run_tag_id &&
    storedOwnership.agent_tag_id
  ) {
    ownership.run_tag_id = storedOwnership.run_tag_id;
    ownership.agent_tag_id = storedOwnership.agent_tag_id;
  } else {
    // Cross-run tag cache: agent tags are shared by every run of this agent,
    // and huge shared workspaces make label lookups unreliable (create 409s
    // while the paged list cannot surface the tag). Cache label->id locally.
    const tagCachePath = path.join(runDir, "..", "tag-cache.json");
    const tagCache = readJson(tagCachePath, {});
    const resolveTag = async (label, description) => {
      if (tagCache[label]) return { id: tagCache[label] };
      const tag = await ensureTag(client, label, description);
      if (!tag?.id) return null;
      tagCache[label] = tag.id;
      writeJson(tagCachePath, tagCache);
      return tag;
    };
    const runTag = await resolveTag(
      ownership.run_tag_label,
      ownership.run_tag_description,
    );
    const agentTag = await resolveTag(
      ownership.agent_tag_label,
      ownership.agent_tag_description,
    );
    ownership.run_tag_id = runTag?.id || null;
    ownership.agent_tag_id = agentTag?.id || null;
  }
  writeJson(ownershipPath, ownership);

  const payload = buildCampaignPayload(spec, emailList, inferredSenderName);
  const campaignFingerprint = sha256(
    stableStringify({
      segment: spec.segment,
      offer: spec.offer,
      campaign: spec.campaign,
    }),
  );
  const desiredSequenceFingerprint = sequenceFingerprint(
    spec,
    emailList,
    inferredSenderName,
  );
  const existingLeadHashes = new Set(readJson(importedLeadsPath, []));
  const previousSequenceState = readJson(sequenceStatePath, {});

  const reuseState = await resolveReusableCampaign(
    client,
    manifest.campaign.id || null,
    spec.campaign.name,
    ownership,
  );
  let campaignId = reuseState.campaignId;
  let reused = reuseState.reused;

  let sequenceAction = "unchanged";
  if (!campaignId) {
    const created = await client.createCampaign(payload);
    if (created.status >= 500) {
      // The campaign may exist anyway, without ownership tags, and other
      // campaigns can share its name: list them for the person to choose.
      const list = await client.listCampaigns(100);
      const readable = list.status >= 200 && list.status < 300 && Array.isArray(list.body?.items);
      const sameName = readable ? list.body.items.filter((c) => c?.name === payload.name) : [];
      fail(
        `Create campaign returned ${created.status}; it may have been created anyway. ` +
          (!readable
            ? `The campaign list could not be read (${list.status}): check Instantly by hand for "${payload.name}". `
            : sameName.length
              ? `Campaigns named "${payload.name}": ` +
                sameName.map((c) => `${c.id} (created ${c.timestamp_created || "?"})`).join(", ") +
                ". "
              : `The campaign list shows none named "${payload.name}". `) +
          `Before re-running, delete only the one created at the time of this run, if any.`,
      );
    }
    if (!(created.status >= 200 && created.status < 300))
      fail(
        `Create campaign failed: ${created.status} ${JSON.stringify(created.body)}`,
      );
    campaignId = created.body?.id;
    sequenceAction = "created-with-campaign";
  } else {
    if (
      previousSequenceState.applied_fingerprint &&
      previousSequenceState.applied_fingerprint !==
        desiredSequenceFingerprint &&
      !args["allow-sequence-update"]
    ) {
      fail(
        "Desired sequence differs from the last applied sequence. Re-run with --allow-sequence-update to patch the live campaign intentionally.",
      );
    }
    const patched = await client.patchCampaign(campaignId, payload);
    if (!(patched.status >= 200 && patched.status < 300))
      fail(
        `Patch campaign failed: ${patched.status} ${JSON.stringify(patched.body)}`,
      );
    sequenceAction =
      previousSequenceState.applied_fingerprint === desiredSequenceFingerprint
        ? "verified-no-change"
        : "patched-intentionally";
  }

  const tagsAssigned = await assignCampaignTags(client, campaignId, [
    ownership.run_tag_id,
    ownership.agent_tag_id,
  ]);
  ownership.tags_assigned = tagsAssigned;
  writeJson(ownershipPath, ownership);

  manifest.campaign = {
    first_launched_at: manifest.campaign?.first_launched_at || null,
    last_activated_at: manifest.campaign?.last_activated_at || null,
    id: campaignId,
    name: spec.campaign.name,
    fingerprint: campaignFingerprint,
    sequence_fingerprint: desiredSequenceFingerprint,
    reused,
    owned_by_run: true,
    last_prepared_at: isoNow(),
    email_list: emailList,
    primary_email: primaryAccount.email,
    sender_name: inferredSenderName,
  };
  const attributionBinding = reconcileInstantlyAttribution(manifest, {
    runKey: spec.run_key,
    campaignId,
    label: "manifest",
  });
  manifest.ownership = ownership;
  manifest.state_files.imported_leads = path.relative(
    runDir,
    importedLeadsPath,
  );
  manifest.state_files.sequence_state = path.relative(
    runDir,
    sequenceStatePath,
  );
  manifest.state_files.ownership = path.relative(runDir, ownershipPath);
  manifest.state_files.resolved_spec = path.relative(runDir, resolvedSpecPath);
  // Register carry-over path unconditionally — replenish-leads.js looks here
  // first, falls back to Apollo if the file is missing or empty.
  manifest.state_files.carry_over_leads = path.relative(
    runDir,
    path.join(stateDir, "carry-over-leads.json"),
  );
  writeJson(manifestPath, manifest);
  writeJson(sequenceStatePath, {
    desired_fingerprint: desiredSequenceFingerprint,
    applied_fingerprint: desiredSequenceFingerprint,
    sequence_action: sequenceAction,
    sender_name: inferredSenderName,
    email_list: emailList,
    updated_at: isoNow(),
  });

  upsertRun(dbPath, {
    run_key: spec.run_key,
    product_name: spec.product?.name || spec.product_name,
    segment_name:
      spec.segment?.name || spec.segment?.description || spec.segment,
    offer_headline:
      spec.offer?.headline ||
      spec.offer?.name ||
      spec.offer?.description ||
      spec.offer,
    campaign_id: campaignId,
    campaign_name: spec.campaign.name,
    status: "draft",
    created_at: manifest.created_at || spec.created_at,
  });

  const dedup = new Map();
  for (const lead of leads) {
    const email = normalizeEmail(lead.email);
    if (!email) continue;
    if (!dedup.has(email)) {
      const normalizedLead = { ...lead, email };
      dedup.set(email, normalizedLead);
      upsertLead(dbPath, normalizedLead);
      upsertRunLead(dbPath, {
        run_key: spec.run_key,
        email,
        campaign_id: campaignId,
        verification_status: "pending",
        last_known_status: "new",
        ownership_tag: ownership.run_tag_label,
      });
    }
  }

  // {{personalization}} resolves from a per-lead field at send time. If the
  // copy references it but no lead carries a value, Instantly substitutes an
  // empty string for every recipient — refuse to ship that.
  const usesPersonalization = spec.sequence.steps.some((step) =>
    `${step.subject || ""}\n${step.body || ""}`.includes("{{personalization}}"),
  );
  if (usesPersonalization && dedup.size) {
    const withPersonalization = Array.from(dedup.values()).filter(
      (lead) =>
        lead.personalization != null && String(lead.personalization).trim(),
    ).length;
    if (withPersonalization === 0) {
      fail(
        `Copy references {{personalization}} but none of the ${dedup.size} leads in ${spec.leads_file} ` +
          `carry a personalization field — the token would render as an empty string in every email. ` +
          `Add a per-lead "personalization" value to the leads file, or remove the token from the copy.`,
      );
    }
    if (withPersonalization < dedup.size) {
      console.error(
        `WARNING: {{personalization}} is used in the copy but only ${withPersonalization} of ${dedup.size} ` +
          `leads carry a value; the token renders as an empty string for the rest.`,
      );
    }
  }

  let imported = 0,
    skipped = 0,
    failed = 0;
  // Leads of this file already in the campaign from earlier launches, and
  // leads of this batch the add call reported as not added — together they
  // give a lower bound of the leads the verification gate must see.
  let alreadyImportedCount = 0;
  let notAddedCount = 0;
  const allCandidates = [];
  const allCandidateHashes = [];
  for (const lead of dedup.values()) {
    const leadHash = sha256(JSON.stringify({ campaignId, email: lead.email }));
    if (existingLeadHashes.has(leadHash)) {
      skipped++;
      alreadyImportedCount++;
      upsertRunLead(dbPath, {
        run_key: spec.run_key,
        email: lead.email,
        campaign_id: campaignId,
        verification_status: "pending",
        last_known_status: "imported",
        ownership_tag: ownership.run_tag_label,
        notes:
          "Lead already present in imported-leads state; skipped on rerun.",
      });
      continue;
    }
    allCandidates.push(buildImportLead(lead));
    allCandidateHashes.push(leadHash);
  }

  // Only an explicitly configured replenishment plan limits the initial batch.
  // Retain excess source data so subsequent batches do not buy it again.
  const carryOverPath = path.join(stateDir, "carry-over-leads.json");
  const existingMembers = await requireMembers(campaignId);
  const initialBatchSize = initialBatchLimit(spec, existingMembers.emails.size, allCandidates.length);
  let pendingLeads = allCandidates;
  let pendingLeadHashes = allCandidateHashes;
  let carryOverWritten = 0;
  if (allCandidates.length > initialBatchSize) {
    pendingLeads = allCandidates.slice(0, initialBatchSize);
    pendingLeadHashes = allCandidateHashes.slice(0, initialBatchSize);
    const carryOver = allCandidates.slice(initialBatchSize);
    // Merge with any pre-existing carry-over from prior partial-failure reruns
    // so reruns don't shrink the carry-over pool.
    const existingCarryOver = readJson(carryOverPath, []);
    const existingCarryOverEmails = new Set(
      existingCarryOver.map((l) => l && l.email).filter(Boolean),
    );
    const merged = existingCarryOver.slice();
    for (const lead of carryOver) {
      if (!existingCarryOverEmails.has(lead.email)) {
        merged.push(lead);
      }
    }
    writeJson(carryOverPath, merged);
    carryOverWritten = carryOver.length;
    console.log(
      `Initial load capped at ${initialBatchSize} of ${allCandidates.length} candidates. ` +
        `${carryOverWritten} new leads carried over → ${merged.length} total in ${path.relative(runDir, carryOverPath)}. ` +
        `replenish-leads.js will drain this pool before calling Apollo.`,
    );
  }

  // An earlier add answered with a 5xx may have landed: send only leads that
  // are not in the campaign yet.
  const preImportFilter = filterConfirmedOptOuts(runDir, pendingLeads);
  pendingLeads = preImportFilter.leads;
  pendingLeadHashes = pendingLeads.map(lead => sha256(JSON.stringify({ campaignId, email: lead.email })));
  const leadsToAdd = preImportFilter.leads.length
    ? leadsNotInCampaign(preImportFilter.leads, await requireMembers(campaignId))
    : [];
  skipped += pendingLeads.length - leadsToAdd.length;
  if (leadsToAdd.length) {
    const res = await client.addLeadsToCampaign({
      campaign_id: campaignId,
      leads: leadsToAdd,
      verify_leads_on_import: verifyOnImport,
    });
    if (!(res.status >= 200 && res.status < 300)) {
      fail(
        `Add leads failed: ${res.status} ${JSON.stringify(res.body)}` +
          (res.status >= 500
            ? ". The batch may have landed; a re-run sends only leads not yet in the campaign."
            : ""),
      );
    }
    const body = res.body || {};
    imported += Number(body.leads_uploaded || body.created_leads?.length || 0);
    skipped +=
      Number(body.skipped_count || 0) +
      Number(body.duplicated_leads || 0) +
      Number(body.in_blocklist || 0) +
      Number(body.duplicate_email_count || 0);
    failed +=
      Number(body.invalid_email_count || 0) +
      Number(body.incomplete_count || 0);
    // Every "not uploaded" counter, so the expected count stays a lower bound.
    notAddedCount +=
      Number(body.skipped_count || 0) +
      Number(body.duplicated_leads || 0) +
      Number(body.in_blocklist || 0) +
      Number(body.duplicate_email_count || 0) +
      Number(body.invalid_email_count || 0) +
      Number(body.incomplete_count || 0);

    // Reconcile the bulk response before treating the batch as landed: a
    // 2xx with 0 uploaded and 0 already-present means every lead was
    // rejected (invalid/incomplete). Nothing has been persisted yet, so
    // failing here leaves the rerun free to retry the import.
    if (imported === 0 && skipped === 0) {
      fail(
        `Add leads returned ${res.status} but reported 0 uploaded and 0 already-present ` +
          `(${failed} invalid/incomplete of ${leadsToAdd.length} sent): ${JSON.stringify(body)}. ` +
          `The batch never landed — fix the leads file and re-run. Campaign was NOT activated.`,
      );
    }
  }

  // Post-launch validation: verify the campaign has sending accounts before activating
  let verification = await client.getCampaign(campaignId);
  let safeguardReadback = campaignSafetyReadback(verification.body);
  const safeguardKeys = Object.keys(safeguardReadback);
  if (verification.status >= 200 && verification.status < 300 &&
      safeguardKeys.some(key => safeguardReadback[key] !== payload[key])) {
    const requested = Object.fromEntries(safeguardKeys.map(key => [key, payload[key]]));
    await client.patchCampaign(campaignId, requested);
    verification = await client.getCampaign(campaignId);
    safeguardReadback = campaignSafetyReadback(verification.body);
  }
  const safeguardConfirmed = verification.status >= 200 && verification.status < 300 &&
    safeguardKeys.every(key => safeguardReadback[key] === payload[key]);
  if (verification.status >= 200 && verification.status < 300) {
    // A GET right after create has been observed returning link_tracking:
    // null even when false was sent. PATCH the intended value explicitly so
    // the tracker-domain rewrite cannot sneak back in.
    const storedLinkTracking = verification.body?.link_tracking;
    if (storedLinkTracking !== payload.link_tracking) {
      const patched = await client.patchCampaign(campaignId, {
        link_tracking: payload.link_tracking,
      });
      if (patched.status >= 200 && patched.status < 300) {
        console.log(
          `link_tracking read back as ${JSON.stringify(storedLinkTracking)}; patched to ${payload.link_tracking}.`,
        );
      } else {
        console.error(
          `WARNING: could not enforce link_tracking=${payload.link_tracking} ` +
            `(read back ${JSON.stringify(storedLinkTracking)}, patch returned ${patched.status}). ` +
            `Verify click tracking manually in the Instantly UI.`,
        );
      }
    }
    const liveEmailList = verification.body?.email_list || [];
    if (!liveEmailList.length) {
      fail(
        `Campaign ${campaignId} has no sending accounts assigned. The campaign was created but email_list is empty. Check that sending accounts exist and are healthy in the Instantly workspace.`,
      );
    }
    if (liveEmailList.length !== emailList.length) {
      console.error(
        `WARNING: Campaign has ${liveEmailList.length} sending accounts but ${emailList.length} were requested. Some accounts may have been rejected by Instantly.`,
      );
    }

    // Instantly's CREATE endpoint has been observed rewriting paragraph
    // markup (a body sent as <p> blocks came back as margin-less <div>s and
    // the delivered email rendered as a wall of text). Bodies are emitted in
    // editor-native <div> form now; still verify the stored copy kept the
    // blank-line separators before activating. Match by regex — Instantly
    // normalizes <br> to <br />, so never compare exact tag strings.
    const SEPARATOR_RE = /<div>\s*<br\s*\/?\s*>\s*<\/div>/i;
    const storedSteps = verification.body?.sequences?.[0]?.steps || [];
    (payload.sequences?.[0]?.steps || []).forEach((desiredStep, idx) => {
      const desiredBody = desiredStep.variants?.[0]?.body || "";
      if (!SEPARATOR_RE.test(desiredBody)) return;
      const storedBody = storedSteps[idx]?.variants?.[0]?.body;
      // A missing stored body means the read surface is degraded, not that
      // Instantly stripped the markup — skip rather than false-positive.
      if (typeof storedBody !== "string" || !storedBody) return;
      if (!SEPARATOR_RE.test(storedBody)) {
        fail(
          `Campaign ${campaignId} step ${idx + 1}: Instantly stripped the paragraph separators from the stored ` +
            `body (no <div><br /></div> left) — the delivered email would render as a wall of text. ` +
            `Refusing to activate. Inspect the stored sequence via a campaign GET and re-launch.`,
        );
      }
    });
  }

  let activation = null;
  let verificationResult = null;

  // Rerun after a failed gate: leads the agent dropped from the leads file
  // are still in the Instantly campaign and would be mailed on activation.
  // Delete them first, then gate the whole campaign as it now is.
  const invalidLeadsPath = path.join(stateDir, "invalid-leads.json");
  const deletedLeadsPath = path.join(stateDir, "deleted-leads.json");
  const previousInvalid = readJson(invalidLeadsPath, null);
  let invalidCleanup = null;
  if (previousInvalid?.campaign_id && previousInvalid.campaign_id !== campaignId) {
    console.error(
      `WARNING: ${path.relative(runDir, invalidLeadsPath)} belongs to campaign ${previousInvalid.campaign_id}, ` +
        `not ${campaignId}; not removing any leads from it.`,
    );
  } else if (previousInvalid) {
    invalidCleanup = await removeDroppedInvalidLeads(
      client,
      campaignId,
      previousInvalid,
      new Set(dedup.keys()),
    );
    const droppedEmails = new Set([
      ...invalidCleanup.deleted.map((d) => d.email),
      ...invalidCleanup.already_absent,
      ...invalidCleanup.failed.map((f) => f.email),
    ]);
    if (invalidCleanup.deleted.length) {
      const deletedAt = isoNow();
      writeJson(deletedLeadsPath, [
        ...readJson(deletedLeadsPath, []),
        ...invalidCleanup.deleted.map((d) => ({
          ...d,
          campaign_id: campaignId,
          deleted_at: deletedAt,
          reason: "failed lead verification; dropped from the leads file",
        })),
      ]);
      console.log(
        `Removed ${invalidCleanup.deleted.length} lead(s) dropped from ${spec.leads_file} after the last failed ` +
          `verification gate from campaign ${campaignId} (recorded in ${path.relative(runDir, deletedLeadsPath)}).`,
      );
    }
    // Replenishment must not bring them back from the carry-over pool.
    if (droppedEmails.size && fs.existsSync(carryOverPath)) {
      const pool = readJson(carryOverPath, []);
      const kept = pool.filter((l) => !droppedEmails.has(normalizeEmail(l?.email)));
      if (kept.length !== pool.length) writeJson(carryOverPath, kept);
    }
    if (!invalidCleanup.ok) {
      fail(
        `Could not remove the leads dropped from ${spec.leads_file} after the last failed verification gate: ` +
          `${invalidCleanup.reason}. They are still in campaign ${campaignId} and would be mailed on activation, ` +
          `so the campaign was NOT activated. Not removed: ` +
          invalidCleanup.failed
            .map((f) => `${f.email}${f.id ? ` (lead ${f.id})` : ""} — status ${f.status}`)
            .join(", ") +
          `. Rerun the same launch command — it re-reads the campaign first, so a delete that answered ` +
          `5xx but happened counts as removed — or remove them in Instantly by hand.` +
          (invalidCleanup.deleted.length
            ? ` Removed so far: ${invalidCleanup.deleted.length} (see ${path.relative(runDir, deletedLeadsPath)}).`
            : ""),
      );
    }
  }

  // A run that ended with verification pending or unread must not activate
  // on a rerun just because no new leads are left to import: re-check the
  // gate whenever the last gate did not pass.
  const verificationStatePath = path.join(stateDir, "verification-state.json");
  const previousVerification = readJson(verificationStatePath, null);
  const gateEnabled = verifyOnImport && waitForVerify;
  const recheckGate =
    gateEnabled &&
    !pendingLeads.length &&
    !!previousVerification?.status &&
    previousVerification.status !== "passed";
  if (recheckGate) {
    console.log(
      `The last launch of this run ended with lead verification "${previousVerification.status}"; ` +
        `re-checking the verification gate before activation.`,
    );
  }
  if (gateEnabled && (pendingLeads.length || recheckGate)) {
    verificationResult = await waitForVerification(client, campaignId, spec, {
      importedCount: imported,
      skippedCount: skipped,
      fileEmails: new Set(dedup.keys()),
      expectedLeads: Math.max(
        0,
        alreadyImportedCount + pendingLeads.length - notAddedCount,
      ),
    });
    if (verificationResult?.import_failed) {
      // Nothing has been persisted for this batch yet — failing here leaves
      // the rerun free to retry the import.
      fail(verificationResult.import_failure_reason);
    }
    const gateStatus = verificationResult?.gate_failed
      ? "failed"
      : verificationResult?.verification_pending
        ? "pending"
        : verificationResult?.verification_unread
          ? "unread"
          : "passed";
    writeJson(verificationStatePath, {
      status: gateStatus,
      campaign_id: campaignId,
      source: verificationResult?.source || null,
      checked_at: isoNow(),
    });
    if (verificationResult?.gate_failed) {
      // Like an import failure, nothing is persisted for this batch: the
      // rerun with the cleaned leads file deletes the dropped leads from the
      // campaign, re-imports what is missing (Instantly dedupes) and re-runs
      // the gate over the whole campaign.
      const invalidLeads = verificationResult.invalid_leads || [];
      const shown = invalidLeads.slice(0, 50).map((l) => l.email);
      if (invalidLeads.length) {
        writeJson(invalidLeadsPath, {
          run_key: spec.run_key,
          campaign_id: campaignId,
          leads_file: spec.leads_file,
          max_invalid_lead_pct: verificationResult.max_invalid_lead_pct,
          invalid_pct: verificationResult.invalidPct,
          generated_at: isoNow(),
          emails: invalidLeads.map((l) => l.email),
          leads: invalidLeads,
        });
      }
      fail(
        `${verificationResult.failure_reason}\n` +
          (invalidLeads.length
            ? `Invalid addresses (${invalidLeads.length}, also written to ${path.relative(runDir, invalidLeadsPath)}): ` +
              `${shown.join(", ")}${invalidLeads.length > shown.length ? `, … (${invalidLeads.length - shown.length} more in the file)` : ""}.\n` +
              `Remove them from ${spec.leads_file} (add replacement leads if you need the volume) and rerun ` +
              `the same launch command: the rerun deletes every listed lead that is no longer in the leads ` +
              `file from the Instantly campaign, then re-checks the gate over the whole campaign. A listed ` +
              `lead you keep in the file stays in the campaign and keeps counting.`
            : `The per-lead listing could not name the invalid addresses — check the leads' verification ` +
              `status in Instantly, remove the invalid ones from ${spec.leads_file}, and rerun.`),
      );
    }
  }

  // Import success state (JSON hashes + run_leads rows + imported events) is
  // persisted only after the import reconciled and the verification gate did
  // not diagnose a failed import — persisting earlier made reports claim a
  // failed batch was imported and let the rerun skip re-importing it. A
  // crash before this point re-imports the batch on rerun; Instantly dedupes
  // by email within a campaign, so the retry lands as skipped duplicates.
  if (pendingLeads.length) {
    for (const leadHash of pendingLeadHashes) {
      existingLeadHashes.add(leadHash);
    }
    const importedAt = isoNow();
    for (const lead of pendingLeads) {
      upsertRunLead(dbPath, {
        run_key: spec.run_key,
        email: lead.email,
        campaign_id: campaignId,
        imported_at: importedAt,
        verification_status: verifyOnImport ? "pending" : "skipped",
        last_known_status: "imported",
        ownership_tag: ownership.run_tag_label,
      });
      insertLeadEvent(dbPath, {
        run_key: spec.run_key,
        email: lead.email,
        event_type: "imported",
        event_at: importedAt,
        payload_json: {
          campaign_id: campaignId,
          verify_leads_on_import: verifyOnImport,
        },
      });
    }
  }
  writeJson(importedLeadsPath, Array.from(existingLeadHashes));

  const allowUnverified = spec.campaign.allow_unverified_activation === true;
  const gateDecision = verificationActivationBlock(
    verificationResult,
    allowUnverified,
  );
  let activationBlocked = gateDecision.blocked;
  if (!safeguardConfirmed) activationBlocked = "safeguard_readback_unconfirmed";
  // A fresh complete membership read catches opt-outs already imported in an
  // earlier pass. Filtering a new input file alone cannot make activation safe.
  const history = readOptOutHistory(runDir);
  if (spec.campaign.activate_on_launch === true || history.emails.size) {
    const assessment = await assessCampaignOptOuts(client, campaignId, history.emails);
    if (!assessment.ok) {
      activationBlocked = assessment.reason || "confirmed_opt_out_exclusion_unconfirmed";
      await containOptOuts(history.emails);
      // Containment may establish exclusion for a later explicit rerun. This
      // launch attempt stays blocked rather than activating as part of recovery.
    }
  }
  if (gateDecision.warning) {
    console.error(
      [
        "WARNING: ================ LEAD VERIFICATION NOT ENFORCED ================",
        `WARNING: ${gateDecision.warning}`,
        allowUnverified
          ? "WARNING: campaign.allow_unverified_activation is true — activation is allowed WITHOUT a completed invalid-lead gate."
          : "WARNING: The campaign will NOT be activated. Rerun the same launch command later (the gate is " +
            "re-checked), or set campaign.allow_unverified_activation: true in the run spec to activate without it.",
        "WARNING: ======================================================================",
      ].join("\n"),
    );
  }
  if (spec.campaign.activate_on_launch === true && !activationBlocked) {
    const act = await client.activateCampaign(campaignId);
    activation = { status: act.status, body: act.body };
    const live = await client.getCampaign(campaignId);
    activation.confirmed = act.status >= 200 && act.status < 300 &&
      live.status >= 200 && live.status < 300 && live.body?.status === 1;
    activation.readback_status = live.body?.status ?? null;
    if (!activation.confirmed) activationBlocked = "activation_unconfirmed";
    if (activation.confirmed) {
      const activatedAt = isoNow();
      if (!reused || verification.body?.status === 0)
        manifest.campaign.first_launched_at ||= activatedAt;
      manifest.campaign.last_activated_at = activatedAt;
      writeJson(manifestPath, manifest);
    }
  }
  let finalCampaign;
  try { finalCampaign = await client.getCampaign(campaignId); }
  catch { finalCampaign = { status: 0, body: null }; }
  const campaignStatus = finalCampaign.status >= 200 && finalCampaign.status < 300
    ? finalCampaign.body?.status ?? null : null;
  const actualState = ({0: "draft", 1: "active", 2: "paused", 3: "completed"})[campaignStatus] || "unknown";
  const launchStatus =
    activation?.confirmed
      ? "launched"
      : activationBlocked || actualState;

  upsertRun(dbPath, {
    run_key: spec.run_key,
    product_name: spec.product?.name || spec.product_name,
    segment_name:
      spec.segment?.name || spec.segment?.description || spec.segment,
    offer_headline:
      spec.offer?.headline ||
      spec.offer?.name ||
      spec.offer?.description ||
      spec.offer,
    campaign_id: campaignId,
    campaign_name: spec.campaign.name,
    status: actualState,
    created_at: manifest.created_at || spec.created_at,
  });

  const summary = {
    business_id: spec.business_id || null,
    product_id: spec.product_id || null,
    launch_id: spec.launch_id || null,
    experiment_id: spec.experiment_id || null,
    variant_id: spec.variant_id || null,
    provider: attributionBinding.provider,
    provider_campaign_id: attributionBinding.provider_campaign_id,
    utm_source: attributionBinding.utm_source,
    utm_medium: attributionBinding.utm_medium,
    utm_campaign: attributionBinding.utm_campaign,
    run_key: spec.run_key,
    campaign_id: campaignId,
    campaign_name: spec.campaign.name,
    reused,
    sequence_action: sequenceAction,
    sender_name: inferredSenderName,
    primary_email: primaryAccount.email,
    email_list: emailList,
    ownership_tags: [ownership.run_tag_label, ownership.agent_tag_label],
    ownership_tags_assigned: tagsAssigned,
    imported,
    skipped,
    failed,
    deduped_input_count: dedup.size,
    raw_input_count: inputLeads.length,
    confirmed_opt_outs_excluded: optOutFilter.excluded.length + preImportFilter.excluded.length,
    opt_out_stop_results: optOutStopResults,
    safeguard_readback: safeguardReadback,
    initial_batch_size: initialBatchSize,
    carry_over_count: carryOverWritten,
    launch_status: launchStatus,
    campaign_status: campaignStatus,
    actual_state: actualState,
    activation_blocked: activationBlocked,
    launched_at: manifest.campaign.first_launched_at || null,
    invalid_lead_cleanup: invalidCleanup,
    activation,
    verification: verificationResult,
    throughput_preflight: throughputPreflight,
    generated_at: isoNow(),
  };
  writeJson(summaryPath, summary);
  console.log(JSON.stringify(summary, null, 2));
  if (activationBlocked) {
    // Not a crash and not an activation: a distinct exit code so a chained
    // command does not treat the run as launched.
    console.error(
      activationBlocked === "verification_pending"
        ? `VERIFICATION PENDING: ${verificationResult.pending_reason}`
        : `NOT CONFIRMED LAUNCHED: ${activationBlocked}. Check the recorded verification/readback before continuing.`,
    );
    process.exit(2);
  }
}

if (require.main === module) main().catch((err) => fail(err.stack || err.message));
module.exports = { buildCampaignPayload, sequenceFingerprint, preflightLeadNames };
