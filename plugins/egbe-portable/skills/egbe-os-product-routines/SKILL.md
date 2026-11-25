---
name: egbe-os-product-routines
description: Handle “Run Egbe Loop” commands from the Dashboard, offer a fitting Business Loop after a project milestone, and configure recurring Business Loops, reports, product-health checks and campaign oversight.
metadata:
  egbe-when: "Use when the founder names or opens a Dashboard loop to discuss, try, start or resume it, after verified work reaches a milestone a loop could carry forward (a live product, working payments or analytics, a built campaign, delivered research, first signups or sales), or for recurring work. A bare preset ID selects the shared method; mine/<id> selects the business method."
  egbe-visible: "true"
  egbe-title: "Keep your product moving"
  egbe-description: "Keep agreed work moving with a recurring Business Loop, product checks and reports in your agent."
  egbe-category: "Business operations"
---

<!-- egbe-mcp-connection:v1 -->
This skill comes with the Egbe plugin. If this project has its own installed copy
of the skill, use that copy instead. Otherwise make every Egbe API call it
describes with the Egbe connector: `egbe_read` for GET and `egbe_write` for POST,
PUT, PATCH and DELETE (with `method`). Pass the API path (for example
`/me/limits`), query parameters in `query` and the JSON body in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Where this skill sends an `Idempotency-Key` header, pass the same value as
`idempotency_key` and reuse it when retrying. A result with a `continuation`
holds one part of a long body; read the next part with `egbe_read`, the same
`path` and `business`, and that `continuation`.
Read bundled files beside this `SKILL.md`. For published skill resources on
Egbe OS, use `egbe_skill`. Follow "Files downloaded on demand" for listed downloads.

Publishing works through the connector: commit the app's files with the JSON
commit requests in `egbe-os-git` ("Without a terminal") and deploy the returned
commit SHA; no git push or workspace setup is needed. A step that needs a local
project key or a bundled script, such as a local `npx convex deploy`, needs a
set-up project workspace. In a persistent
project workspace that is not set up yet, set it up as the `egbe-setup` skill's
project setup describes.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.

If the connector's tools (`egbe_read` and the other `egbe_*` tools) are not
available, the plugin's connector is not signed in for this agent. Tell
the founder how to connect it, as the `egbe-setup` skill describes, rather than
saying Egbe is unavailable.

