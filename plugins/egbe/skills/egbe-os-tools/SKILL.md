---
name: egbe-os-tools
description: Call low-level external-provider tools.
metadata:
  egbe-when: "Use when no higher-level Egbe capability covers the operation."
  egbe-visible: "true"
  egbe-title: "Video & creative research"
  egbe-description: "Generate videos for your marketing and research competitor creatives through the Meta Ad Library."
  egbe-category: "Marketing & growth"
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


# Tools

Low-level external capabilities behind one endpoint. Call
`/tools/{provider}/{path}` with `Authorization: Bearer $OS_API_KEY`; we forward
to the right provider. List providers with `GET /tools`.

Prefer higher-level OS capabilities when they exist:

- `/search/skill` for Brave, Perplexity, and Places search
- `/scrape/skill` for Apify scraping
- `/images/skill` for image generation
- `/ads/google/skill`, `/ads/meta/skill`, or `/ads/reddit/skill` for the selected ad channel
- `/outreach/skill` for Apollo lead sourcing and Instantly campaigns

Base URL: `https://os.hz.egbe.dev`.

## Web & places search → use `/search`

Search has its own capability with one unified result shape. See `GET /search/skill`:
`POST /search/web/brave`, `POST /search/web/perplexity`, `POST /search/places`.

## Generate an image

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/tools/images/generations" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"prompt":"a minimalist logo of a fox","size":"1024x1024"}'
```

## Generate a video

Talking-head and other long-running video generation goes through the low-level
tools endpoint:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/tools/videos/generations" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"prompt":"A founder speaks directly to camera about how the product saved hours each week.","duration_seconds":10,"aspect_ratio":"9:16","generate_audio":true}'
```

Poll status:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/tools/videos/generations/<request_id>?model=fal-ai/kling-video/v2.6/pro/text-to-video" -s
```

Upload a completed generated talking-head video into Meta and get `video_id`:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/tools/videos/generations/<request_id>/meta-upload" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"model":"fal-ai/kling-video/v2.6/pro/text-to-video","filename":"03-talking-head.mp4"}'
```

## Scrape the web (Apify)

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/tools/apify/run-sync" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"actor":"apify/web-scraper","input":{"startUrls":[{"url":"https://example.com"}]}}'
```

## Meta Ad Library

Use this for read-only competitor ad research:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/tools/meta-ad-library/search" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"query":"language learning","countries":["ALL"],"activeStatus":"ALL","adType":"ALL","searchType":"KEYWORD_UNORDERED","limit":50,"sortBy":"none"}'
```

If the upstream Meta app lacks Ad Library permission, treat the research as
blocked rather than fabricating competitor ads.

## Google paid search of a competitor (SpyFu)

Read-only Google Ads intelligence for one domain: estimated monthly budget,
paid clicks and paid keyword count with history, PPC competitors, the
keywords it buys, its ad copy over time, and keywords shared by up to three
domains.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/tools/spyfu/domain-stats" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"domain":"competitor.com","country_code":"US","months":12}'
```

Other operations take the same `domain` and `country_code`:
`ppc-competitors`, `ppc-keywords`, `paid-serps`, `ad-history` (optional
`keyword`, `since`, `until` as `YYYY-MM-DD`), plus `kombat`
(`include_domains`, `exclude_domains`, `intersection`) and `keyword-ads`
(`keyword`). `country_code` is one of 28 markets; `GB` is accepted as `UK`.

SpyFu bills every returned row, so ask for the rows you need (`max_rows`,
default 100, at most 500). Each answer reports `rows_billed` and `cost_usd`.
The per-claw daily `spyfu:rows` limit counts those rows: near the limit a
list answer is cut to the rows left and says `limited_by_quota: true`, and
`domain-stats` answers 429 instead of a shorter history. `has_more` tells
whether another page exists. `found: false` from `domain-stats` means SpyFu
has no data for the domain, not zero spend.

## More providers

For delegated research or processing with Theona agents, follow
[Theona runs](references/theona.md): discover the agent, start a run, and
continue using its returned project-owned handle.

`GET /tools` lists the low-level providers. Do not use `/tools/apollo`,
`/tools/instantly`, or `/tools/*-ads` for normal outreach or ads workflows;
use `/outreach/skill` or the selected channel's `/ads/{source}/skill` instead.
