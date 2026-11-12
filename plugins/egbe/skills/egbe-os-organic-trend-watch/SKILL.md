---
name: egbe-os-organic-trend-watch
description: Research TikTok and Instagram Reels evidence, compare formats and audience responses, and propose grounded creative adaptations for a product.
metadata:
  egbe-when: "Offer when a new or existing product needs short-video evidence to assess an acquisition hypothesis or improve content."
  egbe-visible: "true"
  egbe-title: "Short-video research"
  egbe-description: "Research TikTok and Instagram Reels examples and audience responses, then adapt useful ideas to your product."
  egbe-category: "Marketing & growth"
---

<!-- egbe-mcp-connection:v1 -->
This skill comes with the Egbe plugin. Make every Egbe API call it describes with
the Egbe connector's `egbe_request` tool: pass the HTTP method, the API path (for
example `/me/limits`), query parameters in `query` and the JSON body in `body`.
For these calls leave out `OS_URL`, the Authorization header, `.env.local` and
`egbe-curl.py`, and skip catalog update checks; the connection authenticates and
identifies the request.
Also pass the `business` that `egbe_setup` returned. Files this skill refers to
are next to this `SKILL.md`, except any listed under "Files downloaded on demand".

A step that needs a local project key, such as a git push or a local deploy
command, works only in a persistent project workspace. There, if the project's
Git-ignored `.env.local` has no `OS_API_KEY` yet, call `egbe_local_setup` once
and save its `OS_URL` and `OS_API_KEY` there, preserving other entries. Use only
those two values: the plugin already provides Egbe's skills, so do not install
the Egbe catalog or follow the rest of that result. Never show the key in chat or
put it in logs, commits or URLs. Without such a workspace, tell the founder that
this step needs an agent with a project folder, and continue with the rest of
the work.


# Organic Trend Watch

Answer a scoped research question using collected TikTok/Reels observations.
Compare what the sources actually show, explain uncertainty, and propose
product-relevant adaptations. This skill does not publish videos or measure
the product's resulting conversions. It can run independently or supply a
Product Market Research section; it is not a pre-PRD prerequisite.

## Establish the assignment

Use the question, product/audience context and available evidence. Missing
market-research sections do not block direct use. Keep founder identity and
unrelated personal details out of provider inputs.

Use the product repository and `EGBE_RESEARCH_ID` (default `market`). Resolve
the installed skill separately from the mutable study directory:

```bash
ORGANIC_TREND_SKILL_ROOT=/absolute/path/to/the-directory-containing-this-SKILL.md
WORKSPACE_ROOT=/absolute/path/to/the-product-repository
RUNTIME_ROOT="$WORKSPACE_ROOT/egbe-docs/research/market/work/organic_trend_watch"
```

Keep execution artifacts below that study's `work/organic_trend_watch/`; replace
`market` in examples when using another study ID. Never work inside the installed
skill. Read [runtime-contract.md](references/runtime-contract.md) for context,
state and resume rules, then [collection-and-analysis.md](references/collection-and-analysis.md)
for the execution sequence.

## Collect and interpret

Use `OS_URL` and `OS_API_KEY` through the bundled provider adapters. Read
[provider-contract.md](references/provider-contract.md) before paid collection.
Bound the requested source/sample scope to the assignment and available budget;
save asynchronous handles and resume them instead of duplicating paid runs.

Read [analysis-and-adaptation.md](references/analysis-and-adaptation.md) before
interpreting evidence. Captions, metrics, comments, transcripts and frames support
different claims. A caption is not a viewed opening frame; a high view count is
not proof that a format caused performance. Keep source claims distinct from
claims the product can substantiate.

The bundled media analyzer supplies content-bound receipts for visual/verbal
claims; [visual-analysis-prompt.md](references/visual-analysis-prompt.md) defines
its extraction scope. Missing media may leave useful caption, metric or comment
evidence. Record the gap rather than inventing an analysis or treating limited
coverage as complete.

## Return a traceable result

Write `analysis.json` using [output-contract.md](references/output-contract.md).
The renderer produces `result.md`; the finalizer seals its evidence, coverage and
collection time in `receipt.json`. Do not hand-author either generated file.
Return the result and its limitations, with source-backed findings and feasible
adaptations where supported. Empty findings are valid when evidence is thin.

For PMR, return the validated result to its finalizer; do not edit the combined
report or publish a competing section. For direct use, present the same result
without requiring a PMR report. Business choices, launch plans and ongoing
evaluation remain outside this collection's receipt.
