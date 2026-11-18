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

## Files downloaded on demand

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project workspace; without one,
tell the founder that the step needs it and continue with the rest of the work.

In a project workspace, before a step that runs or copies one of these files,
download it into `.egbe/skills/egbe-os-product-auth/` at the same relative path, for example
`curl -fsSL <url> --create-dirs -o .egbe/skills/egbe-os-product-auth/<file>`, and check that its SHA-256
matches. Also download the files it uses from the same folder, such as the
modules a script imports. Wherever this skill names one of these files by its
path in the skill (for example `scripts/...` or `assets/...`), use `.egbe/skills/egbe-os-product-auth/<file>`;
where it writes `<skills-directory>`, use `.egbe/skills`.
Keep `.egbe/skills/` out of Git by adding it to `.gitignore`.

| File | URL | SHA-256 |
| --- | --- | --- |
| `assets/db/create-validation-session.mjs` | https://os.hz.egbe.dev/skills/egbe-os-product-auth/resources/assets/db/create-validation-session.mjs | `e94daef5a173dfa9b3628356bbd87562ea1fbca9681038ae0fe22de1483ef208` |
| `assets/db/migrate.mjs` | https://os.hz.egbe.dev/skills/egbe-os-product-auth/resources/assets/db/migrate.mjs | `734b0a11a408cc2af77992227abd81d90471ce4db538dd6a6c4867348ca10546` |
| `assets/db/migrations/0001_auth.sql` | https://os.hz.egbe.dev/skills/egbe-os-product-auth/resources/assets/db/migrations/0001_auth.sql | `986185d1424f1e2f0ee7f94ef9d4357b82275f8f105869ce908b40f50489aacf` |
| `assets/db/migrations/0002_auth_identities.sql` | https://os.hz.egbe.dev/skills/egbe-os-product-auth/resources/assets/db/migrations/0002_auth_identities.sql | `1789beda746f9c6285f636da4b1d80579254e7c12651295a39cecfd31898b1d6` |
| `assets/scaffolds/product-nextjs-postgres/src/lib/egbe-product/db.ts` | https://os.hz.egbe.dev/skills/egbe-os-product-auth/resources/assets/scaffolds/product-nextjs-postgres/src/lib/egbe-product/db.ts | `9f4be1466a9255fde9db113123d51913d548903358e41dc5cfe088c4b42a5ad3` |
| `assets/scaffolds/product-nextjs-postgres/src/lib/egbe-product/identity.ts` | https://os.hz.egbe.dev/skills/egbe-os-product-auth/resources/assets/scaffolds/product-nextjs-postgres/src/lib/egbe-product/identity.ts | `0c91ee41810320951a471d07b4e98f254699fa84aa692a3b26ea12a64ee3eec7` |
| `assets/scaffolds/product-nextjs-postgres/src/lib/egbe-product/index.ts` | https://os.hz.egbe.dev/skills/egbe-os-product-auth/resources/assets/scaffolds/product-nextjs-postgres/src/lib/egbe-product/index.ts | `9041be89265812c2004f5dc32c9456306210ffe3a7264bf37be119b6619b13e5` |
| `assets/scaffolds/product-nextjs-postgres/src/lib/egbe-product/session.ts` | https://os.hz.egbe.dev/skills/egbe-os-product-auth/resources/assets/scaffolds/product-nextjs-postgres/src/lib/egbe-product/session.ts | `085e1fa871b94568bc5a844b305a915829c885a51617ffc62063e7eedfb16cc3` |
