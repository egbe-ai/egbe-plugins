# Webhook And Entitlement Security

## Verify the signature

The webhook route must read the exact raw request body before JSON parsing.
Verify `x-egbe-payment-signature` as HMAC-SHA256 over
`<timestamp>.<raw-body>`, compare in constant time, and reject stale timestamps.
Parse the comma-separated `t=<unix>,v1=<hex>` fields explicitly. Reject missing,
duplicate, malformed, non-hex, future, and older-than-five-minutes signatures;
never compare the expected digest with the entire header string or sign only the
raw body.

## Gateway preflight and one-time test acknowledgements

Checkout validation and creation send a signed, non-mutating preflight to the
product receiver. It contains `checkout.session.completed`, `livemode: false`,
`data.object.metadata.egbe_test: "1"` and `x-egbe-payment-test: 1`; preflight also
sets `x-egbe-payment-preflight: 1`. Its session, customer and reference are
synthetic, and its current payload uses `mode: "subscription"` even for a
one-time checkout. Do not require those values to match a real order or offer.

After successful signature verification, a one-time receiver acknowledges these
marked gateway test events with HTTP 200 before real order/session lookup or
amount/mode validation. Return bounded JSON with `contract_version: 1`,
`test_event: true`, `accepted: true`, the received `event_id` and `event_type`,
and `side_effects_applied: false`. Do not invent a subscription transition or
write event/order state, grant access, deliver anything or emit analytics.
Test/preflight headers never bypass signature verification. An unmarked live
event always follows the real order, amount and durable-application checks.

This one-time test acknowledgement may be stateless: repeating the same signed
marked event can return the same acknowledgement. A `duplicate` field is not
required here. The gateway's bounded readback normalizes an omitted field to
`duplicate: false`; that value alone is not a failed one-time acknowledgement.
The subscription simulation's duplicate flag and transition requirements below
do not apply to this contract. Independently verify real one-time event
deduplication, retry and delivery through isolated durable integration; repeated
non-mutating acknowledgements do not prove those behaviors.

A `404` or `405` response is interpreted as a missing receiver and blocks
checkout with `409`; returning order-not-found for this synthetic probe is
therefore incorrect. This acknowledgement proves only the receiver/signature
boundary, not one-time fulfillment. Verify that separately through the
[one-time purchase workflow](../workflows/one-time-purchase.md).

## Subscription application and simulation

Subscription receivers use the test adapter below, not the one-time acknowledgement.
The normalized statuses and simulated transitions here are the subscription
contract; they do not implement or prove one-time order/payment/delivery state.

Use one pure transition reducer for both simulated and live subscription events. The reducer
accepts the verified event plus current billing state and returns a bounded
transition with the resulting `subscription_status`; any additional internal
decision name is product-owned. The reducer does not write to storage or call
analytics/provider APIs itself.

Process each event in this order:

1. Reject an invalid signature.
2. Detect a duplicate `event.id`. A duplicate is reported explicitly and never
   applies the transition twice; no particular internal action name is required.
3. Resolve the local account from the stored checkout/account reference and
   owned customer/subscription mapping. Do not grant by email alone.
4. Compute the normalized transition with the pure reducer.
5. For `livemode: false`, `metadata.egbe_test`, or
   `x-egbe-payment-test: 1`, return the bounded test contract below before any
   local or imported persistence, entitlement, revenue, or analytics operation.
6. For a live event, insert `event.id`, apply the transition, and commit in one
   durable transaction before returning success.

The simulated response contract is:

```json
{
  "contract_version": 1,
  "test_event": true,
  "accepted": true,
  "duplicate": false,
  "event_id": "evt_...",
  "event_type": "checkout.session.completed",
  "transition": {
    "subscription_status": "active"
  },
  "side_effects_applied": false
}
```

Invalid, stale, or future signatures return a 4xx response before the reducer.
For a duplicate simulated event, return `duplicate: true`, report the bounded
subscription state, and apply no side effects. Never trust a client-supplied
transition.

## Simulated Lifecycle Scenarios

The signed Payment Gateway simulation marks each event with
`metadata.egbe_lifecycle_test_scenario`. This marker is valid only after the
normal signature check and only for a test event. It is not a live billing
input and must never replace the durable account state for a live webhook.

For a test event, use the marker to choose one bounded in-memory pre-event
state before calling the same pure reducer used by live delivery:

- `checkout`: a free account;
- `renewal`: an existing active paid subscription bound to the event customer
  and subscription ids;
- `payment_failed`, `canceled`, and `refunded`: an existing active paid
  subscription bound to those ids.

The Payment Gateway also supplies canonical renewal fields for `renewal`,
including `billing_reason: "subscription_cycle"` and a future invoice period.
Do not persist this synthetic state. Its only purpose is to exercise the same
reducer branch that a live event with durable state would use. Unknown or
missing scenarios should use the normal free test state, never arbitrary
metadata supplied by a caller.

Keep this adapter small and explicit. The webhook route should first verify the
raw signed event, then determine whether it is a marked test event. Only then
may it select `testLifecycleState(event, scenario)` instead of loading the
normal durable state; both paths call the same reducer and shape the same
response. The test adapter must not run before signature verification, write
to the database, or be reachable from an unmarked live event.

Return a retryable server error when a valid live event cannot be committed.
Do not return success and defer the only durable write to best-effort work.

Recommended normalized statuses are `free`, `trialing`, `active`, `past_due`,
`canceling`, `paused`, and `canceled`. Store provider customer, subscription,
price, current-period, cancellation, and last-event fields needed to explain
the state.

Access checks use server-side entitlements, not URL flags, browser state, plan
labels, or the Stripe success return. Preserve access through the paid period
when cancellation is scheduled; revoke or downgrade when the effective provider
state requires it.

Keep event transitions distinct:

- paid checkout confirms the account/customer mapping and grants the selected
  entitlement;
- paid renewal extends active access;
- payment failure records `past_due` plus the product's warning/grace policy and
  never grants new access;
- subscription deletion/cancellation records the effective end state and
  revokes or downgrades at the correct time;
- refund records the adjustment and applies the explicit product refund policy,
  never an unconditional paid-access transition.

Do not group failure, cancellation, and refund cases under the same active-state
branch as successful payment events.
