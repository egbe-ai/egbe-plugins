---
name: egbe-os-search
description: Search the web and local businesses; retrieve place details and Google reviews.
metadata:
  egbe-when: "Use when decisions need current sources or local-business discovery."
  egbe-visible: "true"
  egbe-title: "Web & places search"
  egbe-description: "Find web pages, local businesses, and available Google reviews for research and product features."
  egbe-category: "AI & data"
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


# Search

Web and places search behind concrete routes. Every provider returns the **same**
`SearchResponse` shape, so you parse the answer the same way no matter which one
you call. Authenticate with `Authorization: Bearer $OS_API_KEY`. A scoped key
needs the `tools` scope: without it every search route answers 403.

Base URL: `https://os.hz.egbe.dev`.

## Unified shape

```json
{
  "provider": "brave",
  "query": "best ramen in Tokyo",
  "answer": null,
  "results": [
    {"title": "...", "url": "https://...", "snippet": "...", "score": null, "source": "brave", "metadata": {}}
  ],
  "citations": [],
  "count": 1
}
```

- `answer` — a synthesized text answer (only Perplexity fills this; `null` otherwise).
- `score` — a rating when the provider has one (Places stars); `null` otherwise.
- `metadata` — provider-specific extras (place_id, result age, etc.).

## Web search (Brave) — 250/day

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/search/web/brave" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"query":"best ramen in Tokyo","count":5,"country":"jp","lang":"en"}'
```

`country` selects a Brave search region, not the product's target market. The
supported values (checked 2026-09-24 against the
[official API reference](https://api-dashboard.search.brave.com/api-reference/web/search/get)) are:

```text
AR AU AT BE BR CA CL DK FI FR DE GR HK IN ID IT JP KR MY MX NL NZ NO CN
PL PT PH RU SA ZA ES SE CH TW TR GB US ALL
```

OS normalizes case. ISO codes outside this list, including `AE` and `OM`, are
not supported search regions. Use `country: "ALL"` with the target country,
relevant official domains (`site:`) and language in the query; `lang` sets the
search language. Record that this is all-regions search, not local market data.
Omitting `country` uses the provider's US default, not an unbiased global search.
A 422 region error is not evidence of missing demand; correct the region once
and keep the intended market unchanged. Read original pages before treating
snippets as evidence; country search results are not a company census.

## AI research (Perplexity) — 20 successful submissions/claw/day, slow

Returns a synthesized `answer` plus `citations`. Heavily rate-limited (20 per
day per claw). This OS allowance is separate from the shared Perplexity API
credit balance. An upstream `insufficient_quota` error is a billing/credit
failure, not exhaustion of this daily allowance; stop and surface the error
instead of retrying or switching research providers.

**Deep research takes minutes — do NOT call it synchronously.** A blocking call
outlives your HTTP client timeout and you get a dropped connection (HTTP 000)
with no response body. Use the async submit/poll pair instead:

```bash
# 1. submit — returns immediately with a request_id
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/search/web/perplexity/async" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"query":"What changed in EU AI Act enforcement in 2026?"}'
# -> {"request_id":"<id>","status":"PENDING","poll":"GET /search/web/perplexity/async/<id>"}

# 2. poll until status is COMPLETED, FAILED, CANCELLED or INCOMPLETE
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/search/web/perplexity/async/<id>" -s
```

Stop polling on any terminal status. `INCOMPLETE` means the provider stopped
before finishing (for example, output truncation); partial `answer` and `results`
may still be present. Inspect `error_message` for unsuccessful runs and preserve
the request ID rather than resubmitting automatically.

Async research uses Perplexity Agent background runs. Legacy Sonar model names
map to the provider's recommended presets (`sonar-deep-research` → `high`).
Async options: `model` (default `sonar-deep-research`), `reasoning_effort`
(`low|medium|high`), `system_prompt`.

The synchronous route still exists for quick calls, but it is bounded by a short
timeout: if it can't finish in time it returns a `504` envelope pointing you at
the async route rather than hanging.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/search/web/perplexity" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"query":"quick fact-check","preset":"deep-research"}'
```

Optional (sync): `preset` (research depth, default `"deep-research"`) and
`system_prompt`.

## Places (Google) — 200/day

Local businesses. `score` is the star rating; `url` links to Google Maps.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/search/places" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"query":"ramen in Shibuya","max_results":5,"region_code":"jp"}'
```

Optional: `language_code` (e.g. `"ja"`) for localized results.

### Place details and reviews

For business research or reputation monitoring, follow
[the Google Places workflow](references/google-places.md). It covers project
quotas, selecting `data.results[].metadata.place_id` from search, and fetching
details and available reviews through the existing OS `/tools/places/*` routes.
These operations return provider data inside the OS envelope; their shapes
are described in the workflow. Google returns at most five reviews per place,
not a complete review history.

If this skill was read inline from `/search/skill`, the supporting workflow is
available at `GET /skills/search/resources/references/google-places.md` or in
the complete `/skills/search` bundle.

List providers and the shape any time with `GET /search`.
