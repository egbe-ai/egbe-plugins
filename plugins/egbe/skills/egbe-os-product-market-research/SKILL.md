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
This skill comes with the Egbe plugin. If this project has its own installed copy
of the skill, use that copy instead. Otherwise make every Egbe API call it
describes with the Egbe connector: `egbe_read` for GET and `egbe_write` for POST,
PUT, PATCH and DELETE (with `method`). Pass the API path (for example
`/me/limits`), query parameters in `query` and the JSON body in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Where this skill sends an `Idempotency-Key` header, pass the same value as
`idempotency_key` and reuse it when retrying. A result with a `continuation`
holds one part of a long body; read the next part with `egbe_read`, the same
`path` and `business`, and that `continuation`.
Read bundled files beside this `SKILL.md`. For published skill resources on
Egbe OS, use `egbe_skill`. Follow "Files downloaded on demand" for listed downloads.

Publishing works through the connector: commit the app's files with the JSON
commit requests in `egbe-os-git` ("Without a terminal") and deploy the returned
commit SHA; no git push or workspace setup is needed. A step that needs a local
project key or a bundled script, such as a local `npx convex deploy`, needs a
set-up project workspace. In a persistent
project workspace that is not set up yet, set it up as the `egbe-setup` skill's
project setup describes.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.

If the connector's tools (`egbe_read` and the other `egbe_*` tools) are not
available, the plugin's connector is not signed in on this Claude account. Tell
the founder how to connect it, as the `egbe-setup` skill describes, rather than
saying Egbe is unavailable.

The connector's tools work even where this environment's shell cannot reach
Egbe: their calls travel through Claude, not through the shell's network. A step
that runs in the shell, such as a bundled script, a `git push` to Egbe's Git
endpoint or a deploy upload, needs the shell to reach the Egbe host
(`os.hz.egbe.dev`). If a proxy or allowlist refuses that request before Egbe
answers, for example HTTP 403 on CONNECT or curl status `000`, follow the Claude
network recovery in
`egbe_skill(name="egbe-os-quickstart", resource="references/environment.md")`:
the founder allows that host for Claude's code execution or continues in Claude
Code on their own computer. Code can also be published without the shell by
committing through the connector (`egbe-os-git`, "Without a terminal"). Until
the shell step or that commit and its deploy succeed, do not report the work as
published: a Claude Artifact or a local preview is not an Egbe deployment.


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
