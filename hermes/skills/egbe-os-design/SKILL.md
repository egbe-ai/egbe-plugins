---
name: egbe-os-design
description: Search the design-reference catalog and retrieve concrete design systems for interface work.
metadata:
  egbe-when: "Use for interface design; offer when inconsistent visuals need a coherent reference."
  egbe-visible: "true"
  egbe-title: "Design systems"
  egbe-description: "Give your product a consistent visual language using reference design systems for typography, colors and components."
  egbe-category: "Product & design"
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
available, the plugin's connector is not signed in for this agent. Tell
the founder how to connect it, as the `egbe-setup` skill describes, rather than
saying Egbe is unavailable.

The connector's tools work even where this environment's shell cannot reach
Egbe: their calls travel through this agent's connection, not through the
shell's network. A step that runs in the shell, such as a bundled script, a `git
push` to Egbe's Git endpoint or a deploy upload, needs the shell to reach the
Egbe host (`os.hz.egbe.dev`). If a proxy or allowlist refuses that request
before Egbe answers, for example HTTP 403 on CONNECT or curl status `000`, tell
the founder: they allow that host in this agent's network settings or continue
with an agent on their own computer. Code can also be published without the
shell by committing through the connector (`egbe-os-git`, "Without a terminal").
Until the shell step or that commit and its deploy succeed, do not report the
work as published: a preview in this agent or on this computer is not an Egbe
deployment.


# Design references

Search reference design systems from shipped product sites and retrieve their
concrete values and source attribution. The caller chooses the direction and
scope; a catalog reference is not a mandatory design or approval of a brand.

Authenticate with `Authorization: Bearer $OS_API_KEY`. Mirrored catalog reads,
facets, browsing and lexical search have no per-call charge. Semantic search
uses the caller's wallet-tracked `ai-api` credential: each semantic query pays
for its query embedding, and the caller that starts a cold or refreshed shared
corpus build also pays for embedding the roughly 1,300 catalog entries. A
restart, catalog update or embedding-model change can require that corpus
build again. Check `scorer` in the response; a lexical fallback does not erase
charges for embedding work already attempted.

## Workflow

```
GET /design/facets  ->  POST /design/styles/search  ->  GET /design/styles/{id}/design.md
```

Save the returned markdown as `egbe-docs/product/design-reference.md` when using it
as source material. Keep it distinct from the accepted `product/design.md` direction;
preserve attribution and record the selected style ID/source with the task.

## 1. See what the catalog actually contains

Search is **semantic** (embedding similarity — understands meaning, and other
languages) when your account has an ai-api credential, and **lexical** (token
overlap) otherwise. This is automatic; check the search response's `scorer`
field to see which one answered. For lexical queries specifically, invented
tags match nothing while words that exist in the catalog match well — start
here and reuse these values as query terms either way.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/design/facets?theme=dark&limit=25" -s
```

Returns ranked `fonts` (Inter, Geist Mono, DM Sans…), `colors` (Graphite, Paper
White, Ink Black…) and `themes` with counts.

## 2. Search

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/design/styles/search" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"query":"editorial serif on cream paper","theme":"light","limit":5}'
```

Each hit carries `style_id`, `site_name`, `url`, `theme`, `north_star` (a
one-line description of the visual direction), `fonts`, `colors`,
`thumbnail_url` and `score`. With semantic search, describe surfaces, type and
mood in any language ("тёплый editorial минимализм на кремовой бумаге" works);
with lexical, stick to English words from the catalog's own vocabulary
("near-black canvas, mono labels, one acid accent") rather than a business
category.

Browsing works too, when you already know the constraint:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/design/styles?font=Geist&theme=dark&limit=10" -s
```

## 3. Take the design system

```bash
mkdir -p egbe-docs/product
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/design/styles/$STYLE_ID/design.md" -s  \
 | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["markdown"])' > egbe-docs/product/design-reference.md
```

`GET /design/styles/{id}` returns the same content as JSON when you want to read
specific fields instead of the whole document:

- `colors` — hex + name + **role** ("the one chromatic button in the system")
- `surfaces` — elevation levels with the hex for each
- `typography` / `type_scale` — families, weights, sizes, letter-spacing per role
- `spacing` — page max width, section gap, element gap, card padding, radii
- `components` — spec text per component (button, card, nav, input…)
- `dos` / `donts` — the rules that keep a copy from looking like a knock-off
- `guides` — an "Agent Prompt Guide" with ready component prompts, when present
- `similar` — sibling styles with their `style_id`, for a second opinion

## Errors

Unavailability is always `503` with a typed `data`: `error`, `reason`,
`retryable`, `retry_after_seconds` and the `mirror` status. An empty or
unavailable catalog is never returned as an empty `200` result.

- `data.error: "design_catalog_warming"` — the mirror is still being built on
  a freshly started gateway (first walk is ~1 min). Retry after
  `retry_after_seconds` (~30s); after that it is memory-fast and refreshes daily.
- `data.error: "design_catalog_unavailable"` — facets, search or browse cannot
  be served: the upstream catalog failed and the gateway has no copy. The
  message carries the upstream reason.
  - `reason: "upstream_forbidden"`, `retryable: false` — the upstream refuses
    access (HTTP 401/403). Do not retry. Continue without a catalog reference,
    as below, and tell the user the design catalog is unavailable.
  - Other reasons, `retryable: true` — retry after `retry_after_seconds` (~1 min)
    at most 2–3 times, then continue without a catalog reference.
- `data.error: "design_style_unavailable"` — one style's detail or `design.md`
  could not be fetched and was not cached. Try at most one other result, then
  build from the search result's fonts and colours or continue without a
  catalog reference.
- `422` — `style_id` must be a uuid from a search result.

Continuing without a catalog reference means: use the accepted
`product/design.md` direction, the user's brand or existing product UI, or
references the user supplies; otherwise make a deliberate, restrained choice of
one type pairing, a small named palette with roles and a spacing scale, and
record it as your own decision. Do not present it as a catalog reference, do
not invent a `style_id` or attribution, and do not block the build on the catalog.

When the upstream fails after a copy exists, the gateway keeps serving its last
good copy, including after a restart. `data.availability` in `GET /design`
reports `available`, `state` (`ready`, `stale`, `degraded`, `warming` or
`unavailable`) and `reason`; `degraded` means the copy could not be refreshed.
Search, browse and facets still work from it, and so do style detail and
`design.md` for styles the gateway fetched before.

Semantic search never returns an error of its own: no ai-api credential, a
still-building vector cache, or an embeddings-call failure all degrade silently
to the lexical result for that one request — `scorer` in the response tells you
which one you got.

Catalog content © Refero (`styles.refero.design`), mirrored unmodified and
attributed at the bottom of every downloaded design reference.
