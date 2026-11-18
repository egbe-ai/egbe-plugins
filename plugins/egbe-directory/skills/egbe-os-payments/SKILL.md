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
describes with the Egbe connector: `egbe_read` for GET and `egbe_write` for POST,
PUT, PATCH and DELETE (with `method`). Pass the API path (for example
`/me/limits`), query parameters in `query` and the JSON body in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Where this skill sends an `Idempotency-Key` header, pass the same value as
`idempotency_key` and reuse it when retrying. A result with a `continuation`
holds one part of a long body; read the next part with `egbe_read`, the same
`path` and `business`, and that `continuation`.
Read bundled files beside this `SKILL.md`. For published skill resources on
Egbe OS, use `egbe_skill`. Follow "Files downloaded on demand" for listed downloads.

Publishing works through the connector: commit the app's files with the JSON
commit requests in `egbe-os-git` ("Without a terminal") and deploy the returned
commit SHA; no git push or workspace setup is needed. A step that needs a local
project key or a bundled script, such as a local `npx convex deploy`, needs a
set-up project workspace. In a persistent
project workspace that is not set up yet, set it up as the `egbe-setup` skill's
project setup describes.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.

If the connector's tools (`egbe_read` and the other `egbe_*` tools) are not
available, the plugin's connector is not signed in on this Claude account. Tell
the founder how to connect it, as the `egbe-setup` skill describes, rather than
saying Egbe is unavailable.

The connector's tools work even where this environment's shell cannot reach
Egbe: their calls travel through Claude, not through the shell's network. A step
that runs in the shell, such as a bundled script, a `git push` to Egbe's Git
endpoint or a deploy upload, needs the shell to reach the Egbe host
(`os.hz.egbe.dev`). If a proxy or allowlist refuses that request before Egbe
answers, for example HTTP 403 on CONNECT or curl status `000`, follow the Claude
network recovery in
`egbe_skill(name="egbe-os-quickstart", resource="references/environment.md")`:
the founder allows that host for Claude's code execution or continues in Claude
Code on their own computer. Code can also be published without the shell by
committing through the connector (`egbe-os-git`, "Without a terminal"). Until
the shell step or that commit and its deploy succeed, do not report the work as
published: a Claude Artifact or a local preview is not an Egbe deployment.


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

## Files downloaded on demand

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project workspace; without one,
tell the founder that the step needs it and continue with the rest of the work.

In a project workspace, before a step that runs or copies one of these files,
download it into `.egbe/skills/egbe-os-payments/` at the same relative path, for example
`curl -fsSL <url> --create-dirs -o .egbe/skills/egbe-os-payments/<file>`, and check that its SHA-256
matches. Also download the files it uses from the same folder, such as the
modules a script imports. Wherever this skill names one of these files by its
path in the skill (for example `scripts/...` or `assets/...`), use `.egbe/skills/egbe-os-payments/<file>`;
where it writes `<skills-directory>`, use `.egbe/skills`.
Keep `.egbe/skills/` out of Git by adding it to `.gitignore`.

