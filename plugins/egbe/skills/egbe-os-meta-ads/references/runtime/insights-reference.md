# Meta Ads Insights Reference

Use this file to read Meta campaign, ad-set and ad metrics through OS.

Platform insights and product analytics have separate sources and attribution.

## Current OS Endpoints

Use normalized campaign results for quick checks:

```bash
GET $OS_URL/ads/meta/campaigns/{campaign_id}/results
```

Use raw insight endpoints for campaign, ad set, and ad-level details:

```bash
GET $OS_URL/ads/meta/raw/campaigns/{campaign_id}/insights
GET $OS_URL/ads/meta/raw/adsets/{adset_id}/insights
GET $OS_URL/ads/meta/raw/ads/{ad_id}/insights
```

These endpoints use a fixed field set. Without date inputs they retain the
legacy `last_30d` window, which can exclude the current account-local day.
For a campaign-lifetime safety counter, request an explicit current-inclusive
window instead of treating that default as cumulative spend:

```bash
GET $OS_URL/ads/meta/campaigns/{campaign_id}/results?period=MAXIMUM
GET $OS_URL/ads/meta/raw/campaigns/{campaign_id}/insights?period=MAXIMUM
GET $OS_URL/ads/meta/raw/adsets/{adset_id}/insights?date_from=2026-10-31&date_to=2026-11-02
```

Campaign results and all three raw insight routes accept `period=TODAY`,
`YESTERDAY`, `LAST_7_DAYS`, `LAST_30_DAYS` or `MAXIMUM`, OR an inclusive
`date_from`/`date_to` pair, ordered and at most 366 days. Raw insight routes also
accept the equivalent native `date_preset` names (`today`, `yesterday`,
`last_7d`, `last_30d`, `maximum`). Do not mix selections. Unsupported raw date
parameters are rejected; generic raw forwarding does not grant arbitrary Graph
API parameters, breakdowns or attribution settings.

Meta interprets periods and dates in the resource's ad account calendar. Do not
substitute the gateway's UTC date or another shared account's timezone. TODAY
is a daily counter, not a lifetime counter. MAXIMUM asks Meta for its maximum
available history through the current day; retention and reporting lag still
apply. Preserve prior counters and historical evidence.

`report.query` confirms the selected contract. `report.date_from`/`date_to` are
the actual provider-returned bounds, `calendar` is `provider_account`, and
`currency` is the native account currency. Check those bounds against the
required account-local day and campaign history. A request's inclusion of today
does not prove today's spend is final. `retrieved_at` is fetch time, not a
completeness or freshness watermark. Empty rows, missing metrics, incomplete
pagination or missing report-contract metadata for an explicit selection are
unavailable, not zero. Do not enforce a spend cap from an unverified window.
`metrics_available` means at least one requested core metric is usable; inspect
`metric_availability` for each required spend/impression/click/link-click field.
`window_available` checks that returned dates are valid and, for a custom range,
match the selected bounds. It does not certify current-day finality.

Normalized results retain `raw`, expose `report`, `provider_diagnostics` and
`metrics.inline_link_clicks`, and label native `metrics.spend`/`currency`.
`spend_usd`/`cpc_usd` are unavailable for a confirmed non-USD currency. Old
no-input clients keep their default window; a new OS talking to an older Tools
gateway refuses explicit selections that the older gateway could silently ignore.

## Enumeration Completeness

Campaign, ad-set, and ad lists can be truncated at the provider or OS page
limit. Follow pagination only where the route supports it; otherwise record
that the child enumeration is incomplete. A full page is not evidence that
every child was returned. Label incomplete child coverage in saved results.

## Current Field Set

Campaign insights include:

- `campaign_name`
- `impressions`
- `reach`
- `clicks`
- `inline_link_clicks`
- `spend`
- `cpc`
- `cost_per_inline_link_click`
- `ctr`
- `inline_link_click_ctr`
- `frequency`
- `actions`
- `cost_per_action_type`
- `purchase_roas`
- `date_start`
- `date_stop`

Ad set insights replace `campaign_name` with `adset_name`. Ad insights replace
it with `ad_name`.

## Metric Meaning

| Field | Meaning |
|---|---|
| `impressions` | Total ad impressions |
| `reach` | Unique people reached |
| `frequency` | Average impressions per reached person |
| `spend` | Spend in account currency |
| `clicks` | All clicks |
| `inline_link_clicks` | Link clicks inside the ad unit |
| `ctr` | All-click CTR percentage |
| `inline_link_click_ctr` | Link-click CTR percentage |
| `cpc` | Cost per all click |
| `cost_per_inline_link_click` | Cost per link click |
| `actions` | Array of action objects: `{action_type, value}` |
| `cost_per_action_type` | Cost per action object array |
| `purchase_roas` | Return on ad spend object array |

`inline_link_clicks`, `inline_link_click_ctr`, and `cost_per_inline_link_click`
measure link interactions; all-click metrics can also include non-link engagement.

## Common Action Types

Look for these in `actions`:

| Action type | Meaning |
|---|---|
| `landing_page_view` | Meta observed a landing page load |
| `link_click` | Link click |
| `lead` | Lead event |
| `complete_registration` | Registration completion |
| `purchase` | Purchase |
| `add_to_cart` | Add to cart |
| `initiate_checkout` | Checkout started |
| `page_engagement` | Page engagement |
| `post_engagement` | Post engagement |
| `video_view` | 3-second video view |
| `omni_purchase` | Cross-platform purchase |
| `offsite_conversion.fb_pixel_purchase` | Pixel purchase |
| `offsite_conversion.fb_pixel_lead` | Pixel lead |

Meta action names do not replace product analytics events. Product-side
canonical events still come from `/analytics/events`.

## Fresh Object Caveat

Meta does not always return insights immediately after campaign launch or object
creation. Empty `data` can be normal for several hours after a campaign, ad set,
or ad is created.

Record creation and fetch times with empty results. Campaign-level data does not
fill missing child rows: recently created ads/ad sets can still have pending
insights inside an older campaign. An empty report does not distinguish ingestion
delay from no delivery. Read configured/effective delivery state separately.

## Missing Fields

Even when `data` is non-empty, individual fields can be null or absent,
especially `purchase_roas`, `frequency` on fresh objects, and
`cost_per_action_type` when conversion tracking is not configured.

Record missing values as unavailable, pending, or not configured. Do not replace
them with zero.

## Product Analytics Join

When the requested analysis needs product attribution, collect:

- UTM campaign values used in destination URLs
- OS analytics campaign visits
- engagement quality when available
- canonical events such as `cta_click`, `signup_completed`, `activated`, and
  `purchase`
- tracking state: `active`, `degraded`, or `blocked`

Preserve attribution windows, event definitions and coverage for each source;
conflicting values are separate observations, not interchangeable totals.

## Future Fields Not Yet Contracted

Meta supports useful concepts that the current OS route does not expose as
free-form controls:

- daily/weekly time increments;
- age, gender, country, platform, placement, and device breakdowns;
- explicit attribution windows;
- async reports for large datasets.

Do not claim those were checked unless the OS route used for the run actually
returned them.
