---
name: egbe-os-design
description: Search real product design references (styles, screens, user flows) and retrieve concrete design systems for interface work.
metadata:
  egbe-when: "Use for interface design; offer when inconsistent visuals need a coherent reference."
  egbe-visible: "true"
  egbe-title: "Design systems"
  egbe-description: "Give your product a consistent visual language and proven page layouts using real design systems, screens and user flows."
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

The harness can also refuse a step before Egbe answers: a denied file read or
command (`EPERM`, `operation not permitted`), a certificate error, or a
connector call that fails as a whole with HTTP 403. Egbe's own refusals of an
API request come back as a result with a `status` and Egbe's `message`, and the
`egbe_skill` tool never answers 403. Egbe refuses a whole call with 403 only for
a browser `Origin` it does not accept, so such a 403 most likely comes from the
harness, a proxy or a policy in front of Egbe. Don't retry it in a loop, route
around it or disable certificate verification. If `egbe_skill` was refused, read
that skill from an installed Egbe catalog or plugin copy, if this session has
one. Name the blocked file, command, host or tool and ask the founder to allow
it, or to trust the host through the environment's network setting. Then
continue the work that doesn't need it and say what waits on that permission.
While `egbe_skill` works, `egbe-os-quickstart`'s `references/environment.md`
lists these cases.


# Design references

Search references from shipped products and retrieve their concrete values and
source attribution:

