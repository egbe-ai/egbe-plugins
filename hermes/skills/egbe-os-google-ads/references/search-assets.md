# Search objects and ads

Read the selected campaign's `/children` before adding or changing objects.
Use returned IDs and preserve unrelated objects. These operations require owned
campaign/group targets and configured mutation quota; credentials alone do not
authorize new advertising.

## Create Search assets

```http
POST /ads/google/campaigns/{ref}/search-assets
Idempotency-Key: <stable key for this exact batch>
Content-Type: application/json
```

```json
{
  "geoTargets": ["geoTargetConstants/2840"],
  "adGroups": [{
    "name": "Contract review",
    "cpcBidMicros": 2500000,
    "status": "PAUSED",
    "keywords": [{"text": "contract review software", "matchType": "PHRASE", "status": "PAUSED"}],
    "negativeKeywords": [{"text": "login", "matchType": "PHRASE"}],
    "responsiveSearchAds": [{
      "finalUrls": ["https://product.example/?utm_source=google&utm_medium=paid_search&utm_campaign=google-search-001&utm_content=contract-review"],
      "headlines": ["Review Contracts Faster", "Find Risky Clauses", "Clear Contract Insights"],
      "descriptions": ["Check contract risks before signing.", "Review legal documents with clear next steps."],
      "status": "PAUSED"
    }]
  }]
}
```

All choices are illustrative. During new-campaign preparation, create serving
objects PAUSED. For additions to an existing campaign, use the status required
by the authorized operation. Never create real objects, even PAUSED ones, or
enable objects merely to probe an API schema. Resolve an unclear request format
before sending a write. A new campaign needs explicit intended geo criteria and
complete groups, keywords, ads and destinations before launch.

This endpoint performs budget/geos/groups/keywords/negatives/ads sequentially,
not atomically. A failure may leave earlier objects created; releasing a wallet
hold does not roll them back. `adGroups[].id` selects an existing group rather
than upserting it. The current schema still requires that group's `name` and
`cpcBidMicros`, but supplying an id does NOT update its name, bid or status.
Use [campaign bid controls](campaigns.md) for actual bid changes.

`prohibited_category_guardrail:<category>` is an Egbe content-filter rejection,
not a Google moderation result. The filter scans ad copy and positive keywords;
negative keywords remain exclusions. Explicit completed advice disclaimers such
as `Estimates only, not medical advice` are allowed, but other prohibited claims
in the same payload still block the request. Report a suspected false positive
with the submitted text; do not remove a truthful disclaimer to evade the filter.
Passing this check does not establish provider approval or category eligibility.

Use a key for the exact batch. The successful-response cache is process-local,
temporary (default 15 minutes) and keyed by key plus payload, not durable
exactly-once. It does not serialize concurrent requests; changed payload is a
cache miss, not a guaranteed 409. After a timeout, partial failure, restart or
cache expiry, read children and reconcile exact IDs/text/match types before
creating anything else. Never replay a whole uncertain batch blindly.

Inspect `data.raw.results` and `data.raw.readback`, then obtain fresh readback.
Save confirmed IDs before clearing the unfinished operation. Do not substitute
local desired state for provider evidence.

## Granular creates

Use these only for identified missing or intended additional objects:

| Endpoint suffix under /ads/google/campaigns/{ref} | Body |
| --- | --- |
| POST /geo-targets | `{"geoTargets":["geoTargetConstants/2840"]}` |
| POST /ad-groups | `{"adGroups":[{"name":"Contract review","cpcBidMicros":2500000,"status":"PAUSED"}]}` |
| POST /ad-groups/{group}/keywords | `{"keywords":[{"text":"contract review software","matchType":"PHRASE","status":"PAUSED"}]}` |
| POST /ad-groups/{group}/negative-keywords | `{"negativeKeywords":[{"text":"login","matchType":"PHRASE"}]}` |
| POST /ad-groups/{group}/responsive-search-ads | `{"responsiveSearchAds":[...]}` using the ad shape above |

These are create-only, not upserts. Geo-target reads are available at
`GET /ads/google/campaigns/{ref}/geo-targets`. Use targeting PATCH for replacing
targeting categories, not an additive geo POST.

Only the positive-keyword POST and combined search-assets currently forward
Idempotency-Key through OS. Granular geo, group, negative and RSA POSTs do NOT;
do not assume adding a header protects them from duplicates. After uncertain
creation reconcile readback before any repeat. The older granular responses
wrap `results`/`readback` in `data.raw`; positive-keyword creation returns
those fields directly in `data`.

Positive keyword batches accept 1–100 entries. `matchType` is PHRASE (default),
EXACT or BROAD; use plain text without quote/bracket notation.
`cpcBidMicros` is a positive integer in account-currency micros; omit or null
to inherit the group bid. Explicit ENABLED affects only that new keyword and
must fit the requested operation; it does not enable campaign/group ancestors.
Explicit group/keyword bids must also satisfy configured gateway CPC bounds;
do not alter the requested bid just to pass a rejection.
Negatives have no provider status and remain exclusions; do not try to pause
them with positive-keyword status or campaign child status.

## Change selected positive keyword statuses

```http
PATCH /ads/google/campaigns/{ref}/ad-groups/{group}/keywords/status
Content-Type: application/json
```

