#!/usr/bin/env node
// A tripped protection gate stays tripped until someone acts. The monitor must not
// pause an already-paused campaign, and must mark the alert "new" only the
// first time (or when it worsens materially / another gate trips) so the
// hourly cron agent does not re-alert the owner (Fina incident 2026-10-19:
// 7 identical Slack alerts).
//
// Run: node scripts/lib/monitor-repeat-alert.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const http = require("node:http");
const { spawn } = require("node:child_process");

const MONITOR = path.resolve(__dirname, "..", "monitor-campaign.js");

// Fake OS outreach gateway serving the given campaign and analytics objects
// (mutable between runs). A pause call flips the campaign to status 2.
function fakeGateway({ campaign, metrics, pauseStatus = 200, pauseChangesStatus = true, overviewMetrics = null, dropAnalytics = false, emails = null, leadPages = null }) {
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
      if (pauseStatus !== 200) {
        // retry-after keeps the client's 429 back-off fast in tests.
        res.writeHead(pauseStatus, { "content-type": "application/json", "retry-after": "0.01" });
        return res.end(JSON.stringify({ error: "pause refused" }));
      }
      if (pauseChangesStatus) campaign.status = 2;
      return send(200, { id: "camp-1", status: 2 });
    }
    if (url.pathname === base) return send(200, campaign);
    if (url.pathname === `${base}/analytics`) {
      if (dropAnalytics) return req.destroy();
      return send(200, metrics);
    }
    if (url.pathname === `${base}/sending-status`) return send(200, {});
    if (url.pathname.endsWith("/analytics/overview") && overviewMetrics) return send(200, overviewMetrics);
    if (url.pathname === "/outreach/instantly/emails" && emails)
      return send(200, { items: emails[url.searchParams.get("email_type")] || [] });
    if (url.pathname === "/outreach/instantly/leads" && leadPages)
      return send(200, typeof leadPages === "function" ? leadPages(url) : { items: leadPages });
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

const SPEC = {
  run_key: "fina",
  campaign: { open_tracking: false },
  monitoring: { autopause_on_risk: true, thresholds: { max_bounce_rate: 2, max_spam_complaint_rate: 0.05 } },
  lead_replenishment: { enabled: false },
};
const BASE_METRICS = {
  contacted_count: 30,
  emails_sent_count: 30,
  open_count_unique: 0,
  reply_count_unique: 0,
  bounced_count: 3, // 10% > configured 2%
  spam_complaint_count: 0,
};

// Run status the monitor saved to outreach.db (runDir/../../outreach.db).
function dbStatus(runDir) {
  const { DatabaseSync } = require("node:sqlite");
  const db = new DatabaseSync(path.resolve(runDir, "..", "outreach.db"));
  try {
    return db.prepare("SELECT status FROM outreach_runs WHERE run_key = ?").get("fina")?.status;
  } finally {
    db.close();
  }
}

function summaryOf(runDir) {
  return JSON.parse(fs.readFileSync(path.join(runDir, "monitor-summary.json")));
}

test("tripped gate: first run pauses and alerts new, later runs repeat without pausing", async (t) => {
  const camp = { id: "camp-1", status: 1, email_list: ["a@x.test"], lead_stats: { total: 100 } };
  const metrics = { ...BASE_METRICS };
  const { server, pauses } = await fakeGateway({ campaign: camp, metrics });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const port = server.address().port;

  let result = await runMonitor(runDir, port);
  assert.equal(result.status, 0, result.stderr);
  let summary = summaryOf(runDir);
  assert.equal(summary.alert, "new");
  assert.deepEqual(summary.alerts.map((a) => [a.key, a.alert]), [["protection:bounce", "new"]]);
  assert.equal(summary.protection.triggered_gates[0].alert, "new");
  assert.equal(summary.pause_action.status, 200);
  assert.equal(pauses.length, 1);
  assert.equal(dbStatus(runDir), "paused");

  // Campaign is now paused (status 2): no second pause call, alert repeats.
  for (let i = 0; i < 3; i++) {
    result = await runMonitor(runDir, port);
    assert.equal(result.status, 0, result.stderr);
    summary = summaryOf(runDir);
    assert.equal(summary.campaign_status, 2);
    assert.equal(summary.alert, "repeat");
    assert.equal(summary.alerts[0].alert, "repeat");
    assert.equal(summary.pause_action, undefined);
    assert.match(summary.pause_skipped.reason, /already paused/);
    assert.ok(summary.pause_skipped.paused_by_monitor_at);
  }
  assert.equal(pauses.length, 1);

  // Bounce rate worsens materially (10% -> 20%): a fresh alert, still no pause.
  metrics.bounced_count = 6;
  result = await runMonitor(runDir, port);
  summary = summaryOf(runDir);
  assert.equal(summary.alert, "new");
  assert.equal(summary.alerts[0].alert, "new");
  assert.equal(pauses.length, 1);

  // A different gate trips: only that one is new.
  metrics.spam_complaint_count = 1;
  result = await runMonitor(runDir, port);
  summary = summaryOf(runDir);
  assert.deepEqual(
    summary.alerts.map((a) => [a.key, a.alert]),
    [["protection:bounce", "repeat"], ["protection:spam", "new"]],
  );
  assert.equal(summary.alert, "new");
  assert.equal(pauses.length, 1);
});

