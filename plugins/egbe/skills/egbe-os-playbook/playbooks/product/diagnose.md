# Diagnose a product loss or opportunity

Answer the question that can change the next decision. Start from the relevant
product promise, prior findings, current plan and evidence window. Use focused
analytics, product records, customer feedback and path checks; do not require a
complete audit before a known repair or repeat all checks for each report.

## Establish the observed path

Trace the product's actual journey: expectations and arrival, attempt and useful
result, offer exposure, commitment/payment and later value where applicable.
The order is product-specific. Compare people reaching the same prerequisite;
distinguish users, visits, attempts, transactions, new customers and renewals.
Use mature, comparable cohorts and counts behind rates. Recent visitors may not
have had time to buy. Use `egbe-os-analytics` for events, session paths and cohort
counts; use `egbe-os-payments` to verify paid outcomes and refunds against
provider records.

Inspect both large early exits and late journeys, including customers who succeeded
or paid. Compare relevant versions, sources, devices or segments when evidence
supports them; small cuts remain directional, not established winners. Missing
events are not zero or a motive. Scroll and dwell indicate exposure, not why a
person left; an old UTM does not prove a new paid visit. Check actual emitter and
record semantics before trusting a suspicious funnel.

For a consequential path question, reuse prior destination evidence and recheck
changed or unverified parts with `egbe-os-destination-readiness`. A working
homepage does not prove saved work, payment or delivery. A reproduced defect is
real, but its prevalence and historical conversion impact remain separate claims.

## Inspect the value customers actually received

When core attempts exist, compare the promised result with authorized input/output
and execution evidence. Use observable quality criteria from [value](value.md).
Use `egbe-os-db` for authorized product input/result records; when execution
failures could explain the outcome, use `egbe-os-errors` and `egbe-os-deploy`
for error and runtime evidence.
Separate acceptable, degraded, failed and unknown outcomes; technical success or
an unconstrained AI self-score does not establish quality.

Join journeys through explicit user/visit/job/attempt identifiers where available;
label time-based joins as uncertain. Use a reproducible, proportionate selection
covering successes, failures, retries, buyers and late non-buyers. Record inspected
and total counts and selection bias. Repeated attempts of one input are not
independent evidence of prevalence; an error-heavy sample is not a population rate.
Keep customer data and evidence access within the technical capabilities' boundaries.

Ask what people expected, tried, received and why they stopped, using existing
feedback or agreed customer research. Include successful and inactive customers;
avoid leading questions that supply the suspected cause. A retry does not prove
bad quality, payment does not prove good quality, and no return does not explain why.
Repeated failures of a consistent class justify investigation more than one ordinary
stochastic miss. Preserve known-good cases when proposing a quality change.

## Separate the loss from its explanation

For a decision-relevant loss identify the affected cohort, last observed step,
missing next result, plausible explanation, evidence for/against and the check
that would distinguish it from a serious alternative. Consider execution errors,
waiting or lost work, offer exposure/value, audience fit, buying delay and coverage.
An intentional authentication or price step is not inherently a defect.

Inspect the code or live behavior where it can resolve that question, not as an
exhaustive bug hunt. Recommend instrumentation only when the missing observation
could change a real decision. If a check needs unavailable access or permission,
bound the gap and continue conclusions supported by independent evidence.

When external research can distinguish the explanations, prepare its question
from these observations, relevant prior work and founder context. Pass only the
relevant evidence, missing knowledge, needed result and applicable scope or budget
to `egbe-os-product-market-research` or `egbe-os-research`. Substantial work uses
`egbe-docs/research/<id>/brief.md`; a narrow check needs only the existing task or
explicit inputs. Do not collect more data when the existing evidence answers the
question, or turn a product diagnosis into a fresh market investigation.

Return a supported cause or an explicit hypothesis with a proportionate next check.
Use [delivery](deliver.md) to choose product work; return a traffic/offer-test
question to [Market and acquisition](../market-and-acquisition.md) with existing
evidence and decisions. New conflicting evidence may revise a conclusion with a
reason, but does not rewrite the original criteria of an earlier test.
