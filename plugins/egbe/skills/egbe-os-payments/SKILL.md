---
name: egbe-os-payments
description: Build or repair Stripe checkout for one-time purchases or subscriptions, discounts, billing and entitlements.
metadata:
  egbe-when: "Use for monetization work; offer when an agreed paid offer lacks a working payment flow."
  egbe-visible: "true"
  egbe-title: "Payments & subscriptions"
  egbe-description: "Accept payments, offer subscriptions and promo codes, and let customers manage their billing."
  egbe-category: "Payments & accounts"
---

<!-- egbe-mcp-connection:v1 -->
This skill comes with the Egbe plugin. If this project has its own installed copy
of the skill, use that copy instead. Otherwise make every Egbe API call it
describes with the Egbe connector's `egbe_request` tool: pass the HTTP method,
the API path (for example `/me/limits`), query parameters in `query` and the JSON
body in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Files this skill refers to are next to this `SKILL.md`, except any listed under
"Files downloaded on demand".

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs a set-up project workspace. In a persistent
project workspace that is not set up yet, set it up as the `egbe-setup` skill's
project setup describes.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


# Payments

Build payments through Egbe OS, not through provider credentials or direct
payment-gateway routes. Base URL: `https://os.hz.egbe.dev`. Authenticate with
`Authorization: Bearer $OS_API_KEY`.

## Reuse the existing integration

Inspect the product repository and its `AGENTS.md`. When it contains
`EGBE:BILLING-FOUNDATION`, reuse the existing subscription foundation: plan
catalog, provider-binding sync, checkout attempt and endpoint, signed webhook
and lifecycle reducer, durable subscription state, entitlement helper, Billing
status and Portal endpoints, and neutral `/account/billing` surface. Do not
copy, replace, or rebuild that core. Complete only the product-specific catalog,
CTA/auth continuation, product enforcement or usage behavior, design and
navigation adaptation, analytics, and semantic verification. Repair integration
defects without creating competing billing state or bypassing its contracts.

For a repository without it, implement against the established application and
database conventions. The bundled `assets/scaffolds/billing-nextjs-subscription/`
is an optional starting point for a compatible new subscription integration,
not a one-time purchase engine. Do not overwrite working code or add a marker
without the implementation it describes.

Product Build's `references/foundations.md` documents the optional local scaffold
helper's `--subscriptions` selection, which previews and installs this foundation
and its required account/session pieces. Use it only for an accepted subscription
offer on a compatible stack; provider setup and product integration remain here.

## Route The Work

- For customer purchase, buyer, or revenue reports, follow **Reporting customer
  metrics** in the `egbe-os-analytics` skill (`GET /analytics/skill`).
- For catalog, provider setup, checkout, and pricing handoff,
  read [references/workflows/product-checkout.md](references/workflows/product-checkout.md).
- For a one-time purchase and its delivery/access lifecycle, also read
  [references/workflows/one-time-purchase.md](references/workflows/one-time-purchase.md).
- For coupons, customer-entered promotion codes, automatic Checkout discounts,
  and discount operations, read
  [references/workflows/discounts-and-promotion-codes.md](references/workflows/discounts-and-promotion-codes.md).
- For signed webhooks, normalized subscription state, and entitlements, read
  [references/workflows/subscription-lifecycle.md](references/workflows/subscription-lifecycle.md).
- For the account billing page, user-menu plan state, and Customer Portal, read
  [references/workflows/account-billing.md](references/workflows/account-billing.md).

Those workflows select the supporting contract, security, and UX references.
Read only the workflow relevant to the requested payment capability.

## Platform Rules

- Use only `$OS_URL/payments/*`; never request Stripe keys or call Stripe or the
  internal payment gateway directly.
- Use one app-owned plan catalog across landing pricing, checkout, billing UI,
  and entitlements.
- Enable customer-entered promotion codes by default in new Checkout and
  Payment Link implementations. Do not create a coupon or code implicitly;
  follow the discounts workflow when the product needs provider resources or
  an automatic discount.
- Treat provider state from `GET /payments/evidence` as Stripe readback and the
  product database as the source of account entitlement state.
- Treat working Auth as an upstream input. Reuse its private validation identity
  and normal server-side session lookup for authenticated Billing work instead
  of replaying signup, password, or email-link entry. Never add a public
  test-login route or alternate Billing-only auth path.
- Send an `Idempotency-Key` on every provider create operation. Reuse the same
  key when retrying the same logical operation.
- Keep provider ids, scoped keys, webhook secrets, customer ids, and checkout
  creation on the server. Never expose them through `NEXT_PUBLIC_*` or browser
  code.
- Use only the `OS_URL` and `OS_API_KEY` supplied to the current workload. The
  Site Gateway injects the separate product identity; never mint, copy, rename,
  or deploy a payments-specific OS key.
- A checkout return URL is navigation, not payment proof. Grant access only
  after a signed live event is durably and idempotently applied.
- Reading account or billing state must not create a provider customer,
  Checkout Session, or Customer Portal Session. Provider creates happen only
  from an explicit user mutation and remain idempotent.
- Checkout and portal server actions implement the portable validate-only
  request contract documented in their workflows. Probe requests reuse the
  normal auth and binding path, return an opaque short-lived OS receipt, and
  never fall through to provider create.
- Use the Egbe OS `egbe-os-analytics` skill as the sole source of payment event names,
  payloads, attribution, and delivery rules.

## Discovery And Readback

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/payments/skill" -s
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/payments/evidence" -s
```

Evidence is scoped to the current instance and intentionally omits customer
email values. Use it to verify provider objects; do not copy it into a second
payment-state artifact.

This GET automatically retries only failures to establish the gateway connection:
at most four attempts with 0.5/1/2-second backoff, within one 55-second budget.
Each connection attempt is capped at five seconds or the smaller remaining budget.
HTTP errors and failures while reading a response are returned without automatic
replay. Payment writes do not inherit this retry behavior.

An error envelope means provider readiness is unconfirmed; it does not establish
that Stripe is unconfigured or that a charge failed. After recovery is exhausted,
a later read may recheck readiness. Preserve the intended integration and the
reported failure; do not replace unavailable evidence with empty records or
change credentials based on a transient connection error.

## Missing product webhook recovery

Products stay active independently of their founder's agent runtime. When a
product webhook returns 404 or 405, Egbe records a deduplicated repair notice in
`GET /notifications` for local-agent projects. Read that notice, fix the signed
receiver, redeploy, and verify actual event delivery. Paid events continue to
return a retryable failure to Stripe until the product accepts them; an inbox
notice does not grant an entitlement or complete delivery. Expired checkout
notices may be acknowledged after the repair notice is durably recorded.
Retries share one unread notice; another failure after it is read reopens the
action. Marking a notice read does not resolve or repair the webhook.
