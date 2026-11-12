const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { makeRun, startServer, replenish } = require("./replenish-test-harness");

for (const failure of ["lead-read", "ambiguous-import"]) {
  test(`carry-over survives ${failure} and reconciles the same batch on rerun`, async () => {
    const leads = [{ email: "first@example.test" }, { email: "second@example.test" }];
    const { runDir, stateDir, cleanup } = makeRun(leads, "replenish-carry-over-");
    let firstRun = true;
    let posts = 0;
    const srv = await startServer((endpoint, req) => {
      if (endpoint.endsWith("/campaigns/c")) return { data: { id: "c", lead_stats: { total: 1 } } };
      if (endpoint.endsWith("/analytics")) return { data: { contacted_count: 1 } };
      if (endpoint.endsWith("/leads")) {
        return {
          status: firstRun && failure === "lead-read" ? 404 : 200,
          data: { items: !firstRun && failure === "ambiguous-import" ? [{ id: "l1", campaign: "c", email: leads[0].email }] : [] },
        };
      }
      if (endpoint.endsWith("/leads/add") && req.method === "POST") {
        posts++;
        return { status: firstRun ? 504 : 200, data: { leads_uploaded: 1 } };
      }
      return null;
    });
    try {
      const failed = await replenish(runDir, srv.url, ["--force"]);
      assert.equal(failed.code, 1);
      assert.match(failed.stderr, failure === "lead-read" ? /import stopped/ : /batch may have landed/);
      assert.deepEqual(JSON.parse(fs.readFileSync(path.join(stateDir, "carry-over-leads.json"))), leads);
      assert.equal(fs.existsSync(path.join(stateDir, "imported-leads.json")), false);
      firstRun = false;
      const retry = await replenish(runDir, srv.url, ["--force"]);
      assert.equal(retry.code, 0, retry.stderr);
      assert.deepEqual(JSON.parse(fs.readFileSync(path.join(stateDir, "carry-over-leads.json"))), [leads[1]]);
      assert.equal(JSON.parse(fs.readFileSync(path.join(stateDir, "imported-leads.json"))).length, 1);
      assert.equal(posts, 1, "an already-landed ambiguous batch must not be posted again");
    } finally {
      srv.close();
      cleanup();
    }
  });
}
