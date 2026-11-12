# Reddit OS API Reference

All requests authenticate with `Authorization: Bearer $OS_API_KEY`.

## Normalized Endpoints

```bash
GET  $OS_URL/ads/reddit/account
POST $OS_URL/ads/reddit/campaigns
GET  $OS_URL/ads/reddit/campaigns
POST $OS_URL/ads/reddit/campaigns/{campaign_id}/launch
POST $OS_URL/ads/reddit/campaigns/{campaign_id}/pause
GET  $OS_URL/ads/reddit/campaigns/{campaign_id}/results
```

`POST /ads/reddit/campaigns` requires a saved, stable `Idempotency-Key` header,
for example `reddit:<product_slug>:<campaign_slug>:create`, and accepts:

```json
{
  "name": "<owner_prefix> | Product | Reddit | Variant | 2026-07-03",
  "daily_budget_usd": 12.5,
  "objective": "CLICKS",
  "status": "PAUSED",
  "extra": {
    "funding_instrument_id": "<id>"
  }
}
```

The budget example is illustrative, not a recommended default.
Reddit budget is actually set on ad groups. `daily_budget_usd` is kept as the
OS normalized budget input and campaign artifact value; use ad-group
`goal_value` in microcurrency for live spend.

## Account diagnostics

`GET /ads/reddit/account` retains profiles in `data.raw` and funding instruments
in `data.funding_instruments`. `data.provider_account` adds the configured
provider account's `id`, `currency`, `time_zone_id`, `admin_approval` and
`suspension_reason` under its own `data`, plus `field_availability` and
`retrieved_at`. It has no account selector and excludes account contacts and
other private provider fields. `GET /ads/reddit/raw/account` returns that same
safe provider-account object directly inside the OS envelope.

Check `provider_account.available` first. Missing/invalid fields are `null` with
availability `unavailable`; an available, explicit `suspension_reason: null`
means Reddit returned no suspension reason. On a failed details read, availability
is false with a safe reason/status; existing profile/funding results remain.
Neither profiles nor a successful funding read supplies a missing timezone.
Use the returned account timezone as context, separately from the report's
timezone. This read does not expose a daily-budget reset event, private auction
decisions or every account cap. Missing limits are unknown, not unlimited.

## Campaign List Pagination And Readback

`GET /ads/reddit/campaigns` is a list endpoint. Reddit may return a paginated
empty first page with a `next_url`; an empty `campaigns` array on the first
response does not prove that a known campaign is missing.

For selected campaign lifecycle checks, prefer direct readback by id:

```bash
GET $OS_URL/ads/reddit/raw/campaigns/{campaign_id}
```

Use list pagination only when discovering campaigns. When a Reddit `next_url`
contains `page.token=<token>`, use the raw OS proxy with
`page_token=<token>` to advance pages:

```bash
GET $OS_URL/ads/reddit/raw/campaigns?page_token=<token>
```

## Raw Endpoints

Use:

```bash
GET/POST $OS_URL/ads/reddit/raw/{upstream_path}
```

Raw examples:

```bash
GET  $OS_URL/ads/reddit/raw/funding-instruments
GET  $OS_URL/ads/reddit/raw/profiles
GET  $OS_URL/ads/reddit/raw/pixel
GET  $OS_URL/ads/reddit/raw/campaigns/{campaign_id}
GET  $OS_URL/ads/reddit/raw/ad-groups?campaign_id=<campaign_id>
POST $OS_URL/ads/reddit/raw/ad-groups
GET  $OS_URL/ads/reddit/raw/ad-groups/{ad_group_id}
POST $OS_URL/ads/reddit/raw/ad-groups/{ad_group_id}
POST $OS_URL/ads/reddit/raw/ad-groups/{ad_group_id}/status
GET  $OS_URL/ads/reddit/raw/profiles/{profile_id}/posts
POST $OS_URL/ads/reddit/raw/profiles/{profile_id}/posts
GET  $OS_URL/ads/reddit/raw/posts/{post_id}
GET  $OS_URL/ads/reddit/raw/ad-groups/{ad_group_id}/ads
POST $OS_URL/ads/reddit/raw/ads
GET  $OS_URL/ads/reddit/raw/ads/{ad_id}
POST $OS_URL/ads/reddit/raw/ads/{ad_id}/status
GET  $OS_URL/ads/reddit/raw/reports
```

Body and query string are forwarded through OS for `GET` and `POST` requests.
This is a proxy to implemented Tools routes, not arbitrary Reddit API paths.
Keep payloads in campaign artifacts before mutating. Successful raw calls return
an OS envelope: the provider object is `response.data.data`, its ID is
`response.data.data.id`; lists are `response.data.data[]`, with provider pagination
under `response.data.pagination`. Examples below show request bodies, not envelopes.

