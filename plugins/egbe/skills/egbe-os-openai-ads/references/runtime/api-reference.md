# OpenAI Ads API reference

Paths in this reference are relative to `$OS_URL/ads/openai` unless shown in full.
This is the API boundary, not the lifecycle checklist. Follow the selected workflow
for artifact updates and completion conditions.

Use `$OS_URL/ads/openai/...` with `Authorization: Bearer $OS_API_KEY`.
Requires the `ads` scope. Management and conversion provider keys stay inside
Egbe infrastructure; never request them for the product or call OpenAI directly.
This workflow works from any product repository, without scaffold or stages.

Read `GET /ads/openai/account` first. Successful authentication does not prove
billing setup, approval to serve, or access to conversion setup. The API returns
account currency/timezone; this version supports USD accounts and daily budgets
only. OpenAPI at `$OS_URL/openapi.json` is the exact request schema.

## Build and manage a campaign

Every mutation requires `Idempotency-Key`. Keep a stable key and the exact body
for each logical operation; reuse both after a timeout. An ambiguous create
returns a recovery error rather than blindly creating another object. Do not
use a new key to bypass it. Save returned IDs in the project's campaign records.

An unfinished mutation can return `openai_ads_operation_superseded` after a newer
command, or `openai_ads_provider_state_changed` after external drift. Do not
revive the old intent; read current state and reconcile with the latest authorized
request. `openai_ads_wallet_reservation_not_live` requires wallet/campaign review
before a newly authorized operation; retries do not renew expired reservations.

1. Resolve the desired geography with `GET /ads/openai/locations?query=...`.
2. `POST /ads/openai/campaigns`:

   ```json
   {"name":"Product launch","product_slug":"your-product","daily_budget_usd":25,
    "bidding_type":"clicks","location_ids":["<id returned by locations>"],"status":"PAUSED"}
   ```

   Select `clicks`, `impressions` or `conversions` before creation. Strategy and
   an oCPC optimization goal cannot be changed later. Conversion bidding
   additionally requires an owned `conversion_event_setting_id` and provider
   account access; ordinary traffic campaigns do not require tracking setup.
3. `POST /ads/openai/uploads` with `{product_slug,image_url}` for a public image.
   Use the returned `id` as `creative.file_id`.
4. `POST /ads/openai/ad-groups` with `{campaign_id,name,context_hints,bidding_config}`.
   `bidding_config` contains `billing_event_type` (`click` or `impression`) and
   `max_bid_micros`. For conversion bidding use `click`; the bid is CPA, while
   billing is still per click. With impressions the bid is CPM. Money here is
   integer micros in account currency, not dollars.
5. `POST /ads/openai/ads` with `{ad_group_id,name,creative}`. The complete creative
   is `{type:"chat_card",title,body,target_url,file_id}`: title 3–50 characters,
   body 1–100 characters. Use a real product destination with stable campaign UTMs.
   Read `/analytics/skill` for product attribution conventions. Keep captured
   `oppref` intact; UTMs do not replace the provider click identifier.

Resources are created paused. GET `/campaigns/{id}`, `/ad-groups/{id}` and
`/ads/{id}` for readback, including provider ad review state. List the same
collections with `offset` and `limit`; only owned resources are returned.
Group `campaign_id` and ad `ad_group_id` are filled from the durable Registry
binding if omitted by the provider. `parent_binding_source` is `registry` in that
case, or `provider_verified_against_registry` when provider and Registry agree.
A conflicting parent returns `openai_ads_parent_binding_mismatch`, never a silent
overwrite. These fields are included in create/update readbacks too.

Edit existing resources with POST to their by-ID endpoint. Campaign updates
accept `name`, `daily_budget_usd`, `location_ids`; ad-group updates accept `name`,
`context_hints`, `bidding_config`; ad updates accept `name`, full `creative`.
Do not recreate an ad merely to change its copy.

### Select campaign measurement goals without changing bidding

For an existing `clicks` or `impressions` campaign, POST `/campaigns/{id}` with:

```json
{"conversion_event_setting_ids":["<owned signup setting>","<owned purchase setting>"]}
```

