---
name: egbe-os-product-routines
description: Configure and verify recurring Business Loops, reports, product-health checks and campaign oversight.
metadata:
  egbe-when: "Offer when repeated work or changing conditions warrant recurring attention."
  egbe-visible: "true"
  egbe-title: "Keep your product moving"
  egbe-description: "Keep agreed work moving with a recurring Business Loop, product checks and reports in your agent."
  egbe-category: "Business operations"
---

<!-- egbe-mcp-connection:v1 -->
This skill comes with the Egbe plugin. If this project has its own installed copy
of the skill, use that copy instead. Otherwise make every Egbe API call it
describes with the Egbe connector's `egbe_request` tool: pass the HTTP method,
the API path (for example `/me/limits`), query parameters in `query` and the JSON
body in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Files this skill refers to are next to this `SKILL.md`, except any listed under
"Files downloaded on demand".

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs the standard workspace setup. In a persistent
project workspace that is not set up yet, call `egbe_local_setup` and follow it.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


# Useful recurring work

Configure agreed recurring work and keep its execution, context and delivery reliable.

## Choose the entry

For the Business Loop, existing product reports, or a change/disable request,
follow [Business Loop and reporting schedules](references/product-reporting.md).
It owns registration, saved settings and delivery checkpoints. The project's
Business Loop method owns business decisions; `egbe-os-product-report` packages
its result. Neither a manual loop nor a manual report requires scheduling.

For other recurring work, resolve the requested responsibility and configure it below.

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
alone; quickstart has no automatic scheduling exception.

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

Verify that the task is registered with the intended project, schedule and action
scope. Where feasible, run a read-only first check to confirm access and useful
output. Report what is configured, what remains unverified and how to pause or
change it. Never describe a proposed task as active.

## Continue without repeating work

At each run, read the prior checkpoint and current state before acting. Apply the
project's current method, concrete plan and existing authorization for product or marketing
judgments; domain skills supply evidence and operational constraints. For other
work, follow the relevant domain contract. Do not rerun an entire audit or reread
the whole repository when a bounded change check answers the question. Reconcile an uncertain
previous write before retrying it, and avoid duplicate reports or fixes. Retain the
agreed scope when proposing a new task; return decisions outside it to the founder.
When the caller changes the checkpoint or ends this responsibility, update or
disable its existing native job and saved record, then verify the actual state.
