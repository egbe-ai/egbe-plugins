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
describes with the Egbe connector's `egbe_request` tool: pass the HTTP method,
the API path (for example `/me/limits`), query parameters in `query` and the JSON
body in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Files this skill refers to are next to this `SKILL.md`, except any listed under
"Files downloaded on demand".

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs the standard workspace setup. In a persistent
project workspace that is not set up yet, call `egbe_local_setup` and follow it.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


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
