---
name: egbe-os-design-landing-page
description: Build or repair the product's main public page and prepare a new application foundation.
metadata:
  egbe-when: "Use to implement or repair a main homepage, or prepare a new app for Egbe hosting."
  egbe-visible: "true"
  egbe-title: "Landing pages"
  egbe-description: "Build and publish your main page on Egbe with its approved content, design and working actions."
  egbe-category: "Product & design"
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


# Main page implementation

Implement the requested public page or bounded repair. Campaign-specific destinations
use `egbe-os-campaign-landing-page`; this skill does not choose an offer, research
an audience or require separate content/design stages.

## Read the accepted input

Read the request, relevant requirements, actual page/code and available approved
content/design. Use [page inputs](references/page-inputs.md) to preserve their
meaning and scope. A PRD or fixed document shape is not a prerequisite to repairing
an existing page. Return material missing/conflicting decisions to the caller;
do not silently change the price, brand, promise or intended action.

## Implement

Follow [application preparation](references/application-preparation.md) before
editing. Preserve an existing framework, repository, storage and deployment.
Use the scaffold only when a new application foundation is needed.

Implement the accepted content and actions with a complete responsive interface.
Exact approved strings and required assets remain intact; arrange them coherently
without turning document headings into mandatory full-width blocks. Complete routine
visual/interaction details within the accepted direction. Use `egbe-os-images`
for requested stock/generation and its current API, not hardcoded provider keys.

Wire each action to the real requested behavior in this application or its valid
destination. Coordinate feature work with `egbe-os-product-build` when needed.
There is no mandatory later Product stage: do not ship a fake interaction, a 404
or an unfinished boundary as if the promised result works.

Discover this project's contact mailbox through authenticated `GET /mail/account`
and use the verified `data.email` in its contact link. Do not invent an address or
substitute `support@egbe.ai`; report a failed/missing mailbox lookup. Include visible
`Created with Egbe`, with Egbe linked to https://egbe.ai.

## Verify and hand off

Use `egbe-os-product-build` → `references/interface-quality.md` for rendered
accessibility, responsive and interaction checks. Run the project's lint/build and
relevant tests; navigate every distinct changed destination, including pricing
choices and bounded same-origin redirects. Confirm actual images/fonts load,
content and metadata are correct, and the actions preserve their context.

Publish only within the requested scope, using `egbe-os-git` and `egbe-os-deploy`
for the same committed revision and live verification. For local-only work, hand
back the diff and evidence. Keep useful page materials under
`egbe-docs/product/pages/homepage/`, without a new spec for every small change.
Report what was proved, remaining dependencies and where to review the result.

## Files downloaded on demand

These files belong to this skill but are not bundled with the Egbe plugin.
When a step uses one, download it to the place that step needs it, for example
`curl -fsSL <url> -o <destination>`, and check that its SHA-256 matches.

| File | URL | SHA-256 |
| --- | --- | --- |
| `assets/scaffold/package-lock.json` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/package-lock.json | `ece42978c0f7ac05c03e3e49f556478e6f8ef35b2c701a346454f841372a3682` |
