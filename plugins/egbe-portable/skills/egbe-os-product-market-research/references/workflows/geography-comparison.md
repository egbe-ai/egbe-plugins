# Geography comparison

Read `../contracts/research-artifacts.md`, the prepared assignment, and the recommendation
reason when present. This selected workflow compares plausible markets for the
**next test**; it does not change the founder's chosen market, PRD or campaigns.
It can also run standalone after launch. Do not start another research section.

## Assignment and source scope

Use the question, country scope and criteria from the project method/current
task. Comparison and conditional recommendations are allowed; do not choose
a new business goal or assume authority to change a launch market. Preserve
explicit founder constraints separately from preferences or evidence.

## Reuse evidence, then fill assigned gaps

From the workspace root, resolve `<skill-root>` to this extracted bundle:

```bash
python <skill-root>/scripts/geography-comparison.py --workspace . --prepare
```

Pass `--context-file <selected-context>` when the comparison needs provider-safe
background beyond the explicit assignment; do not pass unrelated project material.

Read `egbe-docs/research/market/work/geography_comparison/context.json`. The command returns
its SHA-256 for the comparison input. It includes only receipt-validated public
research as usable evidence; failed and unavailable sections remain explicit
gaps. Valid prior research can be reused even if it is not selected for new
collection. It makes no provider calls. Re-running refreshes changed inputs
and invalidates old completion; unchanged context resumes without recollection.
Keep prior search results/notes under this section's runtime directory for reuse.

Compare the assigned criteria using compatible measurement definitions and
reference periods. Unknown cells stay unknown. Do not combine overlapping
populations, incomparable CPCs or independent budget scenarios.

For gaps relevant to the assigned question, read the live OS `/search/skill` and
use targeted `POST /search/web/brave` queries per country and question, including
local-language queries and relevant official domains. Read original pages before
using decisive facts; snippets are discovery leads. Use available page-reading
tools; where extraction needs OS, discover `/scrape/skill` and use a bounded
actor only within the authorized budget. Do not invent a fetch endpoint or
use direct provider keys. Save source links, dates/periods and material excerpts.

Agree with or stay within the caller's research budget. Search the narrowest
decisive gaps first and stop when another query is unlikely to change the next
test, or the budget is reached. If budget/sources are insufficient, publish an
uncertain comparison with a concrete next check. Do not run every PMR section
for every country or send one giant "compare 12 markets" OS Research request.
This workflow is agent-led synthesis, not another OS Research job; do not create
a fake job ID or perform the OS Research Completion Review.

Brave search regions are not arbitrary ISO countries; follow the search skill's
country guidance. Places is optional discovery of local companies, never a
complete company count. Perplexity is not a prerequisite or an automatic fallback.
Provider failures are limitations, not evidence against a country; preserve
successful work and do not repeatedly spend to fill every cell.

## Compare and publish

Write a temporary input JSON using
[`../contracts/geography-comparison.md`](../contracts/geography-comparison.md).
Keep claims and interpretation separate. Prefer original regulators/registries,
transparent datasets and product outcomes; vendor material is interested
evidence. Preserve the same measurement definitions and reference periods.

When the assignment asks for a recommendation, explain it conditionally and
what could change it. Otherwise keep both recommendation country fields null
and report the comparison. Do not claim approval or rewrite launch geography.

```bash
python <skill-root>/scripts/geography-comparison.py --workspace . \
  --input <temporary-comparison.json>
```

The helper validates structure/references, renders only `## Geography comparison`
in `egbe-docs/research/market/full-report.md`, and publishes the accompanying analysis at
`egbe-docs/research/market/evidence/geography-comparison.json`. It marks completion only
after publication; it cannot establish whether the agent's judgment is correct.
Publication materializes and verifies local files; Git belongs to the caller's
normal project workflow. A receipt does not claim a commit or remote publication.
Retry a failed publication with the same input; do not repeat searches. If inputs
changed, prepare again and review the comparison against the refreshed context.
