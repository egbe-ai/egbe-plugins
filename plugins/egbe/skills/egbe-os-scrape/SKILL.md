---
name: egbe-os-scrape
description: Extract structured data from websites and supported platforms.
metadata:
  egbe-when: "Use when research needs collected web data rather than search results."
  egbe-visible: "true"
  egbe-title: "Web data extraction"
  egbe-description: "Collect structured information from websites for research or data-powered product features."
  egbe-category: "AI & data"
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

The harness can also refuse a step before Egbe answers: a denied file read or
command (`EPERM`, `operation not permitted`), a certificate error, or a connector
call that fails as a whole with HTTP 403. Egbe's own refusals of an API request
come back as a result with a `status` and Egbe's `message`, and the `egbe_skill`
tool never answers 403. Egbe refuses a whole call with 403 only for a browser
`Origin` it does not accept, so such a 403 most likely comes from the harness, a
proxy or a policy in front of Egbe. Don't retry it in a loop, route around it or
disable certificate verification. If `egbe_skill` was refused, read that skill
from an installed Egbe catalog or plugin copy, if this session has one. Name the
blocked file, command, host or tool and ask the founder to allow it, or to trust
the host through the environment's network setting. Then continue the work that
doesn't need it and say what waits on that permission. While `egbe_skill` works,
`egbe-os-quickstart`'s `references/environment.md` lists these cases.


# Scrape (Apify)

Structured web scraping behind one shape. Address everything as
`/scrape/{source}/...` where `source` is `apify` (the only source today; more drop
in later). Authenticate with `Authorization: Bearer $OS_API_KEY`.
Base URL: `https://os.hz.egbe.dev`.

Use only the `OS_URL` and `OS_API_KEY` supplied to the current workload. Product
server code reads those same names; the Site Gateway injects a separate product
identity automatically. Never mint or deploy an Apify-specific key, and never
introduce `APIFY_API_KEY` or a direct provider token for this OS capability.

The lifecycle is the same regardless of source:
**account → discover an actor → run it → read the rows.**

## Account

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/scrape/apify/account" -s
```

Returns the provider account (plan, usage, remaining credit) under `data.raw`.

## Discover an actor

An "actor" is a ready-made scraper. Search the store, or skip straight to a known
actor id if you already know one (e.g. `apify/google-search-scraper`,
`compass/crawler-google-places`, `vdrmota/contact-info-scraper`).

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/scrape/apify/actors?query=google%20maps%20reviews&limit=5" -s
```

`data.actors` is a compact `[{id, name, title, description}]` list. For the full
input schema of one actor:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/scrape/apify/actors/apify/google-search-scraper" -s
```

## Run — synchronous (default)

The simplest path: `sync` is true by default, so the call blocks and returns the
scraped rows directly. Keep `limit` small to save credits, and always set the
actor's own cap field (`maxResults`, `maxPagesPerQuery`, …) inside `input`.
A synchronous run can wait up to about 5 minutes. Through the Egbe MCP
connection, start any run that may take over a minute asynchronously (below),
because the connector's client can stop waiting before a synchronous run returns.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/scrape/apify/run" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{
    "actor": "apify/google-search-scraper",
    "input": {"queries": "best AI tools 2026", "maxPagesPerQuery": 1, "countryCode": "us"},
    "limit": 20
  }'
```

`data` carries `rows` (the scraped records), `count`, and `raw`.

## Run — asynchronous (long jobs)

For big crawls pass `"sync": false`. You get a run handle back instead of rows;
poll the run, then read its dataset when it's `SUCCEEDED`.

Send a stable `Idempotency-Key` for every logical actor run. Persist the returned
`run_id` and `dataset_id`, then reuse or poll them after a retry instead of
starting another paid run. The header is a best-effort retry identity, not a
durable exactly-once guarantee if the start response is lost before the handle
is persisted.

```bash
# 1. start
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/scrape/apify/run" -s -X POST  \
  -H 'Idempotency-Key: places-ramen-tokyo-v1' \
  -H 'Content-Type: application/json' \
  -d '{"actor":"compass/crawler-google-places","input":{"searchStringsArray":["ramen Tokyo"],"maxCrawledPlacesPerSearch":50},"sync":false}'
# -> data: {run_id, status, dataset_id}

# 2. poll
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/scrape/apify/runs/<run_id>" -s

# 3. read rows once SUCCEEDED
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/scrape/apify/datasets/<dataset_id>?limit=50" -s
```

## Passthrough — the native API

Anything the normalized verbs don't cover reaches the provider's own API:

```bash
# GET /scrape/apify/raw/store?search=tiktok  ->  tools-gateway /v1/apify/store?search=tiktok
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/scrape/apify/raw/store?search=tiktok&limit=3" -s
```

Body and query string are forwarded as-is.

## Notes

- Set `$OS_URL` to `https://os.hz.egbe.dev` (or your local gateway).
- Always cap results: a `limit` on the call **and** the actor's own cap field in `input`.
- A non-empty result isn't proof of relevance — check the rows actually match the
  requested place/topic/geography before trusting them.
- Actor ids accept both `user/actor` and `user~actor` forms.
