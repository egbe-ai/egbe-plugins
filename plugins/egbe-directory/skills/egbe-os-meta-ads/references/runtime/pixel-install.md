# Meta Pixel Install Contract

The Meta pixel is the ad network's own view of the product. OS analytics defines
canonical product events (see
`references/runtime/shared-analytics-attribution.md`); the pixel exists so Meta
can optimize delivery and so campaign reports have a channel-side conversion.

One shared pixel serves every egbe product. Products are separated by the
destination URL and by a product-scoped payload on every event — never by a
per-product pixel and never by a product-specific event name.

## Pixel ID

Read `GET /ads/meta/raw/tracking?product_slug=<product_slug>` with the project
OS credentials. It returns `pixel_id` and `event_parameters`; no provider
credentials are needed. Save the public pixel ID as `NEXT_PUBLIC_META_PIXEL_ID`
in the app's public configuration. If Next.js inlines it, supply it before the
build (for example through an imported public JSON config), not only through
deploy runtime `env`. See `egbe-os-deploy` for build-time configuration. No deploy helper
installs the pixel or injects this value automatically.

- Read the ID from the configured `NEXT_PUBLIC_META_PIXEL_ID` value in product code.
- Never hardcode a pixel ID, and never add a hardcoded fallback. Sending to the
  wrong dataset is worse than sending nothing: the custom conversions live on
  one pixel only.
- If the env var is missing, render no pixel and report `pixel_state`
  `not_configured` in `tracking.json`.

## Placement

Install the base snippet in the shared root layout so it loads on every page —
landing, signup, checkout, and in-product. Installing it only on the landing
page is insufficient.

Initialize the pixel only (`fbq('init', id)`). Do not put
`fbq('track','PageView')` inside the base snippet: page views are fired
explicitly so single-page navigations are counted and non-funnel pages can be
excluded.

## Event Contract

Read `GET /ads/meta/raw/tracking?product_slug=<product_slug>` once during setup.
Save the returned `event_parameters` in the product's public tracking config and
in `tracking.json`; send them on every pixel event. They contain `content_name`
and `product_name` (the slug), plus `egbe_product_id` (the stable product identity
returned by OS). This distinguishes even identical slugs in different projects.
The read creates no Meta resources and also works for traffic campaigns.

```javascript
fbq('trackCustom', 'Activation', { ...eventParameters, activation_type: 'first_item_created' });
```

| OS analytics event | Meta browser event | Type |
|---|---|---|
| page open on a public funnel path | `PageView` | standard |
| `activated` | `Activation` | custom (`trackCustom`) |
| `signup_completed` | `Lead` | standard |
| `purchase` | `Purchase` (with `value`, `currency`) | standard |

Use these exact names for every product. Do not invent product-specific event
names such as `<Product>Activation` or `Signup_<slug>`: a shared name plus
the returned event parameters mean one custom conversion shape works for the whole fleet and
products stay comparable.

### PageView

Fire on real opens of the public funnel paths, including client-side route
changes between them. Track the last path a PageView was sent for rather than a
once-per-mount flag, otherwise SPA navigation silently undercounts.

### Activation

The event name stays `Activation`; its product-specific meaning is recorded
in `activation_type` and the tracking notes. Implement the definition chosen
for the product/test, firing only after that action actually succeeds.
Deduplicate according to that event's intended counting unit so route changes,
retries and remounts do not invent additional actions.

If its definition differs from the canonical `activated` event, record that
difference explicitly. Installing tracking must not silently change the supplied
event definition, product access requirements or campaign objective.

### Delivery

The pixel loader is asynchronous. Retry until `window.fbq` is a function
(short interval, bounded attempts) instead of dropping the event on a fast
hydration. Pixel calls are best-effort and must never break the product flow.

## Source diagnostic before publication

Run the bundled checker against the product source and a JSON file containing
only the public pixel configuration:

```bash
python3 <meta-ads-skill>/scripts/check-pixel.py --root <product-root> \
  --pixel-config <public-config.json>
```

It flags literal pixel IDs in code, missing configuration reads, missing
PageView/Activation calls and product identity parameters. Lead and Purchase
checks apply when signup/payment paths exist. It recognizes simple constants
and shared event senders; inspect findings against the actual implementation
when a different delivery abstraction is used. A JSON public config containing
the OS-provided ID is legitimate; a copied ID or hardcoded fallback in code is
not.

