"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { execFile, spawn } = require("node:child_process");
const { promisify } = require("node:util");
const { ApolloClient, toMatchDetails } = require("./apollo-client");
const { searchParams, positiveInteger } = require("./sourcing");
const exec = promisify(execFile);

async function fixture(t, handler) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "apollo-test-"));
  const calls = [];
  const server = http.createServer(async (req, res) => {
    let body = "";
    for await (const chunk of req) body += chunk;
    const call = { url: req.url, headers: req.headers, body: JSON.parse(body || "null") };
    calls.push(call);
    const response = await handler(call, calls.length);
    if (res.destroyed) return;
    res.writeHead(response.status || 200, { "Content-Type": "application/json", ...response.headers });
    res.end(JSON.stringify(response.body));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(() => { server.closeAllConnections(); server.close(); fs.rmSync(directory, { recursive: true, force: true }); });
  const url = `http://127.0.0.1:${server.address().port}`;
  const env = { ...process.env, OS_URL: url, OS_API_KEY: "test-only", OS_AGENT_NAME: "" };
  const run = async (command, args = []) => {
    try {
      const result = await exec(process.execPath, [path.resolve(__dirname, `../${command}.js`), ...args], { env });
      return { code: 0, ...result };
    } catch (error) { return { code: error.code, stdout: error.stdout, stderr: error.stderr }; }
  };
  return { directory, calls, url, env, run };
}
const person = (id) => ({ id: String(id), first_name: "Alex", last_name: "Example", email: `alex${id}@business.test`,
  email_status: "verified", organization: { name: "Example", primary_domain: "business.test" } });
const quota = { status: 429, body: { detail: "limit_exceeded:apollo:enrichments" } };

test("bounded transport retries have no second outer rate-limit loop", async (t) => {
  const f = await fixture(t, () => ({ status: 429, headers: { "Retry-After": "1" }, body: { error: "rate limited" } }));
  let clock = 0;
  const client = new ApolloClient({ osUrl: f.url, osApiKey: "test", now: () => clock,
    sleep: async (ms) => { clock += ms; }, timeBudgetMs: 20000 });
  const result = await client.bulkEnrichAll([person(1)]);
  assert.equal(f.calls.length, 5);
  assert.equal(result.complete, false);
  assert.equal(result.stop_reason, "rate_limited");
  assert.equal(result.not_enriched, 1);
});

test("Retry-After exceeding budget returns without sleeping or retrying", async (t) => {
  const f = await fixture(t, () => ({ status: 429, headers: { "Retry-After": "600" }, body: {} }));
  const client = new ApolloClient({ osUrl: f.url, osApiKey: "test", timeBudgetMs: 1000,
    sleep: async () => { throw new Error("must not sleep"); } });
  const result = await client.bulkEnrichAll([person(1)]);
  assert.equal(f.calls.length, 1);
  assert.equal(result.stop_reason, "time_budget");
});

test("search failure preserves the completed page and its next page", async () => {
  const client = new ApolloClient({ osUrl: "https://os.invalid", osApiKey: "test" });
  client.searchPeople = async ({ page }) => page === 1 ? { status: 200, body: { people: Array.from({ length: 100 }, (_, i) => person(i)) } } : quota;
  const states = [];
  const result = await client.searchAllPeople({}, { maxResults: 200, onProgress: (state) => states.push(JSON.parse(JSON.stringify(state))) });
  assert.equal(result.people.length, 100);
  assert.equal(result.next_page, 2);
  assert.equal(result.stop_reason, "daily_quota");
  assert.equal(result.complete, false);
  assert.equal(states[0].people.length, 100);
});

test("preview is usable by enrich, including ID-less structured inputs and email-status flag", async (t) => {
  const raw = { first_name: "Alex", last_name: "Example", organization: { name: "Firm", primary_domain: "firm.test" } };
  const f = await fixture(t, (call) => call.url.endsWith("/search") ? { body: { data: { people: [raw] } } } :
    { body: { data: { matches: [person(1)] } } });
  const preview = path.join(f.directory, "preview.json");
  const found = await f.run("search", ["--titles", "CTO", "--email-status", "verified", "--output", preview]);
  assert.equal(found.code, 0, found.stderr);
  assert.deepEqual(f.calls[0].body.contact_email_status, ["verified"]);
  assert.deepEqual(JSON.parse(fs.readFileSync(preview)).people, [raw]);
  const enriched = await f.run("enrich", ["--input", preview]);
  assert.equal(enriched.code, 0, enriched.stderr);
  assert.equal(JSON.parse(enriched.stdout).leads.length, 1);
  assert.equal(f.calls[1].body.details[0].domain, "firm.test");
  assert.equal(f.calls[1].body.details[0].last_name, "Example");
  assert.equal(f.calls[1].headers.authorization, "Bearer test-only");
});

test("combined partial output resumes only unfinished inputs and retains earlier leads", async (t) => {
  let limited = true;
  const f = await fixture(t, (call) => {
    if (call.url.endsWith("/search")) return { body: { people: Array.from({ length: 11 }, (_, i) => person(i)) } };
    if (call.body.details[0].id === "10" && limited) return quota;
    return { body: { matches: call.body.details.map((p) => person(p.id)) } };
  });
  const output = path.join(f.directory, "leads.json");
  const first = await f.run("find-leads", ["--max-results", "11", "--output", output]);
  assert.equal(first.code, 2, first.stderr);
  let result = JSON.parse(fs.readFileSync(output));
  assert.equal(result.leads.length, 10);
  assert.equal(result.meta.not_enriched, 1);
  assert.equal(result.meta.stop_reason, "daily_quota");
  limited = false;
  const second = await f.run("enrich", ["--input", output, "--output", output]);
  assert.equal(second.code, 0, second.stderr);
  result = JSON.parse(fs.readFileSync(output));
  assert.equal(result.leads.length, 11);
  assert.equal(result.meta.not_enriched, 0);
  assert.equal(result.meta.processed_count, 11);
  assert.equal(result.meta.enriched, 11);
  assert.equal(result.meta.error_status, undefined);
  assert.deepEqual(f.calls.at(-1).body.details.map((p) => p.id), ["10"]);
  assert.equal(f.calls.filter((call) => call.url.endsWith("/search")).length, 1);
});

test("empty search and empty enrich retain the standard completed zero shape", async (t) => {
  const f = await fixture(t, () => ({ body: { people: [] } }));
  const searched = await f.run("find-leads");
  assert.equal(searched.code, 0, searched.stderr);
  const result = JSON.parse(searched.stdout);
  assert.deepEqual(result.leads, []);
  assert.equal(result.meta.complete, true);
  assert.equal(result.meta.leads_with_email, 0);
  assert.equal(result.meta.not_enriched, 0);
  assert.deepEqual(result.meta.email_status_filter, ["verified", "likely"]);
  const input = path.join(f.directory, "empty.json");
  fs.writeFileSync(input, "[]");
  const enriched = await f.run("enrich", ["--input", input]);
  assert.equal(enriched.code, 0, enriched.stderr);
  assert.equal(JSON.parse(enriched.stdout).meta.complete, true);
  assert.equal(f.calls.length, 1);
});

test("malformed enrichment input fails before requests; config supports raw or nested filters", async (t) => {
  const f = await fixture(t, () => { throw new Error("No calls expected"); });
  const input = path.join(f.directory, "invalid.json");
  fs.writeFileSync(input, JSON.stringify([{ name: "Alex Example" }]));
  const result = await f.run("enrich", ["--input", input]);
  assert.equal(result.code, 1);
  assert.equal(f.calls.length, 0);
  assert.match(result.stderr, /display name alone is not enough/);
  assert.deepEqual(toMatchDetails({ apollo_id: "x" }).id, "x");
  assert.equal(toMatchDetails({ first_name: "A", last_name: "B", company: "Firm", website: "https://firm.test/about" }).domain, "firm.test");
  assert.throws(() => positiveInteger("5x", 50, "--max-results"));
  const config = path.join(f.directory, "config.json");
  fs.writeFileSync(config, JSON.stringify({ search: { person_titles: ["CTO"] } }));
  assert.deepEqual(searchParams({ config }), { person_titles: ["CTO"] });
});

test("filtering and dedup are distinct from unfinished enrichment", async (t) => {
  const f = await fixture(t, () => ({ body: { matches: [person(1), person(1), { ...person(2), email_status: "unknown" }, { id: "3" }, null] } }));
  const input = path.join(f.directory, "people.json");
  fs.writeFileSync(input, JSON.stringify(Array.from({ length: 5 }, (_, i) => ({ id: String(i) }))));
  const run = await f.run("enrich", ["--input", input]);
  assert.equal(run.code, 0, run.stderr);
  const result = JSON.parse(run.stdout);
  assert.equal(result.leads.length, 1);
  assert.equal(result.meta.processed_count, 5);
  assert.equal(result.meta.enriched, 4);
  assert.equal(result.meta.not_enriched, 0);
  assert.deepEqual(result.meta.drops, { no_email: 1, email_status: 1, duplicate_email: 1 });
});

test("network timeout saves pending input and exits incomplete", async (t) => {
  const f = await fixture(t, async () => { await new Promise((resolve) => setTimeout(resolve, 100)); return { body: { matches: [] } }; });
  const input = path.join(f.directory, "people.json");
  const output = path.join(f.directory, "result.json");
  fs.writeFileSync(input, JSON.stringify([{ id: "1" }]));
  const run = await f.run("enrich", ["--input", input, "--output", output, "--time-budget-ms", "20"]);
  assert.equal(run.code, 2, run.stderr);
  const result = JSON.parse(fs.readFileSync(output));
  assert.equal(result.meta.complete, false);
  assert.equal(result.meta.stop_reason, "time_budget");
  assert.equal(result.meta.not_enriched, 1);
});

test("partial search remains incomplete after all discovered people enrich", async (t) => {
  const f = await fixture(t, (call) => ({ body: { matches: call.body.details.map((p) => person(p.id)) } }));
  const input = path.join(f.directory, "partial.json");
  fs.writeFileSync(input, JSON.stringify({ leads: [person(0)], meta: { source: "apollo", enriched: 1, processed_count: 1,
    search_complete: false, search_stop_reason: "daily_quota", search_next_page: 2, not_enriched_people: [{ id: "1" }] } }));
  const run = await f.run("enrich", ["--input", input]);
  assert.equal(run.code, 2, run.stderr);
  const result = JSON.parse(run.stdout);
  assert.equal(result.leads.length, 2);
  assert.equal(result.meta.complete, false);
  assert.equal(result.meta.not_enriched, 0);
  assert.equal(result.meta.stop_reason, "daily_quota");
});

test("a hard interruption retains completed batches and the pending tail", async (t) => {
  const f = await fixture(t, (call) => ({ body: { matches: call.body.details.map((p) => person(p.id)) } }));
  const input = path.join(f.directory, "people.json");
  const output = path.join(f.directory, "checkpoint.json");
  fs.writeFileSync(input, JSON.stringify(Array.from({ length: 11 }, (_, id) => ({ id: String(id) }))));
  const child = spawn(process.execPath, [path.resolve(__dirname, "../enrich.js"), "--input", input, "--output", output],
    { env: f.env, stdio: "ignore" });
  t.after(() => child.kill("SIGKILL"));
  const closed = new Promise((resolve) => child.once("exit", resolve));
  let state;
  const deadline = Date.now() + 3000;
  while (Date.now() < deadline) {
    if (fs.existsSync(output)) state = JSON.parse(fs.readFileSync(output));
    if (state?.leads?.length === 10) break;
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  child.kill("SIGKILL");
  await closed;
  assert.equal(state?.leads?.length, 10);
  assert.equal(state.meta.complete, false);
  assert.equal(state.meta.not_enriched, 1);
  assert.deepEqual(state.meta.not_enriched_people, [{ id: "10" }]);
  assert.equal(f.calls.length, 1);
});
