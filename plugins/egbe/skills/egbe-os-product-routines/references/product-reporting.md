# Business Loop and reporting schedules

Configure the agreed responsibility through the harness's persistent scheduler.
The project method `egbe-docs/playbooks/product/business-loop.md` owns the loop's
decisions and continuation; this reference owns registration, ownership and
delivery. It does not introduce a daemon or require a hosted Egbe agent.

## Agree and reconcile

Resolve the verified business, workspace, timezone and supported destination.
Read saved choices and inspect actual jobs, including jobs owned by another
harness or machine. Connecting Egbe does not authorize scheduling. Create a
Business Loop only after explicit agreement; preserve a prior decline or
disable unless the founder explicitly reverses it. A manual report or broad
request to configure reports is not consent to this new recurring responsibility.

Use the cadence or next checkpoint selected with the project's method and
founder, in the known project/user timezone; disclose the harness timezone if
unknown. Daily is an option, not a fixed interval. Agree the supported schedule,
destination and any quiet hours. Default new schedules to material updates unless
the founder wants an unchanged-state digest. Reuse saved choices. Execution timing
and notification frequency are separate; the founder can change either or stop.

Existing schedules keep their owner, cadence, digest choice and disables until
the founder agrees a migration. When replacing the standalone daily review:

- Prefer updating its existing native job. Agree whether its shorter updates
  remain; do not silently remove them or add a second daily review.
- If replacement requires another job/owner, prepare it inactive, then verify the
  old daily responsibility is disabled before activating the replacement. Preserve
  any agreed brief updates, including when they shared the old combined job.
- If ownership, cancellation or activation cannot be verified, record migration
  as pending and explain what remains active or uncertain. Do not create a second
  active job to work around inaccessible ownership.

Missing local settings do not establish that no job exists. Match business ID as
well as workspace. Git history alone cannot coordinate active jobs on two machines.

## Register and verify

Prefer one dedicated persistent Business Loop chat when the harness supports
scheduled continuation in it. Reuse that chat on later runs and reconnects;
keep it separate from the founder's main development or discussion chat.
If unsupported, use isolated native runs and explain whether they create a new
chat each time. A quiet notification setting does not prevent chat creation.
In either mode, project records remain the durable continuation source; the
chat's history is not a substitute for current plans, methods and results.

Give the job the workspace, non-secret business identity, cadence, delivery
destination and agreed action scope. For a Business Loop, include readable paths to the project's
`EGBE.md`, current `egbe-docs/playbooks/product/business-loop.md`, relevant concrete
plans/results and `egbe-os-product-report`. The runner must read the actual
project methods and adaptations, not a stale copy pasted into its task prompt.
Keep credentials in the project's credential store, never in that prompt.
An explicitly requested report-only schedule instead invokes `egbe-os-product-report`
with its period, mode and read-only scope; do not turn that request into a Business Loop.

Verify registration, the target chat/destination, expiration, the device/runner
that must remain available and access to project records. Where supported, perform
one read-only check of access and output without advancing a scheduled slot.
Registration, successful execution and confirmed delivery are separate facts.

If persistent scheduling, isolation or delivery is unavailable or needs native
permission, leave the relevant part pending and offer manual execution. Do not
promise that a sleeping device or session-bound task keeps running, or substitute
an external scheduler without agreement. Installing a skill is not registration.

## Shared settings and ownership

Reuse versioned `egbe-docs/routines.json`; preserve unrelated entries. Keep the
existing `product_reporting` record keyed by verified business ID, with:

- `enabled`: the saved preference; never confuse it with verified native state.
- `workflow`: `business_loop` after an agreed migration or new loop setup.
  An existing entry without this field retains its reporting behavior.
- `timezone`, the agreed `schedule` (native recurrence or next checkpoint), and
  any quiet hours/digest preference. Distinguish loop checkpoints from additional
  brief updates or operational checks; a shorter check does not advance the loop.
  Existing `daily_at`/`interval_hours` retain their daily-review/brief meaning
  until an agreed change; do not reinterpret a combined job's short interval as
  the frequency of full Business Loops.
