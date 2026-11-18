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


# Reddit Ads

Use `OS_URL`, `OS_API_KEY` and `Authorization: Bearer $OS_API_KEY`.
Ad-network operations go through OS; do not request provider secrets or call
Reddit Ads directly.

Use the requested targeting, objective, budget and assets for writes.
Status, spend and pause requests do not require research or policy files.

## Through the Egbe connector

Campaign reads, paused builds, status changes, metrics and recovery work through
the connector, with execution records in Egbe's artifact store ([execution
records](references/runtime/artifacts.md)).
<!-- egbe-connector-todo: html-render. Replace the next sentence when Egbe serves HTML-to-PNG rendering as an API route. -->
Capturing a static banner from HTML runs `scripts/capture-ad.sh` with a local
Chrome and needs a set-up project workspace: in a persistent project workspace
not set up yet, call `egbe_local_setup`; otherwise tell the founder which step
needs it. Through the connector alone, use a finished image the founder supplies
at a public HTTPS URL or a stock image from `egbe-os-images` instead, and upload
it as [capture/upload](references/creative/html-to-png-pipeline.md) describes.

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