function activeCampaign() {
  return { id: "camp-1", status: 1, email_list: ["a@x.test"], lead_stats: { total: 1000 } };
}

test("operator resume after a monitor pause is an acknowledgement: no re-pause, no new alert", async (t) => {
  const camp = activeCampaign();
  const { server, pauses } = await fakeGateway({ campaign: camp, metrics: { ...BASE_METRICS } });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const port = server.address().port;
  await runMonitor(runDir, port); // trips bounce, pauses
  assert.equal(pauses.length, 1);
  camp.status = 1; // resumed by hand, bounce still 10%
  for (let i = 0; i < 3; i++) {
    const result = await runMonitor(runDir, port);
    assert.equal(result.status, 0, result.stderr);
    const summary = summaryOf(runDir);
    assert.equal(summary.alert, "repeat");
    assert.equal(summary.alerts[0].alert, "repeat");
    assert.ok(summary.alerts[0].acknowledged_at);
    assert.equal(summary.pause_action, undefined);
    assert.deepEqual(summary.pause_suppressed.gates, ["bounce"]);
    assert.equal(dbStatus(runDir), "launched");
  }
  assert.equal(pauses.length, 1);
  const state = JSON.parse(fs.readFileSync(path.join(runDir, "state", "monitor-alerts.json")));
  assert.ok(state.gates["protection:bounce"].acknowledged_at);
  assert.equal(state.gates["protection:bounce"].paused_value, 10);
});

test("after a resume, a 50% worse value than at the pause pauses and alerts again", async (t) => {
  const camp = activeCampaign();
  const metrics = { ...BASE_METRICS };
  const { server, pauses } = await fakeGateway({ campaign: camp, metrics });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const port = server.address().port;
  await runMonitor(runDir, port);
  camp.status = 1;
  metrics.bounced_count = 4; // 13.3%: worse, but < 1.5x the 10% at the pause
  await runMonitor(runDir, port);
  assert.equal(summaryOf(runDir).alert, "repeat");
  assert.equal(pauses.length, 1);
  metrics.bounced_count = 5; // 16.7% >= 15%
  await runMonitor(runDir, port);
  const summary = summaryOf(runDir);
  assert.equal(summary.alerts[0].alert, "new");
  assert.equal(summary.alerts[0].acknowledged_at, undefined);
  assert.equal(summary.pause_action.status, 200);
  assert.equal(summary.alert, "new");
  assert.equal(pauses.length, 2);
});

test("after a resume, a different gate tripping pauses and alerts new", async (t) => {
  const camp = activeCampaign();
  const metrics = { ...BASE_METRICS };
  const { server, pauses } = await fakeGateway({ campaign: camp, metrics });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const port = server.address().port;
  await runMonitor(runDir, port);
  camp.status = 1;
  metrics.spam_complaint_count = 1;
  await runMonitor(runDir, port);
  const summary = summaryOf(runDir);
  assert.deepEqual(
    summary.alerts.map((a) => [a.gate, a.alert]),
    [["bounce", "repeat"], ["spam", "new"]],
  );
  assert.equal(summary.pause_action.status, 200);
  assert.equal(pauses.length, 2);
});

