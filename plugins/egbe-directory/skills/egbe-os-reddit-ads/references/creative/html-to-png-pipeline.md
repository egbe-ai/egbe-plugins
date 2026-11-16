# HTML To PNG Pipeline

Use this workflow for Reddit static banner creatives.

## Preferred Path

Render a completed template HTML file with the bundled local capture script:

```bash
scripts/capture-ad.sh <html-file> <png-file> 1080 1350 --keep-html
```

For final production output, omit `--keep-html` if you do not need the
intermediate HTML.

The script:

- finds a Chrome/Chromium binary;
- captures the exact requested dimensions;
- validates the PNG dimensions with `file`;
- fails non-zero when output size does not match.

## Required Dimensions

Use the selected template's exact dimensions:

```text
1080 x 1350 (4:5) or 1080 x 1080 (1:1)
```

For a square template, pass `1080 1080` to the capture script. Do not use
full-page screenshots. These are our template sizes, not an upload API constraint.

## Source HTML

Start from `assets/static-banners/<family>/template.html`.

Before capture:

1. Replace every template placeholder.
2. Replace `{{accentColor}}` with a product or default hex color.
3. Keep all text inside schema limits.
4. Avoid adding elements not present in the template.
5. Save the adapted file under the campaign artifact directory.

## QA

After capture:

```bash
file <png-file>
```

Confirm:

- dimensions match the template: `1080 x 1350` or `1080 x 1080`;
- text is readable at feed size;
- no text is clipped;
- no placeholder remains visible;
- creative follows `references/creative/static-banner-qa.md`.

## Upload

Upload only after QA passes:

```bash
POST $OS_URL/tools/ad-assets/upload
```

See [API reference](../runtime/api-reference.md#asset-upload) for multipart fields
and response shape. Use the returned CDN URL for Reddit image post creation. Do not host ad
creatives from the product app or arbitrary public URLs.

## If Local Capture Is Unavailable

If the runtime has no usable Chrome/Chromium binary, report that rendering is
blocked and preserve the source HTML. An unrendered template is not an uploadable
image; do not silently substitute a text-only post.
