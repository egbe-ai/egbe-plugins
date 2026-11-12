const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const vm = require("node:vm");
const { createRequire } = require("node:module");

function loadSource(t, checkpoint, failure) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "egbe-apollo-partial-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const output = path.join(root, "leads.json");
  const script = path.resolve(__dirname, "../replenish-leads.js");
  const localRequire = createRequire(script);
  const calls = [];
  const sandbox = { module: { exports: {} }, __dirname: path.dirname(script),
    require: (name) => name === "child_process" ? { execFileSync: (command, args, options) => {
      calls.push({ command, args, options });
      if (checkpoint !== undefined) fs.writeFileSync(output, JSON.stringify(checkpoint));
      if (failure) throw failure;
    } } : localRequire(name),
    process: { execPath: process.execPath, env: { OS_API_KEY: "fixture-key", OS_URL: "http://127.0.0.1" } },
    console: { error: () => {} } };
  vm.runInNewContext(fs.readFileSync(script, "utf8"), sandbox);
  return { run: () => sandbox.module.exports.sourceFromApollo(null, { person_titles: ["Founder"] }, 3, output, false), output, calls };
}

for (const mode of ["partial-exit", "timeout"]) {
  test(`Apollo ${mode} preserves partial leads and unprocessed people without a blind retry`, async (t) => {
    const checkpoint = { leads: [{ email: "kept@example.test" }], meta: {
      complete: false, stop_reason: mode === "timeout" ? "in_progress" : "quota_exhausted",
      not_enriched: 1, not_enriched_people: [{ id: "person-remaining" }],
    } };
    const error = Object.assign(new Error(mode), mode === "timeout" ? { signal: "SIGTERM", status: null } : { status: 2 });
    const f = loadSource(t, checkpoint, error);
    const result = await f.run();
    assert.equal(result.leads[0].email, "kept@example.test");
    assert.equal(result.meta.complete, false);
    assert.equal(result.meta.not_enriched_people[0].id, "person-remaining");
    assert.equal(f.calls.length, 1);
    const args = f.calls[0].args;
    assert.equal(args[args.indexOf("--time-budget-ms") + 1], "90000");
    assert.equal(f.calls[0].options.timeout, 120000);
    const retained = JSON.parse(fs.readFileSync(f.output));
    assert.equal(retained.meta.not_enriched_people[0].id, "person-remaining");
    assert.equal(retained.meta.complete, false);
  });
}

test("empty completed source is distinct from failed or malformed source", async (t) => {
  const empty = loadSource(t, { leads: [], meta: { complete: true, stop_reason: "complete" } });
  assert.equal((await empty.run()).meta.complete, true);
  const failure = loadSource(t, undefined, Object.assign(new Error("child failed"), { status: 1 }));
  await assert.rejects(failure.run(), /no valid result checkpoint/);
  const malformed = loadSource(t, { leads: [] });
  await assert.rejects(malformed.run(), /no valid result checkpoint/);
});

test("a retained incomplete source blocks another implicit paid query", (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "egbe-apollo-recovery-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const { pendingApolloSource } = require("../replenish-leads");
  const file = path.join(root, "leads-old.json");
  fs.writeFileSync(file, JSON.stringify({ leads: [{ email: "kept@example.test" }],
    meta: { complete: false, stop_reason: "uncertain_enrichment", not_enriched: 2 } }));
  const pending = pendingApolloSource(root);
  assert.equal(pending.path, file);
  assert.equal(pending.complete, false);
  assert.equal(pending.stop_reason, "uncertain_enrichment");
  fs.writeFileSync(file, JSON.stringify({ leads: [], meta: { complete: true, stop_reason: "complete" } }));
  assert.equal(pendingApolloSource(root), null);
});
