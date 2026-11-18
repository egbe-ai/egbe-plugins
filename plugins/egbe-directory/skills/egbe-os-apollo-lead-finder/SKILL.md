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

## Files downloaded on demand

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project workspace; without one,
tell the founder that the step needs it and continue with the rest of the work.

In a project workspace, before a step that runs or copies one of these files,
download it into `.egbe/skills/egbe-os-apollo-lead-finder/` at the same relative path, for example
`curl -fsSL <url> --create-dirs -o .egbe/skills/egbe-os-apollo-lead-finder/<file>`, and check that its SHA-256
matches. Also download the files it uses from the same folder, such as the
modules a script imports. Wherever this skill names one of these files by its
path in the skill (for example `scripts/...` or `assets/...`), use `.egbe/skills/egbe-os-apollo-lead-finder/<file>`;
where it writes `<skills-directory>`, use `.egbe/skills`.
Keep `.egbe/skills/` out of Git by adding it to `.gitignore`.

| File | URL | SHA-256 |
| --- | --- | --- |
| `scripts/enrich.js` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/enrich.js | `9211c7c9a5034ffae7f96ed709d8d06e18ff6d70af25fd9b396853e97c91cc5e` |
| `scripts/enrich.sh` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/enrich.sh | `e7b5712d62a849906586f49902da1248df567d37fcca448fc0d12b24dd49b1c9` |
| `scripts/find-leads.js` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/find-leads.js | `e9d2eca7084ff5f712dc34c5c3574ce466c8dc74e73239edf2e6389fdb78845d` |
| `scripts/find-leads.sh` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/find-leads.sh | `f4915aa46cf72598bb0c9435041abbd4dd412532a41be8adb5a955796adee189` |
| `scripts/lib/apollo-client.js` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/lib/apollo-client.js | `4eac5e5ee791c137cdc001ea006d129d85ab02a7dc18fd9c0abf2fb901a54a3d` |
| `scripts/lib/connection-identity.js` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/lib/connection-identity.js | `a23f252b73559814ff1697c5dcac5e6cd7b18d794244245d4fcf484e63e5708c` |
| `scripts/lib/helpers.js` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/lib/helpers.js | `ea229b2bc015394e372bee2926dea7987d6af32a5a6de6b25765e393039391f0` |
| `scripts/lib/places-filters.js` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/lib/places-filters.js | `1e562e83f551d2f954239768842d8bb536b73c89a0a35d46460b2ac640657d97` |
| `scripts/lib/sourcing.js` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/lib/sourcing.js | `41cb5de0929bc56469c93bf9a6a9c998425adade2069b83fb1fd1ad85c92d1d4` |
| `scripts/places-leads.js` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/places-leads.js | `5d9e16d77a7837109dba88afd355401df100ee9fce4e1ad4c476b368f103dcdb` |
| `scripts/places-leads.sh` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/places-leads.sh | `34a4fef7440b50fc9303fac220db4747116dd727c8b0ce48ca39713fca8fa5d7` |
| `scripts/search.js` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/search.js | `b2f64047c60f99d02e098414bf78d803e782772840a983c5b572928b69ef4cf3` |
| `scripts/search.sh` | https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/scripts/search.sh | `fb569b3d7fd7d6632a810a1ac80569ca5074adb4e48570ff08551fa511f02765` |
