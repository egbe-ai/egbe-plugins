---
name: egbe-os-google-ads
description: Inspect and operate Google Search campaigns, keywords, ads, targeting, budgets and conversion measurement through Egbe OS.
metadata:
  egbe-when: "Use for Google Search advertising and existing Google campaigns."
  egbe-visible: "true"
  egbe-title: "Google Ads"
  egbe-description: "Run ads through Egbe. Reach customers through Google Search, manage campaigns and budgets, and measure signups and purchases."
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
Where this skill sends an `Idempotency-Key` header, pass the same value as
`idempotency_key` and reuse it when retrying. A result with a `continuation`
holds one part of a long body; read the next part with `egbe_read`, the same
`path` and `business`, and that `continuation`.
Read bundled files beside this `SKILL.md`. For published skill resources on
Egbe OS, use `egbe_skill`. Follow "Files downloaded on demand" for listed downloads.

Publishing works through the connector: commit the app's files with the JSON
commit requests in `egbe-os-git` ("Without a terminal") and deploy the returned
commit SHA; no git push or workspace setup is needed. A step that needs a local
project key or a bundled script, such as a local `npx convex deploy`, needs a
set-up project workspace. In a persistent
project workspace that is not set up yet, set it up as the `egbe-setup` skill's
project setup describes.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.

If the connector's tools (`egbe_read` and the other `egbe_*` tools) are not
available, the plugin's connector is not signed in for this agent. Tell
the founder how to connect it, as the `egbe-setup` skill describes, rather than
saying Egbe is unavailable.

The connector's tools work even where this environment's shell cannot reach
Egbe: their calls travel through this agent's connection, not through the
shell's network. A step that runs in the shell, such as a bundled script, a `git
push` to Egbe's Git endpoint or a deploy upload, needs the shell to reach the
Egbe host (`os.hz.egbe.dev`). If a proxy or allowlist refuses that request
before Egbe answers, for example HTTP 403 on CONNECT or curl status `000`, tell
the founder: they allow that host in this agent's network settings or continue
with an agent on their own computer. Code can also be published without the
shell by committing through the connector (`egbe-os-git`, "Without a terminal").
Until the shell step or that commit and its deploy succeed, do not report the
work as published: a preview in this agent or on this computer is not an Egbe
deployment.

The harness can also refuse a step before Egbe answers: a denied file read or
command (`EPERM`, `operation not permitted`), a certificate error, or a
connector call that fails as a whole with HTTP 403. Egbe's own refusals of an
API request come back as a result with a `status` and Egbe's `message`, and the
`egbe_skill` tool never answers 403. Egbe refuses a whole call with 403 only for
a browser `Origin` it does not accept, so such a 403 most likely comes from the
harness, a proxy or a policy in front of Egbe. Don't retry it in a loop, route
around it or disable certificate verification. If `egbe_skill` was refused, read
that skill from an installed Egbe catalog or plugin copy, if this session has
one. Name the blocked file, command, host or tool and ask the founder to allow
it, or to trust the host through the environment's network setting. Then
continue the work that doesn't need it and say what waits on that permission.
While `egbe_skill` works, `egbe-os-quickstart`'s `references/environment.md`
lists these cases.


# Google Ads

Inspect and modify the selected Google Search objects through Egbe OS. Use the
requested configuration and exact owned IDs; a status read, edit or pause does
not require a campaign-planning package.

## Connection and account

Use `OS_URL` and `OS_API_KEY`; requests authenticate with
`Authorization: Bearer $OS_API_KEY`. Campaign management needs `ads` scope.
The [server conversions reference](references/server-conversions.md) describes
the narrower runtime `analytics` access. Never put the OS key in browser code
or project evidence; direct Google credentials are not needed.

Before new campaign setup, read the selected account. For work on existing
campaigns, list them and use their saved refs; new-account access is independent:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/ads/google/account" -s
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/ads/google/campaigns" -s
```

`GET /ads/google/account` checks access for new work and returns account
diagnostics in `data.raw` (customer id, currency, timezone, status). An explicit
Registry assignment takes priority. Without one, the shared Egbe account is
available only to approved owner emails. OS selects this server-side; customer
overrides are rejected and the caller cannot grant access by supplying an email.

