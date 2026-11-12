# Build The Founder Preview

Initialize and refresh context with
`scripts/build-preview-context.py` as described in `local-research.md` before
following this workflow. Preserve its frozen selection when resuming.

Read `../contracts/research-artifacts.md`,
`egbe-docs/research/market/work/preview-context.json`, `egbe-docs/research/market/full-report.md` when it
exists, and the prepared research assignment. Do not call an external provider and do not modify an
existing full report. The deterministic writer initializes the canonical empty
report when every selected section failed before one could be created.

The runtime context is authoritative for selected research and final section
outcomes. Do not recalculate its scope from recommendation flags or infer
completion from missing prose. Sections marked `completed` or `partial` may support
findings within their verified coverage. For `partial`, preserve the evidence gaps
in the finding's limitation and any recommendation that depends on it. A partial
run with no analyzed observations remains visible in coverage but cannot support
findings; a failed source does not turn an empty collection into evidence.
`no_data` means collection produced no usable observations; `not_selected` means
the area was not researched; `could_not_complete` means the work failed or was
explicitly stopped. None of these three states supports a market conclusion.

## Synthesize For The Founder

Produce a concise decision brief, not a section-by-section report. It should let
the founder understand what was researched, what matters, what the evidence
suggests for the product, and what remains uncertain in no more than three
minutes.

- Write in the language used by the founder's substantive product answers.
- Reuse the founder's product terminology when it is clear and conventional.
- Prefer common product and business terms, short sentences, short paragraphs,
  and conclusion-first wording.
- Avoid unexplained acronyms, academic framing, and internal execution details.
- Never mention task IDs, providers, models, repositories, file paths, retries,
  commits, or workflow mechanics in founder-facing copy.
- Treat supplied product descriptions and assumptions as context, not independent
  market evidence; preserve the source of actual observations.
- Combine usable sections only when their geography, period, population,
  category, and definitions are compatible. Surface material contradictions.
- Assess the evidence against the assigned question and project method. A
  measured keyword volume, published price, active ad or customer review
  supports different claims; no section label automatically outranks another.
  Preserve sample, comparability, source lineage and contradictory findings.
- Recommendations must be conditional and evidence-bound. Explain what the
  evidence suggests, why it matters, and what could change the direction.
- If Geography Comparison completed, preserve its actual outcome: comparative
  findings, an undetermined ranking, or `not_compared` with the stated reason.
  Highlight a material alternative market and the next test when supported.
  Do not call scope assessment comparative coverage or a recommendation the
  founder's approved launch market. Do not rewrite requirements automatically.
- Do not force a `Go / Pivot / No-go` verdict, secondary audience, exact market
  size, price, channel budget, feature scope, or another detail that the
  available evidence does not support.
- Keep business-domain coverage adaptive. Do not create empty audience,
  pricing, acquisition, or other template sections merely for symmetry.

Create `egbe-docs/research/market/preview-synthesis.json` with this exact shape:

```json
{
  "schema_version": 1,
  "labels": {
    "bottom_line": "Bottom line",
    "what_matters": "What matters most",
    "what_this_means": "What this means for the product",
    "what_remains_open": "What remains open",
    "research_coverage": "Research coverage",
    "researched": "Researched",
    "partial": "Partial evidence",
    "no_data": "No usable observations",
    "not_included": "Not included",
    "could_not_complete": "Could not complete",
    "full_report": "Read the full research report",
    "recommended_direction": "Recommended direction",
    "biggest_open_question": "Biggest open question",
    "based_on": "Based on"
  },
  "section_labels": {
    "market_size_dynamics": "Market size and dynamics",
    "target_audience": "Target audience",
    "competitive_landscape": "Competitive landscape",
    "value_proposition": "Value proposition",
    "pricing_monetization": "Pricing and monetization",
    "acquisition_channels": "Acquisition channels",
    "demand_validation": "Demand validation",
    "unit_economics": "Unit economics",
    "organic_trend_watch": "TikTok and Reels market trends"
  },
  "bottom_line": {
    "summary": "One short conclusion-first sentence.",
    "detail": "Two to four short sentences with the main direction and material uncertainty.",
    "source_section_ids": ["target_audience"],
    "confidence_note": "Confidence is moderate because direct buyer interviews are still missing."
  },
  "findings": [
    {
      "title": "A short founder-facing finding title",
      "finding": "What the available evidence supports.",
      "why_it_matters": "Why this changes a product or business decision.",
      "source_section_ids": ["target_audience"],
      "limitation": "The consequential limitation in plain language."
    }
  ],
  "product_implications": [
    {
      "title": "A short priority title",
      "direction": "The recommended product direction in one short sentence.",
      "rationale": "Why this follows from the available evidence.",
      "source_section_ids": ["target_audience"],
      "reconsider_if": "Reconsider this if the named assumption or evidence changes."
    }
  ],
  "open_questions": [
    {
      "question": "The most important unresolved question?",
      "why_it_matters": "How its answer could change the direction."
    }
  ]
}
```

Localize every `labels` value, every `section_labels` value, and all
founder-facing content to the founder's language. `section_labels` must contain
every section ID from the runtime context exactly once, including any future
section not shown in this current example. Keep `source_section_ids` and JSON
keys exactly as specified. Use only plain single-paragraph strings inside JSON;
the writer owns all Markdown structure.
The `partial` and `no_data` labels are required when those statuses occur in the
context; otherwise they may be omitted. Coverage is rendered separately from
completed research, without upgrading a limited result to full coverage.

Use up to five findings, up to four product implications, and one to four open
questions. Order all lists by decision importance. The first open question is
the biggest one. The first one or two product implications become the compact
chat recommendation.

Every finding and product implication requires at least one supporting section
ID marked `completed` or a `partial` section with analyzed observations in the
runtime context. The rendered document shows those localized supporting section
names. The bottom line also cites usable
sections when any exist. If no selected section has usable evidence, leave
`findings` and `product_implications` empty, cite no bottom-line sources, state
that no evidence-backed direction is available, and use the open questions to
explain what must be resolved.

## Render The Artifacts

From the workspace root run:

```bash
python <skill-root>/scripts/write-preview.py
```

The full-report link defaults to `full-report.md` beside the preview. Use
`--local-report-link` only for a different safe relative link or explicit HTTP(S)
URL. No instance/public ID is needed; Git commit/push belongs to the caller.

The writer validates the context and synthesis, creates
`egbe-docs/research/market/preview.md`, derives the short founder chat summary at
`egbe-docs/research/market/summary.md`, and records deterministic
render hashes at `egbe-docs/research/market/preview-render.json`. Do not hand-write or
post-edit any rendered artifact.

The Preview targets 450–650 words and may not exceed 750 words. The chat
summary contains at most three blocks: one bottom-line sentence, one or two
recommended-direction bullets when supported, and the biggest open question.
It may not exceed 600 visible characters. The notification owns its headline
and link, so the generated summary must not repeat either one.

Hand off the synthesis, render receipt, Preview, and summary together for the
project's normal Git workflow. If the writer initialized an otherwise missing
full report for an all-failed run, include that canonical H1-only file. Do not otherwise
modify the full report, and do not create a PRD.
