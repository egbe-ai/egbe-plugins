# Build Core Product Authentication

## 1. Inspect Before Editing

Work in the existing product repository. Identify:

- deployed slug and live host;
- accepted access requirements and any applicable PRD, design or page material;
- framework, server runtime, data access, migrations, and shared layouts;
- the approved value path, its access prerequisites and any public preview;
- existing signup/login/session code;
- the first useful protected route that exists now.

Reuse established libraries and component patterns when they meet the contracts.
Do not create a second app, auth store, header, or routing system.

The accepted value path and public-preview presentation are inputs to Auth,
not decisions to reinvent here. Preserve
existing work and its continuation across account entry; do not invent a preview.
Limit changes to authentication and its minimal protected continuation; do not
implement monitoring, analytics, or Billing behavior.

## 2. Confirm the selected account-entry paths and scope

Use the methods selected in the requirements or current task, preserving suitable
working authentication. A repair stays within the affected method and its shared
dependencies; it does not require a second login method. If a material choice is
missing, propose an option with its reason and resolve it before dependent work.

For Google, follow `references/workflows/google.md`: the product backend uses
the live Egbe OS auth capability and normal product-scoped OS credential, never
its own Google credentials. For email sign-in links, follow
`references/workflows/passwordless-email.md`. For email/password, use the shared
credential contract and the same opaque server-side sessions. Do not substitute
waitlist capture, localStorage, hardcoded users or an in-memory demo session for
authentication, or implement an unselected login method for verification.

For a new full implementation, resolve how the user returns to the account and
recovers access within the selected authorization and requirements. A missing
safe return/recovery path is an unresolved gap, not a reason to silently add
email/password or email reset. Use `account-recovery.md` only when password
recovery or separate email verification is part of that solution.

## 3. Prepare Durable State

Read the live Egbe OS `egbe-os-deploy` skill. Provision or reuse attached Postgres and
use the injected `DATABASE_URL`.

For a compatible Next.js/custom-Postgres application without an established auth
implementation, Product Build's `references/foundations.md` exposes the shipped
account/session server helpers and canonical migrations through the optional
local scaffold helper's `--accounts` selection. Preview before applying. It does
not choose or implement account-entry methods; continue with this workflow.

**Start from the canonical auth schema — do not re-derive users, sessions, or
provider bindings by hand.** This skill bundle ships it at `assets/db/`
(`migrations/0001_auth.sql`, `migrations/0002_auth_identities.sql`, and
`migrate.mjs`; see `assets/db/README.md`). It provides the universal user and
session state plus the `(provider, subject)` external-identity authority. Apply
it as the starting point:

- **Default custom Node/Postgres path** (the common case — this product talks to
  Postgres with `pg` and raw SQL): copy `assets/db/` into the product repo as
  `db/`, add `"db:migrate": "node db/migrate.mjs"` to `package.json`, and run it
  against `DATABASE_URL` during a controlled build/deploy step. Then add only the
  product-specific extras below as a *new* migration after `0002`; never edit
  the canonical migrations. Use the baseline's SHA-256 token hash in the
  product's normal request-time session resolver. A
  new product defaults to the `egbe_session` cookie. When an existing working
  resolver uses the same authoritative session state and hash contract under
  another valid cookie name, preserve it and pass that name to the bundled
  private validation helper with `--cookie-name`; never rename a working
  session solely to fit the fixture default.
- **ORM / auth-library path** (Prisma, Drizzle, a batteries-included auth lib
  with its own migration ledger): do **not** apply the raw SQL — it would drift
  against the ORM's migration table. Instead reproduce the same users,
  sessions, and unique provider-subject binding from `assets/db/README.md`
  using that library's migration mechanism, then add only the extras below.

In both cases, add only any minimal product-owned link needed to preserve a
pre-signup result. Reuse the canonical external identity contract rather than
creating another provider-binding table.

For email/password, store a maintained password hash. For passwordless email,
leave `password_hash` null and add the minimal hashed one-time-token state as a
later migration. Never generate a fake password or placeholder hash merely to
fill the nullable column.

Use the product's existing migration/data layer. Run migrations at a controlled
build/deploy step, never a public initialization route, and do not commit
connection strings.

## 4. Implement The Server Contract

Implement account entry, session lookup, logout, and protected-route checks as
one coherent server-side system. Follow
[../security/session-and-credentials.md](../security/session-and-credentials.md).

Each account-entry path must converge on the same durable user and session
authority. When Google is selected, it creates a fresh product session only
after the one-time Egbe identity exchange and transactional provider link succeed.
Logout must revoke the server session and clear the browser cookie. Protected
routes must authorize from server state on every request.