- `scheduler`: harness/owner, actual job ID, workspace and delivery destination,
  including the persistent chat ID when supported, with pending or unverified
  state recorded explicitly. Retain old/new job
  references while a migration remains unresolved.
- `last_completed`: responsibility, scheduled occurrence and result/artifact
  path; `last_delivered`: occurrence, artifact path and confirmed notification
  reference when available. Identify a loop occurrence by its scheduled due
  time/checkpoint, not just the calendar day.
  On completion, retain whether notification is pending or not required by the
  agreed digest preference. Not required is a resolved outcome, not delivery.
  Each also retains its latest loop occurrence and result when a brief advances
  the slot. A brief cannot overwrite the loop's completion or delivery state.
  Keep unresolved notification references in the existing records across newer
  loop occurrences, until delivered or included in a confirmed delivered current
  update. Do not rerun completed work to reconstruct an older notification.
  Preserve existing detailed-report covered-date markers until migration.

Keep business goals, approvals, owners of work and decisions in their existing
plans/results, not another copy in this configuration. This record describes the
native job; it neither creates the job nor proves that it is active in this clone.

## Run and deliver

Read saved settings and reconcile the last execution before starting. Determine
which responsibility and occurrence are due from the agreed schedule. Return
quietly when disabled, not due, or when that occurrence is complete and its
notification is delivered or not required. Use
the scheduler's supported non-overlap mechanism; do not execute a second run of
the same responsibility while its predecessor is active or uncertain.

For a due `business_loop` checkpoint, run the project's current method from
saved work state, using domain capabilities only within existing
authorization. Pass its observations, decisions, work status and evidence to
`egbe-os-product-report`; do not start a separate audit to fill the report. Use
detailed output with depth proportional to the actual content. At retained
brief slots, report only the status of this same work. Separate operational
checks keep their agreed scope and feed the current plan; they do not independently
start another Business Loop or choose a new business priority.

Apply the agreed digest preference to brief and loop output alike. With
material-updates-only, retain completed work quietly when there is no meaningful
change or founder decision; tell the reporting skill to prepare without sending
and record notification as not required. Do not retry that output as undelivered.
Check completion separately from notification delivery. For a completed loop
with a required pending notification, retry its saved output, not the loop.
Keep its occurrence marker when a later brief completes or is delivered; the
next short check must not repeat completed loop work.

Unmigrated reporting jobs retain their saved brief/detailed behavior and scope:
the first eligible slot at or after `daily_at` without a completed review of the
previous local day is detailed, replacing that slot's brief; other briefs cover
today so far. A completed daily review awaiting delivery is reused. Do not change
an existing digest to alerts-only.
For either workflow, after downtime produce one useful current run, not a burst
of missed reports. Report actual measurement windows rather than claiming skipped
checks were performed.

Save completion after outputs and continuation records are checked. Confirm
delivery at the founder-facing destination separately; a successful job or local
HTML file does not establish notification delivery. If confirmation arrives after
the turn, reconcile it on the next run. Reuse completed work for a delivery retry;
do not rerun business actions or collection merely because the message failed.
Reconcile uncertain writes before retrying. For an interrupted run, continue
still-useful missing work and preserve its unfinished state; do not mark it done.

## Change or stop

When the current plan selects a different next checkpoint or ends an observation,
apply the agreed change to its existing native job rather than adding another.
Use native rescheduling or supported event triggers when appropriate and
available; do not emulate them with frequent empty agent runs. Retain necessary
safety checks and requested digests. If the harness cannot represent the intended
timing or reuse the chat, explain the limitation and agree a supported alternative.

Update the existing native job and saved settings for an agreed schedule change,
then verify them. To stop, save `enabled: false`, disable the actual job and confirm
its state. If the owner cannot be reached, report the unconfirmed stop rather than
claiming success. Keep the disabled preference through future quickstarts and
leave prior results intact. Finish with the actual configured/pending state and
how the founder can change or stop it.
