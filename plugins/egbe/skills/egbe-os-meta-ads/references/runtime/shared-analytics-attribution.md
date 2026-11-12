# Meta attribution

Read `/analytics/events` and the product's `/analytics/<slug>/tracking`
contract. Use canonical product event names; put channel/product details in
payloads and UTMs. Do not create synthetic product events as readiness proof.

Destination URLs retain stable `utm_source=meta`, `utm_medium=paid_social`,
`utm_campaign=<campaign slug/id>` and meaningful `utm_content`.
Use `utm_term` when needed for audience/placement. Do not put secrets or direct
personal identifiers in UTMs.

Read platform results and product stats/campaigns separately. Compare compatible
windows and attribution scope; site-wide observations are not campaign-attributed
conversions. Missing UTM slicing, delayed events and unconfigured tracking must
remain explicit, not zero. Pixel/platform events support network optimization;
the product event contract is maintained by analytics.
