# Egbe plugins for Claude

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
account; Claude opens Egbe's sign-in page the first time it uses Egbe.

The plugin's [README](plugins/egbe/README.md) describes what it contains, what it
sends where, and its optional, consent-based session logging.

## About this repository

The contents are built and published automatically from Egbe's source, so pull
requests here are not accepted and changes made here would be overwritten.
For help, ask Claude to open an Egbe support ticket or see
<https://os.hz.egbe.dev/plugins/egbe/support>. To report a security issue, see
[SECURITY.md](SECURITY.md).
