# Readiness

Read [API operations](../runtime/api-reference.md). This phase is read-only for
the ad account; it may write local readiness evidence.

1. Identify the product, destination, requested operation and spending authority.
   Resolve existing campaign IDs before checking their configuration.
2. Read `/ads/openai/account`. Record currency/timezone and actual access. Key
   configuration is not proof of payment setup, serving approval or conversion
   setup access. Keep unknown capabilities unknown.
3. Check destination availability, language and offer consistency. Check product
   analytics through the [tracking workflow](tracking.md) when preparing a launch.
4. Resolve geographies through `/ads/openai/locations`; preserve returned IDs and
   rationale. Do not substitute country strings for provider IDs or invent access
   to a keyword planner, audience estimate or competitor library.
5. Reconcile any existing campaign before creating new objects. Verify the
   approved daily amount against provider constraints without raising it silently.

### Minimum daily budget

In the current shared account, a clicks campaign request on 2026-09-09 was rejected
below **$25/day**. Flag a lower requested budget; this is an observed
account/request constraint, not a guaranteed minimum for every account or bid type.
There is currently no minimum-budget discovery endpoint in Egbe OS. The applicable
minimum may only be disclosed by the provider when creating the authorized paused
campaign. Preserve that rejection as evidence, explain the minimum to the founder and
request approval before increasing the budget. Do not create disposable campaigns
to probe it. A changed, newly approved budget is a new journaled request; first
resolve any uncertain outcome of the previous request.

Write `channel-readiness.json`: observations with timestamps and blockers scoped
to build, launch or optional conversions. Lack of conversions need not block a
traffic campaign. Return what can proceed and what requires founder input;
do not create a throwaway campaign just to probe readiness.
