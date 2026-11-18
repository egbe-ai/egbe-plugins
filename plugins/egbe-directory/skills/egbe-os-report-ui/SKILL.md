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

Without a local copy of this skill (through the Egbe connector), read these
files with `egbe_skill` and their relative paths; a long file comes back in
parts with a `continuation`, to be joined unchanged. To keep the unedited
scaffold in a project repository, the Git skill's commit requests copy it there
with `from_skill` instead of sending its text.

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

## Scripts and templates from Egbe

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project folder set up for Egbe;
without one, tell the founder that the step needs it and continue with the rest
of the work.

In a set-up project folder, before a step that runs or copies one of them, get
this skill's whole bundle into `.egbe/skills/egbe-os-report-ui/` as
`egbe_workspace_files(group="scripts")` describes: write that group's files,
which include Egbe's request helper, then download this skill's listed archive,
check its SHA-256 and extract it. Never download single files: scripts import
their sibling files and some use other skills' bundles, which come the same way.
When the `scripts` release changes, refresh the bundles already there.

Wherever this skill names a file by its path in the skill (for example `scripts/...`
or `assets/...`), use `.egbe/skills/egbe-os-report-ui/<file>`; where it writes `<skills-directory>`, use
`.egbe/skills`. Run scripts from the project root with
`OS_AGENT_NAME="<your agent name>"` set inline. Where this skill says a script needs
`OS_URL` or `OS_API_KEY` in its environment, start it as
`python3 .egbe/skills/egbe-os-quickstart/scripts/egbe-curl.py --egbe-run <command>`, which loads `.env.local` without
executing it. Keep `.egbe/skills/` out of Git.

Files in the bundle that this plugin leaves out:

- `assets/egbe-wordmark.svg`
- `assets/examples/components.html`
- `assets/examples/editorial.html`
- `assets/scaffold.html`
