---
name: egbe-os-product-auth
description: Build or repair accounts, sessions, protected routes and navigation, preserving existing work across account entry.
metadata:
  egbe-when: "Use when features need accounts; offer when authentication gaps interrupt the customer journey."
  egbe-visible: "true"
  egbe-title: "Customer accounts"
  egbe-description: "Add signup, login, secure sessions and protected pages, while keeping a customer's progress through sign-in."
  egbe-category: "Payments & accounts"
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


# Product Auth

Build authentication as part of the existing product experience, not as an
isolated pair of forms.

Before planning changes, inspect the repository `AGENTS.md`. When it contains
`EGBE:PRODUCT-FOUNDATION`, the canonical Postgres pool, migrations, durable
users/sessions storage, server-only session primitives, protected-route helper,
and private validation-session helper are scaffold-owned and already present.
Reuse them. Build only the selected account-entry integrations, account UX,
navigation, continuation, and concrete product bindings;
do not copy, replace, or create a parallel DB/session core.

For a new custom Node/Postgres integration,
[Product Build's foundations](../egbe-os-product-build/references/foundations.md)
describe the optional `--auth-db` installer for the
same shipped schema, migrations and private validation-session helper without
Next.js modules. Its `EGBE:AUTH-DATABASE` marker identifies only those database
assets; the application still owns its request-time session and account-entry
implementation. Preserve a working library's own schema/migration system.

## Core Workflow

For every egbe-os-product-auth implementation, read all of these references before changing code:

1. [references/workflows/build-auth.md](references/workflows/build-auth.md)
2. [references/contracts/live-auth-interface.md](references/contracts/live-auth-interface.md)
3. [references/security/session-and-credentials.md](references/security/session-and-credentials.md)
4. [references/ux/auth-experience.md](references/ux/auth-experience.md)

For a Next.js product, also read
[references/frameworks/nextjs.md](references/frameworks/nextjs.md). For another
stack, apply the same live and security contracts using its established server
and routing patterns.

Implement the methods selected in the existing requirements or task. Preserve a
suitable working method; a bounded repair does not add providers or redesign
account entry. If a material access decision is missing, explain the gap and
propose a suitable option with its reason before dependent implementation. This
technical workflow does not require a new plan or a playbook review.

- When Google is selected, follow
  [references/workflows/google.md](references/workflows/google.md).
- When email sign-in links are selected, follow
  [references/workflows/passwordless-email.md](references/workflows/passwordless-email.md).
- For email/password, use the shared credential and session contract below.

Read [references/workflows/account-recovery.md](references/workflows/account-recovery.md)
only when password recovery or separate email verification is required.

## Sources Of Truth

- Use the Egbe OS `egbe-os-deploy` skill for attached Postgres and deployment.
- Use the live Egbe OS `auth` capability skill for Google identity. Products
  keep no Google client secret and browser code never receives `OS_API_KEY`.
- Use the Egbe OS `egbe-os-mail` skill for email delivery when the selected auth flow
  actually requires email.
- Use the Egbe OS `egbe-os-analytics` skill for canonical event names and delivery.
  Do not define or emit signup event catalogs in this skill.
- Reuse a maintained auth library already present when it supports the local
  account/session contract. Never replace an explicitly selected or suitable
  working method merely because another is easier to implement or verify.

## Completion

For a full implementation, verify every selected method on the live product:
fresh account entry, repeat login to the same local account, applicable identity
linking, authenticated continuation, refresh, signed-in navigation, logout and
protected-route denial. A bounded repair verifies the affected method and shared
dependencies it can change; it does not expand the account-entry set. Email-link
proof requires receipt and use of the actual live message. One working method
does not complete a full implementation with another agreed method still broken;
do not silently remove that method from scope. Source inspection, provider
acceptance and redirect-only forms are not account-entry proof.

If a required identity, consent or live check needs the founder, keep Auth
incomplete and use EGBE's “Resume unfinished work” guidance. Record the exact
pending check and how
to resume in existing working notes; give the founder the safe product location
and one clear next action. A deferral does not complete the pending proof, and a
later "done" still requires live verification.

After that real account-entry proof, prepare the workflow's private reusable
validation identity when dependent Product or Billing work needs it, through the
product's authoritative server-side session mechanism. This is authenticated
setup, not proof of Auth behavior and never a public test-login path.