- Success: continue the requested setup and planning with the returned account.
- `403` containing `google_ads_not_available`: tell the founder clearly, “New
  Google advertising through Egbe is unavailable for this project.” They can use
  their own Google Ads account through their own authorized tools/credentials,
  or agree a manual account connection/assignment with Egbe. Having an MCC or
  completing the Dashboard OAuth pilot alone does not assign an OS account.
  Do not request a founder MCC as a prerequisite or promise automatic connection.
- Registry/provider `5xx`: report a temporary account-check failure, retry the
  read later and escalate persistent failure to Egbe. This is not an access denial.

The restriction applies to selecting an account for new work, including keyword
ideas. It does not revoke existing campaign access. A denied account check must
not block an authorized read, edit, pause or saved-operation retry on an existing
campaign. Campaigns are in `data.campaigns`. Preserve the exact returned `ref`, shaped
`customer_id:campaign_id`; existing campaigns can belong to earlier assigned
accounts. Names are not ownership proof. For the selected campaign,
`GET /ads/google/campaigns/{ref}/account-settings` reads currency, timezone and
auto-tagging. Product agents cannot change shared-account auto-tagging; report
a needed change to Egbe, without requesting an admin key.

Other auth, ownership, configuration, quota and wallet errors block the affected
Egbe operation. Never use Egbe credentials, account overrides or raw provider
calls to bypass a restriction. A founder may separately authorize work through
their own tools and credentials; those are outside these OS endpoints. Keep
secrets out of chat, browser code and project evidence.

## Choose the operation

| Task | Read |
| --- | --- |
| Query keyword ideas and interpret their fields | [Keyword ideas](references/keyword-ideas.md) |
| Create a paused campaign; change targeting, device adjustments/exclusions, budget or bids | [Campaigns](references/campaigns.md) |
| Create or edit groups, keywords, negatives and responsive search ads | [Search assets](references/search-assets.md) |
| Launch, pause, inspect serving state or repair child status | [Delivery](references/delivery.md) |
| Read performance, device and keyword x device reports, search terms, diagnostics and product attribution | [Reporting](references/reporting.md) |
| Configure browser/server conversion actions, goals or bidding; read action reports | [Conversions](references/conversions.md) |
| Deliver backend-confirmed outcomes and inspect receipts | [Server conversions](references/server-conversions.md) |
| Preserve authorized inputs, confirmed state or an unfinished operation | [Campaign records](references/artifacts.md) |

Read only the relevant references. Endpoint paths below are relative to OS;
`{ref}` always means the returned campaign ref, not just the campaign id.
Google does not support the generic Meta `/plan`, `/apply`, `/state` or
`/status` routes. Use Google's `/readback`, not raw `/query` or `/mutate`.

## Execution

Before a write, follow [Campaign records](references/artifacts.md): find existing
records by the exact campaign ref, or by the planned work before a ref exists.
Read recorded decisions and `pending_operation`; reconcile an unfinished
operation using its saved request/key and current provider state before starting
another. Do not replace unresolved input with a new operation.

Identify the exact targets, read current state and apply only the intended change.
Do not create real provider objects to test request syntax; use documented
schemas, local validation or an explicit provider validation facility.
Preserve unrelated settings and intentionally paused objects. Save recoverable
inputs before the call. Use the operation's retry rules: temporary caches, durable
receipts and desired-state assignments are not interchangeable.

OS already retries reads briefly when the ads service is restarting or
unreachable. A failure that remains has `data.upstream_status`, `data.retryable`
and `data.attempts`; `data.error: "upstream_unavailable"` means Egbe or Google
was temporarily unavailable, not that a campaign changed. Keep the last confirmed
state, re-read later and report persistent failure through support. A write that
ends in 502/503/504 has an unknown outcome: read the object back before repeating
it. Pause reports its own confirmation; see [Delivery](references/delivery.md).

Approval covers the exact write it describes. After a failed or rejected write,
reconcile an unknown outcome first, then retry without asking only with the same
approved inputs and as the operation's retry rules allow. If the fix changes the
target, payload, amount, keywords, ad text, status or another substantive input,
show the founder the failure and the proposed changed write and wait for fresh
explicit approval before sending it; a fix to request syntax alone is not a
substantive change.

Read back changed objects before reporting completion and preserve the useful
facts for continuation. Simple reads need no new artifacts; missing historical
research must not prevent an explicitly requested pause. Scheduling belongs to
the caller's runtime mechanism, not to this skill; do not claim monitoring or
a future stop is installed unless that mechanism confirms it.
