---
name: egbe-os-db
description: Query/export attached PostgreSQL data; update or delete individual rows by primary key.
metadata:
  egbe-when: "Use for inspecting, exporting or correcting stored product data."
  egbe-visible: "true"
  egbe-title: "Database access"
  egbe-description: "Inspect and correct your app's PostgreSQL data without redeploying your app."
  egbe-category: "Development & hosting"
---

<!-- egbe-mcp-connection:v1 -->
This skill comes with the Egbe plugin. Make every Egbe API call it describes with
the Egbe connector's `egbe_request` tool: pass the HTTP method, the API path (for
example `/me/limits`), query parameters in `query` and the JSON body in `body`.
For these calls leave out `OS_URL`, the Authorization header, `.env.local` and
`egbe-curl.py`, and skip catalog update checks; the connection authenticates and
identifies the request.
Also pass the `business` that `egbe_setup` returned. Files this skill refers to
are next to this `SKILL.md`, except any listed under "Files downloaded on demand".

A step that needs a local project key, such as a git push or a local deploy
command, works only in a persistent project workspace. There, if the project's
Git-ignored `.env.local` has no `OS_API_KEY` yet, call `egbe_local_setup` once
and save its `OS_URL` and `OS_API_KEY` there, preserving other entries. Use only
those two values: the plugin already provides Egbe's skills, so do not install
the Egbe catalog or follow the rest of that result. Never show the key in chat or
put it in logs, commits or URLs. Without such a workspace, tell the founder that
this step needs an agent with a project folder, and continue with the rest of
the work.


# Work with your database

Use the founder's existing `OS_API_KEY` and configured `OS_URL` (normally
`https://os.hz.egbe.dev`). No additional key or scope is needed. Requests use
`Authorization: Bearer $OS_API_KEY` and return the usual `{code,message,data}` envelope.

The attached PostgreSQL/Supabase schema is shared by your account's apps. OS
selects it from your key. If no database exists, provision it through
`POST /deploy/<slug>/db` as described by `/deploy/skill`.

## Read and inspect

`POST /db/query` accepts one read SQL query and a `params` array. Use `$1`, `$2`,
etc. for values. SELECT, joins, aggregates and read-only CTEs work. Supply SQL
without a trailing comment after its final semicolon.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/db/query" -s  \
 -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT id, email FROM leads WHERE email = $1 ORDER BY id","params":["test@example.com"]}'
```

Results contain `rows`, `row_count`, `truncated` and `limits`. Default limits:
1,000 rows, 1 MiB of response data, 5 seconds per statement and 1 second waiting
for a lock. A request body is limited to 64 KiB and 100 SQL parameters. Too many
concurrent requests return 429. An oversized single row returns 413; select
fewer columns or shorter values. Limits may be configured by the platform.

Large integers and fractional numbers are returned as strings to preserve
precision. Send large IDs and exact decimals as strings in parameters/changes
as well. Alias same-named columns when joining tables.

For exports, query ordered pages using a unique key: `WHERE id > $1 ORDER BY id
LIMIT 500`, then pass the last ID to the next call. Composite keys need matching
ordering/continuation on all key columns. A `truncated: true` response is
incomplete: reduce the page size/selected fields and repeat that page. Separate
requests do not share a snapshot; concurrent changes may affect an export.

The repository normally describes the schema. If needed, inspect
`information_schema.columns` or PostgreSQL catalogs using `/db/query`; there is
no separate schema-discovery endpoint.

## Correct one record

Read the target record first. Supply every primary-key column in `key`.
Tables without a primary key are not supported for these operations.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/db/rows/update" -s  \
 -H 'Content-Type: application/json' \
  -d '{"table":"leads","key":{"id":"42"},"values":{"name":"Corrected name"}}'

OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/db/rows/delete" -s  \
 -H 'Content-Type: application/json' \
  -d '{"table":"leads","key":{"id":"42"}}'
```

Changes accept literal values, not SQL expressions. Primary-key/generated
columns cannot be changed. For JSON/JSONB columns, strings remain strings;
send objects and arrays as JSON values. A request value of `null` sets SQL NULL.
Each request commits one direct row change;
database triggers and foreign-key cascades still apply. Missing rows return
404; constraint violations return 409 and roll back. Change activity records
the operation/table/outcome without storing row contents.

If the response says `database_write_outcome_unknown`, read the record before
retrying. A disconnected request can lose the acknowledgement of a committed
change. There is no automatic retry or undo history.

## CLI

Use the same key with the existing CLI environment variable:

```bash
EGBE_API_KEY="$OS_API_KEY" EGBE_OS_URL="$OS_URL" egbe db skill
EGBE_API_KEY="$OS_API_KEY" EGBE_OS_URL="$OS_URL" egbe --json db query \
  --body '{"sql":"SELECT id, email FROM leads ORDER BY id LIMIT 20","params":[]}'
EGBE_API_KEY="$OS_API_KEY" EGBE_OS_URL="$OS_URL" egbe db update \
  --body '{"table":"leads","key":{"id":"42"},"values":{"name":"Corrected name"}}'
EGBE_API_KEY="$OS_API_KEY" EGBE_OS_URL="$OS_URL" egbe db delete \
  --body '{"table":"leads","key":{"id":"42"}}'
```

Generic database inspection and cleanup use this capability. Product admin
features that enforce business workflows can remain in the application.
Migrations stay in the product's existing deployment workflow; this API does
not execute arbitrary write SQL, INSERT, bulk changes or DDL.

## Convex

These SQL endpoints operate on attached PostgreSQL, not Convex. For a Convex
product, obtain its existing backend details through `GET /deploy/<slug>/convex`,
configure `CONVEX_SELF_HOSTED_URL` and `CONVEX_SELF_HOSTED_ADMIN_KEY`, and use the
project's installed Convex CLI: `npx convex data`, `npx convex export`, or
`npx convex run <function> <args>`. Function execution uses deployed queries,
mutations or actions. Check the installed CLI/backend versions before relying
on newer options such as inline queries.
