---
name: egbe-os-gtm-knowledge
description: Find comparable Egbe GTM experiments to inform audience, offer and channel choices.
metadata:
  egbe-when: "Use when prior experiments can inform a new test or reprioritization."
  egbe-visible: "true"
  egbe-title: "Launch GTM insights"
  egbe-description: "Find comparable GTM experiments before choosing or reprioritizing a product's segments, offers, messages, and promotion channels."
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


# Fleet GTM Knowledge

Use this skill while preparing or materially revising `segment -> offer ->
channel` hypotheses. The report is supporting evidence, not a mandatory source:
when it contains no genuinely comparable experiment, continue from the current
product and market evidence.

Authenticate with `Authorization: Bearer $OS_API_KEY`. Base URL:
`$OS_URL` (production default: `https://os.hz.egbe.dev`).

## Find comparable experiments

Prefer `POST /gtm/comparables`: it shows the whole verified/directional pool
to a server-side LLM judge that keeps only experiments whose audience,
problem, or product category genuinely matches your context — so
differently-worded launches still match, and shared keywords alone do not.
The judge call is billed to your own LLM key.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/gtm/comparables" -sS  \
  -H "Content-Type: application/json" \
  -d '{
    "query": "B2B operations teams that need recurring compliance evidence; self-serve subscription; audit generation",
    "geo": "US",
    "limit": 5
  }'
```

Each result carries a `relevance_reason` and a unique `record_id` (one
experiment can emit several records — per campaign, variant, and window).
The response also reports `pool_size`, `judged`, and `partial`: when
`partial` is true the judge saw only part of the pool, so an empty result
must be treated as an incomplete review — never as a no-match conclusion.
`geo` is judge context, not a hard filter.

`POST /gtm/search` remains available as a keyless-of-LLM fallback (token
overlap ranking with optional hard filters). Build one concise query from
the current product truth: the buyer, costly problem or trigger,
offer/mechanism, business model or price band, and the channels under
consideration. Then request at most five records:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/gtm/search" -sS  \
  -H "Content-Type: application/json" \
  -d '{
    "query": "B2B operations teams that need recurring compliance evidence; self-serve subscription; audit generation",
    "channels": ["google", "reddit", "instantly"],
    "buyer_type": "smb",
    "business_model": "subscription",
    "include_directional": true,
    "limit": 5
  }'
```

Omit a hard filter when the current product does not establish it. Do not add a
filter merely to force a desired precedent.

## Evidence rules

For every returned experiment, inspect:

- product and buyer compatibility;
- segment, offer, CTA, message, and channel;
- dates, outcome window, sample size, and spend;
- attribution model and activation definition;
- trust tier, limitations, and evidence references.

Use `verified` evidence for defaults only when the tested conditions are
materially comparable. Use `directional` evidence only as a labelled clue or a
reason to run a bounded test. The endpoint intentionally excludes
`inconclusive` evidence.

Do not infer that a channel caused a result merely because the result happened
during that campaign. Do not compare provider conversions with product
activations or payers. Do not average records with different attribution
windows, currencies, activation definitions, or materially different buyers.

## Write the planning trace

When a record changes a hypothesis, cite its `experiment_id`, trust tier, and
the relevant observed outcome in the planning artifact. State why the precedent
is comparable and its most important limitation.

When no useful record is returned, record `Fleet evidence: none relevant` and
continue. Never invent an experiment ID, metric, or fleet conclusion.
