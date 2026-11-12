# OpenCode: enable a collector, not just credentials

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
