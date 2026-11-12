#!/usr/bin/env node
// Runtime tests for excludeProtectedSenders — cold outreach must never send
// from a trust-reputation domain (@egbe.app / @egbe.dev), GH #752.
//
// Run: node scripts/lib/no-egbe-cold-sender.test.js

const fs = require("node:fs");
const path = require("node:path");

const SOURCE = fs.readFileSync(
  path.resolve(__dirname, "..", "launch-campaign.js"),
  "utf8",
);

function loadFns() {
  // Extract the contiguous guard block: the BLOCKED_SENDER_DOMAINS constant
  // through the end of excludeProtectedSenders().
  const block = SOURCE.match(
    /const BLOCKED_SENDER_DOMAINS[\s\S]*?\nfunction excludeProtectedSenders[\s\S]*?\n\}\n/,
  );
  if (!block) throw new Error("could not extract sender guard from source");
  const exporter = new Function(
    `let __failed = null;
     function fail(msg) { __failed = msg; throw new Error("__guard_fail__"); }
     function normalizeEmail(e) { return String(e || "").trim().toLowerCase(); }
     const console = { error() {} };
     ${block[0]}
     return {
       excludeProtectedSenders,
       isBlockedSender,
       lastFailure: () => __failed,
       resetFailure: () => { __failed = null; },
     };`,
  );
  return exporter();
}

const { excludeProtectedSenders, isBlockedSender, lastFailure, resetFailure } =
  loadFns();

let failed = 0;

function check(name, cond) {
  if (cond) {
    console.log(`OK   ${name}`);
  } else {
    console.error(`FAIL ${name}`);
    failed += 1;
  }
}

function expectFail(name, entries, expectedSubstring) {
  resetFailure();
  try {
    excludeProtectedSenders(entries);
    console.error(`FAIL ${name} — should have rejected, didn't`);
    failed += 1;
    return;
  } catch (err) {
    if (err.message !== "__guard_fail__") throw err;
  }
  const msg = lastFailure() || "";
  check(name, msg.includes(expectedSubstring));
}

// Blocked-domain detection (strings and account objects).
check("egbe.app string is blocked", isBlockedSender("milo.brooks@egbe.app"));
check("egbe.dev string is blocked", isBlockedSender("notify@egbe.dev"));
check("mixed case blocked", isBlockedSender("Ronan.Westcott@EGBE.APP"));
check("account object blocked", isBlockedSender({ email: "x@egbe.app" }));
check(
  "cold domain not blocked",
  !isBlockedSender("jack@smartcreateinc.org"),
);
check(
  "lookalike not blocked (not egbe.app itself)",
  !isBlockedSender("a@notegbe.app.com"),
);

// Filtering keeps only cold-domain senders.
const mixed = ["milo.brooks@egbe.app", "jack@smartcreateinc.org", "n@egbe.dev"];
const kept = excludeProtectedSenders(mixed);
check("filters egbe.* out, keeps cold domain",
  kept.length === 1 && kept[0] === "jack@smartcreateinc.org");

const objs = [
  { email: "ronan.westcott@egbe.app", first_name: "R" },
  { email: "tyler@smartcreateinc.org", first_name: "T" },
];
const keptObjs = excludeProtectedSenders(objs);
check(
  "preserves account objects for allowed senders",
  keptObjs.length === 1 && keptObjs[0].email === "tyler@smartcreateinc.org",
);

// Hard-fail when nothing but trust-domain senders are supplied.
expectFail(
  "all egbe.app -> hard fail pointing at cold domain",
  ["milo.brooks@egbe.app", "ronan.westcott@egbe.app"],
  "dedicated cold domain",
);
expectFail("single egbe.dev only -> hard fail", ["notify@egbe.dev"], "cold domain");

if (failed > 0) {
  console.error(`\n${failed} check(s) failed`);
  process.exit(1);
}
console.log("\nAll no-egbe-cold-sender checks passed");
