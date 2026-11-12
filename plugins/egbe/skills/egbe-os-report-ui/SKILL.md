---
name: egbe-os-report-ui
description: Style supplied report content as offline HTML with shared UI components.
metadata:
  egbe-when: "Use when an existing report needs a readable visual presentation."
  egbe-category: "Business operations"
  egbe-visible: "false"
  egbe-title: "Report presentation"
  egbe-description: "Package findings and plans into clear, self-contained HTML reports with Egbe's shared design components."
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


# Report UI

Render the caller's content as a readable, self-contained HTML document.
The caller owns the data, subject matter, conclusions, recommendations and chat
summary; this skill owns visual composition and HTML packaging.

## Compose for reading

Treat the supplied content as meaning to present, not markup to translate.
Before choosing components, identify its primary message, supporting information
and reference detail. Give them distinct visual weight and reading order.
The first screen should communicate the primary message and key information
without requiring the reader to work through explanatory paragraphs.

Separate labels, values, states and proposed actions from explanatory prose.
Use proximity, contrast, typography and whitespace to show their relationships;
a reader scanning headings and prominent elements should get the main picture.
Reserve continuous prose for explanations that need it. Choose visual forms
by information shape rather than decorating each paragraph with a card.
Group related detail and use disclosure or navigation when it reduces reading
effort. Small reports may need neither. Avoid competing copies of the overview.

You may shorten labels, combine repeated phrasing and reorganize prose while
preserving meaning, exact values, priorities and links. Keep important caveats
with the claims they qualify and supporting detail reachable. If the content
needs a different conclusion or substantive deletion, return that decision
to the caller rather than silently changing it during rendering.

## Create the HTML

1. Copy [the ready scaffold](assets/scaffold.html) to a new report file.
   It already contains the Egbe theme, logo, interactions and offline policy.
   No build, package installation or server is needed.
2. Update `<title>` and `<html lang>`, then replace the markup between
   `<!-- REPORT_CONTENT_START -->` and `<!-- REPORT_CONTENT_END -->`.
   Keep the embedded `<style>`, shared `<script>` and policy metadata unchanged;
   edit the content region rather than rewriting those large blocks.
3. Read [the component guide](references/components.md) for available components
   and their markup. Open the [gallery](assets/examples/components.html) to
   compare their appearance; its editable region contains complete examples.
   The [editorial example](assets/examples/editorial.html) shows a small
   composition. These are references, not required report sections.

Use semantic headings and controls for the chosen composition. Escape external
text before inserting it; do not paste fetched HTML as report content.

Styles are already prepared: use the documented classes and interaction hooks.
For charts and data-dependent dimensions use inline SVG attributes, not new
Tailwind classes or inline styles. Embed images as data URLs or inline SVG.
Ordinary links to supporting material are allowed.

## Check and deliver

Verify the actual output in the available browser. Prefer `file://` with the
network unavailable when supported; a loopback-only preview is suitable for
visual checks when the browser permits only HTTP. Do not expose the workspace
or credentials directory. Check desktop and narrow layouts, links, used
interactions, keyboard access and print. Verify that the report remains readable
if JavaScript is disabled. Record unavailable checks separately: an HTTP preview
does not prove offline file opening. Inspect embedded assets and the absence of
external runtime requests as an additional packaging check, not a substitute
for the checks that could not run.
Check the actual reading experience: without reading the paragraphs, can the
reader identify the main message, key information and where to go next?
Then check that supporting explanations are easy to reach. Fix
competing emphasis, dense text blocks, awkward wrapping and page-wide overflow.
Confirm that visual compression has not changed or concealed substantive content.

Return a local link to the HTML file.

Keep preview fixtures separate from real reports; do not publish a report or
change the underlying product as part of rendering it.
