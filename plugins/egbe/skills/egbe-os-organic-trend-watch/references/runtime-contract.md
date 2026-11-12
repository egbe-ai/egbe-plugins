# Runtime contract

## Ownership

Direct use initializes `context.json` from the assignment; a research caller may
supply it instead. This skill owns collection, analysis and receipt files.
PMR additionally owns its combined report and integration receipt.

All paths below are relative to the workspace:

```text
egbe-docs/research/market/work/organic_trend_watch/
├── context.json
├── run-state.json
├── raw/
│   ├── manifest.json
│   ├── tiktok-enrichment-comments.json
│   └── *.json
├── media/
│   └── *.mp4
├── frames/
│   └── *.jpg
├── visual-analysis/
│   └── <observation-id-and-hash>.json
├── normalized/
│   ├── selection.json
│   └── videos.json
├── analysis.json
├── result.md
└── receipt.json
```

Never write outside this root. Every path stored in JSON is relative to this
root, uses `/`, and must not contain `..`.

Each `visual-analysis/*.json` receipt is bound to the ordered frame paths and
hashes, optional transcript hash, Organic visual-analysis instructions, OS
prompt contract, model role, and effective model. A valid completed receipt is
reused after a task retry or follow-up. A receipt with `status: unavailable` contains
no claims and records that neither frames nor a transcript were available.

## Context v1

```json
{
  "schema_version": 1,
  "section_id": "organic_trend_watch",
  "assignment": "What the collected short-video evidence should help answer",
  "product_context": "Relevant product, audience and constraints",
  "collection": {"discovery_limit_per_account": 30, "lookback_days": 60},
  "supporting_sections": [
    {"id": "target_audience", "label": "Target audience", "content": "..."}
  ],
  "sources": {
    "context": {"path": "egbe-docs/research/market/context.md", "source_sha256": "..."},
    "supporting_sections": [
      {"id": "target_audience", "path": "...", "source_sha256": "..."}
    ]
  }
}
```

Only `schema_version`, `section_id`, `assignment` and `product_context` are
required. `supporting_sections` may contain relevant supplied evidence with
unique IDs; no PMR section is prerequisite. `sources` is optional; supplied
source paths/hashes identify their provenance, and supporting source IDs must
match their content entries. PMR verifies those local files/receipts against its
workspace before publishing; direct callers are responsible for the provenance
of supplied context. The runtime binds the exact context hash.
Do not use failed, stale or tampered receipts as completed research.

Optional `max_analysis_videos` can lower the default 30-video resource ceiling
for the v1 enrichment adapter. This is not a research quality threshold.
Selection records exclusions so a capped sample is not complete coverage.

Optional `collection` configures paid discovery: `discovery_limit_per_account`
is an integer from 1 to 30; `lookback_days` is a positive integer. Omitted fields
default to 30 and 60. These adjustable adapter defaults are not evidence
sufficiency criteria. Account/run limits, the total analysis cap and the dataset
read limit remain independent. Direct and PMR callers use this same context.

## Run state v1

Use `scripts/run-state.py` rather than editing this file directly. Steps are:

1. `discovery`
2. `collection`
3. `normalization`
4. `visual_analysis`
5. `synthesis`
6. `render`

Each step is `pending`, `running`, `completed`, or `failed`. Provider runs are
keyed by a stable logical key such as `tiktok-discovery`; the key and input hash
identify retry intent. Immediately before the first POST, the runner saves
`collection_window` (effective parameters, `reference_at`, `oldest_post_date`),
the exact actor input and each run's `request_json`, `attempted_at`, and stable
idempotency key. Initialization and input previews do not start collection.
The date lower bound is UTC midnight `lookback_days` before the first attempt;
the analytical upper bound is its exact `reference_at`. Both platforms request
the fixed lower date; local normalization enforces the full analytical window.

