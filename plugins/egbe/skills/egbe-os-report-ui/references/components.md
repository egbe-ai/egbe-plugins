# Composing with egbe-os-report-ui

The [component gallery](../assets/examples/components.html) shows the available
visual forms and working controls. Copy the relevant markup from its editable
region; use unique IDs when combining examples. The
[editorial example](../assets/examples/editorial.html) shows a small composition,
not a required report outline. The ready scaffold contains all shared styles
and behavior.

Choose by information shape: comparable values may benefit from a metric group
or table, an emphasized passage from a surface, and secondary explanation from
details. No card count, navigation or section order is required.

## Prepared classes

All `report-*` components below are included even if the blank scaffold does
not use them. The following daisyUI primitives are also prepared:

- `card`, `card-body`, `table`, `tabs`, `tab`.
- `btn` with `btn-primary`, `btn-secondary`, `btn-ghost`, `btn-sm`, `btn-xs`.
- `badge` with `badge-success`, `badge-warning`, `badge-error`, `badge-info`,
  `badge-neutral`.
- `select`, `select-sm`, `textarea` (bordered by default).

Small utility helpers: `sr-only`, `mb-6`, `mt-4`, `self-start`, `bg-white`,
`border-base-300`, `text-base-content`, `font-normal`, `text-xs`, `w-full`.
Arbitrary Tailwind classes are not generated when editing a report.

## Page composition

- Use the [Egbe wordmark](../assets/egbe-wordmark.svg) as inline SVG or a
  data-URL image inside `.report-brand`. It contains the landing-page letter
  outlines and colors, so no font download is needed.
- `report-container` sets reading width and page spacing;
  `report-container-reading` provides a narrower reading column.
- An optional `report-sidebar` pairs with `report-with-sidebar` on the content
  wrapper. Use real section links; the sidebar becomes horizontal navigation
  on smaller screens.
- `report-title`, `report-intro`, `report-section-title` and `report-prose`
  provide the type hierarchy. `report-eyebrow` is a small overline;
  `report-meta-line` groups metadata; `report-caption` provides secondary text.
- `report-section` separates sections; `report-section-heading` aligns a heading
  and optional control. `report-two-column` gives unequal columns; add
  `report-balanced` for equal columns. Both stack on narrow screens.
- `report-masthead`, `report-masthead-title` and `report-masthead-date` style
  a header; `report-navigation`, `report-panel` and `report-panel-title` style
  section navigation. Navigation accepts ordinary section links or connected
  tab controls; long labels wrap within available width. `report-footer`
  provides a closing row.

## Cards and emphasis

| Form | Markup/classes | Purpose and variants |
| --- | --- | --- |
| General card | `article.card.report-card > .card-body` | Neutral surface for related content; `report-card-heading`, `report-card-title`, `report-caption` style its header. |
| Metric | `.card.report-card.report-metric` inside `.report-metric-grid` | Prominent supplied value, label and note; grid adapts to the number of cards. |
| Priority surface | `section.report-priority-card` | Stronger heading and an optional `report-eyebrow`; its text comes from the caller. |
| Compact callout | `.report-decision` | Icon, text and optional link. This is visual emphasis, not a decision-making instruction. |
| Inset explanation | `.report-insight` | Quieter supporting passage within another block. |
| Proposal accent | `.report-proposal` | Left rule emphasizing supplied proposal text. |
| Action surface | `.report-action-card` | Main copy with `.report-action-title` / `.report-action-copy`, optional `.report-action-side` for a link and note; stacks on narrow screens. |
| Compact summary | `.report-summary-row` | Short title and text on the left, related link on the right. |

General card:

```html
<article class="card report-card">
  <div class="card-body">
    <h2 class="report-card-title">Title</h2>
    <p class="report-caption">Supporting text</p>
  </div>
</article>
```

Metric card (repeat inside `.report-metric-grid`):

```html
<article class="card report-card report-metric">
  <h3 class="report-metric-label">Label</h3>
  <p class="report-metric-value">42</p>
  <p class="report-metric-note">Unit and time basis</p>
</article>
```

Use `.report-large-value` for a prominent standalone value and
`.report-comparison` for related labeled values. `.report-delta` is green:
use it only when that meaning fits; no automatic positive/negative coloring
is inferred from a number.

## Icons, status and buttons

There is no icon font, icon-name API or bundled third-party icon library.
Use inline SVG paths with `viewBox="0 0 24 24"` and `.report-icon` (18 px);
add `.report-icon-lg` for 22 px. The theme supplies stroke, color and line ends.
The gallery includes copyable check, information and arrow examples.

