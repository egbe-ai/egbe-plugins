# Product Checkout Workflow

Use this workflow to implement an accepted offer's catalog, pricing handoff and
Checkout Session creation. `one_time` uses `mode: "payment"`; `subscription`
uses `mode: "subscription"` with a recurring price. Do not choose a commercial
model as an implementation shortcut.

## References

Read before implementation:

1. [../contracts/plan-catalog.md](../contracts/plan-catalog.md)
2. [../security/server-integration.md](../security/server-integration.md)
3. [discounts-and-promotion-codes.md](discounts-and-promotion-codes.md)
4. [Webhook security](../security/webhook-and-entitlements.md) for signature
   verification and the gateway preflight that runs during checkout validation.
   Subscription transition details apply only to subscriptions.

## Workflow

1. Inspect accepted requirements, pricing surface, auth continuation, account model,
   deployment env, and any payment code. Continue the same product.
2. Build one plan catalog and make landing pricing render from it.
3. Create or reuse owned Stripe products and prices through OS. Send stable
   `Idempotency-Key` headers and include `plan_key`,
   `payment_gateway_app_slug`, and `payment_gateway_webhook_path` in provider
   metadata so later lifecycle checks can resolve the product target directly
   from scoped readback. Confirm ids and metadata with
   `GET /payments/evidence`.
4. Use the server-only `OS_URL` and `OS_API_KEY` injected by Site Gateway, plus
   the product webhook secret deployed exactly as described in the server
   integration contract. Never mint or deploy a payments-specific OS key.
5. Route a paid CTA to `/checkout?plan=<plan-key>` or an equivalent stable
   product route. A free plan may continue directly to signup.
6. When the accepted flow requires an account, preserve the validated same-origin
   checkout continuation through signup/login. After auth, resume the same plan.
   For an accepted guest purchase, use the server-owned order/session binding
   in [one-time-purchase.md](one-time-purchase.md); do not add signup by default.
7. In a protected server checkout route, resolve `plan_key`, the buyer/order binding,
   any existing owned customer, and allowed return URLs. For an account purchase
   without an owned customer, use the authenticated account's server-read
   verified email as `customer_email`; never accept that email from the browser.
   Create or load a durable logical
   checkout-attempt record before any provider create. Store its idempotency
   key and the bounded buyer/order, plan, return-path, and attribution snapshot.
   When the signed lifecycle event supplies a customer id, preserve its
   buyer/order binding; attach it to an account only through verified ownership.
   A guest purchase requires neither an account nor a provider customer id.
   Keep this work in
   a repository/data-access module when that matches the product architecture;
   checkout routes do not need inline SQL.
   If the product issues customer-restricted promotion codes, do not wait for a
   first lifecycle event: explicitly create and persist the account's owned
   Customer before opening Checkout, then send that exact `customer` in both
   validation and creation. A `customer_email`-only session cannot redeem a
   code restricted to a Stripe Customer, even when the emails match.
8. For subscriptions, if the account already has an active, trialing, past-due, paused, or otherwise
   managed subscription, open Customer Portal instead of creating another
   subscription.
9. Build one server-owned checkout payload from the durable attempt. Validate
   it with `POST /payments/checkout-sessions/validate`; this must not create a
   session. New implementations enable customer-entered promotion codes by
   default. Leave automatic discounts absent unless product billing
   configuration selects one through the discounts workflow.
10. Only after validation succeeds, create the real session through
    `POST /payments/checkout-sessions`. Reuse the same validated price, mode,
    owned `customer` or server-bound `customer_email`, stable account
    or order `client_reference_id`, app slug, webhook
    path, same-origin return URLs, first-touch attribution, and the persisted
    idempotency key for that logical checkout attempt.
11. Return the real Stripe URL to the browser. Complete the browser payment
    handoff through the Egbe OS analytics workflow, then navigate.

## Stable logical-attempt identity

Use one non-empty idempotency identity for the complete logical checkout
attempt. Persist it before validation or provider creation. Concurrent requests
for the same pending attempt must converge on one stored record, using a
transaction, unique constraint plus upsert, or an equivalent atomic
get-or-create operation. If an insert loses a race, reload the winning record.

Treat the persistence row and the checkout-attempt domain value as different
types. Map field names explicitly at the repository boundary, especially when
the database returns snake_case fields and application code uses camelCase.
Validate the mapped identity before returning it:

```ts
type CheckoutAttemptRow = {
  id: string;
  idempotency_key: string | null;
};

type CheckoutAttempt = {
  id: string;
  idempotencyKey: string;
};

function toCheckoutAttempt(row: CheckoutAttemptRow): CheckoutAttempt {
  const idempotencyKey = row.idempotency_key?.trim();
  if (!idempotencyKey) {
    throw new Error("Checkout attempt has no idempotency identity");
  }
  return { id: row.id, idempotencyKey };
}
```

