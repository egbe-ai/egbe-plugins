# Campaign artifacts and continuation

All paths are relative to the actual product repository root, not the current
shell directory or an instance workspace. Reuse its existing `marketing/` tree.
Do not require PRD, scaffold, heartbeat or git remotes merely to manage a campaign.

```text
egbe-docs/marketing/campaigns/openai/
  channel-readiness.json
  campaigns.json
  <openai-campaign-slug>/
    creatives.json
    tracking.json
    campaign-state.json
    launch-readback.json
    operations.json
    change-log.md
    monitoring/
      check-<UTC-timestamp>.md
```

Create files when their phase needs them, not empty placeholders for every future
phase. Store public creative assets beside `creatives.json` or link existing
repo-relative assets. No credentials, raw customer emails, click identifiers,
session cookies or customer conversion payloads belong in these artifacts.

## Resolve exactly one campaign

`campaigns.json` example:

```json
{
  "channel": "openai",
  "selected_campaign": "openai-discovery-001",
  "campaigns": [{
    "campaign_slug": "openai-discovery-001",
    "campaign_path": "egbe-docs/marketing/campaigns/openai/openai-discovery-001",
    "utm_campaign": "openai-discovery-001"
  }]
}
```

An explicit campaign ID/slug in the task wins over the selected pointer. Resolve
the ID against recorded state; zero/ambiguous matches require an OS owned-resource
read, not a guessed campaign or a new create. For an existing campaign with no
local history, reconstruct its factual IDs/readback and label unknown history.
Missing historical documents do not block reads or an authorized emergency pause.

Use one stable `openai-` slug for the folder and `utm_campaign`. Provider names
may include an OS recovery suffix: names are not IDs. Preserve supplied durable
`business_id`, `product_id`, `launch_id`, `experiment_id`, `variant_id` in the index
entry when provided by a promotion caller. Do not fabricate these for standalone
work or put scheduler/session/task IDs into the campaign domain contract.

## Inputs and tracking

- `channel-readiness.json`: `{channel:"openai", product_slug, checked_at,
  account:{id,currency_code,timezone}, blockers:[]}`; add observed payment,
  delivery and conversion-setup availability, distinguishing unknown from false.
- The optional index `plan_path` may link a caller-provided instruction/configuration
  document by repository-relative path. No particular document or format is required.
- `creatives.json`: `{ad_groups:[{slug,context_hints,bidding_config}],
  ads:[{slug,ad_group_slug,title,body,target_url,asset_path}]}`. Slugs are local
  planning identities; provider IDs go in campaign-state. Record asset provenance
  and claim support as needed. This document is not an API payload.
- `tracking.json`: `{destination_url,utm:{source:"openai",medium:"paid_ai",
  campaign:<slug>,content:<ad-slug>},tracking_state:"active|degraded|blocked",
  analytics:{product_slug,campaign_attribution:"available|unavailable|unverified"},
  conversions:{state:"not_configured|configured|verified|unavailable"}}`.
  Record verification evidence and limits; `configured` does not mean attributed.
  Each ad uses the same campaign UTM and its own stable `utm_content`.

## Execution state versus evidence

`campaign-state.json` minimum after a campaign has been created or recovered:

```json
{
  "channel": "openai",
  "campaign_slug": "openai-discovery-001",
  "product_slug": "example-product",
  "status": "paused",
  "budget": {"daily_budget_usd": 25, "currency": "USD"},
  "objects": {
    "campaign_id": "cmpn_example",
    "file_ids": ["file_example"],
    "ad_groups": [{"id": "group_example", "campaign_id": "cmpn_example"}],
    "ads": [{"id": "ad_example", "ad_group_id": "group_example", "file_id": "file_example"}]
  },
  "updated_at": "2026-09-09T12:00:00Z"
}
```

This is a concise factual execution summary. Desired changes remain in requested
configuration and pending operations until read back. Use `status:"unknown"` after an
uncertain mutation; never claim paused/active from intent. Optional `blockers`,
`delivery_state`, `source_id`, `pixel_id`, `conversion_event_setting_id` and factual
launch/pause timestamps can be added. Keep source/goal bindings when configured.

`launch-readback.json` is a timestamped OS observation, not desired state:
`{observed_at,campaign:<GET data>,ad_groups:[<GET data>],ads:[<GET data>]}`.
Preserve provider fields, IDs, parent bindings, statuses, budget and destination.
Refresh this snapshot after relevant mutations; use change-log and monitoring
files for history. Read/list all owned children and filter by exact parent IDs to
detect unexpected children, not just the IDs already present in local state.

## Durable operations and interrupted work

Before a management mutation, write/update `operations.json`:

```json
{
  "operations": [{
    "operation_id": "create-campaign-1",
    "method": "POST",
    "path": "/ads/openai/campaigns",
    "idempotency_key": "openai-discovery-001-create-1",
    "payload": {"name":"openai-discovery-001","product_slug":"example-product","daily_budget_usd":25,"location_ids":["resolved-location-id"],"status":"PAUSED"},
    "status": "prepared",
    "result_ids": []
  }]
}
```

States: `prepared`, `unconfirmed`, `succeeded`, `failed`. Persist the exact method,
relative path (including query parameters), payload and key before sending. Update
the same entry after each attempt; keep IDs/readback even if later steps fail.
Timeout/disconnection is `unconfirmed`, not `failed`. Retry only with that exact
request/key. A changed desired operation gets a new entry/key only after resolving
the previous outcome. Provider response saying Egbe team reconciliation is required
is a stopping condition, not an invitation to generate another key. Do not launch
with unresolved prepared/unconfirmed management writes.

Do not journal customer conversion bodies here: runtime event IDs, consent,
retry state and delivery receipts belong in the product's protected server store.
`tracking.json` records the integration and verification, not per-customer data.

`change-log.md` is append-only: UTC timestamp, operation, reason/evidence,
authorization reference, before/after, IDs, result and any next recovery action.
Saved read-only observations include request bounds, returned bounds, fetch time,
sources, currency, metrics and availability/attribution gaps. Simple reads need
no new files or change-log entry.

## Phase self-check

Run `scripts/validate-openai-artifacts.py --product-root <root> --phase <phase>`.
Use `--campaign <slug>` for an explicit campaign instead of the selected pointer.

| Phase | Required evidence |
|---|---|
| readiness | channel-readiness (may honestly contain blockers) |
| creative-assembly | campaign index and creatives; validate an index plan_path when supplied |
| tracking | index, tracking |
| build-paused | index, state, complete paused readback, creatives, tracking, operations, change-log |
| launch | same execution evidence, active intended path, no unresolved operations |
| edit | index, state/readback, operations and change-log; not a new build checklist |
| recovery | index, operations, change-log and partial factual state if an ID is known; missing children allowed |
| monitoring | index, state, saved timestamped observation; other historical files optional |
| pause | index, state/readback showing paused campaign, change-log |

The checker is local and read-only. It checks JSON, paths, IDs/parents, UTMs,
state/readback agreement, not live freshness, permissions, marketing merit or
whether an observation is true. A blocked but factual record is useful output;
passing structure alone never makes a blocked campaign launchable.