### Activation and status readback

`POST /ads/reddit/campaigns/{campaign_id}/launch` activates only that campaign.
It does not cascade to groups or ads. After launch authorization, activate each
selected child independently:

```text
POST /ads/reddit/raw/ad-groups/{ad_group_id}/status
POST /ads/reddit/raw/ads/{ad_id}/status
```

Both requests use `{"status":"ACTIVE"}`, without a `data` wrapper. Read each
object back by ID. Distinguish:

Campaign ACTIVE and PAUSED writes return `mutation_accepted`, `mutation_accepted_at`,
`status_confirmed` and actual readback. Campaign pause confirmation requires
the readback to show configured PAUSED; accepted/pending is not a confirmed stop.
ACTIVE status writes additionally return
`activation_confirmed`, `confirmation` (confirmed/pending/unconfirmed), actual
`configured_status`, `readback`, and `readback_at` when available. Campaign
launch exposes these under `data.raw`; raw child status routes under `data`.
HTTP 200 with `activation_confirmed=false` is not successful activation.
The API retries transient request errors only, with bounded backoff/Retry-After,
then performs bounded GET checks for delayed status convergence. No second write
is sent after acceptance. After an error without acceptance, read before retrying.
Follow `references/workflows/launch.md` for pending confirmation and receipts.

`GET /ads/reddit/campaigns/{id}/status` reads that exact owned campaign and
returns `provider_observation`: configured/effective/delivery codes, successful
`observed_at`, latest `last_checked_at`, availability and a safe failure reason.
These clocks describe the read, not when Reddit changed state or served an
impression. Successful owned reads refresh the Registry snapshot using its
pre-read revision, so a late read cannot overwrite a newer internal pause.
The regular reconciliation cycle also checks registered campaign IDs independently
of spend reports. No advertising mutation is performed by a status read.

Normalized campaign lists retain the legacy `status` and add separate
`configured_status`, `effective_status`, `delivery_status` and `observed_at`.
Use the separate fields for restrictions; configured ACTIVE alone never proves
delivery. The raw response remains available.

- `configured_status`: the object's own requested on/off state;
- `effective_status` and `delivery_status`: provider-reported serving/review
  state, including parent restrictions;
- `rejection_reason`: provider rejection details, when present.

Reddit can return ACTIVE configuration alongside stale-looking pause flags in
ad delivery status. Re-read the ad and its parents, retaining timestamps and raw
fields. If they still disagree, report inconsistent provider readback: do not
claim delivery, silently discard restrictions, or repeat activation/toggle
pause/recreate objects to clear flags. Pending approval alone does not prove
that review has started; see `references/workflows/launch-ready.md`.

### Targeting discovery

