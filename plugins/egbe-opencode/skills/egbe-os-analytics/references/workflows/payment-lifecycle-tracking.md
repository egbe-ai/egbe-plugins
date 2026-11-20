# Payment Lifecycle Tracking

Use this workflow after the product payment behavior exists. The Egbe OS
`egbe-os-payments` skill owns checkout, webhooks, subscription state, and entitlements;
this workflow owns analytics only.

## Source Of Truth

Read the live contract before implementation:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/analytics/events" -s
```

Use its exact required payloads. Do not copy a second event schema into payment
code or invent plan-specific event names.

## Browser-Session Events

Emit `paywall_view` when a pricing gate, upgrade prompt, or paid-plan choice
actually becomes visible. Deduplicate repeated renders of the same `paywall_id`
within the current view when appropriate.

Emit `checkout_started` only after the backend returns a real Checkout Session
or payment destination. The browser sends it immediately before navigation so
it stays in the visitor's Umami session.

Before requesting checkout, read first-touch attribution:

```js
const attribution = window.__egbeAttribution?.read?.() || {};
```

Send the bounded attribution snapshot to the product backend. The backend stores
it with the durable account/payment record and passes safe fields through the
checkout metadata. Never place email, card data, provider secrets, or raw
customer input in analytics.

The checkout response may return an analytics descriptor:

```json
{
  "checkout_url": "https://checkout.stripe.com/...",
  "analytics": {
    "name": "checkout_started",
    "data": {
      "product_slug": "my-product",
      "path": "/pricing",
      "checkout_type": "subscription",
      "checkout_session_id": "cs_...",
      "plan_name": "pro"
    }
  }
}
```

Send the descriptor with `window.umami.track` and then navigate. Do not send
`checkout_started` from the backend collector as the primary path.

## Purchase

Payment confirmation comes from a signed live payment event applied
idempotently by the product backend. Never emit `purchase` from a Stripe return
query parameter or a simulated webhook.

When the checkout success page can ask the backend for a newly confirmed,
not-yet-delivered purchase descriptor, deliver it through the browser so the
purchase joins the buyer's session. Mark that descriptor delivered
idempotently and bind the read/ack route to the authenticated account.

Do not send canonical `purchase` through the backend Umami collector as a
fallback. A buyer who never returns may be absent from the Umami session funnel;
complete financial totals come from Stripe/OS payment metrics. This keeps one
event name from mixing session-bound and detached server delivery.

## Out-Of-Session Lifecycle

Use backend direct delivery for real committed lifecycle facts that normally
have no active browser session:

- `subscription_renewed` after a renewal invoice is paid;
- `subscription_canceled` after cancellation is accepted or becomes effective;
- `refund` after a successful refund is confirmed.

Store the provider `event.id` and apply the product transition before emitting.
Use that id to make analytics delivery retry-safe and to populate
`stripe_event_id`. A repeated provider delivery must not create a second
canonical event.

The backend emitter may be a shared imported helper; its symbol name is not a
contract. What matters is that the committed real lifecycle branch reaches the
OS/Umami backend delivery path with the canonical event and that the provider
event id controls idempotency.

## Verification

Use the smallest existing verification surface at each authoritative producer:

- for `paywall_view`, inspect or test the existing component/helper that emits
  when the real paywall becomes visible;
- for `checkout_started`, test the existing checkout response/consumer boundary
  to prove the descriptor follows successful Checkout Session creation and is
  delivered before navigation;
- for browser-delivered `purchase`, test the authenticated read/ack descriptor
  boundary and its duplicate-safe delivered state;
- for renewal, cancellation, and refund, use existing signed-webhook handler or
  lifecycle-helper tests to prove committed state reaches canonical delivery
  once and duplicate/error branches do not.

Test webhook events may verify signature and no-op behavior but must not grant
entitlement or produce `purchase`, renewal, cancellation, or refund. The
test-event branch must return before invoking any imported analytics helper.

Do not build a new full Checkout/browser harness, replay the subscription
journey once per event, mutate real payment state, write synthetic revenue events
to production stats, or deploy solely to prove logic already covered by focused
component/handler evidence. Reuse an already-available broader flow only when it
proves several owned boundaries more cheaply than focused checks.

Use real observed Umami and payment evidence after customers transact; observed
revenue is not a readiness prerequisite. Reconcile financial totals against
Stripe/OS metrics rather than treating Umami as the payment ledger.
