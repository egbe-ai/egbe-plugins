# Egbe for Claude

Egbe is an AI co-founder's business stack. This plugin connects Claude to the
business you run with Egbe, so Claude can build, launch and grow it for you:
hosting and databases, email, analytics, payments, advertising, market research,
web search and scraping, and an LLM, all billed to your Egbe wallet.

## Get started

1. Install the plugin:
   - In Claude Code: `claude plugin install egbe --marketplace egbe-ai/egbe-plugins`.
   - In claude.ai, the Claude app or Cowork: **Customize → Plugins → Add → Add
     marketplace → Add from a repository**, enter `egbe-ai/egbe-plugins`,
     select **Sync**, then **Add** on Egbe. To get updates automatically, grant
     the Claude GitHub App access when Claude asks, then turn on **Sync
     automatically**.
2. Ask Claude to set up Egbe, or run `/egbe:egbe-setup` in Claude Code.
3. Connect the plugin's Egbe connector once: sign in to Egbe, choose the
   business Claude may work on and approve the connection.
   - In Claude Code on your computer, your browser opens Egbe's sign-in page
     when Claude first uses Egbe; you can also run `/mcp` and authenticate
     `plugin:egbe:egbe`.
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
Egbe's dashboard. Some capabilities pass requests on to the provider that performs
them, for example a payment, email or advertising provider. Egbe's
[privacy policy](https://egbe.ai/privacy/) describes how this data is handled.

**Session logging, only with your permission.** When Claude sets up a project
folder in Claude Code, it asks whether Egbe may record your sessions. Only if
you agree, it enables the maintained
[Langfuse observability plugin](https://github.com/langfuse/Claude-Observability-Plugin)
for that project. At the end of each turn, that plugin sends the conversation
text, tool inputs and results, and usage information to Egbe at
`https://observe.hz.egbe.dev/telemetry`. Images and attachments are excluded, and
secrets are redacted on a best-effort basis. The authorized Egbe team can read
these records. Ask Claude to turn session logging off at any time.

## What it downloads

The plugin itself downloads nothing, and setting up a project folder copies
files that come with the plugin.

This plugin bundles each skill's instructions. A skill's scripts and code
templates are listed in that skill with their SHA-256: in a project folder,
Claude downloads one into `.egbe/skills/` from Egbe only when a step needs it and
checks its digest before using it.

- `egbe-os-analytics`: 1 file from https://os.hz.egbe.dev/skills/egbe-os-analytics/resources/
- `egbe-os-apollo-lead-finder`: 13 files from https://os.hz.egbe.dev/skills/egbe-os-apollo-lead-finder/resources/
- `egbe-os-design-landing-page`: 21 files from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/
- `egbe-os-instantly-campaign-launcher`: 22 files from https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/
- `egbe-os-meta-ads`: 2 files from https://os.hz.egbe.dev/skills/egbe-os-meta-ads/resources/
- `egbe-os-openai-ads`: 1 file from https://os.hz.egbe.dev/skills/egbe-os-openai-ads/resources/
- `egbe-os-organic-trend-watch`: 15 files from https://os.hz.egbe.dev/skills/egbe-os-organic-trend-watch/resources/
- `egbe-os-payments`: 21 files from https://os.hz.egbe.dev/skills/egbe-os-payments/resources/
- `egbe-os-playbook`: 7 files from https://os.hz.egbe.dev/skills/egbe-os-playbook/resources/
- `egbe-os-product-auth`: 8 files from https://os.hz.egbe.dev/skills/egbe-os-product-auth/resources/
- `egbe-os-product-build`: 1 file from https://os.hz.egbe.dev/skills/egbe-os-product-build/resources/
- `egbe-os-product-market-research`: 50 files from https://os.hz.egbe.dev/skills/egbe-os-product-market-research/resources/
- `egbe-os-quiz-funnel`: 15 files from https://os.hz.egbe.dev/skills/egbe-os-quiz-funnel/resources/
- `egbe-os-reddit-ads`: 7 files from https://os.hz.egbe.dev/skills/egbe-os-reddit-ads/resources/
- `egbe-os-report-ui`: 4 files from https://os.hz.egbe.dev/skills/egbe-os-report-ui/resources/

## Support

Questions and problems: ask Claude to open an Egbe support ticket, or see
<https://os.hz.egbe.dev/plugins/egbe/support>.
