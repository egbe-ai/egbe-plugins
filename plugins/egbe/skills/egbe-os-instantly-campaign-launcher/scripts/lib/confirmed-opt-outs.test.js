const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const store = require("./outreach-db");
const guards = require("./confirmed-opt-outs");

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "egbe-confirmed-optout-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const run = path.join(root, "run-a");
  fs.mkdirSync(run);
  const db = store.initDb(run);
  const email = "recipient@example.test";
  store.upsertRun(db, { run_key: "run-a", campaign_id: "campaign-a", status: "launched" });
  store.upsertLead(db, { email });
  store.upsertRunLead(db, { run_key: "run-a", campaign_id: "campaign-a", email,
    imported_at: "2026-10-01T00:00:00Z" });
  return { root, run, db, email };
}

function confirm(f, extra = {}) {
  return store.confirmOptOut(f.db, { run_key: "run-a", campaign_id: "campaign-a",
    email: f.email, message_id: "message-a", ...extra });
}

function json(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data));
}

test("confirmed opt-outs are normalized, idempotent, cross-run and survive upsert/cleanup", (t) => {
  const f = fixture(t);
  assert.equal(confirm(f, { email: " Recipient@Example.Test " }).inserted, true);
  assert.equal(confirm(f).inserted, false);
  store.upsertRun(f.db, { run_key: "run-a", campaign_id: "campaign-a" });
  store.upsertLead(f.db, { email: f.email, source: "apollo" });
  store.upsertRunLead(f.db, { run_key: "run-a", email: f.email, last_known_status: "new" });
  store.insertLeadEvent(f.db, { run_key: "run-a", email: f.email, event_type: "reply_received" });
  store.queryAll(f.db, "DELETE FROM lead_events WHERE run_key = ?", ["run-a"]);
  const events = store.queryAll(f.db, "SELECT * FROM lead_events");
  assert.equal(events.length, 1);
  assert.equal(events[0].event_type, "opt_out_confirmed");
  const result = guards.filterConfirmedOptOuts(path.join(f.root, "next-run"), [
    { email: "RECIPIENT@example.test" }, { email: "new@example.test" },
  ]);
  assert.deepEqual(result.leads, [{ email: "new@example.test" }]);
  assert.equal(result.excluded.length, 1);
  assert.throws(() => guards.assertRecipientNotOptedOut(f.run, " RECIPIENT@example.test "), /confirmed opt-out/);
});

test("regex and old no_reply records never become confirmed opt-outs", (t) => {
  const f = fixture(t);
  store.upsertRunLead(f.db, { run_key: "run-a", email: f.email, last_known_status: "unsubscribed", reply_intent: "unsubscribe" });
  store.upsertReplyQueueItem(f.db, { run_key: "run-a", email: f.email, message_id: "old", intent: "unsubscribe", status: "no_reply" });
  store.insertLeadEvent(f.db, { run_key: "run-a", email: f.email, event_type: "reply_received",
    payload_json: { intent: "unsubscribe" } });
  assert.equal(guards.readOptOutHistory(f.run).emails.size, 0);
});

test("missing database allows a truly new project, not recovery evidence of sends", (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "egbe-new-optout-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const run = path.join(root, "new-run");
  fs.mkdirSync(run);
  assert.equal(guards.readOptOutHistory(run).emails.size, 0);
  assert.equal(fs.existsSync(path.join(root, "outreach.db")), false);
  json(path.join(run, "manifest.json"), { run_key: "new-run", campaign: { id: "campaign-a" } });
  // A prepared draft is not evidence of sends.
  assert.equal(guards.readOptOutHistory(run).emails.size, 0);
  json(path.join(run, "launch-summary.json"), { run_key: "new-run", campaign_id: "campaign-a", launch_status: "launched" });
  assert.throws(() => guards.readOptOutHistory(run), /missing.*prior sending/);
});

test("an initialized replacement missing a known sending run is not trusted", (t) => {
  const f = fixture(t);
  json(path.join(f.root, "run-b", "manifest.json"), { run_key: "run-b", campaign: { id: "campaign-b" } });
  json(path.join(f.root, "run-b", "monitor-summary.json"), { metrics: { contacted_count: 1 } });
  assert.throws(() => guards.readOptOutHistory(f.run), /sending run run-b.*missing/);
});

test("read errors and partial schema are never an empty suppression list", (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "egbe-bad-optout-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.writeFileSync(path.join(root, "outreach.db"), "not sqlite");
  assert.throws(() => guards.readOptOutHistory(path.join(root, "run")), /history unavailable/);
  const f = fixture(t);
  store.queryAll(f.db, "DROP TABLE reply_queue");
  store.queryAll(f.db, "DROP TABLE lead_events");
  assert.throws(() => guards.readOptOutHistory(f.run), /history unavailable/);
});

