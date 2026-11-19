# Reuse shipped product foundations

Inspect the existing application and accepted behavior first. These optional
application and account/session foundations fit the bundled Next.js/Postgres
stack. The shared auth database assets also support custom Node/Postgres apps.
Another stack or working integration should keep its established implementation.
Installing code does not select an offer, account-entry method or commercial model.

The complete skill catalog includes a local helper at
`<skills-directory>/egbe-os-product-build/scripts/scaffold.py`. It locates sibling
bundles by their published names; no checkout, network call or credentials are
needed. Discover the choices and preview a compatible new application:

```bash
python3 <skills-directory>/egbe-os-product-build/scripts/scaffold.py list
python3 <skills-directory>/egbe-os-product-build/scripts/scaffold.py plan --target <product-directory> --nextjs
```

Select only the required pieces:

| Option | Installs | Still needs implementation/configuration |
| --- | --- | --- |
| `--nextjs` | Blank application from Design landing page | Product UI/behavior, real public observability bindings |
| `--auth-db` | Shared Node/Postgres auth schema, migration runner and private validation-session helper | Application's account-entry/session resolver, protected access, real attached database and controlled migration step; preserves framework/start command |
| `--accounts` | Product Auth's Postgres schema, migrations, server account/session helpers and validation-session helper | Selected account-entry/recovery UX, real attached database and protected product paths |
| `--subscriptions` | Payments' subscription foundation plus its required account foundation | Accepted plan catalog, real provider bindings, account-entry, product entitlements, navigation and verification |

For a compatible new app requiring subscriptions, preview with
`plan --target <product-directory> --nextjs --subscriptions`. For a compatible
existing Next.js app, omit `--nextjs` and select only the absent foundation.
The subscription foundation is **not** a one-time purchase engine: use Payments'
one-time-purchase workflow for that offer instead. A stateless product need not
add accounts or payments.

For a custom Node/Postgres app with a `package.json`, use
`plan --target <product-directory> --auth-db`. This reuses the existing raw-SQL
assets without installing Next.js modules or changing the app's start command.
It adds `pg`, `db:migrate` and `auth:validation-session`; it does not supply a
complete auth implementation. Preserve an established ORM/auth library's schema
and migration ledger instead of installing parallel raw-SQL tables. The full
`--accounts` and `--subscriptions` options include these same database assets.
Read the [shared auth database contract](../../egbe-os-product-auth/assets/db/README.md)
for the schema, session-token contract and private validation-session lifecycle.

Review the preview, then repeat the same arguments with `apply` instead of
`plan`. The helper merges required package entries, copies missing foundation
files and appends the installed foundation's marked ownership guidance to
`AGENTS.md`, preserving existing project guidance and credentials. The Next.js
starter appends its build/secret ignore rules to `.gitignore`, preserving existing
rules; review their order in the resulting file. Different
existing files, dependency versions, scripts or marked guidance stop the whole
plan before writes; resolve the integration deliberately rather than deleting
working code. Symlinks within the destination are rejected. Repeating the same
installation without intervening edits makes no changes. Edited foundations
remain a manual review, not an update/overwrite target.

## Without a terminal

Through the Egbe connector, or wherever the local helper cannot run, Egbe runs
the same helper against a repository. Open a commit session on the product's
repository and branch as `egbe-os-git` describes ("Without a terminal"), then:

```json
POST /git/commit-sessions/<session_id>/scaffold
{"foundations": ["nextjs", "subscriptions"], "directory": ""}
```

`foundations` takes the options above without dashes in front (`nextjs`,
`auth-db`, `accounts`, `subscriptions`); `directory` is the product's folder in
the repository (empty for its root). The plan is made against the session's base
commit and anything already staged in the session, with the same merging and
refusals as the local helper; a refusal (409) stages nothing. The result lists
`changes` (`path`, `action`, `size`); review them, then repeat the same request
with `"apply": true` to stage those files and commit the session with a message.
Repeating an installation that is already staged or committed returns no changes.

`lockfile_current: true` means the resulting `package-lock.json` lists the
package's dependencies, so the starter Dockerfile's `npm ci` works. `false`
means it does not, because the app's dependencies or lockfile differ from the
shipped ones; regenerate the lockfile with `npm install --include=dev` where
npm can run before deploying, or report that dependency as remaining work.

## After installation

Both paths keep an unedited shipped `package-lock.json` (the starter's or a
previous installation's) in step: when a foundation adds dependencies, they
install the matching prebuilt lockfile from Design landing page's
`assets/lockfiles/`. An edited lockfile is left as it is; then refresh it with
the project's package manager (`npm install --include=dev` for the bundled npm
starter), as after any other dependency change. The helper
does not install packages, migrate a database, create provider objects, deploy
or verify an integration. Read the selected Auth/Payments contract, implement
the accepted behavior and verify the resulting customer journey before publishing.
