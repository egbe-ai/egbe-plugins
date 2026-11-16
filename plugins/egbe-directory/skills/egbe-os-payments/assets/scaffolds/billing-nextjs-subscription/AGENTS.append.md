# Billing foundation

This repository includes the subscription foundation; it is not a one-time purchase implementation.

- Do not recreate or replace `db/migrations/1000_egbe_billing.sql`, `src/lib/egbe-billing/*`, `/api/billing/*`, `/api/payments/webhook`, or the base `/account/billing` route.
- Fill `src/lib/egbe-billing/plans.json` from the accepted subscription offer. Keep provider IDs out of source; when provider setup is authorized, use `npm run billing:sync` to create/read back provider objects and persist bindings, not as a schema probe.
- Connect real paid CTA and signed-in continuation to `/api/billing/checkout`; adapt the neutral account Billing surface to the product design and add it to real account navigation.
- Keep customer-entered promotion codes enabled by default through the scaffold checkout payload. If product billing configuration selects one server-owned automatic coupon or promotion-code reference, pass that bounded reference and disable customer code entry; never create discount resources implicitly.
- A customer-restricted Promotion Code requires the exact persisted Stripe Customer on Checkout. Verify each recipient in authoritative product accounts, explicitly create and persist any missing Customer binding before Promotion Code creation, and pass that exact id to Checkout; never bind eligibility from a browser-supplied email.
- Use `hasEntitlement(accountId, capability)` at each real product enforcement point. Only when an accepted right is exhaustible, add its usage limits and atomic consumption in a product-owned migration; the scaffold does not infer quota rules.
- Keep `/api/payments/webhook` raw-body verification, duplicate transaction, pure reducer, and test-event no-side-effect boundary intact.
- Deploy through the active Egbe OS deployment mechanism and follow the `egbe-os-payments` skill's webhook-secret contract. Never place a provider or agent credential in product source or env.
- Verify checkout, lifecycle simulations, entitlement enforcement, Billing states, and Customer Portal through the normal authenticated product journey.
