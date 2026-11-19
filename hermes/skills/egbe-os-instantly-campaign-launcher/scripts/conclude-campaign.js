#!/usr/bin/env node
// Retained filename: conclusion.json is an observation transport, not a verdict.
const path = require("path");
const { readJson, writeJson, parseArgs, isoNow, loadRunEnv } = require("./lib/helpers");
const { reconcileRunIdentity, reconcileInstantlyAttribution } = require("./lib/gtm-identity");

function number(value) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

function timestamp(value) {
  return typeof value === "string" && Number.isFinite(Date.parse(value)) ? value : null;
}

function rate(numerator, denominator) {
  return numerator != null && denominator > 0
    ? Math.round((numerator / denominator) * 1000000) / 10000
    : null;
}

function collectFacts({ manifest, spec, launch = {}, history = [], generatedAt = isoNow() }) {
  // Never replace a recent partial observation with an older complete one, nor
  // combine cumulative snapshots. Repackaging does not refresh measurement.
  const latest = history.length ? history[history.length - 1] : null;
  if ((latest?.campaign_id && latest.campaign_id !== manifest.campaign.id)
    || (latest?.run_key && latest.run_key !== manifest.run_key)) {
    throw new Error("Latest analytics snapshot identity does not match the run");
  }
  const metrics = latest?.metrics || {};
  const observedAt = timestamp(latest && Object.hasOwn(latest, "metrics_observed_at")
    ? latest.metrics_observed_at : latest?.generated_at);
  const openTracking = latest?.open_tracking_enabled ?? latest?.open_tracking?.enabled
    ?? spec.campaign?.open_tracking ?? null;
  const partial = metrics._partial === true;
  const workspaceLevel = metrics._possibly_workspace_level === true;
  const source = metrics._source || null;
  const count = (value) => partial && value === 0 ? null : number(value);
  const contacted = count(metrics.contacted_count);
  const replies = count(metrics.reply_count_unique);
  const opens = openTracking === false ? null : count(metrics.open_count_unique);
  const bounces = count(metrics.bounced_count ?? metrics.bounce_count);
  const unsubscribes = count(metrics.unsubscribed_count ?? metrics.unsubscribe_count);
  const spam = count(metrics.spam_complaint_count ?? metrics.spam_count);
  const positive = count(metrics.positive_reply_count);
  // Partial fallback rows are bounded samples, not complete rate denominators.
  const reliableDenominator = partial || workspaceLevel ? null : contacted;
  const reasons = [];
  if (!latest) reasons.push("analytics_unavailable");
  if (!observedAt) reasons.push("observation_time_unavailable");
  if (partial) reasons.push("partial_snapshot");
  if (workspaceLevel) reasons.push("possibly_workspace_level");
  if (!source) reasons.push("source_unavailable");
  if (openTracking === false) reasons.push("open_tracking_disabled");
  const summary = {
    contacted,
    emails_sent: count(metrics.emails_sent_count),
    opens,
    total_replies: replies,
    positive_replies: positive,
    bounces,
    unsubscribes,
    spam_complaints: spam,
    reply_rate_pct: rate(replies, reliableDenominator),
    positive_reply_rate_pct: rate(positive, reliableDenominator),
    bounce_rate_pct: rate(bounces, reliableDenominator),
    unsubscribe_rate_pct: rate(unsubscribes, reliableDenominator),
    spam_rate_pct: rate(spam, reliableDenominator),
    open_rate_pct: rate(opens, reliableDenominator),
    // Provider counters are counts, not rates; no step is assumed to be a breakup.
    step_reply_counts: metrics.step_reply_counts ?? metrics.replies_by_step ?? null,
  };
  const missing = Object.entries(summary).filter(([, value]) => value == null).map(([key]) => key);
  if (missing.length) reasons.push("metrics_missing");
  // last_launch_at was historically overwritten on launcher reruns and is
  // not a trustworthy start for cumulative measurements.
  const launchedAt = timestamp(launch.launched_at ?? launch.started_at
    ?? manifest.campaign?.first_launched_at);
  return {
    business_id: spec.business_id || manifest.business_id || null,
    product_id: spec.product_id || manifest.product_id || null,
    launch_id: spec.launch_id || manifest.launch_id || null,
    experiment_id: spec.experiment_id || manifest.experiment_id || null,
    variant_id: spec.variant_id || manifest.variant_id || null,
    ...reconcileInstantlyAttribution(manifest, {
      runKey: spec.run_key, campaignId: manifest.campaign.id, label: "manifest",
    }),
    run_key: manifest.run_key,
    campaign_id: manifest.campaign.id,
    campaign_name: manifest.campaign.name,
    product: spec.product || { name: spec.product_name || null },
    segment: spec.segment,
    offer: spec.offer,
    launch: { ...launch, launched_at: launchedAt },
    campaign_status: latest?.campaign_status ?? null,
    metrics_observed_at: observedAt,
    metrics_source: source,
    metrics_quality: !latest || !observedAt || !source || source === "unavailable" ? "unknown" : workspaceLevel
      ? "uncertain-scope" : partial ? "partial" : "full",
    metrics_quality_details: {
      partial, possibly_workspace_level: workspaceLevel,
      missing_metrics: missing, reason_codes: reasons,
      ...(metrics._field_sources ? { field_sources: metrics._field_sources } : {}),
      ...(metrics._contacted_count_recovery ? { contacted_count_recovery: {
        ...metrics._contacted_count_recovery, raw_provider_count: metrics._raw_contacted_count,
      } } : {}),
    },
    metrics_window: {
      starts_at: timestamp(latest?.metrics_window?.starts_at) || launchedAt,
      observed_at: observedAt,
      basis: "cumulative_campaign_snapshot",
    },
    open_tracking_enabled: openTracking,
    rate_denominators: { metric: "contacted", value: reliableDenominator },
    metrics_summary: summary,
    generated_at: generatedAt,
  };
}

async function main() {
  const args = parseArgs(process.argv);
  const runDir = args["run-dir"] ? path.resolve(args["run-dir"]) : null;
  if (!runDir) throw new Error("Missing --run-dir");
  loadRunEnv(runDir, args["env-file"]);
  const manifest = readJson(path.join(runDir, "manifest.json"));
  const spec = readJson(path.join(runDir, "run-spec.json"));
  if (!manifest || !spec) throw new Error("manifest.json and run-spec.json are required");
  reconcileRunIdentity(manifest, spec);
  const providerCampaignId = manifest.campaign?.id;
  if (!providerCampaignId) throw new Error("manifest.campaign.id is required to collect an Instantly run");
  reconcileInstantlyAttribution(manifest, {
    runKey: spec.run_key, campaignId: providerCampaignId, label: "manifest",
  });
  const conclusionPath = path.join(runDir, "conclusion.json");
  const existing = readJson(conclusionPath);
  if (existing) {
    reconcileRunIdentity(existing, spec);
    reconcileInstantlyAttribution(existing, {
      runKey: spec.run_key, campaignId: providerCampaignId, label: "existing conclusion",
    });
  }
  const conclusion = collectFacts({
    manifest, spec,
    launch: readJson(path.join(runDir, "launch-summary.json"), {}),
    history: readJson(path.join(runDir, "state", "analytics-history.json"), []),
  });
  // No DB lifecycle mutation. --force is a legacy no-op and cannot promote quality.
  writeJson(conclusionPath, conclusion);
  console.log(JSON.stringify(conclusion, null, 2));
}

if (require.main === module) {
  main().catch((err) => {
    console.error(err.stack || err.message);
    process.exit(1);
  });
}

module.exports = { collectFacts };
