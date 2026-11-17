---
name: egbe-os-instantly-campaign-launcher
description: Prepare, explicitly activate, observe and recover project-owned Instantly email campaigns and reply queues; inspect assigned sender state.
version: 1.3.5
user-invocable: true
metadata:
  egbe-when: "Use for Instantly campaign preparation, activation, replies, observation or recovery."
  egbe-visible: "true"
  egbe-title: "Email outreach"
  egbe-description: "Operate scoped email campaigns, imports, reply queues and factual campaign observations."
  egbe-category: "Marketing & growth"
---

<!-- egbe-mcp-connection:v1 -->
This skill comes with the Egbe plugin. If this project has its own installed copy
of the skill, use that copy instead. Otherwise make every Egbe API call it
describes with the Egbe connector: `egbe_read` for GET and `egbe_write` for POST,
PUT, PATCH and DELETE (with `method`). Pass the API path (for example
`/me/limits`), query parameters in `query` and the JSON body in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
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

If the connector's tools (`egbe_read` and the other `egbe_*` tools) are not
available, the plugin's connector is not signed in on this Claude account. Tell
the founder how to connect it, as the `egbe-setup` skill describes, rather than
saying Egbe is unavailable.

The connector's tools work even where this environment's shell cannot reach
Egbe: their calls travel through Claude, not through the shell's network. A step
that runs in the shell, such as a bundled script, a `git push` to Egbe's Git
endpoint or a deploy upload, needs the shell to reach the Egbe host
(`os.hz.egbe.dev`). If a proxy or allowlist refuses that request before Egbe
answers, for example HTTP 403 on CONNECT or curl status `000`, follow the Claude
network recovery in
`egbe_skill(name="egbe-os-quickstart", resource="references/environment.md")`:
the founder allows that host for Claude's code execution or continues in Claude
Code on their own computer. Until the shell step succeeds, do not report the work
as published: a Claude Artifact or a local preview is not an Egbe deployment.


# Instantly campaign operations

Use the operation the task calls for; preparing a campaign is not authorization
to activate it, add recipients, reply, or install recurring jobs. Existing
research, copy, lists and run state are valid inputs. This capability does not
select a business goal or decide an outcome from reply rate.

Requires Node 24+ (`node:sqlite`), `OS_URL` and `OS_API_KEY`. Use the project
OS connection, not personal provider keys. Missing credentials are a blocker,
not permission to send cold outreach through Mailu or a trust-domain mailbox.

Read only the reference needed for the operation:

- [Campaign operations](references/instantly-ops.md): preparation/activation,
  sender selection and state, pagination, date-filtered reads, rendering, verification,
  imports and safe cleanup.
- [Reply handling](references/reply-handling.md): queue actions, confirmed
  opt-outs, same-thread sends and uncertain-send recovery.
- [Observation and scheduling](references/observation-and-scheduling.md):
  factual metrics, configured protection, optional jobs and verification.
- [Run state](references/run-state.md): executable configuration, artifacts,
  identity, handoff and replenishment; includes the [spec scaffold](references/run-spec-template.json).

