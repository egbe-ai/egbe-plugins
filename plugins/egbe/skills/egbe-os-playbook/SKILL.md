---
name: egbe-os-playbook
description: Install and synchronize editable project playbooks, and record accepted method changes in Egbe.
metadata:
  egbe-when: "Use when installing playbooks, before work with a project method, or before changing it."
  egbe-visible: "false"
  egbe-title: "Project playbooks"
  egbe-description: "Install and update project working methods, and record accepted adaptations for the Egbe team."
  egbe-category: "Business operations"
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


# Project playbooks

Project playbooks in `egbe-docs/playbooks/` own the method. This skill handles
their delivery, synchronization and change records, not the business decision.

- For setup, follow [initial installation](references/catalog.md#initial-installation).
- Before work with a project method, follow
  [synchronization](references/catalog.md#synchronize-before-method-work).
- Before editing one, read [Changes](references/changes.md) to capture and quietly
  record accepted method changes; also use it to resume unfinished delivery.
