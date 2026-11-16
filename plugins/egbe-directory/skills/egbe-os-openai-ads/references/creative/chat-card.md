# Chat-card creative production

Read this when drafting or changing an image ad, not for a metrics-only audit.

## Provider requirements

- [Ads API](https://developers.openai.com/ads/api-reference/ads): `chat_card`,
  title 3–50 characters, body up to 100, real target URL and uploaded `file_id`.
  On creative updates send the complete object. Editing an ad can trigger review.
- [Files API](https://developers.openai.com/ads/api-reference/files): upload the
  image, then attach its returned file ID. A generated file alone is not an ad.
- [OpenAI ad policies](https://openai.com/policies/ad-policies/): check the offer,
  claims, creative and destination, including restricted categories. Do not imply
  OpenAI endorses the product or that the card is a ChatGPT response.
- Check current image/crop requirements in official docs and provider validation.
  Do not copy another network's dimensions, text-overlay rules or file limits.
  `paused`, `in_review` and `approved` are separate facts; paused creation is not
  policy approval. Return a rejection and its reason instead of bypassing review.

## Generate → inspect → upload → attach

1. Read `$OS_URL/images/skill` and `GET $OS_URL/images` using the current
   `OS_API_KEY`. Choose an available model within the task's cost/quality scope;
   never request OpenAI provider keys or introduce `IMAGE_API_KEY`.
2. Call `POST $OS_URL/images/generations` per that live skill. Describe the actual
   product, intended visual idea, framing, crop-safe subject and what must not be
   fabricated. Existing approved images may be reused instead of regenerated.
3. Save and view the returned bitmap. Check legibility at card size, artifacts,
   product accuracy and cropping. Fix an actual defect, not by unbounded model
   probing. Preserve the prompt/model and approved asset path in campaign records.
4. Use the returned image's stable public `url` when `stored:true`. If only
   base64 is available, save it and use an OS storage capability discovered from
   the root skill to obtain a public URL; do not regenerate just to upload, pass
   local paths to the Ads API, or invent hosting URLs.
5. `POST $OS_URL/ads/openai/uploads` with `{product_slug,image_url}` and a saved
   idempotency key. Save its returned `data.id` (the uploaded file ID).
6. Attach that ID as `creative.file_id` when creating/updating the paused ad.
   Independently read the ad back and verify image, title/body, tracked URL and
   status. Inspect the card in Ads Manager/preview when available; do not claim
   rendered-card verification from JSON alone.

Finish with approved local assets and recorded provider IDs/readback, or identify
the exact unfinished operation. Keep credentials and customer data out of artifacts.
