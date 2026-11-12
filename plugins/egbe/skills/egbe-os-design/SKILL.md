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

- `503` — the mirror is still warming on a freshly started gateway (first walk
  is ~1 min). Retry in ~30s; after that it is memory-fast and refreshes daily.
- `422` — `style_id` must be a uuid from a search result.
- `502` — the upstream catalog is unreachable and we have no cached copy.

Semantic search never returns an error of its own: no ai-api credential, a
still-building vector cache, or an embeddings-call failure all degrade silently
to the lexical result for that one request — `scorer` in the response tells you
which one you got.

Catalog content © Refero (`styles.refero.design`), mirrored unmodified and
attributed at the bottom of every downloaded design reference.
