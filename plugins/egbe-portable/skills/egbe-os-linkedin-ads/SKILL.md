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


# LinkedIn Ads

Use from any product repository with `OS_URL` and `OS_API_KEY` (scope `ads`).
No scaffold, instance layout or egbe-os-product-build stage is required. Provider
credentials stay inside Egbe OS; never request them for product code.

Same convention on every Egbe ads platform: `GET /ads/linkedin/campaigns/{id}` reads one
owned campaign, and `GET /ads/linkedin/campaigns/{id}/results?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`
reads an inclusive window. Dates are UTC; omit both for the last 30 days. Unknown query names fail 400 and list the accepted ones.

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
