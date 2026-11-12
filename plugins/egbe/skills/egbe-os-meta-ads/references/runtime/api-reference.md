# Meta Ads OS API Reference

Use this file when a Meta workflow needs the exact OS endpoint shape for raw
Meta operations. This is not a non-OS Meta setup guide.

Runtime is OS-only:

- `OS_URL`
- `OS_API_KEY`
- `Authorization: Bearer $OS_API_KEY`

Do not ask a product agent for Meta app IDs, access tokens, page IDs, pixel IDs,
or ad account IDs. OS owns those server-side.

## Choosing The Endpoint

Use normalized endpoints when they cover the job:

```bash
GET  $OS_URL/ads/meta/account
GET  $OS_URL/ads/meta/campaigns
POST $OS_URL/ads/meta/plan
POST $OS_URL/ads/meta/apply
GET  $OS_URL/ads/meta/campaigns/{campaign_id}/state
POST $OS_URL/ads/meta/campaigns/{campaign_id}/launch
POST $OS_URL/ads/meta/campaigns/{campaign_id}/pause
GET  $OS_URL/ads/meta/campaigns/{campaign_id}/results
```

For a reused configuration snapshot, add `include_configuration=true` to the
state read. For current-inclusive campaign history, use `results?period=MAXIMUM`
or the supported explicit report dates. [Monitoring](../workflows/monitoring.md)
defines the two-read safety path and native rate-limit context;
[insights](insights-reference.md) defines query windows, availability and currency.

Use raw endpoints when Meta-specific objects are needed:

```bash
GET  $OS_URL/ads/meta/raw/{path}
POST $OS_URL/ads/meta/raw/{path}
```

The raw path is still an OS endpoint. It is allowed for Meta-specific resource
shapes, but it must not be replaced by non-OS calls.

## Targeting Search

Use this when a Meta workflow needs platform IDs for interests, behaviors, geo,
locales, or other targeting categories.

```bash
GET $OS_URL/ads/meta/raw/targetingsearch?q=<name>&type=adinterest&limit=25
```

Parameters:

- `q`: search text. Some Meta search types allow it to be empty.
- `type`: Meta Graph search type. Common values include `adinterest`,
  `adTargetingCategory`, `adgeolocation`, and `adlocale`.
- `limit`: result cap, 1-100. Default is 25.
- `targeting_class`: optional Meta `class` parameter, used with some
  `adTargetingCategory` lookups.

The response is Meta's targeting search payload. Preserve the returned `id`,
`name`, `key`, `audience_size`, and related fields in launch artifacts, then use
the appropriate returned identifier inside the ad set `targeting` object.

Examples:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/ads/meta/raw/targetingsearch?q=fitness&type=adinterest&limit=5" -s

OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/ads/meta/raw/targetingsearch?type=adTargetingCategory&targeting_class=behaviors&limit=25" -s
```

Do not hardcode remembered targeting IDs. Resolve them through OS when the
segment depends on a concrete Meta interest, behavior, geo, or locale ID.

## Read Operations

```bash
GET $OS_URL/ads/meta/raw/campaigns/{campaign_id}
GET $OS_URL/ads/meta/raw/campaigns/{campaign_id}/adsets
GET $OS_URL/ads/meta/raw/campaigns/{campaign_id}/ads
GET $OS_URL/ads/meta/raw/adsets/{adset_id}
GET $OS_URL/ads/meta/raw/ads/{ad_id}
```

Existing object reads are owner-scoped. If OS did not create/register the object
for this instance, a read or mutation can fail even when the upstream object
exists.

## Create Campaign

For image campaign trees prefer plan/apply; see
[paused build](../workflows/build-paused.md). Raw/individual creation is for a
currently authorized operation the declarative spec cannot express, not an
approval or budget-guard bypass. The following is an illustrative request,
not a budget recommendation:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/ads/meta/campaigns" -s -X POST  \
  -H "Content-Type: application/json" \
  -d '{
    "name": "2026-07-02-product-segment-offer",
    "product_slug": "product-slug",
    "daily_budget_usd": 12.5,
    "objective": "OUTCOME_TRAFFIC",
    "status": "PAUSED",
    "extra": {"special_ad_categories": []}
  }'
```

The normalized route accepts dollars and converts to Meta cents.

If a raw campaign create is ever needed, pass Meta-native cents:

```bash
POST $OS_URL/ads/meta/raw/campaigns
{
  "name": "2026-07-02-product-segment-offer",
  "product_slug": "product-slug",
  "objective": "OUTCOME_TRAFFIC",
  "status": "PAUSED",
  "special_ad_categories": []
}
```

Place budget at the requested level; do not set conflicting campaign
and ad-set budgets. The declarative spec uses `budget_level` to select one.

## Create Ad Set

