# LinkedIn OS API

Base `$OS_URL/ads/linkedin`, bearer `$OS_API_KEY`; provider tokens stay in OS.
Writes require `Idempotency-Key` (1–128 characters). Same key and changed payload
is 409. Responses use the OS envelope; inspect data, not only HTTP 200.

## Read and discovery

- `GET /account`, `GET /readiness`.
- `GET /targeting/facets`.
- `GET /targeting/entities?facet=locations&query=United%20States&language=en&country=US`.
  Searchable facets require `query`; `entity_type` is optional and should only
  be supplied when supported by provider facet metadata.
- `GET /targeting/entities?facet=seniorities` also works for `jobFunctions` and
  `staffCountRanges`: returns the facet's options via `adTargetingFacet` rather
  than typeahead. Omit `query` and `entity_type` for these listings. No mutation
  occurs. [Provider targeting contract](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads/advertising-targeting/ads-targeting).
- `POST /audience-estimate`: `{"targeting":{"include":{"locations":["urn:li:geo:<resolved-id>"]}}}`.
- `POST /budget-pricing`: same targeting plus `format` and `daily_budget_usd`;
  provider returns minimum/maximum/suggested bid and daily-budget limits.
- `GET /campaign-groups`, `/campaigns`, `/creatives`, `/images`:
  owned only, `offset=0&limit=20`, follow next_offset until null.
- `GET /<collection>/<id>`; `GET /creatives/<id>/content` resolves its owned
  Sponsored Content reference. IDs are numeric strings except image URNs.
  Inspect raw resource fields including moderation and serving reasons.

## Create a group

`POST /campaign-groups`:

```json
{"product_slug":"example-product","name":"LinkedIn pilot","schedule":{"start":1800000000000}}
```

Schedule values are Unix milliseconds. Use actual approved timestamps, not this
example. Groups have no shared budget; each native campaign owns its budget.
OS creates groups in DRAFT (non-serving); there is no caller status field.
LinkedIn permits initial ACTIVE or DRAFT, not PAUSED. Launch is a separate,
explicitly authorized operation. [Provider group lifecycle](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads/account-structure/create-and-manage-campaign-groups).

## Create a campaign

`POST /campaigns`:

```json
{
  "group_id":"123",
  "name":"LinkedIn pilot — image",
  "format":"SINGLE_IMAGE",
  "daily_budget_usd":30,
  "cpc_bid_usd":3,
  "locale":{"language":"en","country":"US"},
  "targeting":{"include":{"locations":["urn:li:geo:103644278"]},"exclude":{}},
  "schedule":{"start":1800000000000}
}
```

Illustrative IDs must be resolved/owned. format: SINGLE_IMAGE or TEXT_AD.
Created status is DRAFT, including beneath a DRAFT group; launch is separate.
WEBSITE_VISIT/manual CPC, no expansion/offsite delivery.
USD amounts are decimal dollars, not micros; non-USD accounts are rejected.
`PATCH /campaigns/{id}` accepts only changed name, daily_budget_usd, cpc_bid_usd,
targeting or schedule; omit unchanged fields, don't send null. Targeting is a full
replacement. No hidden account-wide changes or budget increases.

## Upload and create creative

`POST /images`: `{"product_slug":"example-product","image_base64":"<base64 PNG/JPEG>"}`.
Maximum 5 MB decoded; no data URI or remote URL. Save the returned image URN,
then GET until AVAILABLE before using it. Signed upload URLs remain internal.

`POST /creatives`:

```json
{"campaign_id":"456","name":"Benefit variant A","image_id":"urn:li:image:<uploaded-id>","headline":"A useful product","text":"A concrete benefit.","destination_url":"https://your-product.example/path?utm_source=linkedin&utm_medium=paid_social&utm_campaign=linkedin-pilot&utm_content=benefit-a","cta":"LEARN_MORE"}
```

Image and campaign must belong to the same product. For Text Ad: headline≤25,
text≤75; for Single Image gateway bounds are headline≤200, text≤3000.
OS sets `intendedStatus=DRAFT` for both formats; there is no caller status field.
CTA: LEARN_MORE, SIGN_UP, DOWNLOAD, REGISTER, REQUEST_DEMO (Single Image only).
`PATCH /creatives/{id}` accepts changed `name` for both formats, and optional
`headline`, `text`, `image_id`, `destination_url` for Text Ads (same Text limits).
Omitted fields and delivery status are preserved. Single Image copy/media changes
return 409 and require an explicitly approved replacement, not implicit duplication.

