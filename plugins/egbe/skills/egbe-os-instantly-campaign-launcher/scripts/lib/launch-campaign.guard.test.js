#!/usr/bin/env node
// Regression guard: launch-campaign.js must build the Instantly sequence
// payload via explicit per-field mapping, never via JSON.stringify on
// spec.sequence. The run-spec template uses `"//"` keys as inline comments;
// a naive stringify would leak those into the live payload and Instantly
// would either reject or honour them as real fields. Cheap to assert.
//
// Run: node scripts/lib/launch-campaign.guard.test.js

const fs = require("node:fs");
const path = require("node:path");

const LAUNCHER = path.resolve(__dirname, "..", "launch-campaign.js");
const source = fs.readFileSync(LAUNCHER, "utf8");

const banned = [
  /JSON\.stringify\s*\(\s*spec\.sequence\s*\)/,
  /JSON\.stringify\s*\(\s*spec\.sequence\.steps\s*\)/,
];

let failed = false;
for (const pattern of banned) {
  if (pattern.test(source)) {
    console.error(
      `FAIL: launch-campaign.js contains a banned pattern: ${pattern}. ` +
        `The Instantly payload must be built by explicit per-field mapping ` +
        `so run-spec "//" comment keys cannot leak into the live request.`,
    );
    failed = true;
  }
}

if (failed) process.exit(1);
console.log("OK: launch-campaign.js sequence-stringify guard");
