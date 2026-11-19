// Known local project opt-outs only; owned exact-ID exclusion with scoped
// campaign containment when native exclusion cannot be confirmed.
const { assessRecipient } = require("./recipient-exclusion");
const fs = require("fs");
const path = require("path");
const { DatabaseSync } = require("node:sqlite");
const { normalizeEmail, readJson, assertCampaignNotForeign } = require("./helpers");
const { dbPathForRun } = require("./outreach-db");

function successful(response) {
  return response?.status >= 200 && response.status < 300;
}

function hasSendingEvidence(value) {
  if (!value || typeof value !== "object") return false;
  if (Array.isArray(value)) return value.some(hasSendingEvidence);
  if (value.first_launched_at || value.last_activated_at) return true;
  if (["launched", "active", "sending"].includes(value.launch_status || value.status)) return true;
  if (successful(value.activation) || value.campaign_status === 1) return true;
  for (const key of ["emails_sent_count", "contacted_count", "reply_count", "reply_count_unique", "unique_replies", "sent_count", "contacted", "emails_sent", "replies"])
    if (Number(value[key]) > 0) return true;
  return ["campaign", "metrics", "metrics_summary", "observation", "sending_status"].some((key) => hasSendingEvidence(value[key]));
}

function recoveryRuns(runDir) {
  const directory = path.dirname(path.resolve(runDir));
  if (!fs.existsSync(directory)) return [];
  const runs = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const dir = path.join(directory, entry.name);
    const manifest = readJson(path.join(dir, "manifest.json"), null);
    const summary = readJson(path.join(dir, "launch-summary.json"), null);
    const monitor = readJson(path.join(dir, "monitor-summary.json"), null);
    const history = readJson(path.join(dir, "state", "analytics-history.json"), []);
    const conclusion = readJson(path.join(dir, "conclusion.json"), null);
    const queue = readJson(path.join(dir, "reply-queue.json"), []);
    const processed = readJson(path.join(dir, "state", "processed-replies.json"), []);
    if (!Array.isArray(queue) || !Array.isArray(processed) || !Array.isArray(history))
      throw new Error(`Opt-out history unknown: malformed recovery state in ${dir}`);
    const sent = [manifest, summary, monitor, history, conclusion].some(hasSendingEvidence)
      || (Array.isArray(queue) && queue.length > 0) || (Array.isArray(processed) && processed.length > 0);
    const run_key = manifest?.run_key || summary?.run_key || monitor?.run_key || conclusion?.run_key;
    const campaign_id = manifest?.campaign?.id || summary?.campaign_id || monitor?.campaign_id
      || conclusion?.campaign_id;
    if (sent && (!run_key || !campaign_id))
      throw new Error(`Opt-out history unknown: sending recovery artifacts in ${dir} lack run/campaign identity`);
    if (run_key || campaign_id) runs.push({ run_key, campaign_id, sent, runDir: dir,
      confirmed: queue.filter((item) => item.opt_out_confirmed),
      ownership: readJson(path.join(dir, "state", "ownership.json"), manifest?.ownership || {}) });
  }
  return runs;
}

function readOptOutHistory(runDir) {
  const dbPath = dbPathForRun(runDir);
  let db;
  try {
    const recovered = recoveryRuns(runDir);
    if (!fs.existsSync(dbPath)) {
      if (recovered.some((run) => run.sent))
        throw new Error("outreach.db is missing but recovery artifacts show prior sending");
      return { dbPath, emails: new Set(), runs: [], recoveryRuns: recovered };
    }
    // Never call initDb here: an empty replacement must not look like history.
    db = new DatabaseSync(dbPath, { readOnly: true });
    db.exec("PRAGMA busy_timeout=5000;");
    const runs = db.prepare("SELECT run_key, campaign_id, status FROM outreach_runs").all();
    db.prepare("SELECT run_key, email, imported_at, last_contacted_at FROM run_leads LIMIT 0").all();
    const events = db.prepare("SELECT run_key, email, payload_json FROM lead_events WHERE event_type = 'opt_out_confirmed'").all();
    if (db.prepare("PRAGMA foreign_key_check").all().length)
      throw new Error("outreach.db has incomplete related history");
    for (const run of recovered.filter((item) => item.sent)) {
      if (!runs.some((row) => row.run_key === run.run_key && row.campaign_id === run.campaign_id))
        throw new Error(`sending run ${run.run_key} (${run.campaign_id}) is missing from outreach.db`);
    }
    const emails = new Set();
    for (const event of events) {
      const payload = JSON.parse(event.payload_json);
      const email = normalizeEmail(event.email);
      if (!email || !payload?.message_id || !payload?.campaign_id)
        throw new Error("confirmed opt-out event is incomplete");
      emails.add(email);
    }
    for (const run of recovered) {
      for (const item of run.confirmed) {
        if (!events.some((event) => event.run_key === run.run_key
          && normalizeEmail(event.email) === normalizeEmail(item.recipient_email)
          && JSON.parse(event.payload_json)?.message_id === item.email_id))
          throw new Error(`confirmed reply ${item.email_id} is missing from outreach.db`);
      }
    }
    return { dbPath, emails, runs, recoveryRuns: recovered };
  } catch (error) {
    throw new Error(`Opt-out history unavailable; restore/check project outreach.db before sending: ${error.message}`);
  } finally {
    db?.close();
  }
}

