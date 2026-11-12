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
This skill comes with the Egbe plugin. Make every Egbe API call it describes with
the Egbe connector's `egbe_request` tool: pass the HTTP method, the API path (for
example `/me/limits`), query parameters in `query` and the JSON body in `body`.
For these calls leave out `OS_URL`, the Authorization header, `.env.local` and
`egbe-curl.py`, and skip catalog update checks; the connection authenticates and
identifies the request.
Also pass the `business` that `egbe_setup` returned. Files this skill refers to
are next to this `SKILL.md`, except any listed under "Files downloaded on demand".

A step that needs a local project key, such as a git push or a local deploy
command, works only in a persistent project workspace. There, if the project's
Git-ignored `.env.local` has no `OS_API_KEY` yet, call `egbe_local_setup` once
and save its `OS_URL` and `OS_API_KEY` there, preserving other entries. Use only
those two values: the plugin already provides Egbe's skills, so do not install
the Egbe catalog or follow the rest of that result. Never show the key in chat or
put it in logs, commits or URLs. Without such a workspace, tell the founder that
this step needs an agent with a project folder, and continue with the rest of
the work.


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

Read the account and existing campaigns before choosing an object:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/ads/google/account" -s
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/ads/google/campaigns" -s
```

Account diagnostics are in `data.raw` (customer id, currency, timezone, status);
campaigns are in `data.campaigns`. OS assigns the account: customer overrides
are rejected. Preserve the exact returned `ref`, shaped
`customer_id:campaign_id`; existing campaigns can belong to earlier assigned
accounts. Names are not ownership proof. For the selected campaign,
`GET /ads/google/campaigns/{ref}/account-settings` reads currency, timezone and
auto-tagging. Product agents cannot change shared-account auto-tagging; report
a needed change to Egbe, without requesting an admin key.

A 401/403, ownership 404, missing provider configuration, unavailable account
assignment, quota or wallet error is a concrete blocker, not permission to use
another account or raw provider API. Retry unavailable account assignment with
read-only requests later; report persistent failure to Egbe.

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
