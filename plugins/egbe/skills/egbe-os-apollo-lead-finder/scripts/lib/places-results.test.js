"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const { execFile } = require("node:child_process");
const { promisify } = require("node:util");
const path = require("node:path");
const { pickEmail, extractEmails } = require("../places-leads");
const { extractOwnerFirstName } = require("./places-filters");

test("email ranking is selectable but trap filtering is not bypassed", () => {
  const candidates = ["impallari@gmail.com", "alex@business.test", "info@business.test", "logo.svg@asset.test"];
  assert.equal(pickEmail(candidates, "business.test").email, "alex@business.test");
  assert.equal(pickEmail(candidates, "business.test", "generic").email, "info@business.test");
  assert.equal(pickEmail(candidates, "business.test", "first").email, "alex@business.test");
  assert.equal(pickEmail(["noreply@business.test"], "business.test"), null);
  assert.deepEqual(extractEmails('<a href="mailto:Alex%40business.test">Mail</a> alex@business.test'), ["alex@business.test"]);
  assert.equal(extractOwnerFirstName("My name is Alex", "Example Studio"), "Alex");
  assert.equal(extractOwnerFirstName("Meet Our Team", "Example Studio"), "");
});

async function runPlaces(t, handler, args = []) {
  const calls = [];
  const server = http.createServer(async (req, res) => {
    let data = "";
    for await (const chunk of req) data += chunk;
    calls.push({ url: req.url, body: JSON.parse(data) });
    const answer = handler(calls.at(-1));
    res.writeHead(answer.status || 200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(answer.body));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => { server.closeAllConnections(); server.close(); });
  const env = { ...process.env, OS_AGENT_NAME: "", OS_API_KEY: "test-only", OS_URL: `http://127.0.0.1:${server.address().port}` };
  let result;
  try { result = { code: 0, ...await promisify(execFile)(process.execPath,
    [path.resolve(__dirname, "../places-leads.js"), "--queries", "a;b", ...args], { env }) }; }
  catch (error) { result = { code: error.code, stdout: error.stdout, stderr: error.stderr }; }
  return { ...result, calls, result: result.stdout ? JSON.parse(result.stdout) : null };
}

test("successful zero Places search is complete, not a false enrichment", async (t) => {
  const run = await runPlaces(t, () => ({ body: { results: [] } }));
  assert.equal(run.code, 0, run.stderr);
  assert.equal(run.result.meta.complete, true);
  assert.equal(run.result.meta.enriched, 0);
  assert.equal(run.result.meta.sites_scraped, 0);
  assert.deepEqual(run.result.leads, []);
});

test("all failed Places search returns structured partial and does not retry daily quota", async (t) => {
  const run = await runPlaces(t, () => ({ status: 429, body: { detail: "limit_exceeded:places:searches" } }));
  assert.equal(run.code, 2, run.stderr);
  assert.equal(run.calls.length, 1);
  assert.equal(run.result.meta.complete, false);
  assert.equal(run.result.meta.stop_reason, "daily_quota");
  assert.deepEqual(run.result.meta.pending_queries, ["a", "b"]);
});

test("Places detail quota retains pending places separately from no-email drops", async (t) => {
  const run = await runPlaces(t, (call) => call.url.endsWith("/places") ?
    { body: { results: [{ title: "Business", metadata: { place_id: "p1" } }] } } :
    { status: 429, body: { detail: "limit_exceeded:places:details" } });
  assert.equal(run.code, 2, run.stderr);
  assert.equal(run.result.meta.total_found, 1);
  assert.equal(run.result.meta.drops.details_failed, 1);
  assert.equal(run.result.meta.drops.no_email, 0);
  assert.equal(run.result.meta.not_processed_places[0].place_id, "p1");
  assert.equal(run.calls.filter((call) => call.url.endsWith("/details")).length, 1);
});

test("blocked/unreadable websites are not reported as zero-email successes", async (t) => {
  const run = await runPlaces(t, (call) => call.url.endsWith("/places") ?
    { body: { results: [{ title: "Business", metadata: { place_id: "p1" } }] } } :
    { body: { displayName: { text: "Business" }, websiteUri: "http://127.0.0.1/private" } });
  assert.equal(run.code, 2, run.stderr);
  assert.equal(run.result.meta.drops.scrape_failed, 1);
  assert.equal(run.result.meta.drops.no_email, 0);
  assert.equal(run.result.meta.stop_reason, "website_unavailable");
});

test("local cap validation prevents accidental unbounded paid work", async (t) => {
  const run = await runPlaces(t, () => { throw new Error("No calls expected"); }, ["--max-places", "6O"]);
  assert.equal(run.code, 1);
  assert.equal(run.calls.length, 0);
});
