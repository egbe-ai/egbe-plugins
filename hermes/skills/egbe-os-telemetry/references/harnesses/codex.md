# Codex: activate the upstream Stop hook

1. Follow the [Langfuse Codex guide](https://langfuse.com/integrations/developer-tools/codex)
   for the maintained Codex observability plugin. Check its Codex/Node requirements
   against the app or CLI that actually runs this session.
2. Enable the plugin and hooks in the configuration loaded by this session's
   project. Codex loads them in a new chat; if it ignores untrusted project
   settings, the founder must trust that project through Codex, and the Stop
   hook needs their approval through its separate prompt. Installation alone
   does not approve it. Keep verification pending until the hook is trusted.
3. Map the common workflow's selected public/secret values and gateway URL into
   the plugin's project-local credential file or scoped environment, with base URL `<EGBE_TELEMETRY_URL>/ingest/codex`. Check
   `LANGFUSE_CODEX_*` and `LANGFUSE_*` overrides in the actual runtime before
   assuming the file is effective. Do not print their values.
4. Do not pause setup or ask for a new chat, trust or hook approval for logging.
   Finish quickstart and the product handoff, then give the common skill's
   optional activation note once: logging starts in the founder's next chat in
   this project, where approving Codex's trust or hook prompt turns it on.
   Verify after the Stop hook has run; if the last turn finalizes on the next
   turn, continue verification there without resetting export checkpoints. If a
   later chat still shows no delivery because the hook awaits approval, remind
   the founder once, briefly, and continue their work.
