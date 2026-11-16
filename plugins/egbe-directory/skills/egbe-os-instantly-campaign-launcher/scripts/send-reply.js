#!/usr/bin/env node
// The agent's way to act on one queued reply (reply-queue.json, written by
// reply-worker.js): send the reply it wrote, in the same thread from the
// mailbox that received the message, or close the item without sending.
//
//   node send-reply.js --run-dir <run> --email-id <id> --text-file reply.txt
//   node send-reply.js --run-dir <run> --email-id <id> --mark owner_review|no_reply|opt_out
// --mark opt_out confirms the agent read the reply; --recipient-email is needed
// when a forwarded reply cannot be associated with the original recipient.
//
// Run it for one message at a time; the queue lock serialises writes, but two
// sends for different messages in parallel gain nothing.
const fs = require("fs");
const path = require("path");
const { InstantlyClient } = require("./lib/instantly-client");
const {
  readJson,
  parseArgs,
  isoNow,
  loadRunEnv,
  getOsConfig,
  assertCampaignNotForeign,
} = require("./lib/helpers");
const {
  initDb,
  insertLeadEvent,
  setReplyQueueStatus,
  queryAll,
  upsertLead,
  confirmOptOut,
} = require("./lib/outreach-db");
const { updateQueue } = require("./lib/reply-queue");
const { readOptOutHistory, assertRecipientNotOptedOut, resolveCampaignRecipient,
  stopConfirmedRecipient } = require("./lib/confirmed-opt-outs");

// owner_review / no_reply close a queued item. sent / pending resolve an item
// left in "sending" by a process that died mid-send: check the thread in
// Instantly first, then record what actually happened.
const MARKS = ["owner_review", "no_reply", "opt_out"];
const RESOLVE_SENDING = ["sent", "pending"];
const OPEN = ["pending", "owner_review"];

function claim(runDir, emailId, campaignId, check) {
  return updateQueue(runDir, (queue) => {
    const item = queue.find((q) => q.email_id === emailId);
    if (!item) throw new Error(`Message ${emailId} is not in this run's reply queue`);
    if (item.campaign_id !== campaignId)
      throw new Error(`Message ${emailId} belongs to another campaign`);
    return check(item);
  });
}

function setStatus(runDir, emailId, status, extra = {}) {
  updateQueue(runDir, (queue) => {
    Object.assign(queue.find((q) => q.email_id === emailId), { status, ...extra });
  });
}

