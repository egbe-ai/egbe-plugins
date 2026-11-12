---
name: egbe-os-linkedin-ads
description: Build, operate and measure LinkedIn Single Image and Text Ad campaigns.
metadata:
  egbe-when: "Offer for audiences defined by roles or companies; use for existing LinkedIn campaigns."
  egbe-visible: "true"
  egbe-title: "LinkedIn Ads"
  egbe-description: "Run ads through Egbe. Reach professional audiences with image and text ads, manage campaigns and measure results."
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


# LinkedIn Ads

Use from any product repository with `OS_URL` and `OS_API_KEY` (scope `ads`).
No scaffold, instance layout or egbe-os-product-build stage is required. Provider
credentials stay inside Egbe OS; never request them for product code.

`GET /ads/linkedin/skill` returns this entrypoint. Read only the references needed
for the task from the installed bundle. External agents may download
`GET /skills/linkedin-ads` (ZIP), or
`GET /skills/linkedin-ads/resources/<relative-path>`.
Exact schemas are at `$OS_URL/openapi.json`.

| Task | Reference |
|---|---|
| Inspect destination-specific requirements only | [Destination requirements](references/destination-requirements.md) |
| Continue any campaign work | [Artifacts](references/runtime/artifacts.md) |
| Check access, account, Page or Egbe team prerequisites | [Readiness](references/workflows/readiness.md) |
| Resolve planned targeting and assemble creatives | [Targeting and creative assembly](references/workflows/targeting-and-creative.md) |
| Build non-serving objects, upload images or recover a partial build | [Build without delivery](references/workflows/build-paused.md) |
| Authorize delivery or stop it | [Launch and pause](references/workflows/launch-and-pause.md) |
| Read delivery/results or change campaign settings | [Reporting and changes](references/workflows/monitoring.md) |
| Add optional browser/server conversions and inspect attribution | [Conversions](references/workflows/conversions.md) |
| Request bodies, units, controls and errors | [API reference](references/runtime/api-reference.md) |

## Operating boundaries

- Resolve existing campaign IDs before writing. OS creates groups, campaigns
  and creatives DRAFT (non-serving). Activate only with
  founder authorization or an applicable product marketing policy. An audit or
  a request to edit text does not authorize launch, a larger budget or a new campaign.
- Use the configured account and its linked organization Page. Do not substitute
  the Page associated with a developer app or publish an organic post as a fallback.
- Single Image uses Direct Sponsored Content (not the organic feed). Text Ads use
  their separate creative format. These require separate native campaigns.
- Preserve the approved destination, offer, targeting, budget and exact UTM URL.
  Provider minimums are discovered through pricing/creation; do not increase an
  approved budget automatically to meet them.
- Persist operation keys before mutations. An ambiguous result is not a failed
  create: reuse the same request/key and read back. Never use a new key to bypass
  an uncertain operation or exhausted quota.
- Separate configuration, moderation, delivery, product outcomes and attribution.
  ACTIVE does not prove impressions; account access does not prove Page posting
  permission; an empty report does not prove zero spend.
- These API operations do not install recurring jobs. Read access alone does not
  authorize campaign changes.

Return the campaign folder/IDs, actual changes, observed state/time, unresolved
operations and recovery instructions. Do not commit/push artifacts solely because the skill ran.

## Scope

First release: USD daily budgets, manual CPC, website visits, Single Image and
Text Ads, native targeting, campaign controls, reporting and actual-spend sync.
Optional Insight Tag/CAPI rules, explicit campaign associations, runtime events
and per-rule reports use the conversions workflow. They do not change manual
CPC, budgets or delivery status and are not prerequisites for an authorized
traffic campaign. Runtime event delivery/readback accepts scope `analytics`;
management requires `ads`. No raw passthrough, audience uploads, organic
publishing, automatic conversions or conversion bidding.
