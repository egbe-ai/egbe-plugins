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
a local deploy command, needs a set-up project workspace. In a persistent
project workspace that is not set up yet, set it up as the `egbe-setup` skill's
project setup describes.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.

If the connector's tools (`egbe_request` and the other `egbe_*` tools) are not
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


# Project playbooks

Project playbooks in `egbe-docs/playbooks/` own the method. This skill handles
their delivery, synchronization and change records, not the business decision.

- For setup, follow [initial installation](references/catalog.md#initial-installation).
- Before work with a project method, follow
  [synchronization](references/catalog.md#synchronize-before-method-work).
- Before editing one, read [Changes](references/changes.md) to capture and quietly
  record accepted method changes; also use it to resume unfinished delivery.
