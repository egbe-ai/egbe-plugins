# Optional static-banner templates

These optional HTML layouts produce static image assets. The API also supports
other authorized assets.

Families under `assets/static-banners/<family>/` are `question-hook`,
`data-proof`, `reddit-post-style`, `honest-breakdown` and
`bold-statement`. Read the selected schema/template and replace placeholders.
Schema character/line limits describe that layout, not the Ads API.

Replace `{{accentColor}}` in the CSS variable; use its `accent` class.
Escape inserted content. Do not invent statistics, testimonials, votes/comments
or endorsements to fill a template. Preserve clear promotion disclosure.

[Capture](html-to-png-pipeline.md), inspect using [QA](static-banner-qa.md), then
upload through OS.
