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
const creditMessage = "You have insufficient credits! Upgrade your plan to increase your number of lead credits.";
const creditError = { error: creditMessage };
const osError = (body) => ({ code: 422, data: null,
  message: `outreach upstream: ${JSON.stringify(body)}. GET / to see what this gateway offers and how to register.` });

for (const [shape, body] of Object.entries({ raw: creditError, os: osError(creditError),
  legacy: { ok: false, error: { message: JSON.stringify(creditError) } }, text: { raw: creditMessage } })) {
  test(`bulk failure retains a safe credit diagnostic from ${shape} without retrying`, async () => {
    const client = new ApolloClient({ osUrl: "https://os.invalid", osApiKey: "test", maxRetries: 0 });
    let calls = 0;
    client.bulkEnrichPeople = async () => { calls++; return { status: 422, body }; };
    const result = await client.bulkEnrichAll(Array.from({ length: 10 }, (_, i) => ({ id: `p${i}` })));
    assert.equal(calls, 1);
    assert.equal(result.error_status, 422);
    assert.equal(result.stop_reason, "provider_error");
    assert.equal(result.processed_count, 0);
    assert.equal(result.not_enriched, 10);
    assert.deepEqual(result.error, { code: "insufficient_credits", message: creditMessage });
  });
}

for (const saved of [false, true]) {
  test(`enrichment CLI keeps safe failure details in ${saved ? "checkpoint" : "stdout"}`, async (t) => {
    const sensitive = "FAKE-secret-person-and-key-not-for-output";
    const f = await fixture(t, () => ({ status: 422, body: osError({ ...creditError,
      input: { email: sensitive }, authorization: sensitive, stack: sensitive }) }));
    const input = path.join(f.directory, "people.json");
    const output = path.join(f.directory, "result.json");
    fs.writeFileSync(input, JSON.stringify(Array.from({ length: 10 }, (_, i) => ({ id: `p${i}` }))));
    const run = await f.run("enrich", ["--input", input, ...(saved ? ["--output", output] : [])]);
    assert.equal(run.code, 2, run.stderr);
    const text = saved ? fs.readFileSync(output, "utf8") : run.stdout;
    const result = JSON.parse(text);
    assert.deepEqual(result.meta.error, { code: "insufficient_credits", message: creditMessage });
    assert.equal(result.meta.error_status, 422);
    assert.equal(result.meta.not_enriched, 10);
    assert.equal(f.calls.length, 1);
    assert.ok(!text.includes(sensitive) && !run.stderr.includes(sensitive));
  });
}

test("validation diagnostics retain safe paths/types without input or free-text echoes", async (t) => {
  const sensitive = "FAKE-private-person@example.test";
  const body = { detail: [
    { type: "missing", loc: ["body", "details", 0, "domain"], msg: "Field required", input: sensitive },
    { type: "value_error", loc: ["body", "details", 0, sensitive], msg: `Invalid ${sensitive}`, ctx: { key: sensitive } },
  ], headers: { Authorization: sensitive } };
  const f = await fixture(t, () => ({ status: 422, body: osError(body) }));
  const input = path.join(f.directory, "people.json");
  fs.writeFileSync(input, JSON.stringify([{ id: "p1" }]));
  const run = await f.run("enrich", ["--input", input]);
  assert.equal(run.code, 2, run.stderr);
  const error = JSON.parse(run.stdout).meta.error;
  assert.equal(error.code, "validation_error");
  assert.deepEqual(error.validation, [
    { loc: ["body", "details", 0, "domain"], type: "missing", message: "Field required." },
    { loc: ["body", "details", 0, "[redacted]"], type: "value_error", message: "Invalid value." },
  ]);
  assert.ok(!run.stdout.includes(sensitive) && !run.stderr.includes(sensitive));
});

test("unknown and malformed failure bodies get a bounded redacted diagnostic", async () => {
  const client = new ApolloClient({ osUrl: "https://os.invalid", osApiKey: "test", maxRetries: 0 });
  for (const body of ["<html>FAKE-private-secret</html>", { message: "FAKE-private-secret" },
    { detail: [{ type: "FAKE-private-secret", loc: ["body", "id"], input: "FAKE-private-secret" }] },
    { detail: [{ type: { toString: "FAKE-private-secret" }, loc: ["body", "id"] }] }, null]) {
    client.bulkEnrichPeople = async () => ({ status: 422, body });
    const result = await client.bulkEnrichAll([{ id: "p1" }]);
    assert.equal(result.error.code, "provider_error");
    assert.match(result.error.message, /omitted/);
    assert.ok(!JSON.stringify(result.error).includes("FAKE-private-secret"));
    assert.ok(JSON.stringify(result.error).length < 512);
  }
});

