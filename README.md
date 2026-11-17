# Egbe plugins for Claude and Gemini CLI

This repository is the [Claude plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces)
for **Egbe**, an AI co-founder's business stack. Its one plugin, [`egbe`](plugins/egbe),
connects Claude to the business you run with Egbe: hosting and databases, email,
analytics, payments, advertising, research, search and an LLM.

## Install

In Claude Code:

```sh
claude plugin install egbe --marketplace egbe-ai/egbe-plugins
```

Then ask Claude to set up Egbe, or run `/egbe:egbe-setup`. You need an Egbe
account; the first time Claude needs Egbe, it opens Egbe's sign-in page or
gives you its link.

In claude.ai, the Claude app or Cowork, add this repository under **Customize →
Plugins → Add → Add marketplace → Add from a repository**, select **Sync**, then
**Add** on Egbe. Automatic updates need the Claude GitHub App granted access and
**Sync automatically** turned on.

There, and in Claude Code cloud sessions, adding the plugin doesn't sign you in:
open **Customize → Plugins → Egbe → Connectors** and select **Connect**. The
first time, keep the settings in **Add custom connector**, select **Add**, then
**Connect** again to sign in. Start a new conversation afterwards.

In Gemini CLI, this repository is also an extension:

```sh
gemini extensions install https://github.com/egbe-ai/egbe-plugins
```

Then ask Gemini to set up Egbe. The first time, run `/mcp auth egbe` to sign in.

The plugin's [README](plugins/egbe/README.md) describes what it contains, what it
sends where, and its session logging, which is on by default in project folders
set up for Egbe and can be turned off.

## About this repository

The contents are built and published automatically from Egbe's source, so pull
requests here are not accepted and changes made here would be overwritten.
For help, ask Claude to open an Egbe support ticket or see
<https://os.hz.egbe.dev/plugins/egbe/support>. To report a security issue, see
[SECURITY.md](SECURITY.md).