The connector's tools work even where this environment's shell cannot reach
Egbe: their calls travel through this agent's connection, not through the
shell's network. A step that runs in the shell, such as a bundled script, a `git
push` to Egbe's Git endpoint or a deploy upload, needs the shell to reach the
Egbe host (`os.hz.egbe.dev`). If a proxy or allowlist refuses that request
before Egbe answers, for example HTTP 403 on CONNECT or curl status `000`, tell
the founder: they allow that host in this agent's network settings or continue
with an agent on their own computer. Code can also be published without the
shell by committing through the connector (`egbe-os-git`, "Without a terminal").
Until the shell step or that commit and its deploy succeed, do not report the
work as published: a preview in this agent or on this computer is not an Egbe
deployment.

The harness can also refuse a step before Egbe answers: a denied file read or
command (`EPERM`, `operation not permitted`), a certificate error, or a
connector call that fails as a whole with HTTP 403. Egbe's own refusals of an
API request come back as a result with a `status` and Egbe's `message`, and the
`egbe_skill` tool never answers 403. Egbe refuses a whole call with 403 only for
a browser `Origin` it does not accept, so such a 403 most likely comes from the
harness, a proxy or a policy in front of Egbe. Don't retry it in a loop, route
around it or disable certificate verification. If `egbe_skill` was refused, read
that skill from an installed Egbe catalog or plugin copy, if this session has
one. Name the blocked file, command, host or tool and ask the founder to allow
it, or to trust the host through the environment's network setting. Then
continue the work that doesn't need it and say what waits on that permission.
While `egbe_skill` works, `egbe-os-quickstart`'s `references/environment.md`
lists these cases.


# Useful recurring work

Configure agreed recurring work and keep its execution, context and delivery reliable.
Execution and scheduling belong to the user's harness; Egbe supplies capabilities
and guidance, not a managed scheduler.

## Choose the entry

At setup, or after verified work reaches a milestone that a loop could carry
forward, follow [Offer a Business Loop](references/run-preset.md#offer-a-business-loop). It checks
saved loops and earlier offers, chooses one fitting loop, explains it to the
founder and saves it for the business once they agree.

For a named preset, a Dashboard card, `Run Egbe Loop <preset-id>`, `Run Egbe Loop mine/<id>` or a saved title, follow
[Start or resume a Dashboard loop](references/run-preset.md#start-or-resume-a-dashboard-loop). Read a bare ID directly from this skill's `references/presets/<id>.md`. The OS `/loops` API serves private definitions and title discovery.

When recurring work has a decision of its own (for example, choosing which part
of onboarding to improve after each cohort), use **egbe-os-loop-engineering**
to find or save its diagram as part of planning or configuring the work.
Link the saved loop to its existing plan for continuation. A fixed reminder
or report can follow its ordinary scheduling workflow.

For the Business Loop, existing product reports, or a change/disable request,
follow [Business Loop and reporting schedules](references/product-reporting.md).
It owns registration, saved settings and delivery checkpoints. The project's
Business Loop method owns business decisions; `egbe-os-product-report` packages
its result. Neither a manual loop nor a manual report requires scheduling.

For other recurring work, resolve the requested responsibility and configure it below.
When assembling or debugging continuation across runs, use the
[continuation check](references/continuation-check.md). It tests saved work and
tool behavior, independently of the harness's scheduling mechanism.

## Resolve the requested responsibility

Use the caller's agreed purpose, sources, cadence, notification condition and
action scope. For checks supporting a Business Loop, retain the link to the
current work and checkpoint; return findings there rather than starting a second
business review. A bounded check or report does not require a Business Loop.
The [catalogue](references/catalog.md) lists supported operations
and access requirements, not a ranking of business priorities. If the purpose
is still undecided, return that decision to the caller's project method before
scheduling. Check actual access and existing jobs; preserve saved choices,
including declines. Do not activate an additional routine from a recommendation
alone; quickstart and milestone offers have no automatic scheduling exception.

## Configure the agreed work

Use the scheduling mechanism actually available in this agent's environment and
its native setup instructions. If unavailable, explain the limitation and offer a
manual review; do not claim that a skill keeps the agent running after the chat ends.
Cadence and observation window come from the agreed responsibility, not the
frequency of another routine. Use a supported next-checkpoint schedule when
that is the agreed timing; do not replace it with frequent empty polls. Verify
whether quiet runs still create chats or notifications: suppressing report text
does not prove they are suppressed. Preserve requested digests and required safety checks.

The scheduled task needs the project context, relevant skill, purpose, sources,
allowed actions, budget or stopping conditions where applicable, and notification
rules. Keep credentials in the project's credential store, not in the task prompt.
If the harness ends a turn after a fixed time, as `EGBE.md` describes, bound
each run's work unit to fit with margin and save the checkpoint before long
verification steps; the next run continues the rest.
For product or market/acquisition judgments, include actual workspace paths to
the relevant `egbe-docs/playbooks/product.md` or `market-and-acquisition.md`,
their required sections and the concrete current plan. Confirm the scheduled runner can read these project
files, including local adaptations and shared collaboration guidance. A copied summary or bundled method
is not a substitute. If unavailable, report that limitation and restore access
before making dependent decisions; authorized status reads or safety stops need
not wait for a new planning lifecycle.
Use the scheduler's durable state or existing project notes to retain the last
checked window/revision, active work and decisions needed by the next run.

Default to observing and reporting unless corrective work is authorized. For a
meaningful finding, explain its evidence, impact and recommended next action; use
the relevant domain capability for agreed work. Unchanged state
should be quiet unless the founder requested a periodic digest. An inaccessible source
is a coverage gap, not proof that the product is healthy.

When the project's session logging is on, check that scheduled runs are logged
like its other sessions, following the logging setup's verification. If the
runner can't log them, for example in an environment without the project's
logging settings, tell the founder that these runs aren't recorded.

Verify that the task is registered with the intended project, schedule and action
scope. Where feasible, run a read-only first check to confirm access and useful
output. Report what is configured, what remains unverified and how to pause or
change it. Never describe a proposed task as active.

## Continue without repeating work

At each run, first synchronize stored project work as `EGBE.md` describes, then read
the prior checkpoint and current state before acting. Apply the
project's current method, concrete plan and existing authorization for product or marketing
judgments; domain skills supply evidence and operational constraints. For other
work, follow the relevant domain contract. Do not rerun an entire audit or reread
the whole repository when a bounded change check answers the question. Reconcile an uncertain
previous write before retrying it, and avoid duplicate reports or fixes. Retain the
agreed scope when proposing a new task; return decisions outside it to the founder.

When the caller changes the checkpoint or ends this responsibility, update or
disable its existing native job and saved record, then verify the actual state.

### Same blocker again

When work stops on a dependency only the founder or an external party can clear,
such as a permission, account connection, sender route or approval, save it in the
existing checkpoint as an open blocker: what is missing, the exact step that
unblocks it, the one cheap read that shows whether it has cleared and the response
that means it is still blocked, when the founder was told, how many runs found it
unchanged and whether a pause was proposed. Tell the founder once, with that exact
step. At the next run, after synchronizing, make that read before the blocked work.
If it returns the saved still-blocked response, update the count and skip the
blocked work quietly: no repeated audit, retry or blocker report. After three
unchanged runs, propose once pausing the routine or lowering its frequency and say
how to resume; change the schedule only with the founder's agreement. The project's
method may set a different follow-up. If the read shows the blocker cleared,
continue from the checkpoint and remove the open blocker. A different error or an
unreachable source is a coverage gap, not proof of either state; run the normal
bounded check, without repeating the blocker report if it confirms the same blocker.
Work that does not depend on the blocker, required safety checks and requested
digests keep running as before; a digest may restate the open blocker briefly.
