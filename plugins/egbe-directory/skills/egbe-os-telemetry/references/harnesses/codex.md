# Codex: activate the upstream Stop hook

1. Follow the [Langfuse Codex guide](https://langfuse.com/integrations/developer-tools/codex)
   for the maintained Codex observability plugin. Check its Codex/Node requirements
   against the app or CLI that actually runs this session.
2. Enable the plugin and hooks in the configuration loaded by this session's
   project. If Codex ignores untrusted project settings, ask the founder to trust
   that project through Codex. Have them approve the Stop hook through its
   separate prompt; installation alone does not approve it. Keep verification
   pending until the hook is trusted.
3. Map the common workflow's selected public/secret values and gateway URL into
   the plugin's project-local credential file or scoped environment, with base URL `<EGBE_TELEMETRY_URL>/ingest/codex`. Check
   `LANGFUSE_CODEX_*` and `LANGFUSE_*` overrides in the actual runtime before
   assuming the file is effective. Do not print their values.
4. Finish quickstart before requesting the new chat needed for activation.
   Verify after the Stop hook has run; if the last turn finalizes on the next
   turn, continue verification there without resetting export checkpoints.
