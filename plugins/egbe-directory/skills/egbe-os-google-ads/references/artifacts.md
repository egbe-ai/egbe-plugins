# Campaign records and recovery

Keep the requested configuration, authorization context and evidence needed to
continue safely. Ordinary reads need no new files; a requested pause must not
wait for a reconstructed launch history.

## Locations and responsibilities

```text
egbe-docs/marketing/campaigns/google/<campaign-slug>/
  campaign.json
  results.md
  evidence/
```

Create these on demand, not as an empty bundle. Reference existing input records
rather than copying them or requiring a new planning document.

- campaign.json: object bindings, last significant confirmed provider state and
  at most one unfinished agent-side campaign operation.
- results.md: observed build/launch result and later measurements, dates,
  source/freshness, limitations and actual stop reason when known. No empty
  report in advance.
- evidence/: useful request/readback snapshots or metric exports.
  Small evidence may live in the main files; no journal of every GET.

Use one stable channel-qualified campaign slug for the folder and utm_campaign.
Do not invent experiment IDs or repurpose the slug as one. Campaign name/ref and
provider IDs are different identifiers; preserve the exact returned ref.

Existing project records remain evidence. Resolve an existing campaign by its
exact provider ref/ID, not a guessed name; ambiguous matches need clarification.
Do not rewrite or delete historical files merely to satisfy this layout.

## Minimal campaign.json

Example after an observed paused build; values are illustrative:

```json
{
  "channel": "google",
  "campaign_slug": "google-search-001",
  "product_slug": "product-slug",
  "plan_path": "egbe-docs/marketing/campaigns/google/google-search-001/plan.md",
  "account": {"customer_id": "1234567890", "currency": "USD", "time_zone": "Europe/London"},
  "campaign_ref": "1234567890:456",
  "objects": {
    "ad_groups": [{"id": "789", "keyword_ids": ["111"], "ad_ids": ["222"]}]
  },
  "confirmed": {
    "observed_at": "2026-10-27T12:00:00Z",
    "source": "GET /ads/google/campaigns/1234567890:456/readback?expect=PAUSED",
    "readback": {"campaign": {"id": "456", "customer_id": "1234567890", "status": "PAUSED"}}
  },
  "pending_operation": null
}
```

The required identity for a campaign record is channel and campaign_slug. Before
creation, campaign_ref and confirmed are null and objects may be empty. Populate
account from actual OS diagnostics; unknown currency/timezone stays unknown.
Once available, preserve the exact campaign_ref and ensure its customer/campaign
components agree with the recorded account and provider readback. A local record
does not establish server ownership.

Keep IDs needed for the task with their parent group, not an unscoped inventory.
Use negative_keyword_ids for relevant negative criteria, and conversion_refs or
restore_keys when conversion work creates values needed for continuation.
product_slug and plan_path are optional when not applicable or not known.
If supplied by the project, preserve immutable durable business_id, product_id,
launch_id, experiment_id and variant_id in an optional identity object. Do not
derive them from names or store caller orchestration identifiers here.

confirmed contains observed_at, the exact read source, and either the relevant
readback object or a project-relative readback_path. Preserve actual statuses,
delivery/drift, destinations, settings or amounts needed to verify that operation;
do not manufacture a universal projection or copy the entire desired plan.
The example is a campaign-only excerpt, not sufficient evidence of every
child's state. Use full or targeted evidence as needed for the actual change.
Never write planned state as confirmed or substitute a deadline for the actual
successful pause/readback time. Missing facts are unknown, not assumed defaults.

## Authorization context

Keep enough content to identify the authorized operation and exact materials,
source/time and boundaries alongside existing campaign notes. A source link to
an inaccessible chat alone is insufficient for a later agent to resume a write.

A snapshot/hash can bind exact inputs; it does not prove human approval.
Do not hash an entire mutable Markdown document as the only binding:
adding commentary does not change an approved ad. Changed substantive inputs
must remain distinguishable from earlier decisions.

## Recover one unfinished campaign operation

Agent-side changes to one campaign are sequential in this workflow. Before a
risky write, durably save pending_operation with:

- method and exact OS path/target;
- payload, or payload_path pointing to an immutable project-relative snapshot;
- idempotency_key only where the endpoint supports it;
- prepared_at with timezone;
- decision_ref to the relevant plan/notes and enough context to identify the
  requested action, not only an inaccessible chat URL.

A hash without the actual request is insufficient for recovery. Preparing this
record is not proof the request was sent or executed. Do not overwrite it with
a new operation while the previous result remains uncertain.

After a response or recovery read, save confirmed IDs and provider readback
before clearing pending_operation. Preserve a needed operation key/restore key
after completion. If the result is unknown, keep the exact request/key and
diagnostic, inspect current provider state and follow that endpoint's own rules.
Some creates require Egbe reconciliation rather than a retry. Temporary caches
do not make a multi-step build atomic; do not replay uncertain batches blindly
or change keys to bypass them.

These records are campaign-management context in the product repository; follow
its ordinary synchronization workflow without requiring a commit after every
operation. Never include keys, tokens, cookies, private user data or credentials.
Do not copy raw responses wholesale without checking their content.

Per-user GCLIDs, product events, delivery intents and retry receipts belong to
the deployed product's existing durable runtime storage, not this repository
or campaign.json. See [Server conversions](server-conversions.md).

This layout is not automatically ingested into GTM Knowledge. Do not claim
central collection of these records.
