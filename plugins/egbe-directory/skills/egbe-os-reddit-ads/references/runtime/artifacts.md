# Reddit execution records

Keep requests, IDs and evidence beside the relevant campaign, normally
`egbe-docs/marketing/campaigns/reddit/<campaign>/`. Reference existing input
records when available; no research, strategy or report package is required.

Before campaign creation save its `create_idempotency_key` and exact
`create_payload` in `campaign-state.json`. Retain every attempt's endpoint,
time, response/error and unknown outcome. Save returned IDs immediately.
Child requests/keys also need recovery records, but their success caches are
not durable campaign-create recovery. Do not store credentials.

The state retains `channel: reddit`, observed operational `status` and
`objects.campaign_id`, `ad_group_ids`, `ad_ids`, plus post IDs for creative
operations. Retain budget units, destination and selected parent mappings where
relevant. A status or campaign-only pause needs no creative/research package.

`launch-readback.json` records timezone-aware `observed_at`, `campaign`,
`ad_groups` and `ads`: exact `id`, provider `configured_status` and
separate effective/delivery/rejection fields. Save parent IDs when returned
and retain raw responses; do not infer missing fields.

## Activation evidence

A new attempt records `activation.started_at` and `accepted_mutations`.
For each accepted status request save the returned `object_type`
(`campaign`, `ad_group` or `ad`), `object_id`, `requested_status`,
`mutation_accepted` and `mutation_accepted_at`. Readback must follow those
receipts. Do not reuse receipts from an earlier pause/launch cycle.
Pending attempts retain actual reads and `status: activation_pending`
without a new successful launch/restart timestamp. Read-only observation can
describe already ACTIVE configuration, but cannot establish a new activation.

## Optional local check

```bash
python3 scripts/validate-reddit-artifacts.py --product-root <repo> \
  --campaign-path egbe-docs/marketing/campaigns/reddit/<campaign> \
  --campaign-id <exact-id> --phase pause
```

Phases: `build-paused`, `launch-ready`, `launch`, `status`,
`monitoring`, `pause`. The check verifies saved ID/status/timestamp integrity
and current-attempt activation evidence, not live freshness, ownership, consent
or a business verdict. Pause checks the campaign is non-serving, not that every
child's configured status changed. No narrative report is required.

Preserve supplied durable business/product/launch/experiment/variant IDs and
UTM mapping; do not substitute scheduler IDs. Keep any used index consistent
with the selected exact IDs. Save confirmed stop time/reason without replacing
history with planned deadlines. Project versioning practices apply, but a
missing commit or report never prevents stopping spend.