function filterConfirmedOptOuts(runDir, leads) {
  const history = readOptOutHistory(runDir);
  const excluded = [];
  const allowed = leads.filter((lead) => {
    if (!history.emails.has(normalizeEmail(lead?.email))) return true;
    excluded.push(lead);
    return false;
  });
  return { leads: allowed, excluded, history };
}

function assertRecipientNotOptedOut(runDir, email) {
  email = normalizeEmail(email);
  if (!email) throw new Error("Campaign recipient unknown; verify the original thread before sending");
  if (readOptOutHistory(runDir).emails.has(email))
    throw new Error(`Recipient ${email} has a confirmed opt-out; no reply may be sent`);
}

// A forwarded reply's author is not automatically the campaign recipient.
// An explicit operator selection is still checked against campaign membership.
function resolveCampaignRecipient(item, knownEmails, explicit) {
  const known = new Set([...knownEmails].map(normalizeEmail));
  const supplied = explicit || item.recipient_email || item.lead_email;
  if (supplied) {
    const candidate = normalizeEmail(supplied);
    if (!known.has(candidate)) throw new Error("Selected recipient is not a known lead in this campaign");
    return candidate;
  }
  const author = normalizeEmail(item.from_email);
  if (known.has(author)) return author;
  throw new Error("Campaign recipient unknown (possibly a forwarded reply); check the original thread and pass --recipient-email");
}

function campaignSafetyReadback(campaign) {
  return Object.fromEntries(["stop_on_reply", "stop_on_auto_reply", "insert_unsubscribe_header"]
    .map((key) => [key, typeof campaign?.[key] === "boolean" ? campaign[key] : null]));
}

function checkKnownOwnership(campaign, ownership, campaignId) {
  // Missing local tags cannot overrule a successful tenant-authorized gateway
  // read. When expectations exist, preserve the local conflict check as well.
  if (ownership && ["run_tag_id", "agent_tag_id", "run_tag_label", "agent_tag_label"].some((key) => ownership[key]))
    assertCampaignNotForeign(campaign, ownership, `campaign ${campaignId}`);
}

async function stopConfirmedRecipient(client, runDir, email) {
  email = normalizeEmail(email);
  const history = readOptOutHistory(runDir);
  if (!history.emails.has(email)) throw new Error("Recipient has no confirmed opt-out event");
  const campaigns = new Map();
  for (const run of [...history.runs, ...history.recoveryRuns]) {
    if (!run.campaign_id) continue;
    campaigns.set(run.campaign_id, { ...(campaigns.get(run.campaign_id) || {}), ...run });
  }
  const results = [];
  for (const [campaignId, run] of campaigns) {
    const result = { campaign_id: campaignId, run_key: run.run_key, stopped: false };
    results.push(result);
    try {
      // This gateway read is tenant-authorized; local tags only reject a known
      // conflict and never grant permission to touch another campaign.
      const response = await client.getCampaign(campaignId);
      if (!successful(response)) throw new Error(`Campaign readback failed (${response.status}); ownership/stop unknown`);
      checkKnownOwnership(response.body, run.ownership, campaignId);
      result.settings = campaignSafetyReadback(response.body);
      result.campaign_status = response.body?.status ?? null;
      const exclusion = await assessRecipient(client, campaignId, email, { confirmed: true, mutate: true });
      result.recipient_exclusion = exclusion;
      result.membership = exclusion.state === "absent" ? "absent" : exclusion.evidence?.length ? "present" : "unknown";
      if (["absent", "excluded"].includes(exclusion.state)) {
        result.stopped = true;
        result.action = exclusion.state === "absent" ? "recipient_absent" : "recipient_excluded";
        continue;
      }
      if (response.body?.status === 2) {
        result.stopped = true;
        result.action = "campaign_already_paused";
        continue;
      }
      // Settings alone do not prove this lead stopped. Unsupported or uncertain
      // native exclusion still requires containment of this owned campaign.
      // Unknown membership is conservatively contained by pausing this owned
      // campaign too; no global campaign/account pause is performed.
      try {
        const pause = await client.pauseCampaign(campaignId);
        result.pause_status = pause.status;
      } catch (error) {
        // A timeout may follow a successful pause; read before retrying it.
        result.pause_error = error.message;
      }
      const readback = await client.getCampaign(campaignId);
      if (successful(readback))
        checkKnownOwnership(readback.body, run.ownership, campaignId);
      result.readback_status = successful(readback) ? readback.body?.status ?? null : null;
      result.stopped = successful(readback) && readback.body?.status === 2;
      result.action = result.stopped ? "campaign_paused" : "provider_action_unresolved";
      if (!result.stopped) result.error = "Recipient stop unconfirmed after scoped pause; inspect provider before resuming";
    } catch (error) {
      result.action = "provider_action_unresolved";
      result.error = error.message;
    }
  }
  return { email, ok: results.length > 0 && results.every((result) => result.stopped), campaigns: results,
    limitation: "Known local project campaigns only; main-sequence exclusion does not cancel in-flight mail; campaign pause is containment, not provider-wide suppression" };
}

module.exports = { readOptOutHistory, filterConfirmedOptOuts, assertRecipientNotOptedOut,
  resolveCampaignRecipient, campaignSafetyReadback, stopConfirmedRecipient };
