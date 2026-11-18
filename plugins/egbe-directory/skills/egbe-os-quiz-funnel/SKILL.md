---
name: egbe-os-quiz-funnel
description: Implement and verify an accepted interactive quiz, its answer-dependent results, conversion handoffs and measurement.
metadata:
  egbe-when: "Use when implementing an agreed quiz or inspecting reference funnels to resolve a specific UX question."
  egbe-visible: "true"
  egbe-title: "Quiz funnels"
  egbe-description: "Build an interactive quiz with personalized results, booking, signup or payment handoffs and reliable measurement."
  egbe-category: "Marketing & growth"
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


# Quiz Funnel

Implement the accepted experience in the product's application. This skill owns
the executable specification, quiz runtime, integration and technical checks;
it does not choose whether the product needs a quiz or prescribe its UX method.

## Through the Egbe connector

Through the connector alone, you can write the specification, keeping
`quiz.json` in Egbe's artifact store (`egbe-os-quickstart` →
`references/artifact-sync.md` ("Through the Egbe connector")), and change and
publish product code with `egbe-os-git` ("Without a terminal") and
`egbe-os-deploy`.

Through the Egbe connector, compile with `POST /quiz/compile {spec}` (step 2): it
returns the same files `scripts/compile-quiz-spec.py` writes, byte for byte, so
no workspace is needed for compilation. The runtime checks still need a set-up
project workspace: in a persistent project workspace not set up yet, call
`egbe_local_setup`; otherwise tell the founder which step needs it. The runtime
reads the compiler's output, so an uncompiled quiz is not ready to release.

## Start from the task

Reuse the request and accepted project decisions for the audience, questions,
results and intended next action. Resolve only missing or conflicting inputs
needed for the current work; see [inputs](references/inputs.md). Planning,
reference research, local implementation and release are distinct scopes, not
mandatory stages of every request.

For a focused reference investigation, use the optional
[competitor teardown](references/competitor-teardown.md) and its local
[observation contract](references/walk-mechanics.v2.json). Research is not a
compiler prerequisite and need not be repeated to correct an existing quiz.

## Implement the accepted experience

1. Write `egbe-docs/product/quizzes/<quiz-slug>/quiz.json` using the
   [specification contract](references/spec-contract.md). Reuse existing project
   context; no separate approval ledger is required. Check that the bundled
   runtime supports the accepted behavior before choosing it. If it does not,
   explain the mismatch and use the product's implementation path rather than
   silently changing the experience to fit this engine.
2. Compile the specification:

   ```bash
   python3 <skill-root>/scripts/compile-quiz-spec.py \
     --workspace <workspace-root> --quiz-slug <quiz-slug>
   ```

   The compiler writes `QUIZ.md`, `quiz.public.json` and `validation.json`;
   do not edit these outputs by hand. It checks structure, references and
   configured constraints, not whether a claim is true or an experience is good.
   Read diagnostics, especially reachability that could not be verified.

   Without a terminal, such as through the Egbe connector (`egbe_write`), send
   the parsed specification to the same compiler:

   ```bash
   POST $OS_URL/quiz/compile
   {"spec": <contents of quiz.json>, "quiz_slug": "<quiz-slug>"}
   ```

   `quiz_slug` defaults to `spec.quiz_slug`. When ready, `response.data.files`
   maps each output name to its exact text, identical to the script's output,
   and `response.data.report` holds the diagnostics. Write each file unchanged
   into `response.data.folder`. A `422` with `status: not_ready` lists
   `problems`, returns only `validation.json` in `files` and names the page
   files in `delete`: remove those, fix `quiz.json` and compile again. Nothing
   is stored or charged.
3. Bind the runtime to the product's framework following
   [implementation](references/implementation.md). Follow
   [conversion handoffs](references/conversion-handoff.md) for the chosen
   destination and [measurement](references/measurement.md) for event semantics
   and delivery. Keep authentication, checkout and analytics under their existing
   Egbe contracts.
4. Use [verification](references/verification.md) for the changed behavior.
   Local work does not require a commit or deployment. When release is in scope,
   use the product's established release workflow and `egbe-os-deploy`, then
   verify the live route without creating unintended real conversions or
   polluting production analytics.

## Handoff

Keep the quiz folder with the product's source. Return what changed, validation
performed, remaining gaps and the artifact or route the caller can inspect.
Distinguish a local build, a released route and an observed real conversion.

## Scripts and templates from Egbe

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project folder set up for Egbe;
without one, tell the founder that the step needs it and continue with the rest
of the work.

In a set-up project folder, before a step that runs or copies one of them, get
this skill's whole bundle into `.egbe/skills/egbe-os-quiz-funnel/` as
`egbe_workspace_files(group="scripts")` describes: write that group's files,
which include Egbe's request helper, then download this skill's listed archive,
check its SHA-256 and extract it. Never download single files: scripts import
their sibling files and some use other skills' bundles, which come the same way.
When the `scripts` release changes, refresh the bundles already there.

Wherever this skill names a file by its path in the skill (for example `scripts/...`
or `assets/...`), use `.egbe/skills/egbe-os-quiz-funnel/<file>`; where it writes `<skills-directory>`, use
`.egbe/skills`. Run scripts from the project root with
`OS_AGENT_NAME="<your agent name>"` set inline. Where this skill says a script needs
`OS_URL` or `OS_API_KEY` in its environment, start it as
`python3 .egbe/skills/egbe-os-quickstart/scripts/egbe-curl.py --egbe-run <command>`, which loads `.env.local` without
executing it. Keep `.egbe/skills/` out of Git.

Files in the bundle that this plugin leaves out:

- `assets/engine/quiz-engine.d.mts`
- `assets/engine/quiz-engine.mjs`
- `assets/engine/quiz-engine.test.mjs`
- `assets/engine/quiz-history.d.mts`
- `assets/engine/quiz-history.mjs`
- `assets/engine/quiz-history.test.mjs`
- `assets/engine/quiz-reference.test.mjs`
- `assets/reference/index.html`
- `assets/reference/quiz-bootstrap.js`
- `assets/reference/quiz-early-actions.mjs`
- `assets/reference/quiz-first-screen.mjs`
- `assets/reference/quiz-page.mjs`
- `assets/reference/quiz.css`
- `scripts/compile-quiz-spec.py`
- `scripts/prepare-research-identity.py`
