# Egbe

Egbe is an AI co-founder's business stack. This plugin connects your AI agent to
the business you run with Egbe, so the agent can build, launch and grow it for
you: hosting and databases, email, analytics, payments, advertising, market
research, web search and scraping, and an LLM, all billed to your Egbe wallet.

It is an [Agent Plugins](https://agent-plugins.org) 1.0 package: a `plugin.json`
manifest, skills under `skills/` and the Egbe connector in `mcp.json`. Agents
that load this format can use it as it is. Claude, Gemini CLI and OpenClaw have
their own Egbe plugins in the same repository,
<https://github.com/egbe-ai/egbe-plugins>.

## Get started

1. Install this folder (`plugins/egbe-portable` in `egbe-ai/egbe-plugins`) the
   way your agent installs a plugin from a Git repository or a local folder. In
   Codex, run `codex plugin marketplace add egbe-ai/egbe-plugins` and install
   Egbe from that marketplace.
2. Ask your agent to set up Egbe.
3. Connect the plugin's Egbe connector once: when your agent asks, sign in to
   Egbe and approve the connection. It covers all your Egbe businesses; in each
   conversation the agent works on the business you name.

You need an Egbe account. Manage or disconnect connected assistants at
<https://dashboard.egbe.ai/settings/connections>.

## What the plugin contains

- **Skills** that teach your agent how to use each Egbe capability.
- **The Egbe connector** (`https://os.hz.egbe.dev/mcp`), a remote MCP server that
  your agent calls to read your project and perform the work you ask for. It
  signs in through your Egbe account; the plugin holds no key.

The plugin has no hooks and no local server. A skill's scripts run only when
your agent runs one for a step in a project folder set up for Egbe.

**In a project folder**, your agent also sets the project up for Egbe, which
plain chats skip. It saves your project's Egbe key in the folder's Git-ignored
`.env.local` and copies Egbe's project guidance (`EGBE.md`) and editable working
methods (`egbe-docs/playbooks/`) from the plugin into the project. Egbe's skills
stay in the plugin and update with it.

## What it sends and where

Your agent sends the requests it makes on your behalf, such as a page to
publish, an email to send or a search to run, to Egbe at
`https://os.hz.egbe.dev` over the connector. Egbe acts only for the business you
approved, within your wallet limits, and records these requests so you can
review activity and spending in Egbe's dashboard. The authorized Egbe team can
also read each connector call, with its inputs and results, to support you and
improve Egbe. Some capabilities pass requests on to the provider that performs
them, for example a payment, email or advertising provider. Egbe's
[privacy policy](https://egbe.ai/privacy/) describes how this data is handled.

**Session logging, only with your permission.** When your agent sets up a
project folder, it asks whether Egbe may record your sessions. Only if you
agree, and where Egbe supports your agent, it connects session logging for that
project: conversation text, tool inputs and results, and usage information go
to Egbe at `https://observe.hz.egbe.dev/telemetry`. The authorized Egbe team can
read these records. Ask your agent to turn session logging off at any time.

## What it downloads

The plugin itself downloads nothing, and setting up a project folder copies
files that come with the plugin.

Files that exceed the plugin directory's size limits are listed in their
skill; your agent downloads one from Egbe only when a step needs it and checks its
SHA-256:

- `egbe-os-design-landing-page/assets/lockfiles/accounts/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/lockfiles/accounts/package-lock.json
- `egbe-os-design-landing-page/assets/lockfiles/auth-db/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/lockfiles/auth-db/package-lock.json
- `egbe-os-design-landing-page/assets/scaffold/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/package-lock.json

## Support

Questions and problems: ask your agent to open an Egbe support ticket, or email
<support@egbe.ai>.
