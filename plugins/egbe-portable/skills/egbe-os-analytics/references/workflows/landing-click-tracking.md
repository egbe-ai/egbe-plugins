# Landing Click Tracking

Use this workflow when instrumenting public landing pages, pricing pages, demo
pages, or other pre-auth product surfaces.

## Source Of Truth

Always read the live event contract first:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/analytics/events" -s
```

`canonical-events.v1.json` remains the source of truth for event names and
payload fields. This reference explains how to apply that contract to HTML.

## HTML Attribute Mapping

For declarative click tracking, each `required_payload` field from the event
contract must be present as a `data-umami-event-*` HTML attribute. For events
sent from JavaScript, supply the same fields in the event data object using
the contract's snake_case names.

Mapping rule:

```text
required_payload field       HTML attribute
product_slug              -> data-umami-event-product-slug
cta_role                  -> data-umami-event-cta-role
button_id                 -> data-umami-event-button-id
```

Use kebab-case in the HTML attribute name and keep the payload value
product-specific.

## Choosing The Event

Use `cta_click` for the primary next step the page is asking the visitor to
take. It is not limited to `/signup`. It can be a signup, checkout, product
demo, generated sample, waitlist, contact-sales, install, or other primary
conversion/evaluation action.

Use `button_click` for meaningful secondary interactions that help understand
visitor intent, such as opening a demo, toggling pricing, viewing a sample,
expanding a key FAQ, or copying/sharing something important.

Do not track incidental UI controls just to satisfy analytics coverage.

## Choose Tracking By Click Behavior

Use `data-umami-event` on an `<a>` only when its click performs ordinary
navigation to its existing `href`. Umami's tracker handles these links in the
capture phase: it records the event and then navigates to that `href` itself.
A page handler's `preventDefault()` does not cancel that later navigation.

For a popup, modal or in-page action, prefer a semantic `<button type="button">`.
It may use declarative tracking: Umami records the button event without taking
over navigation. Choose `cta_click` or `button_click` by the action's role,
not by whether the element is a link or a button.

If an existing `<a>` has a JavaScript click handler, including one that rewrites
the destination or adds a click reference, omit `data-umami-event` from that
anchor and send the event once from its owning handler with
`window.umami.track(name, data)`. Remove a legacy declarative trigger during
initialization, before clicks can occur; removing it inside the click handler
is too late for the capture-phase listener. Remaining `data-umami-event-*`
payload attributes do not trigger tracking by themselves.

Preserve the existing action, modifier/new-tab behavior and attribution fields.
Use the final destination/reference in the event data when the handler computes
it. Keep opening the popup or following the intended URL independent of tracker
availability and delivery; do not await analytics before performing the action.
Do not combine declarative and manual tracking for the same click.

## Complete CTA Example

These anchors perform ordinary navigation; they have no JavaScript click handler.

```html
<a
  href="/signup"
  data-umami-event="cta_click"
  data-umami-event-product-slug="my-product"
  data-umami-event-path="/"
  data-umami-event-surface="hero"
  data-umami-event-cta-id="hero_signup"
  data-umami-event-cta-role="signup_primary"
  data-umami-event-label="Start free"
  data-umami-event-destination="/signup"
>
  Start free
</a>
```

For a primary demo action, keep the event as `cta_click` and change the payload:

```html
<a
  href="/demo"
  data-umami-event="cta_click"
  data-umami-event-product-slug="my-product"
  data-umami-event-path="/"
  data-umami-event-surface="hero"
  data-umami-event-cta-id="hero_demo"
  data-umami-event-cta-role="demo_primary"
  data-umami-event-label="See demo"
  data-umami-event-destination="/demo"
>
  See demo
</a>
```

## JavaScript-Handled CTA Example

This existing link opens a dialog for an ordinary click and retains its fallback
destination for modifier/new-tab navigation. It deliberately has no
`data-umami-event` trigger. Reuse the application's existing handler and analytics
helper rather than adding a second handler or a parallel tracking framework.

```html
<a id="hero_demo" href="/demo">See demo</a>
<dialog id="demo-dialog">Demo content</dialog>
```

```javascript
const demoLink = document.getElementById("hero_demo");
demoLink.addEventListener("click", (event) => {
  if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey ||
      event.altKey || demoLink.target === "_blank") return;
  event.preventDefault();
  document.getElementById("demo-dialog").showModal();
  window.umami?.track?.("cta_click", {
    product_slug: "my-product",
    path: window.location.pathname,
    surface: "hero",
    cta_id: "hero_demo",
    cta_role: "demo_primary",
    label: "See demo",
    destination: demoLink.href,
  });
});
```

## Complete Secondary Button Example

```html
<button
  type="button"
  data-umami-event="button_click"
  data-umami-event-product-slug="my-product"
  data-umami-event-path="/"
  data-umami-event-surface="pricing"
  data-umami-event-button-id="pricing_toggle_monthly"
  data-umami-event-button-role="pricing_toggle"
  data-umami-event-label="Monthly"
>
  Monthly
</button>
```

## Practical Rules

- Put the attributes on the actual clickable `<a>` or `<button>`, not only on a
  wrapper component.
- Use stable ids such as `hero_signup`, `pricing_pro_signup`, `hero_demo`, or
  `sample_view`.
- Use `path` for the page path where the click happens, not the destination.
- Use `destination` as optional payload for the link target.
- Repeat the same primary CTA label only when it represents the same action,
  but give each placement a different `cta_id`.
- If a component abstracts links/buttons, make the analytics attributes explicit
  props and verify they render into the final HTML.

## Bounded Implementation And Verification

Keep this integration proportional to the chosen click behavior:

1. Inspect the existing analytics wiring and preserve it. Reuse the registered
   site, shared tracker, and application conventions; do not provision a second
   site or replace working scaffold-owned wiring.
2. Identify the real primary conversion/evaluation placements and only the
   secondary controls whose intent is useful to measure. Do not instrument every
   link or incidental control.
3. Check whether each click is ordinary navigation or owned by JavaScript.
   Apply the appropriate declarative attributes or handler-based tracking above,
   with the complete canonical payload, then run the application's existing build check.
4. When the caller requires a live result, deploy once after the build succeeds
   and fetch the live HTML once to confirm the intended CTA markup. Check the
   event and required payload attributes for declarative tracking; use the
   interaction check below for handler-owned tracking.

For declarative wiring on ordinary navigation links and buttons, deterministic
inspection of built or live rendered output is sufficient proof of the attributes.
Do not start browser automation or CDP,
intercept analytics network traffic, click several CTA placements, or build a
new browser harness merely to prove the attributes. Do not send synthetic events
to production statistics. Browser-level proof is appropriate only when the
caller explicitly requests it or the CTA has JavaScript-owned behavior that
rendered attributes cannot establish.

For a CTA with a JavaScript click handler, perform one representative real click
with the actual tracker loaded, using an isolated page or mocked analytics
collection. Confirm that the intended popup/dialog opens without leaving the
page, or that navigation uses the final rewritten URL including its click
reference. Verify exactly one click event with the canonical name and complete
payload. Also confirm the intended action works when the tracker is unavailable
or consent blocks it. This bounded interaction check is required even when HTML
inspection and the build pass; use existing browser tooling rather than creating
a new general-purpose harness. Keep synthetic events out of production statistics.
