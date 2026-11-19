# Pause Meta delivery

An exact owned campaign ID is enough to start. Read selected child IDs through
OS if needed; missing local campaign records do not block an authorized pause.

Pause through `POST /ads/meta/campaigns/{campaign_id}/pause`; when the task
includes the whole tree, also pause selected ads/ad sets through status routes.
Do not archive/delete as a substitute.

Read `/ads/meta/campaigns/{id}/state?expect=PAUSED` and preserve statuses/drift.
A parent pause can stop serving while children remain configured ACTIVE: report
what actually changed, not that every child paused. Failed readback leaves
confirmation pending.

Save actual confirmation time, IDs, receipts and known stop reason beside the
campaign. Do not substitute the planned deadline for factual time or infer a
past stop's cause. Missing analytics must not block stopping spend.