## Delivery and reports

`POST /campaign-groups/{id}/launch|pause`,
`POST /campaigns/{id}/launch|pause`,
`POST /creatives/{id}/launch|pause`; no body, Idempotency-Key required.
Follow launch workflow for parent order and wallet authorization.

`GET /campaigns/{id}/results?date_from=2026-09-01&date_to=2026-09-11`:
inclusive UTC dates, today allowed, at most 366 days per request.
Returns campaign_id, dates, currency, metrics (impressions/clicks/spend decimal
in account currency), raw data, observed_ranges, data_status, fetched_at and
freshness. Not a conversion report.

## Optional conversions

- POST `/conversion-rules`: `{"campaign_id":"456","name":"Signup","method":"CONVERSIONS_API","type":"SIGN_UP"}`.
  Method INSIGHT_TAG creates an event-specific browser rule; no URL rules.
  Optional attribution_type: LAST_TOUCH_BY_CONVERSION (default) or
  LAST_TOUCH_BY_CAMPAIGN; post_click_days=30 and view_through_days=7, each 1/7/30.
  Creation does not associate or activate campaigns.
- GET `/conversion-rules` (owned, offset/limit); GET `/conversion-rules/{id}`.
- PATCH `/conversion-rules/{id}`: changed name, enabled, post_click_days,
  view_through_days, attribution_type only. Method/product identity are immutable.
- GET `/conversion-rules/{id}/browser-tag`: owned browser rule + existing
  public Insight Tag and event_id_prefix, not shared account/domain management.
- GET/PUT/DELETE `/campaigns/{campaign_id}/conversion-rules/{id}`: inspect,
  attach or detach one same-product pair. No request body; writes require key.
- POST `/conversion-events`: `{"conversion_id":"789","event_id":"signup:opaque-id","happened_at":1800000000000,"email_sha256":"<64 lowercase hex characters>"}`.
  Replace example time/identity with a real outcome within the past 90 days.
  Optional linkedin_tracking_uuid, value ({currency_code, amount}), validate_only.
  At least one genuine matching identifier is required. See the conversions
  workflow for hooks, prefix/dedupe, retries and privacy.
- GET `/conversion-events/{receipt_id}`: durable delivery status, not a
  provider attribution lookup. Management is ads-only; rule GET and event
  send/receipt GET also accept analytics for deployed product credentials.
- GET `/campaigns/{campaign_id}/conversion-rules/{id}/results`: explicit
  date_from/date_to, inclusive UTC, at most 366 days. String decimal counts
  conversions/post_click_conversions/post_view_conversions; metrics=null when
  no matching rows, provider errors stay errors. No bidding changes.

## Errors and recovery

- 401/403: Egbe admin OAuth/app/account/Page permission, not a reason to switch keys.
- 404: unknown or unowned resource; ownership checks precede mutations.
- 400/422: invalid schema, provider minimum, targeting or format; inspect exact error.
- 409: conflict, unresolved operation, parent state, image processing, readback
  mismatch or unavailable wallet reservation. Follow its message; don't bypass.
- 429: quota/provider throttling; retry with backoff and same operation identity.
- GET transient transport/429/5xx: bounded retry, at most three attempts. Long
  Retry-After defers to the caller; 401/403 aren't repeatedly retried.
- Write transport failure: outcome may be unknown; preserve key and read back.
  No blind transport retries for mutations. Event receipts distinguish confirmed
  retryable refusal from uncertain delivery; see the conversions workflow.
- Same key after a later update: superseded; does not re-activate paused resources.

First defaults: 5 campaign creations/month, 50 other management mutations/day.
Reads do not consume write quotas. Pause is exempt. Image uploads/group/creative
creation and conversion configuration count as management mutations. Disable/
detach are exempt; runtime event delivery does not consume campaign-write quota.
Effective limits come from the caller's
binding, not a hardcoded assumption in the agent.
