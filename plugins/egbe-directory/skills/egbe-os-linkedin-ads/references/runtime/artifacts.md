# Campaign continuity

Paths are relative to the product repository root:

```text
egbe-docs/marketing/campaigns/linkedin/
  channel-readiness.json
  campaigns.json
  <linkedin-slug>/
    creatives.json
    tracking.json
    campaign-state.json
    operations.json
    launch-readback.json
    change-log.md
    assets/
    monitoring/check-<UTC-timestamp>.md
```

Create artifacts when needed, not empty files for future phases. Never store
member tokens, signed upload URLs, raw customer records or private credentials.

- `campaigns.json`: campaign slug/path and selected campaign; preserve caller
  product/experiment identifiers when provided. Explicit task selection wins.
- `creatives.json`: approved text/image paths, format, stable local variant ID,
  exact UTM destination, provenance and substantiation. Not a provider payload.
- `tracking.json`: `utm_source=linkedin`, `utm_medium=paid_social`,
  `utm_campaign=<linkedin-slug>`, `utm_content=<variant>`; product analytics
  verification and attribution gaps. Provider conversions default `not_configured`.
  When requested, record rule IDs/methods, campaign associations, event hooks,
  event_id_prefix and configuration/ingestion/attribution verification separately.
  Save event receipt IDs/status, never their customer matching payloads.
- `campaign-state.json`: product slug, native account and organization URNs,
  group ID, each campaign ID/format/budget, creative IDs/parents/image URNs,
  observed statuses and timestamp. One experiment may contain both formats:
  list their separate campaigns and total authorized daily budget.
- `launch-readback.json`: timestamped GET responses for group, campaigns,
  creatives and images; preserve moderation/serving reasons and exact bindings.
- `change-log.md`: actual mutations, before/after observations and authority.
- Saved observations: query/returned periods, fetch time, source, currency,
  metrics, availability and attribution gaps. Simple reads need no new files.

Before each mutation append to `operations.json`:

```json
{"operations":[{"operation_id":"group-create","method":"POST","path":"/ads/linkedin/campaign-groups","idempotency_key":"linkedin-pilot-group-v1","payload":{"product_slug":"example-product","name":"LinkedIn pilot","schedule":{"start":1800000000000}},"status":"prepared","result_ids":[]}]}
```

Replace the illustrative start with the approved Unix-millisecond schedule.
Store the exact configuration body and key before calling. Runtime customer-event
retry payloads belong in private product storage, not this artifact.
For image bytes store the local file
path and digest, not base64. States: prepared, unconfirmed, succeeded, failed.
A lost response is unconfirmed. Persist returned IDs even if later steps fail.
Same operation means same payload/key; resolve it before authorizing a changed one.

Reconstruct missing local history from owned OS reads and label unknowns. Urgent
authorized pause must not wait for invented strategy or complete documentation.
