---
name: egbe-os-research
description: Run and resume deep multi-source research.
metadata:
  egbe-when: "Use when a question needs in-depth evidence or a research job needs continuation."
  egbe-visible: "true"
  egbe-title: "Deep research"
  egbe-description: "Investigate a question across multiple sources and get a structured report with supporting evidence."
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
a local deploy command, needs a set-up project workspace. In a persistent
project workspace that is not set up yet, set it up as the `egbe-setup` skill's
project setup describes.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


# Deep research

Use this capability when a task needs a cited, multi-source web research report.
OS owns the engine and model routing; callers provide the research question and
instructions, never a provider or model.

Research is asynchronous. Submit once with a stable idempotency key, persist the
returned job ID, and poll that job until it reaches a terminal state.

Authenticate with `Authorization: Bearer $OS_API_KEY`. Base URL: `$OS_URL`
(`https://os.hz.egbe.dev`).

## Submit or recover a job

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/research" -s -X POST  \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Market demand and competitors for AI tutoring apps for European teens in 2026",
    "instructions": "Return cited Markdown. Separate verified facts, estimates, and evidence gaps.",
    "depth": "deep",
    "idempotency_key": "market-research:target-audience:INPUT_SHA256"
  }'
```

- `query` contains the question and relevant product context.
- `instructions` contains stable scope, evidence, and output requirements.
- `depth` is `standard` or `deep`.
- `idempotency_key` identifies this exact logical attempt. Repeating it returns
  the same job and does not spend another quota unit.

Persist `data.id` before doing other work.

## Poll

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/research/<job-id>" -s
```

Statuses are `queued`, `running`, `completed`, and `failed`.

When completed, read `data.result.markdown`. Do not fetch a public report URL as
an agent input. On failure, inspect `data.error.code` and
`data.error.retryable`; do not silently switch providers or write substitute
research.

## Recover after an interruption or failure

- If submission/polling is interrupted, reuse the same payload and key (or poll
  the saved job ID). A lost POST response does not mean the job was not accepted.
- `failed` is terminal. Repeating its key returns that failure, not a requeue;
  HTTP 202 alone does not mean the engine is running. Read `data.status`.
- For `retryable: true`, a transient failure permits one deliberate new attempt
  after a short wait. Persist a new stable key, e.g. append `:retry-1`, and reuse
  that key for all submission/polling recovery. Stop and report repeated failure.
- For `retryable: false`, report the error and job ID. Model-access or upstream
  authentication errors require Egbe to repair the service configuration. Start
  a new attempt/key only after the cause is addressed.

## Limits

Each newly accepted idempotent job consumes one of 20 monthly research jobs per
instance. Polls, result reads, and duplicate submissions with the same key do
not consume another unit.
Failed jobs receive a best-effort quota refund; a failed refund does not permit
bypassing the quota limit.
