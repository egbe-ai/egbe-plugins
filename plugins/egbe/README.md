# Egbe for Claude

Egbe is an AI co-founder's business stack. This plugin connects Claude to the
business you run with Egbe, so Claude can build, launch and grow it for you:
hosting and databases, email, analytics, payments, advertising, market research,
web search and scraping, and an LLM, all billed to your Egbe wallet.

## Get started

1. Install the plugin from Claude's plugin directory, or in Claude Code:
   `claude plugin install egbe --marketplace egbe-ai/egbe-plugins`.
2. Ask Claude to set up Egbe, or run `/egbe:setup` in Claude Code.
3. When Claude first uses Egbe, your browser opens Egbe's sign-in page. Choose
   the business Claude may work on and approve the connection.

You need an Egbe account. Manage or disconnect connected assistants at
<https://dashboard.egbe.ai/settings/connections>.

## What the plugin contains

- **Skills** that teach Claude how to use each Egbe capability.
- **The Egbe connector** (`https://os.hz.egbe.dev/mcp`), a remote MCP server that
  Claude calls to read your project and perform the work you ask for.

The plugin has no hooks and runs nothing on your computer by itself.

**In a project folder** in Claude Code, Claude sets the project up for Egbe the
standard way, which plain chats skip. It saves your project's Egbe key in the
folder's Git-ignored `.env.local`, installs Egbe's skills and editable working
methods (`egbe-docs/playbooks/`) into the project, and keeps them updated. The
project's own copies of the skills then take precedence over the plugin's.

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

The plugin itself downloads nothing. When Claude sets up a project folder, it
downloads Egbe's installer, skills and working methods from https://os.hz.egbe.dev/skills
and https://os.hz.egbe.dev/playbooks, checks their SHA-256 and later checks there for updates.

Files that exceed the plugin directory's size limits are listed in their
skill; Claude downloads one from Egbe only when a step needs it and checks its
SHA-256:

- `egbe-os-design-landing-page/assets/scaffold/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/package-lock.json

## Support

Questions and problems: ask Claude to open an Egbe support ticket, or see
<https://os.hz.egbe.dev/plugins/egbe/support>.
