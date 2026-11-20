# Read-only Meta launch checks

Inspect exact selected campaign/child IDs, not name-matched substitutes.
No provider mutation, create, repair or schema probing belongs in this check.

Read the authorized configuration and saved IDs; refresh
`/ads/meta/campaigns/{id}/state?expect=PAUSED` and raw configuration needed
to compare targeting, budget, media and destination to the requested values. Verify paused
state and parent IDs; image ads need image hashes, video ads also need thumbnails.
Check account access, destination and measurement required by the chosen
objective; see [pixel](../runtime/pixel-install.md) and
[attribution](../runtime/shared-analytics-attribution.md).

Report mismatches/unavailable reads explicitly. Missing objects require separately
authorized build/repair, not a write disguised as readiness. Activate through
[launch](launch.md) only when currently authorized.