test("after a resume, any new spam complaint re-pauses even if the rate fell", async (t) => {
  const camp = activeCampaign();
  const metrics = { ...BASE_METRICS, bounced_count: 0, spam_complaint_count: 1 };
  const { server, pauses } = await fakeGateway({ campaign: camp, metrics });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const port = server.address().port;
  await runMonitor(runDir, port); // spam 1/30 = 3.3%: pause
  assert.equal(pauses.length, 1);
  camp.status = 1;
  metrics.contacted_count = 200; // rate 0.5%: still over 0.05%, same count
  metrics.emails_sent_count = 200;
  await runMonitor(runDir, port);
  assert.equal(summaryOf(runDir).alert, "repeat");
  assert.equal(pauses.length, 1);
  metrics.spam_complaint_count = 2; // 1% rate: lower than at the pause, but a new complaint
  await runMonitor(runDir, port);
  const summary = summaryOf(runDir);
  assert.equal(summary.alerts[0].alert, "new");
  assert.equal(summary.pause_action.status, 200);
  assert.equal(pauses.length, 2);
});

test("a pause that keeps failing (429) is loud and new on every tick", async (t) => {
  const camp = activeCampaign();
  const { server, pauses } = await fakeGateway({ campaign: camp, metrics: { ...BASE_METRICS }, pauseStatus: 429 });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const port = server.address().port;
  for (let i = 0; i < 2; i++) {
    const result = await runMonitor(runDir, port);
    assert.equal(result.status, 0, result.stderr);
    const summary = summaryOf(runDir);
    assert.equal(summary.pause_failed, true);
    assert.equal(summary.pause_http_status, 429);
    assert.equal(summary.alert, "new");
    assert.equal(summary.alerts[0].alert, "new");
    assert.ok(summary.recommendations.some((r) => /Auto-pause FAILED \(HTTP 429\)/.test(r)));
    assert.equal(dbStatus(runDir), "launched");
  }
  assert.ok(pauses.length >= 2);
});

test("cleared gate is forgotten: a later trip is new again", async (t) => {
  const camp = { id: "camp-1", status: 2, email_list: ["a@x.test"], lead_stats: { total: 100 } };
  const metrics = { ...BASE_METRICS };
  const { server, pauses } = await fakeGateway({ campaign: camp, metrics });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const port = server.address().port;
  await runMonitor(runDir, port); // already paused by operator: alert new, no pause
  assert.equal(summaryOf(runDir).alert, "new");
  assert.equal(pauses.length, 0);
  metrics.contacted_count = 300; // 1% bounce: gate clears
  metrics.emails_sent_count = 300;
  camp.lead_stats.total = 400;
  await runMonitor(runDir, port);
  assert.equal(summaryOf(runDir).alert, "none");
  metrics.bounced_count = 30; // 10% again
  await runMonitor(runDir, port);
  assert.equal(summaryOf(runDir).alerts[0].alert, "new");
  assert.equal(pauses.length, 0);
});

test("failed pause call is reported and the run is not recorded as paused", async (t) => {
  const camp = { id: "camp-1", status: 1, email_list: ["a@x.test"], lead_stats: { total: 100 } };
  const { server, pauses } = await fakeGateway({ campaign: camp, metrics: { ...BASE_METRICS }, pauseStatus: 403 });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.pause_action.status, 403);
  assert.equal(summary.alert, "new");
  assert.equal(pauses.length, 1);
  assert.equal(dbStatus(runDir), "launched");
  const state = JSON.parse(fs.readFileSync(path.join(runDir, "state", "monitor-alerts.json")));
  assert.equal(state.paused_by_monitor_at, null);
});

test("campaign paused in Instantly is recorded as paused without a triggered gate", async (t) => {
  const camp = { id: "camp-1", status: 2, email_list: ["a@x.test"], lead_stats: { total: 100 } };
  const { server, pauses } = await fakeGateway({
    campaign: camp,
    metrics: { ...BASE_METRICS, contacted_count: 5, emails_sent_count: 5, bounced_count: 0 },
  });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.protection.active, true);
  assert.equal(summary.alert, "none");
  assert.equal(pauses.length, 0);
  assert.equal(dbStatus(runDir), "paused");
});

