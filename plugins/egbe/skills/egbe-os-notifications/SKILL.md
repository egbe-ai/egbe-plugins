---
name: egbe-os-notifications
description: Read platform notifications and mark them read.
metadata:
  egbe-when: "Use to review notices affecting the business."
  egbe-category: "Business operations"
  egbe-visible: "false"
  egbe-title: "Project notices"
  egbe-description: "Read updates and notices from Egbe about your project."
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


# Notifications

Your inbox of system and Egbe team notices (deploys, limits, capability updates).
Authenticate with `Authorization: Bearer $OS_API_KEY`. Base URL: `https://os.hz.egbe.dev`.

## Read your inbox

```bash
# all notifications (newest first)
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/notifications" -s

# only unread
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/notifications?unread=1" -s
```

Each item has `id`, `title`, `body`, `level` (`info`/`warning`/`action`),
`read_at` (null = unread), `created_at`.

## Mark one read

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/notifications/123/read" -s -X POST
```
