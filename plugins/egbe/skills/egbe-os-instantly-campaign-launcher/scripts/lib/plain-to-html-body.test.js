#!/usr/bin/env node
// Runtime tests for plainToHtmlBody — UTM injection + markdown-link anchors.
//
// We can't import plainToHtmlBody as a module (launch-campaign.js is a CLI
// entrypoint, not exporting), so we re-implement a thin loader that pulls
// the function out of the source via Function constructor + eval-the-source-
// twice trick. Cleaner: refactor to a separate lib file. For now, copy the
// implementation by reading the file and `require`ing it after a trivial
// wrap. This keeps the test runtime real, not regex-based.
//
// Run: node scripts/lib/plain-to-html-body.test.js

const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");

const SOURCE = fs.readFileSync(
  path.resolve(__dirname, "..", "launch-campaign.js"),
  "utf8",
);

// Find addUtmTags + plainToHtmlBody + escapeHtml definitions, evaluate them
// in an isolated scope so we can test them as plain functions.
function loadFn() {
  // Match the function declarations we need; eval them in a sandbox.
  const blocks = [];
  for (const fnName of ["escapeHtml", "addUtmTags", "plainToHtmlBody"]) {
    const re = new RegExp(`function ${fnName}\\b[\\s\\S]*?\\n\\}\\n`);
    const m = SOURCE.match(re);
    if (!m) throw new Error(`could not extract ${fnName} from source`);
    blocks.push(m[0]);
  }
  const exporter = new Function(
    `${blocks.join("\n")}\nreturn { plainToHtmlBody, addUtmTags };`,
  );
  return exporter();
}

const { plainToHtmlBody, addUtmTags } = loadFn();

let failed = 0;
function check(name, cond, ...detail) {
  if (cond) {
    console.log(`OK   ${name}`);
  } else {
    console.error(`FAIL ${name}`, ...detail);
    failed += 1;
  }
}

// ---------------------------------------------------------------------------
// addUtmTags
// ---------------------------------------------------------------------------
check(
  "addUtmTags appends the canonical complete UTM tuple",
  addUtmTags("https://www.rolloo.app/", "rolloo-mid-managers-2026-04-30") ===
    "https://www.rolloo.app/?utm_source=instantly&utm_medium=email&utm_campaign=rolloo-mid-managers-2026-04-30",
  addUtmTags("https://www.rolloo.app/", "rolloo-mid-managers-2026-04-30"),
);

check(
  "addUtmTags uses & when URL already has a query string",
  addUtmTags("https://x.com/?ref=foo", "run-1").includes(
    "?ref=foo&utm_source=",
  ),
  addUtmTags("https://x.com/?ref=foo", "run-1"),
);

const overwrittenUtmOutput = addUtmTags(
  "https://x.com/?utm_source=manual&utm_medium=other&utm_campaign=old",
  "run-1",
);
check(
  "addUtmTags replaces a conflicting UTM tuple",
  overwrittenUtmOutput ===
    "https://x.com/?utm_source=instantly&utm_medium=email&utm_campaign=run-1",
  overwrittenUtmOutput,
);

check(
  "addUtmTags URL-encodes funky run_key chars",
  new URL(addUtmTags("https://x.com/", "run with space")).searchParams.get(
    "utm_campaign",
  ) === "run with space",
);

// ---------------------------------------------------------------------------
// plainToHtmlBody — bare URL display stays clean, href has UTMs
// ---------------------------------------------------------------------------
const bareOut = plainToHtmlBody(
  "Hi {{firstName}},\n\nDemo: https://www.rolloo.app/\n\nThanks",
  "rolloo-2026",
);
check(
  "bare URL: display text stays clean (no utm_source visible)",
  bareOut.includes(">https://www.rolloo.app/</a>"),
  bareOut,
);
check(
  "bare URL: href has utm_source=instantly",
  bareOut.includes('href="https://www.rolloo.app/?utm_source=instantly'),
  bareOut,
);
check(
  "bare URL: href has canonical utm_medium=email",
  bareOut.includes("utm_medium=email"),
  bareOut,
);
check(
  "bare URL: href carries run_key as utm_campaign",
  bareOut.includes("utm_campaign=rolloo-2026"),
  bareOut,
);
check(
  "bare URL: editor-native divs with explicit blank-line separators",
  bareOut.startsWith("<div>") && bareOut.includes("<div><br /></div>"),
  bareOut,
);
check(
  "bare URL: no <p> markup (Instantly CREATE collapses it to margin-less divs)",
  !bareOut.includes("<p>"),
  bareOut,
);
check(
  "bare URL: merge tokens preserved (not escaped to entities)",
  bareOut.includes("{{firstName}}"),
  bareOut,
);

