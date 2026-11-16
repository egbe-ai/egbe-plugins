# Product attribution

Read the live `/analytics/skill` and `/analytics/events`. Product events are canonical
Egbe events, not OpenAI event names. Useful funnel signals include `campaign-visit`,
`cta_click`, `signup_completed`, `activated` and `purchase` where applicable.

Use stable URLs with:

- `utm_source=openai`
- `utm_medium=paid_ai`
- `utm_campaign=<openai-campaign-slug>`
- `utm_content=<ad-slug>`

Do not encode user data or replace campaign slugs with orchestration IDs. Preserve
existing attribution when taking over a historical campaign: record its actual
UTMs and plan an explicit change rather than silently rewriting live URLs. The
portable checker uses the new-campaign convention for build/launch, not for audits.

Read `/analytics/<product_slug>/tracking` and available campaign/funnel reports.
Check that the actual destination loads product tracking; do not emit synthetic
business events to manufacture readiness. Do only bounded verification appropriate
to the requested integration, not a full unrelated product test.

Write `tracking.json` with destination, UTMs, analytics identity, evidence and
`active/degraded/blocked` state. If campaign-level slicing is unavailable, keep
site-wide signals separate; never assign all site purchases to this campaign.
Missing data is unavailable, not zero. Return the unavailable attribution fields
without substituting site-wide outcomes.

OpenAI Pixel/CAPI is optional: see [conversions](conversions.md). Captured `oppref`
and `obref` belong in consent-aware product runtime storage, not marketing docs.
Configured tracking, accepted events and attributed conversions are different facts.
