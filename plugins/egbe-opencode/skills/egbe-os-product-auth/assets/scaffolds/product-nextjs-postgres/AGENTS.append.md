# Product foundation

This repository includes the Postgres account/session foundation.

- Reuse `db/migrations/0001_auth.sql`, `db/migrations/0002_auth_identities.sql`, `db/migrate.mjs`, and `src/lib/egbe-product/*`; do not replace, relocate, or duplicate them.
- Add product-specific migrations after `0002_auth_identities.sql`. Do not edit either shipped migration.
- Implement the selected account-entry methods and applicable recovery behavior and auth UX on the provided users, identities, sessions, and server-only helpers. Use Egbe OS when Google is selected; the foundation does not require Google or an additional email method.
- Keep the cookie name `egbe_session` and SHA-256 token lookup so the private validation-session helper and the real request path share one contract.
- `npm start` applies migrations before the Next.js runtime starts. Never run migrations from a public route.
