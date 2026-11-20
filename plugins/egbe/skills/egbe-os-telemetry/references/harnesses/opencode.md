# OpenCode: enable a collector, not just credentials

## With the Egbe OpenCode plugin

When the Egbe plugin for OpenCode (`@egbe/opencode`) is loaded, its session
logging is the managed exporter for harness `opencode`: when a run of a session
ends, it sends that run's turn with the project folder's `.env.local`
credentials and groups turns by OpenCode session. The plugin's own copy of the
telemetry skill says so below its title ("With the Egbe plugin in OpenCode");
follow it: record `collectors.opencode` with integration `egbe-opencode-plugin`,
verify after the next turn and stop with `EGBE_SESSION_LOGGING=off`. Do not also
install the Langfuse plugin below. Without the plugin, continue below.

## Without the plugin

1. Follow the [Langfuse OpenCode guide](https://langfuse.com/integrations/developer-tools/opencode)
   to install `@langfuse/opencode-observability-plugin`. Check compatibility with
   the installed OpenCode version. Register it in the project configuration:
   use that version's documented plugin field (`plugin` in v1, `plugins` in v2),
   preserving existing entries.
2. Map the common workflow's selected public and secret values into the plugin's
   native credential configuration or project-scoped launch environment. Its environment uses `LANGFUSE_BASEURL`
   for `<EGBE_TELEMETRY_URL>/ingest/opencode`. Keep settings isolated to this
   project instead of replacing credentials shared by other OpenCode projects.
3. Restart OpenCode after completing setup. Confirm this process loaded the
   plugin before performing the common delivery check. If no new receipts
   arrive, check plugin loading and effective environment before changing
   credentials; `setup.json` and saved credentials alone do not collect sessions.
