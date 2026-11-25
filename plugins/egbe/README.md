# Egbe for Claude

Egbe is an AI co-founder's business stack. This plugin connects Claude to the
business you run with Egbe, so Claude can build, launch and grow it for you:
hosting and databases, email, analytics, payments, advertising, market research,
web search and scraping, and an LLM, all billed to your Egbe wallet.

## Get started

1. Install the plugin:
   - In Claude Code 2.0.20 or later: `claude plugin marketplace add
     egbe-ai/egbe-plugins`, then `claude plugin install egbe@egbe`.
   - In claude.ai, the Claude app or Cowork: **Customize → Plugins → Add → Add
     marketplace → Add from a repository**, enter `egbe-ai/egbe-plugins`,
     select **Sync**, then **Add** on Egbe. To get updates automatically, grant
     the Claude GitHub App access when Claude asks, then turn on **Sync
     automatically**.
2. Ask Claude to set up Egbe, or run `/egbe:egbe-setup` in Claude Code.
3. Connect the plugin's Egbe connector once: sign in to Egbe and approve the
   connection. It covers all your Egbe businesses; in each conversation Claude
   works on the business you name.
   - In Claude Code on your computer, Claude opens Egbe's sign-in page in your
     browser the first time it needs Egbe (Claude Code may ask you to allow
     this) and also gives you the link. After you approve, the browser confirms
     the sign-in and Claude continues in the same session. You can also run `/mcp` and
     authenticate `plugin:egbe:egbe`.
   - In claude.ai, the Claude app, Cowork and Claude Code cloud sessions, adding
     the plugin doesn't sign you in: open **Customize → Plugins → Egbe →
     Connectors** and select **Connect**. The first time, keep the settings in
     **Add custom connector** and select **Add**, then select **Connect** again
     to sign in. Start a new conversation afterwards.

Claude's code execution in claude.ai, Cowork and cloud sessions may block other
sites. Steps that run there and reach Egbe directly, such as publishing your app
with Git, need `os.hz.egbe.dev` allowed in Claude's network settings; Claude
tells you when this applies.

You need an Egbe account. Manage or disconnect connected assistants at
<https://dashboard.egbe.ai/settings/connections>.

## What the plugin contains

- **Skills** that teach Claude how to use each Egbe capability.
- **The Egbe connector** (`https://os.hz.egbe.dev/mcp`), a remote MCP server that
  Claude calls to read your project and perform the work you ask for.

- **A session-logging hook** (`hooks/session-log.sh`), which records your
  sessions in project folders set up for Egbe (see below).
- **A Business Loop reminder** (in `hooks/hooks.json`). After Claude publishes an
  app, creates a payment link, launches an ad campaign or activates an email
  campaign through Egbe, it reminds Claude to check once whether a recurring
  Business Loop, such as a weekly report, would help, and to suggest it to you.
  Claude saves or starts a loop only if you agree, and doesn't suggest one again
  after you decline or ask for no suggestions. The reminder sends nothing
  anywhere.
- **A milestone reminder** (in `hooks/hooks.json`). In project folders set up
  for Egbe, each of your messages comes with a short note asking Claude to check,
  before it replies, whether the turn reached a milestone, such as a first live
  page, first sales or customer interviews you ran, and if so to suggest one
  fitting Business Loop. It adds a few lines to Claude's context, nothing else,
  and sends nothing anywhere.

**In a project folder** in Claude Code, Claude also sets the project up for
Egbe, which plain chats skip. It saves your project's Egbe key in the folder's
Git-ignored `.env.local` and copies Egbe's project guidance (`EGBE.md`) and
editable working methods (`egbe-docs/playbooks/`) from the plugin into the
project. Egbe's skills stay in the plugin and update with it.

## What it sends and where

Claude sends the requests it makes on your behalf, such as a page to publish, an
email to send or a search to run, to Egbe at `https://os.hz.egbe.dev` over the
connector. Egbe acts only for the business you approved, within your wallet
limits, and records these requests so you can review activity and spending in
Egbe's dashboard. The authorized Egbe team can also read each connector call,
with its inputs and results, to support you and improve Egbe. Some capabilities pass requests on to the provider that performs
them, for example a payment, email or advertising provider. Egbe's
[privacy policy](https://egbe.ai/privacy/) describes how this data is handled.

**Session logging is on by default.** By installing the plugin you agree that
Egbe records your Claude Code and Cowork sessions in project folders set up for
Egbe; Claude also tells you when it sets up a folder. At the end
of each turn and session, the plugin's hook uploads the new part of the session's
transcript files (conversation text, tool inputs and results, and usage
information, including subagents) to Egbe at
`https://observe.hz.egbe.dev/telemetry`, authenticated with the project's Egbe
key. Egbe keeps that copy for at most three days after the session's last upload
and converts it into session records with the maintained
[Langfuse observability collector](https://github.com/langfuse/Claude-Observability-Plugin).
Images and attachments are excluded from the records, and secrets are redacted on
a best-effort basis. The authorized Egbe team can read these records. The hook
sends nothing from a folder that is not set up for Egbe, never sends anywhere but
that Egbe address, and plain chats do not run hooks. Scheduled and other runs on
your computer are recorded too: a Git worktree of the project and other copies
of the project use the settings in the project's folder, which the plugin
remembers (only its location) after it records a session there. Cloud
scheduled tasks don't run the plugin from your computer, so they aren't
recorded this way. To stop, ask Claude to turn session logging off, or set
`EGBE_SESSION_LOGGING=off` in the project folder's Git-ignored `.env.local`;
this also stops its worktrees and copies. Each run's result is listed in
`last-run` in the plugin's data folder.

## What it downloads

The plugin itself downloads nothing, and setting up a project folder copies
files that come with the plugin.

Files that exceed the plugin directory's size limits are listed in their
skill; Claude downloads one from Egbe only when a step needs it and checks its
SHA-256:

- `egbe-os-design-landing-page/assets/lockfiles/accounts/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/lockfiles/accounts/package-lock.json
- `egbe-os-design-landing-page/assets/lockfiles/auth-db/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/lockfiles/auth-db/package-lock.json
- `egbe-os-design-landing-page/assets/scaffold/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/package-lock.json

## Support

Questions and problems: ask Claude to open an Egbe support ticket, or see
<https://os.hz.egbe.dev/plugins/egbe/support>.
