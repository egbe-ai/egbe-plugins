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
Files this skill refers to are next to this `SKILL.md`, except any listed under
"Files downloaded on demand".

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs a set-up project workspace. In a persistent
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
Code on their own computer. Until the shell step succeeds, do not report the work
as published: a Claude Artifact or a local preview is not an Egbe deployment.


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

## Files downloaded on demand

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project workspace; without one,
tell the founder that the step needs it and continue with the rest of the work.

In a project workspace, before a step that runs or copies one of these files,
download it into `.egbe/skills/egbe-os-reddit-ads/` at the same relative path, for example
`curl -fsSL <url> --create-dirs -o .egbe/skills/egbe-os-reddit-ads/<file>`, and check that its SHA-256
matches. Also download the files it uses from the same folder, such as the
modules a script imports. Wherever this skill names one of these files by its
path in the skill (for example `scripts/...` or `assets/...`), use `.egbe/skills/egbe-os-reddit-ads/<file>`;
where it writes `<skills-directory>`, use `.egbe/skills`.
Keep `.egbe/skills/` out of Git by adding it to `.gitignore`.

| File | URL | SHA-256 |
| --- | --- | --- |
| `assets/static-banners/bold-statement/template.html` | https://os.hz.egbe.dev/skills/egbe-os-reddit-ads/resources/assets/static-banners/bold-statement/template.html | `bb60b26c259ada4765c3c3e579ab52335970878b7e926f342aa05f7ab1156d87` |
| `assets/static-banners/data-proof/template.html` | https://os.hz.egbe.dev/skills/egbe-os-reddit-ads/resources/assets/static-banners/data-proof/template.html | `4ff2b2dc8bcdca4e9feeecfaf554f7103cf48fdb509e2e137c8c5327bd3f0914` |
| `assets/static-banners/honest-breakdown/template.html` | https://os.hz.egbe.dev/skills/egbe-os-reddit-ads/resources/assets/static-banners/honest-breakdown/template.html | `add05a2330836e49b98f938706fbd6aed58c63c25ddeecad06d49b9b323be8c2` |
| `assets/static-banners/question-hook/template.html` | https://os.hz.egbe.dev/skills/egbe-os-reddit-ads/resources/assets/static-banners/question-hook/template.html | `34a6fff76aff55a9eb23e8e2be082741133a1051f20a5743549233c7004f5d7a` |
| `assets/static-banners/reddit-post-style/template.html` | https://os.hz.egbe.dev/skills/egbe-os-reddit-ads/resources/assets/static-banners/reddit-post-style/template.html | `2defc73f5047bebf570f03d4d66192050a159edca5c661f139a92b1d0bace138` |
| `scripts/capture-ad.sh` | https://os.hz.egbe.dev/skills/egbe-os-reddit-ads/resources/scripts/capture-ad.sh | `c72f1e393519a2f9ea46891e9dc6fc3433f4cea2d1e65cd27ec376a0a6d19a02` |
| `scripts/validate-reddit-artifacts.py` | https://os.hz.egbe.dev/skills/egbe-os-reddit-ads/resources/scripts/validate-reddit-artifacts.py | `d2c7917ae0d8e27da735114fbf604b0ebceac3ddc23254f75024af3aa07fc0c3` |
