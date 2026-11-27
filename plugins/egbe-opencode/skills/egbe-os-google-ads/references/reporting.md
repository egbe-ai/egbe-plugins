# Performance, diagnostics and product attribution

Reporting is read-only. Use the requested date range and exact campaign ref;
these calls do not change bids, budget, targeting or delivery.

## Product analytics

For a performance or scaling assessment, read the available product analytics or
payment outcomes alongside Google results before calling reported conversions
paying customers or concluding that downstream outcomes are unavailable. A
Google conversion can be only a signup. Check the connected outcome records
before asking the founder for a signup-to-paid rate; if those reads fail or
tracking cannot attribute a sale, report that specific evidence gap.

Keep each comparison row on one explicit window: spend, clicks, signups and paid
customers must cover the same dates before computing acquisition cost. If the
agreed decision uses lifetime performance, read from the campaign's creation
date rather than substituting a recent seven- or thirty-day report. Check the
resolved dates in the response; a correct keep/pause decision does not make a
mixed-window table accurate. When matched evidence is unavailable, label the
separate windows and leave their combined ratio uncomputed.

Before choosing that window, inspect the existing campaign notes or launch
record for this exact campaign ID/ref. With a local project folder, search and
read its relevant files even if a remote artifact-store read failed; historical
notes can live outside the current recommended layout. An absent provider start
date or an artifact-store 404 does not make existing local notes unavailable.
Never assume that two campaigns started together. Use the recorded launch date
as historical context and the provider reads for current state.

For paying-customer counts, revenue or signup-to-paid conversion, follow
**Reporting customer metrics** in `GET /analytics/skill` and read the connected
payment records for the same window and campaign. A campaign's signup activations
and site-wide purchase event count alone do not establish its paying customers.

Read the current analytics capability and canonical events:

```http
GET /analytics/skill
GET /analytics/events
GET /analytics/{product_slug}/tracking
GET /analytics/{product_slug}/campaigns?period=all
GET /analytics/{product_slug}/stats?period=24h
```

Preserve the campaign's stable attribution: utm_source=google,
utm_medium=paid_search, utm_campaign equal to its channel-qualified slug,
useful utm_content and utm_term when available. These are not product event names
or experiment IDs. Keep existing durable business/product/launch/experiment/
variant identity separate when supplied; do not invent it or change it to fit
a campaign name.

Use canonical events from /analytics/events, not new channel-specific event
names. Do not emit synthetic product events to prove readiness. Google clicks
are not product visits or conversions. If only site-wide product signals are
available, label them non-attributed; never present them as exact campaign
outcomes. Missing tracking, unavailable metrics and pending data are not zeros.

Label saved observations with their actual date when live reads are unavailable;
they are not current provider state. Preserve useful results as described in
[Campaign records](artifacts.md). For metrics of one conversion action, see
[Conversions](conversions.md).

## Campaign results

```http
GET /ads/google/campaigns/{ref}/results?period=TODAY
GET /ads/google/campaigns/{ref}/results?date_from=2026-01-01&date_to=2026-01-31
```

Choose either a period (TODAY, YESTERDAY, LAST_7_DAYS, LAST_30_DAYS) or both dates,
not both forms. Omission defaults to LAST_30_DAYS, excluding today. Dates are
inclusive account-local calendar dates, ordered, at most 366 days and not in the
future. TODAY includes the whole account-local day, not only time since a bid
change. Keep a timestamped baseline when a before/after comparison is needed.

Read `data.metrics`, resolved dates, account timezone, `data_status`,
`retrieved_at` and `freshness`. Monetary amounts use the returned currency,
not assumed USD. Same-day figures can lag; fetch time is not a completeness
watermark. Actual reported zero, no_rows, missing metric and failed query are
different states. Never replace unknown/missing values or errors with zero.

Search impression share fields in metrics are ratios, not percentages or counts:

- `search_impression_share`: received / estimated eligible Search impressions.
- `search_rank_lost_impression_share`: estimated share lost to Ad Rank.
- `search_budget_lost_impression_share`: estimated share lost to budget.

