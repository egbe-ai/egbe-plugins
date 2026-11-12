---
name: egbe-os-support
description: Contact the Egbe team through support tickets and follow up on replies.
metadata:
  egbe-when: "Use for Egbe-team contact; offer a handoff when an Egbe blocker needs human intervention."
  egbe-category: "Business operations"
  egbe-visible: "true"
  egbe-title: "Help from the Egbe team"
  egbe-description: "Ask your agent to contact Egbe about a blocker and follow up on the team's replies."
---

<!-- egbe-mcp-connection:v1 -->
This skill was delivered through the Egbe MCP connection. Make every Egbe API
call it describes with the `egbe_request` tool: pass the HTTP method, the API
path (for example `/me/limits`), query parameters in `query` and the JSON body
in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Read a referenced file with
`egbe_skill(name=<skill>, resource=<relative path>)`.

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs the standard workspace setup. In a persistent
project workspace that is not set up yet, call `egbe_local_setup` and follow it.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


# Support Tickets

Use Egbe's built-in support to contact the Egbe team and track human handoffs.
No external helpdesk connection is required. The team sees your ticket and acts
on it; check replies in a later session.

Tickets are scoped to you: you only ever see and touch your own. Each ticket
has a stable numeric `id` — use it for follow-ups. At the project's configured
`OS_URL`, authenticate with `Authorization: Bearer $OS_API_KEY`; the key needs
support permission. `POST /support/tickets` uses the `CreateTicketRequest`
schema in `/openapi.json` (operation `support_ticket_create`).

## When to use this

- Blocked on a human-only action (credential, domain, third-party dashboard).
- A shared service is broken and you can't fix it yourself.
- You need to ask the team a question and want it tracked, not lost in chat.

Do **not** open a ticket for things you can fix yourself — debugging, installing
packages, retrying a flaky deploy. Tickets are for genuine human handoffs.

## Create a ticket

Prepare a redacted report. Send it only with the founder's authorization or an
applicable workflow that explicitly requires the handoff; respect draft-only
requests.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/support/tickets" -fsS -X POST  \
 -H "Content-Type: application/json" \
  -d '{"title":"Need domain DNS access","body":"Please add the required DNS records or grant access to the domain settings.","reason":"The business cannot launch its custom-domain landing page until DNS is configured.","environment":"I am an AI assistant with shell and OS API access, but no access to the domain registrar. I checked the available DNS tools and cannot update these records.","requested_action":"Add the DNS records listed in the report or provide registrar access. Do not start paid work."}'
```

The response `data` carries the created ticket, including its `id` (use this for
follow-ups). Write a clear `body`: what you need, why you can't do it yourself,
and exactly what action would unblock you.

Include `reason`, `environment`, and `requested_action` whenever you open a
ticket. These fields are optional for older API clients, but make the handoff
actionable: explain the business goal and impact, your runtime and access
constraints (for example browser-only secrets versus shell access), what you
already tried, and the precise answer or action needed. Include relevant budget
and approval limits. Do not include API keys, tokens, passwords, or private keys.

The server adds the authenticated business ID, registry instance ID, instance
name, and agent support API attribution to the ticket and each follow-up. You
do not need to guess these IDs. Environment and reason are your account of the
problem; the API attribution alone does not establish human approval.

## List your tickets

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/support/tickets" -fsS
```

Returns your tickets, newest first. Check the `status` field of each:
`open` = not resolved yet, `closed` = the team marked it done.

## Get one ticket + comments (was it resolved?)

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/support/tickets/12" -fsS
```

Returns the ticket plus all replies from the human team in `comments`.

**Reading "resolved or not":**
- `status: "open"` → still being worked on (or not picked up yet). Keep waiting.
- `status: "closed"` → the team considers it resolved. Read the `comments` for
  what they did, then act on it (e.g. redeploy, retry the blocked step).
- New `comments` while still `open` → the team may be asking you for more info.
  Reply with the comment command below.

Poll this on a later session rather than busy-waiting — a ticket is an async
handoff, not a synchronous call.

## Comment on a ticket

Add context, answer a team question, or report that something is still broken:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/support/tickets/12/comments" -fsS -X POST  \
 -H "Content-Type: application/json" \
  -d '{"body":"Confirmed — redeployed and Stripe is working now. Thanks."}'
```

## Notes

- If a request fails, diagnose the actual authentication, scope or service error;
  a third-party helpdesk is not a prerequisite.
- You can only see and comment on **your own** tickets. A ticket id that isn't
  yours returns `404` — that's expected, not a bug.
- You do **not** close tickets — the human team does that. Your job is to file
  a clear ticket, answer questions, and act on the resolution.
