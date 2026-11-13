---
name: egbe-os-telemetry
description: Connect, verify or disable project session logging.
metadata:
  egbe-when: "Use when session logging is requested or needs checking."
  egbe-category: "Business operations"
  egbe-visible: "false"
  egbe-title: "Session logging"
  egbe-description: "Connect authorized project session logging, verify delivery or turn it off."
---

<!-- egbe-mcp-connection:v1 -->
This skill comes with the Egbe plugin. If this project has its own installed copy
of the skill, use that copy instead. Otherwise make every Egbe API call it
describes with the Egbe connector's `egbe_request` tool: pass the HTTP method,
the API path (for example `/me/limits`), query parameters in `query` and the JSON
body in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Files this skill refers to are next to this `SKILL.md`, except any listed under
"Files downloaded on demand".

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs a set-up project workspace. In a persistent
project workspace that is not set up yet, set it up as the `egbe-setup` skill's
project setup describes.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


# Agent session logging

## Connect

1. Check the founder's request and the project's saved choice in
   `egbe-docs/telemetry/setup.json` and project notes **before any setup work**.
   A saved decline, skip or disable takes precedence over a pasted standard
   connection prompt, including its "enable session logging" and authorization
   text. Keep logging off and return to product work without collector discovery,
   configuration or installation. Reopen setup only on an explicit request to
   reverse the previous choice; routine reruns and harness changes do not qualify.

   Otherwise, reuse applicable permission from the standard prompt or a saved
   grant without asking again. The prompt authorizes conversation text, tool
   inputs/results and usage through Egbe for access by the authorized Egbe team.
   Without applicable permission, keep logging off and continue product work;
   silence is not consent. If an explicit logging request leaves its scope
   unresolved, ask only about the missing scope.

   Save `consent: granted`, `declined` or `skipped`, the verified project ID,
   choice date, authorization source and any scope restriction, preserving
   connection and collector records. A missing answer is not a saved founder
   choice. `skipped` means an explicit dismissed offer, never a grant. A later
   explicit re-enable replaces the saved choice with `granted` and reuses records.
2. Read `GET /telemetry`. If `data.available` is false, report that logging is
   unavailable and continue Egbe setup without it.