for (const [label, liveStatus] of [["null (status unreadable)", null]]) {
  test(`after a monitor pause, live status ${label} is not an acknowledgement`, async (t) => {
    const camp = activeCampaign();
    const { server, pauses } = await fakeGateway({ campaign: camp, metrics: { ...BASE_METRICS } });
    t.after(() => server.close());
    const runDir = makeRun(t, SPEC);
    const port = server.address().port;
    await runMonitor(runDir, port); // trips bounce, pauses
    assert.equal(pauses.length, 1);
    camp.status = liveStatus;
    const result = await runMonitor(runDir, port);
    assert.equal(result.status, 0, result.stderr);
    const summary = summaryOf(runDir);
    assert.equal(summary.campaign_status, liveStatus);
    assert.equal(summary.alerts[0].acknowledged_at, undefined);
    assert.equal(summary.pause_suppressed, undefined);
    assert.equal(summary.pause_skipped, undefined);
    assert.equal(summary.pause_action.status, 200);
    assert.equal(summary.alert, "new");
    assert.equal(pauses.length, 2);
    const state = JSON.parse(fs.readFileSync(path.join(runDir, "state", "monitor-alerts.json")));
    assert.equal(state.gates["protection:bounce"].acknowledged_at, null);
  });
}

for (const [label, liveStatus] of [["completed", 3], ["draft", 0]]) {
  test(`campaign ${label} (status ${liveStatus}) with a tripped bounce gate: no pause call, no new alert`, async (t) => {
    const camp = { ...activeCampaign(), status: liveStatus };
    const { server, pauses } = await fakeGateway({ campaign: camp, metrics: { ...BASE_METRICS }, pauseStatus: 400 });
    t.after(() => server.close());
    const runDir = makeRun(t, SPEC);
    const port = server.address().port;
    for (let i = 0; i < 2; i++) {
      const result = await runMonitor(runDir, port);
      assert.equal(result.status, 0, result.stderr);
      const summary = summaryOf(runDir);
      assert.equal(summary.campaign_status, liveStatus);
      assert.deepEqual(summary.protection.triggered_gates.map((g) => [g.gate, g.alert]), [["bounce", "repeat"]]);
      assert.equal(summary.alerts[0].alert, "repeat");
      assert.match(summary.alerts[0].not_news_reason, new RegExp(`${label} in Instantly; nothing is sending`));
      assert.equal(summary.alert, "repeat");
      assert.equal(summary.pause_action, undefined);
      assert.equal(summary.pause_failed, undefined);
      assert.equal(summary.pause_skipped.reason, `campaign is ${label} in Instantly; nothing is sending`);
    }
    assert.equal(pauses.length, 0);
    const history = JSON.parse(fs.readFileSync(path.join(runDir, "state", "analytics-history.json")));
    assert.equal(history.length, 2);
    assert.equal(history[1].derived.bounce_rate, 10);
  });
}

test("completed after a monitor pause: no further pause attempts or alerts", async (t) => {
  const camp = activeCampaign();
  const { server, pauses } = await fakeGateway({ campaign: camp, metrics: { ...BASE_METRICS } });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const port = server.address().port;
  await runMonitor(runDir, port); // pauses
  camp.status = 3;
  const result = await runMonitor(runDir, port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.alert, "repeat");
  assert.equal(summary.pause_action, undefined);
  assert.equal(pauses.length, 1);
});

test("gate tripped while draft is reported once the campaign starts sending", async (t) => {
  const camp = { ...activeCampaign(), status: 0 };
  const { server, pauses } = await fakeGateway({ campaign: camp, metrics: { ...BASE_METRICS } });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const port = server.address().port;
  await runMonitor(runDir, port);
  assert.equal(summaryOf(runDir).alert, "repeat");
  camp.status = 1;
  await runMonitor(runDir, port);
  const summary = summaryOf(runDir);
  assert.equal(summary.alerts[0].alert, "new");
  assert.equal(summary.pause_action.status, 200);
  assert.equal(pauses.length, 1);
});

