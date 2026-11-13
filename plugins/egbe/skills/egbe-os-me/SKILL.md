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
