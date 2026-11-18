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
Files this skill refers to are next to this `SKILL.md`, except any listed under
"Files downloaded on demand".

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

## Files downloaded on demand

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project workspace; without one,
tell the founder that the step needs it and continue with the rest of the work.

In a project workspace, before a step that runs or copies one of these files,
download it into `.egbe/skills/egbe-os-organic-trend-watch/` at the same relative path, for example
`curl -fsSL <url> --create-dirs -o .egbe/skills/egbe-os-organic-trend-watch/<file>`, and check that its SHA-256
matches. Also download the files it uses from the same folder, such as the
modules a script imports. Wherever this skill names one of these files by its
path in the skill (for example `scripts/...` or `assets/...`), use `.egbe/skills/egbe-os-organic-trend-watch/<file>`;
where it writes `<skills-directory>`, use `.egbe/skills`.
Keep `.egbe/skills/` out of Git by adding it to `.gitignore`.

| File | URL | SHA-256 |
| --- | --- | --- |
| `scripts/_analysis.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/_analysis.py | `a8ef75be4523cbbb91615b234df8c1b83036295fb67b66dfc30ae1c501a4ffb8` |
| `scripts/_contract.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/_contract.py | `2f196b3144d5cae3c93b6a450ce6135e0e4d2987fd3699db4d8f77d10cafd8fe` |
| `scripts/_provider_inputs.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/_provider_inputs.py | `71ef58c3f9a078d49b13cec5f5f0e69c637000b8e331734a673f1752015420d5` |
| `scripts/analyze-visual-evidence.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/analyze-visual-evidence.py | `5326aa20340d4b1e416c82d5dd6dc2537f26f8d7ec0d5eeaca3c791319cdd81a` |
| `scripts/build-provider-inputs.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/build-provider-inputs.py | `1ca0cb56dcf3c7f53b7c9141fd34508d3e36c1cb23721d4876a7b906358a5edf` |
| `scripts/connection_identity.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/connection_identity.py | `32851ccf3431289e470cd83c5ec649515cafe374a589a38beae353e167e726b5` |
| `scripts/egbe_artifacts.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/egbe_artifacts.py | `292df7b2d1b0863d9bed85d166ba66e6798ebc66b90ec0a3c89d018102ddbe3a` |
| `scripts/finalize-receipt.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/finalize-receipt.py | `94cfa0fb682ae3197a34186eaf6b8678e0b4c96cc6a24a860458a653677e6963` |
| `scripts/normalize-videos.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/normalize-videos.py | `2f1d82e70f4091e78f13828a30afcc117dd87d53e0bc1d1f56349e6e3f12ca4c` |
| `scripts/prepare-visual-evidence.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/prepare-visual-evidence.py | `0c8927adc0a2792fc0ca90c79fa246dbb1c64e9fc9bf54673179bf71afdf1b76` |
| `scripts/render-result.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/render-result.py | `f909f1f3c9d715cda346d0ceead312453c28b3cd5c57acf03f60513c42ef00fb` |
| `scripts/run-apify.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/run-apify.py | `d4591c8be01c86e183dabb346d15be12baa4f54dd2e6b22dcfd57a4ff615ee06` |
| `scripts/run-state.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/run-state.py | `dd39eadc757197e0eb024188a4975d22a079ada19d63c3820d0ae35390d6c9dd` |
| `scripts/validate-context.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/validate-context.py | `4bc6927fb96480be8e0cc682351f0b87b81f33f8220113df729980af441633d1` |
| `scripts/validate-runtime.py` | https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/scripts/validate-runtime.py | `d3856824c1c782f7ec80a7dadd3754859b15bfb8f1fbe642a05388df31a2fa10` |
