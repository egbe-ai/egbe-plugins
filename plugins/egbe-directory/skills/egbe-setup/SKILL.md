---
name: egbe-setup
description: Set up Egbe for the founder's business through the Egbe connector. Use when the founder asks to set up, connect or start using Egbe.
---

**If the `egbe_*` tools are missing.** The plugin's Egbe connector isn't signed
in yet: installing the plugin doesn't sign in. Ask the founder to connect their
Egbe account before setup continues, in a short message in their language:

- Say that this is a one-time step.
- Number the steps: open the sign-in, sign in to Egbe and select **Connect**.
  Egbe's page doesn't ask for a business, so don't ask them to choose one there.
- Say what happens afterwards and what to reply.
- End with one line on what the connection allows: it covers all their Egbe
  businesses, including ones they start later, and in each conversation Claude
  works on the business they name; the Egbe team can read what Claude does in Egbe to
  support them and improve Egbe, and they can disconnect Claude anytime under
  [connected AI assistants](https://dashboard.egbe.ai/settings/connections).

Give a sign-in address as a link with a short label, such as **Sign in to
Egbe**, never as a bare address. Leave out its parameters, local callback
addresses and fallbacks the founder doesn't need yet.

- In Claude Code on their computer, when a sign-in tool for `plugin:egbe:egbe`
  is available, such as `mcp__plugin_egbe_egbe__authenticate`, call it.
  If the address it returns starts with
  `https://dashboard.egbe.ai/oauth/authorize?` and this session runs on the
  founder's own computer, open it once in their default browser: `open` on
  macOS, `xdg-open` on Linux, `cmd.exe /c start "" "<address>"` on Windows,
  passing the address as one quoted argument. Don't open it in a remote session,
  such as one with `SSH_CONNECTION` or `CLAUDE_CODE_REMOTE` set or Linux without
  `DISPLAY` or `WAYLAND_DISPLAY`, and never open any other address this way. In
  the message, say that you opened Egbe's sign-in page and still link the
  address in case it didn't open; without opening, just link it.
  After approval the browser confirms the sign-in and
  Egbe's tools become available in this session: ask the founder to reply when
  they're done, not to start a new session. Only if they say the browser couldn't
  connect after approval, ask them to paste the full address from its address
  bar and finish with the matching completion tool. Without a sign-in tool, ask
  them to run `/mcp`, select `plugin:egbe:egbe` and sign in.
- In claude.ai, the Claude app, Cowork and Claude Code cloud sessions: open
  **Customize → Plugins → Egbe → Connectors** and select **Connect**. The first
  time, Claude shows **Add custom connector**: keep its settings and select
  **Add**. When the connector shows **Not connected**, select **Connect** again,
  sign in to Egbe and approve the connection. Then start a new conversation.

Don't call Egbe unavailable before this step, and don't reach Egbe from the shell
instead.

# Set up Egbe through this connection

You are connected to the founder's Egbe project through MCP. If this result names
a `business`, pass it to every later egbe_read, egbe_write, egbe_local_setup and
egbe_complete_setup call.

This setup runs from the Egbe plugin, which provides Egbe's skills in every
session. Read those skills and their files from the plugin; use `egbe_skill`
only for what the plugin lacks, such as `egbe-os-quickstart` below. In step 2,
set up a persistent project workspace that is not set up yet as
[project setup](references/project.md) describes. It still calls `egbe_local_setup`
and keeps the standard project setup, including saved credentials, playbooks,
session logging and the Business Loop, but installs no skills. A project that
already has its own installed Egbe skills uses those rather than the plugin's
copies.

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
     use the saved credentials and the installed skills, or `egbe_skill` where
     none are installed, and continue with what the founder asked.
     If it has `egbe-docs/egbe-workspace.json` and its saved `releases` differ
     from this result's `releases`, first update its files as
     `egbe_workspace_files` describes.
   - **Persistent project workspace not set up yet:** call `egbe_local_setup` and
     follow its result instead of the steps below. Through your own file tools
     and this connection, with no Egbe installer or script, the workspace gets
     saved credentials, project playbooks and guidance, logging authorization
     and the Business Loop offer; skills stay readable with `egbe_skill`. If it refuses, mention the reason once and
     continue below.
   - **Otherwise:** continue below. This path needs no installation, API key,
     curl, shell command or local file.
3. **Understand the project.** `project.limits` is the verified availability of
   this project. An unused zero allowance (`max_allowed: 0`, `current: 0`) means
   unavailable, not exhausted. Mention a limit only if it affects requested work
   or the next step. Review the context you already have, such as notes, to
   recommend where to continue. Do not run a full audit.
4. **Offer useful follow-through.** Use the founder's goal and project evidence
   with `egbe_skill(name="egbe-os-quickstart", resource="references/offer-loop.md")`
   to recommend a preset or custom loop. Discuss the choice in this chat; keep
   ongoing work in a workspace with persistent access to the project.
5. **Finish.** Call `egbe_complete_setup` once, then give a concise handoff in the
   first person: what you can do with Egbe, a compact capabilities table and the
   concrete next step. If no product idea exists yet, start that conversation
   now with an easy question about the founder's experience, interests or the
   people they can reach. If the founder asked to finish without questions, ask
   none: give the next step and what you will prepare, and keep any question for
   a later reply.

For any later Egbe work, use its advertised `name` from the skills list with
`egbe_skill` and perform
its API steps with `egbe_read` (GET) and `egbe_write` (other methods). Connection alone does not authorize
development, publishing, spending, outreach or recurring work; ask the founder
for the missing decision.

To start another business, call `egbe_create_business` with the name the founder
chose, only when they ask for one or agree to it, then set it up with
`egbe_setup` and the `business` it returns.
