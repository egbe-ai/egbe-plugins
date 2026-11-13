---
name: egbe-os-errors
description: Set up Sentry error reporting and inspect project-scoped issues, exception traces and event diagnostics.
metadata:
  egbe-when: "Use when a product has errors to investigate or needs its error reporting connected or checked."
  egbe-visible: "true"
  egbe-title: "Error monitoring"
  egbe-description: "Connect your app to Sentry so your agent can investigate real browser and server errors."
  egbe-category: "Development & hosting"
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
a local deploy command, needs a set-up project workspace. In a persistent
project workspace that is not set up yet, set it up as the `egbe-setup` skill's
project setup describes.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


# Error tracking (Sentry)

Use OS `errors` to connect an app to Sentry and inspect its failures. The gateway
resolves ownership from the project key; no provider token is needed. Preserve
an existing working SDK, DSN and event tags rather than installing them again.
For an existing error, start with [issue diagnostics](#read-issue-diagnostics).

Authenticate with `Authorization: Bearer $OS_API_KEY`.
Base URL: `https://os.hz.egbe.dev`.

## Get a DSN

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/errors/<your-app-slug>" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"target":"api","platform":"node-express"}'
```

`platform` must be one of these values; without it the project gets
`javascript-nextjs`:

| `platform` | Use it for |
|---|---|
| `javascript-nextjs` | Next.js apps, browser and server (the default) |
| `javascript-react` | React or Vite browser apps and other static browser pages, including a Vite SPA served from Convex |
| `node-express` | Node.js or Express servers, APIs, and workers |
| `python` | Other Python services |
| `python-django` | Django |
| `python-fastapi` | FastAPI |
| `python-flask` | Flask |

Any other value, such as `javascript` or `browser`, fails with 400
`invalid_platform`, and the error lists `supported_platforms`. The gateway also
maps a few short aliases (`next`, `react`, `vite`, `node`, `express`) to these
names, but send the full value.

The response carries `project.dsn`. Fetch it again later with:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/errors/<your-app-slug>" -s
```

Use one product slug and separate targets when the product has multiple runtime
services:

- `web` - public frontend or a combined full-stack Next app.
- `api` - separate backend/API service.
- `worker` - background jobs.
- `admin` - separate admin/control surface.

For a single full-stack Next app, `target:"web"` is enough if both browser and
server Sentry are initialized from the same codebase. For separate frontend and
backend services, provision the same product slug with targets such as `web` and
`api`.

## Read issue diagnostics

Use the provisioned product slug and target. The reads below work with ordinary
project credentials and read-only credentials carrying `errors:read` or
`project:read`. They do not grant permission to modify or resolve an issue.

List recent issues (defaults to unresolved, most frequent first):

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/errors/<your-app-slug>/<target>/issues?status=unresolved&limit=10" -s
```

Query params: `status` (`unresolved` | `resolved` | `ignored` | `all`), `limit`
(1-50), `query` (raw Sentry search, overrides `status`), `sort` (`freq` | `date`
| `new`), `statsPeriod` (`24h` | `14d`). `<target>` is the project target
you provisioned (`web`, `api`, `worker`, `admin`).

Take the numeric `id` from the list, not the display `short_id` or a Sentry URL:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/errors/<your-app-slug>/<target>/issues/<issue_id>" -s

OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/errors/<your-app-slug>/<target>/issues/<issue_id>/events/latest" -s
```

The issue response includes its summary, platform and available first/last
release. The event response contains `issue` and `event`: the event ID and time,
release/environment, exception stack frames and breadcrumbs when Sentry captured
them. To inspect the same occurrence again, replace `latest` with its 32-character
hexadecimal event ID. The gateway verifies that both issue and event belong to
the requested product and target.

Diagnostics are a bounded, redacted projection, not a raw Sentry export. User
records, request headers/bodies, frame locals and source context are excluded;
URL credentials and query strings are removed. Inspect truncation markers and
treat missing fields as unavailable, not as evidence that nothing failed.
An inaccessible event does not mean the issue is resolved.

Use the event's timestamp, release, failing frame and breadcrumbs to inspect the
matching product code and reproduce the affected path. Compare the release with
the serving revision through `egbe-os-deploy`; an older event is not proof of a
failure in a later release. Keep the issue/event IDs with the existing repair
evidence so a later run can resume the same investigation.

## Resolve a verified repair

After the affected behavior is verified in the intended release, use the
numeric issue ID to mark it resolved. Resolving the Sentry record does not
repair the app or verify deployment, and the absence of a new event alone does
not prove a fix. A read-only key cannot perform this operation.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/errors/<your-app-slug>/<target>/issues/<issue_id>/resolve" -s -X POST
```

## Wire Env

Set the DSN as `SENTRY_DSN` in server/API/worker runtime env. The same DSN is
public-safe and may also be exposed to browser code when the framework needs a
public build-time variable such as `NEXT_PUBLIC_SENTRY_DSN`.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/deploy" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"slug":"my-app","repo":"my-app","env":{"SENTRY_DSN":"<dsn>","NEXT_PUBLIC_SENTRY_DSN":"<dsn>"}}'
```

Do not put Sentry auth tokens in product env. Product code only needs the DSN.

## Initialize SDK

### Next / full-stack app

Use `@sentry/nextjs` and initialize both client and server sides from the same
DSN when the app is full-stack. Detect the installed Next.js/Sentry versions
and follow their bundled/current file conventions instead of assuming a
training-era filename. Current Next.js with Turbopack uses
`instrumentation-client.ts` for browser initialization and `instrumentation.ts`
for server registration; export `captureRouterTransitionStart` and
`captureRequestError` hooks when the installed SDK exposes them.

```js
// instrumentation-client.ts (current Next.js/Turbopack)
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || process.env.SENTRY_DSN,
  tracesSampleRate: 0,
});
```

```js
// sentry.server.config.js
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  tracesSampleRate: 0,
});
```

### Node / API service

```js
import * as Sentry from "@sentry/node";

if (process.env.SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.SENTRY_DSN,
    tracesSampleRate: 0,
  });
}
```

### Browser-only app

```js
import * as Sentry from "@sentry/browser";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || process.env.SENTRY_DSN,
  tracesSampleRate: 0,
});
```

## Required Tags

Set these tags before capturing product exceptions:

- `product_slug` - the deployed product slug.
- `openclaw_instance` - the Egbe project identity, under its retained compatibility tag name; it does not require OpenClaw or a hosted agent.
- `runtime_target` - `web`, `api`, `worker`, or `admin`.

Example:

```js
Sentry.setTag("product_slug", process.env.PRODUCT_SLUG || "my-app");
Sentry.setTag("openclaw_instance", process.env.EGBE_INSTANCE_ID || process.env.OPENCLAW_INSTANCE || "unknown");
Sentry.setTag("runtime_target", "web");
```

## Controlled Smoke

For manual verification, you may trigger one controlled test exception and flush
the SDK before returning a response. Do not leave public debug routes enabled in
production, and do not use synthetic Sentry issues as the only proof that product
monitoring is ready. First verify setup and wiring:
Sentry project/DSN exists, deploy env carries the DSN, and product source
initializes the SDK with the required tags.
