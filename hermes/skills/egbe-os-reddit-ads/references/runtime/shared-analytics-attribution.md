# Reddit attribution

Read `/analytics/events` and the product tracking contract. Use canonical product
events, not channel-specific product names; preserve Reddit mappings separately.
Do not generate synthetic conversion events as readiness proof.

Destination URLs retain `utm_source=reddit`, `utm_medium=paid_social`,
stable `utm_campaign=<campaign slug/id>` and meaningful `utm_content`.
Keep product details in event payloads; no secrets or personal identifiers in UTMs.

Read Reddit delivery/click/spend metrics and product campaign visits/funnel
events separately. Compare compatible windows/attribution scope. Missing or
delayed product data is not zero, and site-wide totals are not campaign results.
Reddit comments, clicks and reactions are not product conversion events.
