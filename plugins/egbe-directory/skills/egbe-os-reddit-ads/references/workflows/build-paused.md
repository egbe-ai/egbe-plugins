# Build paused Reddit objects

Use the requested configuration and [API payloads](../runtime/api-reference.md).
Inspect account, funding, wallet and recorded IDs. Reuse confirmed objects from
this operation; do not recreate them to repair documents.

Before campaign create, persist its exact request and stable `Idempotency-Key`
(1–128 nonblank characters) in [execution records](../runtime/artifacts.md).
Send the saved key on every retry. Create PAUSED via `/ads/reddit/campaigns`;
save its ID before creating selected missing groups, posts and ads.
Retain each child's request/key/ID too, but child keys have only a short-lived
success cache, not durable recovery.

Read campaign/groups/posts/ads by ID. Verify parent links, budget units,
targeting, destination and paused state against the authorized inputs. Save partial state
immediately on failure, keeping it paused. No minimum creative count applies.

## Recovery

Same-key/same-payload campaign replay resumes saved registration/accounting.
For `operation_in_progress`, wait before the same request.
For `reddit_campaign_create_not_sent` or explicit provider 429, retry with
backoff and any `retry_after`.
For `reddit_campaign_create_outcome_unknown`,
`reddit_campaign_create_readback_invalid` or
`idempotency_key_payload_conflict`, preserve the record and request Egbe
reconciliation. Never bypass uncertainty with a fresh key/replacement.

For ambiguous child writes, inspect saved IDs and provider readback first.
Empty owned lists do not prove no create occurred; unresolved identity needs
reconciliation. Never probe real creates for schema discovery.

Targeting repair uses the known group's update route with complete intended
writable settings. Budget changes are not supported there; do not silently
replace the group. Build remains separate from activation.
