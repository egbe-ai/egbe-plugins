// Replenishment applies the launcher's lead-name checks before every import
// into the live campaign: missing substitutions are rejected and retained,
// while cosmetic name warnings do not discard an otherwise usable contact.
//
// Run: node scripts/lib/replenish-name-check.test.js

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const http = require("node:http");
const { spawn } = require("node:child_process");
const { initDb, upsertRun } = require("./outreach-db");

function replenish(runDir, url) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.execPath,
      [
        path.join(__dirname, "../replenish-leads.js"),
        "--run-dir",
        runDir,
        "--force",
      ],
      {
        env: { ...process.env, OS_API_KEY: "test", OS_URL: url },
        stdio: ["ignore", "pipe", "pipe"],
      },
    );
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

async function withRun({ steps, carryOver }, fn) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "replenish-names-"));
  const runDir = path.join(root, "runs", "test");
  const stateDir = path.join(runDir, "state");
  fs.mkdirSync(stateDir, { recursive: true });
  const write = (name, value) =>
    fs.writeFileSync(path.join(runDir, name), JSON.stringify(value));
  write("manifest.json", {
    run_key: "test-run",
    campaign: { id: "c", name: "test-campaign" },
  });
  write("run-spec.json", {
    product: { name: "test" },
    segment: { name: "test" },
    offer: { headline: "test" },
    sequence: { steps },
    lead_replenishment: { enabled: true, batch_size: 10, max_total_leads: 100,
      max_replenishments: 3, utilization_threshold: 0.5, cooldown_minutes: 0 },
  });
  write("state/carry-over-leads.json", carryOver);
  const dbPath = initDb(runDir);
  upsertRun(dbPath, {
    run_key: "test-run",
    product_name: "test",
    segment_name: "test",
    offer_headline: "test",
    campaign_id: "c",
    status: "launched",
  });
  const posted = [];
  const srv = http.createServer((req, res) => {
    const endpoint = req.url.split("?")[0];
    let body = "";
    req.on("data", (c) => {
      body += c;
    });
    req.on("end", () => {
      let status = 200;
      let data;
      if (endpoint.endsWith("/campaigns/c"))
        data = { id: "c", lead_stats: { total: 1 } };
      else if (endpoint.endsWith("/analytics")) data = { contacted_count: 1 };
      else if (endpoint.endsWith("/leads/add") && req.method === "POST") {
        const leads = JSON.parse(body).payload.leads;
        posted.push(...leads);
        data = { leads_uploaded: leads.length };
      } else if (endpoint.endsWith("/leads")) data = { items: [] };
      else status = 400;
      res.writeHead(status, { "content-type": "application/json" });
      res.end(JSON.stringify({ data }));
    });
  });
  await new Promise((resolve) => srv.listen(0, "127.0.0.1", resolve));
  try {
    await fn({
      runDir,
      stateDir,
      posted,
      url: `http://127.0.0.1:${srv.address().port}`,
    });
  } finally {
    srv.close();
    fs.rmSync(root, { recursive: true, force: true });
  }
}

const LEADS = [
  { email: "ok@one.test", first_name: "Anna", company_name: "Acme Accounting" },
  { email: "ca@two.test", first_name: "CA", company_name: "Good Co" },
  {
    email: "caps@three.test",
    first_name: "Rahul",
    company_name: "AL MASAOOD ACCOUNTING LLC",
  },
  { email: "li@four.test", first_name: "Li", company_name: "Wu & Partners" },
  {
    email: "j@five.test",
    first_name: "J",
    first_name_confirmed: true,
    company_name: "Fine Ltd",
  },
];

