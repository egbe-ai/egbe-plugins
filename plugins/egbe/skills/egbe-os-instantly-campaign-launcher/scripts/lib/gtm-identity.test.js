#!/usr/bin/env node
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const {
  GTM_IDENTITY_FIELDS,
  assertStableGtmIdentifiers,
  reconcileRunIdentity,
  reconcileInstantlyAttribution,
} = require("./gtm-identity");

const identity = {
  business_id: "egbe-fleet",
  product_id: "product:pet-stickers",
  launch_id: "launch:pet-stickers:2026-08-18",
  experiment_id: "gtm:pet-stickers:instantly:01",
  variant_id: "gtm:pet-stickers:instantly:01:v1",
};

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function check(name, fn) {
  try {
    fn();
    console.log(`OK   ${name}`);
  } catch (error) {
    console.error(`FAIL ${name}`);
    throw error;
  }
}

check("new run copies stable GTM identity into the manifest", () => {
  const manifest = { run_key: "pet-stickers-email" };
  const spec = { run_key: "pet-stickers-email", ...clone(identity) };
  reconcileRunIdentity(manifest, spec);
  for (const field of GTM_IDENTITY_FIELDS) {
    assert.equal(manifest[field], identity[field]);
  }
});

check("legacy rerun is hydrated from the immutable manifest", () => {
  const manifest = { run_key: "pet-stickers-email", ...clone(identity) };
  const spec = { run_key: "pet-stickers-email" };
  reconcileRunIdentity(manifest, spec);
  for (const field of GTM_IDENTITY_FIELDS) {
    assert.equal(spec[field], identity[field]);
  }
});

for (const field of GTM_IDENTITY_FIELDS) {
  check(`conflicting ${field} fails closed`, () => {
    const manifest = { run_key: "pet-stickers-email", ...clone(identity) };
    const before = clone(manifest);
    const spec = {
      run_key: "pet-stickers-email",
      ...clone(identity),
      [field]: `${identity[field]}-different`,
    };
    assert.throws(
      () => reconcileRunIdentity(manifest, spec),
      new RegExp(`conflict for ${field}`),
    );
    assert.deepEqual(manifest, before);
  });
}

check("malformed stable IDs are rejected", () => {
  assert.throws(
    () => assertStableGtmIdentifiers({ experiment_id: 123 }, "run spec"),
    /run spec\.experiment_id/,
  );
  assert.throws(
    () =>
      assertStableGtmIdentifiers(
        { launch_id: "launch id with spaces" },
        "manifest",
      ),
    /manifest\.launch_id/,
  );
});

check("manifest records the provider ID and complete UTM tuple", () => {
  const manifest = {
    run_key: "pet-stickers-email",
    campaign: { id: "instantly-campaign-123" },
  };
  const binding = reconcileInstantlyAttribution(manifest, {
    runKey: manifest.run_key,
    campaignId: manifest.campaign.id,
    label: "manifest",
  });
  assert.deepEqual(binding, {
    provider: "instantly",
    provider_campaign_id: "instantly-campaign-123",
    utm_source: "instantly",
    utm_medium: "email",
    utm_campaign: "pet-stickers-email",
  });
  assert.equal(manifest.provider_campaign_id, manifest.campaign.id);
});

for (const [field, badValue] of [
  ["provider", "another-provider"],
  ["utm_source", "newsletter"],
  ["utm_medium", "paid"],
  ["utm_campaign", "another-run"],
]) {
  check(`conflicting ${field} attribution fails closed`, () => {
    assert.throws(
      () =>
        reconcileInstantlyAttribution(
          {
            run_key: "pet-stickers-email",
            campaign_id: "instantly-campaign-123",
            [field]: badValue,
          },
          {
            runKey: "pet-stickers-email",
            campaignId: "instantly-campaign-123",
            label: "conclusion",
          },
        ),
      new RegExp(`conflict for ${field}`),
    );
  });
}

check("CLI paths reject identity relabeling before durable writes", () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "instantly-id-test-"));
  const scriptsDir = path.resolve(__dirname, "..");
  const writeJson = (name, value) => {
    const target = path.join(tempRoot, name);
    fs.writeFileSync(target, `${JSON.stringify(value, null, 2)}\n`);
    return target;
  };
  try {
    const manifestPath = writeJson("manifest.json", {
      run_key: "stable-run-key",
      ...identity,
      campaign: { id: "campaign-123" },
    });
    const originalManifest = fs.readFileSync(manifestPath, "utf8");
    const runSpecPath = writeJson("run-spec.json", {
      run_key: "stable-run-key",
      ...identity,
      experiment_id: "gtm:conflicting-experiment",
      leads_file: "leads.json",
      sequence: { steps: [{ subject: "hello", body: "hello" }] },
    });
    const launch = spawnSync(
      process.execPath,
      [path.join(scriptsDir, "launch-campaign.js"), "--run-spec", runSpecPath],
      { encoding: "utf8", env: { ...process.env, OS_URL: "", OS_API_KEY: "" } },
    );
    assert.notEqual(launch.status, 0);
    assert.match(launch.stderr, /conflict for experiment_id/);
    assert.equal(fs.readFileSync(manifestPath, "utf8"), originalManifest);
    assert.equal(fs.existsSync(path.join(tempRoot, ".env")), false);
    assert.equal(fs.existsSync(path.join(tempRoot, "outreach.db")), false);

    writeJson("run-spec.json", {
      run_key: "stable-run-key",
      ...identity,
      sequence: { steps: [{ delay_days: 0 }] },
    });
    const conclusionPath = writeJson("conclusion.json", {
      run_key: "stable-run-key",
      ...identity,
      provider: "instantly",
      provider_campaign_id: "campaign-999",
      campaign_id: "campaign-999",
      utm_source: "instantly",
      utm_medium: "email",
      utm_campaign: "stable-run-key",
    });
    const originalConclusion = fs.readFileSync(conclusionPath, "utf8");
    const conclude = spawnSync(
      process.execPath,
      [path.join(scriptsDir, "conclude-campaign.js"), "--run-dir", tempRoot, "--force"],
      { encoding: "utf8" },
    );
    assert.notEqual(conclude.status, 0);
    assert.match(conclude.stderr, /conflict for provider_campaign_id/);
    assert.equal(fs.readFileSync(conclusionPath, "utf8"), originalConclusion);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});

console.log("\nAll GTM identity checks passed");
