# Account Billing Workflow

Use this workflow after checkout and lifecycle state are present.

## References

Read [../ux/billing-experience.md](../ux/billing-experience.md) before changing
the account UI.

## Workflow

1. Add `/account/billing` stable protected route.
2. Render the current plan, amount/interval, normalized status, renewal or end
   date, and relevant warning from local provider-synchronized state. Page
   rendering and account-state reads must not create or repair Stripe objects.
3. Give free users without a stored customer a plan-aware upgrade action that
   enters the existing checkout flow. Do not create a customer merely to make a
   manage action available. Existing customers use an explicit protected server
   action that creates a fresh Customer Portal session from their stored owned
   customer id. Send the deployed `app_slug` and a fixed relative
   `return_path`; never accept a customer id or absolute portal return URL from
   the browser.
4. Use Customer Portal for plan changes, cancellation, payment methods, and
   invoice history. Assume those capabilities are enabled for this iteration.
5. Add a compact plan label to the authenticated user menu and link it to the
   billing route. Show actionable warning state for past-due, canceling, or
   paused subscriptions.
6. Handle portal/configuration/provider failures locally with a useful error and
   retry. Keep the previous billing state until a signed lifecycle event changes
   it.
7. Verify signed-out denial, cross-account denial, account-page rendering,
   user-menu state, upgrade handoff, and Customer Portal redirect on the live
   product.

Treat existing working authentication as product infrastructure and preserve it
while adding billing. Change auth only when the billing workflow exposes a
concrete protected-route integration defect.

Use the private validation identity prepared by Auth to enter protected account
Billing through the normal session lookup. Reuse that identity across retries;
do not create a new login, email delivery, or Billing-only auth path.

When an owned customer already exists, call
`POST /payments/portal-sessions/validate` with the same server-owned customer,
`app_slug`, and `return_path` before readiness. This verifies ownership and
same-origin navigation without creating a Stripe Customer Portal Session. When
no customer exists, verify the protected source/configuration path and the free
upgrade branch without manufacturing provider state. The real protected user
action then uses `POST /payments/portal-sessions`.

The portal server action follows the same validate-only request contract as
checkout. If both `X-Egbe-Payment-Probe: validate-only` and a valid
`X-Egbe-Payment-Probe-ID` are present, forward them to
`POST /payments/portal-sessions/validate`, return its opaque
`validation_receipt` in bounded JSON, and do not create or redirect to a real
Customer Portal Session. Normal user requests still create a fresh portal
session. Never persist the receipt.

## Completion

An authenticated user can understand the current plan and safely reach the
right next billing action. No user can read another account's billing state or
choose another account's customer id. Provider errors never become false plan
changes in the UI.
