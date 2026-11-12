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


# Quiz Funnel

Implement the accepted experience in the product's application. This skill owns
the executable specification, quiz runtime, integration and technical checks;
it does not choose whether the product needs a quiz or prescribe its UX method.

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
