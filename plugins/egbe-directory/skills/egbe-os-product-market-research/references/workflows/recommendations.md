# Serialize research recommendations

This optional writer serves the existing recommendation UI. It does not select
research or run providers. Derive any proposed scope from the current task and
project market-and-acquisition method, reusing existing material. No research
may be the right recommendation; an empty recommendations object is valid.

Read the catalog for supported IDs and the artifact contract for publication.
The UI omits catalog entries marked internal; that presentation filter does not
forbid the agent from using their research operations for a bounded assignment.
Explicit competitor domains can supply Ads/Reviews directly; Keyword Economics
is not an automatic prerequisite.

Supply temporary JSON:

```json
{
  "recommendations": {"target_audience": "Question this work would answer."},
  "explanation": "Why this scope is useful for the current decision, or why no new research is needed."
}
```

Reasons are nonempty plain-text single lines of at most 180 characters. The
explanation is one plain-text paragraph of at most 400 characters. These are
existing UI limits, not a research-depth or evidence requirement. Name the
uncertainty without presenting intended findings as established facts or
including unrelated founder personal information.

```bash
python <skill-root>/scripts/write-recommendations.py --input <temporary-json-path>
```

The writer validates IDs, fills the selectable option list, and atomically
serializes `egbe-docs/research/<id>/pre-prd-recommendations.md`. It does not
expand the selection. The caller owns Git and the next action.
