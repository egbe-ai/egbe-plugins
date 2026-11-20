# Reddit Pixel And Product Analytics

Reddit pixel tracking and OS product analytics are separate systems.

OS analytics is the source of truth for product funnel events. Reddit custom
events are channel-side mappings used for ad-network optimization.

## Canonical Event Source

Read when configuring product-event tracking:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/analytics/skill" -s
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/analytics/events" -s
```

Do not create new product event names for Reddit. Use canonical events such as
`signup_completed`, `activated`, and `purchase`, with Reddit-specific details in
UTMs and payload fields.

## Reddit Event Mapping

When Reddit needs product-scoped custom events, map canonical events to a
channel-side name:

| Product event | Reddit custom event example |
|---|---|
| `signup_completed` | `Signup_<product_slug>` |
| `purchase` | `Purchase_<product_slug>` |

The mapping must be recorded in campaign artifacts.

## Pixel Placement

Install the Reddit Pixel base snippet in the shared marketing layout that covers
landing, signup, checkout, and conversion pages. Installing it only on the
landing page is insufficient.

Fire `rdt('track', '<event_name>')` only after the conversion action succeeds,
for example on signup success or purchase confirmation.

## Tracking evidence

Record separately whether the pixel is installed, the expected product-scoped
event is observed, and product analytics is available. A pixel ID required by
the ad-group API does not prove website tracking works. Missing event readback
does not authorize changing the requested objective. Report the limitation,
and do not claim observed
conversion tracking from source code or synthetic events alone.
