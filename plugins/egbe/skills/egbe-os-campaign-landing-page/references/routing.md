# Routing and attribution

Implement the plan's destinations and variants. Keep the approved promise/action
consistent with what the destination actually does; report a mismatch rather than
editing campaigns or changing the offer inside page implementation.

Select a planned variant by its path or dedicated parameter such as `v`.
Do not use `utm_content` to switch content: that field identifies an ad/creative.
Preserve existing destination parameters and the channel's attribution contract.
A plan without variants does not require an A/B test.

For product handoffs, preserve the applicable UTM tags and channel click IDs
(`gclid`, `gbraid`, `wbraid`, `fbclid`, `msclkid`, `ttclid`,
`rdt_cid`, `li_fat_id`, `oppref`, `twclid`) and, where the Analytics
contract uses it, `egbe_vid` from its visitor identity. Validate values and decorate
only allowlisted destination hosts. Do not forward QA markers, credentials or
personal data in public links.

Use the current visit's accepted attribution, then the Analytics runtime's stored
first touch where applicable. Refresh decorated links when identity/consent changes
and before pointer, keyboard, copied or middle-click navigation. A click beacon
must not block leaving the page. Keep path/query before any fragment and confirm
tags survive actual redirects.

Use the current canonical Analytics events and required fields. Log action intent
separately from server-confirmed completion; a click to another product does not
prove signup, payment or delivered value there. Report missing downstream attribution
or an unreadable result without fabricating conversions.

Use declarative tracker attributes for ordinary links only. For dialogs, calendar
launchers and dynamically rewritten URLs, track from the actual handler and verify
with the real tracker loaded; automatic anchor handling can bypass the interaction.