Persist `run_id` and `dataset_id` immediately after the response, before polling.
After any attempted submission, the builder preserves its input bytes or rejects
a conflict. Missing responses/handles retain `SUBMITTING` state. A retry may ask
the gateway to recover the same saved key/request; it never creates a replacement
operation. A gateway reconciliation error needs inspection, not a new key. This
is not an exactly-once guarantee for the external provider.

`run-state.py init` never discards existing collection because of age or a
changed context. Resume unchanged work; use a new study ID for a different
assignment. When a fresh collection is explicitly needed, `run-state.py refresh`
archives finished or terminal work and creates a new `collection_epoch` for
idempotency. It refuses active or uncertain provider starts. The narrower
`restart-failed-collection --key ... --run-id ...` flow validates the exact
terminal failure before archiving; see `provider-contract.md`. Preserve original
collection times so old evidence is not relabeled as fresh.

## Raw manifest v1

```json
{
  "schema_version": 1,
  "collection_epoch": "opaque-run-epoch",
  "collection_started_at": "2026-07-31T12:00:00Z",
  "collection_completed_at": "2026-07-31T12:10:00Z",
  "accounts": [
    {
      "platform": "tiktok",
      "handle": "example",
      "account_type": "official",
      "product_keywords": ["product"]
    }
  ],
  "accounts_source": {
    "path": "raw/accounts.json",
    "sha256": "..."
  },
  "datasets": [
    {
      "platform": "tiktok",
      "kind": "discovery",
      "path": "raw/tiktok-discovery.json",
      "sha256": "..."
    }
  ],
  "linked_datasets": [
    {
      "kind": "tiktok-comments",
      "parent_logical_key": "tiktok-enrichment",
      "path": "raw/tiktok-enrichment-comments.json",
      "sha256": "..."
    }
  ],
  "provider_runs": [
    {
      "logical_key": "tiktok-discovery",
      "provider": "apify",
      "actor_id": "clockworks/tiktok-scraper",
      "run_id": "...",
      "dataset_id": "...",
      "status": "SUCCEEDED",
      "input_sha256": "...",
      "input_contract_version": "apify-inputs-v1",
      "input_keys": ["oldestPostDateUnified", "profileSorting", "profiles", "resultsPerPage"],
      "actor_metadata": {
        "path": "raw/tiktok-discovery-actor-metadata.json",
        "sha256": "..."
      }
    }
  ]
}
```

Allowed account types are `official`, `shadow`, `partner`,
`shadow-or-partner`, and `viral` (an independent high-performing account in the
same problem/category space). A dataset file may contain an OS envelope
(`data.rows`), a provider object with `items`, or a raw JSON array. Its declared
hash must match.

The manifest contains at most six accounts in v1. Its collection epoch and
provider handles, inputs, actor metadata, and raw hashes must match
`run-state.json` exactly. Discovery applies to each declared account platform;
enrichment is optional according to the question's evidence needs. A discovery-only
result is valid without inventing enrichment receipts. Terminal failures may be
explicit coverage gaps; no started run may disappear silently. Successful
TikTok enrichment also requires the hash-bound linked-comments bundle, even
when the actor exposed no comment dataset URLs.

## Receipt v1

`scripts/finalize-receipt.py` creates the receipt only after validating all
artifacts. It binds the collection epoch and exact context, raw manifest, normalized observations,
analysis, and rendered Markdown by SHA-256. `collected_at` equals the manifest's
`collection_completed_at`; `completed_at` cannot precede it. At least one
successful collected Apify dataset is required. Required discovery and any started
enrichment must be successful or a recorded terminal failure; running/unknown
handles block sealing. Needed but unavailable modalities remain coverage gaps,
not permission to infer them from captions or counts.

`status` is `completed`, `partial` or `no_data`. `coverage` records the matching
`complete`, `partial` or `no_data` status, collected/selected/analyzed counts and
gaps. Limited or absent usable evidence is a valid result, distinct from a
corrupt receipt or an unfinished/uncertain provider call. See `output-contract.md`.
