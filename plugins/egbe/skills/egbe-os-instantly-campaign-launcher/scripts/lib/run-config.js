"use strict";

// Execution bounds are authored for the run. Do not infer a marketing plan.
function numberIn(value, min, max = Infinity, integer = false) {
  return typeof value === "number" && Number.isFinite(value) && value >= min &&
    value <= max && (!integer || Number.isInteger(value));
}

function replenishmentConfig(spec) {
  const config = spec.lead_replenishment;
  if (config?.enabled !== true) return null;
  const checks = {
    batch_size: numberIn(config.batch_size, 1, Infinity, true),
    max_total_leads: numberIn(config.max_total_leads, 1, Infinity, true),
    max_replenishments: numberIn(config.max_replenishments, 0, Infinity, true),
    utilization_threshold: numberIn(config.utilization_threshold, 0, 1),
    cooldown_minutes: numberIn(config.cooldown_minutes, 0),
  };
  const missing = Object.keys(checks).filter(key => !checks[key]);
  if (missing.length) throw new Error(`Enabled lead_replenishment requires explicit valid bounds: ${missing.join(", ")}`);
  return config;
}

function protectionConfig(spec) {
  const thresholds = spec.monitoring?.thresholds || {};
  const errors = [];
  if (!numberIn(thresholds.max_bounce_rate, 0, 100))
    errors.push("monitoring.thresholds.max_bounce_rate must be an explicit percentage (0–100)");
  if (thresholds.max_spam_complaint_rate !== undefined &&
      !numberIn(thresholds.max_spam_complaint_rate, 0, 100))
    errors.push("max_spam_complaint_rate must be a percentage when this signal is monitored");
  if (spec.monitoring?.autopause_on_risk !== undefined &&
      typeof spec.monitoring.autopause_on_risk !== "boolean")
    errors.push("autopause_on_risk must be boolean");
  return { valid: !errors.length, errors,
    autopause: spec.monitoring?.autopause_on_risk !== false,
    thresholds: {
      max_bounce_rate: thresholds.max_bounce_rate ?? null,
      max_spam_complaint_rate: thresholds.max_spam_complaint_rate ?? null,
    },
    denominator: "contacted_count",
  };
}

function validateLaunchConfig(spec) {
  if (!numberIn(spec.campaign?.daily_limit, 1, Infinity, true))
    throw new Error("campaign.daily_limit must be an explicit positive integer (campaign-wide daily cap)");
  if (spec.campaign.daily_max_new_leads !== undefined &&
      !numberIn(spec.campaign.daily_max_new_leads, 0, Infinity, true))
    throw new Error("campaign.daily_max_new_leads must be a non-negative integer");
  replenishmentConfig(spec);
  if (spec.campaign.activate_on_launch === true) {
    const protection = protectionConfig(spec);
    if (!protection.valid) throw new Error(`Cannot activate: ${protection.errors.join("; ")}`);
  }
}

function metricNumber(value) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

function initialBatchLimit(spec, existingCount, candidateCount) {
  const config = replenishmentConfig(spec);
  if (!config) return candidateCount;
  if (!numberIn(existingCount, 0, Infinity, true))
    throw new Error("A complete campaign member count is required before a bounded import");
  return Math.min(candidateCount, config.batch_size, Math.max(0, config.max_total_leads - existingCount));
}

function evaluateProtection(spec, metrics) {
  const config = protectionConfig(spec);
  const triggered = [], skipped = [], evaluated = [];
  if (!config.valid) triggered.push({ gate: "configuration", value: null,
    threshold: null, reason: config.errors.join("; ") });
  const contacted = metricNumber(metrics.contacted_count);
  const hasActivity = ["emails_sent_count", "new_leads_contacted_count", "reply_count_unique",
    "bounced_count", "spam_complaint_count", "spam_count"].some(key => metricNumber(metrics[key]) > 0);
  for (const [gate, key, raw] of [
    ["bounce", "max_bounce_rate", metrics.bounced_count],
    ["spam", "max_spam_complaint_rate", metrics.spam_complaint_count ?? metrics.spam_count],
  ]) {
    const threshold = config.thresholds[key];
    if (threshold === null) { skipped.push({ gate, reason: "not_configured" }); continue; }
    const count = metricNumber(raw);
    // A scoped, consistent zero is not an outage; missing signals are not zero.
    if (contacted === 0 && count === 0 && !hasActivity && !metrics._partial && !metrics._possibly_workspace_level) {
      skipped.push({ gate, reason: "no_recipients_yet" }); continue;
    }
    if (count === null || contacted === null || contacted === 0 || count > contacted ||
        metrics._partial || metrics._possibly_workspace_level) {
      triggered.push({ gate: `${gate}_unavailable`, value: null, threshold,
        reason: "Required campaign-scoped signal unavailable after read fallbacks" });
      continue;
    }
    const value = count / contacted * 100;
    evaluated.push(gate);
    if (value > threshold) triggered.push({ gate, value, threshold, count });
  }
  return { ...config, contacted, triggered, skipped, evaluated };
}

module.exports = { numberIn, replenishmentConfig, protectionConfig, validateLaunchConfig, initialBatchLimit,
  metricNumber, evaluateProtection };
