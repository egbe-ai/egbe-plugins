# Optional conversion measurement

Use when the founder asks to measure real product outcomes in LinkedIn. A
traffic campaign can run without this setup. Work in the existing product's
auth, billing, analytics and job conventions; no scaffold or instance is needed.
Keep provider credentials in OS. Server code uses its product `OS_API_KEY`
(scope `analytics` or `ads`); configuration needs `ads`.

## Configure and associate

1. Read owned campaigns and conversion rules before creating anything. Reuse the
   rule for the same product outcome and source. Inspect exact schemas in OpenAPI.
2. Create `POST /ads/linkedin/conversion-rules` with an owned `campaign_id`,
   `name`, `type` (e.g. SIGN_UP or PURCHASE), and `method`:
   `INSIGHT_TAG` for an event-specific browser rule or `CONVERSIONS_API` for a
   server rule. The campaign resolves ownership; creation does **not** attach it.
3. Explicitly `PUT /ads/linkedin/campaigns/{campaign_id}/conversion-rules/{id}`
   for each approved campaign; GET the same path to confirm `associated:true`.
   This is measurement association, not campaign activation or conversion bidding.
   DELETE detaches only this pair. PATCH the rule with `enabled:false` to disable
   it; do not delete/recreate rules to fix reporting delays.

Mutations require a persisted Idempotency-Key. Save rule IDs, method, campaign
associations, readback and actual event hooks in tracking.json. Do not automatically
associate every campaign in the shared account.

## Browser

For the owned browser rule, GET `/conversion-rules/{id}/browser-tag` to read the
existing shared Insight Tag. Install its returned public `insight_tag.tag` once
using the project's script conventions; never expose OS credentials. If the
account tag is missing, report the Egbe team prerequisite; don't create or change
shared tags, domain permissions or audiences.

Fire `window.lintrk("track", {conversion_id: Number(ruleId), event_id: providerEventId})`
on the actual completed outcome, not a button click or generic success-page load.
Use the rule's returned `event_id_prefix` plus the same stable product event ID
used below. The prefix isolates products sharing one LinkedIn account.

## Server

Call `POST /ads/linkedin/conversion-events` after the authoritative product
operation succeeds: a committed registration, or a verified paid invoice/event.
Use one stable opaque `event_id` per business event (not a fresh ID per retry),
its original Unix-millisecond `happened_at`, and:

- `email_sha256`: lowercase hex SHA-256 of trimmed, lowercase email; and/or
- `linkedin_tracking_uuid`: genuine `li_fat_id` captured by the product.
- Optional `value: {"currency_code":"USD","amount":"19.00"}` for the real value.

Only send user identifiers the product is allowed to share. Never invent a click
identifier or email. Retain retry data in the product's existing server-side
storage/queue; don't put matching identifiers into marketing artifacts. Don't
block a successful signup/payment on ad delivery.

OS adds the product namespace to `event_id`; **do not add the prefix yourself in
the server request**. For redundant browser + server measurement, use separate
rules and the same prefixed event ID in the browser. LinkedIn may credit the
browser rule and remove the duplicate from the CAPI rule. Don't sum the two as
independent outcomes or treat a low CAPI count alone as failure.

## Verify without fake conversions

- `validate_only:true` validates the body, owned enabled server rule and a live
  campaign association. It sends no event; this is **not** provider ingestion proof.
- Locally test the real event hook and outbound body with a stubbed OS response.
  Do not create fictional registrations/purchases in LinkedIn to get a green check.
- Actual delivery returns a durable `receipt_id`; GET
  `/conversion-events/{receipt_id}`. `accepted` means provider acceptance, not
  matching or attribution. The product must inspect `data.status`, not HTTP alone.
- `retryable`: fix access for 401/403, wait until `retry_at_ms`, then resubmit the
  identical body/key. At most five delivery attempts; no automatic OS scheduler.
  `unconfirmed` means a response was lost/ambiguous: preserve the receipt for
  Egbe team review, don't generate a new event/key. `rejected` or `exhausted`
  also needs diagnosis, not a loop. Receipts never contain customer identifiers.
- GET `/campaigns/{campaign_id}/conversion-rules/{id}/results?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`.
  Counts are attributed to that campaign/rule, including post-click and post-view.
  Empty rows mean unavailable, not zero. Full conversion reporting can take up to
  72 hours; real traffic and outcomes are needed to prove attribution.

Report separately: configuration/association, implementation of the product
hook, actual provider acceptance, and attributed results. Leave the last two
unverified until real events exist.

[Conversion contracts](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads-reporting/conversions-api-schema),
[Insight Tag](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads-reporting/conversion-tracking),
[Deduplication](https://learn.microsoft.com/en-us/linkedin/marketing/conversions/deduplication),
[Reporting delay](https://learn.microsoft.com/en-us/linkedin/marketing/conversions/conversions-faq).
