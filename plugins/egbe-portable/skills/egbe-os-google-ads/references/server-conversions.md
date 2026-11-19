# Server-confirmed conversion delivery

Use when a backend confirms the actual outcome, possibly after the browser has
closed. This is optional; no product scaffold or direct Google credential is
required. It does not change campaign goals, bidding, budget or status.

## Setup and runtime access

Use the agent's ads-scoped access for action discovery/creation and goal changes
in [Conversions](conversions.md). Choose an enabled owned UPLOAD_CLICKS action
(created with delivery_method=server). Its tag=null is expected.

The deployed product keeps its server-only product-runtime OS_API_KEY.
The existing analytics scope permits reading a known action, sending
conversion-events (including validate-only), and reading an owned event receipt.
These also accept ads but still enforce ownership. Save the selected refs at
setup; runtime does not need action listing or management. Do not replace its
key with an agent key or request broad ads access just for delivery.

## Capture and persist the actual outcome

Capture the real gclid from the ad arrival and retain it through existing
attribution/auth/order persistence so the backend can retrieve it after
redirects, login or browser exit. UTMs are not a GCLID. Never manufacture one.

On the authoritative successful outcome, persist an immutable delivery intent:
stable non-PII transaction_id, real outcome timestamp, campaign/action refs,
saved click, values and applicable consent state. For payments, use verified
paid-state transition, not checkout creation, return-page visit or failed payment.
Repeated webhooks reuse the same outcome ID. Do not block fulfillment on Google.

Use the product's existing durable persistence/retry mechanism. Per-user clicks,
events, delivery intents and receipts belong to product runtime storage, NOT
Git, campaign.json or the agent's campaign-operation record. Do not use an
in-memory fire-and-forget call or create a second permanent event system here.

## Validate, then deliver

```http
POST /ads/google/conversion-events
Idempotency-Key: <stable key for this outcome>
Content-Type: application/json
```

```json
{
  "campaign_ref":"1234567890:456",
  "conversion_ref":"1234567890:77",
  "transaction_id":"order-42",
  "gclid":"REPLACE_WITH_SAVED_REAL_GCLID",
  "event_timestamp":"2026-09-08T10:00:00Z",
  "ad_user_data":"CONSENT_GRANTED",
  "ad_personalization":"CONSENT_DENIED",
  "value":19.99,
  "currency":"EUR",
  "validate_only":true
}
```

Use actual outcome values. The consent values above illustrate API syntax, not
a default grant. OS does not collect consent or infer it. Send the product's
applicable explicit state using CONSENT_GRANTED/CONSENT_DENIED (bare
GRANTED/DENIED is invalid); denied ad_user_data prevents upload. Do not change
a denied/unknown state merely to pass validation. Optional ad_personalization
is never defaulted to granted; DENIED allows measurement without personalization.
Browser consent-mode syntax is different; do not copy these enums into gtag.

Timestamp must include timezone and not be future. Value/currency are optional
but paired; finite nonnegative amount uses that uppercase ISO currency, not
implicit USD. transaction_id accepts 1–64 letters, digits, underscore, dot, colon
or hyphen; never include email or PII. This API supports GCLID, not email/phone
matching, GBRAID/WBRAID or conversion adjustments.

validate_only=true calls Google validation without importing or consuming a real
receipt. It does not prove attribution. After an authorized actual outcome,
send the same body with validate_only=false (default). Preserve original values
on retries. No Google provider token or SDK belongs in the product.

## Receipts and retries

HTTP 200 is a receipt response. Inspect `data.status`:

- validated: validation only, nothing imported.
- submitted: Google returned a request ID; processing is not yet verified.
- retryable: repeat the identical POST after retry_after_seconds. Persist the
  receipt and obey the delay. OS does not run a background resend. An ambiguous
  timeout may already have been accepted; retain the same transaction ID.
- rejected/exhausted: stop delivery retries and surface receipt, last_error and
  error_fields. The current service allows five attempts with durable backoff.
  Fix configuration/access before retries; do not rotate IDs/keys to bypass it.

OS also deduplicates by project/action/transaction when a caller changes its key.
Changed payload under that transaction or key conflicts. Do not alter timestamp
or amount during retries or invent a new transaction to bypass an uncertain
result. Ads management working does not prove separate Data Manager access.

```http
GET /ads/google/conversion-events/{receipt}
```

Use the returned OS receipt, not a Google request ID. Diagnostics can report
processing, processed, failed or partial_success with error/warning reasons and
counts. status_available=false means diagnostics unavailable, not zero
conversions. checked_at is status-fetch time, not reporting completeness.
processed means processing succeeded, NOT proven attribution. Inspect asynchronous
rejections (including click not found, recent click, duplicates); do not
automatically mint replacement events.

Use the selected-action conversion-report for actual reporting. A secondary
action may appear in all_conversions rather than conversions unless selected
in campaign goals. Processing and reporting can lag; do not poll indefinitely.

## Integration checks

Verify that an authoritative successful outcome has the saved click and one
durable intent, and a failed outcome has none. Replay the same webhook/POST and
confirm the same receipt without another upload. Validate-only must not prevent
a later real send. Check processing diagnostics and the action report separately.
A synthetic click or successful HTTP response is not evidence of real attribution.