Choose the server transport before building the forms and keep it consistent.
For a JavaScript-enhanced UI, expose the actual same-origin signup, login, and
logout endpoints through the live auth interface attributes. This is a stable
machine interface to the production auth path, not a second implementation.

Keep any selected email entry deliberately narrow: email plus password for
the password profile, or email alone for passwordless email. Google may supply
verified name/picture but must not force new signup fields. Do not collect
company, username, password confirmation, or other profile data in this
workflow. Hidden CSRF, attribution, and safe continuation fields are allowed.

Keep return destinations same-origin and relative. Preserve a valid intended
destination through signup/login without putting identity or credentials in the
URL.

## 5. Build The Product Experience

Follow [../ux/auth-experience.md](../ux/auth-experience.md) and
[../contracts/live-auth-interface.md](../contracts/live-auth-interface.md).

Provide canonical `/signup` and `/login` entry routes for new products. Add one
real protected continuation route. Preserve an existing useful route when one
already exists. If the real destination is not implemented yet, a minimal
protected verification surface can prove the auth mechanism, but is not a
completed product journey. Do not introduce a dashboard or placeholder feature
controls merely to satisfy a stage; connect the accepted destination when ready.

Make the shared landing navigation auth-aware. Signed-out users see login and
the normal product CTA. Signed-in users see identity, a valid continue action,
and logout in a user menu. Preserve the existing visual system and mobile nav.

If the current product already lets a visitor reach first value before signup,
associate that exact result with the account and continue it after signup. Do
not erase or regenerate it, and do not create the first-value flow in this
workflow.

When the real pre-signup result exists, verify that exact result survives
account entry. Otherwise verify the safe continuation mechanism and record
the missing integration check. Exercise the real producer and Auth together
once both exist; a placeholder result cannot prove this boundary.

## 6. Deploy And Verify

When release is authorized, follow Egbe Git and Deploy for the committed
revision and verify on the returned live host. For local-only work, run the
applicable local checks and leave live account-entry proof explicitly pending.
For a full implementation, verify every selected method; for a bounded repair,
verify the affected method and shared dependencies touched by the change:

1. signed-out entry exposes the selected account-entry controls;
2. fresh account entry and protected continuation;
3. session persistence after reload and signed-in navigation;
4. logout and denial of the protected route;
5. repeat login to the same local account and applicable identity linking;
6. durable return access, the selected recovery behavior and safe continuation
   restoration, including the exact Product result only when it already exists
   within the implementation being verified.

When Google is in scope, its workflow includes verified-email linking to existing
accounts, including imported accounts without another login method. Email-link
verification includes receiving and using the actual live message.

Before deploying, confirm that each JavaScript-only auth control identifies its
real action and encoding as defined by the live auth interface contract. Native
POST forms need no extra action metadata.

Exercise rendered protected mutations through the browser with the deployed
headers and session cookies, including logout and applicable closed or invalid
states. Keep financial and communication checks non-charging and non-sending.
Endpoint probes with manually supplied headers can support security checks but
do not prove that the rendered form or control works. Preserve server-side
request protection when correcting a browser failure.

Use one private verification identity for this sequence and reuse it when a
check is repeated. Do not manufacture another account for every retry, and do
not write its password, access link, or token to the product repository or
shared reports. Reusing an identity means exercising current account-entry,
session, protected-route, and logout behavior; a saved prior success is not
current evidence. If a failed first entry is proven to have created the account
before failing later in the flow, a verifier may rotate to one strictly bounded
recovery identity instead of creating a new account on every retry.

Treat a redirect without authenticated state as failure. An unavailable agreed
method leaves a full implementation incomplete even when another method works;
do not silently remove it from the agreed scope.

Only after this real Auth proof succeeds, prepare one reusable private
validation identity when later Product or Billing work needs it. On the default
custom Node/Postgres path, run the bundled
`db/create-validation-session.mjs` as documented in `assets/db/README.md` and
load its cookie into an isolated browser session. On an ORM or maintained auth
library path, use its equivalent server-side user/session creation primitive
with the same properties: a unique validation user, short-lived revocable
session, raw credential kept only in private mode-`0600` state, and no public
route or bypass. This setup lets dependent sections exercise authenticated
behavior without replaying account entry. It never replaces the Auth proof
above.

When an authorized reviewer will continue after this section finishes, preserve
the minimum private validation access through the agreed review window and
record expiry/cleanup in the existing handoff. Confirm that the recipient's
supported tools can actually use the access; a private token file alone is not
interactive browser access. Keep ordinary account-entry proof and any pending
credential or consent action explicit. Do not broaden access or prolong a
session beyond the caller's authorized window.