Read the current interest taxonomy before choosing an interest ID:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/ads/reddit/targeting/interests" -sS
```

`response.data.data[]` contains provider `id`, `name` and `category`, for example
`{"id":"programming_v3","name":"Programming","category":"Technology & Computing"}`.
Use the ID returned by the current catalog, not the display name or a guessed
`t2_...` ID. `GET /ads/reddit/raw/targeting/interests` returns the same catalog.
The lookup is read-only, needs `ads` scope, and neither reserves budget nor
validates an ad group. An empty result or provider error is not permission to
invent an ID or use a paid write as a lookup.

OS currently exposes neither community targetability lookup nor audience forecasts
or a validate-only group endpoint. Search/scrape can establish community relevance,
not Ads eligibility or reach. Record these as unverified; do not probe paid writes
or silently broaden targeting. An approved creation can return provider validation
errors; report rejected communities without substituting others.

### Create an ad group on pause

`POST /ads/reddit/raw/ad-groups`, for an existing non-CBO `CLICKS` campaign:

```json
{
  "data": {
    "campaign_id": "<owned-campaign-id>",
    "name": "<group-name>",
    "configured_status": "PAUSED",
    "bid_strategy": "BIDLESS",
    "bid_type": "CPC",
    "goal_type": "DAILY_SPEND",
    "goal_value": 12500000,
    "start_time": "<chosen-start-YYYY-MM-DDTHH:MM:SSZ>",
    "conversion_pixel_id": "<pixel-id>",
    "targeting": {
      "geolocations": ["US"],
      "communities": ["<approved-subreddit-name>"],
      "locations": ["FEED"],
      "expand_targeting": false
    }
  }
}
```

Use the requested budget/targeting; `12500000` means USD 12.50/day.
`BIDLESS` has no CPC ceiling; omit `bid_value` entirely. Placement is
`targeting.locations` (`FEED` and/or `COMMENTS_PAGE`), not `placements`.
`expand_targeting: false` disables automatic expansion. Set `start_time` to an
explicit ISO-8601 UTC timestamp, not `null`; omit `end_time` when no end is intended.
The live create API rejects null start times despite the nullable upstream schema;
OS rejects this before reserving a wallet hold. For a bounded window, also supply
an explicit `end_time`. Dates do not grant launch permission: keep campaign, group
and ads PAUSED. Do not send a report-only `time_zone_id` in the group body.

Read available Pixel IDs from `GET /ads/reddit/raw/pixel`. Reddit now requires
`conversion_pixel_id` for all groups; selecting it does not prove that website
Pixel/CAPI tracking works or change `CLICKS` into conversion optimization.
[Provider group schema](https://ads-api.reddit.com/docs/v3/api/create-ad-group).

Use the requested targeting values and verify provider acceptance.
Communities are not universally required by this skill; do not invent a
community to satisfy a template or silently broaden targeting after rejection.

Creation reserves `ceil(goal_value / 10000)` USD cents in the wallet **before**
the provider call, even for PAUSED groups: USD 12.50/day reserves USD 12.50, not an amount
multiplied by the scheduled days. This is a hold, not spent money. Posts/ads do
not add budget holds. Check `/wallet/balance` before and after; an uncertain
provider outcome needs readback, not another reservation/create attempt.

`POST /ads/reddit/raw/ad-groups/{ad_group_id}` updates fields (typically
`targeting`) on an existing ad group without creating a replacement — this is
the legal repair path when a live ad group's targeting needs narrowing.
`goal_value`/`goal_type` are rejected on this route since the wallet hold is
only reserved at ad-group creation. No supported in-place budget-change route
is exposed here. Report that limitation; a new group is a distinct authorized
operation with additional hold/learning consequences, not an automatic repair.
`configured_status` is rejected too — use
`POST /ads/reddit/raw/ad-groups/{ad_group_id}/status` so the Registry's
tracked status (and the wallet hold it releases on teardown) stays in sync
with the live ad group.

### Update targeting on an existing group

Read `GET /ads/reddit/raw/ad-groups/{ad_group_id}` first and save the current
targeting and status. Prepare the complete intended **writable targeting** in
`data.targeting`, preserving approved geo, communities, placements
(`locations`), exclusions, existing interests and `expand_targeting` unless the
authorized change explicitly replaces them. Do not copy the entire provider
response: IDs, delivery state and other managed fields are not update inputs.
The OS wrapper forwards the payload as provider PATCH; it does not merge arrays
or guarantee that omitted nested fields survive.

For example, only if these are the approved complete targeting settings:

```http
POST /ads/reddit/raw/ad-groups/{ad_group_id}
Content-Type: application/json

{"data":{"targeting":{"geolocations":["US"],"communities":["learnprogramming"],"interests":["programming_v3"],"locations":["FEED"],"expand_targeting":false}}}
```

Do not send budget, bid, status, schedule or creative fields for a targeting-only
change, and do not create a replacement group. Read the same group back after
the update; compare all intended targeting and unchanged status, saving both
responses. After an ambiguous failure, read before retrying. If unchanged fields
cannot be represented safely, stop and report the exact limitation.

Do not describe adding interests to communities as guaranteed audience broadening
or narrowing. Reddit's published guidance conflicts on mixed-type AND/OR logic;
the catalog establishes valid IDs, not combination semantics or audience size.
Record that uncertainty instead of promising reach or silently changing targeting.

## Asset Upload

Upload a rendered creative with multipart field **`file`** (scope `tools`):

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/tools/ad-assets/upload" -sS  \
  -F 'file=@creative.png;type=image/png'
```

Let curl set the multipart boundary. OS `response.data` contains
`{"url":"https://<cdn>/<key>","key":"<key>","size_bytes":12345,"content_type":"image/png"}`.
Use `response.data.url` as `media_url`. Images (PNG/JPEG/WebP) are limited to
10 MiB; MP4/WebM to 100 MiB. The upload endpoint checks MIME/size, not dimensions
or Reddit eligibility. Our PNG templates support **1080×1350 and 1080×1080**;
match the selected template and still check provider acceptance. Save the URL;
each upload creates a new asset. Do not use arbitrary public image hosts.

### Create an image post, then its paused ad

`POST /ads/reddit/raw/profiles/{profile_id}/posts` (use a profile from `/raw/profiles`):

```json
{
  "data": {
    "headline": "<approved-headline>",
    "type": "IMAGE",
    "allow_comments": false,
    "content": [{
      "media_url": "https://<cdn>/<uploaded-key>",
      "destination_url": "https://<product>/<path>?utm_source=reddit&utm_medium=paid_social&utm_campaign=<slug>&utm_content=<asset>",
      "call_to_action": "Learn More"
    }]
  }
}
```