```html
<a class="btn btn-secondary btn-sm" href="#details">
  <svg class="report-icon" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M5 12h14M13 6l6 6-6 6"/>
  </svg>
  View details
</a>
```

Decorative icons beside text use `aria-hidden="true"`. An icon-only control
needs an accessible name; a meaningful standalone SVG needs `role="img"`
and a title or `aria-label`. Status also needs visible text, not just color.

Badges use `badge report-badge` plus `badge-success`, `badge-warning`,
`badge-error`, `badge-info` or `badge-neutral`. Buttons use `btn` with the
prepared variants listed above. Use a link for navigation and a button for a
connected interaction; button styling alone does not implement an action.

## Lists, steps and supporting detail

- A sequence uses `ol.report-roadmap > li > div`, containing a heading and text.
  Numbering is automatic; the caller supplies the sequence.
- A check list uses `.report-checks > .report-check`, with a
  `.report-check-icon` and a text wrapper containing `strong` and `p`.
  Add `report-check-icon-warn` or `report-check-icon-unknown` to the icon wrapper
  for alternative visual states.
- Supporting references use `ul.report-evidence-list > li`, containing a
  labeled link or `strong` and a paragraph. It becomes one column on narrow
  screens. `.report-footnote` separates a short closing note.

```html
<ol class="report-roadmap">
  <li><div><h3>Step title</h3><p>Explanation.</p></div></li>
</ol>
```

## Tables and graphics

Wrap `table.table.report-table` in `.report-table-wrap` so a wide table scrolls
within the page. Retain a caption, header cells and readable row labels.
Use `.report-number` for numeric cells; `.report-table-narrow` removes the
default minimum width for genuinely small tables.

Inline SVG charts use `.report-chart`, with `.report-chart-grid`,
`.report-chart-line`, `.report-chart-point` and `.report-chart-label` as
appropriate. This is styling, not a chart-generation library: the author
computes coordinates from supplied values. Give the chart an accessible
name/description and exact values in nearby text or a table.

### Meters and funnels

Set exact sizes with SVG attributes. For example, a meter with a supplied
percentage needs no generated class:

```html
<div class="report-progress" role="img" aria-label="37.4 percent">
  <svg class="report-meter" aria-hidden="true" width="100%" height="7">
    <rect class="report-meter-fill-accent" width="37.4%" height="7"/>
  </svg>
</div>
```

For related rows, `report-funnel`, `report-funnel-row` and
`report-funnel-track` provide the layout. Place the same SVG inside each track;
`report-meter-fill` and `report-meter-fill-strong` provide alternative fills.
Keep exact values in accessible text as well as the graphic.

## Tabs

Tabs can display supplied sections or related views within a section.
Section names and content belong to the caller.

Place related controls and panels under `[data-report-tabs]`:

- Buttons: `role="tab"` within `role="tablist"`, unique `id`,
  `aria-controls="<panel-id>"`, and `aria-selected="true"` on the initial tab.
- Panels: `role="tabpanel"`, matching `id`, `aria-labelledby="<tab-id>"`,
  and `tabindex="0"`.

Keep panels visible in the source. The runtime hides inactive panels only after
their connections are checked; without JavaScript all content remains readable.
Arrow keys, Home and End move between tabs. An anchor link to an element in
an inactive panel reveals it.

## Expandable details

Use native `<details><summary>…</summary>…</details>` with `report-details`
and a `report-details-content` wrapper. Assign IDs to link targets so ordinary
`href="#detail-id"` links can reach them. The runtime opens enclosing details
when following a link. Printing expands details and shows all tab panels and
filtered rows, then restores the interactive state.

## Copyable text

Give the source text an ID. On a button set `data-copy-target="<source-id>"`
and `data-copy-status="<status-id>"`; provide a status element with `role="status"`.
Use `data-copy-success`, `data-copy-fallback` and `data-copy-label` for localized
messages. See the editorial example for a connected pair.

If local-file clipboard access fails, the runtime displays and selects a
read-only text field for manual copying. The button copies text only; it does
not execute the requested action or transmit data.

## Scoped filters

On a select set `data-report-filter="<container-id>"` and
`data-filter-key="status"`. Inside that container, mark rows
`data-filter-item data-filter-status="<value>"`. An empty select value shows
all rows; multiple controls for one container combine their conditions.

Optionally add `data-filter-count="<container-id>"` and a localized
`data-filter-label` on a live status element. Use explicit labels for controls;
filtering is an aid to reading, not a change to the underlying report totals.