An ORM or another language may provide equivalent mapping, but do not cast a
raw persistence row to a differently named application type. Do not recover a
missing stored identity with the probe id, request time, or a request-local
random value. A missing identity is invalid attempt state and fails closed.

Generate a new opaque provider idempotency key once when a new logical attempt
row is created, and persist it as part of that atomic creation. A UUID or an
equivalent random value is appropriate at this boundary. For a subscription,
an active-attempt uniqueness rule may use account and plan. For a one-time
purchase, scope it to the specific order and plan: two orders for the same
buyer and price must not share a pending attempt. Preserve that order and attempt
across guest-to-account entry. Neither account/plan nor order/plan is a permanent
provider idempotency key. After an attempt reaches a terminal state, a deliberate new
attempt gets a new row and a new provider idempotency key. Current time or a
fresh random value is unsafe only when it is recomputed for each retry or used
as a fallback for a missing stored identity.

## Validate-only contract

The protected checkout entry point must support a non-mutating validation mode
without creating a second checkout implementation. When the incoming product
request contains both:

```text
X-Egbe-Payment-Probe: validate-only
X-Egbe-Payment-Probe-ID: <opaque caller id>
```

run the same authentication or protected guest-order lookup, plan and customer binding, return URL,
webhook, attribution, and durable logical-attempt lookup as the normal flow.
Then:

1. forward both headers to `POST /payments/checkout-sessions/validate`;
2. include the logical attempt's stable idempotency key as
   `idempotency_key` in the validation body;
3. do not call customer, Checkout Session, Payment Link, entitlement, or
   analytics mutation routes;
4. unwrap the standard Egbe OS response envelope and return bounded JSON
   containing `validation_only: true`, `operation: "checkout"`, `valid: true`,
   and the real opaque `data.validation_receipt`;
5. do not redirect to Stripe in this mode and do not persist the receipt.

Egbe OS responses use the same envelope:

```json
{
  "code": 200,
  "message": "Checkout configuration is valid; no session was created.",
  "data": {
    "valid": true,
    "validation_receipt": "<opaque signed receipt>"
  }
}
```

Read provider fields from the decoded envelope's `data`, not from the top-level
envelope. If the HTTP client itself wraps the decoded body in `response.data`,
the receipt is therefore `response.data.data.validation_receipt`, not
`response.data.validation_receipt`.
Never substitute a placeholder or fallback receipt when
`data.validation_receipt` is absent. Treat that as a failed validation response
and return an error without creating a Checkout Session. A value such as
`probe-accepted`, an empty string, or a locally generated token is not a
validation receipt.

For example, when the product OS client returns the decoded envelope:

```ts
const envelope = await validateCheckoutSession(validationPayload);
const receipt = envelope.data?.validation_receipt;
if (!envelope.data?.valid || !receipt) {
  throw new Error("OS checkout validation returned no validation receipt");
}
return Response.json({
  validation_only: true,
  operation: "checkout",
  valid: true,
  validation_receipt: receipt,
});
```

A paid landing CTA may be an ordinary same-origin link to
`/checkout?plan=<plan-key>` or an equivalent stable route. Do not add
probe-specific DOM topology to the landing page. On the reached paid checkout
surface, keep `data-plan-key` on the selected plan container and use
`data-checkout-action` on a same-origin form or a control associated with that
form. The form action is the protected checkout endpoint and carries the
selected plan as form data. This is a runtime contract, not a layout
requirement: intermediate pages, router transitions, button text, and component
topology remain product-owned.

Two retries of the same logical attempt must reuse the same persisted
idempotency key. Unknown or malformed probe headers fail closed; they never fall
through to provider create.

Never create Checkout Sessions as schema probes. Treat existing working
authentication as product infrastructure and preserve it while adding checkout.
Do not redesign login UI, redirects, client hydration, or session behavior as
part of this workflow.

For authenticated implementation and verification, reuse the private
validation identity prepared by Auth and the normal product session resolver.
Do not create another account, replay password or email-link entry, or add a
public test-login path merely to reach Checkout.

For an authorized after-turn review, leave a supported way to repeat this
validate-only flow with the reviewer's available tools and normal authentication.
Generate and verify fresh receipts during that review; an expired builder
receipt is not a reusable handoff. Preserve the existing non-mutating contract
and receipt lifetime. A successful checkout validation does not by itself prove
signed lifecycle processing, durable paid access or delivery.

## OS Calls

Use snake_case payloads:

```text
POST /payments/products
POST /payments/prices
POST /payments/customers
POST /payments/checkout-sessions/validate
POST /payments/checkout-sessions
GET  /payments/evidence
```

