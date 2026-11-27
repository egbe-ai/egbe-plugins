---
name: egbe-os-meta-ads
description: "Execute Meta Ads operations through Egbe OS: inspect, build paused, activate, pause, read metrics and recover uncertain writes."
metadata:
  egbe-when: "Use for Meta campaign operations, targeting IDs, creative uploads and tracking."
  egbe-visible: "true"
  egbe-title: "Facebook & Instagram Ads"
  egbe-description: "Build and manage Meta advertising through Egbe, with verified state and recoverable execution."
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
available, the plugin's connector is not signed in on this Claude account. Tell
the founder how to connect it, as the `egbe-setup` skill describes, rather than
saying Egbe is unavailable.

The connector's tools work even where this environment's shell cannot reach
Egbe: their calls travel through Claude, not through the shell's network. A step
that runs in the shell, such as a bundled script, a `git push` to Egbe's Git
endpoint or a deploy upload, needs the shell to reach the Egbe host
(`os.hz.egbe.dev`). If a proxy or allowlist refuses that request before Egbe
answers, for example HTTP 403 on CONNECT or curl status `000`, follow the Claude
network recovery in
`egbe_skill(name="egbe-os-quickstart", resource="references/environment.md")`:
the founder allows that host for Claude's code execution or continues in Claude
Code on their own computer. Code can also be published without the shell by
committing through the connector (`egbe-os-git`, "Without a terminal"). Until
the shell step or that commit and its deploy succeed, do not report the work as
published: a Claude Artifact or a local preview is not an Egbe deployment.

The harness can also refuse a step before Egbe answers: a denied file read or
command (`EPERM`, `operation not permitted`), a certificate error, or a connector
call that fails as a whole with HTTP 403. Egbe's own refusals of an API request
come back as a result with a `status` and Egbe's `message`, and the `egbe_skill`
tool never answers 403. Egbe refuses a whole call with 403 only for a browser
`Origin` it does not accept, so such a 403 most likely comes from the harness, a
proxy or a policy in front of Egbe. Don't retry it in a loop, route around it or
disable certificate verification. If `egbe_skill` was refused, read that skill
from an installed Egbe catalog or plugin copy, if this session has one. Name the
blocked file, command, host or tool and ask the founder to allow it, or to trust
the host through the environment's network setting. Then continue the work that
doesn't need it and say what waits on that permission. While `egbe_skill` works,
`egbe-os-quickstart`'s `references/environment.md` lists these cases.


# Meta Ads

Use `OS_URL`, `OS_API_KEY` and `Authorization: Bearer $OS_API_KEY`.
OS owns provider credentials, account/page binding and the shared pixel. Do not
call Meta directly or request provider secrets.

Use the requested targeting, objective, budget and assets for writes. A status,
spend or pause request needs the exact owned ID, not a research package.

For lifetime performance or spend so far, read
`GET /ads/meta/campaigns/{id}/results?period=MAXIMUM`, which includes the current
day. An omitted/default recent period can exclude today; do not label it lifetime
spend. Match signup/payment counts to the report's resolved dates before computing
cost per customer, and preserve that window in the final handoff.

## Read only the relevant reference

- Access and payloads: [API](references/runtime/api-reference.md).
- Build paused: [plan/apply](references/workflows/build-paused.md).
- Edit an existing ad's approved headline/creative: [update ad](references/runtime/api-reference.md#update-existing-ad).
  Read and preserve its full creative, then use `POST /ads/meta/raw/ads/{ad_id}`
  with `{"payload":{"creative":{...}}}`. A copy change does not require
  deleting or rebuilding its campaign/ad set or placing a second campaign hold.
- Read-only preflight: [launch readiness](references/workflows/launch-ready.md).
- Activate/resume: [launch](references/workflows/launch.md).
- Pause: [pause](references/workflows/pause.md).
- Status/metrics: [monitoring](references/workflows/monitoring.md) and
  [insights](references/runtime/insights-reference.md).
