---
name: egbe-os-llm
description: Add LLM-powered assistants, text generation and document analysis.
metadata:
  egbe-when: "Use when a product needs AI features."
  egbe-visible: "true"
  egbe-title: "AI features"
  egbe-description: "Add AI-powered text generation, chat and other language-model features to your product."
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


# LLM

OpenAI-compatible chat completions, routed through your account — you don't
handle the model key. Authenticate with `Authorization: Bearer $OS_API_KEY`.

Base URL: `https://os.hz.egbe.dev`. Endpoint: `POST /v1/llm/chat/completions`
(standard OpenAI body in, standard completion out).

Use only the `OS_URL` and `OS_API_KEY` supplied to the current workload. Product
server code reads those same names; the Site Gateway injects a separate product
identity automatically and OS routes its spend through the product AI role.
Never mint or deploy an LLM-specific OS key, and never introduce `LLM_API_KEY`
for this capability.

## Models

Model names are **egbe catalog slugs**, not the public OpenAI/Anthropic names —
`gpt-4o`, `gpt-3.5-turbo` or `claude-3-sonnet-20240229` are rejected upstream
with `Invalid model name`. Discover the slugs your account can use:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/v1/llm/models" -s
```

This returns the standard OpenAI `{ "data": [ { "id": "<slug>" }, ... ] }` shape.
Typical slugs include `gpt-6-luna`, `gpt-6.1-sol`, `gemini-3-pro`,
`bedrock-sonnet-4.6`, and `bedrock-glm-5`.
Pass only a slug returned for the current account.

Use `gpt-6.1-sol` for general work at `medium`, or `high` for harder tasks.
Use `gpt-6-luna` at `low` or `medium` for focused summaries, extraction, and
inexpensive pipelines. Sol supports `low`, `medium`, `high`, `xhigh`, and `max`;
Luna also supports `none`. Both default to `medium`; explicit supported effort
values take precedence. The gateway bridges GPT chat requests to upstream
Responses so function tools retain the requested reasoning effort.

## Chat

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/v1/llm/chat/completions" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-6-luna",
    "messages": [{"role":"user","content":"Say hi in 3 words."}]
  }'
```

The response is the standard chat-completions shape (`choices[0].message.content`),
so existing OpenAI SDKs work by pointing `base_url` at `$OS_URL/v1/llm` and using
your `$OS_API_KEY`.

## Streaming usage

Streamed responses report token usage only when the request sets
`"stream_options": {"include_usage": true}`; the usage arrives in a final chunk
with empty `choices`. Some harnesses omit it for custom endpoints. OpenClaw
does unless each model entry of its custom provider for this endpoint sets
`compat.supportsUsageInStreaming: true`. Without it, that harness and its
telemetry record zero tokens for every call.

## Speech evidence

`GET /v1/media` advertises whether speech transcription is configured.
`POST /v1/media/transcribe` accepts a local audio upload encoded in JSON:
`schema_version: 1`, `media_type`, `sha256` and `content_base64`, with an optional
two- or three-letter `language` hint. Supply the actual SHA-256 of the decoded
audio. Through the Egbe connector (`egbe_write`), or when the audio is already at
a public HTTPS URL, send `content_url` instead of `content_base64`; OS downloads
it and `sha256` becomes an optional check. `/v1/media/analyze` frames accept
`content_url` the same way. Supported types are WAV, MP3, MP4 audio, WebM, Ogg
and FLAC, with a 24 MiB decoded bound. Caller-selected models are rejected. The account's
provisioned AI key pays for the server-configured `media-transcription` role.
The response preserves text, available language and timestamped segments as
speech evidence; it does not prove the competitor's claims.

The deployment must explicitly set `OS_MEDIA_TRANSCRIPTION_MODEL` to an audio
model configured in that account's upstream. It must support multipart
`/v1/audio/transcriptions` with `response_format=verbose_json`. There is no
catalogued default audio model in this repository. A missing policy returns 503;
video research can still analyse available frames and report the speech gap.