- **styles**: a visual direction distilled into a design system (colours with
  roles, typography, layout, components, section recipes, do/don't rules);
- **screens**: how a real product laid out one concrete page or state;
- **flows**: how a real product sequenced a multi-step journey.

The caller chooses the direction and scope; a catalog reference is not a
mandatory design or approval of a brand.

Authenticate with `Authorization: Bearer $OS_API_KEY`. There is no per-call
wallet charge. Each call that reaches the catalog counts against the business's
daily `design-references:calls` allowance (`GET /me/limits?resource=design-references`);
repeated searches and details the gateway already holds are not counted, so
reuse ids instead of searching again.

## Workflow

```
POST /design/styles/search  ->  GET /design/styles/{id}/design.md      (visual direction)
POST /design/screens/search ->  GET /design/screens/{id}               (one per key page)
POST /design/flows/search   ->  GET /design/flows/{id}                 (multi-step journeys)
```

Save the chosen style's markdown as `egbe-docs/product/design-reference.md` when
using it as source material. Keep it distinct from the accepted
`product/design.md` direction; preserve attribution and record the selected
style, screen and flow ids with the task.

Search is semantic: describe surfaces, type and mood (styles), or the concrete
UI problem (screens, flows), in plain words; any language works. The catalog
has no filters: write constraints such as "dark theme", "Geist font" or
"one acid accent" into the query. Results come 10 per page; pass `page` for
more.

## 1. Pick a visual direction

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/design/styles/search" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"query":"editorial serif on cream paper, warm and calm","limit":5}'
```

Each hit carries `style_id`, `name`, `site_name`, `url`, `north_star` (the
visual direction in a sentence), `fonts`, `colors` (`name`, `hex`) and
`thumbnail_url`. Pagination is in `page`, `next_page`, `total` and `total_pages`.

## 2. Take the design system

```bash
mkdir -p egbe-docs/product
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/design/styles/$STYLE_ID/design.md" -s  \
 | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["markdown"])' > egbe-docs/product/design-reference.md
```

`GET /design/styles/{id}` returns the same system as JSON when you want to read
specific fields instead of the whole document:

- `north_star`, `essentials` — the direction and the handful of rules that make it;
- `colors` — `token`, `name`, `hex`, `group`, `usage` and where each is used;
- `fonts` — `role`, `family`, `use`, a free `substitute` and a `fallback` stack;
- `dos` / `donts` — the rules that keep a copy from looking like a knock-off;
- `design` — every section as Refero wrote it: `typography` (styles per role),
  `layout`, `corner_radius`, `surfaces_and_depth`, `components`,
  `imagery_and_graphics`, `section_recipes`, `page_flow`, `writing`,
  `motion_and_responsive`.

Use the substitutes for licensed fonts unless the user owns them, and do not
reuse the source's names, logos, artwork or copy.

## 3. Lay out each key page from a real screen

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/design/screens/search" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"query":"pricing page with three plans and a yearly toggle","platform":"web","limit":5}'
```

`platform` is `web` (default) or `ios`. Each screen carries `screen_id`,
`site_name`, `page_url`, `refero_url`, `thumbnail_url`, `colors`, `page_types`,
`ux_patterns`, `ui_elements`, `description` and the `flows` it belongs to.

- `GET /design/screens/{id}` adds `layout`, `functions`, `fonts` and `preview_url`.
- `GET /design/screens/{id}/similar?limit=5` returns comparable screens.
- `GET /design/screens/{id}/image?size=thumbnail|full` returns the screenshot as
  `b64` with `mime_type`, when you need to look at it; `thumbnail_url` is a
  public image and needs no call.

Take structure, hierarchy, states and copy patterns from screens; take the
visual language from the chosen style.

## 4. Sequence journeys from a real flow

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/design/flows/search" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"query":"signup and first-run onboarding","platform":"web","limit":3}'
```

`GET /design/flows/{flow_id}` returns `problem`, `related_queries` and every
step with `name`, `screen_id`, `goal`, `action`, `system_response` and its
screen description. Use it for step count, entry and exit states, decision
points and recovery paths, not for visual style.

## Errors

Every failure is typed in `data`; an unavailable reference is never an empty
`200` result.

- `503`, `data.error: "design_catalog_unavailable"`, with `reason`,
  `retryable`, `retry_after_seconds` and `upstream` status:
  - `reason: "upstream_forbidden"` or `"not_configured"`, `retryable: false` —
    the catalog refuses this gateway or is not set up. Do not retry. Continue
    without a catalog reference, as below, and tell the user the design catalog
    is unavailable.
  - `reason: "upstream_rate_limited"` or `"upstream_error"`, `retryable: true` —
    retry after `retry_after_seconds` at most 2–3 times, then continue without a
    catalog reference.
- `429`, `data.error: "design_quota_exceeded"` — this business used its daily
  allowance; `resets_at` says when it returns. Continue from references already
  fetched (they stay readable) or without a new reference. Do not loop.
- `404`, `data.error: "design_reference_not_found"` — the id is unknown; use an
  id from a search result on this gateway.
- `410`, `data.error: "design_route_retired"` — `GET /design/facets` and
  `GET /design/styles` no longer exist; search instead.
- `422` — a style or screen id must be a uuid, a flow id a positive integer,
  `platform` `web` or `ios`.

Continuing without a catalog reference means following
[Designing without the catalog](#designing-without-the-catalog) below: the same
best-effort quality bar, built from the accepted `product/design.md`, the
user's brand, references they supply, ids fetched earlier and real products you
can study, recorded as your own design. Do not invent an id or attribution, and
do not block the build on the catalog.

When the catalog fails after the gateway has fetched a style, screen or flow,
that copy keeps being served, including after a restart. `GET /design` reports
`availability` (`available`, `state`: `ready`, `checking` or `unavailable`,
`reason`).

## Designing without the catalog

Use this when the design catalog cannot answer: `503 design_catalog_unavailable`
after the allowed retries, `429 design_quota_exceeded`, or no useful result for
the product. The bar does not drop: aim for the best design you can make for
this product and audience, as distinctive and finished as one built from a
reference. The catalog is a source of examples, not the source of quality.

### 1. Collect what already exists

In this order, and use everything that applies:

1. The accepted `egbe-docs/product/design.md` direction. If it exists, it rules;
   use the steps below only for what it leaves open.
2. The user's brand: logo, colours, fonts, tone, existing product UI or
   marketing pages. Extend them; do not replace them.
3. References the user supplies, and catalog ids fetched earlier for this
   project: `GET /design/styles/{id}`, `/design/screens/{id}` and
   `/design/flows/{id}` keep answering from the gateway's copy during an outage.
4. Real products you can open: the competitors and adjacent products from the
   project's research, and well-designed products in the same category. Study
   how they structure pages, sequence onboarding and present pricing and proof.
   Take structure and patterns, never their names, logos, artwork or copy.

### 2. Decide the direction

Write down, before any styling:

- who the product is for, what they must feel and do on the first screen;
- three to five adjectives for the personality, and what it must not look like;
- one signature idea that makes the product recognisable: a type treatment, a
  colour, a layout motif, an illustration or photography style, a motion detail.

Pick the direction that best serves the audience and the product's job, not
the safest or the most generic one.

### 3. Build the system

Make every value concrete; an agent building pages must not have to interpret prose.

- **Typography:** families you may use (open licence, the user's own, or system
  stacks) with roles: display, text, and mono or accent if the product needs
  them. A type scale per role: size, weight, line height, letter spacing, for
  desktop and mobile.
- **Colour:** a neutral ramp (canvas, surfaces, borders, text levels), the
  brand or accent colours with what each is for, and semantic colours (success,
  warning, error, info). Check contrast: at least 4.5:1 for body text and 3:1
  for large text and interface controls. Define dark mode only if the product
  needs it.
- **Layout and spacing:** a spacing scale on a 4 or 8 px base, container widths,
  grid and breakpoints, section rhythm, corner radii, borders, shadows and
  elevation levels.
- **Components:** navigation, buttons (each variant with hover, focus, pressed
  and disabled), inputs with validation, cards, tables or lists, modals, toasts,
  footer, and the empty, loading and error states of each data view.
- **Imagery and icons:** one icon set, the image or illustration style, how
  images are cropped and framed, and what to show when there is no image.
- **Motion:** what moves, durations and easing, and the reduced-motion behaviour.

### 4. Structure pages and journeys

For every key page: its job, the sections in order, the hierarchy within each,
and the primary action. For multi-step journeys (signup, onboarding, checkout):
the steps, the entry and exit points, decisions, validation and recovery from
errors. Design from the product's jobs and the user's task, not from a template.

### 5. Record it

Write the direction and the system into `egbe-docs/product/design.md` using the
same headings as a catalog reference (overview, colours, typography, layout,
components, imagery, page recipes, do/don't), so later skills read it the same
way. Mark the source as your own design, list what it was derived from (brand,
user references, products studied), and do not invent a catalog id or attribution.

### 6. Verify the rendered result

Build, render and screenshot the key pages at desktop and mobile widths, check
them with `egbe-os-product-build` → `references/interface-quality.md`, and
iterate until they meet the direction. Tell the user the design catalog was
unavailable and that the design is your own; when the catalog is back, a
reference can still be used to refine it.

Content © Refero (refero.design), attributed at the bottom of every downloaded
design reference.