test("confirmation mirrored in queue but absent from DB blocks automatic sending", (t) => {
  const f = fixture(t);
  json(path.join(f.run, "manifest.json"), { run_key: "run-a", campaign: { id: "campaign-a" } });
  json(path.join(f.run, "reply-queue.json"), [{ email_id: "message-a", opt_out_confirmed: true, recipient_email: f.email }]);
  assert.throws(() => guards.readOptOutHistory(f.run), /confirmed reply.*missing/);
});

test("forwarded reply uses known campaign recipient, never an unverified author", () => {
  const known = new Set(["recipient@example.test"]);
  const item = { from_email: "assistant@example.test", lead_email: " Recipient@Example.Test " };
  assert.equal(guards.resolveCampaignRecipient(item, known), "recipient@example.test");
  assert.throws(() => guards.resolveCampaignRecipient({ from_email: item.from_email }, known), /recipient unknown/);
  assert.throws(() => guards.resolveCampaignRecipient(item, known, item.from_email), /not a known lead/);
});

function mockClient(email, overrides = {}) {
  const statuses = { "campaign-a": 1, "campaign-b": 1, "campaign-c": 1 };
  const pauses = [];
  return {
    pauses, statuses,
    getCampaign: async (id) => ({ status: 200, body: { id, status: statuses[id],
      stop_on_reply: true, stop_on_auto_reply: false, insert_unsubscribe_header: true } }),
    listLeadEmails: async () => ({ ok: true, emails: new Set([email]) }),
    pauseCampaign: async (id) => { pauses.push(id); statuses[id] = 2; return { status: 200 }; },
    ...overrides,
  };
}

test("opt-out in A checks and pauses A and B, excludes absent C, and retries without repeat pause", async (t) => {
  const f = fixture(t);
  confirm(f);
  for (const suffix of ["b", "c"]) store.upsertRun(f.db, { run_key: `run-${suffix}`, campaign_id: `campaign-${suffix}` });
  const client = mockClient(f.email, { listLeadEmails: async (id) => ({ ok: true,
    emails: new Set(id === "campaign-c" ? [] : [f.email]) }) });
  const first = await guards.stopConfirmedRecipient(client, f.run, f.email);
  assert.equal(first.ok, true);
  assert.deepEqual(client.pauses, ["campaign-a", "campaign-b"]);
  assert.deepEqual(first.campaigns[0].settings, { stop_on_reply: true, stop_on_auto_reply: false, insert_unsubscribe_header: true });
  assert.equal(first.campaigns[2].action, "recipient_absent");
  assert.equal((await guards.stopConfirmedRecipient(client, f.run, f.email)).ok, true);
  assert.deepEqual(client.pauses, ["campaign-a", "campaign-b"]);
});

test("incomplete lead reads pause only the known owned campaign and require readback", async (t) => {
  const f = fixture(t);
  confirm(f);
  const client = mockClient(f.email, { listLeadEmails: async () => { throw new Error("read timed out"); } });
  const result = await guards.stopConfirmedRecipient(client, f.run, f.email);
  assert.equal(result.ok, true);
  assert.equal(result.campaigns[0].membership, "unknown");
  assert.deepEqual(client.pauses, ["campaign-a"]);
});

test("pause success without readback is unresolved, while a timed-out pause can be verified", async (t) => {
  const f = fixture(t);
  confirm(f);
  const client = mockClient(f.email, { pauseCampaign: async () => ({ status: 200 }) });
  const unresolved = await guards.stopConfirmedRecipient(client, f.run, f.email);
  assert.equal(unresolved.ok, false);
  assert.equal(unresolved.campaigns[0].action, "provider_action_unresolved");
  client.pauseCampaign = async () => { client.statuses["campaign-a"] = 2; throw new Error("timeout"); };
  const verified = await guards.stopConfirmedRecipient(client, f.run, f.email);
  assert.equal(verified.ok, true);
  assert.equal(verified.campaigns[0].pause_error, "timeout");
});

test("ownership rejection never pauses foreign campaign and does not skip other runs", async (t) => {
  const f = fixture(t);
  confirm(f);
  store.upsertRun(f.db, { run_key: "run-b", campaign_id: "campaign-b" });
  const client = mockClient(f.email);
  const get = client.getCampaign;
  client.getCampaign = async (id) => id === "campaign-a" ? { status: 404 } : get(id);
  const result = await guards.stopConfirmedRecipient(client, f.run, f.email);
  assert.equal(result.ok, false);
  assert.deepEqual(client.pauses, ["campaign-b"]);
  assert.match(result.campaigns[0].error, /ownership\/stop unknown/);
});

test("gateway ownership works for DB-only runs without local tag metadata", async (t) => {
  const f = fixture(t);
  confirm(f);
  const client = mockClient(f.email);
  const get = client.getCampaign;
  client.getCampaign = async (id) => {
    const response = await get(id);
    response.body.tags = ["provider-tag"];
    return response;
  };
  assert.equal((await guards.stopConfirmedRecipient(client, f.run, f.email)).ok, true);
  assert.deepEqual(client.pauses, ["campaign-a"]);
});
