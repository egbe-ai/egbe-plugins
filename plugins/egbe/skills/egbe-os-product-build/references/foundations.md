# Reuse shipped product foundations

Inspect the existing application and accepted behavior first. These optional
foundations fit the bundled Next.js/Postgres stack; another stack or working
integration should keep its established implementation. Installing code does
not select an offer, account-entry method or commercial model.

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
| `--accounts` | Product Auth's Postgres schema, migrations, server account/session helpers and validation-session helper | Selected account-entry/recovery UX, real attached database and protected product paths |
| `--subscriptions` | Payments' subscription foundation plus its required account foundation | Accepted plan catalog, real provider bindings, account-entry, product entitlements, navigation and verification |

For a compatible new app requiring subscriptions, preview with
`plan --target <product-directory> --nextjs --subscriptions`. For a compatible
existing Next.js app, omit `--nextjs` and select only the absent foundation.
The subscription foundation is **not** a one-time purchase engine: use Payments'
one-time-purchase workflow for that offer instead. A stateless product need not
add accounts or payments.

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

Use the project's package manager to refresh its lockfile after dependency
changes (`npm install --include=dev` for the bundled npm starter). The helper
does not install packages, migrate a database, create provider objects, deploy
or verify an integration. Read the selected Auth/Payments contract, implement
the accepted behavior and verify the resulting customer journey before publishing.
