---
name: egbe-os-product-market-research
description: Collect and analyze product-market evidence for a bounded research assignment, with source provenance and resumable execution.
metadata:
  egbe-when: "Use for scoped customer, competitor, demand, channel or economic evidence collection and analysis."
  egbe-visible: "true"
  egbe-title: "Market research"
  egbe-description: "Collect reliable market evidence and answer the project's research question."
  egbe-category: "Product & design"
---

<!-- egbe-mcp-connection:v1 -->
This skill was delivered through the Egbe MCP connection. Make every Egbe API
call it describes with the `egbe_request` tool: pass the HTTP method, the API
path (for example `/me/limits`), query parameters in `query` and the JSON body
in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Read a referenced file with
`egbe_skill(name=<skill>, resource=<relative path>)`.

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs the standard workspace setup. In a persistent
project workspace that is not set up yet, call `egbe_local_setup` and follow it.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


# Product Market Research

Execute a bounded research assignment prepared from the user's task and relevant
project evidence. The calling method owns the question: Market and acquisition
for a market decision, Product for a value or diagnosis question, or the current
task for a narrow operation. It owns sufficient depth, comparative criteria and the
next business decision. PMR owns reliable collection, source integrity and the
requested analysis. Comparing, synthesizing, ranking and conditional conclusions
are allowed within the assignment; they are not authority to choose a new goal,
test, budget or approval policy.

The assignment states the question, relevant known evidence, consequential gaps,
requested result and applicable constraints. For substantial research, use its
brief at `egbe-docs/research/<id>/brief.md`; a narrow operation can use existing
task text or explicit CLI inputs. No fixed headings or full questionnaire are
required. Clarify missing operational inputs within that question, without
choosing a new product strategy. Reuse evidence and collect only the missing work.
The caller need not know an internal workflow ID. Select the operations that
serve the question; their real input dependencies, not a fixed catalog sequence,
determine execution order. Finishing a section does not stop the surrounding task.

## Choose the operation

Find available sections and their contracts in
[references/catalog.v1.json](references/catalog.v1.json); read only the selected
workflows and [research artifact contract](references/contracts/research-artifacts.md).

- For provider-backed narrative research, use the section's bundled OS Research
  runner with `--assignment "bounded question and scope"` or
  `--assignment-file <existing-task-text>`. Its evidence prompt does not replace
  the task. The deterministic query preserves selected context, assignment and
  receipt-backed supporting evidence.
- For measurements (keywords, competitors, ad libraries, creative/funnel data,
  reviews, communities and comparable fleet results), use the corresponding
  bundled adapters. Their CLI inputs bound collection. Keep raw observations,
  dates, native scope, units, identity/relevance decisions and coverage separate
  from hypotheses about effectiveness.
- Geography Comparison applies the requested comparison to validated existing
  inputs, using its publisher. It has no code-owned country score and does not
  implicitly start other research.
- Organic Trend Watch uses its dedicated skill and the provider-safe context
  builder named by its workflow. Do not duplicate that runtime.
- [Local research](references/workflows/local-research.md) explains research IDs,
  resume and optional multi-section publication.
- [Preview](references/workflows/preview.md) and
  [recommendation serialization](references/workflows/recommendations.md) are
  available when that output is requested. A narrow investigation does not
  require the complete recommendation/preview package.

## Execution and handoff

Work from the prepared assignment; choose one stable `EGBE_RESEARCH_ID` and
preserve its execution state. Do not modify the PRD. Pass `--context-file` only
for deliberately selected provider-safe context needed beyond the assignment or
operation inputs. Supply its relevant contents, not local links an external
researcher cannot read. Do not sweep the repository, chat, profile, env or personal
notes into a request. The shared input snapshot retains what was used for resume;
only declared, validated upstream evidence is added by the operation.
The OS gateway, metered starts, cumulative limits, cache keys, timeout/retry
journals and source-specific access restrictions remain authoritative.

Preserve the actual request, response, raw evidence and receipt hashes. Reuse
a matching completed response or resume its known job. Changed task or prompt
inputs are not the same research question: the runner preserves the old work
and requires a separate research ID before a new paid submission. A skill
update alone never warrants a paid rerun; prior evidence remains usable for
what it actually investigated. Complete the bounded transport-truncation review
for OS Research responses; uncertainty never triggers an extra submission.

Follow the lifecycle/funnel contracts for authorized signup or form actions,
stable aliases, uncertain outcomes and privacy. No research assignment grants
additional authority to submit forms, launch campaigns or spend beyond scope.

Hand off the relevant findings, sources, coverage and unresolved questions from
the existing research artifacts. Their receipts remain evidence provenance, not
a requirement to produce a preview or a new product-definition input file.
Link findings into the caller's current requirements or plan; do not copy a new
master report between stages.