```json
{"keyword_ids":["111","222"],"status":"PAUSED"}
```

Supply 1–100 unique IDs and ENABLED or PAUSED. All must be positive keywords
in that owned campaign/group; foreign, missing or negative IDs fail before any
mutation. Other keywords, ancestors, ads, bids and budget remain unchanged.

This is desired-state assignment, not replay of an old operation. No key is
required; matching statuses skip mutation. Do not retry an obsolete instruction
after a later intentional change. Inspect `data.keywords`, `updated`,
`readback` and `verified`; on a 409 mismatch inspect children first.
Verification is not policy approval or proof of impressions.

## Read or edit an existing RSA

GET then PATCH the exact owned ad:

```http
GET /ads/google/campaigns/{ref}/ad-groups/{group}/responsive-search-ads/{ad}
PATCH /ads/google/campaigns/{ref}/ad-groups/{group}/responsive-search-ads/{ad}
Idempotency-Key: <stable key for this text change>
```

```json
{
  "headlines": [
    {"text":"Find Your Community","pinned_field":"HEADLINE_1"},
    {"text":"Explore Relevant Groups"},
    {"text":"Start With Your Product"}
  ]
}
```

PATCH accepts only headlines and/or descriptions. A supplied list replaces that
whole list; omit the other to preserve it, do not send null. Headlines: 3–15,
at most 30 characters each. Descriptions: 2–4, at most 90. Text must be unique
and nonblank within its list. Google also applies language and policy rules.

GET returns text assets with optional `pinned_field`. Preserve pins on retained
assets; omission/null means unpinned. Headline pins are HEADLINE_1–HEADLINE_3,
description pins DESCRIPTION_1–DESCRIPTION_2. Creation takes strings rather
than this PATCH object shape; apply pins to a new paused ad with PATCH.

The edit preserves ID, URLs, status, settings, bids and budget. A creative shared
with another group is rejected to avoid changing other placements. Inspect
`data.ad`, `verified` and `policy_summary`; edited ads may need review.
Retry interruption with the same key/payload. On 409 inspect the exact ad and
diagnostic; do not create replacements or change keys to bypass uncertainty.

## Change one RSA's status or replace it

```http
PATCH /ads/google/campaigns/{ref}/ad-groups/{group}/responsive-search-ads/{ad}/status
Idempotency-Key: <stable key for this status change>
Content-Type: application/json
```

```json
{"status":"ENABLED"}
```

Only ENABLED/PAUSED is accepted; this changes the selected group/ad association,
even if the creative is shared. It cannot edit URLs/content, enable ancestors,
change bids/budget or approve policy. Inspect the exact returned `ad` and
`verified`. A wallet with depleted/unknown availability blocks a new ENABLED
mutation; funded holds are respected. PAUSED does not require wallet availability.
An already-matching status skips provider mutation, wallet admission and quota
increment. Confirmed mutations have a durable quota receipt.

Retry an interrupted status request with the same key and payload for
reconciliation. Changed payload conflicts; uncertain outcome, drift or a
readback mismatch may return 409 even after a successful mutation. Inspect the
exact ad, do not bypass with new keys or resume an obsolete status operation.

When replacing an ad is requested, preserve its group, exact destination query,
copy, pins, targeting and budgets unless the requested change says otherwise.
Create the replacement PAUSED in the same group, reconcile its exact ID, then
inspect policy review. Wait for REVIEWED and APPROVED; APPROVED_LIMITED needs
inspection of policyTopicEntries to establish that restrictions fit the campaign.
Missing/pending/disapproved data is not approval. Never enable ancestors merely
to force review or resume a safety stop for this procedure.

For the agreed cutover, after acceptable policy review, enable only the replacement
with the exact status endpoint; verify it, then pause the old ad. Respect any
additional authorization conditions on the cutover. These two writes are not atomic:
do not promise zero overlap or delivery. A support ticket or destination approval
alone is not authorization for advertising writes.

## Destination and attribution

Preserve the actual intended destination and query string. Use canonical product
analytics attribution: `utm_source=google`, `utm_medium=paid_search`, stable
channel-qualified `utm_campaign`, useful `utm_content` and, when available,
`utm_term`. Keep `utm_campaign` stable across the plan and product analytics,
not an unrelated experiment ID. See [Reporting](reporting.md).

For a visitor-path audit use the installed destination-readiness skill, available
at `GET /skills/destination-readiness`. For Google, compare displayed/final/mobile
domain and actual redirect chain. A later disclosed booking/payment CTA is not
automatically an initial ad-domain mismatch. Browser success does not prove
AdsBot or target-region access. A useful page with an external CTA is not
automatically a prohibited bridge page. Check observed identity, security and
collection issues against the applicable current official policy, not spelling
differences between brand and disclosed operator.

Policy sources: [destination requirements](https://support.google.com/adspolicy/answer/6368661?hl=en),
[misleading representation](https://support.google.com/adspolicy/answer/15936666?hl=en),
[data collection](https://support.google.com/adspolicy/answer/6020956?hl=en).
Read the relevant current section before attributing a failure. Report exact URL,
evidence and repair/recheck condition; distinguish visitor defects, policy risk
and confirmed provider rejection. No local audit grants Google approval.
