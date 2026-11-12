---
name: egbe-os-mail
description: Send and read email through the business's @egbe.app mailbox.
metadata:
  egbe-when: "Use for business correspondence and inbox review."
  egbe-visible: "true"
  egbe-title: "Email"
  egbe-description: "Send product emails and read replies through your business's own egbe.app mailbox."
  egbe-category: "Business operations"
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


# Mail

You have a real `@egbe.app` mailbox. Send and read mail without ever touching
SMTP/IMAP or your mail password — just call these with `Authorization: Bearer $OS_API_KEY`.

Base URL: `https://os.hz.egbe.dev`.

## Sending policy

The `@egbe.app` mailbox carries verification/onboarding links, replies to
opted-in users, founder-facing 1:1 follow-ups, and product/operational notices.
Its sending reputation is shared across businesses.

Never send cold outreach or any list/batch/multi-recipient mail through
`POST /mail/send`. Use the OS `outreach` capability and its Instantly skill
for cold outbound, with a dedicated sending domain distinct from `egbe.app`
and `egbe.dev`. If outreach is unavailable, report the blocker; do not fall
back to the trust mailbox.

## Discover your assigned mailbox

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/mail/account" -s
```

This returns your mailbox email and non-secret mail metadata. Use
`data.operational_recipient` as the source of truth for internal product/admin
notifications, founder alerts, report delivery tests, and product notification
environment variables.

Do not use a public footer/contact/support/marketing email as an operational
recipient just because it appears in product UI copy. Public contact email and
operational notification recipient are different concepts.

Use an external or custom-domain recipient only after explicit live delivery
verification. SMTP send success only means the sending server accepted the
message; it does not prove final delivery. If a `MAILER-DAEMON` bounce appears
after the test, the recipient is invalid and must not be used for operational
notifications.

## Send

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/mail/send" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"to":"someone@example.com","subject":"Hello","text":"Sent by my agent."}'
```

Optional `from_name` sets the display name the recipient sees, for example
`"from_name":"Acme Team"` gives `Acme Team <you@egbe.app>`. The address is always
your mailbox. Use your product's or your own name, never one that claims to be another
company, including Egbe itself unless the business belongs to the Egbe team. Up to 64 characters, without `@`, `<`, `>`, quotes or line breaks.

Recipient checks run automatically; do not add a separate verification API step.
A 200 response means SMTP accepted the message. If it includes
`recipient_verification_warning`, the optional check was inconclusive; do not
resend an accepted message. A 422 invalid-recipient response means nothing was
sent: correct the destination instead of repeating it. Transient baseline
checks can return503 with no send; retry only after that failure is resolved.

If sending returns 422 because this recipient previously returned a confirmed
mailbox-not-found bounce, correct the destination. Repeating the same request
cannot send the email. If sending returns 503 for an unavailable recipient check,
retry later; that request sent no email. A successful submission still requires
delivery verification for operational recipients.

## Read your inbox

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/mail/inbox?limit=10" -s
```

Returns the most recent messages (`uid`, `from`, `to`, `delivered_to`, `subject`, `date`, `received_at`, `unread`). Use `limit` (1–50), `since=YYYY-MM-DD` (server arrival date) and `to=<address or alias>` (a substring of To or Delivered-To, e.g. a plus-addressed alias of your mailbox such as `you+tag@egbe.app`); the filters run on the server, so an older message to an alias is found even when newer mail fills the last `limit` messages.
The `uid` is a stable handle — pass it to read the full message.

## Read one message in full

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/mail/message/$UID" -s
```

Returns the full message: `from`, `to`, `subject`, `date`, and `text` (the body —
plain text, or HTML stripped to text; truncated to 20k chars). Get `$UID` from `/mail/inbox`.
