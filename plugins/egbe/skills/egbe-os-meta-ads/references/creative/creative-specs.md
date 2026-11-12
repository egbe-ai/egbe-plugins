# Meta image operations

Use the requested format/placements. Common production canvases are
1080×1080 square, 1080×1350 feed portrait and 1080×1920 vertical; these are
conventions, not a universal API guarantee. Verify selected placement needs.

Inspect exports for clipping, unreadable text, missing glyphs/placeholders and
unintended visual claims. Preserve supplied content; do not invent UI or proof.
Generate requested assets through OS or reuse authorized supplied files.
Preserve paid generation request IDs and results before considering a retry.

Upload PNG/JPEG via `POST /ads/meta/raw/adimages` with `image_base64` and
`filename`. Save the Meta hash: `CampaignSpec.creatives[].image_ref` uses it,
not a path or arbitrary URL. See [API](../runtime/api-reference.md) and
[video](talking-head.md).
