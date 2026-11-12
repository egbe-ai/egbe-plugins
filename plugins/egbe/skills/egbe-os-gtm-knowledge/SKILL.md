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
This skill comes with the Egbe plugin. Make every Egbe API call it describes with
the Egbe connector's `egbe_request` tool: pass the HTTP method, the API path (for
example `/me/limits`), query parameters in `query` and the JSON body in `body`.
For these calls leave out `OS_URL`, the Authorization header, `.env.local` and
`egbe-curl.py`, and skip catalog update checks; the connection authenticates and
identifies the request.
Also pass the `business` that `egbe_setup` returned. Files this skill refers to
are next to this `SKILL.md`, except any listed under "Files downloaded on demand".

A step that needs a local project key, such as a git push or a local deploy
command, works only in a persistent project workspace. There, if the project's
Git-ignored `.env.local` has no `OS_API_KEY` yet, call `egbe_local_setup` once
and save its `OS_URL` and `OS_API_KEY` there, preserving other entries. Use only
those two values: the plugin already provides Egbe's skills, so do not install
the Egbe catalog or follow the rest of that result. Never show the key in chat or
put it in logs, commits or URLs. Without such a workspace, tell the founder that
this step needs an agent with a project folder, and continue with the rest of
the work.


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
