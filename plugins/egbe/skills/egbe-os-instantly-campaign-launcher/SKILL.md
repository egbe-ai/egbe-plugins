---
name: egbe-os-instantly-campaign-launcher
description: Prepare, explicitly activate, observe and recover project-owned Instantly email campaigns and reply queues.
version: 1.3.2
user-invocable: true
metadata:
  egbe-when: "Use for Instantly campaign preparation, activation, replies, observation or recovery."
  openclaw: {"requires":{"env":["OS_URL","OS_API_KEY"]},"primaryEnv":"OS_URL","emoji":"📬","os":["linux","darwin"]}
  egbe-visible: "true"
  egbe-title: "Email outreach"
  egbe-description: "Operate scoped email campaigns, imports, reply queues and factual campaign observations."
  egbe-category: "Marketing & growth"
---

<!-- egbe-mcp-connection:v1 -->
This skill comes with the Egbe plugin. Make every Egbe API call it describes with
the Egbe connector's `egbe_request` tool: pass the HTTP method, the API path (for
example `/me/limits`), query parameters in `query` and the JSON body in `body`.
For these calls leave out `OS_URL`, the Authorization header, `.env.local` and
`egbe-curl.py`, and skip catalog update checks; the connection authenticates and
identifies the request.
Also pass the `business` that `egbe_setup` returned. Files this skill refers to
are next to this `SKILL.md`, except any listed under "Files downloaded on demand".

A step that needs a local project key, such as a git push or a local deploy
command, works only in a persistent project workspace. There, if the project's
Git-ignored `.env.local` has no `OS_API_KEY` yet, call `egbe_local_setup` once
and save its `OS_URL` and `OS_API_KEY` there, preserving other entries. Use only
those two values: the plugin already provides Egbe's skills, so do not install
the Egbe catalog or follow the rest of that result. Never show the key in chat or
put it in logs, commits or URLs. Without such a workspace, tell the founder that
this step needs an agent with a project folder, and continue with the rest of
the work.


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
  sender selection, pagination, date-filtered reads, rendering, verification,
  imports and safe cleanup.
- [Reply handling](references/reply-handling.md): queue actions, confirmed
  opt-outs, same-thread sends and uncertain-send recovery.
- [Observation and scheduling](references/observation-and-scheduling.md):
  factual metrics, configured protection, optional jobs and verification.
- [Run state](references/run-state.md): executable configuration, artifacts,
  identity, handoff and replenishment; includes the [spec scaffold](references/run-spec-template.json).

Before activation, also read [configured protection](references/observation-and-scheduling.md#configured-operational-protection)
to check whether the supplied safeguards are supported by the bundled monitor.

Keep the owning run under
`egbe-docs/marketing/campaigns/instantly/<run_key>/`. Inspect its manifest,
state and project `outreach.db` before continuing; JSON checkpoints and queue
files remain active state, not disposable duplicates. Use only the run's
campaign IDs. Registry/gateway ownership is the tenant authority; local
manifest/tags narrow the run and detect conflicts, but do not grant access.

Commands return observations and operation evidence. Check readbacks and
incomplete actions before reporting success. Preserve contacts/messages/state
in the access-controlled project repository, credentials outside Git, and one
active executor when transferring work. Keep the current plan and decisions in
the existing project context, without a second preflight/log/lessons package.
