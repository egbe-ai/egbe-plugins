# Complete Product Funnel Tracking

Use this workflow when analytics must cover a complete product journey rather
than one isolated lifecycle category.

## Establish applicable coverage

Read the live event contract first:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/analytics/events" -s
```

Build a temporary measurement inventory from the caller-supplied requirements,
real product behavior, and relevant user-facing surfaces. Account for each
explicit measurement moment exactly once. Evaluate event applicability
additively; do not select one static product profile as a complete checklist.

Map applicable moments as follows:

- use native Umami pageviews for page-view measurement;
- use `campaign-visit` only for explicitly attributed visits handled by the
  shared snippet;
- use `cta_click` for every primary conversion-driving placement;
- use `button_click` only for analytically meaningful secondary actions, never
  every incidental control;
- use `activated` for real first value and caller-required core outcome
  completion, with a stable product-specific `activation_type` for each
  measured outcome and one clearly identified primary activation type;
- use the canonical signup lifecycle when signup, registration, account
  creation, or lead capture exists;
- add `email_verified` when verification or a magic-link return establishes the
  verified state;
- use payment lifecycle events only when the owned scope includes their real
  payment boundaries.

For every applicable moment identify the actual interaction, producer, or
authoritative success boundary; canonical event and discriminator or role;
delivery and attribution path; privacy exclusions; and the smallest evidence
that demonstrates the instrumentation. Do not relabel a click as a durable
success or invent a product-specific event name when semantics differ.

Read only the focused workflows required by this inventory:

- `landing-click-tracking.md` for meaningful CTA and button interactions;
- `signup-lifecycle-tracking.md` for signup and conditional verification;
- `activation-tracking.md` for first value and core outcome completion;
- `payment-lifecycle-tracking.md` for real payment boundaries.

## Implement one bounded integration pass

Reuse the existing analytics site, shared snippet, attribution state, client,
and helpers. Instrument the real existing components and success boundaries.
Do not refactor product features, authentication, navigation, or payments to
make analytics easier, and do not create a parallel analytics framework.

Preserve one canonical event name across product-specific uses and put identity
in stable payload fields such as `cta_id`, `button_id`, `activation_type`, and
their roles. A repeated CTA action may use the same role with a distinct stable
placement id.

## Verify proportionally

Use the smallest existing verification surface that matches each change:

- inspect rendered attributes or component output for CTA/button tracking;
- use an existing component, unit, or helper test for browser-only events;
- use an existing handler or route test for backend-confirmed descriptors and
  confirm failure responses omit success descriptors;
- test a pending redirect queue only when the product actually uses one;
- reuse one already-available broader flow when it cheaply proves several
  events together.

Do not build a new full browser-journey harness, replay the whole product once
per event, send synthetic events to production statistics, or wait for live
traffic. Use live browser evidence only when the caller explicitly requires it
and the path is already available without building new test infrastructure.
