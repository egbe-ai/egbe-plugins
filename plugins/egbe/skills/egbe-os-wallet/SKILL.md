---
name: egbe-os-wallet
description: Read wallet funds, current operating charges and service limits, or prepare a top-up link.
metadata:
  egbe-when: "Use when a spending decision or customer commitment depends on available resources, or the wallet needs replenishing."
  egbe-visible: "true"
  egbe-title: "Egbe Wallet control"
  egbe-description: "Check available funds and operating charges or prepare a top-up link when needed."
  egbe-category: "Business operations"
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
a local deploy command, needs the standard workspace setup. In a persistent
project workspace that is not set up yet, call `egbe_local_setup` and follow it.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


# Wallet

The prepaid Wallet funds periodic project operation and metered services such
as AI and paid tools. New accounts start with a small free-tier balance. Read
the project's current policy before inferring a charge or funded runway.

Base URL: `https://os.hz.egbe.dev`. Authenticate every call with
`Authorization: Bearer $OS_API_KEY`.

## Check balance

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/wallet/balance" -s
```

Response `data.wallet`:
- `available_to_spend_cents` — what you can spend now (settled minus held).
- `settled_balance_cents` — settled funds.
- `held_cents` — reserved by in-flight operations.

## Read the operating policy

Before budgeting continued operation or making customer commitments, read the
balance and this project's existing policy:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/wallet/policy" -s
```

`data.policy` is a read-only snapshot. It does not debit the Wallet, advance a
billing clock, buy credit or change a subscription.
Existing authentication fences still apply: read it before making commitments,
and do not assume an agent can keep querying after work/access is disabled.
Use the owner's normal Dashboard recovery path if access is blocked; never ask
for administrator credentials to bypass the fence.

- `wallet_funded_project` identifies whether this policy applies. `false` and
  null policy fields mean no wallet-funded enrollment, not free legacy service.
- `service_fee` gives the existing installment in cents, its interval in
  seconds, the billable states, and the persisted billing clock. A delayed
  sweep can charge several completed intervals; a small remaining balance is
  not a cap on a due installment. Paused states are not currently billable.
- `welcome_credit_expires_at` describes a remaining welcome-credit bucket in
  this Wallet. It does not assert that every positive balance is promotional.
- `depletion` explains when new paid work stops and the purchased-funds runtime
  grace conditions. Grace is conditional, time limited and subject to the
  owner's aggregate floor across wallet-funded businesses; it is not extra
  spendable credit or guaranteed service continuity.
- `retention` gives the pause retention period and any recorded deletion
  deadline. Read the actual state/deadline rather than inventing a recovery date.

`commercial_pricing` reports the usage markup, top-up fee and revenue share.
Paid usage carries a 15% Egbe service fee on the underlying service price:
$10 of usage + $1.50 fee = $11.50 total. Top-ups credit the full amount with no
Egbe top-up fee. Egbe takes no revenue share; processor fees, taxes, refunds and
chargebacks can still affect payouts. Transfers, credits, promotional expiry
and the periodic business fee do not incur the usage markup. Promotional funds
pay the same usage prices as purchased funds. Underlying prices can be
provider-reported costs or configured rates/estimates, not exact invoice costs.

Quote budgets including the usage fee before approval. Provider campaign
budgets and hold API amounts remain underlying-service amounts: a $10 provider
budget reserves $11.50 including the fee. For an approved total Wallet budget,
fit the provider budget and fee inside it. Unused reservations are released
without a fee. Fractional cents carry forward; do not round up each request.
Journal metadata exposes `usage_base_cents`, `egbe_usage_fee_cents` and
`usage_total_cents` for itemized charges. Fees apply only to new usage journals;
retries do not add another fee.

Additional service usage is separate from the periodic fee. This snapshot and a
positive balance do not establish the full hosting, database, tool or customer
fulfillment cost, funded runway, or a hard spending limit. Report current rates
where available and distinguish missing cost data from a zero charge.

When present, `usage_cost_basis` describes current managed Wallet accounting:
AI, paid tools and advertising can produce additional usage debits. Managed app
hosting and the attached database currently have no separate usage meter in
that accounting path; the periodic project fee still applies. This is not a
perpetual free-service promise, a provider price quote or a statement about
external/manual charges. The Wallet is not a hard spending cap: reconciliation
of incurred usage and due fees can exceed a small available balance. A null or
missing basis is unknown, including legacy projects and older deployments.
Use capability-specific costs or proportionate estimates for variable work.
Sale deductions, refunds, chargebacks and payout timing remain separate
commercial questions; absence of a Wallet debit does not erase those liabilities
or establish a required gross-refund Wallet deposit.

Read the current [Egbe commercial terms](https://egbe.ai/terms/) separately for
sale and top-up fees, merchant responsibilities, payouts and refunds. Do not
substitute a generic direct-provider tariff. If policy discovery is unavailable
during rollout, report that gap; do not infer a zero-cost policy or buy credit.

## Top up

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/wallet/topup" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"amount_cents":1000}'
```

Optional `currency` (default `"usd"`). Starts a top-up (min `100` cents = $1.00) and returns a top-up intent with a
`checkout_url`. Open that Stripe checkout link and complete payment; your wallet is credited automatically once the
payment succeeds. If `checkout_url` is `null`, retry shortly.
