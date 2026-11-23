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

The harness can also refuse a step before Egbe answers: a denied file read or
command (`EPERM`, `operation not permitted`), a certificate error, or a connector
call that fails as a whole with HTTP 403. Egbe's own refusals of an API request
come back as a result with a `status` and Egbe's `message`, and the `egbe_skill`
tool never answers 403. Egbe refuses a whole call with 403 only for a browser
`Origin` it does not accept, so such a 403 most likely comes from the harness, a
proxy or a policy in front of Egbe. Don't retry it in a loop, route around it or
disable certificate verification. If `egbe_skill` was refused, read that skill
from an installed Egbe catalog or plugin copy, if this session has one. Name the
blocked file, command, host or tool and ask the founder to allow it, or to trust
the host through the environment's network setting. Then continue the work that
doesn't need it and say what waits on that permission. While `egbe_skill` works,
`egbe-os-quickstart`'s `references/environment.md` lists these cases.


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

## Scripts and templates from Egbe

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project folder set up for Egbe;
without one, tell the founder that the step needs it and continue with the rest
of the work.

In a set-up project folder, before a step that runs or copies one of them, get
this skill's whole bundle into `.egbe/skills/egbe-os-design-landing-page/` as
`egbe_workspace_files(group="scripts")` describes: write that group's files,
which include Egbe's request helper, then download this skill's listed archive,
check its SHA-256 and extract it. Never download single files: scripts import
their sibling files and some use other skills' bundles, which come the same way.
When the `scripts` release changes, refresh the bundles already there.

Wherever this skill names a file by its path in the skill (for example `scripts/...`
or `assets/...`), use `.egbe/skills/egbe-os-design-landing-page/<file>`; where it writes `<skills-directory>`, use
`.egbe/skills`. Run scripts from the project root with
`OS_AGENT_NAME="<your agent name>"` set inline. Where this skill says a script needs
`OS_URL` or `OS_API_KEY` in its environment, start it as
`python3 .egbe/skills/egbe-os-quickstart/scripts/egbe-curl.py --egbe-run <command>`, which loads `.env.local` without
executing it. Keep `.egbe/skills/` out of Git.

Files in the bundle that this plugin leaves out:

- `assets/lockfiles/accounts/package-lock.json`
- `assets/lockfiles/auth-db/package-lock.json`
- `assets/scaffold/.dockerignore`
- `assets/scaffold/.gitignore`
- `assets/scaffold/Dockerfile`
- `assets/scaffold/eslint.config.mjs`
- `assets/scaffold/next.config.ts`
- `assets/scaffold/package-lock.json`
- `assets/scaffold/package.json`
- `assets/scaffold/postcss.config.mjs`
- `assets/scaffold/public/.gitkeep`
- `assets/scaffold/sentry.edge.config.ts`
- `assets/scaffold/sentry.server.config.ts`
- `assets/scaffold/src/app/global-error.tsx`
- `assets/scaffold/src/app/globals.css`
- `assets/scaffold/src/app/layout.tsx`
- `assets/scaffold/src/app/page.tsx`
- `assets/scaffold/src/app/privacy/page.tsx`
- `assets/scaffold/src/components/egbe-analytics.tsx`
- `assets/scaffold/src/instrumentation-client.ts`
- `assets/scaffold/src/instrumentation.ts`
- `assets/scaffold/src/lib/egbe-observability.generated.ts`
- `assets/scaffold/src/lib/utils.ts`