3. Check whether the environment already supplies a managed session exporter.
   Reuse it only when its installed integration/version, project scope,
   configuration inputs, activation owner and flush point are established and
   compatible with the gateway and granted capture scope. Record that managed
   route without installing a second collector or assuming native hooks are
   active. Unknown availability is not an installed integration.

   Otherwise identify the active harness, version and launch mode. Read only its
   reference:
   * [Codex](references/harnesses/codex.md)
   * [Claude Code](references/harnesses/claude-code.md)
   * [Hermes](references/harnesses/hermes.md)
   * [OpenCode](references/harnesses/opencode.md)
   * [OpenClaw](references/harnesses/openclaw.md)
   If not installed, fetch it at
   `GET /skills/telemetry/resources/references/harnesses/<harness>.md`.
   For another harness, find its current session
   tracing integration in the [Langfuse integration catalog](https://langfuse.com/integrations)
   or [documentation index](https://langfuse.com/llms.txt), and read the linked
   official installation/configuration guide. When selecting or installing an
   integration yourself, use a maintained plugin or native exporter unchanged,
   not an Egbe wrapper or a copied collector implementation.
   Check its capture coverage and the gateway contract below. A missing or
   incompatible integration ends this setup attempt before configuration or
   installation: report the limitation and continue product work, rather than
   building a custom adapter or claiming logging is active.

   Briefly explain that you are configuring session logging and the founder can
   ask you to disable it. Storage is Egbe's shared Langfuse project, accessible
   to the authorized Egbe team. Attachments/media are excluded; secret redaction
   is best-effort. Explain any history replay from the harness reference: first
   activation may include earlier messages from this session, not just new ones.
   Honor narrower permission; do not expand it to match a collector's coverage.
4. Leave a working existing collector and its saved credentials unchanged,
   including an existing telemetry key pair. Check project/harness status through
   `GET /telemetry/status?harness=<harness>`. A saved decline or locally stopped
   collector stays off; a skill update is not a request to re-enable it. If a
   saved pair is rejected, diagnose it and keep verification pending rather than
   silently replacing it.

   For new setup, lost settings or explicitly requested reconfiguration, use the
   project's existing primary `OS_API_KEY` from its private OS configuration.
   Verify the project ID through authenticated OS context, for example
   `GET /me/limits`. Do not use a founder OAuth token, scoped/apps/eval key or
   shared gateway token as the collector secret. Obtain the nonsecret base URL
   from `GET /telemetry` and retained environment/connection metadata from status.
   If status is unavailable, leave setup pending until that context can be checked.
   Use the retained environment when a legacy connection exists. Otherwise use
   production, or test for a designated test project. Select native values:

   - Public key: `pk-lf-egbe-<project_id>`; append `-test` for test environment.
   - Secret key: the existing primary `OS_API_KEY`.

   There is no registration, new key issuance or fallback pair to request. A
   legacy `connection_id` is optional history, not a setup prerequisite. Reusing
   the OS key means its private plugin copy has ordinary OS permissions too;
   the gateway's traces-only route does not reduce those permissions. Never put
   this secret in the public-key field or copy provider Langfuse keys to clients.
5. Save the shared settings below and configure the selected route through its
   documented project-scoped inputs. For a native integration, follow its upstream
   guide using native settings or a dedicated runtime profile.
   Map the selected public/secret values and gateway URL to the integration's
   documented fields; the native field names still use Langfuse terminology.
   An isolated harness profile or plugin cache may live outside the workspace;
   use the normal permission flow for those locations or protected files,
   keeping collection scoped to this project.
   Check effective settings, including inherited environment overrides, without
   printing secrets. Preserve other hooks/collectors; avoid duplicate exporters.
   Verify which working directory or profile resolves those settings; nested
   directories do not necessarily inherit the project's configuration.
   Disable media upload with native settings where available; media endpoints
   are blocked at the gateway regardless. Keep text/tool capture enabled and
   record unavoidable truncation or unsupported launch modes.
6. Confirm the selected plugin/exporter is actually installed and enabled in the
   runtime that will run this project; saved credentials alone do not enable it.
   For a verified managed route, follow its documented activation ownership;
   do not request native hook trust for a route that does not use that hook.
   This does not approve or activate any separate native integration.
   Record the integration/version, guide URL, config locations and verification
   state under `collectors.<harness>` in `setup.json`. For an already verified
   collector, retain it and its export checkpoints. For a native integration,
   prefer the harness reference's supported reload in the current session.
   When only the founder can run its native command, save pending verification
   and give that command as the next
   step; do not run it in a shell or start a child harness as a substitute.
   Request a new session/restart only for an evidenced runtime or consent-scope
   limitation, after completing the rest of quickstart. Resume pending verification
   after activation; do not claim that a reload alone proves delivery.

## Shared settings and gateway contract

Keep the existing OS credentials in Git-ignored `.env.local` (mode `600`),
preserving other variables. Save the nonsecret gateway location alongside them:

```dotenv
EGBE_TELEMETRY_URL=<data.base_url from GET /telemetry>
```

For new setup, no separate telemetry public/secret variables are needed. A plugin
need not read `.env.local`: pass the selected public identifier and existing OS
secret through its documented private native configuration or scoped environment.
Keep any copies out of Git and do not print them. OS-key rotation requires updating
those native secret copies before verifying delivery again.

Existing `EGBE_TELEMETRY_PUBLIC_KEY` / `EGBE_TELEMETRY_SECRET_KEY` and native copies
remain supported. Leave a working saved pair in place; no migration step is
required when skills update. New collectors follow step 4 above.

Use `<EGBE_TELEMETRY_URL>/ingest/<harness>` as the Langfuse SDK base URL. Choose a
stable harness label: 1–64 lowercase letters, digits or hyphens, starting with a
letter (for example `codex`, `hermes`, `opencode`). No server registration is needed.
The gateway accepts **only** `POST /api/public/otel/v1/traces` under that prefix:
OTLP HTTP JSON/protobuf, optional gzip, Basic auth with the selected public and secret values.
For a native exporter, use that complete traces URL. Packet limit: 8 MiB after
decompression. Other signals, legacy ingestion, media, read and admin APIs are
not proxied. Confirm the selected integration uses this transport; an arbitrary
Langfuse-compatible tool is not necessarily a session collector.

Version `egbe-docs/telemetry/setup.json` with the project. It has no secrets:
`project_id`, `consent` (`granted`, `declined` or `skipped`), choice date,
authorization source (for example, the setup request, not a copy containing its
API key), optional consent scope, `environment`, optional historical `connection_id`,
and `collectors` keyed by harness. Each collector records `enabled`, integration
version/config locations and `verification` (`pending` or `verified`). When
switching harnesses, retain existing entries and configure only the new one.
After cloning or moving the project, verify the current machine's collector
and config before treating a saved `verified` status as active here. Keep the
recorded consent scope; installation elsewhere does not expand authorization.

## Verify

Record a delivery baseline from
`GET /telemetry/status?harness=<harness>`, then make a harmless
text exchange and tool call. Check again after the integration's documented
flush point. If it exports after the current turn, save **pending verification**
and check on the next normal turn; do not generate extra turns just to verify.

- New receipts in `delivery.counts`/`last_result.updated` prove gateway acceptance;
  an increase in `delivery.delivered` proves upstream acknowledgement, not
  transcript completeness. `delivery.received` alone can refer to old records.
  Another harness's deliveries or old counts do not verify this collector.
- Where Langfuse read access is available to the Egbe team, check the corresponding
  session for test text, tool output and grouping. Report capture gaps separately.
- `last_result` is the latest receipt and may be successful despite an earlier
  failure. For `needs_attention`, inspect `last_failure.reason` and its safe
  `diagnostic` (known status, phase, error type, duration and bytes). On old
  gateways without `last_failure`, report that failure details are unavailable;
  do not use a successful `last_result` to clear the warning. Old receipts may
  have no diagnostic. After payload expiry its diagnostic preserves the earlier
  attempt while the current state/reason report expiry.
  `uncertain` means an upstream acknowledgement was lost or partial; report it
  without deleting checkpoints or blindly re-exporting. Missing status is not success.

For `401`, check the selected credential, project binding and key rotation; do not
request a legacy pair as fallback. For `409`, check retained environment and span
compatibility without resetting history or checkpoints.
For `413`, reduce batch size rather than silently truncate content. `429`/`503`
are temporary failures. Logging failures do not block product work. Offline
recovery depends on the upstream collector; Egbe can retry only received packets.

## Disable

For one harness, use its verified managed stop path when applicable; otherwise
read its reference and disable its integration using the upstream procedure,
including applying the change to the **running session**. Record
`stop: pending` until effective shutdown is confirmed; only then mark that
collector `enabled: false` and `stop: confirmed`. Removing saved credentials
alone does not prove shutdown. If applying the change is unavailable or fails,
explain any remaining hook/export risk, keep stop pending and give the next native
step. Preserve OS credentials, other collectors and upstream export checkpoints.
After confirmed stop, remove only that collector's private credential copies;
keep `.env.local`'s `OS_API_KEY` for ordinary OS access.

For the whole project, record `consent: declined` immediately and shut down all
recorded collectors, including other machines, through their native procedures.
Keep each unavailable/unconfirmed stop pending and explain any remaining export
risk. There is no server telemetry enable/disable switch or key-revocation call.
Never revoke/delete the primary OS key just to stop logging. Stopping collection
does not delete existing Langfuse data; refer a deletion request to the Egbe team.
