# Auth database foundation

Reuse `db/migrations/0001_auth.sql`, `db/migrations/0002_auth_identities.sql`,
`db/migrate.mjs` and `db/create-validation-session.mjs`. Add product-specific
migrations after the shipped ones; do not edit or duplicate them.

These are the shared custom Node/Postgres database assets, not a complete auth
implementation. The application must implement the selected account-entry,
request-time session resolution, protected access, logout and recovery behavior
under the Product Auth contracts. Preserve an established auth library and its
own migration system instead of installing a parallel schema.

Run `npm run db:migrate` during a controlled build/deploy step with the attached
`DATABASE_URL`, never from a public route. The database-only installation does
not change the application's start command. Prepare private validation sessions
only after proving the real account-entry journey, matching the application's
cookie name and SHA-256 token lookup as described in `db/README.md`.