test("throughput anomaly on a completed campaign is suppressed", async (t) => {
  const camp = { ...activeCampaign(), status: 3 };
  const metrics = { ...BASE_METRICS, bounced_count: 0 };
  const { server } = await fakeGateway({ campaign: camp, metrics });
  t.after(() => server.close());
  const runDir = makeRun(t, { ...SPEC, campaign: { ...SPEC.campaign, daily_limit: 50 },
    monitoring: { ...SPEC.monitoring, min_daily_capacity_pct: 30 } });
  const { initDb, upsertRun } = require("./outreach-db");
  upsertRun(initDb(runDir), { run_key: "fina", campaign_id: "camp-1", status: "launched" });
  // A snapshot 24h ago with the same send count: zero sends since.
  fs.writeFileSync(
    path.join(runDir, "state", "analytics-history.json"),
    JSON.stringify([{ generated_at: new Date(Date.now() - 24 * 3600e3).toISOString(), metrics: { emails_sent_count: 30 } }]),
  );
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.throughput_health.anomaly, true);
  assert.equal(summary.throughput_health.alert, "suppressed");
  assert.match(summary.throughput_health.alert_suppressed_reason, /completed/);
  assert.deepEqual(summary.alerts, []);
  assert.equal(summary.alert, "none");
});

test("status 4 (running subsequences) is still sending: tripped gate pauses and alerts new", async (t) => {
  const camp = { ...activeCampaign(), status: 4 };
  const { server, pauses } = await fakeGateway({ campaign: camp, metrics: { ...BASE_METRICS } });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.campaign_status, 4);
  assert.equal(summary.alerts[0].alert, "new");
  assert.equal(summary.alerts[0].not_news_reason, undefined);
  assert.equal(summary.alert, "new");
  assert.equal(summary.pause_action.status, 200);
  assert.equal(summary.pause_skipped, undefined);
  assert.equal(pauses.length, 1);
});

test("protection applies at small volume without a minimum judgment gate", async (t) => {
  const { server, pauses } = await fakeGateway({ campaign: activeCampaign(),
    metrics: { ...BASE_METRICS, contacted_count: 2, emails_sent_count: 2, bounced_count: 1 } });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.derived.bounce_rate, 50);
  assert.equal(summary.pause_readback.campaign_status, 2);
  assert.equal(pauses.length, 1);
});

test("missing required metrics remain null and pause after read fallbacks", async (t) => {
  const { server, pauses } = await fakeGateway({ campaign: activeCampaign(), metrics: {} });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.derived.bounce_rate, null);
  assert.equal(summary.derived.reply_rate, null);
  assert.equal(summary.protection.contacted, null);
  assert.deepEqual(summary.protection.triggered_gates.map(g => g.gate), ["bounce_unavailable", "spam_unavailable"]);
  assert.equal(pauses.length, 1);
});

test("usable campaign-filtered overview recovers missing primary signal before pause", async (t) => {
  const { server, pauses } = await fakeGateway({ campaign: activeCampaign(), metrics: {},
    overviewMetrics: { ...BASE_METRICS, bounced_count: 0 } });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.metrics._source, "campaign-filtered-overview");
  assert.equal(summary.derived.bounce_rate, 0);
  assert.equal(pauses.length, 0);
});

test("HTTP 200 pause without paused readback is not confirmed or recorded", async (t) => {
  const { server, pauses } = await fakeGateway({ campaign: activeCampaign(), metrics: { ...BASE_METRICS },
    pauseChangesStatus: false });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.pause_action.status, 200);
  assert.equal(summary.pause_readback.campaign_status, 1);
  assert.equal(summary.pause_failed, true);
  assert.equal(summary.alert, "new");
  assert.equal(dbStatus(runDir), "launched");
  assert.equal(pauses.length, 1);
});

test("throughput and replenishment are not enabled by absent configuration", async (t) => {
  const { server, pauses } = await fakeGateway({ campaign: activeCampaign(),
    metrics: { ...BASE_METRICS, bounced_count: 0, contacted_count: 1000, emails_sent_count: 1000 } });
  t.after(() => server.close());
  const runDir = makeRun(t, { ...SPEC, lead_replenishment: undefined });
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.throughput_health.measurable, false);
  assert.equal(summary.throughput_health.skipped_reason, "not_configured");
  assert.equal(summary.throughput_health.expected_daily_sends, null);
  assert.equal(summary.lead_utilization.needs_replenishment, false);
  assert.equal(summary.lead_utilization.threshold_pct, null);
  assert.equal(pauses.length, 0);
  assert.ok(Date.parse(summary.metrics_observed_at) <= Date.parse(summary.generated_at));
});

