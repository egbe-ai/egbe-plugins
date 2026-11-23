---
name: egbe-os-apollo-lead-finder
description: Search and enrich Apollo contacts or extract contact candidates from Places business websites through Egbe OS.
version: 1.1.2
user-invocable: true
argument-hint: "[find-leads --config <file> | search --titles <t> | enrich --input <file> | places-leads --queries <q;q>] --output <leads.json>"
metadata:
  egbe-when: "Use for contact discovery, Apollo enrichment, or Places website sourcing."
  egbe-visible: "true"
  egbe-title: "Lead discovery"
  egbe-description: "Search business contacts and return source status, enrichment progress and contact candidates."
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

Run a script bundled with this skill from the root of a project folder set up
for Egbe, with `OS_AGENT_NAME="<your agent name>"` set inline, such as `OpenCode`.
A script that calls Egbe reads `OS_URL`, `OS_API_KEY` and this agent's connection
ID from `.env.local` through Egbe's request helper, which comes with the plugin at
`../egbe-os-quickstart/scripts/egbe-curl.py` from this skill's folder. Where this
skill says a script needs `OS_URL` or `OS_API_KEY` in its environment, start it
through the helper, which loads `.env.local` without executing it:
`python3 <helper> --egbe-run <command>`, with the helper's absolute path. Where
this skill writes `<skills-directory>`, use the plugin's `skills` folder, which
holds this skill's folder.


# Apollo Lead Finder

Use this capability for a requested contact search or enrichment. It does not
choose the audience, grant permission to spend or contact people, or require an
Instantly campaign.

Read [operations](references/operations.md) for commands, input/output shapes,
limits and recovery. The four commands are:

- `search`: live Apollo preview without enrichment; consumes search quota.
- `find-leads`: search followed by enrichment.
- `enrich`: enrich a compatible people list, or resume unfinished enrichment
  from a partial Apollo result while preserving its existing leads.
- `places-leads`: Places search/details followed by guarded public website reads.

Use Node and `OS_URL` / `OS_API_KEY` (or `--env-file`). Authenticated provider
operations go through Egbe OS with Bearer auth; do not request separate Apollo
keys or bypass the gateway. Public website reads by Places are unauthenticated.

Set `--output` to a durable location in the access-controlled project repository:
the owning campaign's `egbe-docs/marketing/campaigns/instantly/<run_key>/leads.json`,
or `egbe-docs/research/<id>/work/` before a campaign exists. Keep the result's
source and completeness metadata with the contacts. Files contain personal data.

Check `meta.complete`, `stop_reason` and the unfinished inputs, not just the
number of emails. A completed zero-result search differs from an outage or quota
stop. Partial results remain usable evidence, not a claim that sourcing finished.
A provider status such as `verified` or `likely`, or a scraped `unverified`
address, does not establish current deliverability, relevance, consent or
authorization to send. These commands neither launch campaigns nor replace
downstream import verification.

## Through the Egbe connector

Without Node, make the scripts' requests with `egbe_write` and keep their
bounds. Each result's `data` is the provider body.

- **Search** (`POST /outreach/apollo/people/search`, consumes search quota): the
  Apollo fields from [search inputs](references/operations.md#search-inputs),
  plus `page` (from 1) and `per_page` (at most 100). Read `data.people`. Request
  the next page until a page is empty or shorter than `per_page`, the page
  reaches `data.pagination.total_pages` (missing pagination does not mean one
  page) or you have the requested number. Deduplicate by person `id` across
  pages; a page that adds no new `id` is a repeated page, an incomplete result
  rather than the end.
- **Enrich** (`POST /outreach/apollo/people/bulk_match`, consumes enrichment
  quota and can cost money): `{"details": [...]}` with at most 10 people, each
  with `id`, or `linkedin_url`, or `first_name` and `last_name` with `domain` or
  `organization_name`, and `"reveal_personal_emails": false`. Read
  `data.matches`; a null entry is an unmatched person. `POST
  /outreach/apollo/people/match` takes one such person.
- Keep a match as a lead only with an email, trimmed and lower-cased, once per
  address; the scripts keep `email_status` `verified` and `likely` by default.

Save the result after every page or batch, before the next request, in the
`{leads, meta}` shape of
[operations](references/operations.md#enrichment-and-result-contract) with
`complete`, `stop_reason`, `processed_count` and the inputs not yet sent as
`not_enriched_people`. Keep it at its location above in Egbe's artifact store,
as `egbe-os-quickstart` → `references/artifact-sync.md` ("Through the Egbe
connector") describes; it holds personal data, so keep it nowhere else. A lost
response may already be charged: on resume send only the saved unsent inputs.
`places-leads` reads business websites with a guarded local client and needs a
set-up project workspace: in a persistent project workspace not set up yet, call
`egbe_local_setup`; otherwise tell the founder which step needs it. Through the
connector, use `egbe-os-search` for Places listings and details instead.
