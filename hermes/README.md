# Egbe plugin for Hermes

Egbe's native plugin for [Hermes Agent](https://hermes-agent.nousresearch.com)
connects Hermes to the business you run with Egbe: hosting and databases, email,
analytics, payments, advertising, research, search and an LLM.

## Install

```sh
hermes plugins install egbe-ai/egbe-plugins/hermes --enable
hermes egbe connect
```

The first command installs this folder of the `egbe-ai/egbe-plugins` repository.
The second adds Egbe's MCP server (`https://os.hz.egbe.dev/mcp`) to the active
Hermes profile and opens Egbe's sign-in page: sign in to Egbe and approve the
connection. It is the same as
`hermes mcp add egbe --url https://os.hz.egbe.dev/mcp --auth oauth`. Then start
Hermes in your project folder and ask it to set up Egbe.

## What it contains

- **Skills.** `egbe:egbe` (how to connect, set up and log sessions in Hermes),
  `egbe:egbe-setup` and Egbe's capability skills `egbe:egbe-os-*` with their
  scripts and references, the playbooks and the project guidance that setting
  up a project folder copies. Hermes loads them read-only with `skill_view`.
- **Session logging** from Hermes's plugin hooks, described below.
- **`hermes egbe status`**, **`hermes egbe connect`**, **`hermes egbe update`**
  and the `egbe_status` tool, which show the plugin version, whether Egbe's MCP
  server is configured, the last session logging result and the last update
  check.

The plugin updates itself. At most every six hours, when a session starts, it
reads the latest release from `egbe-ai/egbe-plugins`. It checks that release's
files against the published commit, installs that commit with Hermes's own
installer and checks the installed files again. If a check fails, it restores
the previous version. A release that adds tools or hooks waits for you to run
`hermes plugins update egbe`. `hermes egbe status` shows the last check and
`hermes egbe update` checks now.
`hermes config set plugins.entries.egbe.settings.auto_update false` turns
automatic updates off.

The plugin itself downloads nothing, and setting up a project folder copies
files that come with the plugin.

Files that exceed the plugin directory's size limits are listed in their
skill; Hermes downloads one from Egbe only when a step needs it and checks its
SHA-256:

- `egbe-os-design-landing-page/assets/lockfiles/accounts/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/lockfiles/accounts/package-lock.json
- `egbe-os-design-landing-page/assets/lockfiles/auth-db/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/lockfiles/auth-db/package-lock.json
- `egbe-os-design-landing-page/assets/scaffold/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/package-lock.json

## Session logging

**Session logging is on by default.** By installing this plugin you agree that
Egbe records Hermes's sessions in project folders set up for Egbe (a private
`.env.local` with Egbe's `OS_URL` and `OS_API_KEY`): your messages, model calls
with usage, tool calls with their results, and replies. Each turn is sent when
it ends to `https://observe.hz.egbe.dev/telemetry` with the project's Egbe key,
after Hermes's secret scrubber redacts it. The authorized Egbe team can read
them; images and attachments are not sent and secrets are redacted on a
best-effort basis. Nothing is sent outside such folders.

To stop, ask the agent to turn session logging off, or set
`EGBE_SESSION_LOGGING=off` in the project's `.env.local`. A declined choice
saved in `egbe-docs/telemetry/setup.json` also keeps it off, and
`hermes config set plugins.entries.egbe.settings.session_logging false` turns it
off for the whole Hermes profile. If the `hermes_otel` plugin already sends this
profile's traces to Egbe, the plugin sends nothing, so sessions are not
recorded twice.

## Support

Ask Hermes to open an Egbe support ticket, write to <support@egbe.ai>, or see
<https://os.hz.egbe.dev/plugins/egbe/support>.
