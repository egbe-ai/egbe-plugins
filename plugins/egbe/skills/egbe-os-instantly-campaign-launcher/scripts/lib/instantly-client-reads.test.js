const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const { InstantlyClient } = require("./instantly-client");

async function withClient(run, responseBody) {
  const seen = [];
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, "http://localhost");
    seen.push({ path: url.pathname, query: Object.fromEntries(url.searchParams) });
    assert.equal(req.method, "GET");
    assert.equal(req.headers.authorization, "Bearer test");
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ data: responseBody ?? (url.searchParams.has("starting_after")
      ? { items: [{ id: "owned" }], next_starting_after: null }
      : { items: [], next_starting_after: "opaque/page+1" }) }));
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  try {
    await run(new InstantlyClient({ osApiKey: "test", osUrl: `http://127.0.0.1:${server.address().port}` }), seen);
  } finally {
    await new Promise(resolve => server.close(resolve));
  }
}

test("campaign pagination advances even after an empty project-filtered page", async () => {
  await withClient(async (client, seen) => {
    const first = await client.listCampaigns(2);
    assert.deepEqual(first.body.items, []);
    const next = await client.listCampaigns(2, first.body.next_starting_after);
    assert.deepEqual(next.body.items, [{ id: "owned" }]);
    assert.equal(next.body.next_starting_after, null);
    assert.deepEqual(seen.map(r => r.query), [{ limit: "2" }, { limit: "2", starting_after: "opaque/page+1" }]);
    assert.ok(seen.every(r => r.path === "/outreach/instantly/campaigns"));
  });
});

test("default campaign reads retain limit 100 without a cursor", async () => {
  await withClient(async (client, seen) => {
    await client.listCampaigns();
    assert.deepEqual(seen[0].query, { limit: "100" });
  });
});

test("account reads preserve cursor and provider status alias", async () => {
  await withClient(async (client, seen) => {
    await client.listAccounts(2, { status: 1, starting_after: "sender+1@example.test" });
    assert.deepEqual(seen, [{ path: "/outreach/instantly/accounts", query: {
      limit: "2", status_filter: "1", starting_after: "sender+1@example.test",
    } }]);
  });
});

test("campaign sender reads use only the encoded campaign path", async () => {
  await withClient(async (client, seen) => {
    await client.campaignSenders("campaign/other?email=foreign@example.test#fragment");
    assert.deepEqual(seen, [{
      path: "/outreach/instantly/campaigns/campaign%2Fother%3Femail%3Dforeign%40example.test%23fragment/senders",
      query: {},
    }]);
  });
});

test("campaign sender reads preserve unavailable signals without shared-list fallback", async () => {
  const observation = {
    campaign_id: "campaign-1", observed_at: "2026-11-12T12:00:00Z", complete: false,
    items: [{ email: "sender@example.test", status: 1, daily_limit: 0,
      warmup_status: null, stat_warmup_score: null, data_status: "partial",
      missing_fields: ["warmup_status", "stat_warmup_score"] }],
  };
  await withClient(async (client, seen) => {
    const result = await client.campaignSenders("campaign-1");
    assert.equal(result.status, 200);
    assert.deepEqual(result.body, observation);
    assert.deepEqual(seen, [{ path: "/outreach/instantly/campaigns/campaign-1/senders", query: {} }]);
  }, observation);
});

test("overview keeps date-only and ISO timestamp queries exactly as supplied", async () => {
  await withClient(async (client, seen) => {
    const ranges = [{}, { start_date: "2026-11-11", end_date: "2026-11-12" },
      { start_date: "2026-11-11T02:00:00+02:00", end_date: "2026-11-11T23:59:59.999Z" }];
    for (const range of ranges) await client.analyticsOverview(["campaign-1"], range);
    assert.deepEqual(seen.map(r => r.query), ranges);
    assert.ok(seen.every(r => r.path === "/outreach/instantly/campaigns/campaign-1/analytics/overview"));
  });
});