test("legacy pause acknowledgement continues without retaining the open-rate policy", async (t) => {
  const { server, pauses } = await fakeGateway({ campaign: activeCampaign(), metrics: { ...BASE_METRICS } });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const at = new Date(Date.now() - 1000).toISOString();
  fs.writeFileSync(path.join(runDir, "state", "monitor-alerts.json"), JSON.stringify({
    gates: { "c1:bounce": { paused_at: at, paused_value: 10, alerted_at: at, alerted_value: 10 },
      "c1:open_rate": { paused_at: at, paused_value: 0 } },
    paused_by_monitor_at: at,
  }));
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.alert, "repeat");
  assert.deepEqual(summary.pause_suppressed.gates, ["bounce"]);
  assert.equal(pauses.length, 0);
  const state = JSON.parse(fs.readFileSync(path.join(runDir, "state", "monitor-alerts.json")));
  assert.deepEqual(Object.keys(state.gates), ["protection:bounce"]);
});

test("transport failure can recover through a read fallback", async (t) => {
  const { server, pauses } = await fakeGateway({ campaign: activeCampaign(), metrics: {}, dropAnalytics: true,
    overviewMetrics: { ...BASE_METRICS, bounced_count: 0 } });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(summaryOf(runDir).metrics._source, "campaign-filtered-overview");
  assert.equal(pauses.length, 0);
});

test("absent protection configuration does not invent a threshold", async (t) => {
  const { server, pauses } = await fakeGateway({ campaign: activeCampaign(), metrics: { ...BASE_METRICS } });
  t.after(() => server.close());
  const runDir = makeRun(t, { ...SPEC, monitoring: {} });
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.protection.active, false);
  assert.equal(summary.protection.thresholds.max_bounce_rate, null);
  assert.deepEqual(summary.protection.triggered_gates.map(g => g.gate), ["configuration"]);
  assert.equal(pauses.length, 1);
});

test("monitor cannot replace missing sending history with a clean DB", async (t) => {
  const { server, pauses } = await fakeGateway({ campaign: activeCampaign(),
    metrics: { ...BASE_METRICS, bounced_count: 0 } });
  t.after(() => server.close());
  const runDir = makeRun(t, SPEC);
  fs.writeFileSync(path.join(runDir, "launch-summary.json"), JSON.stringify({
    run_key: "fina", campaign_id: "camp-1", launch_status: "launched",
  }));
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  const summary = summaryOf(runDir);
  assert.equal(summary.outreach_history_available, false);
  assert.ok(summary.protection.triggered_gates.some(g => g.gate === "history_unavailable"));
  assert.equal(fs.existsSync(path.resolve(runDir, "..", "outreach.db")), false);
  assert.equal(pauses.length, 1);
  assert.throws(() => require("./confirmed-opt-outs").readOptOutHistory(runDir), /missing/);
});

function campaignMetrics(overrides = {}) {
  return { campaign_id: "camp-1", leads_count: 126, contacted_count: 126,
    new_leads_contacted_count: 126, emails_sent_count: 357,
    bounced_count: 0, unsubscribed_count: 0, reply_count_unique: 0, ...overrides };
}
const EMAIL_SAMPLE = { sent: Array.from({ length: 100 }, (_, i) => ({
  campaign_id: "camp-1", to_address_email_list: `p${i}@example.test`,
})), received: [] };

function contactedMembers(total) {
  return Array.from({ length: total }, (_, i) => ({ id: `l${i}`, email: `p${i}@example.test`,
    campaign: "camp-1", status: 1, timestamp_last_contact: "2026-11-02T12:00:00Z" }));
}

async function monitorFixture(t, options, spec = SPEC) {
  const { server, pauses } = await fakeGateway(options);
  t.after(() => server.close());
  const runDir = makeRun(t, spec);
  const result = await runMonitor(runDir, server.address().port);
  assert.equal(result.status, 0, result.stderr);
  return { summary: summaryOf(runDir), pauses, runDir };
}

test("missing required spam preserves independently readable zero bounces", async t => {
  const metrics = campaignMetrics();
  const { summary, pauses } = await monitorFixture(t, { campaign: activeCampaign(), metrics,
    overviewMetrics: metrics, emails: EMAIL_SAMPLE });
  assert.equal(summary.metrics.bounced_count, 0);
  assert.equal(summary.derived.bounce_rate, 0);
  assert.equal(summary.metrics._partial, undefined);
  assert.deepEqual(summary.protection.triggered_gates.map(g => g.gate), ["spam_unavailable"]);
  assert.equal(pauses.length, 1); // Required complaint protection is not disabled.
});

