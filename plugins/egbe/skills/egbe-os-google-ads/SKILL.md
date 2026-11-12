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
describes with the Egbe connector's `egbe_request` tool: pass the HTTP method,
the API path (for example `/me/limits`), query parameters in `query` and the JSON
body in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Files this skill refers to are next to this `SKILL.md`, except any listed under
"Files downloaded on demand".

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs the standard workspace setup. In a persistent
project workspace that is not set up yet, call `egbe_local_setup` and follow it.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


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
| Create a paused campaign; change targeting, budget or bids | [Campaigns](references/campaigns.md) |
| Create or edit groups, keywords, negatives and responsive search ads | [Search assets](references/search-assets.md) |
| Launch, pause, inspect serving state or repair child status | [Delivery](references/delivery.md) |
| Read performance, search terms, diagnostics and product attribution | [Reporting](references/reporting.md) |
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

Read back changed objects before reporting completion and preserve the useful
facts for continuation. Simple reads need no new artifacts; missing historical
research must not prevent an explicitly requested pause. Scheduling belongs to
the caller's runtime mechanism, not to this skill; do not claim monitoring or
a future stop is installed unless that mechanism confirms it.
