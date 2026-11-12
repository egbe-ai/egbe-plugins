# Conversion actions, goals and reports

Conversion measurement is optional for an ordinary CPC campaign. Creating an
action, choosing campaign goals and changing bidding are separate operations.
Use only the operation requested; action configuration is not event delivery,
attribution, reliable training data or permission to launch.

## Choose or create an owned action

```http
GET /ads/google/conversion-actions?offset=0&limit=20
GET /ads/google/conversion-actions/{conversion_ref}
POST /ads/google/conversion-actions
Idempotency-Key: <stable key for this creation>
Content-Type: application/json
```

```json
{
  "campaign_ref":"1234567890:456",
  "name":"Account signup",
  "delivery_method":"browser",
  "category":"SIGNUP",
  "counting_type":"ONE_PER_CLICK"
}
```

List pagination has offset >=0 and limit 1–100. Reuse an appropriate owned action;
do not adopt unregistered account-wide actions by name. The campaign ref selects
its authoritative conversion account and product. A paused shell suffices and
is not modified. Optional product_slug at campaign creation binds actions for
reuse across that product. Older campaigns without it have exact-campaign
binding; do not silently broaden it.

Supported categories: SIGNUP, PURCHASE, SUBMIT_LEAD_FORM, CONTACT. Browser
(default) creates WEBPAGE; server creates UPLOAD_CLICKS. Counting is ONE_PER_CLICK
or MANY_PER_CLICK. Optional default_value and uppercase three-letter currency
must be paired, with nonnegative finite value. Choose the actual outcome and
counting behavior, not a UI click presented as a completed purchase.

Read `data.ref`, `resource` and `tag`. Browser tag includes ready,
conversion_id (AW-…), conversion_label, send_to and provider snippets. Use
returned values, not a tag ID derived from customer/action ID. Missing/ambiguous
snippets are an integration blocker. The friendly name is stored by OS; the
provider uses a recovery name. Server actions have tag=null intentionally; use
[Server conversions](server-conversions.md) for delivery.

New actions are secondary (primary_for_goal=false), so they do not silently
enter account-wide bidding. Without explicit campaign goal selection, tracking
typically appears in All conversions, not primary Conversions. This is not
evidence of broken tracking.

## Connect a browser event

Continue the product's existing Google tag and consent setup. Initialize the
returned tag once and send its exact send_to only on the confirmed successful
outcome: account creation, verified payment, or the actual selected event.
Do not duplicate on refresh/re-render or send on failed attempts. Use a stable
non-PII transaction ID for an outcome where appropriate.

Tag ID/label are public browser configuration; OS keys, auth tokens, emails and
other personal data do not belong in the event payload. Check successful and
failed paths separately. Browser dispatch is not proof of Google attribution;
reporting can lag. Do not poll/retry indefinitely waiting for a test event.

A browser signup and server purchase can coexist. Do not report the same outcome
to two different actions and select both in goals: transaction deduplication does
not span actions. Do not replace an existing browser action automatically.

## Inspect readiness and select goals

```http
GET /ads/google/campaigns/{ref}/conversion-readiness
GET /ads/google/campaigns/{ref}/conversion-optimization
POST /ads/google/campaigns/{ref}/conversion-optimization
Idempotency-Key: <stable key for this goal change>
Content-Type: application/json
```

```json
{"mode":"select_goals","conversion_actions":["1234567890:77"]}
```

Readiness is in `data.raw` and includes only Registry-owned actions in the
campaign's product/exact-campaign binding and authoritative conversion account.
configured=true requires an ENABLED owned action. configuration_only=true means
it does not prove goal selection or event delivery. No action is not a blocker
for CPC advertising.

Always set mode explicitly. select_goals binds a campaign-specific custom goal
to the exact selected enabled actions and excludes other standard campaign goals.
It does not change bidding, budget, status, account defaults or global primary
flags. A secondary action in this custom goal can contribute to Conversions;
it is no longer necessarily limited to All conversions. This does not turn
Manual CPC into smart bidding.

## Change conversion bidding or restore

Use the same POST endpoint with an explicit intended mode:

```json
{"mode":"maximize_conversions","conversion_actions":["1234567890:77"]}
```

This selects the owned actions via a custom goal, excludes other campaign goals
and switches to Maximize Conversions. It does not launch or change budget/status
or account defaults. Both browser and server actions can be selected. The
current supported starting strategies are standard Manual CPC, Maximize Clicks
(TARGET_SPEND) and Maximize Conversions on Search; portfolio strategies are not
supported. Selecting goals/configuring bidding does not prove tracking is usable.

Read the returned state and verified field, then GET conversion-optimization.
Retain the returned restore_key. To undo, send a new idempotent request:

```json
{"mode":"restore","restore_key":"<key of the completed change>"}
```

Restore uses the saved previous configuration, not an assumed default.
Restoring select_goals restores only goals, preserving later bid changes.
Restoring a bidding change includes its saved bidding configuration. Concurrent
or newer configuration/goal-inventory changes conflict rather than being silently
overwritten. verified confirms configuration readback, not conversions or
sufficient learning.

## Report an exact action

```http
GET /ads/google/campaigns/{ref}/conversion-report?conversion_ref=1234567890:77&date_from=2026-01-01&date_to=2026-01-31&date_basis=interaction
```

Dates are inclusive in the returned account timezone, at most 366 days and cannot
end in the future. interaction attributes to the ad interaction date; conversion
uses the outcome date. The report is for the exact owned action, not all actions.
Both conversions and all_conversions follow Google's goal/attribution rules;
counts can be fractional, and neither is all product registrations.

data_status=available can contain actual reported zeros. no_rows means no rows,
with null metrics; unavailable means expected metrics are missing. Failed queries
stay errors. retrieved_at is completion time, not a freshness watermark; lag and
attribution revisions are possible. Do not infer broken tracking from a recent
empty report or wait indefinitely for a test event.

## Retry and retention

Creation and optimization require Idempotency-Key. Reuse the identical key/body
after a timeout; changing payload under a key returns 409. Completed operations
with later drift are not silently reapplied. Inspect current state and use a
new key only for an intentional new change.

For provider_create_outcome_unconfirmed, retry the same key for readback; if
still unknown, request Egbe reconciliation, not a replacement with a new key.
Actions/custom goals are retained with archived campaigns.