test("validation diagnostics stay bounded and do not echo unknown path values", async () => {
  const client = new ApolloClient({ osUrl: "https://os.invalid", osApiKey: "test" });
  client.bulkEnrichPeople = async () => ({ status: 422, body: { detail: Array.from({ length: 200 }, () => ({
    type: "missing", loc: ["body", "details", 123456789012, "FAKE-private-secret"], msg: "FAKE-private-secret",
  })) } });
  const result = await client.bulkEnrichAll([{ id: "p1" }]);
  assert.equal(result.error.validation.length, 10);
  assert.ok(JSON.stringify(result.error).length < 4096);
  assert.ok(!JSON.stringify(result.error).includes("FAKE-private-secret"));
  assert.deepEqual(result.error.validation[0].loc, ["body", "details", "[redacted]", "[redacted]"]);
});

for (const [status, body, code, stop] of [[401, {}, "authorization", "authorization"],
  [429, {}, "rate_limited", "rate_limited"], [429, quota.body, "daily_quota", "daily_quota"]]) {
  test(`safe ${code} diagnostic retains the existing ${stop} stop reason`, async () => {
    const client = new ApolloClient({ osUrl: "https://os.invalid", osApiKey: "test" });
    client.bulkEnrichPeople = async () => ({ status, body });
    const result = await client.bulkEnrichAll([{ id: "p1" }]);
    assert.equal(result.error.code, code);
    assert.equal(result.stop_reason, stop);
    assert.equal(result.error_status, status);
  });
}

test("partial enrichment preserves diagnostic and explicit resume clears stale legacy errors", async (t) => {
  let rejected = true;
  const f = await fixture(t, (call) => rejected && call.body.details[0].id === "10"
    ? { status: 422, body: osError(creditError) }
    : { body: { matches: call.body.details.map((p) => person(p.id)) } });
  const input = path.join(f.directory, "people.json");
  const output = path.join(f.directory, "result.json");
  fs.writeFileSync(input, JSON.stringify(Array.from({ length: 11 }, (_, i) => ({ id: String(i) }))));
  const first = await f.run("enrich", ["--input", input, "--output", output]);
  assert.equal(first.code, 2, first.stderr);
  const partial = JSON.parse(fs.readFileSync(output));
  assert.equal(partial.meta.error.code, "insufficient_credits");
  assert.equal(partial.meta.processed_count, 10);
  assert.equal(partial.leads.length, 10);
  assert.deepEqual(partial.meta.not_enriched_people, [{ id: "10" }]);
  // Older/custom checkpoints may carry untrusted diagnostics: never carry them
  // forward into a new operation's first checkpoint or successful result.
  partial.meta.error = { raw: "FAKE-stale-secret" };
  fs.writeFileSync(output, JSON.stringify(partial));
  rejected = false;
  const resumed = await f.run("enrich", ["--input", output, "--output", output]);
  assert.equal(resumed.code, 0, resumed.stderr);
  const text = fs.readFileSync(output, "utf8");
  const result = JSON.parse(text);
  assert.equal(result.meta.error, undefined);
  assert.equal(result.meta.error_status, undefined);
  assert.equal(result.meta.processed_count, 11);
  assert.equal(result.leads.length, 11);
  assert.ok(!text.includes("FAKE-stale-secret"));
  assert.deepEqual(f.calls.at(-1).body.details.map((p) => p.id), ["10"]);
  assert.equal(f.calls.length, 3);
});

test("combined search/enrichment persists the failed enrichment diagnostic", async (t) => {
  const f = await fixture(t, (call) => call.url.endsWith("/search")
    ? { body: { people: [person(1)] } } : { status: 422, body: osError(creditError) });
  const run = await f.run("find-leads", ["--max-results", "1"]);
  assert.equal(run.code, 2, run.stderr);
  const result = JSON.parse(run.stdout);
  assert.equal(result.meta.search_complete, true);
  assert.equal(result.meta.error.code, "insufficient_credits");
  assert.equal(result.meta.not_enriched, 1);
  assert.equal(f.calls.length, 2);
});

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
