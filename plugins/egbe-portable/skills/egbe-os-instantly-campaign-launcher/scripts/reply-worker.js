#!/usr/bin/env node
const path = require("path");
const { InstantlyClient } = require("./lib/instantly-client");
const {
  readJson,
  writeJson,
  parseArgs,
  isoNow,
  loadRunEnv,
  getOsConfig,
  assertCampaignNotForeign,
} = require("./lib/helpers");
const {
  initDb,
  upsertLead,
  upsertRunLead,
  insertLeadEvent,
  upsertReplyQueueItem,
  queryAll,
} = require("./lib/outreach-db");
const { resolveCampaignRecipient, readOptOutHistory } = require("./lib/confirmed-opt-outs");
const { updateQueue } = require("./lib/reply-queue");

// A hint for the agent, not a decision: the agent reads every queued reply and
// decides by references/reply-handling.md. Refusals and opt-outs are checked
// before interest so "not interested" never reads as positive.
function classify(email) {
  const text = String(email?.body?.text || "").toLowerCase();
  if (/\bunsubscribe\b|\bremove me\b|\bopt[- ]?out\b|\b(?:do not|don'?t|never) (?:call|contact|email|e-mail|write to|message) (?:me|us)\b|^\s*stop\s*[.!]?\s*$/m.test(text))
    return "unsubscribe";
  if (/\bnot (?:interested|relevant|a fit)\b|\bno,? thanks?\b|\bwrong person\b|\bnot the right person\b/.test(text))
    return "negative";
  if (/\bprice\b|\bpricing\b|\bcost\b|\bhow much\b/.test(text)) return "pricing";
  if (/\binterested\b|\blet'?s talk\b|\bavailable\b|\bbook\b|\bcall\b|\bdemo\b/.test(text))
    return "positive";
  return "ambiguous";
}

async function unreadReplies(client, campaignId) {
  const items = [];
  const cursors = new Set();
  let cursor;
  // Bound malformed provider pagination and stay within its 20 email reads/min.
  // Collect every page before advancing the local queue/processed checkpoint.
  for (let page = 0; page < 100; page++) {
    const res = await client.listEmails({
      campaign_id: campaignId,
      email_type: "received",
      is_unread: true,
      limit: 100,
      ...(cursor === undefined ? {} : { starting_after: cursor }),
    });
    if (!(res.status >= 200 && res.status < 300))
      throw new Error(`Email list failed: ${res.status}`);
    if (!Array.isArray(res.body?.items))
      throw new Error("Email list returned invalid items; collection incomplete");
    if (!res.body.items.length) return items;
    items.push(...res.body.items);
    const next = res.body.next_starting_after;
    if (next === undefined || next === null) return items;
    if (typeof next !== "string" || !next.trim() || cursors.has(next))
      throw new Error("Email list returned an invalid or repeated cursor; collection incomplete");
    cursors.add(next);
    cursor = next;
    if (page < 99) await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  throw new Error("Email list page limit reached; collection incomplete");
}

async function main() {
  const args = parseArgs(process.argv);
  const runDir = args["run-dir"] ? path.resolve(args["run-dir"]) : null;
  if (!runDir) throw new Error("Missing --run-dir");
  const connectionEnvFile = loadRunEnv(runDir, args["env-file"]);
  const manifest = readJson(path.join(runDir, "manifest.json"));
  let spec = readJson(path.join(runDir, "run-spec.json"));
  // launch-campaign.js no longer bakes derived values (sender identity,
  // chosen mailboxes) into the operator's run-spec; they live in
  // state/resolved-run-spec.json. Overlay only the derived fields so any
  // operator edit to run-spec.json still wins.
  const resolvedSpec = readJson(
    path.join(runDir, "state", "resolved-run-spec.json"),
    null,
  );
  if (!spec && resolvedSpec) {
    // Operator input missing (moved/renamed) — the resolved spec is a full
    // superset from launch time; better than crashing every 10-minute tick.
    spec = resolvedSpec;
  }
  if (!spec) {
    throw new Error(
      "run-spec.json not found in the run dir (and no state/resolved-run-spec.json to fall back to)",
    );
  }
  if (spec && resolvedSpec && spec !== resolvedSpec) {
    spec.reply_policy = spec.reply_policy || {};
    if (!spec.reply_policy.sender_name) {
      spec.reply_policy.sender_name = resolvedSpec.reply_policy?.sender_name;
    }
    if (!spec.reply_policy.reply_from_email) {
      spec.reply_policy.reply_from_email =
        resolvedSpec.reply_policy?.reply_from_email;
    }
    spec.campaign = spec.campaign || {};
    if (
      !Array.isArray(spec.campaign.email_list) ||
      !spec.campaign.email_list.length
    ) {
      spec.campaign.email_list = resolvedSpec.campaign?.email_list;
    }
  }
  const ownership = readJson(
    path.join(runDir, "state", "ownership.json"),
    manifest?.ownership || {},
  );
  if (!manifest?.campaign?.id)
    throw new Error("Run manifest missing campaign ID");
  const history = readOptOutHistory(runDir);
  if (!history.runs.some((run) => run.run_key === manifest.run_key && run.campaign_id === manifest.campaign.id))
    throw new Error("Reply collection requires this run's existing outreach.db history; restore it before collecting replies");
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
  const dbPath = initDb(runDir);
  const knownRecipients = new Set(queryAll(dbPath,
    `SELECT email FROM run_leads WHERE run_key = ? AND
     (imported_at IS NOT NULL OR last_contacted_at IS NOT NULL)`, [manifest.run_key])
    .map((lead) => lead.email));

  const stateDir = path.join(runDir, "state");
  const processedPath = path.join(stateDir, "processed-replies.json");
  const processed = new Set(readJson(processedPath, []));
  const added = [];

  const items = await unreadReplies(client, manifest.campaign.id);

  const actions = [];
  if (spec.reply_policy?.auto_reply_enabled) {
    console.error(
      "reply_policy.auto_reply_enabled is ignored: the agent answers queued replies with send-reply.js",
    );
  }
  for (const email of items) {
    if (!email?.id || processed.has(email.id)) continue;
    const fromEmail =
      email.from_address_email || email.email_from || email.from || null;
    // Provider association, when exposed as an address, wins over the author
    // of a forwarded message. Unresolved identity stays explicit in the queue.
    const leadEmail = email.lead_email || (typeof email.lead === "string" && email.lead.includes("@") ? email.lead : null);
    let recipientEmail = null;
    try {
      recipientEmail = resolveCampaignRecipient({ from_email: fromEmail, lead_email: leadEmail }, knownRecipients);
    } catch (_) { /* The agent must inspect the original thread before acting. */ }
    upsertLead(dbPath, {
      email: fromEmail,
      first_name: email.from_address_name || null,
      source: "instantly-reply",
    });
    const intent = classify(email);
    const actionAt = isoNow();

    if (fromEmail) {
      if (recipientEmail) upsertRunLead(dbPath, {
        run_key: manifest.run_key,
        email: recipientEmail,
        campaign_id: manifest.campaign.id,
        last_known_status: "replied",
        last_replied_at: actionAt,
        reply_intent: intent,
        ownership_tag: ownership.run_tag_label,
      });
      insertLeadEvent(dbPath, {
        run_key: manifest.run_key,
        email: fromEmail,
        event_type: "reply_received",
        event_at: actionAt,
        payload_json: {
          email_id: email.id,
          intent,
          subject: email.subject || null,
        },
      });
      upsertReplyQueueItem(dbPath, {
        run_key: manifest.run_key,
        email: fromEmail,
        message_id: email.id,
        intent,
        status: "pending",
      });
    }
    // Everything the agent needs to answer in the same thread with the same
    // mailbox; send-reply.js reads it back from here.
    added.push({
      email_id: email.id,
      campaign_id: manifest.campaign.id,
      from_email: fromEmail,
      recipient_email: recipientEmail,
      lead_email: leadEmail,
      from_name: email.from_address_name || null,
      eaccount:
        typeof email.eaccount === "string" && email.eaccount.trim()
          ? email.eaccount.trim()
          : null,
      subject: email.subject || null,
      text: String(email?.body?.text || "").slice(0, 4000),
      intent_hint: intent,
      status: "pending",
      at: actionAt,
    });
    actions.push({ email_id: email.id, intent_hint: intent, action: "queued", at: actionAt });
    processed.add(email.id);
  }

  // Append under the queue lock: send-reply.js may be changing statuses in
  // the same file, and a whole-file rewrite from here would undo them.
  const pending = updateQueue(runDir, (queue) => {
    const known = new Set(queue.map((q) => q.email_id));
    for (const item of added) if (!known.has(item.email_id)) queue.push(item);
    return queue.filter((q) => q.status === "pending").length;
  });
  // A failed queue write must leave these replies collectable on the next tick.
  writeJson(processedPath, Array.from(processed));
  console.log(
    JSON.stringify(
      {
        run_key: manifest.run_key,
        campaign_id: manifest.campaign.id,
        inspected: items.length,
        actions,
        pending,
      },
      null,
      2,
    ),
  );
}

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exit(1);
});
