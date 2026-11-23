---
name: egbe-os-product-build
description: Plan and implement product changes, integrations and repairs with direct verification of the accepted behavior.
metadata:
  egbe-when: "Use when product requirements need an engineering plan, implementation or repair."
  egbe-visible: "true"
  egbe-title: "Product development"
  egbe-description: "Build and improve your product using Egbe infrastructure, with working integrations and verified customer journeys."
  egbe-category: "Development & hosting"
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


# Product build

Implement the requested behavior in the product's repository. Read the accepted
requirements or bounded task, relevant design, existing code and prior evidence.
Preserve recorded choices and the assigned scope; a missing product decision is
not permission to invent one. A narrow repair needs no complete PRD or new app.

## Plan, implement and verify

- Read [engineering planning](references/engineering.md) before choosing the
  implementation. It covers requirements, state, dependencies and failure boundaries.
- Follow [execution and verification](references/execution.md) for implementation,
  regression checks, saved work, release and resumable progress.
- For platform integrations, read [capability discovery](references/capabilities.md)
  and the relevant current domain contract before selecting an approach.
- For a compatible application foundation, read [shipped foundations](references/foundations.md).
  The optional local helper previews and installs the existing Next.js, account/session
  and subscription pieces without choosing the stack or commercial model for you.
  Without a terminal, Egbe runs the same installation into a Git commit session.
- For a user-facing interface, use [interface quality](references/interface-quality.md).
- For review that must remain usable after handoff, use
  [private review](references/workflows/private-review-handoff.md).

Use an existing work plan or `egbe-docs/development/<work-id>/` for the concrete
plan, TODOs and evidence. Keep accepted requirements in their existing product
documents; do not create a second definition or mandatory structured plan.
Update progress as work is proved and preserve open decisions/checks for resumption.

## Domain capabilities

Use only what the accepted behavior requires; these are not sequential stages.

| Work | Capability |
| --- | --- |
| New application foundation or main page | `egbe-os-design-landing-page`: its application-preparation reference; preserve an existing application |
| Accounts, sessions, protected access | `egbe-os-product-auth` |
| Purchases, subscriptions, payment state | `egbe-os-payments`: select the workflow matching the accepted model |
| Outcome and payment measurement | `egbe-os-analytics`: activation-tracking or payment-lifecycle-tracking as applicable |
| Storage, generated output and other integrations | Discover DB, LLM, images or other capabilities through OS |
| Source control and serving release | `egbe-os-git`, `egbe-os-deploy` within the authorized publication scope |

Read accepted product decisions by meaning, not a prescribed PRD heading. Account
entry, a public preview and payment are independent choices, not universal gates.
Do not recreate missing planning artifacts merely to satisfy a capability's example.
Keep the real producer, consumer and integration proof connected across domain work.

## Scripts and templates from Egbe

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project folder set up for Egbe;
without one, tell the founder that the step needs it and continue with the rest
of the work.

In a set-up project folder, before a step that runs or copies one of them, get
this skill's whole bundle into `.egbe/skills/egbe-os-product-build/` as
`egbe_workspace_files(group="scripts")` describes: write that group's files,
which include Egbe's request helper, then download this skill's listed archive,
check its SHA-256 and extract it. Never download single files: scripts import
their sibling files and some use other skills' bundles, which come the same way.
When the `scripts` release changes, refresh the bundles already there.

Wherever this skill names a file by its path in the skill (for example `scripts/...`
or `assets/...`), use `.egbe/skills/egbe-os-product-build/<file>`; where it writes `<skills-directory>`, use
`.egbe/skills`. Run scripts from the project root with
`OS_AGENT_NAME="<your agent name>"` set inline. Where this skill says a script needs
`OS_URL` or `OS_API_KEY` in its environment, start it as
`python3 .egbe/skills/egbe-os-quickstart/scripts/egbe-curl.py --egbe-run <command>`, which loads `.env.local` without
executing it. Keep `.egbe/skills/` out of Git.

Files in the bundle that this plugin leaves out:

- `scripts/scaffold.py`
