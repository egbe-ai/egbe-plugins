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
Files this skill refers to are next to this `SKILL.md`, except any listed under
"Files downloaded on demand".

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs a set-up project workspace. In a persistent
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
Code on their own computer. Until the shell step succeeds, do not report the work
as published: a Claude Artifact or a local preview is not an Egbe deployment.


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
