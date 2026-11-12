// Utilization when lead_stats is null (#3790): replenish falls back to the
// leads API. Instantly v2 leads keep status 1 after the first send, so the
// contacted signal is send/reply activity (timestamp_last_contact, last step,
// counters), and analytics contacted_count wins when it is plausible for the
// campaign (as in monitor-campaign).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { isContactedLead, contactedForUtilization } = require("./instantly-client");
const { makeRun, startServer, replenish } = require("./replenish-test-harness");

// v2 lead shape after the first send: status 1, no lead_status.
function sentLead(i) {
  return {
    id: `l${i}`,
    email: `sent${i}@example.test`,
    status: 1,
    timestamp_last_contact: "2026-10-20T15:00:00.000Z",
    status_summary: { lastStep: { stepID: "0_0_0" } },
  };
}
function unsentLead(i) {
  return { id: `u${i}`, email: `unsent${i}@example.test`, status: 1, status_summary: {} };
}

test("isContactedLead reads the Instantly v2 contact fields", () => {
  assert.equal(isContactedLead(sentLead(0)), true);
  assert.equal(isContactedLead({ status: 1, timestamp_last_contact: "2026-10-20T15:00:00.000Z" }), true);
  assert.equal(isContactedLead({ status: 1, status_summary: { lastStep: { stepID: "0_0_0" } } }), true);
  assert.equal(isContactedLead({ status: 1, last_step_id: "s1" }), true);
  assert.equal(isContactedLead({ status: 1, email_reply_count: 1 }), true);
  assert.equal(isContactedLead(unsentLead(0)), false);
  assert.equal(isContactedLead({ status: 1 }), false);
  assert.equal(isContactedLead({ status: 1, status_summary: { lastStep: {} } }), false);
  assert.equal(isContactedLead({ status: 1, email_reply_count: 0, email_open_count: 0 }), false);
});

test("contactedForUtilization caps analytics and drops workspace-level counts", () => {
  const counts = { total: 10, contacted: 3 };
  assert.equal(contactedForUtilization(8, counts), 8);
  assert.equal(contactedForUtilization(12, counts), 10);
  assert.equal(contactedForUtilization(300, counts), 3);
  assert.equal(contactedForUtilization(0, counts), 3);
  assert.equal(contactedForUtilization(1, counts), 3);
});

const cases = [
  {
    name: "analytics contacted_count with null lead_stats",
    analyticsContacted: 4,
    leads: [0, 1, 2, 3].map(unsentLead),
    imports: true,
  },
  {
    name: "no analytics count, leads carry v2 contact fields",
    analyticsContacted: 0,
    leads: [0, 1, 2, 3].map(sentLead),
    imports: true,
  },
  {
    name: "nobody contacted yet",
    analyticsContacted: 0,
    leads: [0, 1, 2, 3].map(unsentLead),
    skipped: /Utilization 0\.0% < threshold/,
  },
  {
    name: "workspace-level analytics count is ignored",
    analyticsContacted: 300,
    leads: [0, 1, 2, 3].map(unsentLead),
    skipped: /Utilization 0\.0% < threshold/,
  },
  {
    name: "partial leads count is unreadable",
    analyticsContacted: 300,
    leads: Array.from({ length: 100 }, (_, i) => sentLead(i)),
    failNextPage: true,
    skipped: /cannot compute utilization/,
  },
];

for (const c of cases) {
  test(`replenish with null lead_stats: ${c.name}`, async () => {
    const carryOver = [{ email: "next@example.test" }];
    const { runDir, stateDir, cleanup } = makeRun(carryOver, "replenish-utilization-");
    const campaignLeads = [...c.leads];
    let posts = 0;
    const srv = await startServer((endpoint, req) => {
      if (endpoint.endsWith("/campaigns/c")) return { data: { id: "c", lead_stats: null } };
      if (endpoint.endsWith("/analytics")) return { data: { contacted_count: c.analyticsContacted } };
      if (endpoint.endsWith("/leads")) {
        if (c.failNextPage && req.url.includes("starting_after")) return { status: 500 };
        return { data: { items: campaignLeads } };
      }
      if (endpoint.endsWith("/leads/add") && req.method === "POST") {
        posts++;
        campaignLeads.push({ id: "n1", email: carryOver[0].email, status: 1 });
        return { data: { leads_uploaded: 1 } };
      }
      return null;
    });
    try {
      const run = await replenish(runDir, srv.url);
      assert.equal(run.code, 0, run.stderr);
      if (c.imports) {
        assert.equal(posts, 1, run.stdout + run.stderr);
        assert.deepEqual(JSON.parse(fs.readFileSync(path.join(stateDir, "carry-over-leads.json"))), []);
      } else {
        assert.equal(posts, 0);
        assert.match(run.stdout, c.skipped);
      }
    } finally {
      srv.close();
      cleanup();
    }
  });
}
