---
name: egbe-os-design-landing-page
description: Build or repair the product's main public page and prepare a new application foundation.
metadata:
  egbe-when: "Use to implement or repair a main homepage, or prepare a new app for Egbe hosting."
  egbe-visible: "true"
  egbe-title: "Landing pages"
  egbe-description: "Build and publish your main page on Egbe with its approved content, design and working actions."
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


# Main page implementation

Implement the requested public page or bounded repair. Campaign-specific destinations
use `egbe-os-campaign-landing-page`; this skill does not choose an offer, research
an audience or require separate content/design stages.

## Read the accepted input

Read the request, relevant requirements, actual page/code and available approved
content/design. Use [page inputs](references/page-inputs.md) to preserve their
meaning and scope. A PRD or fixed document shape is not a prerequisite to repairing
an existing page. Return material missing/conflicting decisions to the caller;
do not silently change the price, brand, promise or intended action.

## Implement

Follow [application preparation](references/application-preparation.md) before
editing. Preserve an existing framework, repository, storage and deployment.
Use the scaffold only when a new application foundation is needed.

Implement the accepted content and actions with a complete responsive interface.
Exact approved strings and required assets remain intact; arrange them coherently
without turning document headings into mandatory full-width blocks. Complete routine
visual/interaction details within the accepted direction. Use `egbe-os-images`
for requested stock/generation and its current API, not hardcoded provider keys.

Wire each action to the real requested behavior in this application or its valid
destination. Coordinate feature work with `egbe-os-product-build` when needed.
There is no mandatory later Product stage: do not ship a fake interaction, a 404
or an unfinished boundary as if the promised result works.

Discover this project's contact mailbox through authenticated `GET /mail/account`
and use the verified `data.email` in its contact link. Do not invent an address or
substitute `support@egbe.ai`; report a failed/missing mailbox lookup. Include visible
`Created with Egbe`, with Egbe linked to https://egbe.ai.

## Verify and hand off

Use `egbe-os-product-build` → `references/interface-quality.md` for rendered
accessibility, responsive and interaction checks. Run the project's lint/build and
relevant tests; navigate every distinct changed destination, including pricing
choices and bounded same-origin redirects. Confirm actual images/fonts load,
content and metadata are correct, and the actions preserve their context.

Publish only within the requested scope, using `egbe-os-git` and `egbe-os-deploy`
for the same committed revision and live verification. For local-only work, hand
back the diff and evidence. Keep useful page materials under
`egbe-docs/product/pages/homepage/`, without a new spec for every small change.
Report what was proved, remaining dependencies and where to review the result.

## Files downloaded on demand

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project workspace; without one,
tell the founder that the step needs it and continue with the rest of the work.

In a project workspace, before a step that runs or copies one of these files,
download it into `.egbe/skills/egbe-os-design-landing-page/` at the same relative path, for example
`curl -fsSL <url> --create-dirs -o .egbe/skills/egbe-os-design-landing-page/<file>`, and check that its SHA-256
matches. Also download the files it uses from the same folder, such as the
modules a script imports. Wherever this skill names one of these files by its
path in the skill (for example `scripts/...` or `assets/...`), use `.egbe/skills/egbe-os-design-landing-page/<file>`;
where it writes `<skills-directory>`, use `.egbe/skills`.
Keep `.egbe/skills/` out of Git by adding it to `.gitignore`.

| File | URL | SHA-256 |
| --- | --- | --- |
| `assets/scaffold/.dockerignore` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/.dockerignore | `9edf9c8ea71aa771fd9cda65a89dbfdeb24f678abb1552b9918bfa2b4b5632ab` |
| `assets/scaffold/.gitignore` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/.gitignore | `71ad838817dea7f0923afd767de0eee8e5d76e967712dbbc3be01fbb27266427` |
| `assets/scaffold/Dockerfile` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/Dockerfile | `bae7045848fb5167bb8ab2d8135e81f5aa2f0be465fcdb021b988efe2dae1726` |
| `assets/scaffold/eslint.config.mjs` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/eslint.config.mjs | `870f1adccecf3051cbcd9fd307cef51d7633cf510979c181a81f4b1797273493` |
| `assets/scaffold/next.config.ts` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/next.config.ts | `7b651c37a6222dc83e7b3612dd9853829664b6bb4ce3dd9af8b10ef78996b783` |
| `assets/scaffold/package-lock.json` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/package-lock.json | `ece42978c0f7ac05c03e3e49f556478e6f8ef35b2c701a346454f841372a3682` |
| `assets/scaffold/package.json` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/package.json | `afa3397944bf4e488b623ce5c4d2c6f9b39fb56aec0fe146adf2ec09fe996385` |
| `assets/scaffold/postcss.config.mjs` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/postcss.config.mjs | `dfac7ac2d86d326a0e5adb024e7943c181393ed17a5fcb8f0315b24c7da6ddde` |
| `assets/scaffold/public/.gitkeep` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/public/.gitkeep | `01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b` |
| `assets/scaffold/sentry.edge.config.ts` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/sentry.edge.config.ts | `060641f5e4fbd4fa380eef342b721f61a610b0e6056b0689008d6d88672ae8d8` |
| `assets/scaffold/sentry.server.config.ts` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/sentry.server.config.ts | `060641f5e4fbd4fa380eef342b721f61a610b0e6056b0689008d6d88672ae8d8` |
| `assets/scaffold/src/app/global-error.tsx` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/src/app/global-error.tsx | `09e2d1f8f654d2f0c1a2116d23d0dee2f579df0b21e0a9e67d179763ec49cdf9` |
| `assets/scaffold/src/app/globals.css` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/src/app/globals.css | `1dcbce69c95506d6ce8ba3c5412060ecc924aa025413817928df9f2f3365fa2b` |
| `assets/scaffold/src/app/layout.tsx` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/src/app/layout.tsx | `6f25b8b9c4afe5b9aa39ae7d91ef9f03e5b3952024dc4358438596e9c86bd340` |
| `assets/scaffold/src/app/page.tsx` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/src/app/page.tsx | `e5a02eaa1ad18daaf76c9a9968ff24333ec868d392c9af8fda983a9f9969be5f` |
| `assets/scaffold/src/app/privacy/page.tsx` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/src/app/privacy/page.tsx | `f611d919ebf5aafb4478bfff21644f1834448206bdbc1f7d3922c98205b525b3` |
| `assets/scaffold/src/components/egbe-analytics.tsx` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/src/components/egbe-analytics.tsx | `b7f28d15d174d65918d4715b9fb29b0e75fa58e315c1c7db8e1b96c5556ef8e2` |
| `assets/scaffold/src/instrumentation-client.ts` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/src/instrumentation-client.ts | `438276892c9516d311b68c8eab87a2f80f0d4b47377d1b2a6da2df3ed8b0f595` |
| `assets/scaffold/src/instrumentation.ts` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/src/instrumentation.ts | `4a351bb98c1ab7fed481670c78277c9321e014cb6d8aeaf73a6649d3611708df` |
| `assets/scaffold/src/lib/egbe-observability.generated.ts` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/src/lib/egbe-observability.generated.ts | `421aa422310a5a356ed02b16ea2251107e104d7d286d605043f45d06e416732b` |
| `assets/scaffold/src/lib/utils.ts` | https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/src/lib/utils.ts | `7c8c3dfc0cdd370d44932828eb067ef771c8fe7996693221d5d4b90af6d54f2d` |
