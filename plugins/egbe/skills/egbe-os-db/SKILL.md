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


# Work with your database

Use the founder's existing `OS_API_KEY` and configured `OS_URL` (normally
`https://os.hz.egbe.dev`). No additional key or scope is needed. Requests use
`Authorization: Bearer $OS_API_KEY` and return the usual `{code,message,data}` envelope.

The attached PostgreSQL/Supabase schema is shared by your account's apps. OS
selects it from your key. If no database exists, provision it through
`POST /deploy/<slug>/db` as described by `/deploy/skill`.

## Read and inspect

`POST /db/query` accepts one read SQL query and a `params` array. Use `$1`, `$2`,
etc. for values. SELECT, joins, aggregates and read-only CTEs work; other keys
have narrower limits (see Read-only keys). Supply SQL without a trailing comment
after its final semicolon.

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

The repository normally describes the schema. If needed, the owner's key can
inspect `information_schema.columns` or PostgreSQL catalogs using `/db/query`;
there is no separate schema-discovery endpoint.

### Read-only keys

Any key other than the owner's full `OS_API_KEY`, such as an evaluation key or a
key allowed to read but not change the database, gets a stricter query check.
It accepts one SELECT, including joins, aggregates, window functions, UNION and
read-only CTEs, using common built-in functions, operators and casts. Each
referenced table must be a plain table in this project's schema whose every
column, selected or not, has a common built-in type (boolean, numbers, text,
bytea, date/time/interval, uuid, json/jsonb, network addresses, bit) or an array
of one. It rejects views, partitioned, foreign or inherited tables, row-level
security, other column types, expression/partial indexes or other stored custom
logic, PostgreSQL catalogs, other schemas, `SELECT INTO`, row locks and overly
complex queries.

Schema discovery is limited to reduced `information_schema.tables`
(`table_schema`, `table_name`, `table_type`) and `information_schema.columns`
(`table_name`, `column_name`, `ordinal_position`, `is_nullable`, `data_type`,
`udt_name`). `data_type` is the PostgreSQL type name, such as `int4` or
`timestamptz`; other fields return 400. These lists can include views and other
tables this check rejects.

A rejected query returns 403 `database_read_query_unsupported` without running
it. Rewrite it with plain tables and built-in expressions. If the needed data
lives only in an ineligible table or view, or restricted reads return 503
`database_api_unavailable`, report that data as unavailable and its value as
unknown, not as zero or absent. Do not look for another key or admin
credentials, and do not write or copy data to work around the check.

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

These SQL endpoints operate on attached PostgreSQL, not Convex.

### Read Convex documents without a terminal

`GET /db/convex/tables/<table>` returns one page of a table of the account's
Convex backend, like `npx convex data <table>`, with the same key and no admin
key:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/db/convex/tables/users" -s
```

The result has `documents`, `count`, `hasMore`, `cursor` and `snapshot`. While
`hasMore` is true, request the next page with `?cursor=<cursor>&snapshot=<snapshot>`;
keep the first page's `snapshot` so every page reads the same point in time.
Table names come from the repository's `convex/schema.ts`; an unknown table
returns 404. System tables such as `_storage` can be read the same way. A page
too large to return gives 413; export from a workspace instead.

### Export, run functions and change data: workspace only

`npx convex export`, `npx convex run <function> <args>`, `npx convex import` and
direct document edits need a workspace with Node. Obtain the backend details
through `GET /deploy/<slug>/convex`, configure `CONVEX_SELF_HOSTED_URL` and
`CONVEX_SELF_HOSTED_ADMIN_KEY`, and use the project's installed Convex CLI.
Function execution uses deployed queries, mutations or actions. Check the
installed CLI/backend versions before relying on newer options such as inline
queries. Without a workspace, correct data through the product's own functions:
change the code and publish it with `POST /deploy/<slug>/convex/deploy`.
