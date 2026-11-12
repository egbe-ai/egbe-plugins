---
name: setup
description: Set up Egbe for the founder's business through the Egbe connector. Use when the founder asks to set up, connect or start using Egbe.
---

# Set up Egbe through this connection

You are connected to the founder's Egbe project through MCP. If this result names
a `business`, pass it to every later egbe_request, egbe_local_setup and
egbe_complete_setup call.

This setup runs from the Egbe plugin, which provides Egbe's skills in every
session. Read those skills and their files from the plugin; use `egbe_skill`
only for what the plugin lacks, such as `egbe-os-quickstart` below. Step 2 is
unchanged: a persistent project workspace still gets the standard setup through
`egbe_local_setup`, including the project's playbooks, saved credentials and
session logging. Once a project has its own installed Egbe skills, use those
rather than the plugin's copies.

1. **Introduce Egbe.** Read
   `egbe_skill(name="egbe-os-quickstart", resource="references/introduction.md")` and the
   `skills` list in this result. Give the founder a warm, compact introduction in
   their language: what you can now do for their business with Egbe. Describe
   platform capabilities, not an already configured business.
2. **Choose where setup lives.** Establish from the environment context or native
   documentation whether you work in a persistent project workspace: a project
   folder whose files and configuration persist across sessions, where you can
   run commands and reuse project-scoped skills and instructions. A chat's
   temporary execution environment, a terminal alone or this connection does not
   establish one; do not create one through installation or plugins.
   - **Workspace already set up for Egbe** (saved Egbe credentials or an
     installed Egbe catalog): this is not a new setup. Skip `egbe_local_setup`,
     use the installed skills and saved credentials, and continue with what the
     founder asked.
   - **Persistent project workspace not set up yet:** call `egbe_local_setup` and
     follow its result instead of the steps below. The workspace gets the same
     skills, project playbooks, credentials, logging authorization and Business
     Loop offer as the instruction-based connection. If it refuses, mention the reason once and
     continue below.
   - **Otherwise:** continue below. This path needs no installation, API key,
     curl, shell command or local file.
3. **Understand the project.** `project.limits` is the verified availability of
   this project. An unused zero allowance (`max_allowed: 0`, `current: 0`) means
   unavailable, not exhausted. Mention a limit only if it affects requested work
   or the next step. Review the context you already have, such as notes, to
   recommend where to continue. Do not run a full audit.
4. **Offer useful follow-through.** Clarify the nearest business goal and material
   constraints from known context, asking only what could change the next step.
   Offer a Business Loop at a useful, agreed cadence: review progress, propose
   useful work and follow agreed actions through to their results. Before
   scheduling, follow
   `egbe_skill(name="egbe-os-product-routines")` and verify persistent access to the
   project's current methods, decisions and work. Create or migrate a schedule
   only after the founder agrees; preserve existing owners and disables. If
   context cannot persist or scheduling/delivery is unavailable, offer a manual
   review and help move ongoing work to a supported project workspace. A connected
   chat alone does not establish continuing background work.
5. **Finish.** Call `egbe_complete_setup` once, then give a concise handoff in the
   first person: what you can do with Egbe, a compact capabilities table and the
   concrete next step. If no product idea exists yet, start that conversation
   now with an easy question about the founder's experience, interests or the
   people they can reach.

For any later Egbe work, use its advertised `name` from the skills list with
`egbe_skill` and perform
its API steps with `egbe_request`. Connection alone does not authorize
development, publishing, spending, outreach or recurring work; ask the founder
for the missing decision.
