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
