# Keyword ideas

Use `POST /ads/google/keyword-ideas` to read provider keyword suggestions and
historical metrics. This operation does not create campaign keywords.

```http
POST /ads/google/keyword-ideas
Content-Type: application/json
```

```json
{
  "keywords": ["contract review software"],
  "pageUrl": "https://product.example",
  "geoTargets": ["geoTargetConstants/2826"],
  "language": "languageConstants/1000"
}
```

Use the requested seeds and market, not this example.
At least keywords or pageUrl is needed. There are three distinct seed modes:
keywords only, URL only, and combined keyword-and-URL. A keyword-only response
may repeat the submitted seeds without useful expansion; URL ideas can be
generic. Do not invent missing ideas. Supplying both uses the combined seed,
not two independently aggregated queries.

Supply geo constants and language deliberately. The provider currently defaults
an omitted/empty geography to the US and omitted language to English. This is
an API default, not a recommendation or a campaign-targeting setting. Keyword
research does not apply locations to a campaign.

The OS response includes `data.ideas` and the provider response in `data.raw`.
Retain relevant rows with their query, geography/language, source and retrieval
time. No separate keyword-plan file is required.

Historical search volume and top-of-page low/high bids describe the provider's
observed market. Read monetary units as returned; micros are millionths of the
account currency, not an FX conversion. Historical bid ranges are not a
guaranteed actual CPC, traffic forecast or executable starting bid. The endpoint
does not set a bid or campaign budget.
