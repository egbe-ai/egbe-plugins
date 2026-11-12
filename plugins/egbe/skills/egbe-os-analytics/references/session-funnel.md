# Collect and replay session evidence

Use this for a requested cohort/window analysis. The helper collects scoped Umami
events and counts per-session stage observations, not ordered conversion or
causal business impact. Select event names and property filters from the current
product emitters and `GET /analytics/events`; one canonical event name may cover
several different actions.

## Collection

Run from the product root. The helper loads `.env.local` through the installed
quickstart connection helper and includes the current agent identity; otherwise
it uses `OS_URL` and `OS_API_KEY`. Keep credentials out of artifacts.

```bash
python3 <analytics-skill>/scripts/umami_funnel.py --site <unique-domain-or-name> \
  --since <YYYY-MM-DD> --until <YYYY-MM-DD> \
  --act-start-event <core-start> --act-event <core-complete> \
  --events-json <work>/evidence/umami-events.json --json <work>/analysis/umami.json
```

Create the output parent directories in the caller's existing work folder first.
Both outputs refuse overwrite. Dates are UTC; `--until` is exclusive. Omit dates
for all history. Exact name/domain/id wins over a unique substring; ambiguous
sites and incomplete base-event downloads fail rather than silently truncate.
Record the resolved window/config and inspect enrichment/coverage status.

The event snapshot retains every downloaded row, including excluded sessions,
with safe properties and pseudonymous joins. It preserves safe UTM labels, not
arbitrary query values, free text or private identifiers. It is not a raw backup;
redaction limits later analyses needing omitted fields. Preserve source dates,
queries, exclusions and coverage alongside any derived result.

## Reconcile independent evidence

For supplied trackers/exports, read relevant notes and history with the values:
retain source row/range, definition, reporting window and last update. A blank
is not zero; old status and source-author advice are not current observed state.
Preserve the inspected inputs and helper version needed to reproduce material
calculations. Corrected evidence gets a distinct version, not a silent overwrite.

For accounts, jobs and results, inspect the product's actual data-access code.
Use `egbe-os-db` for scoped read-only SQL and paginated exports, following its
current response/limit contract. For Convex, use that skill's backend discovery
and an existing deployed query whose filters and limits you have inspected, not
a mutation or action. Reading evidence does not authorize provisioning, creating
jobs or contacting customers. Keep credentials in memory.

Inspect only authorized customer evidence. Select necessary fields and redact
credentials, personal data and signed URLs before the first write; use consistent
pseudonymous joins. Do not persist raw private media or session replays in the
analysis. Remove temporary inspection copies after use, retaining anonymous
observations, access/selection limits and reproducible calculations.

## Offline replay and custom calculations

```bash
python3 <analytics-skill>/scripts/umami_funnel.py \
  --from-events <work>/evidence/umami-events.json --json <work>/analysis/replay.json
```

The saved configuration is replayed without a network request. Other event types
remain in the snapshot, but only pageviews (1) and custom events (2) supply stage
observations and timelines. Filter **before** grouping, counting or taking time
extrema, with the same window/internal-activity exclusions:

```python
funnel_rows = [r for r in snapshot["rows"] if r["eventType"] in (1, 2)]
```

For fields absent from this snapshot, use authorized source queries and sanitize
before retaining them. Base events use
`GET /analytics/<appSlug>/events?startAt=<ms>&endAt=<ms>&page=N&pageSize=500`:
both bounds are inclusive UTC milliseconds; paginate from 1 through `.data.count`,
reading `.data.data[]`. Event-data uses the same window/pagination; join event
`id` to `eventId` and read `eventProperties[]`. Its count is events with properties,
not property count. The helper converts its exclusive CLI end into the API window.

## Counting and coverage

- A session may span visits. Per-session observations are unordered; cross-visit
  purchases require appropriate identity. Completion is a technical proxy, not
  proof of useful quality. Reconcile signup with account records and payments
  with provider-confirmed records using the owning capabilities.
- Only signup-completion events count as signup proxies; account-page visits and
  signup-page visits without intent events are separate. Keep users, attempts,
  transactions, test payments, renewals and refunds distinct in derived analyses.
- `included_sessions` means not excluded, not verified customers. Engagement/bounce
  are activity proxies: a different page, non-ambient custom event, or scroll+time
  beacons. Section/scroll alone does not count. Check actual emitter wiring;
  mount-fired events cannot establish intent. Sparse events and their observed
  span do not establish total attention or why a person left.
- Event-only sessions are not arrivals. For an arrival/click ratio, use pageview-
  backed `arrivals_by_source`, not `mix`, and match source, identity and window.
  A source aggregate cannot identify a winning creative. `cta_click` and
  `button_click` remain separate; secondary navigation is not automatically intent.
- Confirmed synthetic sources (`--internal-sources`, default `smoke`) and verified
  internal countries (`--internal-country`, no default) are excluded. Geography
  alone is not proof of internal activity. Direct desktop DE/FI and debug/admin
  paths are suspect, not automatically excluded; keep uncertainty visible.
- Reconcile test accounts/jobs with product records and verified testing context.
  Do not infer a customer from a missing test flag. Preserve unknown coverage;
  truncated recent payment readbacks cannot establish lifetime totals.

Fleet `product-metrics` uses different definitions: it can infer starts from
completions, exclude sessions this helper only flags, and include legacy signup-
submission events excluded here. Reconcile definitions before comparing totals;
do not change either counter to force agreement or interpret a fleet stage as
the product's goal.
