# Baseline auth schema (canonical fixture)

Shipped inside the `egbe-os-product-auth` skill bundle. The `build-auth` workflow (§3
"Prepare Durable State") applies this as the **starting point** for durable auth
state, so the canonical users, sessions, and provider bindings are never
re-derived by hand on every product. The agent adds only product-specific
columns/tables on top.

Use this for the **custom Node/Postgres path** — selected provider, email/password
or passwordless methods implemented against attached Postgres with `pg` and raw
SQL. If the product adopts an ORM or auth library with its own migration ledger (Prisma,
Drizzle, a batteries-included auth lib), do **not** apply this raw SQL — it would
drift against the ORM's migration table. Instead create the same users,
sessions, and unique provider-subject binding via that library's migration
mechanism. See build-auth.md §3 for the branch.

## Files
- `migrations/0001_auth.sql` — the universal user/session tables. Idempotent.
- `migrations/0002_auth_identities.sql` — provider-subject links used by Google
  and future verified identity providers. Idempotent.
- `migrate.mjs` — concurrency-safe runner (advisory-locked). Applies each SQL
  file once, tracked in a `schema_migrations` table. Only dep is `pg`.
- `create-validation-session.mjs` — creates or reuses one private, short-lived
  validation identity after the real account-entry journey has been proven.
  It can load the resulting cookie into an isolated `agent-browser` session so
  later Product and Billing work can start from authenticated state without
  replaying account entry.

## Tables

`users(id uuid pk, email text, password_hash text null, created_at, updated_at)`
- Uniqueness is enforced on `lower(email)` (case-insensitive). Insert the email
  as typed; the index normalizes. Return one generic invalid-credentials
  response for both unknown email and wrong password.
- `password_hash` is nullable so OAuth/passwordless identities can be added
  later. For email/password, set it with Argon2id / scrypt / bcrypt (see the
  `session-and-credentials` contract). For passwordless email, leave it null;
  never fill it with a random placeholder merely to imitate password auth.

`sessions(id uuid pk, user_id uuid fk, token_hash text, expires_at, created_at, revoked_at null)`
- Store a **hash** of the opaque, cryptographically-random session token in
  `token_hash`, never the token itself.
- In a new custom Node/Postgres profile, the default token lookup is SHA-256
  hexadecimal in `sessions.token_hash` and the default cookie name is
  `egbe_session`. The product's normal request-time session resolver and the
  validation helper must use the same token and cookie contract.
- When an existing working resolver already uses the same authoritative
  `users`/`sessions` state and SHA-256 token lookup under another valid cookie
  name, preserve that cookie name. Pass it to the helper with `--cookie-name`;
  do not rename a working product session solely to fit the fixture default.
- Revoke by setting `revoked_at`. Check expiry AND `revoked_at is null` on every
  protected request. On logout, revoke the server record before clearing the
  cookie.

`auth_identities(id uuid pk, user_id uuid fk, provider, subject, email_at_link, created_at, updated_at)`
- `(provider, subject)` is unique and authoritative. Email is verified linking
  context and may change at the provider.
- A verified provider email may link an existing local user. Never erase that
  user's password or passwordless state when adding a provider identity.

## Running
Run during a controlled build/deploy step (never a public route). Requires
`DATABASE_URL`; safe to run repeatedly and concurrently:

```bash
node db/migrate.mjs        # or wire it as: npm run db:migrate
```

After the Auth section has proved real account entry, create or reuse the
private validation identity for dependent Product or Billing work. Set
`PRIVATE_STATE_DIR` to a private directory outside the product repository and
shared reports (for a new validation run, `mktemp -d` creates one):

```bash
node db/create-validation-session.mjs \
  --origin "$APP_URL" \
  --state "${PRIVATE_STATE_DIR}/${APP_SLUG}.json" \
  --browser-session "validation-${APP_SLUG}"
```

For an existing compatible resolver whose real cookie is, for example,
`wp_session`, add `--cookie-name "wp_session"`. Omit the flag for a new product
using the `egbe_session` default. Always take the value from the real
request-time resolver; never guess a cookie name from this documentation.

The helper requires `DATABASE_URL`. Its state file contains the only raw token,
is written with mode `0600`, and must stay outside the product repository and
shared reports. The database receives only the token hash. The helper prints
only non-secret status and may be run again to reuse an unexpired, unrevoked
session.

This identity is setup for verifying authenticated Product and Billing
behavior. It is not evidence that signup, login, email delivery, credential
exchange, logout, or recovery works. Those remain Auth-owned live proofs. Do
not expose a public validation login route or add a runtime bypass.

## Extending
Add later migrations as `migrations/000N_<name>.sql` — the runner applies new
files in order, once each. Product-specific columns/tables (e.g. an ownership
link that preserves a pre-signup result, or profile fields) go in such a later
migration. Do **not** edit `0001_auth.sql` or `0002_auth_identities.sql` after
they have shipped.
