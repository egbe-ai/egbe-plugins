---
name: egbe-os-saas-unit-economics
description: Calculate subscription customer value, acquisition costs and funnel requirements from grounded inputs.
metadata:
  egbe-when: "Offer when pricing or acquisition decisions need a viability check."
  version: "1.4.0"
  egbe-visible: "true"
  egbe-title: "SaaS unit economics"
  egbe-description: "Check subscription economics with measured data, explicit scenarios and traceable calculations."
  egbe-category: "Business operations"
  openclaw:
    requires:
      env: ["OS_API_KEY", "OS_URL"]
      bins: ["curl", "jq"]
    primaryEnv: "OS_API_KEY"
    emoji: "💰"
    os: ["linux", "darwin"]
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


# Subscription unit economics

Calculate the economics needed for the current question using product evidence,
applicable benchmarks and explicit assumptions. Take the question and acceptable
risk from the caller's concrete task or plan. This skill supplies
calculations and validity checks, not a standing target for LTV/CAC, channel mix,
spend or conversion.

Reuse the product's existing `egbe-docs/product/economics.md` or linked test
calculation. Preserve measured values, sources and relevant prior assumptions;
do not overwrite them with a fresh benchmark forecast. Save only the calculations
needed for the task, not a compulsory full metric table or new master report.

## Establish the applicable inputs

Read the supplied brief, file, pricing page and existing records. Confirm which
product is meant only if ambiguous. Use an available browser when prices are
client-rendered; if unavailable, request the consequential missing price or leave
that scenario conditional. Do not infer current prices from search snippets.

These formulas apply to recurring monthly/annual subscription revenue. Identify
the actual billing, customer and cost units. A newsletter subscription and a
workflow SaaS can both recur but need different retention and cost evidence.
One-time purchases, transaction take-rates, ad revenue, and pure usage billing
need another model: explain the mismatch and do not force them into perpetual
monthly ARPU/churn. In a hybrid business, isolate the supported subscription
component and state what the calculation excludes.

Reuse observed cohort data when definitions, maturity and periods fit. Distinguish
observed values, externally observed benchmarks, product estimates and chosen
scenario assumptions. Do not invent a tier mix, churn adjustment, geography
discount, target ratio or conversion split to fill a table. Ask only for missing
inputs that would change the current decision; otherwise show a range, conditional
calculation or unavailable metric and explain what remains useful.

## Ground research and costs

Research only decision-relevant gaps. Before using Egbe search, read the live
`GET /search/skill`; the configured `OS_URL` and project `OS_API_KEY` need `tools`
scope. Credentials stay out of artifacts. This is an example query, not a
mandatory research stage or claim about the category:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/search/web/brave" -fsS \
  -H "Content-Type: application/json" \
  -d '{"query":"monthly customer churn <relevant subscription category> cohort benchmark <current-year>","count":5}' \
  | jq '.data.results[] | {title, url, snippet}'