test("replenishment rejects known title tokens but does not drop cosmetic name warnings", async () => {
  await withRun(
    {
      steps: [
        {
          subject: "hi",
          body: "Dear {{firstName}},\n\nA question about {{companyName}}.",
        },
      ],
      carryOver: LEADS,
    },
    async ({ stateDir, posted, runDir, url }) => {
      const result = await replenish(runDir, url);
      assert.equal(result.code, 0, result.stderr);
      assert.deepEqual(posted.map((l) => l.email).sort(), [
        "caps@three.test",
        "j@five.test",
        "li@four.test",
        "ok@one.test",
      ]);
      assert.ok(
        posted.every(
          (l) => !("first_name_confirmed" in (l.custom_variables || {})),
        ),
      );
      const rejected = JSON.parse(fs.readFileSync(path.join(stateDir, "rejected-leads.json")));
      assert.deepEqual(rejected.map(lead => lead.email), ["ca@two.test"]);
      const event = JSON.parse(result.stdout);
      assert.deepEqual(event.lead_name_warnings.map((r) => r.email).sort(), [
        "caps@three.test",
      ]);
      assert.equal(event.leads_rejected_names, 1);
      const history = JSON.parse(
        fs.readFileSync(path.join(stateDir, "replenishment-history.json")),
      );
      assert.equal(history[0].leads_rejected_names, 1);
    },
  );
});

test("first_name is not checked when the copy does not use {{firstName}}", async () => {
  await withRun(
    {
      steps: [
        { subject: "hi", body: "Hello,\n\nA question about {{companyName}}." },
      ],
      carryOver: LEADS,
    },
    async ({ stateDir, posted, runDir, url }) => {
      const result = await replenish(runDir, url);
      assert.equal(result.code, 0, result.stderr);
      assert.equal(
        posted.length,
        5,
        "cosmetic company warning does not skip the lead",
      );
      assert.deepEqual(
        JSON.parse(result.stdout).lead_name_warnings.map((r) => r.email),
        ["caps@three.test"],
      );
    },
  );
});

test("every sourced lead rejected: no import, clear reason and the count", async () => {
  await withRun(
    {
      steps: [{ subject: "hi", body: "Dear {{firstName}}," }],
      carryOver: [{ email: "missing@example.test", source_ref: "apollo-person-1", custom_variables: { research: "retained" } }],
    },
    async ({ stateDir, posted, runDir, url }) => {
      const result = await replenish(runDir, url);
      assert.equal(result.code, 0, result.stderr);
      assert.equal(posted.length, 0);
      const out = JSON.parse(result.stdout);
      assert.equal(out.skipped, true);
      assert.match(out.reason, /missing copy substitutions/);
      assert.equal(out.leads_rejected_names, 1);
      assert.deepEqual(
        JSON.parse(
          fs.readFileSync(path.join(stateDir, "carry-over-leads.json")),
        ),
        [],
      );
      const rejected = JSON.parse(fs.readFileSync(path.join(stateDir, "rejected-leads.json")));
      assert.equal(rejected[0].source_ref, "apollo-person-1");
      assert.deepEqual(rejected[0].custom_variables, { research: "retained" });
    },
  );
});

test("a missing custom variable is rejected even when no name token is used", async () => {
  await withRun({ steps: [{ subject: "Hello", body: "We saw {{recentLaunch}}." }],
    carryOver: [{ email: "missing@example.test", source_ref: "keep-me" }] },
  async ({ stateDir, posted, runDir, url }) => {
    const result = await replenish(runDir, url);
    assert.equal(result.code, 0, result.stderr);
    assert.equal(posted.length, 0);
    const rejected = JSON.parse(fs.readFileSync(path.join(stateDir, "rejected-leads.json")));
    assert.equal(rejected[0].problems[0].field, "recentLaunch");
    assert.equal(rejected[0].source_ref, "keep-me");
  });
});

test("an explicitly confirmed genuine name can match a title token", async () => {
  await withRun({ steps: [{ subject: "Hello", body: "Hello {{firstName}}." }],
    carryOver: [{ email: "confirmed@example.test", first_name: "CA", first_name_confirmed: true }] },
  async ({ posted, runDir, url }) => {
    const result = await replenish(runDir, url);
    assert.equal(result.code, 0, result.stderr);
    assert.equal(posted.length, 1);
  });
});
