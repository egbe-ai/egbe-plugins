---
name: egbe-os-openai-ads
description: Build, operate and measure OpenAI Ads campaigns, including conversion tracking.
metadata:
  egbe-when: "Offer when customers discover products through AI; use for existing OpenAI Ads campaigns."
  egbe-visible: "true"
  egbe-title: "OpenAI Ads"
  egbe-description: "Run ads through Egbe. Create and manage OpenAI advertising campaigns, track conversions and review performance."
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


# OpenAI Ads

Run the requested part of a campaign lifecycle from any product repository.
No scaffold, egbe-os-product-build stage, instance layout or particular agent runtime
is required. An edit or audit does not authorize a new campaign or a launch.

## Runtime and reference discovery

Use `OS_URL` and `OS_API_KEY` with the `ads` scope:
`Authorization: Bearer $OS_API_KEY`. Provider credentials stay inside Egbe OS.
Browser Pixel is the public tracking exception; management and server event
delivery go through OS.

`GET /ads/openai/skill` returns this entrypoint only. Read the referenced files
from the installed `egbe-os-openai-ads` bundle. If absent, retrieve the complete
bundle with `GET $OS_URL/skills/openai-ads` (ZIP), or fetch one file through
`GET $OS_URL/skills/openai-ads/resources/<relative-path>`, for example
`references/workflows/monitoring.md`. Do not guess missing instructions.
Exact request schemas are at `$OS_URL/openapi.json`.

## Choose the workflow

For campaign work read the [artifact contract](references/runtime/artifacts.md),
then only the relevant workflow. Resolve the existing campaign before writing.

For a performance or cross-channel comparison, read
[Monitoring and changes](references/workflows/monitoring.md) and fetch
`GET /ads/openai/campaigns/{id}/results?start_time=<unix_seconds>&end_time=<unix_seconds>`
for each selected campaign's reporting window. Both query parameters are
required integers in UTC Unix **seconds**, not ISO date strings or milliseconds.
For example, January 1–2, 2026 UTC uses `start_time=1767225600&end_time=1767312000`;
convert the actual requested dates. Correct a missing/invalid-period 422 and retry
the report before treating it as unavailable. A campaign list/detail can include a `metrics` snapshot, but it does not
replace this report or establish its dates and freshness. Match the report's
window to the product/payment outcomes before computing acquisition cost.

| Request | Read |
|---|---|
| Inspect destination-specific requirements only | [Destination requirements](references/destination-requirements.md) |
| Check account/product readiness | [Readiness](references/workflows/readiness.md) |
| Assemble planned targeting and creatives | [Creative and targeting assembly](references/workflows/creative-assembly.md) |
| Bind UTMs and product analytics | [Tracking](references/workflows/tracking.md) |
| Build paused objects or recover a partial build | [Build and recovery](references/workflows/build-paused.md) |
| Activate an approved campaign | [Launch](references/workflows/launch.md) |
| Diagnose serving/review blockers, inspect performance or edit an existing campaign | [Monitoring and changes](references/workflows/monitoring.md) |
| Stop delivery and confirm state | [Pause](references/workflows/pause.md) |
| Add optional Pixel/server conversions or conversion bidding | [Conversions](references/workflows/conversions.md) |
| Exact operations, units, errors and readback | [API reference](references/runtime/api-reference.md) |

## Shared operating boundaries

- Preserve the selected campaign, segment, offer, destination and approved daily
  budget. Reuse recorded provider IDs. A new request key is not recovery.
- Create paused; launch only within explicit founder authorization or an
  applicable product marketing policy. Neither this skill nor an API key grants
  permission to spend. Never raise an approved budget to satisfy provider minima.
- Only daily USD budgets. Daily budget is an average, not a hard daily cap;
  use the API reference for pacing and wallet semantics. No mandatory lifetime
  budget, arbitrary total-spend ceiling, or copied cross-network thresholds.
- Distinguish intended configuration, observed provider state, actual delivery,
  product outcomes and attribution. Do not infer one from another.
- Provider conversion tracking is optional for ordinary traffic campaigns.
- Monitoring reads do not authorize campaign changes. These API operations do
  not install recurring jobs.
- Persist artifacts after meaningful progress and before handing off a partial
  result. Preserve repository conventions; commit/push only when authorized by
  the current task or repository rules, not merely because this skill ran.
- Artifact repair and audits do not mutate provider objects. Real
  repairs use the explicitly authorized build/edit workflow.

## Local self-check and handoff

Run the portable, read-only structural check from the downloaded skill:

```bash
python3 <skill-dir>/scripts/validate-openai-artifacts.py \
  --product-root <product-repo-root> --phase <phase>
```

Use `--campaign <openai-slug>` when the task names a different campaign from
the selected one. See the artifact contract for phases and required files.
This validates structure and cross-references, not permission, current provider
state, creative quality or campaign success. A validation error never justifies
inventing evidence or blocking an urgent authorized pause.

Return: campaign folder/ID, actual changes (or none), observed state and timestamp,
evidence gaps and operation outcome. For unfinished work include the pending
operation and its saved recovery key; never include credentials or customer data.

## Scope

No raw provider passthrough, lifetime budgets, product feeds, custom audiences,
automatic payment-gateway events, fleet scheduling or Dashboard integration.
Scheduling is external to these API operations.
