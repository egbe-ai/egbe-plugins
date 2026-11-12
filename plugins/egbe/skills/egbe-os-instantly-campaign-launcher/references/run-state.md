# Executable run configuration and durable state

The canonical directory is
`egbe-docs/marketing/campaigns/instantly/<run_key>/`.
Use the existing plan/materials; for a new campaign, `plan.md` can hold its
chosen scope, decision and result. The tool does not require separate preflight,
log, lessons or daily-memory copies, or a particular language.

The plan records the run's accepted requirements; `run-spec.json` supplies
supported executable settings. A requirement written in the plan is not thereby
implemented by the spec. Use the existing operation records below as evidence
of settings and execution, not a second copy of the business decisions.

## Inputs and identity

Start with [run-spec-template.json](run-spec-template.json) when useful.
It is a non-executable scaffold: replace placeholders/null required choices
before running. It contains no invented sender, proof, customer result or
experiment identity.

`run-spec.json` needs `run_key`, nonempty `sequence.steps`, `leads_file`,
an explicit positive `campaign.daily_limit`, schedule and owned sender selection.
`product`, `segment`, `offer`, reply policy and other context are available
to the operator; they are not a requirement to repeat research. Campaign name
may be explicit; otherwise the launcher derives one from the available context.
Set `activate_on_launch: true` only for the intended activation operation.
Otherwise the run is prepared without activation.

