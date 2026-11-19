# Activate or resume Reddit objects

Resolve selected IDs and current authorization; refresh
[read-only checks](launch-ready.md). Activation creates/replaces nothing.

For a new attempt preserve `activation.started_at` and a fresh
`accepted_mutations` list; follow-ups continue that attempt.
Activate the campaign if needed via `/ads/reddit/campaigns/{id}/launch`, then
selected groups/ads via their raw `/status` routes using
`{"status":"ACTIVE"}` without a `data` wrapper. Campaign launch does not
cascade. Skip already ACTIVE objects; never activate unselected siblings.

Persist receipts immediately (campaign: `data.raw`; children: `data`).
HTTP success with `activation_confirmed:false` is not confirmation.
Read each object and retain configured/effective/delivery status, rejection
reason and timestamps. ACTIVE is not moderation approval or actual traffic.

Report new successful activation only after current-attempt acceptance evidence
and ACTIVE readback of every selected object. If everything was already ACTIVE
and no write was made, say "already configured active"; invent no restart time.

## Pending confirmation

After acceptance, do not repeat the write because readback lags. Save
`status: activation_pending`, receipts and reads, without a new successful
launch/restart timestamp. A timeout without acceptance is uncertain: read first.

Arrange follow-up only through an available mechanism when covered by the task.
Preserve attempt identity and agreed boundaries, honor Retry-After and bounded
retries, and do not busy-poll moderation. If no scheduler was installed, say so.
Waiting does not extend authorization, budget or time. A status-only read can
establish current configuration but not when a past activation happened.