Every create call must use `Idempotency-Key`. Keep provider ids in the server
catalog/database and return only the checkout destination needed by the browser.
Persist a checkout-attempt record bound to the buyer/order and selected plan before the
provider call. Retries of that attempt reload its stored payload identity and
idempotency key; a deliberate new attempt gets a new record and a new key. Do
not derive one permanent provider key from account plus plan. Do not recompute
retry identity from current time or a fresh UUID inside each request.
Do not rebuild a materially different payload between validation and creation.

The checkout webhook path is a future delivery address, not proof that its
handler is ready. Never add a placeholder handler that returns a successful
response before verifying and durably recording the signed event; that would
discard a real payment event and suppress provider retries. When signed
lifecycle processing is unfinished, keep checkout unavailable for real purchases
until it can safely accept delivery; do not acknowledge unverified events.

The canonical checkout payload uses one provider `price`, not Stripe SDK
`line_items`. Build it once on the server and reuse it for validation and
creation. The two OS operations carry the same persisted identity through
different transport contracts: validation requires body field
`idempotency_key`; creation requires HTTP header `Idempotency-Key`. Keep those
transport details explicit in typed client methods instead of spreading an
ambiguous camelCase field into both payloads:

`checkoutBinding` below is the server-validated snapshot stored with the attempt.
Its `purchaseReference` identifies the order for a one-time purchase or the account
for a subscription. `customerFields` contains either an owned `customer`, a
server-bound `customer_email`, or neither when Checkout collects the guest's contact;
that contact alone never establishes ownership. Return URLs are validated for the
accepted product flow, not forced to an account billing page.

```ts
const checkoutPayload = {
  price: plan.priceId,
  mode: plan.kind === "subscription" ? "subscription" : "payment",
  ...checkoutBinding.customerFields,
  client_reference_id: checkoutBinding.purchaseReference,
  success_url: checkoutBinding.successUrl,
  cancel_url: checkoutBinding.cancelUrl,
  app_slug: deployedAppSlug,
  webhook_path: "/api/payments/webhook",
  metadata: { plan_key: plan.planKey, attribution: firstTouchAttribution },
};
const idempotencyKey = attempt.idempotencyKey.trim();
if (!idempotencyKey) {
  throw new Error("Checkout attempt has no idempotency identity");
}

await validateCheckoutSession({
  ...checkoutPayload,
  idempotency_key: idempotencyKey,
});
return createCheckoutSession(checkoutPayload, {
  headers: { "Idempotency-Key": idempotencyKey },
});
```

After verifying both validation receipts, interpret idempotency evidence before
deploying. An absent idempotency fingerprint means the persisted identity did
not reach the validation body. Different fingerprints mean repeated requests
did not reload the same logical attempt. Fix the repository/client boundary;
never manufacture a probe-only fallback identity.

## Preflight Before Deploy

Check the implementation once against this list before deploying:

1. Checkout creation requires the normal server-side buyer/order authorization;
   any account-entry continuation preserves `plan_key`.
2. A repository or database adapter atomically reads or creates the logical
   checkout attempt before validation or provider creation and explicitly maps
   persistence field names into the application type.
3. The mapped attempt supplies one non-empty stable idempotency key; request
   time, probe ids, and request-local random values do not define retry
   identity.
4. Validation and creation share the same server-owned price, mode, customer,
   buyer/order reference, customer/customer-email choice, return URLs, app slug,
   webhook path, and attribution.
5. Starting from the deployed landing page, each paid CTA reaches its selected
   same-origin checkout route without relying on a particular card or component
   structure.
6. On that route, the selected plan container, same-origin form action, and plan
   form value expose one coherent endpoint contract.
7. With the normal authenticated test account or authorized guest-order session,
   submit the live form twice over HTTP to
   the product checkout endpoint using the validate-only headers. Both responses
   must return the real
   `data.validation_receipt`; verify both receipts through
   `POST /payments/validation-receipts/verify`.
8. Verified claims bind the expected app, plan, owned product/price, current
   buyer/order reference, and one stable idempotency fingerprint. Scoped provider readback is
   unchanged before and after both requests.
9. The validate-only request body contains `idempotency_key`; the provider
   create request sends the same value in the `Idempotency-Key` header.
10. Product build/type checks pass and the paid CTA preserves the plan through
    any required authentication to the checkout endpoint. An authorized real
    checkout handoff is a separate check, not a schema probe or mandatory charge.

Do not implement billing analytics in this workflow. Do not apply subscription
entitlements from checkout return URLs; provider lifecycle events own that
state in the payment lifecycle workflow.

## Completion

Each displayed paid plan preserves its identity through the accepted buyer flow
to the validated checkout endpoint. State separately whether the real Stripe
handoff has been observed. Unknown plans, foreign
provider ids, duplicate subscriptions, unsafe return URLs, and provider errors
fail without changing entitlement state.
