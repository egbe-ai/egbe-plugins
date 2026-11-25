---
name: egbe-os-loop-engineering
description: Save and improve a business's own loops in its Dashboard. Use when the founder describes recurring work, the agent identifies a repeatable decision in project work, or a loop's decision method needs to change.
metadata:
  egbe-when: "Use when project work reveals a recurring decision or the founder wants to design or adapt a loop. Use product-routines to run a loop already chosen."
  egbe-visible: "true"
  egbe-title: "Design your own loop"
  egbe-description: "Turn a recurring decision into a loop for your business and improve it as results come in."
  egbe-category: "Business operations"
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

The harness can also refuse a step before Egbe answers: a denied file read or
command (`EPERM`, `operation not permitted`), a certificate error, or a connector
call that fails as a whole with HTTP 403. Egbe's own refusals of an API request
come back as a result with a `status` and Egbe's `message`, and the `egbe_skill`
tool never answers 403. Egbe refuses a whole call with 403 only for a browser
`Origin` it does not accept, so such a 403 most likely comes from the harness, a
proxy or a policy in front of Egbe. Don't retry it in a loop, route around it or
disable certificate verification. If `egbe_skill` was refused, read that skill
from an installed Egbe catalog or plugin copy, if this session has one. Name the
blocked file, command, host or tool and ask the founder to allow it, or to trust
the host through the environment's network setting. Then continue the work that
doesn't need it and say what waits on that permission. While `egbe_skill` works,
`egbe-os-quickstart`'s `references/environment.md` lists these cases.


# Design a business loop

Use the project's goals, playbooks, plans and evidence. When the work reveals a recurring decision and you can explain how different observations change the next action, save the method in this business's Dashboard on your own initiative. The founder can also describe the task in ordinary language. Keep work local if the founder asks only for discussion, a draft or offline work.

Look for a match in the business's saved loops (`GET /loops`) and in `egbe-os-product-routines` → `references/presets/index.json`. Reuse a loop that already covers the decision. A project's audience, budget or first check belongs in that loop's launch plan. Save a business version when the project calls for different decisions, actions or owners, when the founder explicitly wants their own copy, or when they accept a preset through "Offer a Business Loop" in `egbe-os-product-routines` → `references/run-preset.md`. Read the original before adapting it.

## From conversation to diagram

- Find one result the founder cares about, the observation that would change the next action, and when that observation becomes meaningful. Ask for a missing decision that changes the design. Offer a grounded starting point when the project already answers it.
- Walk through two plausible outcomes with the founder's examples. “Few suitable buyers replied” can change the audience; “mail was not delivered” calls for a delivery check. If evidence is thin, identify what to observe and when to return. Specify who owns public actions and which changes require new authority or spend.
- Group steps by the question they answer for the founder. Start a new entry in `stages` when one group produces a result the next group uses. For example, selecting qualified replies yields a shortlist. Deciding which offer to test with those buyers uses that shortlist. Give each stage a title that makes the handoff clear. Checks and alternative outcomes that answer the same question belong together. One stage is enough when the whole loop makes a single decision.
- Link each outcome to the step it actually leads to, including across stage boundaries. Point a return to the step that should run again. When revising a loop, check whether a new decision introduces a distinct result that deserves its own stage.
- Give each visible step a short action and each decision card a useful response. Founders read `label`, `description`, `bullets` and `example` on the diagram. Say what they can observe and what changes for the business. Put procedures for the agent, queries and evidence checks in `agentInstructions`.
- Use `terms.budget` for the scope the founder agrees to, such as work covered, time available or a spending cap. Write a short statement in the founder’s language and name whoever makes a decision. For example, “Raising the spending cap requires the founder’s approval.”
- Mark a material limit or decision still under discussion as proposed or open. Describe a value as agreed only after the founder confirms it. Put instructions for carrying out the agreement in `agentInstructions`.
- Distinguish the end of a run from a recoverable failure. For a failure, show which activity pauses, where diagnosis and repair happen, and what evidence allows it to resume under the agreed limits.
- Use the [storage contract](references/save-loop.md) as soon as the first usable definition is ready. Read back the saved revision, share its Dashboard link and explain one concrete branch. Record open launch decisions as proposals. Starting work, enabling a schedule and spending money require the applicable founder agreement.

## Improve a working loop

At review time, compare what the loop predicted with what happened. A new observation can select an existing branch. Repeated evidence that the method misses something can justify a change to the definition. For example, qualified buyers who consistently get stuck after a demo may need an internal approval step before a pilot. Add that step with a signal to check on the next group. Record the evidence and reason with the revision; keep the agreed budget, pause state and owners. If the change needs broader authority, ask the founder for that decision.

For an actual launch or scheduled continuation, use **egbe-os-product-routines**, resource `references/run-preset.md`, with the saved business command. If the founder only wants a draft or rehearsal, return the plan and indicate which actions would follow their agreement.
