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
Files this skill refers to are next to this `SKILL.md`, except any listed under
"Files downloaded on demand".

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


# Meta Ads

Use `OS_URL`, `OS_API_KEY` and `Authorization: Bearer $OS_API_KEY`.
OS owns provider credentials, account/page binding and the shared pixel. Do not
call Meta directly or request provider secrets.

Use the requested targeting, objective, budget and assets for writes. A status,
spend or pause request needs the exact owned ID, not a research package.

## Read only the relevant reference

- Access and payloads: [API](references/runtime/api-reference.md).
- Build paused: [plan/apply](references/workflows/build-paused.md).
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

Use `POST /ads/meta/plan` for no-write validation, then `POST /ads/meta/apply`
with the unchanged spec, signed `plan_token` and `approved: true`.
That flag is a server contract, not evidence of user authorization. Apply only
within current authorization; raw creates are not an approval bypass.
The current declarative API supports one ad set because ads have no per-ad
ad-set mapping. The configured per-operation budget guard and wallet hold are
server contracts, not recommended spending amounts.

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
