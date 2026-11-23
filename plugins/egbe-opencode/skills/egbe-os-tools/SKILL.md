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
available, the plugin's connector is not signed in for this agent. Tell
the founder how to connect it, as the `egbe-setup` skill describes, rather than
saying Egbe is unavailable.

The connector's tools work even where this environment's shell cannot reach
Egbe: their calls travel through this agent's connection, not through the
shell's network. A step that runs in the shell, such as a bundled script, a `git
push` to Egbe's Git endpoint or a deploy upload, needs the shell to reach the
Egbe host (`os.hz.egbe.dev`). If a proxy or allowlist refuses that request
before Egbe answers, for example HTTP 403 on CONNECT or curl status `000`, tell
the founder: they allow that host in this agent's network settings or continue
with an agent on their own computer. Code can also be published without the
shell by committing through the connector (`egbe-os-git`, "Without a terminal").
Until the shell step or that commit and its deploy succeed, do not report the
work as published: a preview in this agent or on this computer is not an Egbe
deployment.

The harness can also refuse a step before Egbe answers: a denied file read or
command (`EPERM`, `operation not permitted`), a certificate error, or a
connector call that fails as a whole with HTTP 403. Egbe's own refusals of an
API request come back as a result with a `status` and Egbe's `message`, and the
`egbe_skill` tool never answers 403. Egbe refuses a whole call with 403 only for
a browser `Origin` it does not accept, so such a 403 most likely comes from the
harness, a proxy or a policy in front of Egbe. Don't retry it in a loop, route
around it or disable certificate verification. If `egbe_skill` was refused, read
that skill from an installed Egbe catalog or plugin copy, if this session has
one. Name the blocked file, command, host or tool and ask the founder to allow
it, or to trust the host through the environment's network setting. Then
continue the work that doesn't need it and say what waits on that permission.
While `egbe_skill` works, `egbe-os-quickstart`'s `references/environment.md`
lists these cases.


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

## Long calls: async mode (DataForSEO, SpyFu)

A DataForSEO live call can take up to two minutes, longer than some clients wait
for one tool call. Through the Egbe connector, add `?async=1` to a
`/tools/dataforseo/...` or `/tools/spyfu/...` call (`egbe_write` or `egbe_read`
with query `{"async": "1"}`; the provider body is unchanged). It answers `202`
with a `job_id` at once. Poll `GET /tools/jobs/<job_id>` (`egbe_read`) about every
10 seconds until `status` is `succeeded` or `failed`; `result` then holds the
call's own response (`code`, `message`, `data`), provider errors included. The
provider call runs and bills once per job. Retry a start with the same
`idempotency_key` to get the existing job back instead of a second call. Results
are kept for an hour; a `404` on poll means the job is unknown or expired. Other
providers have no async mode; OS forwards the flag to them unchanged.

## More providers

For delegated research or processing with Theona agents, follow
[Theona runs](references/theona.md): discover the agent, start a run, and
continue using its returned project-owned handle.

`GET /tools` lists the low-level providers. Do not use `/tools/apollo`,
`/tools/instantly`, or `/tools/*-ads` for normal outreach or ads workflows;
use `/outreach/skill` or the selected channel's `/ads/{source}/skill` instead.
