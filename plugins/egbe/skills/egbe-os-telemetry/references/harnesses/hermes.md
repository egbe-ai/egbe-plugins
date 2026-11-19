# Hermes: configure the active profile

## With the Egbe Hermes plugin

When the Egbe plugin for Hermes is installed (`hermes plugins list` shows
`egbe` enabled), its session logging is the managed exporter for harness
`hermes`: it sends each turn from Hermes's plugin hooks when the turn ends, with
the project's `.env.local` credentials, grouped by Hermes session. Follow the
"Session logging" section of the plugin's `egbe:egbe` skill: record
`collectors.hermes` with integration `egbe-hermes-plugin`, verify with the
`egbe_status` tool or `hermes egbe status`, and stop with
`EGBE_SESSION_LOGGING=off`. Do not also install or configure `hermes_otel`
below; an existing `hermes_otel` export to Egbe keeps the plugin's logging off,
so sessions are not recorded twice. Without the plugin, continue below.

## Without the plugin

1. Use the maintained [hermes_otel plugin](https://github.com/briancaffey/hermes-otel):
   install and enable it through Hermes's plugin commands in the profile used
   for this project. Resolve that profile's `HERMES_HOME` first.
2. Configure `<HERMES_HOME>/hermes_otel.yaml`, not an unrelated default
   `~/.hermes` profile. Use an OTLP backend with the complete traces URL
   `<EGBE_TELEMETRY_URL>/ingest/hermes/api/public/otel/v1/traces` and Basic auth
   from the common workflow's selected public and secret values. Keep the native
   credential copy private.
3. Set `content_capture: full`. Send traces only to Egbe; disable metrics/log
   export to this endpoint. This records full model requests/responses on
   `api.*` spans; ordinary tool and `llm.*` spans can still contain previews.
   Inspect full API history before treating a preview as missing content.
   Preserve exact tool-call IDs and report unresolved or underlying tool-output
   cutoffs; do not promise verbatim full capture or increase preview limits as
   a substitute for verifying it.
4. Restart the active runtime after common setup, then verify delivery through
   Egbe. For a messaging gateway in a Slack thread, ask the founder to send
   `!restart` in that thread; Slack does not deliver native slash commands such
   as `/restart` in threads, so those must be sent outside the thread
   ([Hermes Slack guide](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/slack)).
   If only the plugin's local SQLite store changes, check the configured
   backend and active profile; local records are not proof of remote delivery.
