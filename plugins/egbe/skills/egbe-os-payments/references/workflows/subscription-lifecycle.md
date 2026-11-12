# Subscription Lifecycle Workflow

Use this workflow to turn signed Stripe events into durable product access.

## References

Read [../security/webhook-and-entitlements.md](../security/webhook-and-entitlements.md)
before changing the webhook or access checks. Read the Egbe OS analytics payment
workflow when adding lifecycle events; analytics is not defined here.

## Workflow

1. Add durable account billing, subscription, processed-event, and entitlement
   storage using the product's existing database and migration conventions.
2. Implement the configured POST webhook route with raw-body signature
   verification and duplicate-safe transactions. Signature verification must
   complete before JSON event dispatch.
3. Map checkout completion using `client_reference_id` plus the stored owned
   customer mapping. Persist customer, subscription, plan, period, and provider
   event ids.
4. Apply live lifecycle events:
   - paid checkout confirms the initial purchase;
   - subscription create/update/delete/pause/resume synchronizes status;
   - paid renewal invoice extends the paid period;
   - failed payment moves to the product's warning/grace behavior;
   - successful refund records the adjustment and updates access according to
     the product policy.
5. Make server-side feature access read entitlements from this durable state.
6. Keep lifecycle decisions in one pure transition reducer shared by simulated
   and live events. Exercise it through `POST /payments/webhooks/test` for paid
   checkout, renewal, failed payment, cancellation, and refund. After signature
   verification, return the bounded test contract from
   [../security/webhook-and-entitlements.md](../security/webhook-and-entitlements.md)
   before calling any persistence, entitlement, revenue, or analytics helper.
   The no-side-effect boundary applies to imported helpers as well as
   route-local code. Invalid, stale, and future signatures must return 4xx;
   replaying one simulated event id must be reported as a duplicate and remain
   side-effect free. No particular internal action name is required.
7. Prove durable application and actual Product enforcement separately from
   the side-effect-free simulation. Follow
   [../security/durable-verification.md](../security/durable-verification.md)
   using the product's isolated integration-test mechanism. Do not require a
   real charge or make a test event mutate production to obtain this proof.
8. Use `GET /payments/evidence` to confirm provider-side customer,
   subscription, checkout, and event ownership when real evidence exists.

Do not infer purchase from a success URL, client state, email address, or an
unsigned payload. Do not require a real charge merely to prove readiness.

## Completion

Invalid and stale signatures fail, duplicate events are harmless, simulated
events cannot grant access, real subscription transitions are explainable in
the local database, and protected product behavior uses those entitlements.
