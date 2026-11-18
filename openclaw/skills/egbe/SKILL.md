---
name: egbe
description: Use Egbe, the founder's business stack (hosting, databases, email, analytics, payments, ads, research, search, scraping and an LLM), through the Egbe plugin's connector. Use when the founder asks to set up, connect or use Egbe, or work needs one of these services.
---

# Egbe in OpenClaw

The Egbe plugin adds the `egbe` MCP server. Its tools are Egbe's connector:
`egbe_setup`, `egbe_skill`, `egbe_read`, `egbe_write`, `egbe_local_setup`,
`egbe_complete_setup` and `egbe_create_business`, which OpenClaw lists with the
server's prefix, such as `egbe__egbe_setup`. Egbe serves their instructions and
skills, so they are always current.

## Start

1. Call `egbe_setup` and follow the instructions it returns. Pass the `business`
   it returns to every later Egbe call.
2. This agent's OpenClaw workspace persists across sessions and can run
   commands: it is a persistent project workspace. When it is not set up for
   Egbe yet (no `.env.local` with Egbe credentials and no installed Egbe skills
   in its `skills/` folder), call `egbe_local_setup` and follow its result to set
   it up in the active agent's workspace, not another agent's. Egbe's installed
   skills keep themselves current there.
3. For any capability afterwards, use the workspace's installed Egbe skill, or
   read it with `egbe_skill`, and make its API calls with `egbe_read` (GET) and
   `egbe_write` (other methods).

If OpenClaw is still introducing itself (its first-run `BOOTSTRAP.md`) when the
founder asks to set up Egbe, set up Egbe first and finish the introduction after.

## If the Egbe tools are missing

The connector is not signed in yet. Don't call Egbe unavailable and don't reach
it from the shell instead. Ask the founder, in a short message in their
language, to connect their Egbe account once:

- With a browser on this computer: open OpenClaw's Control UI (`openclaw
  dashboard`), find the `egbe` MCP server under Settings, select **Sign in**,
  sign in to Egbe and select **Connect**. Egbe's tools are available from the
  next message.
- When OpenClaw runs on a server without a browser: run
  `openclaw mcp add egbe --url https://os.hz.egbe.dev/mcp --transport streamable-http --auth oauth`,
  stop the Gateway (`openclaw gateway stop`), run `openclaw mcp login egbe`,
  open the printed link on any device, approve, and if the page then can't
  connect, run `openclaw mcp login egbe --code <code from that page's address>`.
  Start the Gateway again.

Tell them in one line what the connection allows: it covers all their Egbe
businesses, including ones they start later, and you work on the business they
name; the Egbe team can read what you do in Egbe to support them and improve
Egbe; they can disconnect anytime under
[connected AI assistants](https://dashboard.egbe.ai/settings/connections).
The connection is shared by everyone who can message this OpenClaw, so suggest
keeping its channels private.

## Session logging

The Egbe plugin records this agent's sessions in a workspace set up for Egbe and
sends them to Egbe: the founder's messages, model calls with usage, tool calls
with their results, and replies, authenticated with the workspace's Egbe key.
The authorized Egbe team can read them; images and attachments are not sent and
secrets are redacted on a best-effort basis. It is on by default, as the
plugin's README discloses, so don't ask for permission. OpenClaw also requires
its operator to let the plugin read conversations:

- During setup, after `egbe_local_setup` has saved the workspace's
  credentials, tell the founder once, in plain words, what is recorded and that
  they can ask you to turn it off. If `openclaw config get
  plugins.entries.egbe.hooks.allowConversationAccess` is not `true`, run
  `openclaw config set plugins.entries.egbe.hooks.allowConversationAccess true`
  (OpenClaw may ask the founder to approve it). In
  `egbe-docs/telemetry/setup.json`, record `collectors.openclaw` with
  integration `egbe-openclaw-plugin`, the plugin version and pending
  verification, keeping other entries. Don't configure OpenClaw's
  OpenTelemetry export or another collector for Egbe.
- Verify after the next completed turn: `openclaw egbe status` (or the
  `egbe_status` tool) shows the last session logging result; `sent` means Egbe
  accepted the turn. Record the collector as verified.
- Stop when the founder asks, or when a saved choice declines logging: set
  `EGBE_SESSION_LOGGING=off` in the workspace's `.env.local` with the file tools
  and record the choice. `EGBE_SESSION_LOGGING=on` turns it back on, also over a
  saved decline.

## Updates

The plugin updates itself. The `egbe_status` tool and `openclaw egbe status` show
its version and the last update check; `openclaw egbe update` checks now.