Inspect `data.metric_availability[field]`. Available values may genuinely be
zero. Unavailable values are null with a reason such as not_reported, no_rows or
invalid_provider_value. Below_threshold means share <10%; above_threshold means
the relevant lost share >90%, with the boundary in `threshold`.
These bounded values are null, not exact measurements. Raw provider sentinels
0.0999/0.9001 must not become exact 9.99%/90.01% claims. Unit is ratio.

Overall data_status=available describes the basic metrics; individual share
metrics can still be unavailable. Search shares update daily and can lag 1–2
days. Unknown freshness.provider_data_through does not establish completeness.

## Device and keyword-device reports

```http
GET /ads/google/campaigns/{ref}/device-report?period=LAST_7_DAYS
GET /ads/google/campaigns/{ref}/device-report?date_from=2026-01-05&date_to=2026-01-05&level=keyword&ad_group_id=789&by_hour=true
```

Read-only native Google rows segmented by `segments.device`. Dates use the same
rules as campaign results (period OR both dates, account-local, inclusive).
`level` selects the row identity:

- `campaign` (default): date x device.
- `ad_group`: adds `ad_group_id` and `ad_group_name`.
- `keyword`: the joint keyword x device matrix with `ad_group_id`,
  `criterion_id`, `keyword_text` and `match_type` (traffic matched by that
  bid keyword, not the search query).

`ad_group_id` (ad_group/keyword levels only) restricts to one group of this
campaign. `by_hour=true` adds the account-local `hour` (0-23) for windows of at
most 7 days, for example to separate delivery before a known start time.
Ad-level device rows are not available.

Each row has `date`, `device` (DESKTOP, MOBILE, TABLET, CONNECTED_TV, OTHER or
UNKNOWN), `impressions`, `clicks`, `cost_micros` and `cost` in the returned
`currency_code`. `totals` and `totals_by_device` sum the rows. `reconciliation`
compares them with unsegmented totals of the campaign (or the selected ad group)
for the same dates: `difference` = reference minus rows. Keyword rows omit
traffic not matched by a keyword; any other non-zero difference is a provider
omission or revision, not lost data. Also read `time_zone`, `date_from`,
`date_to`, `data_status` (`available`, `no_rows`, `unavailable`),
`retrieved_at` and `freshness`; recent figures can still be revised.

## Search terms and current diagnostics

```http
GET /ads/google/campaigns/{ref}/search-terms?period=LAST_30_DAYS
GET /ads/google/campaigns/{ref}/diagnostics
GET /ads/google/campaigns/{ref}/children
```

Search terms uses its own period query; do not assume the campaign results
date_from/date_to interface exists on it. Its provider response is in
`data.raw`. Record unavailable term evidence; raw GAQL is not an exposed
alternative. Diagnostics returns directly in `data`:

- Campaign status, primary_status, primary_status_reasons and availability.
  A valid empty reason list differs from unavailable; UNKNOWN remains unknown.
- Configured/effective keyword CPC and inheritance source; absent/inherited
  configured bids are not zero.
- Ad review/approval and policy topics.
- Current keyword quality_info: quality_score (1–10), expected_ctr,
  ad_relevance and landing_page_experience. Components use ABOVE_AVERAGE,
  AVERAGE or BELOW_AVERAGE when reported.
- Per-field availability, nulls and reasons not_reported, unspecified, unknown
  or invalid_provider_value; raw_value can retain a provider sentinel.
- UTC retrieved_at and account currency/timezone.

Current quality_info differs from historical quality metrics in term reports.
An unavailable overall score does not erase available components, and missing
historical data does not prove that current scores are absent. A failure is
an error, not an empty list. LIMITED/BUDGET_CONSTRAINED and quality buckets are
provider diagnostics, not product-sales measurements.

For delivery status use [Delivery](delivery.md). An eligible enabled path,
observed impressions and campaign-attributed product outcomes are different
pieces of evidence.