This replaces the campaign's entire measurement selection; read the current IDs
first and preserve any still wanted. `[]` explicitly clears it; omission leaves
it unchanged. Egbe accepts up to 100 unique IDs (its bounded API limit, not a
claim about provider limits). Every setting and its source must belong to this
product/account, and the setting must be active. No settings are auto-attached.
Send only this field to keep bidding, budget, status and targeting unchanged;
the gateway verifies those invariants and the selected IDs in provider readback.
Use a recorded Idempotency-Key. A provider rejection or readback mismatch is not
successful attachment and does not authorize recreating or launching a campaign.
For `conversions` campaigns, the single optimization goal remains immutable.
See [official campaign update rules](https://developers.openai.com/ads/api-reference/campaigns#update-a-campaign).

When launch is authorized, keep the campaign paused while enabling the intended
children with `POST /ad-groups/{id}/status?status=active` and
`POST /ads/{id}/status?status=active`, then `POST /campaigns/{id}/launch`.
Launch reserves funds through the existing wallet. It does not promise delivery:
children, creative review, account/payment readiness and actual insights matter.
Pause using `/campaigns/{id}/pause`; child status also accepts `paused`.

Daily budget is an **average**, not a hard daily cap: with an unchanged budget,
provider spending can reach 2× per day and 7× over a full seven-day period.
The wallet reservation accounts for the possible daily maximum; it is not a
replacement for provider spend reconciliation or a guarantee of seven-day funds.
Provider market/bid restrictions may exceed the static schema minimum.
See the [minimum-budget note](../workflows/readiness.md#minimum-daily-budget) before
proposing a budget; a provider rejection during creation may reveal the current floor.

## Optional conversions

Use only when measurement or conversion optimization is part of the request.
For ordinary campaign creation, do not force this setup.

- `POST /conversion-sources` with `{product_slug,name}` creates a product-owned
  web source. Save its `id` and returned `resource.pixel_id`.
- `POST /conversion-settings` with `{source_id,name,event_type}` creates a goal.
  Supported events: `registration_completed`, `order_created`,
  `subscription_created`, `trial_started`, `lead_created`.
- GET `/conversion-sources` and `/conversion-settings` for owned configuration.
  Provider setup may return 403/404 when not enabled for the account. Report
  that blocker; do not borrow another product's pixel or create new API keys.

For browser tracking, use the returned public Pixel ID and follow the official
[Pixel instructions](https://developers.openai.com/ads/measurement-pixel).
Respect measurement consent; automatic advanced matching must not collect data
before consent. No conversion API credential belongs in the browser.

Server delivery is `POST /conversion-events` with:

```json
{"source_id":"<owned source id>","event_id":"<stable business event id>",
 "event_type":"registration_completed","timestamp_ms":1788951369000,
 "source_url":"https://your-product.example/signup/complete",
 "measurement_consent":true,"oppref":"<captured original value>","validate_only":true}
```

Use the real event time, not the sample. Capture `oppref` when present and the
Pixel's `__obref` cookie as optional `obref`, subject to consent. Omit unavailable
identifiers rather than inventing them. This release doesn't need raw email or
other customer PII. On payment events, optional `amount_minor` + `currency`
represent actual money (e.g. 2500 USD means $25), not micros. `plan_id` is optional
for subscription/trial events. Signup means successful account creation; purchase
means confirmed payment, not a Checkout redirect or trial start. Integrate with
the product's authoritative completion points; no automatic payment-gateway
conversion emission is provided by this release.

Start with `validate_only:true`, then send real events only when appropriate.
Reuse the same `event_id` as the browser Pixel's `event_id` for the same event
and source. API delivery dedupes by product/source/event identity, not just the
request key. GET `/conversion-events/{receipt_id}` reads delivery status.
Retries are caller-driven, bounded to five attempts with receipt backoff; there
is no hidden delivery worker. API acceptance does not prove attribution.

## Reports

GET `/campaigns/{id}/results?start_time=<unix seconds>&end_time=<unix seconds>`.
The gateway rounds the start down and the end up to full hours in the ad account
timezone, capped at the latest completed hour (never a future boundary).
Do not send future timestamps.
Use the returned `start_time`/`end_time` as the effective reporting period;
the currently incomplete hour is picked up on a later read. A period with no
completed hour returns `503 openai_ads_report_not_available_yet`, not zero.
Follow `next_cursor` as `after` until `has_more` is false before summing pages.
Response includes currency, timezone, period, fetch time and data availability.
`metrics` uses shared names (impressions, clicks, spend_usd, fractional ctr,
cpc_usd, conversions) with `metrics_scope:"page"`. It covers only returned rows:
sum all pages before reporting totals and recompute ratios from totals. Missing
metrics remain null; non-USD money is not relabeled USD. Delivery reports leave
conversions null; use the separate attribution report when needed.
`no_rows`, numeric zero, and request failure are different outcomes. Provider
freshness is unknown unless explicitly reported. General insights are delivery
metrics; never relabel clicks or accepted server events as attributed conversions.

GET `/campaigns/{id}/conversion-results` with the same Unix period for attributed
campaign totals. `conversions` means click-through conversions; view-through is
separate and must not be added to it. Account availability can limit this report.
This is a campaign total, not a breakdown by event setting. If signup and purchase
are both selected, do not label the total as signups or purchases or infer unique
customers. The exposed report has no event-setting filter. Use product analytics
for separate funnel counts and distinguish those from OpenAI-attributed totals.

Safe report/account reads retry transient network errors, 429 and 5xx up to
three attempts with bounded backoff. Long `Retry-After` values defer recovery
to a later request; errors are not converted into zero metrics. Writes and
conversion submissions are not automatically replayed by this transport.
Wallet reconciliation retries on its normal schedule and settles only the
unaccounted cumulative spend, including spend missed during a failed read.

This capability has no raw passthrough, lifetime budgets, product feeds or custom
audiences. Provider contracts: [Campaigns](https://developers.openai.com/ads/api-reference/campaigns),
[OpenAPI](https://developers.openai.com/ads/openapi.json),
[Conversions API](https://developers.openai.com/ads/conversions-api).
