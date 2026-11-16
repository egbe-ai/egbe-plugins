# Hermes: configure the active profile

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
   Egbe. If only the plugin's local SQLite store changes, check the configured
   backend and active profile; local records are not proof of remote delivery.
