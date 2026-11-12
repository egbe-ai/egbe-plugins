---
name: egbe-os-campaign-landing-page
description: Implement campaign destinations, attribution, lead capture and booking or product handoffs.
metadata:
  egbe-when: "Use when a campaign needs a working destination, lead form or attributed handoff."
  egbe-visible: "true"
  egbe-title: "Campaign landing pages"
  egbe-description: "Build campaign pages on Egbe with working requests, bookings and attribution to the visitor's source."
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


# Campaign page implementation

Implement the accepted page/test plan: content, audience, offer, variants, actions,
destinations and required measurement. Reuse actual product materials and existing
source. Missing material decisions go back to the caller; this capability does
not choose a new campaign strategy or require a fresh research pack.

The main homepage is `egbe-os-design-landing-page`. Provider campaign creation,
creative limits and spend controls belong to the selected channel skill; building
a page neither changes those objects nor authorizes traffic.

## Build the owned page

1. Inspect the accepted inputs, current route, storage and integration contracts.
   Preserve approved claims and design within their scope. Do not invent proof
   or render internal plan metadata as public copy.
2. Follow [OS wiring](references/os-wiring.md) for hosting, credentials, endpoints
   and analytics. Preserve existing app bindings rather than deploying a duplicate.
3. Implement [routing and attribution](references/routing.md) and the applicable
   [lead, booking or product handoff](references/leads-calendar-and-tracking.md).
   Use the accepted fields and behavior; a popup, extra qualification form or
   email sequence is not a universal requirement.
4. Use `egbe-os-product-build` → `references/interface-quality.md` for interface
   implementation and check [campaign QA](references/qa.md) for integration proof.
5. Publish through Git/Deploy only when requested. Report the page location,
   verified operations, remaining gaps and the exact serving revision if deployed.

Keep reusable page decisions/materials in `egbe-docs/product/pages/<page-id>/`
and technical evidence alongside the task. Credential-bearing captures are private.
Do not create inventory, facts, copy and per-round ledgers solely for this workflow.
