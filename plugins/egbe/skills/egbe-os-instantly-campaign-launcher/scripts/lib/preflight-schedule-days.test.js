#!/usr/bin/env node
// Runtime tests for mapDays — the run-spec schedule days become Instantly's
// numeric day map ("0" = Sunday … "6" = Saturday). Numeric keys without "0"
// or "1" (e.g. {"2": true, "3": true}) used to fall through to the day-name
// lookup and come out as all false: a campaign that never sends.
//
// Run: node scripts/lib/preflight-schedule-days.test.js

const fs = require("node:fs");
const path = require("node:path");

const SOURCE = fs.readFileSync(
  path.resolve(__dirname, "..", "launch-campaign.js"),
  "utf8",
);
const block = SOURCE.match(/function mapDays\b[\s\S]*?\n\}\n/);
if (!block) throw new Error("could not extract mapDays");
const mapDays = new Function(`${block[0]}\nreturn mapDays;`)();

let failed = 0;
function check(name, cond, ...detail) {
  if (cond) {
    console.log(`OK   ${name}`);
  } else {
    console.error(`FAIL ${name}`, ...detail);
    failed += 1;
  }
}
const asList = (days) =>
  [0, 1, 2, 3, 4, 5, 6].filter((d) => days[d] === true || days[String(d)] === true).join(",");

check("undefined stays undefined", mapDays(undefined) === undefined);
check(
  "day names map to numeric keys",
  asList(mapDays({ monday: true, tuesday: true, wednesday: true, thursday: true, friday: true })) ===
    "1,2,3,4,5",
);
check(
  "numeric keys without 0/1 are kept (Tue–Thu)",
  asList(mapDays({ 2: true, 3: true, 4: true })) === "2,3,4",
  mapDays({ 2: true, 3: true, 4: true }),
);
check(
  "numeric string keys without 0/1 are kept",
  asList(mapDays({ "5": true, "6": false })) === "5",
);
check(
  "full numeric map unchanged",
  asList(mapDays({ 0: false, 1: true, 2: true, 3: true, 4: true, 5: true, 6: false })) ===
    "1,2,3,4,5",
);
check(
  "numeric map always has all seven days as booleans",
  JSON.stringify(mapDays({ 3: true })) ===
    JSON.stringify({ 0: false, 1: false, 2: false, 3: true, 4: false, 5: false, 6: false }),
  mapDays({ 3: true }),
);

if (failed > 0) {
  console.error(`\n${failed} check(s) failed`);
  process.exit(1);
}
console.log("\nAll preflight-schedule-days checks passed");
