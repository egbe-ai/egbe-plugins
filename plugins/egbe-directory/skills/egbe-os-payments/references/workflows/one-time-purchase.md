# One-time purchase and fulfillment

Use the accepted offer's price, deliverable, access and refund rules. A one-time
purchase is not a subscription with an artificial period. The subscription
scaffold and its lifecycle simulation do not implement this flow.

## Bind the purchase

Follow [product checkout](product-checkout.md) for the shared catalog, protected
server endpoint, durable attempt, validation receipt and provider idempotency.
Use a non-recurring price and `mode: "payment"`.

Bind the attempt to a durable local order and its owner before checkout. Set
`client_reference_id` to a stable server-owned reference that resolves that
binding; persist the returned Checkout Session id. Resolve price, currency,
quantity and any existing provider customer on the server. Browser parameters
or an email address alone cannot establish ownership.

If guest purchase is part of the accepted flow, authorize the order through a
private server-managed session or equivalent unguessable, bounded access
mechanism. Keep the secret out of shared artifacts and URLs used for analytics.
An optional collected email is a contact address, not proof of an existing
account. Later account attachment requires verified ownership; do not merge
orders merely because emails match. For an account purchase, reuse normal Auth.

## Apply payment separately from delivery

Follow [webhook security](../security/webhook-and-entitlements.md) for raw-body
signature verification and the gateway's non-mutating test/preflight branch.
For a live event, correlate its session/payment-intent ids with the stored attempt
and expected order. Confirm
the accepted price/amount and currency, including a valid configured discount;
an unexplained mismatch must not unlock the product.

- `checkout.session.completed` alone is not payment proof: check paid status.
  Delayed methods may complete checkout before payment succeeds.
- A later `checkout.session.async_payment_succeeded` can confirm that same
  order; `async_payment_failed`, abandonment or expiry cannot grant it.
- If handling payment-intent events too, correlate them with the same purchase.
  Different event ids may describe one payment; grant once per business order,
  not once per webhook event type.
- Store the event, payment transition and local right/delivery obligation
  atomically. A valid event that cannot be committed gets a retryable error,
  not success. Handle out-of-order events without regressing confirmed state.
- Keep paid, fulfilled, failed delivery, refunded and partially refunded facts
  distinct. Apply the accepted refund/access policy; a refund is never a new
  grant. Do not infer revocation rules or create refunds during verification.

For an external delivery operation, durably record the pending work with the
payment transaction, then retry using a stable operation identity. Record the
actual result so recovery does not send, charge or deliver twice. Do not hold a
database transaction open across an external side effect or call a successful
payment a delivered result.

The real product consumer authorizes from this durable order/right. Protect
downloads, background jobs and direct API paths as well as the visible page.
The success URL is navigation only; show pending confirmation when necessary.

## Verify without a real charge

Use checkout validate-only for deployed configuration and binding. Prove the
one-time lifecycle through the application's isolated database and actual
receiver/consumer, following [durable verification](../security/durable-verification.md):
valid paid, unpaid, delayed success/failure, duplicates across event types,
wrong owner/amount, out-of-order refund, rollback and failed delivery recovery.
Verify that retries of one order reuse its pending attempt, while two orders
for the same buyer and price remain distinct, including across guest-to-account entry.
Test markers must remain non-mutating in production; never strip them to force
a live grant. An isolated signed fixture is not evidence of live payment.

Report configuration, durable integration, deployed access and actual payment
observations separately. A real paid purchase or customer delivery is not
required merely to prove implementation readiness.
