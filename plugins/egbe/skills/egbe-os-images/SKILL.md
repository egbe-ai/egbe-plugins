---
name: egbe-os-images
description: Generate images or find stock photography and illustrations.
metadata:
  egbe-when: "Use when a product, website or campaign needs visuals."
  egbe-visible: "true"
  egbe-title: "Images"
  egbe-description: "Generate images or find stock photography for your product, website and advertising."
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
a local deploy command, needs the standard workspace setup. In a persistent
project workspace that is not set up yet, call `egbe_local_setup` and follow it.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


# Images

Image generation and stock image search through Egbe OS. Authenticate with
`Authorization: Bearer $OS_API_KEY`. The provider keys live on the gateway —
you never handle them.

Base URL: `https://os.hz.egbe.dev`.

Use only the `OS_URL` and `OS_API_KEY` supplied to the current workload. Product
server code reads those same names; the Site Gateway injects a separate product
identity automatically. Never mint or deploy an image-specific key, and never
introduce `IMAGE_API_KEY` for this OS capability.

Available options:

- [Image generation](#generate) from a text prompt.
- [Stock image search](references/stock-images.md) through Pixabay.

## Generate

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/images/generations" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"prompt":"a minimalist logo of a fox, flat vector","model":"gemini-flash-image"}'
```

Response:

```json
{
  "model": "gemini-flash-image",
  "backend": "litellm",
  "size": null,
  "images": [{
    "b64_json": "<base64>",
    "mime_type": "image/png",
    "url": "https://supabase.hz.gcp.egbe.dev/storage/v1/object/public/img_<you>/gen/<id>.png",
    "stored": true
  }],
  "count": 1
}
```

Each image is also **saved to your own image bucket** and gets a stable public
`url` (`stored:true`) — use it directly on landing pages, no re-upload needed.
If storage is briefly unavailable the image still comes back as base64 with
`stored:false`; just retry later if you need the URL.

Save the first image:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/images/generations" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"prompt":"a red apple on a wooden table"}' \
| python3 -c 'import sys,json,base64; d=json.load(sys.stdin)["data"]; open("out.png","wb").write(base64.b64decode(d["images"][0]["b64_json"]))'
```

## Models

`model` is optional — omit it for the default (`gemini-flash-image`). Aliases:

- `gemini-flash-image` — default, Gemini 2.5 Flash via OpenRouter, fast (~seconds)
- `gpt-image-2.5-flare` — fast, high-quality everyday generation via CLI Proxy
- `gpt-image-2.5-sunburst` — demanding quality via CLI Proxy
- `gpt-image-2`, `gpt-image-mini`, `gpt-image`, `dall-e-3` — compatibility aliases
  for Flare; `dall-e-3` does not invoke the retired DALL·E model
- `gemini-3-pro-image-preview` — Gemini via OpenRouter, high quality

Choose Flare for everyday OpenAI image generation and Sunburst when quality
matters most. OpenAI image models use CLI Proxy; the existing Gemini fallback
can serve a request if the selected OpenAI model is temporarily unavailable.
All requests keep the same OS account authentication and quota controls.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/images/generations" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"prompt":"a product photograph of a blue ceramic mug","model":"gpt-image-2.5-flare","size":"1536x1024","n":1}'
```

`size` is forwarded to the provider. Request `n=1..4` images; each generated
image counts against your quota. OpenAI requests expand into individual image
calls, so requesting several images takes longer.

List them any time with `GET /images`.

## Limits

Two quotas apply:
- **Generation** — `image-gen:generations`, 100/day. `n` > 1 charges per image.
- **Image uploads** — `image-storage:bytes`, 500 MB total uploaded image data.
  This cumulative allowance does not reset. Deleting images from your bucket
  does not automatically restore it.

A `429` means you've hit a cap. Check both:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/me/limits?resource=image-gen" -s
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/me/limits?resource=image-storage" -s
```
