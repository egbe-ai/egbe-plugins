# Activation Tracking

Use this workflow when a product has a real first-value moment or core action
completion.

## Applicability

Read the accepted Core Value/CAP result and its confirmation from the current
product requirements, including `First-value signal` when a PRD exists. For
bounded maintenance, use the task's accepted behavior and authoritative product
records. Confirm the actual success branch in implementation before instrumenting.

`Public preview` controls only public sampling; `no` does not disable measurement
of real value after login, payment or processing. Observe that result, not merely
its prerequisites. If the outcome is unknown or conflicting, identify the missing
definition and leave it unresolved rather than declaring it inapplicable.
An informational/static product need not have a discrete activation event:
use its meaningful existing observations without inventing a form, result or
synthetic completion. Existing event names or routes alone do not prove value.

## Source Of Truth

Always read the live event contract first:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/analytics/events" -s
```

`canonical-events.v1.json` remains the source of truth for the activation event
name, required payload fields, recommended attribution fields, and delivery
policy.

## Event

Use the canonical `activated` event when the visitor receives real product
value. Do not fire it for merely clicking a CTA or landing on a dashboard.

Use `activation_type` for the product-specific value shape instead of inventing
product-specific event names:

```js
window.umami?.track("activated", {
  product_slug: "my-product",
  path: "/dashboard",
  activation_type: "report_generated",
});
```

## Browser Payload

Read first-touch attribution from the shared snippet when the browser starts the
core action:

```js
const attribution = window.__egbeAttribution?.read?.() || {};
```

Include the required payload from the event contract and useful attribution
fields:

```js
const activationPayload = {
  product_slug: "my-product",
  path: "/dashboard",
  activation_type: "report_generated",
  visitor_id: attribution.visitor_id,
  visit_id: attribution.visit_id,
  first_utm_source: attribution.first_utm_source,
  first_utm_medium: attribution.first_utm_medium,
  first_utm_campaign: attribution.first_utm_campaign,
};
```

## Backend-Confirmed Activation

If first value is created by a backend/API action, separate the durable
confirmation source from Umami delivery:

1. Browser sends attribution with the core-action request.
2. Backend performs the durable first-value write or confirms the real result.
3. Backend returns an analytics descriptor only after success.
4. Browser emits that descriptor with `window.umami.track(...)`.

Backend response shape:

```json
{
  "ok": true,
  "analytics": {
    "name": "activated",
    "data": {
      "product_slug": "my-product",
      "path": "/dashboard",
      "activation_type": "report_generated",
      "activation_id": "report_123",
      "visitor_id": "visitor_123",
      "visit_id": "visit_123",
      "first_utm_source": "reddit"
    }
  }
}
```

Browser delivery:

```js
const result = await response.json();

if (result.analytics?.name && window.umami?.track) {
  window.umami.track(result.analytics.name, result.analytics.data || {});
}
```

If the activation flow redirects immediately, store the descriptor in a
short-lived `sessionStorage` pending queue, navigate, then flush it from the next
browser page with `window.umami.track(...)`.

Do not use direct backend Umami `/api/send` or `trackServerEvent` as the primary
delivery path for `activated`; it can attach the event to a different Umami
session than the visitor's browser session.

## Practical Rules

- Preserve the existing product feature behavior.
- Emit activation once per real first-value moment or use payload state such as
  `activation_id` to make repeat behavior explainable.
- Put no raw emails, secrets, input documents, tokens, or payment details in
  Umami payloads.
- Persist first-touch attribution with durable user/account/value metadata when
  a backend exists, so later revenue and retention reporting can join back to
  acquisition channel.

## Bounded Verification

When activation is applicable, prove the authoritative first-value branch with
the smallest existing helper, handler, route, or component test. For a
backend-confirmed outcome, verify that the success branch returns the canonical
descriptor only after the real result or durable write succeeds, and that error,
placeholder, and no-result branches omit it. Verify browser delivery through the
existing descriptor consumer or one focused test around it. Test a pending
redirect queue only when the product uses one.

Do not replay the whole product journey, build a new browser harness, emit a
synthetic activation into production stats, or deploy solely to prove logic
already covered by focused evidence. If the accepted behavior has no discrete
first-value event and no misleading instrumentation needs repair, no code or
deployment change is required; report that bounded conclusion, not absent value.
