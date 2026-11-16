#!/usr/bin/env node
const path = require("path");
const {
  InstantlyClient,
  contactedForUtilization,
} = require("./lib/instantly-client");
const {
  readJson,
  writeJson,
  parseArgs,
  isoNow,
  loadRunEnv,
  getOsConfig,
  assertCampaignNotForeign,
} = require("./lib/helpers");
const { initDb, upsertRun } = require("./lib/outreach-db");
const { collectCampaignMetrics } = require("./lib/campaign-metrics");
const { readOptOutHistory } = require("./lib/confirmed-opt-outs");
const { evaluateProtection, metricNumber, numberIn, replenishmentConfig } = require("./lib/run-config");

function pct(n, d) {
  return metricNumber(n) != null && d > 0 ? (n / d) * 100 : null;
}

async function readOrUnavailable(operation) {
  try { return await operation(); }
  catch { return { status: 0, body: null }; }
}

// Instantly campaign status codes: 0 draft, 1 active, 2 paused, 3 completed.
const INSTANTLY_STATUS_DRAFT = 0;
const INSTANTLY_STATUS_ACTIVE = 1;
const INSTANTLY_STATUS_PAUSED = 2;
const INSTANTLY_STATUS_COMPLETED = 3;

// Statuses where Instantly sends nothing: gates are recorded but are not news
// and there is nothing to pause. Unknown/null is NOT here (fail safe).
const NOT_SENDING_STATUS = {
  [INSTANTLY_STATUS_DRAFT]: "draft",
  [INSTANTLY_STATUS_PAUSED]: "paused",
  [INSTANTLY_STATUS_COMPLETED]: "completed",
};

// Relative change that turns an already-reported item into a fresh alert.
const MATERIAL_WORSENING = 0.5;

// The live campaign is what Instantly actually does, so its boolean wins; the
// run spec decides only when the live object does not carry the field.
// Launch defaults open_tracking to false when the spec omits it.
function openTrackingState(spec, campaignBody) {
  const live = campaignBody?.open_tracking;
  if (typeof live === "boolean") {
    return {
      enabled: live,
      source: "live campaign",
      reason: `live campaign open_tracking=${live}`,
    };
  }
  if (typeof spec.campaign?.open_tracking === "boolean") {
    return {
      enabled: spec.campaign.open_tracking,
      source: "run spec",
      reason: `run spec campaign.open_tracking=${spec.campaign.open_tracking} (live campaign has no open_tracking field)`,
    };
  }
  return {
    enabled: false,
    source: "default",
    reason: "open_tracking unset in run spec and live campaign (launch default: off)",
  };
}

function worsenedMaterially(item, alertedValue) {
  if (typeof alertedValue !== "number" || typeof item.value !== "number") {
    return false;
  }
  if (item.worse === "lower") {
    return alertedValue > 0 && item.value <= alertedValue * (1 - MATERIAL_WORSENING);
  }
  return item.value >= alertedValue * (1 + MATERIAL_WORSENING) && item.value > alertedValue;
}

function expectedDailyCapacity(spec) {
  return metricNumber(spec.campaign?.daily_limit);
}

function snapshotNearHoursAgo(history, hoursAgo) {
  if (!Array.isArray(history) || history.length === 0) return null;
  const target = Date.now() - hoursAgo * 3600 * 1000;
  let best = null;
  let bestDelta = Infinity;
  for (const snap of history) {
    const t = Date.parse(snap?.metrics_observed_at ?? snap?.generated_at ?? "");
    if (Number.isNaN(t)) continue;
    const delta = Math.abs(t - target);
    if (delta < bestDelta) {
      best = snap;
      bestDelta = delta;
    }
  }
  // Reject if the closest snapshot is too far from the target window (>50% drift).
  if (best && bestDelta > hoursAgo * 0.5 * 3600 * 1000) return null;
  return best;
}

