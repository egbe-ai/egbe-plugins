---
name: egbe-os-me
description: Read service usage and daily, monthly and total allowances.
metadata:
  egbe-when: "Use when planning work requires checking resource consumption or limits."
  egbe-category: "Business operations"
  egbe-visible: "true"
  egbe-title: "Usage & allowances"
  egbe-description: "Check service usage, remaining allowances and when limits reset."
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


# Me

Your own account state. Authenticate with `Authorization: Bearer $OS_API_KEY`.

Base URL: `https://os.hz.egbe.dev`.

## Check your limits

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/me/limits" -s
```

Returns every tracked resource with its current usage and remaining budget:

```json
{
  "instance_id": 1142,
  "count": 2,
  "limits": [
    {"resource": "brave:searches", "display_name": "Brave · Web searches",
     "service_name": "Brave", "counter_name": "Web searches", "unit": "searches",
     "description": "Each successful web search request counts once, regardless of the number of results returned.",
     "category": "research", "advanced": false,
     "current": 3, "max_allowed": 250, "remaining": 247,
     "reset_period": "daily", "next_reset_at": "2026-06-18T00:00:00Z", "allowed": true},
    {"resource": "perplexity:responses", "display_name": "Perplexity · AI web answers",
     "service_name": "Perplexity", "counter_name": "AI web answers", "unit": "answers",
     "description": "Each successful request for an AI answer with web sources counts once.",
     "category": "research", "advanced": false,
     "current": 20, "max_allowed": 20, "remaining": 0,
     "reset_period": "daily", "next_reset_at": "2026-06-18T00:00:00Z", "allowed": false}
  ]
}
```

- `resource` — stable technical ID for filtering and integrations. Do not rename it.
- `display_name` — the shared `Service · Counter` label; use it when explaining usage.
- `description` — what counts as one unit. Records, requests, and generated images are different units; do not equate them with completed reports or sales.
- `unit` — the counted unit, such as `records`, `requests`, or `bytes`.
- `category` — research, media, hosting, payments, advertising, or other.
- `advanced` — automatic operational counters, such as research or video progress checks. They still enforce limits.
- `reset_period` — `daily` and `monthly` reset at the supplied `next_reset_at`; `inventory` means a total allowance that does not reset.
- `current` — usage this period, or cumulative usage for a total allowance.
- `remaining` — what's left before you're blocked.
- `max_allowed` — the configured allowance; a negative value means unlimited. When both `max_allowed` and `current` are zero, the action is unavailable, not used up.
- `allowed` — whether another unit can be used. `false` can mean an unavailable action or exhausted usage; check `max_allowed` and `current` before describing it. For exhausted daily or monthly limits, wait until `next_reset_at`. Total allowances have no reset date; release resources where supported or have the allowance increased.

The response message distinguishes `unavailable` actions from `exhausted` usage.
Keep unavailable actions out of a capabilities introduction, and explain their
restrictions only when they affect the founder's requested work or next step.

The `egbe me limits` CLI shows the same names, units, and reset periods in a table.
Use `egbe --json me limits` to inspect descriptions and stable IDs.

## Watch a limit decrement

Filter to one tool to confirm a call was billed:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/me/limits?resource=perplexity" -s
```

Call the tool (e.g. `POST /search/web/perplexity`), then hit `/me/limits?resource=perplexity`
again — `current` goes up by one and `remaining` drops.
