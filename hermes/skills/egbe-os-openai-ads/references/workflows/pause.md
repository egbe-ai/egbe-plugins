# Pause delivery

For an authorized stop, resolve the exact campaign and call its pause endpoint
with a persisted idempotency key. Do not delay an urgent safety stop for missing
historical docs or validator errors. Do not archive/delete children or tracking
resources merely to pause delivery.

Independently read campaign status. Only then record factual `paused_at`; a planned
stop time or accepted request is not proof of pause. On error/timeout, preserve the
unconfirmed operation, report current exposure and follow the saved-key recovery
procedure. Child flags can remain active under a paused campaign; do not claim they
were individually paused if only the parent was stopped.

Update state/readback and change-log; run `--phase pause`. Pausing delivery does
not cancel external jobs, remove reporting access or make delayed results final.

Record the requested trigger/authority in the existing change-log, then append
the affected ID, actual confirmation time and readback after success. Preserve
the known cause for this run; later balance or deadline changes do not replace it.
If the provider exposes no cause, record it as unknown. A later relaunch does not
reuse the earlier stop timestamp. Return the confirmed stop state or the unresolved
operation; a failed pause or stopped monitoring alone is not a confirmed stop.
