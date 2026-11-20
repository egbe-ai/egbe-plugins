---
name: egbe-os-instantly-campaign-launcher
description: Prepare, explicitly activate, observe and recover project-owned Instantly email campaigns and reply queues; inspect assigned sender state.
version: 1.3.5
user-invocable: true
metadata:
  egbe-when: "Use for Instantly campaign preparation, activation, replies, observation or recovery."
  egbe-visible: "true"
  egbe-title: "Email outreach"
  egbe-description: "Operate scoped email campaigns, imports, reply queues and factual campaign observations."
  egbe-category: "Marketing & growth"
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

Run a script bundled with this skill from the root of a project folder set up
for Egbe, with `OS_AGENT_NAME="<your agent name>"` set inline, such as `OpenCode`.
A script that calls Egbe reads `OS_URL`, `OS_API_KEY` and this agent's connection
ID from `.env.local` through Egbe's request helper, which comes with the plugin at
`../egbe-os-quickstart/scripts/egbe-curl.py` from this skill's folder. Where this
skill says a script needs `OS_URL` or `OS_API_KEY` in its environment, start it
through the helper, which loads `.env.local` without executing it:
`python3 <helper> --egbe-run <command>`, with the helper's absolute path. Where
this skill writes `<skills-directory>`, use the plugin's `skills` folder, which
holds this skill's folder.


# Instantly campaign operations

Use the operation the task calls for; preparing a campaign is not authorization
to activate it, add recipients, reply, or install recurring jobs. Existing
research, copy, lists and run state are valid inputs. This capability does not
select a business goal or decide an outcome from reply rate.

Requires Node 24+ (`node:sqlite`), `OS_URL` and `OS_API_KEY`. Use the project
OS connection, not personal provider keys. Missing credentials are a blocker,
not permission to send cold outreach through Mailu or a trust-domain mailbox.

Read only the reference needed for the operation:

- [Campaign operations](references/instantly-ops.md): preparation/activation,
  sender selection and state, pagination, date-filtered reads, rendering, verification,
  imports and safe cleanup.
- [Reply handling](references/reply-handling.md): queue actions, confirmed
  opt-outs, same-thread sends and uncertain-send recovery.
- [Observation and scheduling](references/observation-and-scheduling.md):
  factual metrics, configured protection, optional jobs and verification.
- [Run state](references/run-state.md): executable configuration, artifacts,
  identity, handoff and replenishment; includes the [spec scaffold](references/run-spec-template.json).

For activation, readiness to continue, or protection recovery, read
[configured protection](references/observation-and-scheduling.md#configured-operational-protection)
to check what the bundled monitor supports and what its state actually proves.

## Through the Egbe connector

Through the connector alone, observe without changing anything: the reads in
[campaign operations](references/instantly-ops.md#paginated-and-date-filtered-reads)
with their cursor rules, `GET /outreach/instantly/campaigns/{id}`,
`/campaigns/{id}/analytics`, `/campaigns/{id}/sending-status`, and the
assigned-sender and exclusion reads, all below `/outreach/instantly`. Report
them as provider observations at their read time; they are not the run's
`outreach.db` history, so do not compute conclusions that need it. Preparation,
activation, imports, replies, opt-out handling and monitoring run the bundled
Node scripts against the run's files and `outreach.db`, and need a set-up
project workspace: in a persistent project workspace not set up yet, call
`egbe_local_setup`; otherwise tell the founder which step needs it. Do not
reproduce those writes with raw requests.

Keep the owning run under
`egbe-docs/marketing/campaigns/instantly/<run_key>/`. Before continuing, read its
manifest and state files and query the project `outreach.db`, next to the run
directories, only through the read-only `scripts/outreach-report.js`
([usage](references/observation-and-scheduling.md#collect-facts-for-one-run)).
If it reports the database missing, say so; do not search the workspace or open
SQLite with inline code. Bundled scripts treat missing history after sending as a
blocker, not something to recreate. JSON checkpoints and queue
files remain active state, not disposable duplicates. Use only the run's
campaign IDs. Registry/gateway ownership is the tenant authority; local
manifest/tags narrow the run and detect conflicts, but do not grant access.

Commands return observations and operation evidence. Check readbacks and
incomplete actions before reporting success. Preserve contacts/messages/state
in the access-controlled project repository, credentials outside Git, and one
active executor when transferring work. Keep the current plan and decisions in
the existing project context, without a second preflight/log/lessons package.