async function main() {
  const args = parseArgs(process.argv);
  const runDir = args["run-dir"] ? path.resolve(args["run-dir"]) : null;
  const emailId = args["email-id"];
  if (!runDir || !emailId) throw new Error("Missing --run-dir or --email-id");
  const mark = args.mark;
  if (mark && !MARKS.includes(mark) && !RESOLVE_SENDING.includes(mark))
    throw new Error(`--mark must be one of: ${[...MARKS, ...RESOLVE_SENDING].join(", ")}`);
  const text = args["text-file"]
    ? fs.readFileSync(path.resolve(args["text-file"]), "utf8").trim()
    : "";
  if (!mark && !text) throw new Error("Give --text-file with the reply, or --mark");

  const connectionEnvFile = loadRunEnv(runDir, args["env-file"]);
  const manifest = readJson(path.join(runDir, "manifest.json"));
  if (!manifest?.campaign?.id) throw new Error("Run manifest missing campaign ID");
  const campaignId = manifest.campaign.id;
  if (!mark || mark === "opt_out") readOptOutHistory(runDir);
  const dbPath = initDb(runDir);
  const at = isoNow();
  const record = (status) =>
    setReplyQueueStatus(dbPath, { run_key: manifest.run_key, message_id: emailId, status });

  if (mark && mark !== "opt_out") {
    claim(runDir, emailId, campaignId, (item) => {
      const from = item.status || "pending";
      if (RESOLVE_SENDING.includes(mark) ? from !== "sending" : !OPEN.includes(from))
        throw new Error(`Message ${emailId} is ${from}; --mark ${mark} does not apply`);
      Object.assign(item, { status: mark, handled_at: at });
    });
    record(mark);
    console.log(JSON.stringify({ email_id: emailId, action: mark, at }));
    return;
  }

  // Keep the durable refusal even if provider access is temporarily unavailable.
  // The queue records any unresolved scoped pause for the next agent to handle.
  const queued = claim(runDir, emailId, campaignId, (item) => {
    const from = item.status || "pending";
    if (from === "sending")
      throw new Error(`Message ${emailId} is "sending": check the thread in Instantly, then --mark sent or --mark pending`);
    if (!OPEN.includes(from) && !(mark === "opt_out" && from === "no_reply"))
      throw new Error(`Message ${emailId} is already handled (${from})`);
    return { ...item };
  });
  const localRecipients = new Set(queryAll(dbPath,
    `SELECT email FROM run_leads WHERE run_key = ? AND
     (imported_at IS NOT NULL OR last_contacted_at IS NOT NULL)`, [manifest.run_key])
    .map((lead) => lead.email));
  let client;
  const getClient = () => {
    if (client) return client;
    const os = getOsConfig();
    if (os.missing.length) throw new Error(`Missing ${os.missing.join(" and ")}`);
    client = new InstantlyClient({ connectionEnvFile, osApiKey: os.osApiKey, osUrl: os.osUrl });
    return client;
  };
  let recipient;
  try {
    recipient = resolveCampaignRecipient(queued, localRecipients, args["recipient-email"]);
  } catch (_) {
    const members = await getClient().listLeadEmails(campaignId);
    if (!members.ok) throw new Error("Campaign recipient lookup incomplete; inspect the original thread before acting");
    recipient = resolveCampaignRecipient(queued, members.emails, args["recipient-email"]);
  }
  if (mark === "opt_out") {
    claim(runDir, emailId, campaignId, (item) => {
      if (![...OPEN, "no_reply"].includes(item.status || "pending"))
        throw new Error(`Message ${emailId} changed status; inspect before confirming opt-out`);
      if (item.opt_out_confirmed && item.recipient_email !== recipient)
        throw new Error("This message already confirmed a different recipient; inspect the original thread");
      if (!queryAll(dbPath, "SELECT email FROM leads WHERE email = ?", [recipient]).length)
        upsertLead(dbPath, { email: recipient, source: "instantly-reply" });
      // Commit first: failed persistence must never close the JSON queue.
      confirmOptOut(dbPath, { run_key: manifest.run_key, email: recipient,
        campaign_id: campaignId, message_id: emailId, event_at: at });
      Object.assign(item, { status: "no_reply", handled_at: at, recipient_email: recipient,
        opt_out_confirmed: true, opt_out_provider: { ok: false, pending: true } });
    });
    record("no_reply");
    let provider;
    try {
      provider = await stopConfirmedRecipient(getClient(), runDir, recipient);
    } catch (error) {
      provider = { ok: false, error: error.message };
    }
    setStatus(runDir, emailId, "no_reply", { opt_out_provider: provider });
    console.log(JSON.stringify({ email_id: emailId, recipient_email: recipient,
      action: "opt_out_confirmed", provider, at }));
    if (!provider.ok) process.exitCode = 1;
    return;
  }
  assertRecipientNotOptedOut(runDir, recipient);
  // A reply can go to a forwarder rather than the original lead. Check both.
  if (queued.from_email) assertRecipientNotOptedOut(runDir, queued.from_email);
  getClient();
  const campaign = await client.getCampaign(campaignId);
  if (!(campaign.status >= 200 && campaign.status < 300))
    throw new Error(`Campaign lookup failed: ${campaign.status}`);
  assertCampaignNotForeign(
    campaign.body,
    readJson(path.join(runDir, "state", "ownership.json"), manifest.ownership || {}),
    `campaign ${campaignId}`,
  );

  // Claim the item before calling the API. If this process dies after the
  // send, the item stays "sending" and no later run sends it again.
  const item = claim(runDir, emailId, campaignId, (it) => {
    const from = it.status || "pending";
    if (from === "sending")
      throw new Error(
        `Message ${emailId} is "sending": a previous send may have gone out. Check the thread in Instantly, then --mark sent or --mark pending`,
      );
    if (!OPEN.includes(from)) throw new Error(`Message ${emailId} is already handled (${from})`);
    if (!it.eaccount)
      throw new Error("Receiving mailbox unknown for this message; answer it in Instantly by hand");
    assertRecipientNotOptedOut(runDir, recipient);
    if (it.from_email) assertRecipientNotOptedOut(runDir, it.from_email);
    Object.assign(it, { status: "sending", sending_at: at });
    return { ...it };
  });
  record("sending");

  const subject = item.subject
    ? /^re:/i.test(item.subject) ? item.subject : `Re: ${item.subject}`
    : "Re:";
  const res = await client.replyToEmail({
    reply_to_uuid: emailId,
    eaccount: item.eaccount,
    subject,
    body: { text },
  });
  if (res.status >= 400 && res.status < 500) {
    // Rejected by the API, so nothing was sent: back to the open queue.
    setStatus(runDir, emailId, "pending");
    record("pending");
    console.log(JSON.stringify({ email_id: emailId, action: "reply_failed", status: res.status, at }));
    process.exitCode = 1;
    return;
  }
  if (!(res.status >= 200 && res.status < 300)) {
    // A 5xx can come after Instantly sent the email: leave the item "sending"
    // so it is checked in the thread instead of being sent again.
    console.log(
      JSON.stringify({
        email_id: emailId,
        action: "reply_unknown",
        status: res.status,
        next: "check the thread in Instantly, then --mark sent or --mark pending",
        at,
      }),
    );
    process.exitCode = 1;
    return;
  }
  setStatus(runDir, emailId, "sent", { handled_at: at, reply_text: text });
  record("sent");
  if (recipient) {
    insertLeadEvent(dbPath, {
      run_key: manifest.run_key,
      email: recipient,
      event_type: "reply_sent",
      event_at: at,
      payload_json: { email_id: emailId, status: res.status },
    });
  }
  console.log(JSON.stringify({ email_id: emailId, action: "replied", status: res.status, at }));
}

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exit(1);
});
