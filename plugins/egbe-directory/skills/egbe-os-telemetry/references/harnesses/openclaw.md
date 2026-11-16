# OpenClaw: qualify the active conversation tracing route

## Select before installation

Use the installed runtime's [OpenTelemetry guide](https://docs.openclaw.ai/gateway/opentelemetry)
and [configuration reference](https://docs.openclaw.ai/gateway/opentelemetry/configuration)
to check its native `diagnostics-otel` plugin, content capture and launch mode.
An unchanged native exporter that captures the granted text/tool scope and uses
the Egbe traces transport is allowed; the word "diagnostics" alone does not
establish or rule out conversation capture. Check actual content, not just OTLP.

Native capture covers every run executed by its Gateway. Require a
**project-dedicated Gateway/profile**, not a project config file on a shared
Gateway. Check effective process environment privately:

- Set `OTEL_NODE_RESOURCE_DETECTORS=none` before native activation. Default
  process detection can export `process.command_args`, including credentials
  passed as positional CLI arguments; content redaction does not cover this.
  Exclude process/environment/host resource discovery and verify effective
  settings. Do not print or copy credentials into commands or reports.
- `OPENCLAW_OTEL_PRELOADED=1` delegates traces to an external provider. Native
  endpoint, headers, detector settings and shutdown do not control that provider.
  Reuse it only through the common skill's verified managed-exporter contract
  (destination, privacy, project scope, activation owner, flush and stop).
  Otherwise leave capture off; do not remove a preload to take over its provider.
- `OTEL_SDK_DISABLED=true` disables plugin-owned export; saved config is not
  evidence of an active collector.

If considering [Langfuse Bridge](https://langfuse.com/integrations/no-code/openclaw),
read its [upstream compatibility instructions](https://github.com/langfuse/openclaw-x-langfuse-plugin)
and check the installed release against storage and launch mode. Bridge 1.5.0
recovers text from trajectory JSONL, not SQLite; do not select it for SQLite
conversation recovery. It also fails runtime activation on tested OpenClaw
2026.10.2 with a missing `SeverityNumber` export. Retain an already qualified
Bridge on compatible runtimes; do not install a second exporter alongside it.
If neither route meets the required capture scope, report the limitation and
continue product work before configuring credentials or installing anything.

## Configure a qualified native route

1. Use the official `@openclaw/diagnostics-otel` package unchanged, through the
   runtime's documented plugin installation and enable commands in this profile.
   Inspect the selected release's `pluginApi` compatibility as well as minimum
   host version. For example, stock plugin 2026.10.2 was tested on host 2026.10.2;
   release 2026.10.7 requires a newer plugin API and is rejected there. Choose a
   compatible maintained release, never force an incompatible latest install.
   Preserve other plugin entries and allowlists through normal native trust
   controls; do not bypass provenance checks or patch dependencies to load it.
2. Map the common workflow's selected values into private native configuration.
   The plugin need not read `.env.local`. Replace placeholders with actual values privately;
   `Authorization` is `Basic ` followed by base64 of the selected public value,
   colon and selected secret value. Base64 is not encryption. Keep the native file
   out of Git
   with restrictive permissions, preserving existing configuration:

   ```json
   {
     "diagnostics": {
       "enabled": true,
       "otel": {
         "enabled": true,
         "tracesEndpoint": "<EGBE_TELEMETRY_URL>/ingest/openclaw/api/public/otel/v1/traces",
         "protocol": "http/protobuf",
         "headers": {"Authorization": "<privately computed Basic value>"},
         "traces": true,
         "metrics": false,
         "logs": false,
         "captureContent": true,
         "sampleRate": 1
       }
     }
   }
   ```

   `captureContent: true` requires the existing grant for text/tool capture.
   Default capture is off. Sampling 1 is for verification; sampled-out turns
   cannot prove capture. Use `tracesEndpoint` as the exact full URL; do not send
   metrics/logs to the traces-only gateway.
3. Activate the installed/enabled plugin in the actual project Gateway using
   its documented native restart/reload. Installation and process-environment
   changes require that process to take up the new settings; a config reload
   does not change its inherited environment. Once loaded, supported changes to
   `diagnostics.otel` hot-reload the exporter and flush its previous generation.
   Verify runtime load/exporter health, not merely plugin discovery or saved keys.
4. Use Gateway-dispatched turns for verification. `openclaw agent --local`
   qualifies only when the installed runtime documents starting and flushing
   this exporter; 2026.10.2 does. `openclaw agent exec` does not start it in that
   release. Do not start a child harness instead of activating the founder's
   current runtime; follow the common skill's pending-activation procedure.

## Verify coverage and stop

Follow the common delivery-baseline procedure. Inspect child model and tool
observations as well as roots for text, results/errors, model/usage and parent
relationships. Check cross-turn session grouping separately. Never infer it from
packet counts or manufacture a constant session ID.

On native 2026.10.2 with SQLite, synthetic Gateway runs captured user/assistant
text, read results, usage and per-turn parent-child trees without reading JSONL.
Roots had empty I/O; a failed read had error status and its message in the next
model input, without a dedicated failed-tool result. No session/conversation ID
was emitted, so **cross-turn session grouping is unsupported in this release**.
Content is bounded/redacted; system prompts, thinking and external CLI harness
tool I/O are not guaranteed. Do not promise complete verbatim transcripts.

Record the chosen integration/version, actual launch/profile/environment and
these capture gaps in `collectors.openclaw`. Keep full session verification
`pending` while required grouping or live content readback is missing; report
the measured per-turn coverage separately. If joined cross-turn sessions are
required, this native release does not satisfy that requirement: leave setup
unavailable/unverified and continue product work. Local synthetic acknowledgement
does not activate the customer's connection or verify its Langfuse UI.

For one-harness native stop, set `diagnostics.otel.enabled: false` and confirm
the running exporter's documented reload/flush/shutdown before recording stop
confirmed. Preserve other plugins, collectors, keys and checkpoints. A preloaded
provider needs its verified managed stop path instead. Whole-project stop
uses the common skill and confirms every collector shutdown; it preserves the
OS key.

For a qualified Bridge route, map `publicKey`, `secretKey`, `baseUrl` to the
common workflow's selected public/secret values and base URL
`<EGBE_TELEMETRY_URL>/ingest/openclaw`. Preserve the profile's
other plugins. Follow the installed release's activation/stop procedure and
verify through its supported channel/webchat/TUI path; direct `openclaw agent`
CLI use does not establish Bridge conversation capture. Verify nonempty text,
tool results and session grouping; otherwise retain pending verification.
