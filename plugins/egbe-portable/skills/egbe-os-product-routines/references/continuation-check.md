# Check continuation across runs

Use when assembling or debugging a recurring task. This checks the tools and
saved continuation, not the user's scheduler, uptime or notification transport.
It is not a required extra test before every routine run.

Use the task's existing purpose, action scope, method and plan. Keep evidence in
its existing work records. Read or prepare a bounded safe example; do not trigger
real purchases, send messages or mutate the business merely to test repetition.
Any synthetic inputs belong in an isolated check, not production metrics.

## Exercise the handoff

- Run the bounded work manually and retain the source record IDs, observation
  window or revision, actual action/result references, unfinished work and next
  checkpoint needed to resume. Reuse existing records rather than adding a
  parallel state schema.
- Start a continuation from those files. Confirm it can recover what completed,
  what remains pending and where the result can be checked. Chat history alone
  must not be necessary to reconstruct a completed action.
- Present the same source record again. Confirm completed effects are recognized
  rather than repeated. If an earlier write has an unknown outcome, check its
  external status before retrying; missing local confirmation is not failure.
- Present a later observation, with its source and time or revision. Confirm it
  is distinguishable from the earlier one and the updated work/result is saved
  for the next continuation. The caller's method owns its business interpretation.
- With no new observation, confirm the continuation retains pending work and
  checkpoint without fabricating new evidence or repeating completed effects.

Record what the check actually established and any unavailable operation.
Successful reads, resumed actions and saved outputs do not establish that a
native schedule will fire or that its notification was delivered. Nor does a
synthetic test establish an improvement in customer or business outcomes.
