# Keyword Economics

Read `../contracts/research-artifacts.md` and the prepared assignment (plus the
recommendation artifact when relevant). This section uses NO OS Research job
and no free-form web research: every number comes from metered DataForSEO
calls made by the bundled deterministic runner, and the section body plus its
machine-readable evidence file are rendered by that runner. Do not write or
edit section prose, tables, or the evidence file by hand.

## 1. Use the assigned search scope

Supply the nonempty phrase list relevant to the caller's question, using the
assignment's evidence and explicitly supplied scope as context. There is no required
number of phrases or mix of category/problem/purchase language. The runner
measures each candidate and records exclusions and coverage; observed search
volume is not by itself product-fit or willingness-to-pay evidence. Named
competitor domains may be supplied as seed domains.

Translate the assignment's geography and language to Google Ads location and
language codes and pass them explicitly. If locale is unresolved, establish the
scope before a paid query; the runner's US/en defaults are not a market choice.
For several countries, invoke the runner once per country. Locale files live at
`egbe-docs/research/market/evidence/keyword-economics/<location>-<language>.json`;
the stable aggregate and report retain all current locales. Rerunning one locale
does not replace another. Compare locale inputs before combining them; changed
selected context does not authorize new collection or make old observations
false. Preserve saved evidence and review applicability rather than blending
different research scopes or silently refreshing paid data.

## 2. Run the deterministic runner

From the workspace root, resolve `<skill-root>` to the extracted directory
containing this skill's `SKILL.md`, then run:

```bash
python3 <skill-root>/scripts/run-keyword-economics.py \
  --workspace . \
  --seed-keywords "<phrase one>, <phrase two>, <phrase three>, ..." \
  --seed-domains "<competitor.com, other.com — omit flag when none>" \
  --location-code 2840 \
  --language-code en
```

The runner needs `OS_API_KEY` (and optional `OS_URL`) in the environment. It
expands seeds through Google Ads keyword data, probes the results page for the
top head keywords (who ranks organically, who pays in the ads block), confirms
  candidate competitors from that demand surface, confirms only those with
  category-relevant SERP evidence (or preserves founder-named domains as
  hypotheses), pulls each confirmed domain's ranked-keyword footprint,
  reports provider forecast estimates, optionally scales them to a supplied
`--test-budget-usd` scenario, and then:

- writes evidence rows to `egbe-docs/research/market/evidence/keyword-economics.json`;
- materializes the exact section under `## Keyword economics` in
  `egbe-docs/research/market/full-report.md`;
- verifies the report and evidence together; Git remains caller-owned;
- records the completed state receipt under
  `egbe-docs/research/market/work/keyword_economics/`.

Every upstream response is cached in the runtime directory, so re-running the
same command replays cached data instead of spending the metered budget again.
The default forecast covers all eligible seed/expansion candidates up to 1000,
not a fixed five keywords. Coverage records requested/submitted keywords,
exclusions and cap omissions. It is an exploratory exact-match scenario, not an
approved campaign, total reachable demand or a live starting bid. Aggregate
provider responses describe the set once. US/UK budgets are alternative
comparisons, not additive allocations. Null/empty forecasts are unavailable,
not zero demand; budget-scaled clicks are conditional arithmetic.

For an explicitly chosen homogeneous scenario, pass `--scenario <file.json>`:

```json
{"keywords":["example service","example pricing"],"location_code":2840,"language_code":"en","match":"phrase","bid":2.5,"rationale":"Bounded exploratory bid assumption","source":"Caller-selected scenario"}
```

The locale must match the run; one match type and one positive bid (up to 500)
apply to at most 1000 unique keywords. Mixed per-keyword bids/matches cannot be
represented faithfully by this endpoint; do not silently flatten campaign
assets into a forecast. The scenario never changes a live campaign.
The evidence adds a bounded `intent_signal` to keyword and SERP rows. It is a
lexical clue (`vendor_seeking`, `tool_seeking`, `informational`, `job_seeking`,
`free_intent`, or `unknown`), not an offer-fit or campaign-selection verdict.
Google Ads must compare it with the actual product offer before selecting paid
keywords. An ambiguous AEO/GEO query cannot alone confirm a competitor.

## 3. On failure

Provider rate limits and recognized internal DataForSEO errors explicitly
confirmed as unpaid are handled inside the runner: it logs the failure and
retries the unchanged request with bounded backoff. Do not add manual waits or
retry wrappers around it. An internal error is not proof of valid input or a
guarantee of recovery. Validation errors need corrected input; unknown billing
status is not safe to retry automatically.

If the runner reports exhausted retries, the section is blocked, not completed.
Preserve the workspace and report the failed operation, provider code and task
ID (when available), and that automatic retries were exhausted. Do not hide the
failure by skipping evidence or declaring the research complete. A later
recovery attempt can rerun the same command using its cached successful
responses; use the caller's recovery mechanism rather than starting an
unbounded manual loop.

If the runner
reports that no seed survived volume validation, report the measured coverage. Expand or change the assigned phrase list only
when that remains within the caller's requested scope and collection budget. For
any other failure, preserve the runtime state and stop; a later attempt
resumes from cache. Do not substitute Brave search, generic OS Research,
Apify, direct provider access, or an agent-written result, and do not edit
`egbe-docs/research/market/full-report.md` or the evidence file manually. Completion is
validated deterministically from the runtime receipt; this section has no
LLM-based Research Completion Review step.
Old single-locale evidence is not silently migrated. Preserve it and use a new
workspace with the current bundle when the runner reports an unsupported format.