test("optional absent spam does not pause an otherwise measurable campaign", async t => {
  const spec = { ...SPEC, monitoring: { thresholds: { max_bounce_rate: 2 } } };
  const { summary, pauses } = await monitorFixture(t,
    { campaign: activeCampaign(), metrics: campaignMetrics(), emails: EMAIL_SAMPLE }, spec);
  assert.equal(summary.derived.bounce_rate, 0);
  assert.deepEqual(summary.protection.triggered_gates, []);
  assert.equal(pauses.length, 0);
});

for (const contacted of [231, 408]) {
  test(`inconsistent contacted=${contacted} recovers the corroborated 126 unique contacts`, async t => {
    const members = contactedMembers(126);
    const metrics = campaignMetrics({ contacted_count: contacted, emails_sent_count: contacted === 408 ? 408 : 357 });
    const { summary } = await monitorFixture(t, { campaign: { ...activeCampaign(), lead_stats: null }, metrics,
      overviewMetrics: metrics, emails: EMAIL_SAMPLE,
      leadPages: url => ({ items: url.searchParams.has("starting_after") ? members.slice(100) : members.slice(0, 100) }) });
    assert.equal(summary.metrics.contacted_count, 126);
    assert.equal(summary.metrics._raw_contacted_count, contacted);
    assert.equal(summary.metrics._field_sources.contacted_count, "campaign-leads");
    assert.equal(summary.metrics.bounced_count, 0);
    assert.equal(summary.derived.bounce_rate, 0);
    assert.deepEqual(summary.protection.triggered_gates.map(g => g.gate), ["spam_unavailable"]);
  });
}

for (const fixture of [
  { name: "historical contacts exceed current membership", members: contactedMembers(2), newContacts: 3 },
  { name: "activity is unknown", members: [{ id: "l1", email: "a@example.test", campaign: "camp-1", status: 1 }], newContacts: 0 },
  { name: "foreign campaign membership", members: [{ ...contactedMembers(1)[0], campaign: "foreign" }], newContacts: 1 },
]) {
  test(`an unverified denominator stays unavailable: ${fixture.name}`, async t => {
    const metrics = campaignMetrics({ leads_count: fixture.members.length, contacted_count: 408,
      new_leads_contacted_count: fixture.newContacts });
    const { summary } = await monitorFixture(t, { campaign: { ...activeCampaign(), lead_stats: null }, metrics,
      overviewMetrics: metrics, leadPages: fixture.members });
    assert.equal(summary.metrics.contacted_count, null);
    assert.equal(summary.metrics.bounced_count, 0);
    assert.equal(summary.derived.bounce_rate, null);
    assert.ok(summary.protection.triggered_gates.some(g => g.gate === "bounce_unavailable"));
    assert.equal(summary.protection.skipped_gates.some(g => g.reason === "no_recipients_yet"), false);
  });
}

test("foreign analytics cannot supply a healthy zero or denominator", async t => {
  const { summary, pauses } = await monitorFixture(t, { campaign: activeCampaign(),
    metrics: campaignMetrics({ campaign_id: "foreign", spam_complaint_count: 0 }) });
  assert.equal(summary.metrics.bounced_count ?? null, null);
  assert.equal(summary.derived.bounce_rate, null);
  assert.ok(summary.protection.triggered_gates.some(g => g.gate === "bounce_unavailable"));
  assert.equal(pauses.length, 1);
});

test("complete analytics fields merge without borrowing a sampled reply rate", async t => {
  const spec = { ...SPEC, monitoring: { thresholds: { max_bounce_rate: 3 } } };
  const metrics = campaignMetrics({ contacted_count: 100, new_leads_contacted_count: 100,
    reply_count_unique: null, bounced_count: 2 });
  const { summary, pauses } = await monitorFixture(t, { campaign: activeCampaign(), metrics,
    emails: { ...EMAIL_SAMPLE, received: [{ campaign_id: "camp-1", from_address_email: "p1@example.test" }] } }, spec);
  assert.equal(summary.metrics.bounced_count, 2);
  assert.equal(summary.derived.bounce_rate, 2);
  assert.equal(summary.metrics.reply_count_unique, null);
  assert.equal(summary.derived.reply_rate, null);
  assert.equal(pauses.length, 0);
});

