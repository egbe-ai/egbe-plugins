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
This skill was delivered through the Egbe MCP connection. Make every Egbe API
call it describes with the `egbe_request` tool: pass the HTTP method, the API
path (for example `/me/limits`), query parameters in `query` and the JSON body
in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Read a referenced file with
`egbe_skill(name=<skill>, resource=<relative path>)`.

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs the standard workspace setup. In a persistent
project workspace that is not set up yet, call `egbe_local_setup` and follow it.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


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
| Outcome and payment measurement | `egbe-os-analytics`: activation-tracking or payment-tracking as applicable |
| Storage, generated output and other integrations | Discover DB, LLM, images or other capabilities through OS |
| Source control and serving release | `egbe-os-git`, `egbe-os-deploy` within the authorized publication scope |

Read accepted product decisions by meaning, not a prescribed PRD heading. Account
entry, a public preview and payment are independent choices, not universal gates.
Do not recreate missing planning artifacts merely to satisfy a capability's example.
Keep the real producer, consumer and integration proof connected across domain work.