For activation, readiness to continue, or protection recovery, read
[configured protection](references/observation-and-scheduling.md#configured-operational-protection)
to check what the bundled monitor supports and what its state actually proves.

Keep the owning run under
`egbe-docs/marketing/campaigns/instantly/<run_key>/`. Before continuing, read its
manifest and state files and query the project `outreach.db`, next to the run
directories, only through the read-only `scripts/outreach-report.js`
([usage](references/observation-and-scheduling.md#collect-facts-for-one-run)).
If it reports the database missing, say so; do not search the workspace or open
SQLite with inline code. Bundled scripts treat missing history after sending as a
blocker, not something to recreate. JSON checkpoints and queue
files remain active state, not disposable duplicates. Use only the run's
campaign IDs. Registry/gateway ownership is the tenant authority; local
manifest/tags narrow the run and detect conflicts, but do not grant access.

Commands return observations and operation evidence. Check readbacks and
incomplete actions before reporting success. Preserve contacts/messages/state
in the access-controlled project repository, credentials outside Git, and one
active executor when transferring work. Keep the current plan and decisions in
the existing project context, without a second preflight/log/lessons package.

## Files downloaded on demand

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project workspace; without one,
tell the founder that the step needs it and continue with the rest of the work.

In a project workspace, before a step that runs or copies one of these files,
download it into `.egbe/skills/egbe-os-instantly-campaign-launcher/` at the same relative path, for example
`curl -fsSL <url> --create-dirs -o .egbe/skills/egbe-os-instantly-campaign-launcher/<file>`, and check that its SHA-256
matches. Also download the files it uses from the same folder, such as the
modules a script imports. Wherever this skill names one of these files by its
path in the skill (for example `scripts/...` or `assets/...`), use `.egbe/skills/egbe-os-instantly-campaign-launcher/<file>`;
where it writes `<skills-directory>`, use `.egbe/skills`.
Keep `.egbe/skills/` out of Git by adding it to `.gitignore`.

| File | URL | SHA-256 |
| --- | --- | --- |
| `scripts/conclude-campaign.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/conclude-campaign.js | `9e5ff3f4bbcbb16032dd59b3efe760c381be082adb3adbf8f78b32ede26bdc3b` |
| `scripts/install-crons.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/install-crons.js | `0b2e308e285bf60ea9cccf76417a76456a59f438b91bacd2e81f0567efa0a620` |
| `scripts/launch-campaign.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/launch-campaign.js | `70e3cb37129a0344743915f7a56ef1621eca2bb4ef0ae6b711192cc284332c21` |
| `scripts/lib/campaign-metrics.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/campaign-metrics.js | `d1eab288d3ef20b55c7608e4cb1e3573254a0808387c881ed98a7d08050bec56` |
| `scripts/lib/confirmed-opt-outs.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/confirmed-opt-outs.js | `c418ee1fc67213f1646ab1a7a3abdd99d32c91f98d2a8a258edbb9f6111ed12d` |
| `scripts/lib/connection-identity.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/connection-identity.js | `a23f252b73559814ff1697c5dcac5e6cd7b18d794244245d4fcf484e63e5708c` |
| `scripts/lib/create-once.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/create-once.js | `f8e69155643c3a2ff11b528081fea40ed4b10d5129041766667a7084711d78b8` |
| `scripts/lib/gtm-identity.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/gtm-identity.js | `787587835b2e744dbafefeff4a333425bcf355cb7e758ecba23a808d2cba7692` |
| `scripts/lib/helpers.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/helpers.js | `5ad78af4112e8cb7d1a7a9f98b08ba6152b4b87a457d72201c55b4f7de06de5a` |
| `scripts/lib/html-body.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/html-body.js | `8ffbe8c1f697358e45e69a7c0798cf650404d1a19501c09efaf65a6c309d3139` |
| `scripts/lib/instantly-client.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/instantly-client.js | `32f3048a770057c280dc2ccde22c4ae37a48f506c82d42affd7e5e923f513e8b` |
| `scripts/lib/outreach-db.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/outreach-db.js | `fe2ebc2af7c967a0fa726ee7d9cb5387129ea978ca1e7758bd18afbbcf0483b8` |
| `scripts/lib/recipient-exclusion/index.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/recipient-exclusion/index.js | `a0c236996f6089d9c62a54b580709f4c02e811749ebacea45cc468925a6819dc` |
| `scripts/lib/replenish-test-harness.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/replenish-test-harness.js | `5fb72d8824c8e1b34f2a4795d98acf39d178e81e60b9caf93ed85992c2cd689c` |
| `scripts/lib/reply-queue.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/reply-queue.js | `18381342fd354d85d4608c7f44329bb586760920016c417eb48dc95f6aacc71b` |
| `scripts/lib/run-config.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/run-config.js | `291883bd439935eaef9bf4e5957515b381911c3bd963aebb68dc3955fd3a7bb4` |
| `scripts/lib/sender-selection.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/lib/sender-selection.js | `f97fe20fae7c3687266d77b74cdbf9076f364b49ccab14091cb70dcbb2eafef0` |
| `scripts/monitor-campaign.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/monitor-campaign.js | `91420d662108c5722cb52034fb59d36d6a416b4bc867db85416e9316c4f9d254` |
| `scripts/outreach-report.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/outreach-report.js | `02adae18f09d915321bf44a1c155c64b876df4fd2757cf3899d2d32fe6d0f6e0` |
| `scripts/replenish-leads.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/replenish-leads.js | `b16d8f5287763c890b05ec2b95da7f13efc5b16e128126c4c153e3562839a145` |
| `scripts/reply-worker.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/reply-worker.js | `596862bcece04fb5197676bef6447470e69677cf2e56aae4d868532034357683` |
| `scripts/run-cron-job.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/run-cron-job.js | `aeeeb4a68beecd588cbc75e40aa7863459055ab6ab3d21a1f2a2739eb8ec6b5c` |
| `scripts/send-reply.js` | https://os.hz.egbe.dev/skills/egbe-os-instantly-campaign-launcher/resources/scripts/send-reply.js | `9479b960acc1ca46590ba4b9f58de378c0f1d0422b47747b563b0e8bbf39d4da` |
