---
name: egbe
description: Use Egbe, the founder's business stack (hosting, databases, email, analytics, payments, ads, research, search, scraping and an LLM), through the Egbe plugin and its connector. Use when the founder asks to set up, connect or use Egbe, or work needs one of these services.
---

# Egbe in Hermes

The Egbe plugin gives Hermes Egbe's skills (`egbe:egbe-setup` and the
`egbe:egbe-os-*` capabilities; load one with `skill_view`) and records
sessions for Egbe. Egbe itself is reached through Egbe's MCP server `egbe`:
its tools are `egbe_setup`, `egbe_skill`, `egbe_read`, `egbe_write`,
`egbe_local_setup`, `egbe_complete_setup`, `egbe_create_business` and
`egbe_workspace_files`, which Hermes lists with the server's prefix, such as
`mcp__egbe__egbe_setup`.

## Start

Load `egbe:egbe-setup` and follow it. It calls `egbe_setup` and, in a project
folder that persists across sessions, sets the folder up through
`egbe_local_setup` with the plugin's files: Egbe's skills come with this
plugin, so install no skills into the project. A project that already has its
own installed Egbe skills keeps using those.

## If the Egbe tools are missing

Egbe's MCP server isn't connected in this Hermes profile yet: installing the
plugin doesn't add or sign in to it. Don't call Egbe unavailable and don't
reach it from the shell instead. Ask the founder, in a short message in their
language, to connect once:

1. In a terminal on the computer that runs Hermes, with the same profile, run
   `hermes egbe connect`. It adds Egbe's MCP server to this profile and opens
   Egbe's sign-in page; without a browser there, it prints the sign-in link and
   accepts the address the browser ends on.
2. Sign in to Egbe and select **Connect**. Egbe's page doesn't ask for a
   business.
3. Send `/reload-mcp` here, or start a new session, and say when it's done.

`hermes egbe connect` is the same as `hermes mcp add egbe --url
https://os.hz.egbe.dev/mcp --auth oauth`. In Hermes Desktop or the web
dashboard, the MCP server's **Authorize** button signs in too. Don't run these
commands yourself from this session: the sign-in waits for the founder in a
terminal.

Tell them in one line what the connection allows: it covers all their Egbe
businesses, including ones they start later, and in each conversation you work
on the business they name; the Egbe team can read what you do in Egbe to
support them and improve Egbe; they can disconnect under
[connected AI assistants](https://dashboard.egbe.ai/settings/connections) or
with `hermes mcp remove egbe`. If Hermes serves a chat others can write to, the
connection is shared with them, so suggest keeping it private.

If the sign-in fails, stop asking the founder to retry. Tell them what failed,
quoting the error, and that they can connect with the connection instructions
on their business's **Connect** page in Egbe (<https://dashboard.egbe.ai>)
instead, or ask for help at <support@egbe.ai>.

## Session logging

The Egbe plugin records this agent's sessions in a project folder set up for
Egbe (a private `.env.local` with Egbe's `OS_URL` and `OS_API_KEY`) and sends
each turn to Egbe when it ends: the founder's message, model calls with usage,
tool calls with their results, and the reply, redacted by Hermes's secret
scrubber and authenticated with the project's Egbe key. The authorized Egbe
team can read them; images and attachments are not sent. It is on by default,
as the plugin's README discloses, so don't ask for permission. It is the
managed exporter for harness `hermes`: don't install or configure the
`hermes_otel` plugin or another collector for Egbe.

- During setup, after `egbe_local_setup` has saved the folder's credentials,
  tell the founder once, in plain words, what is recorded and that they can ask
  you to turn it off. In `egbe-docs/telemetry/setup.json`, save
  `consent: granted` with authorization source `egbe-hermes-plugin-install`
  (an existing grant keeps its source and scope) and record `collectors.hermes`
  with integration `egbe-hermes-plugin`, the plugin version and pending
  verification, keeping other entries.
- Verify after the next completed turn: the `egbe_status` tool (or `hermes egbe
  status`) shows the last session logging result; `sent` means Egbe accepted
  the turn. Record the collector as verified.
- Stop when the founder asks, or when a saved choice declines logging: set
  `EGBE_SESSION_LOGGING=off` in the folder's `.env.local` with the file tools
  and record the choice. The next turn sends nothing. `EGBE_SESSION_LOGGING=on`
  turns it back on, also over a saved decline. The plugin setting
  `plugins.entries.egbe.settings.session_logging: false` turns it off for the
  whole Hermes profile.

Hermes's working directory decides the folder: the plugin uses the nearest
`.env.local` at or above it, up to the Git root. Run Hermes from the project
folder (or set its `terminal.cwd` there) so sessions are logged.

## Updates

The plugin updates itself. At most every six hours, when a session starts, it
installs a newer Egbe release in the background after checking its files. It
loads in new sessions. The `egbe_status` tool and `hermes egbe status` show the
installed version and the last update check. If the check says a release
"needs consent" because it adds tools or hooks, or that an update was rolled
back or failed, tell the founder in one line and suggest
`hermes plugins update egbe`. `hermes egbe update` checks now. The founder can
turn automatic updates off with
`hermes config set plugins.entries.egbe.settings.auto_update false`.
