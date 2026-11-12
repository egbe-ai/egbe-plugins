const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { collectFacts } = require("../conclude-campaign");

const manifest = { run_key: "run-1", campaign: { id: "campaign-1", first_launched_at: "2026-08-01T00:00:00Z" } };
const spec = { run_key: "run-1", product: { name: "Demo" }, sequence: { steps: [{ delay_days: 0 }] } };
const observedAt = "2026-08-02T00:00:00Z";
const generatedAt = "2026-08-20T00:00:00Z";
function snapshot(metrics = {}) {
  return { metrics_observed_at: observedAt, generated_at: observedAt, metrics: {
    _source: "campaign-analytics", contacted_count: 10, reply_count_unique: 1, ...metrics,
  }};
}
function collect(history, options = {}) {
  return collectFacts({ manifest: structuredClone(manifest), spec, history, generatedAt, ...options });
}

test("per-step counters stay counts without last-step interpretation or a verdict", () => {
  const result = collect([snapshot({ step_reply_counts: [9, 4, 3, 2, 0] })]);
  assert.deepEqual(result.metrics_summary.step_reply_counts, [9, 4, 3, 2, 0]);
  assert.equal(result.metrics_summary.reply_rate_pct, 10);
  for (const key of ["verdict", "verdict_reason", "lessons_learned", "next_step", "prior_runs_considered"]) {
    assert.equal(Object.hasOwn(result, key), false);
  }
});

test("latest partial snapshot remains partial and missing counts are not zero", () => {
  const latest = snapshot({ _partial: true, _source: "emails-fallback", contacted_count: 5, reply_count_unique: 0 });
  latest.metrics_observed_at = "2026-08-03T00:00:00Z";
  const result = collect([snapshot(), latest]);
  assert.equal(result.metrics_quality, "partial");
  assert.equal(result.metrics_summary.contacted, 5);
  assert.equal(result.metrics_summary.total_replies, null);
  assert.equal(result.metrics_summary.reply_rate_pct, null);
  assert.equal(result.metrics_summary.bounces, null);
  assert.equal(result.metrics_observed_at, latest.metrics_observed_at);
  assert.equal(result.generated_at, generatedAt);
});

test("disabled tracking is unavailable even with a provider zero", () => {
  const result = collect([{ ...snapshot({ open_count_unique: 0 }), open_tracking_enabled: false }]);
  assert.equal(result.metrics_summary.opens, null);
  assert.equal(result.metrics_summary.open_rate_pct, null);
  assert.ok(result.metrics_quality_details.reason_codes.includes("open_tracking_disabled"));
});

test("empty history remains unknown and never gets a packaging observation time", () => {
  const result = collect([]);
  assert.equal(result.metrics_quality, "unknown");
  assert.equal(result.metrics_observed_at, null);
  assert.equal(result.metrics_summary.contacted, null);
  assert.equal(result.metrics_summary.reply_rate_pct, null);
});

test("explicitly unavailable observation time is not replaced with packaging time", () => {
  const result = collect([{ metrics_observed_at: null, generated_at: generatedAt,
    metrics: { _source: "unavailable", _partial: true } }]);
  assert.equal(result.metrics_observed_at, null);
  assert.equal(result.metrics_quality, "unknown");
});

test("a stale snapshot and recently added cohort do not acquire sequence maturity", () => {
  const result = collect([snapshot()], {
    spec: { ...spec, sequence: { steps: [{ delay_days: 0 }, { delay_days: 90 }] } },
  });
  assert.equal(result.metrics_observed_at, observedAt);
  assert.equal(result.generated_at, generatedAt);
  assert.equal(Object.hasOwn(result, "sequence_complete"), false);
});

test("per-step counters are not borrowed from an older observation", () => {
  const result = collect([snapshot({ step_reply_counts: [1, 2] }), snapshot()]);
  assert.equal(result.metrics_summary.step_reply_counts, null);
});

test("mismatched snapshot identity is rejected", () => {
  assert.throws(() => collect([{ ...snapshot(), campaign_id: "other" }]), /identity/);
});

test("rerun last_launch_at does not invent the cumulative measurement start", () => {
  const result = collect([snapshot()], {
    manifest: { run_key: "run-1", campaign: { id: "campaign-1", last_launch_at: generatedAt } },
  });
  assert.equal(result.metrics_window.starts_at, null);
});

test("CLI packaging with --force cannot change the DB or upgrade missing quality", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "outreach-facts-"));
  try {
    fs.writeFileSync(path.join(dir, "manifest.json"), JSON.stringify(manifest));
    fs.writeFileSync(path.join(dir, "run-spec.json"), JSON.stringify(spec));
    const dbPath = path.join(dir, "outreach.db");
    fs.writeFileSync(dbPath, "sentinel: existing operational DB");
    const before = fs.readFileSync(dbPath);
    const command = spawnSync(process.execPath, [
      path.resolve(__dirname, "../conclude-campaign.js"), "--run-dir", dir, "--force",
    ], { encoding: "utf8", env: { ...process.env, OS_API_KEY: "", OS_URL: "" } });
    assert.equal(command.status, 0, command.stderr);
    const result = JSON.parse(command.stdout);
    assert.equal(result.metrics_quality, "unknown");
    assert.equal(result.metrics_observed_at, null);
    assert.deepEqual(fs.readFileSync(dbPath), before);
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(dir, "conclusion.json"))), result);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