// ---------------------------------------------------------------------------
// plainToHtmlBody — markdown link → anchor-text CTA
// ---------------------------------------------------------------------------
const mdOut = plainToHtmlBody(
  "Hey {{firstName}},\n\nReady? [try Rolloo free](https://www.rolloo.app/)",
  "rolloo-2026",
);
check(
  "markdown link: anchor text is the visible CTA",
  mdOut.includes(">try Rolloo free</a>"),
  mdOut,
);
check(
  "markdown link: href contains target URL with UTMs",
  mdOut.includes('href="https://www.rolloo.app/?utm_source=instantly'),
  mdOut,
);
check(
  "markdown link: square-bracket source syntax not visible in output",
  !mdOut.includes("[try Rolloo free]") && !mdOut.includes("](https"),
  mdOut,
);

// ---------------------------------------------------------------------------
// plainToHtmlBody — mixed bare + markdown in one body
// ---------------------------------------------------------------------------
const mixOut = plainToHtmlBody(
  "Read more at https://www.rolloo.app/docs and [start now](https://www.rolloo.app/signup)",
  "rolloo-2026",
);
check(
  "mixed: bare URL kept clean in display",
  mixOut.includes(">https://www.rolloo.app/docs</a>"),
  mixOut,
);
check(
  "mixed: markdown link rendered as anchor text",
  mixOut.includes(">start now</a>"),
  mixOut,
);
check(
  "mixed: both hrefs have UTMs",
  (mixOut.match(/utm_source=instantly/g) || []).length === 2,
  mixOut,
);

// ---------------------------------------------------------------------------
// Idempotency for HTML-authored bodies (markup stays intact; href is tracked)
// ---------------------------------------------------------------------------
const htmlIn =
  '<p>Hi <strong>{{firstName}}</strong>, demo: <a href="x">x</a></p>';
check(
  "relative pre-HTML anchor passes through unchanged",
  plainToHtmlBody(htmlIn, "run-1") === htmlIn,
);
const trackedHtmlIn =
  '<p>Demo: <a class="cta" href="https://rolloo.app/?utm_source=old">try it</a></p>';
const trackedHtmlOut = plainToHtmlBody(trackedHtmlIn, "run-1");
check(
  "pre-HTML HTTP anchor receives the canonical complete UTM tuple",
  trackedHtmlOut.includes(
    'href="https://rolloo.app/?utm_source=instantly&utm_medium=email&utm_campaign=run-1"',
  ),
  trackedHtmlOut,
);

// ---------------------------------------------------------------------------
// Line rendering — one <div> per line, blank lines as <div><br /></div>
// ---------------------------------------------------------------------------
check(
  "adjacent lines each get their own div (no <br> line-joins)",
  plainToHtmlBody("a\nb", "run-1") === "<div>a</div><div>b</div>",
  plainToHtmlBody("a\nb", "run-1"),
);
check(
  "blank line renders as a single explicit separator div",
  plainToHtmlBody("a\n\nb", "run-1") ===
    "<div>a</div><div><br /></div><div>b</div>",
  plainToHtmlBody("a\n\nb", "run-1"),
);
check(
  "runs of 3+ newlines collapse to one separator",
  plainToHtmlBody("a\n\n\n\nb", "run-1") ===
    "<div>a</div><div><br /></div><div>b</div>",
  plainToHtmlBody("a\n\n\n\nb", "run-1"),
);
check(
  "leading/trailing newlines don't produce stray separator divs",
  plainToHtmlBody("\na\n", "run-1") === "<div>a</div>",
  plainToHtmlBody("\na\n", "run-1"),
);

// ---------------------------------------------------------------------------
// Edge: empty body returns input as-is
// ---------------------------------------------------------------------------
check("empty body returns as-is", plainToHtmlBody("", "run-1") === "");
check(
  "whitespace-only body returns as-is",
  plainToHtmlBody("  ", "run-1") === "  ",
);

// ---------------------------------------------------------------------------
// Edge: missing run_key — UTMs skipped silently, bare URL still linkified
// ---------------------------------------------------------------------------
const noRunKey = plainToHtmlBody("see https://x.com", null);
check(
  "missing run_key: bare URL still linkified, no UTMs",
  noRunKey.includes('<a href="https://x.com">https://x.com</a>'),
  noRunKey,
);

// ---------------------------------------------------------------------------
if (failed > 0) {
  console.error(`\n${failed} check(s) failed`);
  process.exit(1);
}
console.log("\nAll plain-to-html-body checks passed");