```

Results use `data.results` and `snippet`; OS does not expose Brave's raw
`freshness` option. Verify publication dates and definitions on original pages.
An unavailable search source is a coverage gap, not permission to invent figures
or discard valid product data already available.

Compare category, buyer, product maturity, billing interval, acquisition channel,
geography, date, and measurement definition before applying a benchmark. Keep
reported ranges and sample limitations. A best-in-class statistic is not typical;
neither the low end nor midpoint of a published range is automatically a product
estimate. Triangulate consequential uncertain inputs where useful, without a
fixed source quota or averaging incompatible channels/cohorts. Explain any chosen
summary and adjustment. No automatic geographic or maturity multipliers apply.

Build product-specific COGS from applicable costs: hosting, storage/database,
third-party/AI usage, payment fees, support, and recurring content production,
localization or licensing where relevant. Use actual contracts/usage or labeled
estimates at a stated scale. Do not assume future volume discounts or optimized
support costs already exist. Separate fixed and variable costs and avoid counting
them twice; scenario comparisons can expose scale sensitivity. Include payment
fees at the actual billing frequency and applicable fee schedule, not a universal
processor percentage. Preserve links or other provenance for cost inputs.

## Calculations and validity

Use consistent currency, periods, population and gross/net revenue definitions.
Keep full precision internally and round for presentation. Rates below are
fractions, not percentage-point values.

| Quantity | Calculation | Conditions |
| --- | --- | --- |
| Monthly revenue per paying customer | recurring monthly revenue / paying customers | Same population and period; label a per-user denominator differently. Normalize annual revenue to monthly when comparing earned recurring revenue, not cash receipts. |
| Scenario ARPU from tiers | `sum(weight_i * monthly_price_i)` | Supported or explicitly proposed mix; nonnegative weights sum to one. Include discounts and billing mix where material. With no credible mix, show relevant tier/scenario values instead. |
| Gross margin | `(revenue - COGS) / revenue` | Positive revenue and compatible costs/periods. Negative margin is possible; do not clamp it or force a benchmark band. |
| Monthly customer churn | churned eligible customers / customers exposed to churn | Use a coherent cohort and exposure window; distinguish customer churn, revenue churn, refunds and net revenue retention. |
| Constant-hazard monthly equivalent | `1 - (1 - annual_customer_churn) ** (1/12)` | Only a conversion under constant monthly survival, not a measured monthly cohort rate or annual-contract cancellation cadence. |
| Approximate expected lifetime | `1 / monthly_customer_churn` months | Constant churn model with `0 < churn <= 1`; zero observed churn in a short/small cohort does not establish infinite lifetime. |
| Approximate gross-profit LTV | `ARPU * gross_margin / monthly_customer_churn` | Same steady-state model; excludes discounting, expansion and varying retention/cost. Label as a model, not guaranteed lifetime value. Use cohort/horizon contribution when this model does not fit. |
| Observed acquisition cost | attributable acquisition cost / acquired customers | State media-only vs fully loaded cost and comparable attribution/cohort window. No observed customers means undefined CAC, not zero or a fabricated finite number. |
| CPC | paid-media spend / measured ad clicks | Same source and window; zero clicks leaves CPC undefined. A click is not automatically a product visit. |
| Conditional required click-to-customer rate | `CPC / proposed_CAC` | Positive proposed CAC and consistent media-only cost basis. This is a requirement, not a forecast; greater than one is infeasible under the assumptions. |
| Conditional affordable CPC | `proposed_CAC * supported_click_to_customer_rate` | The conversion rate needs appropriate cohort evidence or an explicit scenario. It is not a provider bid recommendation. |

An affordable CAC is a plan decision, not LTV divided by a built-in constant.
If the plan chooses a positive LTV/CAC target `r`, its implied ceiling is `LTV/r`;
if it chooses a payback horizon, relate acquisition cost to contribution during
that horizon and state retention/cash-flow assumptions. Do not require either
target when the question can be answered without it. LTV-based sustainability
and a limited learning budget are different quantities.

Funnel stage probabilities can be multiplied only for linked conditional stages
of the same cohort: `P(signup | click) * P(paid | signup)` yields click-to-paid
when those stages cover the relevant path. Add arrival loss if starting at clicks
and the measured funnel starts at visits. Separate cohorts and unrelated period
totals do not establish these rates. A total conversion rate alone cannot identify
the stage split; leave it unidentified unless evidence or a labeled scenario
supplies an independent stage rate. There is no fixed signup/payment ratio.

Check finite values, positive denominators, rate bounds, weight sums and units.
An impossible required rate, nonpositive contribution or incompatible model is
an informative limitation, not a reason to hide the result or declare the whole
product unviable. Distinguish a mathematical error from an unsupported assumption.
Sensitivity cases should vary consequential assumptions coherently, not combine
every favorable cost with every unfavorable market statistic by rule.

## Return a traceable answer

Show the relevant observed/scenario metrics with units, scope and calculation
inputs. Record source URLs or file references, collection dates, original ranges,
definitions, chosen assumptions and material exclusions beside the calculation
or in a short source log. Do not label modeled LTV a proven minimum, a required
conversion rate an expected result, or provider CPC a guaranteed future cost.

Explain which assumption changes the answer and which evidence would improve it.
Return the supported calculation and implications to the caller; do not
change prices, budgets or campaigns as part of this calculation. Match the
founder's language and preserve unknowns instead of requiring every metric.
