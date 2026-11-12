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

| Request | Read |
|---|---|
| Inspect destination-specific requirements only | [Destination requirements](references/destination-requirements.md) |
| Check account/product readiness | [Readiness](references/workflows/readiness.md) |
| Assemble planned targeting and creatives | [Creative and targeting assembly](references/workflows/creative-assembly.md) |
| Bind UTMs and product analytics | [Tracking](references/workflows/tracking.md) |
| Build paused objects or recover a partial build | [Build and recovery](references/workflows/build-paused.md) |
| Activate an approved campaign | [Launch](references/workflows/launch.md) |
| Inspect performance or edit an existing campaign | [Monitoring and changes](references/workflows/monitoring.md) |
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