test("overview fills one missing field without replacing another complete field", async t => {
  const primary = campaignMetrics({ reply_count_unique: null });
  const overview = campaignMetrics({ bounced_count: null, reply_count_unique: 2 });
  const { summary } = await monitorFixture(t, { campaign: activeCampaign(), metrics: primary,
    overviewMetrics: overview, emails: EMAIL_SAMPLE });
  assert.equal(summary.metrics.bounced_count, 0);
  assert.equal(summary.metrics.reply_count_unique, 2);
  assert.equal(summary.metrics._field_sources.bounced_count, "campaign-analytics");
  assert.equal(summary.metrics._field_sources.reply_count_unique, "campaign-filtered-overview");
  assert.deepEqual(summary.protection.triggered_gates.map(g => g.gate), ["spam_unavailable"]);
});

test("a cyclic partial membership read cannot clear a required denominator", async t => {
  const metrics = campaignMetrics({ contacted_count: 408 });
  const { summary } = await monitorFixture(t, { campaign: { ...activeCampaign(), lead_stats: null }, metrics,
    overviewMetrics: metrics, leadPages: contactedMembers(100) });
  assert.equal(summary.metrics.contacted_count, null);
  assert.equal(summary.metrics.bounced_count, 0);
  assert.ok(summary.protection.triggered_gates.some(g => g.gate === "bounce_unavailable"));
});

test("contradictory positive sends cannot be skipped as zero recipients", async t => {
  const metrics = campaignMetrics({ contacted_count: 0, new_leads_contacted_count: 0, emails_sent_count: 357 });
  const { summary } = await monitorFixture(t, { campaign: { ...activeCampaign(), lead_stats: null }, metrics,
    overviewMetrics: metrics, leadPages: [{ id: "unknown", email: "a@example.test", status: 1 }] });
  assert.equal(summary.metrics.contacted_count, null);
  assert.ok(summary.protection.triggered_gates.some(g => g.gate === "bounce_unavailable"));
  assert.equal(summary.protection.skipped_gates.some(g => g.reason === "no_recipients_yet"), false);
});

test("foreign overview cannot fill an unavailable bounce signal", async t => {
  const { summary } = await monitorFixture(t, { campaign: activeCampaign(),
    metrics: campaignMetrics({ bounced_count: null }),
    overviewMetrics: campaignMetrics({ campaign_id: "foreign", spam_complaint_count: 0 }) });
  assert.equal(summary.metrics.bounced_count, null);
  assert.equal(summary.derived.bounce_rate, null);
  assert.ok(summary.protection.triggered_gates.some(g => g.gate === "bounce_unavailable"));
});

test("foreign email evidence is rejected by the partial fallback", async t => {
  const { summary } = await monitorFixture(t, { campaign: activeCampaign(), metrics: {},
    emails: { sent: [{ campaign_id: "foreign", to_address_email_list: "a@example.test" }] } });
  assert.equal(summary.metrics._source, "unavailable");
  assert.equal(summary.metrics.contacted_count ?? null, null);
  assert.ok(summary.protection.triggered_gates.some(g => g.gate === "bounce_unavailable"));
});

test("corroborated activity corrects an inflated counter within a larger lead list", async t => {
  const members = contactedMembers(126).concat(Array.from({ length: 74 }, (_, i) => ({
    id: `u${i}`, email: `u${i}@example.test`, campaign: "camp-1", status: 1, timestamp_last_contact: null,
  })));
  const metrics = campaignMetrics({ contacted_count: 180, leads_count: 200, emails_sent_count: 500 });
  const { summary } = await monitorFixture(t, { campaign: { ...activeCampaign(), lead_stats: { total: 200 } },
    metrics, overviewMetrics: metrics,
    leadPages: url => ({ items: !url.searchParams.has("starting_after") ? members.slice(0, 100)
      : url.searchParams.get("starting_after") === "l99" ? members.slice(100) : [] }) });
  assert.equal(summary.metrics.contacted_count, 126);
  assert.equal(summary.metrics._raw_contacted_count, 180);
  assert.equal(summary.derived.bounce_rate, 0);
  assert.deepEqual(summary.protection.triggered_gates.map(g => g.gate), ["spam_unavailable"]);
});
