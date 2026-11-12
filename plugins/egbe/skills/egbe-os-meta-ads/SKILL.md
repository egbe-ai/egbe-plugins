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
This skill was delivered through the Egbe MCP connection. Make every Egbe API
call it describes with the `egbe_request` tool: pass the HTTP method, the API
path (for example `/me/limits`), query parameters in `query` and the JSON body
in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Read a referenced file with
`egbe_skill(name=<skill>, resource=<relative path>)`.

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs the standard workspace setup. In a persistent
project workspace that is not set up yet, call `egbe_local_setup` and follow it.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


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
