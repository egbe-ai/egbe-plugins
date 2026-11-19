# Observation, protection and scheduling

## Collect facts for one run

```bash
node "$SKILL_DIR/scripts/monitor-campaign.js" --run-dir "$RUN_DIR" --env-file "$RUN_DIR/.env"
node "$SKILL_DIR/scripts/conclude-campaign.js" --run-dir "$RUN_DIR"
node "$SKILL_DIR/scripts/outreach-report.js" --run-dir "$RUN_DIR" --run-key RUN_KEY --mode summary
```

Monitor reads only the manifest campaign, writes `monitor-summary.json` and
appends cumulative snapshots to `state/analytics-history.json`. It preserves
source/quality and `metrics_observed_at` separately from packaging
`generated_at`. Do not sum cumulative snapshots or call a newly packaged old
snapshot fresh evidence.

For mailbox state and warmup, use the [assigned sender read](instantly-ops.md#read-assigned-sender-state).
It is available to regular and read-only project keys; it does not install a
warmup-based pause control in the bundled monitor.

`outreach-report` reads project SQLite and returns a JSON array of rows.
Modes are `summary`, `leads`, `queue` and `events`, with optional `--limit`,
`--run-key` and `--db`. `--run-dir` selects the project DB; add `--run-key`
when you need a particular run, because the DB contains multiple runs.
The summary attributes confirmed refusals to the run where they were received,
without counting repeated confirmations twice. The leads view separately exposes
project-wide `opt_out_confirmed`; this is not proof that provider sending stopped.

Current derived reply/bounce/unsubscribe/spam/open rates use a campaign-scoped
unique `contacted_count` as denominator, expressed in percent. Keep raw numerators
and that definition with any comparison. Positive reply count is a provider
classification, not proof of qualified demand. Step-reply values are counts,
not automatically rates; the last step is not assumed to be a breakup.

Analytics and campaign-filtered overview fill missing fields independently;
missing complaint data does not erase readable zero bounces. Field sources are
recorded in `_field_sources` and retained in conclusion quality details. A
complete observation can still have missing metrics; each rate needs its own
readable numerator and a trustworthy denominator.

Instantly's raw `contacted_count` can exceed campaign membership or conflict
with sending activity. The monitor retains that raw value for diagnosis and
recovers unique contacts only from a complete, identity-consistent lead read
with known contact activity that agrees with cumulative
`new_leads_contacted_count`. Present membership alone does not establish the
historical population: a mismatch, partial read or unknown activity leaves the
denominator unavailable. This does not prove workspace-wide data leakage.

Unknown metrics stay unknown. An email-list fallback is a bounded partial
sample and cannot supply complete bounce/spam/open signals or trustworthy
rate denominators. It is used when analytics is unavailable, or when actual
messages contradict the established all-zero/degraded analytics signature;
sampled replies are never merged into otherwise complete campaign totals.
A scoped zero recipients/zero events observation means no data yet, not an API
outage. Tracking disabled means no measured opens, not a measured zero.

The collector `conclude-campaign.js` packages the latest snapshot as
`conclusion.json` for the existing GTM consumer. The filename is retained,
but collection does not finish a campaign or wait for a prescribed sequence age.
It preserves identity/attribution, observation time/window, counters,
denominators, partial/unknown/scope limitations and missing fields. It does not
compute a verdict, fabricate lessons, change DB lifecycle to concluded, or infer
cohort maturity from the launch date. `--force` does not refresh stale data or
improve quality. Put the actual interpretation and accepted action in the
existing plan/result, not a second assessment JSON.

For product-side outcomes, use the OS analytics capability when available and
the run's `utm_source=instantly`, `utm_medium=email`,
`utm_campaign=<run_key>`. Read canonical product event names from
`/analytics/events`; do not invent run-specific conversion names or claim this
collector automatically retrieves product events. A reply counter and a product
action are different observations.

## Configured operational protection

Protection is separate from business evaluation. `monitoring.autopause_on_risk`
defaults true. Activation requires a valid explicit
`monitoring.thresholds.max_bounce_rate` (percentage 0–100).
`max_spam_complaint_rate` is optional and should be configured only when its
signal is available. The bundled monitor compares cumulative campaign bounce/spam
counts to unique `contacted_count`, as percentages, using strictly `>` with no
minimum sample. Use the run's accepted thresholds; the code supplies no universal
marketing threshold.

The bundled monitor has no configurable sent-message denominator, calendar-day
bounce-count gate, assigned-sender warmup status/score gate or timed missing-signal
grace period. Sender selection checks account activity, not ongoing warmup health.
Available reads or extra `run-spec.json` keys do not implement those controls.
Identify unsupported required conditions explicitly; do not represent a different
supported check as equivalent.

`monitor-summary.json.protection.active` means the supported threshold configuration
validates, not that autopause is enabled, every requested condition is enforced,
or scheduled observation is running. Keep these distinctions when reporting readiness.

With protection enabled, a configured threshold exceeded or a required signal
unavailable after bounded read attempts/fallbacks triggers scoped protective
pause. Missing configuration is not a healthy monitor result; it blocks
automatic activation and surfaces as a configuration risk on an existing run.
Explicitly disabling autopause is a run choice, not an accidental consequence
of an omitted field.

Open rate never triggers pause. The supported Instantly campaign analytics
routes currently expose no complaint/spam counter. An unconfigured complaint
threshold is listed as not monitored. If the run explicitly requires it and
the signal is absent, `spam_unavailable` still triggers protection; changing
that requirement needs the run's authorized decision. Refreshing this skill
does not change thresholds or resume a paused campaign. Partial/unknown required
signals cannot clear an earlier risk. No-recipient/zero-count observations skip
rate evaluation without declaring an outage.

Pause success requires readback. `pause_action` is an attempt;
`pause_failed` or unconfirmed readback requires attention. Already-paused,
draft and completed campaigns are not repeatedly paused. Alert state in
`state/monitor-alerts.json` distinguishes new/repeated incidents. A confirmed
operator resume acknowledges a prior numeric gate, not unknown data; material
worsening/new complaints/new gates can alert and pause again. Do not remove
the checkpoint just to suppress an alert.

Throughput compares comparable full snapshots against the run's explicit daily
cap. `monitoring.min_daily_capacity_pct` is optional; absent configuration or
incomplete metrics means no automatic throughput judgment. The monitor does
not auto-pause merely for slow sending or automatically increase spending,
mailboxes or recipients. Treat diagnostic hints as checks, not proven causes.

## Optional scheduler installation

Use scheduled workers only for the agreed operating arrangement. Manual
observation remains possible; record who handles observation and replies.
Installing a scheduler is not part of every operation, and four jobs are not
universally required.

```bash
node "$SKILL_DIR/scripts/install-crons.js" --check-scheduler --scheduler openclaw
node "$SKILL_DIR/scripts/install-crons.js" --run-dir "$RUN_DIR" --scheduler openclaw \
  --deliver-channel slack --deliver-to channel:CHANNEL_ID
node "$SKILL_DIR/scripts/install-crons.js" --run-dir "$RUN_DIR" --scheduler cron
node "$SKILL_DIR/scripts/install-crons.js" --run-dir "$RUN_DIR" --scheduler cron --remove
```

These commands create/remove recurring external work when actually run; choose
them explicitly. `--dry-run` previews installer output, not live sourcing or
campaign execution. Credentials are read from the private run snapshot, never
embedded in scheduler entries; explicit `--env-file` supplies them without
modifying that source file. The installer enforces run `.env` permissions.

- `openclaw` (default) runs agent turns. It needs a deliver-channel/to pair
  (CLI or `notifications` config), or explicit `--no-chat-delivery`; isolated
  jobs have no implicit last chat. It selects the agent owning the run workspace,
  else the host default; `--agent` selects explicitly. Review recorded agent
  identity before reinstall/moving a run.
  Reply turns read the current project email method and plan before content
  decisions; technical references govern queue/send execution.
- `cron` runs Node directly on an always-on host, in the host timezone.
  Reply collection is not reasoning or automatic reply handling. Identify the
  person/agent that reads the queue; a sleeping laptop is not an always-on host.
- The Unix scheduler check executes a temporary harmless probe and removes it.
  Default wait is 75 seconds; the accepted override
  `--scheduler-check-timeout-seconds` is 65–120. A writable crontab alone is
  insufficient evidence of execution.

The current installer includes reply and monitor jobs. OpenClaw uses the sending
window plus one hour before/two hours after, on campaign days/timezone:
reply hourly at :05, monitor at :15. If no usable schedule exists it records the
24/7 UTC fallback. Direct Unix cron uses hourly host-time cadence.

Replenishment is installed only for `lead_replenishment.enabled: true`, every
two hours at :45; the operation itself enforces the configured cooldown/bounds.
A factual-export job is added only when `monitoring.snapshot_schedule` is
provided. Its cadence is explicit, not a claim that a test is ready for a verdict.

Registration is scoped by `instantly-<run_key>-<job>` and exact run directory.
OpenClaw reuses/edits existing job IDs and removes jobs omitted from the new
configuration, verifying their exact run directory and removal. Unix cron replaces
only this run's marked block and preserves unrelated entries. The installer rereads registration and
records verified IDs/settings in `cron-install.json` and manifest `cron_jobs`.
Registration readback is not evidence that every later tick or reply succeeded.

Installation failure returns nonzero, with `installed: false` and manual
commands/cadences when supported. Do not announce automation as working then.
Before switching schedulers, remove through the recorded scheduler and verify
removal. The receipt supports removal even if the manifest is damaged; keep it
until removal is confirmed. `launchd` is not supported.

Direct cron ticks use per-job locks and bounded execution; inspect
`cron-<job>.log`. Stale locks fail closed. Verify no tick/installer is alive
before removing only the identified stale lock and retrying. Keep one executor
and the same absolute bundle/run/Node paths on the scheduler host.
