# Sources and measurement

Use the connected business's current capability and skill contracts. Discover
which apps, campaigns and integrations belong to it; never treat another
project's objects or a shared advertising account total as this project's data.
Read the relevant domain skill before using its API. Missing access is a
coverage gap, not evidence that an integration or campaign does not exist.
Select the required fields before displaying or saving responses. Metadata can
contain credentials in URLs or nested values; a key-name denylist is insufficient.
Retain each value's ownership, unit and time basis when reducing a response.

## Source map

| Question | Source and boundary |
|---|---|
| Which business and product? | Verified connection identity from `/me/limits`, product notes and the deployed apps listed by `deploy`. Distinguish plans and local code from the serving revision. |
| What can it spend? | `wallet`: available funds, settled balance and holds. Preserve the returned ownership scope and currency; do not imply a project-only balance if the source is shared. |
| Is it available? | `deploy` status and the returned public URL, plus `errors` and relevant bounded logs. An HTTP response proves only the tested surface, not signup, checkout or recovery. |
| Are customers arriving and getting value? | `analytics`: canonical metrics/events, acquisition and product-specific activation evidence. Use the product's actual goal, not an assumed purchase funnel. |
| Are there real payments? | `payments` and canonical analytics with their stated provenance. Distinguish payment confirmation, browser purchase events, renewals and refunds. |
| What is advertising doing? | Each connected Google, Meta, Reddit, LinkedIn or OpenAI channel's reporting/monitoring contract. Include delivery, moderation, spend, outcomes and the concrete test conditions; interpret through the project's market-and-acquisition method. |
| What changed in the product? | Relevant local Git changes, deployment evidence, existing issues, tests and feedback already available to this project. Do not equate an unmerged change with a released fix. |

Channel monitoring workflows can include optimizations and pause operations.
Use their observation contracts only for this report; apply the project's method
and plan for evaluation and do not execute modifying steps. Do not provision analytics, launch a synthetic purchase
or change a product merely to fill a missing metric.

## Make comparisons meaningful

- Define whether a number counts events, sessions, people, registrations or
  confirmed transactions. Do not label pageviews as visitors or repeated events
  as unique customers. Record the definition when it affects interpretation.
- Align periods, timezone, currency and attribution windows. Compare today so
  far with an equivalent elapsed period, not an unlabelled full previous day.
  A daily report normally compares completed days; flag provider lag.
  Period totals are not a linked cohort: do not call activations divided by
  registrations a signup conversion rate unless they describe the same people.
- Use the owning source's units. Convert cents explicitly. Keep Wallet balance,
  product revenue, Egbe usage cost, campaign spend and test budget distinct.
  Do not add advertising spend twice if it is already included in a cost total.
  Quota counters describe resource usage or inventory with their own reset periods;
  they are not interchangeable daily activity or billing metrics.
- Attribute outcomes only where supported. Total product purchases are not
  automatically ad-attributed purchases; platform conversion totals can overlap.
- A source error, missing instrumentation or incomplete coverage means unknown
  or partial, not zero. Use a zero only when a successful, applicable query
  establishes it. Preserve both conflicting values with their provenance until
  the difference is understood.
- Current resource lists describe now, not yesterday's activity. An empty app
  or campaign list does not establish zero historical visits, sales or spend;
  use a period-specific source or leave those totals unknown.
- Keep negative findings within the checked scope: no owned deployment means
  none found in Egbe, not that the founder has no product anywhere. Likewise,
  zero checkout sessions is not zero sales through every payment path. Broader
  conclusions need product context or sources covering those paths.

## Bound the collection

Start with project-level status and aggregates for the selected window. Follow
pagination or state an explicit coverage limit; stop repeated failures and use
the remaining sources. Describe observed access/empty-Wallet failures without
bypassing them or claiming that inaccessible services are healthy.

Inspect changed pages and evidence relevant to a material finding. Do not run
the full product diagnosis or `egbe-os-destination-readiness` workflow every day;
recommend a focused check when the evidence warrants it. Existing routine
results can supply evidence if their scope, revision and freshness are suitable.
