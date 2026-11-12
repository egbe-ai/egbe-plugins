# Targeting and creative assembly

Use the requested targeting, format, budget, copy, assets and destination.
Resolve missing operation inputs before writing; preserve unaffected settings
when editing an existing object.

Resolve targeting with `GET /ads/linkedin/targeting/facets` and
`GET /ads/linkedin/targeting/entities`. Use returned facet/entity URNs, not guessed
company names or copied example IDs. Explicit locations are required. Values
within a facet are OR; included facets are AND; exclusions remove matching members.
The first release exposes locations, industries, staff count ranges, seniorities,
job functions, titles, employers and skills.

Call audience-estimate and budget-pricing with the proposed targeting/format.
Record estimates as estimates. Check provider minimum/suggested CPC and daily
budget against the authorized amount. A too-small audience is a decision to
discuss targeting, not permission to silently broaden it. Audience expansion
and offsite delivery are disabled.

## Two creative formats

- Single Image: image, headline, introductory text, CTA and exact landing URL.
  Current gateway bounds: headline ≤200 and text ≤3000 characters.
- Text Ad: headline ≤25 and description ≤75 characters, plus image and landing URL.

These formats require separate native campaigns. Verify asset dimensions/cropping
against the current format rules below.

Use approved product assets or generate an image through Egbe OS: discover the
current `images` capability via `GET $OS_URL/`, read its live skill and exact
generation contract. Save the resulting PNG/JPEG locally, inspect its readability
and claims, then upload its bytes through LinkedIn images. An OS-generated URL,
an image URN and a creative ID are different things; only the returned LinkedIn
`urn:li:image:...` goes in `image_id`. No embedded credentials or external
provider keys are needed.

Read the format's current rules before producing final assets:
[Single Image](https://business.linkedin.com/advertise/ads/sponsored-content/single-image-ads),
[Text Ads](https://business.linkedin.com/advertise/ads/text-ads),
[Advertising policies](https://www.linkedin.com/legal/ads-policy).
Use truthful, substantiated claims and a matching destination. No deceptive UI,
unsupported endorsements or fabricated customer proof.

## Measurement

Bind stable UTMs before creative creation. Read the product's Egbe analytics
workflow when integrating attribution; reuse existing tracking rather than adding
a second tracker. Verify destination preserves the intended path/query and that
product analytics can distinguish the campaign. Record unverified attribution.
Traffic impressions/clicks are available independently of Insight Tag/CAPI.
If provider outcome measurement is requested, follow [Conversions](conversions.md).
It is optional and does not implicitly change the approved traffic strategy.
