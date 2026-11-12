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
