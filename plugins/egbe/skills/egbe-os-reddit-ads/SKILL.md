---
name: egbe-os-reddit-ads
description: Execute Reddit Ads operations through Egbe OS, including paused builds, status changes, metrics, assets and uncertain-write recovery.
metadata:
  egbe-when: "Use for paid Reddit campaign operations, targeting IDs, creative uploads, metrics and recovery."
  egbe-visible: "true"
  egbe-title: "Reddit Ads"
  egbe-description: "Build and manage Reddit advertising through Egbe, with verified state and recoverable execution."
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


# Reddit Ads

Use `OS_URL`, `OS_API_KEY` and `Authorization: Bearer $OS_API_KEY`.
Ad-network operations go through OS; do not request provider secrets or call
Reddit Ads directly.

Use the requested targeting, objective, budget and assets for writes.
Status, spend and pause requests do not require research or policy files.

## Read only what the operation needs

- Payloads, targeting lookup and errors: [API](references/runtime/api-reference.md).
- Access/funding: [readiness](references/workflows/readiness.md).
- Build paused: [build](references/workflows/build-paused.md).
- Read-only checks: [launch readiness](references/workflows/launch-ready.md).
- Activate/resume: [launch](references/workflows/launch.md).
- Status, metrics, diagnostics and pause: [monitoring](references/runtime/monitoring.md).
- Wallet/update restrictions: [constraints](references/runtime/policies.md).
- Durable requests and IDs: [execution records](references/runtime/artifacts.md).
- Destination: [requirements](references/destination-requirements.md).
- Tracking: [pixel/events](references/runtime/pixel-and-tracking.md) and
  [attribution](references/runtime/shared-analytics-attribution.md).
- Optional static banners: [templates](references/creative/static-banner-system.md)
  and [capture/upload](references/creative/html-to-png-pipeline.md).

## Execution constraints

Create PAUSED. Persist the exact campaign request and stable `Idempotency-Key`
before sending. Reuse that key/payload; never mint a key to bypass an unknown
outcome. Child-create caches are not durable recovery: reconcile ambiguous writes.

Campaign launch does not activate children. Activate only selected groups/ads
through status routes, save acceptance receipts, then read each object.
Configured ACTIVE, moderation approval and actual delivery are different facts.
Never infer a new activation timestamp from a read-only check.

Ad-group creation reserves a wallet hold even when paused. Ordinary update
rejects `goal_value`/`goal_type`; no in-place budget-change operation is
supported here. Status uses its dedicated route for Registry synchronization.
Do not automatically create a replacement group to change budget.
Never use creates to probe an API schema or broaden rejected targeting silently.

`scripts/validate-reddit-artifacts.py` checks saved operation evidence locally;
it is not authorization, a marketing validator or proof of live freshness.
