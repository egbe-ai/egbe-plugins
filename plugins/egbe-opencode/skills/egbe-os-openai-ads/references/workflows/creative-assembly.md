# Creative and targeting assembly

Use the requested context hints, destination, daily budget, bidding, copy and
assets. Resolve missing operation inputs before writing. For a copy edit,
preserve unaffected settings.

Read [Chat-card production](../creative/chat-card.md) for format/policy requirements
and the generate/upload/attach chain. Preserve the supplied assets and provenance.

The Ads API exposes no Google-style keyword planner, audience estimate or
search-term report. Context hints are inputs, not measured search demand.
Read the [minimum-budget note](readiness.md#minimum-daily-budget) before a build;
a provider constraint is not permission to increase the planned amount.

Record the chosen bidding type before building: strategy and an oCPC optimization
goal are immutable after creation. Conversion bidding needs verified owned setup.
Measurement selections for clicks/impressions campaigns can change separately
through [conversions](conversions.md); optional measurement is not a strategy change.

Assemble `creatives.json` with local ad-group/ad slugs, context hints, bid settings,
chat-card title/body, exact tracked destination and actual asset paths. These are
local assembly records, not raw API payloads. Verify language, limits and asset
bindings before upload. Keep assets available to the next agent; a draft alone
does not authorize upload, creation or launch.
