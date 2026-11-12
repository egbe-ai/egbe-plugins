#!/usr/bin/env node
// Tracking controls metric availability, not an automatic marketing verdict.
// Without the tracking pixel Instantly's zero opens are not observed zeros.
//
// Run: node scripts/lib/monitor-open-tracking.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const http = require("node:http");
const { spawn } = require("node:child_process");

const MONITOR = path.resolve(__dirname, "..", "monitor-campaign.js");

// Fake OS outreach gateway: a healthy campaign with 30 contacted, 0 opens,
// 0 replies, 0 bounces. Records pause calls.
function fakeGateway({ campaign, metrics }) {
  const pauses = [];
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://x");
    const send = (status, body) => {
      res.writeHead(status, { "content-type": "application/json" });
      res.end(JSON.stringify(body));
    };
    const base = "/outreach/instantly/campaigns/camp-1";
    if (req.method === "POST" && url.pathname === `${base}/pause`) {
      pauses.push(Date.now());
      campaign.status = 2;
      return send(200, { id: "camp-1", status: 2 });
    }
    if (url.pathname === base) return send(200, campaign);
    if (url.pathname === `${base}/analytics`) return send(200, metrics);
    if (url.pathname === `${base}/sending-status`) return send(200, {});
    return send(404, { error: "not mocked" });
  });
  return new Promise((resolve) =>
    server.listen(0, "127.0.0.1", () => resolve({ server, pauses })),
  );
}

function makeRun(t, spec) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "egbe-monitor-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const runDir = path.join(root, "runs", "fina");
  fs.mkdirSync(path.join(runDir, "state"), { recursive: true });
  fs.writeFileSync(
    path.join(runDir, "manifest.json"),
    JSON.stringify({ run_key: "fina", campaign: { id: "camp-1" } }),
  );
  fs.writeFileSync(path.join(runDir, "run-spec.json"), JSON.stringify(spec));
  return runDir;
}

function runMonitor(runDir, port) {
  return new Promise((resolve) => {
    const env = { ...process.env, OS_URL: `http://127.0.0.1:${port}`, OS_API_KEY: "test" };
    delete env.OS_AGENT_NAME;
    const child = spawn(process.execPath, [MONITOR, "--run-dir", runDir], { env });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c) => (stdout += c));
    child.stderr.on("data", (c) => (stderr += c));
    child.on("close", (status) => resolve({ status, stdout, stderr }));
  });
}

const METRICS = {
  contacted_count: 30,
  emails_sent_count: 30,
  open_count_unique: 0,
  reply_count_unique: 0,
  bounced_count: 0,
};

function spec(openTracking) {
  return {
    run_key: "fina",
    campaign: { open_tracking: openTracking },
    monitoring: { autopause_on_risk: true, thresholds: { max_bounce_rate: 2 } },
    lead_replenishment: { enabled: false },
  };
}

function campaign(extra = {}) {
  return { id: "camp-1", status: 1, email_list: ["a@x.test"], lead_stats: { total: 100 }, ...extra };
}

test("open tracking off in the run spec: no open-rate gate, no pause", async (t) => {
  const { server, pauses } = await fakeGateway({ campaign: campaign(), metrics: { ...METRICS } });
  t.after(() => server.close());
  const runDir = makeRun(t, spec(false));
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = JSON.parse(fs.readFileSync(path.join(runDir, "monitor-summary.json")));
  assert.equal(summary.protection.active, true);
  assert.deepEqual(summary.protection.triggered_gates, []);
  assert.equal(summary.protection.skipped_gates.some(g => g.gate === "open_rate"), false);
  assert.equal(summary.metrics.open_count_unique, null);
  assert.equal(summary.open_tracking.enabled, false);
  assert.equal(summary.open_tracking.source, "run spec");
  assert.equal(summary.derived.open_rate, null);
  assert.equal(summary.pause_suggested, false);
  assert.equal(summary.pause_action, undefined);
  assert.equal(summary.alert, "none");
  assert.equal(pauses.length, 0);
});

test("open tracking off on the live campaign only: gate skipped too", async (t) => {
  const { server, pauses } = await fakeGateway({
    campaign: campaign({ open_tracking: false }),
    metrics: { ...METRICS },
  });
  t.after(() => server.close());
  const runDir = makeRun(t, spec(undefined));
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = JSON.parse(fs.readFileSync(path.join(runDir, "monitor-summary.json")));
  assert.deepEqual(summary.protection.triggered_gates, []);
  assert.equal(summary.metrics.open_count_unique, null);
  assert.equal(summary.open_tracking.source, "live campaign");
  assert.equal(pauses.length, 0);
});

test("live campaign tracking on overrides a spec that says off", async (t) => {
  const { server, pauses } = await fakeGateway({
    campaign: campaign({ open_tracking: true }),
    metrics: { ...METRICS },
  });
  t.after(() => server.close());
  const runDir = makeRun(t, spec(false));
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = JSON.parse(fs.readFileSync(path.join(runDir, "monitor-summary.json")));
  assert.deepEqual(summary.open_tracking, {
    enabled: true,
    source: "live campaign",
    reason: "live campaign open_tracking=true",
  });
  assert.deepEqual(summary.protection.triggered_gates, []);
  assert.equal(pauses.length, 0);
});

test("open tracking on: a zero open rate is a fact, not a pause gate", async (t) => {
  const { server, pauses } = await fakeGateway({
    campaign: campaign({ open_tracking: true }),
    metrics: { ...METRICS },
  });
  t.after(() => server.close());
  const runDir = makeRun(t, spec(true));
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = JSON.parse(fs.readFileSync(path.join(runDir, "monitor-summary.json")));
  assert.deepEqual(summary.protection.triggered_gates, []);
  assert.deepEqual(summary.protection.skipped_gates, [{ gate: "spam", reason: "not_configured" }]);
  assert.equal(summary.derived.open_rate, 0);
  assert.equal(summary.pause_suggested, false);
  assert.equal(summary.pause_action, undefined);
  assert.equal(summary.alert, "none");
  assert.equal(pauses.length, 0);
});

test("retired min_open_rate configuration cannot create a pause gate", async (t) => {
  const { server, pauses } = await fakeGateway({
    campaign: campaign(),
    metrics: { ...METRICS, open_count_unique: 6 }, // 20%
  });
  t.after(() => server.close());
  const s = spec(true);
  s.monitoring.thresholds = { max_bounce_rate: 2, min_open_rate: 90 };
  const runDir = makeRun(t, s);
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = JSON.parse(fs.readFileSync(path.join(runDir, "monitor-summary.json")));
  assert.equal(summary.protection.thresholds.min_open_rate, undefined);
  assert.equal(summary.derived.open_rate, 20);
  assert.deepEqual(summary.protection.triggered_gates, []);
  assert.equal(pauses.length, 0);
});

test("unspecified tracking follows the launch default off", async (t) => {
  const { server, pauses } = await fakeGateway({ campaign: campaign(), metrics: { ...METRICS } });
  t.after(() => server.close());
  const runDir = makeRun(t, spec(undefined));
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = JSON.parse(fs.readFileSync(path.join(runDir, "monitor-summary.json")));
  assert.equal(summary.open_tracking.enabled, false);
  assert.equal(summary.open_tracking.source, "default");
  assert.equal(summary.derived.open_rate, null);
  assert.equal(summary.metrics.open_count_unique, null);
  assert.equal(pauses.length, 0);
});