| File | URL | SHA-256 |
| --- | --- | --- |
| `assets/scaffolds/billing-nextjs-subscription/db/migrations/1000_egbe_billing.sql` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/db/migrations/1000_egbe_billing.sql | `0632ebdaa6740709654c690b36c858a9b5f8ce0c5b025e09cf469bf1c93eac18` |
| `assets/scaffolds/billing-nextjs-subscription/scripts/billing-sync.mjs` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/scripts/billing-sync.mjs | `4aff533b0dac6a956b77e92db3be46aefea4cc33c9059097c39c482d9bd2aea7` |
| `assets/scaffolds/billing-nextjs-subscription/src/app/account/billing/error.tsx` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/app/account/billing/error.tsx | `0c008ae4fbc9efced8b3a8d1ac69230d70cc3493c2f08bcdf9634fe0c74838cc` |
| `assets/scaffolds/billing-nextjs-subscription/src/app/account/billing/loading.tsx` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/app/account/billing/loading.tsx | `89b47b6c909aac59e7b80b9689eaf385943bbe57854845ea3890b81487848f84` |
| `assets/scaffolds/billing-nextjs-subscription/src/app/account/billing/page.tsx` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/app/account/billing/page.tsx | `f73b7d19f2e593cc2e11c69063d1c6dbcb6205da144d1f48a38ed67aa124060e` |
| `assets/scaffolds/billing-nextjs-subscription/src/app/api/billing/checkout/route.ts` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/app/api/billing/checkout/route.ts | `e36088ac5ed108d32f7dc3682c89a5fd79c2fa90bdd586cc323a8f69832bff7e` |
| `assets/scaffolds/billing-nextjs-subscription/src/app/api/billing/portal/route.ts` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/app/api/billing/portal/route.ts | `31b0ce9e424ff59e1e8c62f9891507647914b35c02ebc248de1acc29c96c65a8` |
| `assets/scaffolds/billing-nextjs-subscription/src/app/api/billing/status/route.ts` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/app/api/billing/status/route.ts | `1ec8efdf4725a899fded5516e4969b2e91e7cfec18ba1aaabecb2a5e93e81fee` |
| `assets/scaffolds/billing-nextjs-subscription/src/app/api/payments/webhook/route.ts` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/app/api/payments/webhook/route.ts | `40d24dd15faba2f666ffba0783aaca7281a1f61be0f41384b0296db7db9716d1` |
| `assets/scaffolds/billing-nextjs-subscription/src/components/egbe-billing/plan-badge.tsx` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/components/egbe-billing/plan-badge.tsx | `f84d3988509459a83942300bf0eeb420530d5f104d8e917d6bbed998f8358d28` |
| `assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/billing-sync.test.mjs` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/billing-sync.test.mjs | `1b31a444b196c3eb1a98e2110822c1e194e225526dd9e93c4f9faa89be283dc3` |
| `assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/catalog.ts` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/catalog.ts | `aa224f75898679fdc7d9f9d62166754a5db3d6ce4849211cc8e9d0e67016790f` |
| `assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/checkout-payload.ts` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/checkout-payload.ts | `2f27af5cf4d96646fb855e5cf686776dfbf8b8acd9e5ef410136ecc19ecf56b3` |
| `assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/foundation-contract.test.mjs` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/foundation-contract.test.mjs | `9e8c2af7d4546c39956d499ce446f4971ddc42760abb13bbd2a69e0aef3b443f` |
| `assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/lifecycle.d.ts` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/lifecycle.d.ts | `886892ebe02048313079f0b887b9d0de4378277fcfb149beade0609e514208ab` |
| `assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/lifecycle.mjs` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/lifecycle.mjs | `32b81a9a6e6ef4297fc447b4468395faf3401cfd035c5cf9990cf93ee9005611` |
| `assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/lifecycle.test.mjs` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/lifecycle.test.mjs | `9fb47cf7d4eb7d8876ee5f622a649cb21b4218e2564e0a15cb7a9a08c25c5251` |
| `assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/os-client.ts` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/os-client.ts | `de9bedb29137232e6e33c3d1607de98f5f3329d01abb9831349322af3c3ebdbe` |
| `assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/repository.ts` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/repository.ts | `868e8f277ae47f148f7b262006753d6a331026b5af458f91c370ec0a3e6618d8` |
| `assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/signature.d.ts` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/signature.d.ts | `0a60e3251368f572e2949e57e780bccbfe378eea2f2641746c4c74b87ef313a7` |
| `assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/signature.mjs` | https://os.hz.egbe.dev/skills/egbe-os-payments/resources/assets/scaffolds/billing-nextjs-subscription/src/lib/egbe-billing/signature.mjs | `bb02abeacebc7a2838dd34ea9136076787b2be7a9f2d56a9bd9181dd99a8cdb9` |
