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

<!-- egbe-connector-todo: quiz-compile. Replace this paragraph when Egbe serves the quiz compiler as an API route. -->
The compiler (`scripts/compile-quiz-spec.py`) and the runtime checks need a
set-up project workspace: in a persistent project workspace not set up yet, call
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

## Files downloaded on demand

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project workspace; without one,
tell the founder that the step needs it and continue with the rest of the work.

In a project workspace, before a step that runs or copies one of these files,
download it into `.egbe/skills/egbe-os-quiz-funnel/` at the same relative path, for example
`curl -fsSL <url> --create-dirs -o .egbe/skills/egbe-os-quiz-funnel/<file>`, and check that its SHA-256
matches. Also download the files it uses from the same folder, such as the
modules a script imports. Wherever this skill names one of these files by its
path in the skill (for example `scripts/...` or `assets/...`), use `.egbe/skills/egbe-os-quiz-funnel/<file>`;
where it writes `<skills-directory>`, use `.egbe/skills`.
Keep `.egbe/skills/` out of Git by adding it to `.gitignore`.

| File | URL | SHA-256 |
| --- | --- | --- |
| `assets/engine/quiz-engine.d.mts` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/engine/quiz-engine.d.mts | `426fb25b7cec91d72570a398987d2c7c284f96acadeb1ac1a377a83cd08325b6` |
| `assets/engine/quiz-engine.mjs` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/engine/quiz-engine.mjs | `ea898ed24ed95e81f98e8939bf9234f423d05ef9c4572be45f3b0a9aacf589ef` |
| `assets/engine/quiz-engine.test.mjs` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/engine/quiz-engine.test.mjs | `68f0b9a8b3781e4fa3659e814da2290857febb0d6db224ce42abfcdea9d76c8e` |
| `assets/engine/quiz-history.d.mts` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/engine/quiz-history.d.mts | `f0b08105cac6f973973b8caf8f06465cdd837739c03d26bca91c071236405ce9` |
| `assets/engine/quiz-history.mjs` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/engine/quiz-history.mjs | `f751218e891490bf5ba7665a3e5ff518c087bb4b529a74903c500289333f624b` |
| `assets/engine/quiz-history.test.mjs` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/engine/quiz-history.test.mjs | `c4d9eabf2d48ddddfa1848188970682afb86b97643c4e63ee3324171799cef35` |
| `assets/engine/quiz-reference.test.mjs` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/engine/quiz-reference.test.mjs | `6daf3e33d46ac527970a57c6078987d0c8abdf06c759de1c01a06f0c61369d32` |
| `assets/reference/index.html` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/reference/index.html | `ca4f019c5ac1a115b173e02396e4953633db30965badc211de17dd8748d446ee` |
| `assets/reference/quiz-bootstrap.js` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/reference/quiz-bootstrap.js | `774722451dc76095084ade669c97ee06a646363cc133abb55f36111a01a849a6` |
| `assets/reference/quiz-early-actions.mjs` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/reference/quiz-early-actions.mjs | `3ae7433033fb2128ce9ef1d69c522cb1d723ec3b806e886be2371ad2a118d982` |
| `assets/reference/quiz-first-screen.mjs` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/reference/quiz-first-screen.mjs | `a1be9874f944d16381174532737338d90751dd519aab7ee8a50b300480758a3b` |
| `assets/reference/quiz-page.mjs` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/reference/quiz-page.mjs | `5807e2378bb2bae0a2fbc5cf71dc24d96f96325d8bef82480267d5c13ac9edef` |
| `assets/reference/quiz.css` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/assets/reference/quiz.css | `db5a24036257c73abcd6653baba0fca75f80c3e529dfaa8da08934c1caf7edb7` |
| `scripts/compile-quiz-spec.py` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/scripts/compile-quiz-spec.py | `02815107081b323b258e6bfd3b7e197f8ff0e388133d75936022c8164046aa6d` |
| `scripts/prepare-research-identity.py` | https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/scripts/prepare-research-identity.py | `e8405b1ff02878ee88182ecad327d97e067b0f2a08ed9676a80e103dc9bdb2d3` |