This is a focused source diagnostic, not an automatic deploy gate or proof of
network delivery. Verify the actual journey and product-scoped payload in the
browser as described below, including any signup/purchase steps the app owns.
A product without signup or payments does not need artificial Lead/Purchase
steps to pass a checker.

## Custom Conversion

The browser events and their slug parameters are sufficient for Events Manager,
product reporting, and traffic campaigns. A custom conversion is an optional,
finite account-level resource: do not create one at product deploy or for a
traffic experiment. Only if a conversion-objective campaign is deliberately
introduced, create (or reuse) one to select that product's `Activation` as the
campaign optimization goal:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/ads/meta/raw/customconversions" -sS -X POST  \
 -H "Content-Type: application/json" \
  -H "Idempotency-Key: <stable-key-for-this-conversion>" \
  -d '{
    "name": "<Product> — Activation",
    "product_slug": "<product_slug>",
    "event_name": "Activation",
    "custom_event_type": "OTHER"
  }'
```

Record the returned conversion id and `event_parameters` in `tracking.json`.
OS builds the product-scoped rule and verifies it against Meta. Reuse the same
Idempotency-Key and body on retry. If the outcome is unconfirmed, retain the key
and report the blocker for Egbe team recovery.

For a conversion-objective campaign, pass that exact id as
`CampaignSpec.custom_conversion_id`. The OS creates the ad set's
`promoted_object` itself, using the configured shared pixel plus this id; do
not supply a pixel id from product code or an artifact. The gateway rejects a
conversion optimization request without a custom conversion or with a different
pixel.

## Verification

Do not report the pixel as working from code inspection alone:

1. Load the live URL and confirm a request to
   `https://www.facebook.com/tr/?id=<pixel_id>&ev=PageView` carrying
   `cd[content_name]=<product_slug>` and `cd[egbe_product_id]` matching OS tracking config.
2. Perform the activation action on the live site and confirm a request with
   `ev=Activation` and the product-scoped payload.
3. Read `GET $OS_URL/ads/meta/raw/pixels` and check `last_fired_time`.

These browser checks establish outgoing instrumentation, not Meta receipt or
custom-conversion matching. Record the evidence separately. `eligible` on the
conversion verifies its configuration only; `eligibility.event_matching` stays
`unverified`, and a clean plan does not upgrade that result.

If the actual event request lacks `content_name` or `egbe_product_id`, the
product-scoped rule cannot match that event. Report tracking as `degraded`, naming
the missing fields and observed pixel/event. Source code passing an object to
`fbq` does not establish what the browser sent. Do not mark the conversion as
working from `eligible`, `plan.ok`, a shared-pixel timestamp or an event name alone.
Use authorized provider diagnostics, when available, to distinguish receipt from
actual conversion matching. If that evidence is unavailable, report matching as
unverified. Missing parameters alone do not establish a category restriction;
check the evidence before naming a provider-side cause. Preserve the product
rule: event-only or caller-authored domain rules are not supported alternatives.

Two traps when reading Events Manager:

- A newly introduced custom event name does not appear as its own row
  immediately — allow up to about an hour before concluding it is missing. The
  Test events tab shows it instantly and is the only instrument that separates
  "not delivered" from "not displayed yet".
- The `Integration` column aggregates every source that ever sent that event
  name across the whole dataset. A browser event can show as `Conversions API`
  because some other property sends the same name server-side. Never use that
  column as evidence about a specific product's events.
- `last_fired_time` on pixels and custom conversions is unreliable on a shared
  account: it stays empty on conversions that are in fact matching. Confirm in
  Events Manager, not from that field.

## Tracking State

| State | Meaning |
|---|---|
| `verified` | outgoing PageView and the product's conversion event observed live with the configured pixel and both product parameters; provider receipt and conversion matching are reported separately |
| `degraded` | pixel installed but a required event or product parameter is missing, or a planned conversion goal cannot be verified |
| `not_configured` | no pixel ID in the app environment |

Conversion optimization needs a verified eligible product-scoped custom
conversion; a traffic campaign does not require creating that resource.
