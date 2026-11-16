# Meta execution records

Keep requests, IDs and evidence beside the relevant campaign, normally
`egbe-docs/marketing/campaigns/meta/<campaign>/`. Reference existing input records
when available; no research, strategy or report package is required.

Before a write save its exact endpoint/payload, time and request identity.
For plan/apply preserve the exact spec, plan/token and authorization context;
OS derives apply idempotency from the original token. Save responses, errors,
unknown outcomes and returned IDs immediately. Never overwrite an uncertain
attempt with a new one or store credentials in these records.

`campaign-state.json` keeps `channel: meta`, the known operational `status`
and `objects.campaign_id`, `adset_ids`, `ad_ids`. Record budget, destination,
media hashes and parent mapping when part of the operation. Requested fields
are not provider readback.

`launch-readback.json` holds `observed_at` (timezone-aware), `campaign`,
`adsets` and `ads`, each with the exact `id` and returned
`effective_status`/`status`. These are the `observed` rows from the state
endpoint; retain its full response and configuration reads alongside the
projection. Do not fabricate parent IDs or other fields absent from a read.

For a status or campaign-only pause, campaign ID/readback suffice; include known
selected child IDs when checking them. For build/launch, retain the complete
selected tree. This is recovery evidence, not a universal campaign schema.

Optional local check:

```bash
python3 scripts/validate-meta-artifacts.py --product-root <repo> \
  --campaign-path egbe-docs/marketing/campaigns/meta/<campaign> \
  --campaign-id <exact-id> --phase pause
```

Supported phases: `build-paused`, `launch-ready`, `launch`, `status`,
`monitoring`, `pause`. It checks saved IDs/status/timestamps and optional
numeric/recovery values, not live ownership, consent, current API validation,
report wording or business outcomes. For pause it proves the campaign is
non-serving, not that every child is independently paused.

Preserve any existing durable business/product/launch/experiment/variant IDs
and stable UTM mapping when provided; do not replace them with scheduler IDs.
When an index is used, update it consistently with the same exact IDs rather
than switching campaigns to make a check pass. Commit/share records according
to the project's collaboration workflow, not as a prerequisite to stopping spend.
