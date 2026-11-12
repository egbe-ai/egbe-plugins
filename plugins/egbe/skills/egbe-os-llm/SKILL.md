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
This skill was delivered through the Egbe MCP connection. Make every Egbe API
call it describes with the `egbe_request` tool: pass the HTTP method, the API
path (for example `/me/limits`), query parameters in `query` and the JSON body
in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Read a referenced file with
`egbe_skill(name=<skill>, resource=<relative path>)`.

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs the standard workspace setup. In a persistent
project workspace that is not set up yet, call `egbe_local_setup` and follow it.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


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
audio. Supported types are WAV, MP3, MP4 audio, WebM, Ogg and FLAC, with a 24 MiB
decoded bound. Remote URLs and caller-selected models are rejected. The account's
provisioned AI key pays for the server-configured `media-transcription` role.
The response preserves text, available language and timestamped segments as
speech evidence; it does not prove the competitor's claims.

The deployment must explicitly set `OS_MEDIA_TRANSCRIPTION_MODEL` to an audio
model configured in that account's upstream. It must support multipart
`/v1/audio/transcriptions` with `response_format=verbose_json`. There is no
catalogued default audio model in this repository. A missing policy returns 503;
video research can still analyse available frames and report the speech gap.
