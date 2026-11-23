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

`query`, `instructions` and `idempotency_key` are required and non-blank.

- `query` contains the question and relevant product context.
- `instructions` contains stable scope, evidence, and output requirements.
- `depth` is `standard` (default) or `deep`.
- `idempotency_key` identifies this exact logical attempt. Repeating it returns
  the same job and does not spend another quota unit. Use 1-128 characters from
  `A-Z a-z 0-9 . _ : -` only: no slashes or spaces, so never an artifact path.

A 422 rejects the body without creating a job and names each invalid field
(`Invalid request: <field>: <reason>`); fix that field and submit again.

Persist `data.id` before doing other work. Through the Egbe connector without a
project folder, persist it, and later the result you rely on, in Egbe's artifact
store (for example `research/<id>/job.json`), as `egbe-os-quickstart` →
`references/artifact-sync.md` ("Through the Egbe connector") describes. A job ID
kept only in the conversation cannot be recovered after it.

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