`campaign.daily_max_new_leads` optionally limits new leads contacted per day;
`campaign.daily_limit` caps all messages for this campaign, including follow-ups,
across its senders. Neither enforces a project-wide aggregate across campaigns.
For supported protection fields and their semantics, read
[configured protection](observation-and-scheduling.md#configured-operational-protection).

Use a stable key for this particular run, not a permanent key for every future
test of the same audience/offer. Preserve available `business_id`,
`product_id`, `launch_id`, `experiment_id`, and `variant_id` from existing
project context; leave unknown IDs absent, do not invent them to satisfy a
report. After the manifest exists, run/GTM identity conflicts fail before
provider writes. A new test uses a new run rather than rewriting history.
The first actual launch time is preserved as `first_launched_at`; preparation
reruns update `last_prepared_at`, and explicit activation updates
`last_activated_at`. A new preparation timestamp is not a fresh cohort start.

Attribution is `provider=instantly`, `utm_source=instantly`,
`utm_medium=email`, `utm_campaign=<run_key>`, plus
`provider_campaign_id`. The operational run/UTM key is not a substitute for
a portable experiment ID. Both are preserved when known.

`leads_file` is a JSON array or `{"leads":[...]}`; source metadata may accompany
it. Leads require email and the values actually used in the sequence. Names,
company, website and optional scalar custom variables are mapped by the client.
Keep the file in the run and reference `./leads.json`: relative paths resolve
from the spec directory (CWD fallback exists with a warning). Known opt-outs
are filtered independently of source status or cosmetic name review.

## Replenishment is explicit and bounded

```bash
node "$SKILL_DIR/scripts/replenish-leads.js" --run-dir "$RUN_DIR" --env-file "$RUN_DIR/.env"
```

Absent configuration or `enabled` other than true does not request sourcing.
Enabled replenishment requires all these authored values:

| Field | Required value |
| --- | --- |
| `batch_size` | positive integer |
| `max_total_leads` | positive integer hard campaign membership cap |
| `max_replenishments` | nonnegative integer additional-cycle cap |
| `utilization_threshold` | fraction 0–1 |
| `cooldown_minutes` | nonnegative number |
| `apollo_search` | optional compatible Apollo search object when that source is selected |

There are no default fifty-lead batches, 250-lead tests, 48-hour cooldowns or
80-percent utilization requirements. Initial import is capped by the configured
batch/total only when replenishment is enabled; surplus remains in carry-over.
Without it, the selected initial input is not silently reduced to a marketing
batch size.

The replenisher drains carry-over before sourcing, checks complete live
membership/utilization, deduplicates, filters confirmed opt-outs, validates
used variables, imports with verification, and records the result. It
rechecks membership before import so stale local counts cannot exceed the cap.
`--force` bypasses utilization only: it does not override cooldown, total/cycle
caps, disabled sourcing or unknown membership.

Rejected leads retain full data and reasons in `state/rejected-leads.json`.
Correct an actual missing/invalid substitution and deliberately return the lead to
carry-over; do not pay to source it again. Unusual but real names cause warnings.
Exact title/credential tokens remain invalid names unless explicitly confirmed.
A rejection/empty result is not permission to widen the audience or spending.

Apollo runs with a 90-second client budget inside a 120-second subprocess
timeout. Its atomic output is read even after incomplete exit or interruption.
Results/history retain `source_meta` and `source_file`; full pending inputs
remain in `state/replenish-temp/leads-*.json`. Despite the directory name,
these source checkpoints are durable and are not automatically deleted.

Before another paid Apollo search, the replenisher blocks on a prior
incomplete/unknown source checkpoint. Carry-over may still be used. Review
that source explicitly and use Apollo `enrich --input <source_file>` to resume
only pending inputs if appropriate; a lost response may already have incurred
cost. Preserve/reconcile usable leads into carry-over as needed. A completed
source no longer blocks new search. No blind new search or enrichment replay is
performed merely because the previous sourcing subprocess failed.
New partial sourcing exits 2 even if usable retained leads were imported;
an earlier unresolved checkpoint blocks another paid search with exit 1.
Ordinary configured skips (disabled, cooldown, caps) return exit 0 and a reason.

## Active artifacts and consumers

Files appear as operations create them; this is not a checklist to pre-create.

| Artifact | Writer / reader and purpose |
| --- | --- |
| `run-spec.json`, `leads.json` | Authored inputs / launcher and replenisher |
| `state/resolved-run-spec.json` | Launcher-derived senders/identity / reply worker; original spec is not rewritten |
| `manifest.json`, `state/ownership.json` | Launcher / every worker; IDs, fingerprints, tags and run scope |
| `state/sequence-state.json` | Launcher / rerun; applied rendered-sequence fingerprint |
| `state/imported-leads.json`, `state/carry-over-leads.json` | Importers / safe dedup and remaining inputs |
| `state/verification-state.json`, `state/invalid-leads.json`, `state/deleted-leads.json` | Launcher / verification, targeted cleanup and rerun |
| `state/rejected-leads.json`, `state/replenishment-history.json` | Replenisher / fixes, bounds and actual import evidence |
| `state/processed-replies.json`, `reply-queue.json` | Collector/sender / checkpoints, locks and pending/uncertain actions |
| `monitor-summary.json`, `state/analytics-history.json`, `state/monitor-alerts.json` | Monitor / observations and alert/acknowledgment recovery |
| `launch-summary.json`, `cron-install.json`, manifest scheduler fields | Launch/installer / readback, execution handoff and verified removal |
| `conclusion.json` | Facts-only collector / existing GTM consumer; no automatic verdict or lifecycle completion |
| `../outreach.db` | Operational scripts / run, lead, queue and event history across project runs, including confirmed opt-outs |
| `../tag-cache.json` | Launcher / tag reuse, not proof of tenant access |
| `.env` | Private credentials and connection identity / launcher and workers |

JSON queue/checkpoints and SQLite both have active readers/writers. Neither is
a disposable legacy mirror. `outreach-report.js` reads the DB, while queue/send
recovery still depends on the files.

Version specs, contacts, messages, queue/history and the SQLite DB in the
access-controlled project repository, never a public site. Credentials, process
locks and temporary SQLite journals stay Git-ignored. SQLite uses rollback
journaling; committed state is in the DB, not a separate WAL archive.

For handoff, stop/pause the local workers and synchronize the DB and files as one
coherent snapshot. Do not merge competing binary DB copies or start a second
sender from a clone. Reconcile provider state, identity, pending imports and
`sending` queue items before transferring execution. Missing DB after known
sending is a recovery task, not permission to initialize empty history.
