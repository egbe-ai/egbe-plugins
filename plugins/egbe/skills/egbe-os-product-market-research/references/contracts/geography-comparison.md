# Geography comparison input

Agent-authored analysis, not direct provider measurements. The helper validates
structure and reference integrity, not the truth of claims or the best market.
Use these exact fields; free-text values below explain their purpose.

```json
{
  "schema_version": 1,
  "section_id": "geography_comparison",
  "context_sha256": "<SHA-256 returned by --prepare>",
  "decision": "compare",
  "geography_basis": "preference",
  "reason": "Why geography can change the next decision; what the founder actually constrained.",
  "countries": [
    {"code": "GB", "reason": "Why this market belongs in the shortlist."},
    {"code": "DE", "reason": "Why this is a credible alternative for the same buyer/problem."}
  ],
  "criteria": ["Reachable buyers"],
  "sources": [],
  "rows": [
    {"type": "geography_finding", "country": "GB", "criterion": "Reachable buyers", "classification": "unknown", "statement": "The relevant reachable population has not been measured.", "source_ids": [], "limitation": "No comparable count for this buyer definition."},
    {"type": "geography_finding", "country": "DE", "criterion": "Reachable buyers", "classification": "unknown", "statement": "The relevant reachable population has not been measured.", "source_ids": [], "limitation": "No comparable count for this buyer definition."}
  ],
  "recommendation": {
    "primary_country": null,
    "runner_up_country": null,
    "rationale": "Insufficient evidence to rank these markets.",
    "changes_choice_when": "A comparable reachable-buyer estimate materially favors one country.",
    "next_step": "A specific bounded check of that difference, with cost/time assumptions."
  },
  "limitations": ["What was unavailable, not collected, stale or not comparable."]
}
```

The example represents missing evidence, not a recommended country pair or a
sufficient research effort. Choose relevant criteria and countries for the product.

- `geography_basis`: `founder_constraint`, `preference`, `open` or
  `evidence_supported`. Explain the basis in `reason`; founder preference is
  not independent market evidence.
- `decision: compare` needs at least two unique uppercase two-letter country codes and
  one row for each country × chosen criterion. Cells may be unknown; do not
  manufacture equal coverage or fill gaps with unsourced certainty.
- Each row is `observation`, `estimate`, `hypothesis` or `unknown`. Observations
  need sources. Estimates explain calculations/assumptions in the statement
  and limitation; hypotheses/unknowns are not measured facts.
- Sources have exactly `id` (`S1`, `S2`, …), `reference`, `accessed_on`
  (`YYYY-MM-DD`), `period` and `limitation`. `reference` is a direct public
  HTTP(S) URL or `research:<section_id>` completed in the prepared context.
  For actual product outcomes or source excerpts saved locally, use
  `artifact:egbe-docs/research/market/evidence/geography-comparison-sources/<name>.md`
  (also `.json`/`.txt`). Record anonymous counts, cohort, dates and origin, never
  customer identities, credentials or raw private records. The helper binds
  these files by hash and publishes them with the comparison. This is optional;
  unavailable product outcomes remain unknown, not invented zeros.
  An unknown original publication date/period must be stated, not replaced by
  today's access date. Reused research does not become independent new evidence.
- `source_ids` cites declared IDs. Read sources and preserve notes/excerpts;
  never cite an uninspected URL as proof. Refer to available product outcomes
  anonymously; missing outcomes may remain unknown rather than uploading PII.
- `primary_country` and `runner_up_country` name shortlisted countries or null.
  A runner-up needs a distinct primary. No scores or mandatory winner.
- `decision: not_compared` is a reasoned scope assessment: retain the relevant
  countries, leave `criteria`/`rows` empty and both recommended countries null.
  Explain the actual constraint or why new comparison has no decision value,
  the supporting evidence if available and when to reopen it. Completion then
  means the scope was assessed, **not** that comparative market research occurred.

The canonical JSON and report are projections of this single input. Do not
hand-edit the report, generated JSON or completion receipt after publication.
