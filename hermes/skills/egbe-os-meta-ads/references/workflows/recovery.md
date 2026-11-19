# Meta uncertain-write recovery

Preserve exact request/spec, original plan token, IDs, timestamps, error and
last readback. An uncertain write is not a failed write.

After timeout or `409 apply_rolled_back`, do not re-plan first: OS derives
apply idempotency from the token and a new token can build a duplicate.
Inspect owned campaigns and exact returned IDs through state/raw reads.
Rollback attempts deletion, but failed deletes are ignored. An empty owned
list does not prove no unregistered provider object exists.

Reuse an unambiguously confirmed complete paused tree. Keep partial objects
paused while reconciling. Remove proven leftovers only when cleanup is authorized,
via per-level status routes; preserve evidence. Unclear identity/ownership needs
Egbe team reconciliation, not guessing from names or another create.

Once reconciliation confirms no surviving tree, retry the same payload/token if
usable; if expired, re-plan only after that confirmation. Repair local validation
failures locally, never with another campaign.

Resolve real locale/interest IDs for targeting errors; do not remove language
restrictions to bypass blockers. Missing binding, permissions or regulated-market
fields are explicit configuration/validation blockers.