```bash
POST $OS_URL/ads/meta/raw/adsets
{
  "payload": {
    "name": "PT | broad buyers | feeds+stories",
    "campaign_id": "<campaign_id>",
    "daily_budget": 1250,
    "optimization_goal": "LANDING_PAGE_VIEWS",
    "billing_event": "IMPRESSIONS",
    "targeting": {
      "geo_locations": {"countries": ["PT"]},
      "age_min": 25,
      "age_max": 54,
      "publisher_platforms": ["facebook", "instagram"],
      "facebook_positions": ["feed"],
      "instagram_positions": ["stream", "story", "reels"]
    },
    "status": "PAUSED"
  }
}
```

Rules:

- `daily_budget` is Meta cents; the example `1250` is USD 12.50.
- Lifetime budgets are not supported in the default OS flow.
- Daily-budget ad sets should not include `end_time`.
- OS may inject configured pixel/dataset IDs into `promoted_object` when the
  server-side Meta configuration supports it.
- Preserve the authorized targeting values.

## Upload Image

Upload approved PNG/JPEG creative to receive `image_hash`:

```bash
POST $OS_URL/ads/meta/raw/adimages
{
  "image_base64": "<base64_png_or_jpeg>",
  "filename": "creative-01.png"
}
```

The response is expected to include a stable `hash`. Every image ad must carry
that hash at:

```text
creative.object_story_spec.link_data.image_hash
```

Do not create an intended image ad without an `image_hash`.

## Upload Video

Upload an approved completed MP4 creative to receive `video_id`:

```bash
POST $OS_URL/ads/meta/raw/advideos
{
  "video_base64": "<base64_mp4>",
  "filename": "03-talking-head.mp4"
}
```

The response is expected to include a stable `video_id`. This endpoint uploads a
finished video; it does not define video generation. Use it only after an
approved OS generation capability or founder-provided asset produced the MP4.

## Create Ad

```bash
POST $OS_URL/ads/meta/raw/ads
{
  "payload": {
    "name": "angle | ai-lifestyle | creative-01.png",
    "adset_id": "<adset_id>",
    "creative": {
      "object_story_spec": {
        "link_data": {
          "message": "Primary text...",
          "link": "https://product.example/?utm_source=meta&utm_medium=paid_social&utm_campaign=...",
          "image_hash": "<image_hash>",
          "call_to_action": {
            "type": "LEARN_MORE",
            "value": {"link": "https://product.example/?utm_source=meta&utm_medium=paid_social&utm_campaign=..."}
          }
        }
      }
    },
    "status": "PAUSED"
  }
}
```

OS injects the configured page ID when the server-side Meta configuration has
one and the payload omits it. The workflow should still record whether page or
Instagram linkage was missing as a launch limitation when relevant.

## Update Existing Ad

Use this only when the launch state already has an ad ID and a targeted repair
is needed, such as attaching a repaired creative spec:

```bash
POST $OS_URL/ads/meta/raw/ads/{ad_id}
{
  "payload": {
    "creative": {
      "object_story_spec": {
        "link_data": {
          "link": "https://product.example/?utm_source=meta&utm_medium=paid_social&utm_campaign=...",
          "image_hash": "<image_hash>",
          "message": "Primary text..."
        }
      }
    }
  }
}
```

Prefer creating clean objects in the first launch attempt. Use updates for
recovery, not as the normal happy path.

## Update Existing Ad Set

Use this to narrow/correct `targeting` (or `name`) on a live ad set without
burning an `adset_creates` slot on a replacement:

```bash
POST $OS_URL/ads/meta/raw/adsets/{adset_id}
{
  "payload": {
    "targeting": {
      "geo_locations": {"countries": ["PT"]},
      "age_min": 25,
      "age_max": 54
    }
  }
}
```

`daily_budget` and `lifetime_budget` are rejected here — use the dedicated
`POST $OS_URL/ads/meta/raw/adsets/{adset_id}/budget` route so budget changes
go through the wallet-hold guardrail. `status` is rejected too — use
`POST $OS_URL/ads/meta/raw/adsets/{adset_id}/status` so the Registry's
tracked status stays in sync with the live ad set.

## Launch And Pause

Meta delivery requires all three levels to be active:

```bash
POST $OS_URL/ads/meta/raw/ads/{ad_id}/status      {"status": "ACTIVE"}
POST $OS_URL/ads/meta/raw/adsets/{adset_id}/status {"status": "ACTIVE"}
POST $OS_URL/ads/meta/campaigns/{campaign_id}/launch
```

Pause in the reverse or safest practical order:

```bash
POST $OS_URL/ads/meta/raw/ads/{ad_id}/status       {"status": "PAUSED"}
POST $OS_URL/ads/meta/raw/adsets/{adset_id}/status {"status": "PAUSED"}
POST $OS_URL/ads/meta/campaigns/{campaign_id}/pause
```

Allowed status values are `ACTIVE`, `PAUSED`, `ARCHIVED`, and `DELETED`.

