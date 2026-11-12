#!/usr/bin/env node
// Runtime tests for preflightCtaUrls — catches placeholder URLs in step bodies
// before the launcher creates a campaign in Instantly.
//
// Run: node scripts/lib/cta-url-preflight.test.js

const fs = require("node:fs");
const path = require("node:path");

const SOURCE = fs.readFileSync(
  path.resolve(__dirname, "..", "launch-campaign.js"),
  "utf8",
);

// Extract preflightCtaUrls + URL_PLACEHOLDER_PATTERNS from the source so we
// can call it as a plain function. We replace the real `fail()` (which calls
// process.exit) with a captured-error shim so the test runs in-process.
function loadFn() {
  const patternsBlock = SOURCE.match(
    /const URL_PLACEHOLDER_PATTERNS = \[[\s\S]*?\];\n/,
  );
  const fnBlock = SOURCE.match(/function preflightCtaUrls\b[\s\S]*?\n\}\n/);
  if (!patternsBlock || !fnBlock) {
    throw new Error("could not extract preflightCtaUrls from source");
  }
  const exporter = new Function(
    `let __failed = null;
     function fail(msg) { __failed = msg; throw new Error("__preflight_fail__"); }
     ${patternsBlock[0]}
     ${fnBlock[0]}
     return {
       preflightCtaUrls,
       lastFailure: () => __failed,
       resetFailure: () => { __failed = null; },
     };`,
  );
  return exporter();
}

const { preflightCtaUrls, lastFailure, resetFailure } = loadFn();

let failed = 0;
function expectPass(name, spec) {
  resetFailure();
  try {
    preflightCtaUrls(spec);
    console.log(`OK   ${name}`);
  } catch (err) {
    if (err.message === "__preflight_fail__") {
      console.error(`FAIL ${name} — preflight rejected: ${lastFailure()}`);
      failed += 1;
    } else {
      throw err;
    }
  }
}

function expectFailMatch(name, spec, expectedSubstring) {
  resetFailure();
  try {
    preflightCtaUrls(spec);
    console.error(`FAIL ${name} — preflight should have rejected, didn't`);
    failed += 1;
    return;
  } catch (err) {
    if (err.message !== "__preflight_fail__") {
      throw err;
    }
  }
  const msg = lastFailure() || "";
  if (msg.includes(expectedSubstring)) {
    console.log(`OK   ${name}`);
  } else {
    console.error(
      `FAIL ${name} — rejected but message lacked "${expectedSubstring}". Got: ${msg}`,
    );
    failed += 1;
  }
}

// ---------------------------------------------------------------------------
// Should PASS — real product URLs
// ---------------------------------------------------------------------------
expectPass("real .app domain passes", {
  sequence: {
    steps: [
      { subject: "demo", body: "Try [Rolloo free](https://www.rolloo.app/)" },
      { subject: "follow up", body: "Reminder: https://www.rolloo.app/" },
    ],
  },
});
expectPass("real *.n.egbe.app deployment URL with real instance-id passes", {
  sequence: {
    steps: [
      {
        subject: "demo",
        body: "Demo at https://rolloo.0e49b60.n.egbe.app/ — see for yourself.",
      },
    ],
  },
});
expectPass("URL with query string passes", {
  sequence: {
    steps: [{ subject: "x", body: "https://pitchmode.org?ref=email&v=2" }],
  },
});

// ---------------------------------------------------------------------------
// Should FAIL — angle-bracket placeholders
// ---------------------------------------------------------------------------
expectFailMatch(
  "<instance-id> placeholder rejected",
  {
    sequence: {
      steps: [
        {
          subject: "demo",
          body: "Visit https://<slug>.<instance-id>.n.egbe.app/",
        },
      ],
    },
  },
  "step 1",
);
expectFailMatch(
  "<your-product> placeholder rejected",
  {
    sequence: {
      steps: [{ subject: "x", body: "Try https://<your-product>.com/" }],
    },
  },
  "step 1",
);

// ---------------------------------------------------------------------------
// Should FAIL — literal '.instance-id.' subdomain (no brackets) — the
// real-world Estimate Nudge case
// ---------------------------------------------------------------------------
expectFailMatch(
  "literal .instance-id. subdomain rejected (Estimate Nudge case)",
  {
    sequence: {
      steps: [
        {
          subject: "demo",
          body: "https://estimate-nudge.instance-id.n.egbe.app/",
        },
      ],
    },
  },
  "instance-id",
);

// ---------------------------------------------------------------------------
// Should FAIL — example.com / example.org / *.example placeholder
// ---------------------------------------------------------------------------
expectFailMatch(
  "https://example.com/demo rejected",
  {
    sequence: {
      steps: [{ subject: "x", body: "demo: https://example.com/demo" }],
    },
  },
  "example",
);
expectFailMatch(
  "https://example.org rejected",
  {
    sequence: { steps: [{ subject: "x", body: "https://example.org" }] },
  },
  "example",
);
expectFailMatch(
  "*.example placeholder (https://bike-ad-tracker.example) rejected",
  {
    sequence: {
      steps: [{ subject: "x", body: "https://bike-ad-tracker.example" }],
    },
  },
  "example",
);

// ---------------------------------------------------------------------------
// Should FAIL — your-product / your-domain literals
// ---------------------------------------------------------------------------
expectFailMatch(
  "your-product literal rejected",
  {
    sequence: {
      steps: [{ subject: "x", body: "https://your-product.com/" }],
    },
  },
  "your-",
);

// ---------------------------------------------------------------------------
// Should FAIL — placeholder in subject line, not body
// ---------------------------------------------------------------------------
expectFailMatch(
  "placeholder in subject is also caught",
  {
    sequence: {
      steps: [{ subject: "ping <your-product>", body: "https://rolloo.app/" }],
    },
  },
  "step 1",
);

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------
expectPass("empty sequence skipped (no offenses)", { sequence: { steps: [] } });
expectPass("missing sequence skipped (no offenses)", {});
expectPass("URL containing 'example' but not as placeholder passes", {
  sequence: {
    steps: [
      // 'examples' as part of a real path, not 'example.com' or '*.example' — passes.
      { subject: "x", body: "https://docs.rolloo.app/examples/quickstart" },
    ],
  },
});

if (failed > 0) {
  console.error(`\n${failed} check(s) failed`);
  process.exit(1);
}
console.log("\nAll cta-url-preflight checks passed");
