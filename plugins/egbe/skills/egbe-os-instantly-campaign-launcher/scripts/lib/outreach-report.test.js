const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { initDb, upsertRun, upsertLead, upsertRunLead, confirmOptOut } = require("./outreach-db");

function report(dbPath, mode = "summary", runKey) {
  const args = [path.resolve(__dirname, "../outreach-report.js"), "--db", dbPath, "--mode", mode];
  if (runKey) args.push("--run-key", runKey);
  const result = spawnSync(process.execPath, args, { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

function reportingFixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "outreach-refusal-report-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const dbPath = initDb(path.join(root, "runs", "one"));
  for (const run_key of ["one", "two"])
    upsertRun(dbPath, { run_key, campaign_id: `campaign-${run_key}`, status: "active" });
  const lead = (run_key, email, status = "replied", reply_intent = null) => {
    upsertLead(dbPath, { email });
    upsertRunLead(dbPath, { run_key, email, campaign_id: `campaign-${run_key}`,
      last_known_status: status, reply_intent });
  };
  const refuse = (run_key, email, message_id, event_at = "2026-11-01T12:00:00Z") =>
    confirmOptOut(dbPath, { run_key, email, message_id, campaign_id: `campaign-${run_key}`, event_at });
  return { dbPath, lead, refuse };
}

test("report cannot create an empty replacement for a missing outreach DB", t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "outreach-report-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const dbPath = path.join(root, "missing", "outreach.db");
  const result = spawnSync(process.execPath, [path.resolve(__dirname, "../outreach-report.js"), "--db", dbPath], { encoding: "utf8" });
  assert.notEqual(result.status, 0);
  assert.equal(fs.existsSync(dbPath), false);
  assert.equal(fs.existsSync(path.dirname(dbPath)), false);
});

test("report reads an existing operational DB without changing its bytes", t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "outreach-report-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const runDir = path.join(root, "runs", "one");
  fs.mkdirSync(runDir, { recursive: true });
  const dbPath = initDb(runDir);
  upsertRun(dbPath, { run_key: "one", campaign_id: "campaign-1", status: "paused" });
  const before = fs.readFileSync(dbPath);
  const result = spawnSync(process.execPath, [path.resolve(__dirname, "../outreach-report.js"), "--db", dbPath], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout)[0].status, "paused");
  assert.deepEqual(fs.readFileSync(dbPath), before);
});

test("summary counts confirmed recipients once despite repeated messages or later status changes", t => {
  const f = reportingFixture(t);
  f.lead("one", "confirmed@example.test");
  f.refuse("one", "confirmed@example.test", "first");
  f.refuse("one", "confirmed@example.test", "first");
  f.refuse("one", "confirmed@example.test", "second");
  f.lead("one", "confirmed@example.test", "imported");
  f.lead("one", "hint-only@example.test", "replied", "unsubscribe");
  f.lead("one", "legacy@example.test", "unsubscribed");
  f.refuse("one", "legacy@example.test", "legacy-confirmation");
  f.lead("one", "provider-only@example.test", "unsubscribed");
  // A confirmed provider member can lack a local run_leads row after recovery.
  upsertLead(f.dbPath, { email: "missing-local-membership@example.test" });
  f.refuse("one", "missing-local-membership@example.test", "provider-member");
  const before = fs.readFileSync(f.dbPath);
  const [row] = report(f.dbPath, "summary", "one");
  assert.equal(row.leads_total, 4);
  assert.equal(row.leads_unsubscribed, 4);
  assert.deepEqual(fs.readFileSync(f.dbPath), before);
});

test("summary attributes refusals to their source run; leads expose project-wide suppression separately", t => {
  const f = reportingFixture(t);
  for (const run of ["one", "two"]) f.lead(run, "shared@example.test", "imported");
  f.lead("two", "other@example.test", "replied", "unsubscribe");
  f.refuse("one", "shared@example.test", "first", "2026-11-01T12:00:00Z");
  f.refuse("one", "shared@example.test", "second", "2026-11-02T12:00:00Z");
  const before = fs.readFileSync(f.dbPath);
  const summaries = report(f.dbPath);
  assert.equal(summaries.find(row => row.run_key === "one").leads_unsubscribed, 1);
  assert.equal(summaries.find(row => row.run_key === "two").leads_unsubscribed, 0);
  const rows = report(f.dbPath, "leads", "two");
  assert.equal(rows.length, 2);
  const suppressed = rows.find(row => row.email === "shared@example.test");
  assert.equal(suppressed.last_known_status, "imported");
  assert.equal(suppressed.opt_out_confirmed, 1);
  assert.equal(suppressed.opt_out_confirmed_at, "2026-11-01T12:00:00Z");
  const hint = rows.find(row => row.email === "other@example.test");
  assert.equal(hint.opt_out_confirmed, 0);
  assert.equal(hint.opt_out_confirmed_at, null);
  assert.deepEqual(fs.readFileSync(f.dbPath), before);
});
