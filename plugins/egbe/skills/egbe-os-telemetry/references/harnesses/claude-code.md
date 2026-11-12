# Claude Code: activate the maintained plugin in this session

1. Before activation, explain that the plugin reads the session
   transcript at `Stop`/`SessionEnd`. First activation can include earlier messages
   and tool results from this session. Do not promise capture only from opt-in
   onward. If the founder permits only future conversation, leave this session's
   collector disabled, including at `SessionEnd`, and configure/activate it in a
   genuinely fresh session; resuming the same transcript does not remove its
   earlier history. Preserve upstream checkpoints.
2. With applicable authorization from the shared workflow, follow the current README of the
   [Langfuse Observability Plugin](https://github.com/langfuse/Claude-Observability-Plugin).
   Choose this maintained plugin, not the manual hook-copying instructions in
   the general Claude Code integration guide. Enable and configure it only for
   the current project: install from its root with `--scope local`, keeping private
   settings in Git-ignored `.claude/settings.local.json` (mode `600`). Before
   writing keys, run `git check-ignore .claude/settings.local.json` and add its
   path to this project's `.gitignore` if necessary. The shared
   plugin cache may remain outside the workspace. Merge the following into that
   file's documented [`env` object](https://code.claude.com/docs/en/settings-reference#env),
   substituting the actual selected values, not literal placeholders:

   ```json
   {
     "env": {
       "LANGFUSE_PUBLIC_KEY": "<selected public key>",
       "LANGFUSE_SECRET_KEY": "<selected secret key>",
       "LANGFUSE_BASE_URL": "<EGBE_TELEMETRY_URL>/ingest/claude-code",
       "CC_LANGFUSE_CAPTURE_IMAGES": "false"
     }
   }
   ```

   Do not write these names as top-level settings or put `pluginConfigs` in
   project/local settings. Claude Code's [`userConfig` answers](https://code.claude.com/docs/en/settings-reference#pluginconfigs)
   are user/managed scoped even when installation uses `--scope local`;
   `/plugin configure` would share these answers across projects. The maintained
   collector supports plain environment variables ahead of those answers. Claude
   applies trusted local `env` changes to the running session and its subprocesses.
   Check effective settings, including desktop/runner launch overrides, without
   printing secrets; `.env.local` alone is not loaded by the plugin. Preserve
   unrelated settings and hooks, and keep image capture off before activation.
3. After consent and configuration, prefer Claude Code's native
   [`/reload-plugins`](https://code.claude.com/docs/en/plugins/cli-reference#reload-plugins)
   in the **current session**. It loads newly installed/enabled plugin hooks
   without restarting Claude Code, even when the plugin README or shell installer
   says to restart. If you cannot invoke native slash commands, tell the founder:
   “Run `/reload-plugins` here to activate session logging; then continue here so
   I can check delivery.” This is a Claude Code command, not a shell command.
   Save `verification: pending`, the delivery baseline and the pending command
   before handing over. A shell `claude plugin list` proves installation/enabling,
   not that the current session loaded the hook.
4. Check the reload summary for hooks and load errors; inspect `/plugin` errors
   if needed. If Claude defers a reload because it would invalidate the prompt
   cache, explain its message and the supported `/reload-plugins --force` option.
   Do not claim a deferred/failed reload activated logging. Direct-entry reloads
   outside an interactive terminal require Claude Code 2.1.260 or later and may
   be unavailable over remote connections; check the active version/launch mode.
   Request a restart only if reload is unavailable or cannot load the hook after
   diagnosis, and record the concrete reason. Keep product work usable meanwhile.
5. Resume the shared delivery verification after a normal turn reaches `Stop`,
   filtering status with `harness=claude-code`. Keep it pending until this harness's
   delivered count increases over the saved baseline; loaded hooks alone do not
   prove delivery. Retain the settings and checkpoints across reloads, and do
   not start a child Claude session to claim the active session is verified.
6. If Auto mode denies a required setup action, keep setup/verification pending
   and ask the founder to approve that specific action through Claude's native
   Manual / Ask permissions mode. Explain what the action does: saving
   credentials does not itself export conversations; enabling the
   collector does. Do not broaden permission rules yourself or rewrite the
   command to bypass the denial. Resume after approval, then use the shared
   delivery verification workflow.

## Stop logging in the current session

Use the installed plugin's actual qualified ID from its saved record or plugin
list. From this project root, run `claude plugin disable <plugin-id> --scope local`
to disable only this project's collector; preserve other plugins and harnesses.
Then apply the change with native `/reload-plugins` in the **current session**
(using `--force` only when the reload message requires it). A shell disable
changes saved configuration; it does not prove that loaded hooks are gone.

Confirm the reload succeeded and the selected plugin's `Stop`/`SessionEnd` hooks
are no longer loaded. Record `stop: confirmed` and `enabled: false` only after
that confirmation. Preserve upstream checkpoints. Remove this collector's saved
key copies afterward, without changing other settings or shared keys still used
by another harness. Removing `env` entries does not unset their values in a
running Claude session, so key removal alone is never the stop procedure.

If reload is deferred, denied, unsupported or unavailable over the active remote
connection, record `stop: pending` and keep the last confirmed enabled state.
Tell the founder that previously loaded hooks may still export at `Stop` or
`SessionEnd`, and provide the native reload/diagnosed restart step without
claiming logging has stopped. For a whole-project consent withdrawal, follow the
common stop procedure for every collector and retain pending shutdowns. Keep the primary OS key for ordinary
OS access; there is no remote telemetry kill switch.
