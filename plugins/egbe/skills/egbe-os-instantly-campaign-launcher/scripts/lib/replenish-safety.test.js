const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const store = require("./outreach-db");
const { makeRun, startServer, replenish } = require("./replenish-test-harness");

function configure(fixture, changes) {
  const file = path.join(fixture.runDir, "run-spec.json");
  const spec = JSON.parse(fs.readFileSync(file));
  Object.assign(spec.lead_replenishment, changes);
  fs.writeFileSync(file, JSON.stringify(spec));
}

for (const enabled of [false, undefined, "true"]) {
  test(`replenishment is disabled unless enabled is literally true (${enabled})`, async () => {
    const f = makeRun([{ email: "new@example.test" }]);
    configure(f, { enabled });
    let calls = 0;
    const server = await startServer(() => { calls++; return { data: {} }; });
    try {
      const result = await replenish(f.runDir, server.url, ["--force"]);
      assert.equal(result.code, 0, result.stderr);
      assert.match(result.stdout, /enabled is not true/);
      assert.equal(calls, 0);
    } finally { server.close(); f.cleanup(); }
  });
}

test("enabled replenishment requires all authored bounds, even with force", async () => {
  const f = makeRun([{ email: "new@example.test" }]);
  configure(f, { max_total_leads: undefined });
  let calls = 0;
  const server = await startServer(() => { calls++; return { data: {} }; });
  try {
    const result = await replenish(f.runDir, server.url, ["--force"]);
    assert.equal(result.code, 1);
    assert.match(result.stderr, /explicit valid bounds: max_total_leads/);
    assert.equal(calls, 0);
  } finally { server.close(); f.cleanup(); }
});

for (const limit of ["max_replenishments", "max_total_leads", "cooldown_minutes", "unknown_counts"]) {
  test(`force cannot bypass ${limit}`, async () => {
    const f = makeRun([{ email: "new@example.test" }]);
    if (limit === "max_replenishments") configure(f, { max_replenishments: 0 });
    if (limit === "max_total_leads") configure(f, { max_total_leads: 1 });
    if (limit === "cooldown_minutes") {
      configure(f, { cooldown_minutes: 60 });
      fs.writeFileSync(path.join(f.stateDir, "replenishment-history.json"), JSON.stringify([{ completed_at: new Date().toISOString() }]));
    }
    let posts = 0;
    const server = await startServer((endpoint) => {
      if (endpoint.endsWith("/campaigns/c")) return { data: { id: "c", lead_stats: limit === "unknown_counts" ? null : { total: 1 } } };
      if (endpoint.endsWith("/analytics")) return { data: { contacted_count: 1 } };
      if (endpoint.endsWith("/leads")) return { status: 404 };
      if (endpoint.endsWith("/leads/add")) { posts++; return { data: { leads_uploaded: 1 } }; }
    });
    try {
      const result = await replenish(f.runDir, server.url, ["--force"]);
      assert.equal(result.code, 0, result.stderr);
      assert.equal(JSON.parse(result.stdout).skipped, true);
      assert.equal(posts, 0);
      assert.deepEqual(JSON.parse(fs.readFileSync(path.join(f.stateDir, "carry-over-leads.json"))), [{ email: "new@example.test" }]);
    } finally { server.close(); f.cleanup(); }
  });
}

test("cross-run confirmed opt-out is excluded from carry-over before import", async () => {
  const f = makeRun([{ email: " OPTOUT@EXAMPLE.TEST " }, { email: "new@example.test" }]);
  store.upsertRun(f.dbPath, { run_key: "other-run", campaign_id: "other-campaign" });
  store.upsertLead(f.dbPath, { email: "optout@example.test" });
  store.confirmOptOut(f.dbPath, { run_key: "other-run", campaign_id: "other-campaign", email: "optout@example.test", message_id: "refusal" });
  let posts = 0;
  const server = await startServer((endpoint) => {
    if (endpoint.endsWith("/campaigns/c")) return { data: { id: "c", lead_stats: { total: 1 } } };
    if (endpoint.endsWith("/analytics")) return { data: { contacted_count: 1 } };
    if (endpoint.endsWith("/leads")) return { data: { items: [] } };
    if (endpoint.endsWith("/leads/add")) { posts++; return { data: { leads_uploaded: 1 } }; }
  });
  try {
    const result = await replenish(f.runDir, server.url);
    assert.equal(result.code, 0, result.stderr);
    assert.equal(posts, 1);
    assert.equal(JSON.parse(result.stdout).leads_excluded_opt_out, 1);
    assert.deepEqual(store.queryAll(f.dbPath, "SELECT email FROM run_leads WHERE run_key = 'test-run'").map(row => row.email), ["new@example.test"]);
  } finally { server.close(); f.cleanup(); }
});

