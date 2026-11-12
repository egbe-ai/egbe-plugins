# Report artifacts

## Location and ownership

Store reports in the current product's local workspace:
`egbe-docs/reports/<UTC timestamp>-<mode>/`, for example
`2026-10-20T090000Z-detailed/`. For several Egbe businesses in one workspace,
prefix the report ID with the verified business ID. Do not mix their history.
Use `brief` or `detailed`; append a unique suffix if a separate run collides.

Use the existing product repository when present; reporting does not require
creating a repository, committing, pushing or publishing. Do not use the
installed skill folder as artifact storage. Keep reports out of public/static
app directories and exclude all `egbe-docs/` from the build context.

## Files

| File | Brief | Detailed | Purpose |
|---|---|---|---|
| `snapshot.json` | Yes | Yes | Facts, provenance, windows and coverage |
| `summary.md` | Yes | Yes | The message delivered to the founder |
| `report.md` | No | Yes | Canonical complete findings and proposals |
| `report.html` | No | Yes | Offline presentation derived from report.md |

Markdown owns the interpretation, not `snapshot.json`. For detailed reports,
change content in `report.md` first and refresh both derived outputs. Do not
silently overwrite a different completed run.

## Minimal snapshot contract

Keep these fields stable; the observations themselves depend on the product:

- `project_id`, `run_id`, `mode`, `trigger` (`manual` or `scheduled`).
- `generated_at`: timestamp with offset; `timezone`: the reporting IANA timezone.
- `period`: `from` and `to` timestamps, start inclusive and end exclusive.
- `sources`: entries with a stable `id`, capability/reference, scope,
  `checked_at`, status (`ok`, `partial`, `unavailable`, `not_applicable`) and a
  concise reason when coverage is limited. Record actual data freshness if known.
- `observations`: entries with an `id`, name/definition, value, unit where
  applicable and `source_ids`. Record `as_of` for point-in-time states or a
  `period` for windowed values; aggregate granularity must be explicit.
- `result`: `status` (`in_progress`, `complete`, `incomplete`), overall
  `coverage` (`complete`, `partial`, `unavailable`), produced file paths and any
  unfinished output/check. A complete report can have partial source coverage.

Assess coverage against the applicable questions, metrics and period of this
report, not every feature a provider could supply. Mark a missing breakdown
as a limitation of that analysis, not of otherwise complete totals.
`not_applicable` sources alone do not make overall coverage partial: a new
project can have a complete status report without a deployed product or sales.

Use `null` for an unavailable value with the reason in its source record, not
an invented zero. Keep only aggregates and sanitized evidence used by the
report, not whole API payloads, credentials, customer identities or raw logs.
The report can cite observation/source IDs and source links or query descriptions;
do not embed authenticated URLs.

## Continuation and delivery

Start with the latest applicable summary/snapshot. Read the prior detailed
report and older evidence only when they explain an open question or decision.
Compare only matching scopes, definitions and windows. Keep recommendations
already accepted, rejected or underway visible in the authored result.

On interruption, leave the run incomplete and resume its missing work rather
than treating partial files as a finished report. Set `result.status` after
verification, independently of data coverage. If rendering failed, retain the
valid Markdown and record the missing HTML; the summary can still be delivered.
Required checks that could not run, including visual HTML verification, also
leave the result `incomplete` with those checks listed; they do not invalidate
verified facts or prevent delivery with an explicit limitation.
Keep the detailed validation ledger here, not in the report narrative. In the
founder handoff, name only the practical limitation and available alternative.

The scheduling owner is `egbe-os-product-routines`. It stores settings and delivery
checkpoints separately in the versioned `egbe-docs/routines.json`, and advances
them only after the relevant action is confirmed. Saving a report does not prove
that a notification was delivered. A manual run does not consume scheduled slots.
