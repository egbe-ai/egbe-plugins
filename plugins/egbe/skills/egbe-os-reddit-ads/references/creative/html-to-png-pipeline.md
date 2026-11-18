# HTML To PNG Pipeline

Use this workflow for Reddit static banner creatives. There are two ways to
render the same template HTML:

- **Egbe render**: works without a terminal or local browser, including through
  the Egbe connector (`egbe_write`). The PNG is stored as an uploaded creative
  and the response carries its CDN URL. Each render uses one `ad-assets:uploads`
  allowance, the same as an upload.
- **Local capture**: a workspace with Chrome/Chromium renders with the bundled
  script. Use it to iterate on a draft without spending uploads, then upload the
  final PNG.

## Egbe Render

Send the completed HTML document as a JSON string:

```bash
POST $OS_URL/tools/render/html
{"html":"<!doctype html>...","width":1080,"height":1350}
```

Optional `device_scale` (integer 1-3, default 1) multiplies both pixel
dimensions; keep it at 1 for the template sizes below. OS `response.data` is the
upload shape plus the PNG's pixel size:
`{"url":"https://<cdn>/<key>","key":"<key>","size_bytes":12345,"content_type":"image/png","width":1080,"height":1350,"device_scale":1}`.
`response.data.url` is already a hosted creative: use it as Reddit `media_url`
directly, or as `source_url` where another upload asks for one. Do not upload it
again.

The page renders in an isolated browser at exactly `width` x `height` CSS
pixels, without scrolling:

- JavaScript does not run and nothing is fetched. Inline every stylesheet and
  embed images and fonts as `data:` URIs; links to web fonts or image URLs
  render as missing. The bundled templates already meet this.
- HTML is limited to 5 MiB, each side to 4096 px and the PNG to 10 MiB; a render
  must finish within 20 seconds.
- `422` means the request was out of bounds. `408` means the page was too slow:
  simplify it. `429` means the upload allowance is used up. `503` means rendering
  is unavailable: retry later or use local capture.

## Local Capture

Render a completed template HTML file with the bundled local capture script:

```bash
scripts/capture-ad.sh <html-file> <png-file> 1080 1350 --keep-html
```

For final production output, omit `--keep-html` if you do not need the
intermediate HTML.

The script:

- finds a Chrome/Chromium binary on Linux or macOS (Chrome, Chromium, Canary,
  Edge or Brave app bundles), or uses `CHROME_PATH` when set to an executable;
- captures the exact requested dimensions;
- validates the PNG dimensions with `file`;
- fails non-zero when output size does not match.

If the runtime has no usable Chrome/Chromium binary, the script lists every
location it searched. Set `CHROME_PATH` to an installed browser executable, or
use Egbe render.

## Required Dimensions

Use the selected template's exact dimensions:

```text
1080 x 1350 (4:5) or 1080 x 1080 (1:1)
```

For a square template, pass `1080 1080` to the capture script or
`"width":1080,"height":1080` to Egbe render. Do not use full-page screenshots.
These are our template sizes, not an upload API constraint.

## Source HTML

Start from `assets/static-banners/<family>/template.html`.

Before rendering:

1. Replace every template placeholder.
2. Replace `{{accentColor}}` with a product or default hex color.
3. Keep all text inside schema limits.
4. Avoid adding elements not present in the template.
5. Save the adapted file under the campaign artifact directory when the
   workspace has one; through the connector, keep the exact HTML you sent.

## QA

After rendering, confirm:

- dimensions match the template: `1080 x 1350` or `1080 x 1080` (`file
  <png-file>` locally, `response.data.width` and `height` for Egbe render);
- text is readable at feed size;
- no text is clipped;
- no placeholder remains visible;
- no image or font is missing;
- creative follows `references/creative/static-banner-qa.md`.

Open the PNG or its URL to check the visual items. If the creative fails QA,
fix the HTML and render again; do not use the failed URL.

## Upload

A local PNG is uploaded only after QA passes:

```bash
POST $OS_URL/tools/ad-assets/upload
```

See [API reference](../runtime/api-reference.md#asset-upload) for multipart fields,
the JSON forms and upload sessions for the Egbe connector, and response shape. Use the
returned CDN URL for Reddit image post creation. Do not host ad creatives from the
product app or arbitrary public URLs.

## If Rendering Is Unavailable

If neither Egbe render nor local capture works, report that rendering is blocked
and preserve the source HTML. An unrendered template is not an uploadable image;
do not silently substitute a text-only post.