## Budget Updates

Change budget only within the current authorization. Use these dedicated routes
so wallet-hold handling is applied; ordinary ad-set update rejects budget fields.

```bash
POST $OS_URL/ads/meta/raw/campaigns/{campaign_id}/budget {"daily_budget": 1250}
POST $OS_URL/ads/meta/raw/adsets/{adset_id}/budget       {"daily_budget": 1250}
```

Rules:

- `daily_budget` is Meta cents.
- Lifetime budgets are rejected by the OS default flow.
- Per-operation budget guardrails are enforced server-side.
- The configured `meta_ads_max_budget_cents_per_operation` is a server
  per-operation limit, not a channel testing budget. Its source default is
  10,000 cents; the deployed value may differ. Resolve a returned blocker
  without guessing the live value or bypassing the guard.

## Pixels And Custom Conversions

Custom conversions are optional for traffic tests; create one when selecting a
conversion-objective campaign. The install
and event contract is `references/runtime/pixel-install.md`; the endpoints below
are the raw operations behind it.

```bash
GET  $OS_URL/ads/meta/raw/pixels
GET  $OS_URL/ads/meta/raw/pixels/{pixel_id}
GET  $OS_URL/ads/meta/raw/tracking?product_slug=<product_slug>

GET  $OS_URL/ads/meta/raw/customconversions?offset=0&limit=50
GET  $OS_URL/ads/meta/raw/customconversions/{conversion_id}
POST $OS_URL/ads/meta/raw/customconversions
Idempotency-Key: <stable-key-for-this-conversion>
{
  "name": "Product - Activation",
  "product_slug": "product-slug",
  "event_name": "Activation",
  "custom_event_type": "OTHER"
}
```

Server-side OS configuration owns the pixel/dataset binding. Do not ask the
product agent for pixel credentials. Product code reads the pixel ID from
`NEXT_PUBLIC_META_PIXEL_ID`, populated from `/tracking` before building the app;
follow [pixel installation](pixel-install.md) for public configuration and verification.

Send the `event_parameters` returned by `/tracking` on pixel events. Conversion
creation returns the same parameters and a Meta ID. OS builds the rule from the
product and event. List/read expose only this project's registered conversions;
continue listing at `next_offset` until it is null. Retry creation with the same
key and payload; an unconfirmed outcome needs recovery by the Egbe team, not a new key.
Each list/detail item includes `eligibility.status`: `eligible`, `ineligible`
(for example, archived or changed rule), or `unavailable` (readback could not be
verified). Only `eligible` goals can be bound. Other items remain visible with
`code`, `message`, `retryable`, and `next_action`; a successful list/read is not
proof that every goal is usable.
`POST .../pixels` is intentionally absent from the product workflow: creating a
pixel is an OS migration operation, not a product launch step.

For `OFFSITE_CONVERSIONS`, include the recorded id in the declarative spec:

```json
{
  "objective": "OUTCOME_SALES",
  "optimization_goal": "OFFSITE_CONVERSIONS",
  "custom_conversion_id": "<verified product conversion id>"
}
```

Use the same `product_slug` on the campaign and conversion. OS verifies ownership,
product, shared pixel, rule and active conversion state before binding or
activation, and rechecks on apply after plan. An unverified or changed rule
blocks conversion optimization; a traffic campaign needs no conversion.
Campaign activation checks groups whose own status is `ACTIVE`; it leaves
`PAUSED`/`ARCHIVED`/`DELETED` groups unchanged. Activating an individual group
checks its goal again.

Eligibility failures return the reason and `next_action` in the OS error
`data`. With `retryable: true`, retry with backoff up to three times,
keeping the same create key/payload; report the blocker if it persists. With
`retryable: false`, address the stated cause before retrying. Campaign errors
identify the blocking group and, when available, conversion. A `plan` response
reports the same details under `blockers[].detail` instead of applying changes.

## Common Error Classes

| Error | Meaning | Action |
|---|---|---|
| `meta_budget_guardrail_exceeded` | Budget exceeds OS guardrail | Lower budget or get Egbe admin approval |
| `meta_lifetime_budget_not_supported_use_daily_budget` | Default flow rejects lifetime budget | Use `daily_budget` in cents |
| `meta_end_time_not_supported_in_default_daily_budget_flow` | Daily-budget ad set included `end_time` | Remove `end_time` |
| owner/404 on object read or mutation | Object is not registered to this instance | Use IDs created by the current OS workflow or record blocker |
| upstream permission/configuration error | OS server-side Meta binding is not ready | Stop and report OS configuration blocker |

## Output Discipline

Every raw operation that mutates Meta state must update durable launch artifacts:

- operation timestamp
- endpoint path
- request intent, not secrets
- returned object ID
- status after mutation
- known limitations or compromises

Do not print credentials, access tokens, page IDs, pixel IDs, or account IDs in
founder-facing summaries.
