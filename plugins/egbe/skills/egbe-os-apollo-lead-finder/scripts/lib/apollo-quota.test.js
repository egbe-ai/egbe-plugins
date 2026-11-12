#!/usr/bin/env node
// Unit test: the gateway's per-claw daily Apollo quota (429 with
// "limit_exceeded:<resource>") must end bulk enrichment with the partial
// results instead of retrying every 60s until the quota resets (#4546).
// Apollo's own rate-limit 429s are still retried.
//
// Pure stub test — no network calls.
// Run: node scripts/lib/apollo-quota.test.js

const assert = require("node:assert/strict");
const { ApolloClient, isDailyQuotaError } = require("./apollo-client");

const quota = {
  status: 429,
  headers: {},
  body: { ok: false, error: { message: '{"detail":"limit_exceeded:apollo:enrichments","resource":"apollo:enrichments"}' } },
};

assert.equal(isDailyQuotaError(quota), true);
assert.equal(isDailyQuotaError({ status: 429, headers: {}, body: { error: "rate limited" } }), false);
assert.equal(isDailyQuotaError({ status: 200, headers: {}, body: { detail: "limit_exceeded:x" } }), false);

(async () => {
  const client = new ApolloClient({ osUrl: "https://os.invalid", osApiKey: "test-key" });
  let calls = 0;
  client.bulkEnrichPeople = async (details) => {
    calls += 1;
    if (calls === 1) return { status: 200, headers: {}, body: { matches: details.map((d) => ({ id: d.id })) } };
    return quota;
  };
  const people = Array.from({ length: 25 }, (_, i) => ({ id: `p${i}` }));
  const started = Date.now();
  const enriched = await client.bulkEnrichAll(people, { batchDelayMs: 0 });
  assert.equal(enriched.matches.length, 10, "keeps the batch enriched before the quota");
  assert.equal(enriched.complete, false);
  assert.equal(enriched.stop_reason, "daily_quota");
  assert.equal(enriched.not_enriched, 15);
  assert.deepEqual(enriched.not_enriched_people, people.slice(10));
  assert.equal(calls, 2, "stops instead of retrying the exhausted batch");
  assert.ok(Date.now() - started < 5_000, "does not wait out a Retry-After loop");
  console.log("apollo-quota.test.js: ok");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
