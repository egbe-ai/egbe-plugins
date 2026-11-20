"use strict";

const { metricNumber } = require("./run-config");

const COUNTERS = ["contacted_count", "new_leads_contacted_count", "leads_count",
  "emails_sent_count", "reply_count_unique", "bounced_count", "unsubscribed_count",
  "open_count_unique", "spam_complaint_count", "spam_count", "positive_reply_count"];

function matchesCampaign(value, campaignId) {
  return value && typeof value === "object" && ["campaign", "campaign_id"].every(key =>
    value[key] == null || value[key] === campaignId);
}

async function read(operation) {
  try { return await operation(); }
  catch { return { status: 0, body: null }; }
}

// These rows are a diagnostic sample, never complete campaign counts or rate
// denominators. Keep the legacy partial fallback only when analytics is absent
// or its all-zero activity is contradicted by actual messages (#3790).
async function emailSample(client, campaignId) {
  const limit = 100;
  const sent = await read(() => client.listEmails({ campaign_id: campaignId, email_type: "sent", limit }));
  if (sent.status < 200 || sent.status >= 300 || !Array.isArray(sent.body?.items)
    || sent.body.items.some(item => !matchesCampaign(item, campaignId))) return null;
  const received = await read(() => client.listEmails({ campaign_id: campaignId, email_type: "received", limit }));
  const receivedUsable = received.status >= 200 && received.status < 300
    && Array.isArray(received.body?.items)
    && received.body.items.every(item => matchesCampaign(item, campaignId));
  const address = (item, keys) => {
    const value = keys.map(key => item[key]).find(value => typeof value === "string" && value.trim());
    return value ? value.split(",")[0].trim().toLowerCase() : null;
  };
  const recipients = new Set(sent.body.items.map(item =>
    address(item, ["to_address_email_list", "to_address_email", "lead"])).filter(Boolean));
  const repliers = receivedUsable ? new Set(received.body.items.map(item =>
    address(item, ["from_address_email", "from_address", "lead"])).filter(Boolean)) : null;
  return { emails_sent_count: sent.body.items.length, contacted_count: recipients.size,
    reply_count_unique: repliers?.size ?? null, _source: "emails-fallback", _partial: true, _capped_at: limit };
}

function completeMembership(counts) {
  return counts?.ok && !counts.partial && counts.contact_activity_unknown === 0;
}

async function collectCampaignMetrics(client, campaignId, campaign) {
  campaign = campaign || {};
  const responses = await Promise.all([
    read(() => client.campaignAnalytics(campaignId)),
    read(() => client.analyticsOverview([campaignId])),
  ]);
  const sources = ["campaign-analytics", "campaign-filtered-overview"];
  let metrics = {};
  const fieldSources = {};
  const rejected = [];
  for (const [index, response] of responses.entries()) {
    if (!(response.status >= 200 && response.status < 300) || !response.body
      || typeof response.body !== "object" || Array.isArray(response.body)) continue;
    if (!matchesCampaign(response.body, campaignId)) { rejected.push(sources[index]); continue; }
    if (!COUNTERS.some(key => metricNumber(response.body[key]) != null)) continue;
    if (!metrics._source) {
      metrics = Object.fromEntries(Object.entries(response.body).filter(([key]) => !key.startsWith("_")));
      metrics._source = sources[index];
    }
    for (const key of COUNTERS) {
      if (metricNumber(response.body[key]) != null && !fieldSources[key]) {
        metrics[key] = response.body[key];
        fieldSources[key] = sources[index];
      }
    }
  }
  if (!metrics._source) {
    const fallback = await emailSample(client, campaignId);
    const unavailable = fallback || { _source: "unavailable", _partial: true };
    if (rejected.length) unavailable._rejected_sources = rejected;
    return { metrics: unavailable, leadCounts: null };
  }
  metrics._field_sources = fieldSources;
  if (rejected.length) metrics._rejected_sources = rejected;

  // Missing complaints cannot make an otherwise complete bounce observation
  // partial. A bounded email sample cannot fill that missing complaint signal.
  const activity = [metrics.emails_sent_count, metrics.new_leads_contacted_count,
    metrics.reply_count_unique, metrics.bounced_count].some(value => metricNumber(value) > 0);
  if (metrics.contacted_count === 0 && !activity && campaign.lead_stats == null) {
    const sample = await emailSample(client, campaignId);
    if (sample && sample.emails_sent_count > 0 && !(metrics.emails_sent_count > 0))
      return { metrics: { ...sample, _analytics_rejected_reason: "zero_activity_contradicted_by_emails" }, leadCounts: null };
  }

  let leadCounts = null;
  const membership = async () => {
    if (leadCounts == null) leadCounts = await client.countLeads(campaignId).catch(() => ({ ok: false }));
    return leadCounts;
  };
  const raw = metricNumber(metrics.contacted_count);
  const newContacts = metricNumber(metrics.new_leads_contacted_count);
  // Already needed for utilization with null lead_stats. A disagreement between
  // counters can also expose repeat sends counted as unique within a large list.
  if (metricNumber(campaign.lead_stats?.total) == null
    || (raw != null && newContacts != null && raw !== newContacts)) await membership();
  const corroborated = completeMembership(leadCounts) && newContacts === leadCounts.contacted;
  const totals = [campaign.lead_stats?.total, metrics.leads_count,
    leadCounts?.ok && !leadCounts.partial ? leadCounts.total : null].map(metricNumber).filter(value => value != null);
  const invalid = raw == null || !Number.isInteger(raw) || totals.some(total => raw > total)
    || (corroborated && raw !== leadCounts.contacted)
    || (raw === 0 && (activity || (completeMembership(leadCounts) && leadCounts.contacted > 0)));
  if (invalid) {
    const counts = await membership();
    const populationMatches = completeMembership(counts)
      && newContacts === counts.contacted
      && !(counts.contacted === 0 && activity);
    metrics._raw_contacted_count = metrics.contacted_count ?? null;
    metrics._contacted_count_recovery = { source: "campaign-leads", complete: !!completeMembership(counts),
      total: counts.total ?? null, contacted: counts.contacted ?? null, population_matches: !!populationMatches };
    metrics.contacted_count = populationMatches ? counts.contacted : null;
    delete fieldSources.contacted_count;
    if (populationMatches) fieldSources.contacted_count = "campaign-leads";
  }
  return { metrics, leadCounts };
}

module.exports = { collectCampaignMetrics };
