# Campaign creation and settings

All paths use `/ads/google`. For a new campaign, first check `/account` as
described in the skill. For existing campaigns, use their saved refs and
campaign-specific account settings; a denied new-account check does not block
them. Keep settings changes scoped to the user's actual request.

## Create a paused Search shell

```http
POST /ads/google/campaigns
Idempotency-Key: <stable key for this creation>
Content-Type: application/json
```

```json
{
  "name": "google-search-001",
  "daily_budget_usd": 5,
  "objective": "SEARCH",
  "status": "PAUSED",
  "product_slug": "product-slug"
}
```

The amount is illustrative, not spending authorization. Creation requires a USD
account, configured mutation quota and wallet admission; no FX conversion is
performed. Use the stable campaign slug chosen for attribution. The provider creates Search with Manual CPC,
Google Search enabled and search-partner/display networks disabled. It creates
the budget and campaign separately, not as one atomic transaction. OS's generic
status field can echo the request; the actual shell is PAUSED. Verify provider
readback rather than treating that echo as truth.

Optional `product_slug` binds reusable conversion actions to the product;
it is not required for launch. Preserve `data.ref`, `customer_id` and
`campaign_id`. Never override the assigned customer.

Creation requires a stable Idempotency-Key. Reuse it with the identical payload;
a changed payload conflicts. The durable operation pins the original account.
If `google_campaign_create_outcome_unknown` is returned, stop for Egbe
reconciliation. Do not create a replacement with a new key. A timeout is not
proof that no budget or campaign was created.

Build serving objects with [Search assets](search-assets.md); use
[Delivery](delivery.md) for activation, pause and actual serving readback.

## Inspect and change targeting

```http
GET /ads/google/campaigns/{ref}/account-settings
GET /ads/google/campaigns/{ref}/targeting
GET /ads/google/campaigns/{ref}/diagnostics
PATCH /ads/google/campaigns/{ref}/targeting
Idempotency-Key: <stable key for this change>
```

```json
{
  "language_ids": ["1000"],
  "location_ids": ["2840"],
  "positive_geo_target_type": "PRESENCE",
  "networks": {"google_search": true, "search_partners": false, "display": false}
}
```

This example selects English/US; it is not a targeting recommendation.
IDs are numeric Google constants, not full resource names. Supplied lists
replace that category; omitted fields remain unchanged, while explicit null
is invalid. `excluded_location_ids: []` clears exclusions. Positive location
and language lists cannot be empty, include/exclude sets cannot overlap and
IDs must be unique. Limits: 20 languages, 100 included and 100 excluded locations.

A supplied networks object sets all three switches and disables the separate
partner-search network; `google_search` must be true for Search. Other
criteria, status, bids and budget stay unchanged. PRESENCE excludes interest
targeting, but includes people in or regularly in the location; it is not a
precise physical-location guarantee.

Inspect `data.verified` and returned configuration. Retry an interrupted
operation with the same key and payload. On an uncertain outcome or drift,
inspect readback and the diagnostic; do not recreate criteria or change keys
to bypass it.

## Change only the daily budget

```http
POST /ads/google/campaigns/{ref}/search-assets
Idempotency-Key: <distinct key for this campaign and intentional change>
Content-Type: application/json
```

```json
{"daily_budget_usd": 4.5}
```

Omit `geoTargets` and `adGroups`: supplying them can create assets. This
updates only the existing budget amount; it does not launch, alter statuses,
bids or targeting, or create a budget. The amount must be authorized, including
a reduction. The current budget must belong to this campaign and be used by
exactly one campaign. `explicitly_shared=true` alone is not proof of multiple
current users. Concurrent provider-side reassignments cannot be made atomic
by this API.

Current writes require USD, an explicit mutation quota, configured amount limits
and wallet admission. The wallet reserves twice the requested daily budget
using the existing budget asset key; even a reduction can fail admission.
This is not a top-up or permission to spend more.

The successful-response cache is temporary (default 15 minutes), process-local
and keyed by key AND payload; changed payload is a cache miss, not a durable
conflict check. Concurrent calls, expiry, restart or failure after mutation can
escape it. Do not send parallel copies or replay an old budget instruction.
After uncertainty, inspect the current budget and reconcile before another write.

Inspect `data.raw.readback.campaign.daily_budget`, currency and unchanged
statuses, then obtain fresh `/children` or `/readback`. A cached response is
historical, not fresh verification; HTTP 200 alone proves neither the requested
amount nor current configuration.

## Change existing Manual CPC bids

```http
PATCH /ads/google/campaigns/{ref}/bids
Idempotency-Key: <stable key for this bid change>
Content-Type: application/json
```

```json
{
  "ad_groups": [{"id": "789", "cpc_bid_micros": 2500000}],
  "keywords": [{"ad_group_id": "789", "criterion_id": "111", "cpc_bid_micros": null}]
}
```

Read `/diagnostics` first. A group default does not replace explicit keyword
overrides; inherited keywords follow a changed group. Null clears a keyword
override to inherit; group bids cannot be null. Omitted targets keep their
configured bids. Supply at least one target, no duplicates, at most 100 groups
and 500 keywords. Positive bids are integer account-currency micros; 2500000
means $2.50 in USD, not an instruction to use that amount.

Configured gateway minimum/maximum CPC guardrails still apply to explicit bids.
If a bound rejects the requested amount, report that constraint; do not raise
the bid or substitute the historical high-range metric without a new decision.

This operation supports Manual CPC Search in USD accounts. It atomically changes
only the requested bids, not strategy, budget, statuses or targeting, and creates
nothing. Inspect `verified`, configured/effective CPC and its source. Retry the
same key/payload after interruption; inspect drift before a new intentional
change, never recreate groups or keywords. Higher bids can increase spend within
the existing campaign budget. Preserve the confirmed change timestamp so later
reports can distinguish observations before and after the change.

Readbacks label `currency_code` alongside money. Legacy `*_usd` values are
populated only for USD accounts; do not relabel other currencies or bypass
wallet/quota errors with provider/admin credentials. An inherited/unavailable
bid is not zero, and a configured base bid is not the average auction price.