test("missing DB with known send history blocks before initialization and provider reads", async () => {
  const f = makeRun([{ email: "new@example.test" }]);
  fs.writeFileSync(path.join(f.runDir, "launch-summary.json"), JSON.stringify({ run_key: "test-run", campaign_id: "c", launch_status: "launched" }));
  fs.renameSync(f.dbPath, `${f.dbPath}.recovery`);
  let calls = 0;
  const server = await startServer(() => { calls++; return { data: {} }; });
  try {
    const result = await replenish(f.runDir, server.url, ["--force"]);
    assert.equal(result.code, 1);
    assert.match(result.stderr, /missing.*prior sending/);
    assert.equal(fs.existsSync(f.dbPath), false);
    assert.equal(calls, 0);
  } finally { server.close(); f.cleanup(); }
});

test("fresh membership count cannot exceed authored cap despite stale lead_stats", async () => {
  const f = makeRun([{ email: "new@example.test" }]);
  configure(f, { max_total_leads: 2 });
  let posts = 0;
  const server = await startServer((endpoint) => {
    if (endpoint.endsWith("/campaigns/c")) return { data: { id: "c", lead_stats: { total: 1 } } };
    if (endpoint.endsWith("/analytics")) return { data: { contacted_count: 1 } };
    if (endpoint.endsWith("/leads")) return { data: { items: [{ id: "a", campaign: "c", email: "a@example.test" }, { id: "b", campaign: "c", email: "b@example.test" }] } };
    if (endpoint.endsWith("/leads/add")) { posts++; return { data: { leads_uploaded: 1 } }; }
  });
  try {
    const result = await replenish(f.runDir, server.url, ["--force"]);
    assert.equal(result.code, 0, result.stderr);
    assert.match(result.stdout, /Fresh lead count would exceed/);
    assert.equal(posts, 0);
    assert.equal(fs.existsSync(path.join(f.stateDir, "imported-leads.json")), false);
    assert.equal(JSON.parse(fs.readFileSync(path.join(f.stateDir, "carry-over-leads.json"))).length, 1);
  } finally { server.close(); f.cleanup(); }
});

for (const carryOver of [[], [{ email: "new@example.test" }]]) {
  test(`unfinished Apollo checkpoint ${carryOver.length ? "allows existing carry-over" : "blocks another paid query"}`, async () => {
    const f = makeRun(carryOver);
    configure(f, { apollo_search: { person_titles: ["Founder"] } });
    const checkpointPath = path.join(f.stateDir, "replenish-temp", "leads-old.json");
    fs.mkdirSync(path.dirname(checkpointPath), { recursive: true });
    const checkpoint = { leads: [], meta: { complete: false, stop_reason: "uncertain_enrichment",
      not_enriched: 1, not_enriched_people: [{ id: "person-unresolved" }] } };
    fs.writeFileSync(checkpointPath, JSON.stringify(checkpoint));
    let posts = 0;
    const server = await startServer((endpoint) => {
      if (endpoint.endsWith("/campaigns/c")) return { data: { id: "c", lead_stats: { total: 1 } } };
      if (endpoint.endsWith("/analytics")) return { data: { contacted_count: 1 } };
      if (endpoint.endsWith("/leads")) return { data: { items: [] } };
      if (endpoint.endsWith("/leads/add")) { posts++; return { data: { leads_uploaded: 1 } }; }
      throw new Error(`Unexpected provider request: ${endpoint}`);
    });
    try {
      const result = await replenish(f.runDir, server.url);
      assert.equal(result.code, carryOver.length ? 0 : 1, result.stderr);
      const summary = JSON.parse(result.stdout);
      if (!carryOver.length) {
        assert.equal(summary.source_meta.complete, false);
        assert.equal(summary.source_meta.stop_reason, "uncertain_enrichment");
        assert.equal(summary.source_file, "state/replenish-temp/leads-old.json");
      }
      assert.equal(posts, carryOver.length);
      assert.deepEqual(JSON.parse(fs.readFileSync(checkpointPath)), checkpoint);
    } finally { server.close(); f.cleanup(); }
  });
}