function diagnoseThroughputAnomaly({
  campaignBody,
  contactedDelta,
  utilization,
  utilizationThreshold,
  totalLeads,
  leadCountsUnavailable,
}) {
  const causes = [];
  const status = campaignBody?.status;
  if (status === 0 || status === 2 || status === 3) {
    causes.push("campaign appears paused or not active in Instantly");
  }
  const liveEmailList = campaignBody?.email_list || [];
  if (!liveEmailList.length) {
    causes.push("campaign has no sending accounts assigned");
  }
  if (totalLeads === 0 || totalLeads == null) {
    causes.push(
      leadCountsUnavailable
        ? "lead totals unreadable (leads read surface degraded, #3790) — zero-leads diagnosis unavailable"
        : "campaign has zero leads loaded",
    );
  } else if (utilizationThreshold != null && utilization != null && utilization >= utilizationThreshold && contactedDelta === 0) {
    causes.push(
      "lead utilization reached the configured threshold with no new sends; inspect existing lead availability",
    );
  }
  if (causes.length === 0) {
    causes.push(
      "no obvious cause; check mailbox health (per-account daily_limit may be reduced) and Instantly workspace warmup state",
    );
  }
  return causes;
}

async function main() {
  const args = parseArgs(process.argv);
  const runDir = args["run-dir"] ? path.resolve(args["run-dir"]) : null;
  if (!runDir) throw new Error("Missing --run-dir");
  const connectionEnvFile = loadRunEnv(runDir, args["env-file"]);
  const manifest = readJson(path.join(runDir, "manifest.json"));
  const spec = readJson(path.join(runDir, "run-spec.json"));
  const ownership = readJson(
    path.join(runDir, "state", "ownership.json"),
    manifest?.ownership || {},
  );
  if (!manifest?.campaign?.id)
    throw new Error("Run manifest missing campaign ID");
  const os = getOsConfig();
  if (os.missing.length)
    throw new Error(`Missing ${os.missing.join(" and ")}`);
  const client = new InstantlyClient({
    connectionEnvFile,
    osApiKey: os.osApiKey,
    osUrl: os.osUrl,
    verbose: !!args.verbose,
  });
  const campaign = await client.getCampaign(manifest.campaign.id);
  if (!(campaign.status >= 200 && campaign.status < 300)) {
    throw new Error(
      `Campaign lookup failed: ${campaign.status} ${JSON.stringify(campaign.body)}`,
    );
  }
  assertCampaignNotForeign(
    campaign.body,
    ownership,
    `campaign ${manifest.campaign.id}`,
  );
  const liveStatus =
    typeof campaign.body?.status === "number" ? campaign.body.status : null;
  // Observation must not turn lost opt-out history into a valid empty DB.
  // Keep fail-safe provider pause available even when local recovery is needed.
  let dbPath = null;
  let historyError = null;
  try {
    readOptOutHistory(runDir);
    dbPath = initDb(runDir);
  } catch (error) {
    historyError = error.message;
  }

  const launch = readJson(path.join(runDir, "launch-summary.json"), {});
  const observation = await collectCampaignMetrics(client, manifest.campaign.id, campaign.body);
  const metrics = observation.metrics;
  const hasMetricObservation = ["contacted_count", "emails_sent_count", "reply_count_unique",
    "bounced_count", "open_count_unique", "spam_complaint_count", "spam_count"]
    .some(key => metricNumber(metrics[key]) != null);
  const metricsObservedAt = hasMetricObservation ? isoNow() : null;
  const status = await readOrUnavailable(() => client.sendingStatus(manifest.campaign.id));
  const contacted = metricNumber(metrics.contacted_count);
  const denominator = metrics._partial || metrics._possibly_workspace_level ? null : contacted;
  const replyRate = pct(metrics.reply_count_unique, denominator);
  const bounceRate = pct(metrics.bounced_count, denominator);
  const unsubRate = pct(metrics.unsubscribed_count, denominator);
  const spamCount = metricNumber(metrics.spam_complaint_count ?? metrics.spam_count);
  const spamRate = pct(spamCount, denominator);
  const openTracking = openTrackingState(spec, campaign.body);
  if (!openTracking.enabled) metrics.open_count_unique = null;
  const openRate = openTracking.enabled ? pct(metrics.open_count_unique, denominator) : null;

  const protection = evaluateProtection(spec, metrics);
  const thresholds = protection.thresholds;
  const triggeredGates = protection.triggered;
  if (historyError) triggeredGates.push({ gate: "history_unavailable", value: null,
    threshold: null, reason: historyError });
  const skippedGates = protection.skipped;
  const pauseSuggested = triggeredGates.length > 0;
  const recommendations = triggeredGates.map(g => g.reason
    ? `Protection ${g.gate}: ${g.reason}.`
    : `Protection ${g.gate}: ${g.value.toFixed(3)}% exceeds configured ${g.threshold}%.`);
  if (!(status.status >= 200 && status.status < 300)) recommendations.push(
    "Sending status endpoint returned an error. Inspect sending health."
  );

  // --- Lead utilization tracking ---
  const leadStats = campaign.body?.lead_stats || {};
  let totalLeads = metricNumber(leadStats.total);
  let contactedLeads = denominator;
  let leadCountsSource = "lead_stats";
  let leadCountsUnavailable = false;
  if (totalLeads == null) {
    // lead_stats can be null while the campaign is healthy (#3790); count
    // through the leads API before concluding "zero leads loaded".
    const counts = observation.leadCounts || await client.countLeads(manifest.campaign.id).catch(() => ({ ok: false }));
    if (counts.ok && counts.partial) {
      // A partial count is only a lower bound — using it as a utilization
      // denominator inflates the ratio (90 contacted of a truncated 90-lead
      // page reads as 100% on a 1000-lead campaign). Treat as unreadable,
      // matching replenish-leads.
      leadCountsSource = "unavailable";
      leadCountsUnavailable = true;
    } else if (counts.ok) {
      totalLeads = counts.total;
      contactedLeads = contactedForUtilization(contactedLeads, counts);
      leadCountsSource = "leads-api";
    } else if (!counts.ok) {
      leadCountsSource = "unavailable";
      leadCountsUnavailable = true;
    }
  }
  const leadUtilization = totalLeads > 0 && contactedLeads != null ? contactedLeads / totalLeads : null;
  let replenishConfig = null;
  try {
    replenishConfig = replenishmentConfig(spec);
  } catch (error) {
    recommendations.push(error.message);
  }
  const utilizationThreshold = replenishConfig?.utilization_threshold ?? null;
  const needsReplenishment = !!replenishConfig && leadUtilization != null
    && leadUtilization >= utilizationThreshold;
  if (needsReplenishment) recommendations.push(
    `Lead utilization is ${(leadUtilization * 100).toFixed(0)}% at configured ${(utilizationThreshold * 100).toFixed(0)}% threshold. Replenishment is enabled; job execution has not been verified by this observation.`
  );

  // Throughput is observable only against an explicitly configured capacity
  // floor and comparable complete cumulative snapshots.
  const snapshotsPathExisting = path.join(
    runDir,
    "state",
    "analytics-history.json",
  );
  const priorHistory = readJson(snapshotsPathExisting, []);
  const expectedDaily = expectedDailyCapacity(spec);
  const throughputFloorPct = numberIn(spec.monitoring?.min_daily_capacity_pct, 0, 100)
    ? spec.monitoring.min_daily_capacity_pct : null;
  const referenceSnap = snapshotNearHoursAgo(priorHistory, 24);
  let throughputHealth = {
    expected_daily_sends: expectedDaily,
    floor_pct: throughputFloorPct,
    measurable: false,
  };
  // Emails-fallback snapshots cap counts at ~100 rows — comparing one
  // against a full analytics snapshot produces phantom deltas in either
  // direction, so the throughput gate requires two same-quality snapshots.
  if (throughputFloorPct == null) {
    throughputHealth.skipped_reason = "not_configured";
  } else if (metrics._partial || referenceSnap?.metrics?._partial
    || metrics._possibly_workspace_level || referenceSnap?.metrics?._possibly_workspace_level) {
    throughputHealth.skipped_reason = "partial-metrics";
  } else if (expectedDaily > 0 && referenceSnap
    && metricNumber(referenceSnap.metrics?.emails_sent_count) != null
    && metricNumber(metrics.emails_sent_count) != null
    && metrics.emails_sent_count >= referenceSnap.metrics.emails_sent_count) {
    const refSent = referenceSnap.metrics.emails_sent_count;
    const curSent = metrics.emails_sent_count;
    const refTime = Date.parse(referenceSnap.metrics_observed_at ?? referenceSnap.generated_at ?? "");
    const curTime = Date.now();
    const hoursElapsed = Math.max(1, (curTime - refTime) / (3600 * 1000));
    const sendsDelta = Math.max(0, curSent - refSent);
    const actualDailyRate = (sendsDelta / hoursElapsed) * 24;
    const actualPctOfExpected = pct(actualDailyRate, expectedDaily);
    const anomaly = actualPctOfExpected < throughputFloorPct;
    throughputHealth = {
      ...throughputHealth,
      measurable: true,
      hours_elapsed: Math.round(hoursElapsed * 10) / 10,
      sends_delta: sendsDelta,
      actual_daily_rate: Math.round(actualDailyRate * 10) / 10,
      actual_pct_of_expected: Math.round(actualPctOfExpected),
      anomaly,
    };
    if (anomaly) {
      const causes = diagnoseThroughputAnomaly({
        campaignBody: campaign.body,
        contactedDelta: sendsDelta,
        utilization: leadUtilization,
        utilizationThreshold,
        totalLeads,
        leadCountsUnavailable,
      });
      throughputHealth.probable_causes = causes;
      recommendations.push(
        `Throughput anomaly: actual ${actualDailyRate.toFixed(1)} sends/day vs expected ${expectedDaily} (${actualPctOfExpected.toFixed(0)}% < ${throughputFloorPct}% floor). Probable causes: ${causes.join("; ")}.`,
      );
    }
  }

  // --- Alert de-duplication ---
  // The monitor runs hourly; a tripped gate stays tripped until someone acts.
  // Mark each tripped item "new" only the first time (or when it worsens
  // materially) so the cron agent reports it once instead of every hour.
  const alertStatePath = path.join(runDir, "state", "monitor-alerts.json");
  const alertState = readJson(alertStatePath, {});
  const alertItems = triggeredGates.map((g) => ({
    key: `protection:${g.gate}`,
    kind: "protection_gate",
    gate: g.gate,
    value: g.value,
    threshold: g.threshold,
    ...(g.gate === "spam" ? { count: spamCount } : {}),
    worse: "higher",
  }));
  // A paused, completed or draft campaign sends nothing, so its throughput
  // "anomaly" is expected and not a separate incident.
  const notSendingState =
    liveStatus != null ? NOT_SENDING_STATUS[liveStatus] || null : null;
  // Completed/draft: nothing to pause and nothing the owner must act on.
  const finishedOrDraft =
    liveStatus === INSTANTLY_STATUS_COMPLETED || liveStatus === INSTANTLY_STATUS_DRAFT;
  const throughputAlertable = throughputHealth.anomaly && !notSendingState;
  if (throughputHealth.anomaly && !throughputAlertable) {
    throughputHealth.alert = "suppressed";
    throughputHealth.alert_suppressed_reason = `campaign is ${notSendingState} (Instantly status ${liveStatus})`;
  }
  if (throughputAlertable) {
    alertItems.push({
      key: "throughput",
      kind: "throughput_anomaly",
      value: throughputHealth.actual_pct_of_expected,
      threshold: throughputFloorPct,
      worse: "lower",
    });
  }
  // Keys evaluated this poll: a gate that was checked and did not trip is
  // cleared, so a later trip is "new" again. Gates that were not evaluated
  // (unreadable metrics) keep their state until an evaluated recovery.
  const evaluatedKeys = new Set(["protection:configuration", "protection:history_unavailable"]);
  for (const gate of ["bounce", "spam"]) {
    if (protection.evaluated.includes(gate)
      || protection.skipped.some(item => item.gate === gate)) {
      evaluatedKeys.add(`protection:${gate}`);
      evaluatedKeys.add(`protection:${gate}_unavailable`);
    }
  }
  if (throughputHealth.measurable && !notSendingState) {
    evaluatedKeys.add("throughput");
  }
  const nowIso = isoNow();
  // Migrate operational alert acknowledgements, not the retired stage model.
  const nextGates = Object.fromEntries(Object.entries(alertState.gates || {})
    .map(([key, value]) => [key.replace(/^c1:/, "protection:"), value]));
  delete nextGates["protection:open_rate"];
  for (const key of Object.keys(nextGates)) {
    if (evaluatedKeys.has(key) && !alertItems.some((a) => a.key === key)) {
      delete nextGates[key];
    }
  }

  // Operator acknowledgement: the monitor paused for a gate and the campaign
  // is active again, so someone resumed it on purpose. Do not pause or alert
  // again for that gate unless it worsens materially against the value at the
  // pause (for spam: any new complaint), or another gate trips.
  // Only an explicit "active" counts as a resume. A failed read (null),
  // completed (3) or any other status leaves the gate un-acknowledged, so the
  // monitor keeps trying to pause and keeps reporting (fail safe).
  const resumedByOperator = liveStatus === INSTANTLY_STATUS_ACTIVE;
  const needsPause = new Set();
  const alerts = alertItems.map((item) => {
    const prior = nextGates[item.key];
    const resumedAfterPause =
      item.kind === "protection_gate" && typeof item.value === "number"
      && !!prior?.paused_at && resumedByOperator;
    let isNew;
    let acknowledged = false;
    if (resumedAfterPause) {
      const worse =
        worsenedMaterially(item, prior.paused_value) ||
        (item.count != null && item.count > (prior.paused_count ?? 0));
      acknowledged = !worse;
      isNew = worse;
    } else if (finishedOrDraft) {
      // Recorded, never news: nothing is sending. alerted_at stays unset if
      // it was never reported, so a later send (draft activated) alerts.
      isNew = false;
    } else {
      isNew = !prior?.alerted_at || worsenedMaterially(item, prior.alerted_value);
    }
    if (item.kind === "protection_gate" && !acknowledged) needsPause.add(item.key);
    nextGates[item.key] = {
      first_tripped_at: prior?.first_tripped_at || nowIso,
      alerted_at: isNew ? nowIso : prior?.alerted_at || null,
      alerted_value: isNew ? item.value : prior?.alerted_value ?? null,
      last_value: item.value,
      ...(item.count != null ? { last_count: item.count } : {}),
      last_seen_at: nowIso,
      paused_at: prior?.paused_at || null,
      paused_value: prior?.paused_value ?? null,
      paused_count: prior?.paused_count ?? null,
      acknowledged_at: acknowledged ? prior.acknowledged_at || nowIso : null,
    };
    const { worse, ...rest } = item;
    return {
      ...rest,
      alert: isNew ? "new" : "repeat",
      first_tripped_at: nextGates[item.key].first_tripped_at,
      ...(finishedOrDraft
        ? { not_news_reason: `campaign is ${notSendingState} in Instantly; nothing is sending` }
        : {}),
      ...(acknowledged
        ? {
            acknowledged_at: nextGates[item.key].acknowledged_at,
            acknowledged_reason: "campaign resumed after the monitor paused it for this gate",
          }
        : {}),
    };
  });
  for (const gate of triggeredGates) {
    const match = alerts.find((a) => a.key === `protection:${gate.gate}`);
    if (match) gate.alert = match.alert;
  }
  if (throughputAlertable) {
    throughputHealth.alert = alerts.find((a) => a.key === "throughput").alert;
  }

  const snapshot = {
    run_key: manifest.run_key,
    campaign_id: manifest.campaign.id,
    metrics,
    sending_status: status.body,
    derived: {
      reply_rate: replyRate,
      bounce_rate: bounceRate,
      unsubscribe_rate: unsubRate,
      spam_complaint_rate: spamRate,
      open_rate: openRate,
    },
    protection: {
      active: protection.valid,
      contacted,
      thresholds,
      triggered_gates: triggeredGates,
      skipped_gates: skippedGates,
    },
    open_tracking: openTracking,
    open_tracking_enabled: openTracking.enabled,
    metrics_observed_at: metricsObservedAt,
    metrics_window: {
      starts_at: manifest.campaign?.first_launched_at ?? launch.launched_at ?? launch.started_at ?? null,
      observed_at: metricsObservedAt,
      basis: "cumulative_campaign_snapshot",
    },
    campaign_status: liveStatus,
    outreach_history_available: !historyError,
    lead_utilization: {
      total_leads: totalLeads,
      contacted: contactedLeads,
      source: leadCountsSource,
      utilization_pct: leadUtilization != null ? Math.round(leadUtilization * 1000) / 10 : null,
      threshold_pct: utilizationThreshold != null ? utilizationThreshold * 100 : null,
      needs_replenishment: needsReplenishment,
    },
    throughput_health: throughputHealth,
    recommendations,
    pause_suggested: pauseSuggested,
    alerts,
    // "new": at least one item needs the owner this run; "repeat": items are
    // still tripped but were already reported; "none": nothing tripped.
    alert: alerts.some((a) => a.alert === "new")
      ? "new"
      : alerts.length
        ? "repeat"
        : "none",
    generated_at: nowIso,
  };

  priorHistory.push(snapshot);
  writeJson(snapshotsPathExisting, priorHistory);
  writeJson(path.join(runDir, "monitor-summary.json"), snapshot);

  let pausedThisRun = false;
  const autopause = protection.autopause;
  if (pauseSuggested && autopause && needsPause.size === 0) {
    snapshot.pause_suppressed = {
      reason: "operator resumed the campaign after a monitor pause; tripped gates are acknowledged",
      gates: alerts.filter((a) => a.acknowledged_at).map((a) => a.gate),
    };
  } else if (pauseSuggested && autopause) {
    if (finishedOrDraft) {
      snapshot.pause_skipped = {
        reason: `campaign is ${notSendingState} in Instantly; nothing is sending`,
      };
    } else if (liveStatus === INSTANTLY_STATUS_PAUSED) {
      // Already paused (by an earlier tick or the operator): pausing again
      // changes nothing and would read as a fresh incident.
      snapshot.pause_skipped = {
        reason: "campaign already paused in Instantly (status 2)",
        paused_by_monitor_at: alertState.paused_by_monitor_at || null,
      };
    } else {
      const pause = await readOrUnavailable(() => client.pauseCampaign(manifest.campaign.id));
      const at = isoNow();
      snapshot.pause_action = { status: pause.status, body: pause.body, at };
      if (pause.status >= 200 && pause.status < 300) {
        const readback = await readOrUnavailable(() => client.getCampaign(manifest.campaign.id));
        if (readback.status >= 200 && readback.status < 300) {
          assertCampaignNotForeign(readback.body, ownership, `campaign ${manifest.campaign.id}`);
        }
        snapshot.pause_readback = { status: readback.status, campaign_status: readback.body?.status ?? null };
        pausedThisRun = readback.status >= 200 && readback.status < 300
          && readback.body?.status === INSTANTLY_STATUS_PAUSED;
      }
      if (pausedThisRun) {
        for (const item of alerts) {
          if (item.kind !== "protection_gate") continue;
          Object.assign(nextGates[item.key], {
            paused_at: at,
            paused_value: item.value,
            paused_count: item.count ?? null,
            acknowledged_at: null,
          });
        }
      } else {
        // A campaign that should be paused but cannot be is never a repeat:
        // every tick says so until a pause succeeds or it is paused by hand.
        snapshot.pause_failed = true;
        snapshot.pause_http_status = pause.status;
        snapshot.recommendations.push(
          `Auto-pause FAILED (HTTP ${pause.status}). Pause was not confirmed by provider readback; check the campaign and pause it in Instantly.`,
        );
        for (const item of alerts) {
          if (needsPause.has(item.key)) item.alert = "new";
        }
      }
      // A pause (or a failed pause) is always news for the owner.
      snapshot.alert = "new";
    }
  }
  for (const gate of triggeredGates) {
    const match = alerts.find((a) => a.key === `protection:${gate.gate}`);
    if (match) gate.alert = match.alert;
  }
  // The history entry is the same object: rewrite it with the pause outcome.
  writeJson(snapshotsPathExisting, priorHistory);
  writeJson(path.join(runDir, "monitor-summary.json"), snapshot);

  writeJson(alertStatePath, {
    gates: nextGates,
    paused_by_monitor_at: pausedThisRun
      ? snapshot.pause_action.at
      : alertState.paused_by_monitor_at || null,
    updated_at: nowIso,
  });

  if (dbPath) upsertRun(dbPath, {
    run_key: manifest.run_key,
    product_name: spec.product?.name || spec.product_name,
    segment_name:
      spec.segment?.name || spec.segment?.description || spec.segment,
    offer_headline:
      spec.offer?.headline ||
      spec.offer?.name ||
      spec.offer?.description ||
      spec.offer,
    campaign_id: manifest.campaign.id,
    campaign_name: manifest.campaign?.name || spec.campaign?.name,
    // Reflect what Instantly is doing: paused when this tick's pause call
    // succeeded or the live campaign is already paused, never on a failed call.
    status:
      pausedThisRun || liveStatus === INSTANTLY_STATUS_PAUSED
        ? "paused"
        : "launched",
    created_at: manifest.created_at || spec.created_at || isoNow(),
  });

  console.log(JSON.stringify(snapshot, null, 2));
}

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exit(1);
});
