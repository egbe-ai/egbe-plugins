# OpenAI destination requirements

Use for OpenAI ad destinations, not the account or conversion-readiness workflow.
Apply network checks to the same evidence as the common visitor-path review.
Technical sources were checked 2026-09-29; verify current applicable wording.

For a complete visitor-path review, apply the `egbe-os-destination-readiness` skill with
this reference in one audit run. If missing locally, its full bundle is available
at `GET $OS_URL/skills/destination-readiness`.

- For a chat-card, inspect the actual `creative.target_url` and its destination.
  The [campaign/creative documentation](https://developers.openai.com/ads/campaign-management)
  requires an HTTP(S) URL within 2,048 characters, accessible to OpenAI ad
  crawlers. Include actual query parameters in the inspection; a browser success
  is not proof that a crawler can access the page. Do not substitute training
  crawler rules for ad-crawler requirements.
- If the actual integration uses product-feed ads, the
  [feed documentation](https://developers.openai.com/ads/product-feeds)
  requires publicly accessible HTTPS product pages/images. Compare the selected
  item's offer with the destination; do not add feed setup to a chat-card review.
- For an offer/content concern, consult the relevant
  [OpenAI ad policy](https://openai.com/policies/ad-policies/) and record the
  actual clause and applicability. The API's acceptance of a URL is not evidence
  of policy compliance. If the policy cannot be inspected, distinguish that
  uncertainty from observed broken or misleading visitor steps.

Return affected path, evidence, source and repair/recheck. Do not infer review
approval or launch eligibility from a usable destination. Image-production rules
remain in the creative workflow; this review does not create or edit an ad.