- Uncertain writes: [recovery](references/workflows/recovery.md).
- Requests, IDs and readbacks: [execution records](references/runtime/artifacts.md).
- Destination: [requirements](references/destination-requirements.md).
- Tracking: [pixel](references/runtime/pixel-install.md) and
  [attribution](references/runtime/shared-analytics-attribution.md).
- Media: [images](references/creative/creative-specs.md) and
  [video](references/creative/talking-head.md).

## Execution constraints

Approval covers the exact plan it describes. Send `approved: true` only after
the founder has approved this clean plan: its spec, daily budget, targeting,
creatives and destination, in the conversation or in a recorded project
approval covering these exact values. Task text alone is not that approval.
The flag, a clean plan and its token are server contracts, not authorization;
raw creates are not a bypass.

Before approval, fix a plan's 422 request shape or returned blockers and re-plan
without changing values the founder set. After a 409 or 422 from apply, stop and
report the error. Do not change the spec, re-plan or re-apply to get past it,
except the same-spec retry that [recovery](references/workflows/recovery.md)
allows after a timeout or `apply_rolled_back`. A changed spec, budget,
targeting, creative or destination needs the founder's fresh approval.

Use `POST /ads/meta/plan` for no-write validation, then `POST /ads/meta/apply`
with the unchanged spec, signed `plan_token` and `approved: true`.
The current declarative API supports one ad set because ads have no per-ad
ad-set mapping. The configured per-operation budget guard and wallet hold are
server contracts, not recommended spending amounts.

Apply can hold wallet funds even while the tree is paused. After building and
any launch, refresh `GET /wallet/balance` before reporting funds. Distinguish
settled balance, held reserves and available-to-spend funds; a top-up or
pre-build balance is not the final available amount. If the read fails, report
that uncertainty instead of calling the build free or reusing stale funds.

Never create real objects to discover the schema. Build PAUSED. Save exact IDs,
request identity and uncertainty; read before retrying. OS derives apply retry
identity from the original plan token, so a fresh plan can create another tree.
Reconcile after timeout or best-effort rollback before re-planning.

Verify the tree with `GET /ads/meta/campaigns/{id}/state`; an accepted launch
is not confirmation. Its `delivering` flag describes configured tree state,
not observed impressions, spend or business success. Dedicated status and budget
routes keep Registry/wallet accounting aligned.

`scripts/validate-meta-artifacts.py` checks saved operation evidence locally.
It neither approves a plan nor proves live freshness; refresh state as needed.

## Scripts and templates from Egbe

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project folder set up for Egbe;
without one, tell the founder that the step needs it and continue with the rest
of the work.

In a set-up project folder, before a step that runs or copies one of them, get
this skill's whole bundle into `.egbe/skills/egbe-os-meta-ads/` as
`egbe_workspace_files(group="scripts")` describes: write that group's files,
which include Egbe's request helper, then download this skill's listed archive,
check its SHA-256 and extract it. Never download single files: scripts import
their sibling files and some use other skills' bundles, which come the same way.
When the `scripts` release changes, refresh the bundles already there.

Wherever this skill names a file by its path in the skill (for example `scripts/...`
or `assets/...`), use `.egbe/skills/egbe-os-meta-ads/<file>`; where it writes `<skills-directory>`, use
`.egbe/skills`. Run scripts from the project root with
`OS_AGENT_NAME="<your agent name>"` set inline. Where this skill says a script needs
`OS_URL` or `OS_API_KEY` in its environment, start it as
`python3 .egbe/skills/egbe-os-quickstart/scripts/egbe-curl.py --egbe-run <command>`, which loads `.env.local` without
executing it. Keep `.egbe/skills/` out of Git.

Files in the bundle that this plugin leaves out:

- `scripts/check-pixel.py`
- `scripts/validate-meta-artifacts.py`