The field is `headline`, not `title`; CTA is exactly **`Learn More`**, not
`LEARN_MORE`. `display_url` is optional; if supplied, match the destination domain.
This creates the profile's advertising creative, not a submission to the targeted
subreddit. There is no `promoted_only` switch in this endpoint; a `post_url` may
be public, so do not promise a private draft. Comments follow the chosen
`allow_comments` setting. OS uses Reddit's legacy [Create Post schema](https://ads-api.reddit.com/docs/v3/api/create-post),
not the newer structured-post payload.

`POST /ads/reddit/raw/ads`:

```json
{
  "data": {
    "ad_group_id": "<owned-group-id>",
    "name": "<ad-name>",
    "post_id": "<returned-t3-id>",
    "click_url": "<same-complete-destination-with-UTMs>",
    "configured_status": "PAUSED"
  }
}
```

The campaign is linked through the group; no separate `campaign_id` is needed
on the ad. Use [Create Ad](https://ads-api.reddit.com/docs/v3/api/create-ad) fields,
then GET the existing campaign, group, post and ad IDs. In `response.data.data`,
check group `campaign_id`, budget, targeting and `configured_status`; post
`headline`, `content` and `type`; ad `ad_group_id`, `post_id`, `click_url` and
`configured_status`. Keep returned `effective_status`/review fields when present;
PAUSED does not mean approved or ready to deliver.

### Retries and uncertain writes

Campaign creation requires `Idempotency-Key` (1–128 nonblank characters) on
both `POST /ads/reddit/campaigns` and `POST /ads/reddit/raw/campaigns`. OS forwards
the header; tools stores the campaign operation durably in its database, like
Google Ads. Save the key and exact request in campaign artifacts before sending.
A same-key, same-payload replay returns the same campaign and resumes unfinished
registration/quota accounting without another provider create. A different
payload with that key returns `409`; do not mint a new key to bypass it.

For `reddit_campaign_create_not_sent` (OAuth preparation failed before the
campaign request), retry the saved payload and key after backoff. An explicit
provider `429` also permits the same-key retry; honor `retry_after` when present.
The gateway does not automatically retry campaign writes.

The normalized response exposes `data.campaign_id`; the raw route exposes
`data.data.id`. Store that ID immediately. For `operation_in_progress`, wait and
retry with the same key. `reddit_campaign_create_outcome_unknown` means the write
started but no response was durably saved; `reddit_campaign_create_readback_invalid`
means the saved response has no trustworthy ID. Stop and request Egbe team
reconciliation in either case. Do not issue a replacement create.

This durable guarantee applies only to campaign creation. Ad-group, post and ad
creates still use a short-lived tools success cache; OS now forwards their keys,
but this is not durable recovery. After timeout/5xx on those writes, inspect saved
IDs and provider readback; reuse only unambiguously confirmed owned objects.
An empty owned list is not proof that a provider write failed.

## Results

`GET /ads/reddit/campaigns/{campaign_id}/results` returns normalized metrics
plus raw report data. For ad-group or ad-level decisions, use raw reports with
the needed breakdown and then match object ids client-side.

Retain the request, report timezone, `metrics_updated_at` and every pagination
page through `next_url: null`. Inspect the **actual returned** `date`/`hour`
buckets before labeling coverage: hourly UTC request syntax does not prove that
the response contains only those hours. Provider responses can include wider
calendar dates; use the returned buckets for the intended day/hour comparison
and do not sum overlapping query results. A total without date/hour breakdown
cannot establish the last delivery hour.

`metrics_updated_at` is a provider update timestamp, not the last impression or
a completeness watermark. A last nonzero hour is a reported bucket, not an
individual event timestamp. Reddit documents that metrics can take up to six
hours to stabilize and historical totals can change; a missing current-day row
does not prove final zero billing. See [Get A Report](https://ads-api.reddit.com/docs/v3/api/get-a-report).

## Error Handling

- Account/resource reads and supported reports retry transient network failures,
  429 and 5xx up to three attempts with bounded backoff. A 401 allows one token
  refresh within that budget; a generic 403 does not trigger refresh or retry.
  Persistent provider failures remain errors, never zero-spend observations;
  Wallet reconciliation retries on its normal schedule.
- `401` / `403`: OS key lacks scope or provider access is unavailable.
- `404` on object read: wrong object id or object is not owned by this instance.
- Funding unavailable: stop as `INPUTS_BLOCKED`.
- Write failure after campaign creation: apply the saved-operation recovery rules in
  `references/workflows/build-paused.md`.
