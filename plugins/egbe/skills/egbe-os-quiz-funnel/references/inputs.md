# Integration Inputs

Reuse accepted project context, including the request, product requirements,
UX decisions and existing research. A goal already settled there does not need
to be asked again. Clarify ambiguity that changes the implementation; do not
invent an offer, disqualification or conversion goal.

Before implementing the route identify the product repository, framework,
existing design and analytics wiring. Keep the quiz in the product application;
do not create a separate app just to host it. A deployed application and working
destination are release prerequisites, not prerequisites for discussion,
reference research or a local implementation.

## Destination contract

| Accepted goal | Resolve before wiring the handoff |
|---|---|
| `call` → `booking_url` | HTTPS scheduling URL and supported attribution/result parameters. Check it opens the intended calendar, without booking. |
| `call` → `lead_form` | Same-origin endpoint, accepted contact fields, durable storage and notification path; intended behavior on save failure and any onward navigation. |
| `signup` | Working signup route and what, if anything, the product persists from the quiz. |
| `payment` | Checkout route, real plan key, exact price and billing period from the plan catalog, and signup continuation when required. Inspect without creating a checkout session. |

Booking directly, collecting contact first, and handling a failed save are
experience decisions. Implement the accepted choice; this skill does not select
one by default. Missing authentication, database or payment work blocks only
the dependent integration: describe what remains and use the relevant Egbe
capability when that work is in scope.

## Specification context

Record product, audience, offer, traffic geography and source references in
`quiz.json`. `goal.statement` may summarize the accepted intent; no special
approval provenance field is needed. Slugs and IDs are stable technical keys,
not sensitive answers. `inputs.offer.not_for` records actual exclusions, and
`claims_to_avoid` records known forbidden claims in the visitor's language.
Verify proof against its attributable source, including the founder's own
records where available. Unknown is not permission to invent evidence.
