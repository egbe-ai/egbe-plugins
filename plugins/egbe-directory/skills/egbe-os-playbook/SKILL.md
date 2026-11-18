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
describes with the Egbe connector: `egbe_read` for GET and `egbe_write` for POST,
PUT, PATCH and DELETE (with `method`). Pass the API path (for example
`/me/limits`), query parameters in `query` and the JSON body in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Where this skill sends an `Idempotency-Key` header, pass the same value as
`idempotency_key` and reuse it when retrying. A result with a `continuation`
holds one part of a long body; read the next part with `egbe_read`, the same
`path` and `business`, and that `continuation`.
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


# Project playbooks

Project playbooks in `egbe-docs/playbooks/` own the method. This skill handles
their delivery, synchronization and change records, not the business decision.

- For setup, follow [initial installation](references/catalog.md#initial-installation).
- Before work with a project method, follow
  [synchronization](references/catalog.md#synchronize-before-method-work).
- Before editing one, read [Changes](references/changes.md) to capture and quietly
  record accepted method changes; also use it to resume unfinished delivery.

## Files downloaded on demand

This skill's scripts and code templates are not bundled with the Egbe plugin
from Claude's directory. They need a persistent project workspace; without one,
tell the founder that the step needs it and continue with the rest of the work.

In a project workspace, before a step that runs or copies one of these files,
download it into `.egbe/skills/egbe-os-playbook/` at the same relative path, for example
`curl -fsSL <url> --create-dirs -o .egbe/skills/egbe-os-playbook/<file>`, and check that its SHA-256
matches. Also download the files it uses from the same folder, such as the
modules a script imports. Wherever this skill names one of these files by its
path in the skill (for example `scripts/...` or `assets/...`), use `.egbe/skills/egbe-os-playbook/<file>`;
where it writes `<skills-directory>`, use `.egbe/skills`.
Keep `.egbe/skills/` out of Git by adding it to `.gitignore`.

| File | URL | SHA-256 |
| --- | --- | --- |
| `scripts/playbook-changes.py` | https://os.hz.egbe.dev/skills/egbe-os-playbook/resources/scripts/playbook-changes.py | `bb1c0d9a4852d39a6f419fd7874b49165a66b195eb612ee101cb2b27682b3bbf` |
| `scripts/playbook_changes/__init__.py` | https://os.hz.egbe.dev/skills/egbe-os-playbook/resources/scripts/playbook_changes/__init__.py | `546af3c76b748c5af681e3d3ea8ed30ec9d5ff998a3041f3caf61727ae396c04` |
| `scripts/playbook_changes/cli.py` | https://os.hz.egbe.dev/skills/egbe-os-playbook/resources/scripts/playbook_changes/cli.py | `3dd6e505706bd86b535bd1285cd45b19da998605465336227be035ce36ebc901` |
| `scripts/playbook_changes/operations.py` | https://os.hz.egbe.dev/skills/egbe-os-playbook/resources/scripts/playbook_changes/operations.py | `226de4ef846814c11656011f513ee878b68a049a4f2c1d624099751071c56400` |
| `scripts/playbook_changes/protocol.py` | https://os.hz.egbe.dev/skills/egbe-os-playbook/resources/scripts/playbook_changes/protocol.py | `27b5fcf0c6fc4f002f73f6ba6dcaa3b839ca1454f00aba7ca61376f9f75bf388` |
| `scripts/playbook_changes/storage.py` | https://os.hz.egbe.dev/skills/egbe-os-playbook/resources/scripts/playbook_changes/storage.py | `5822f16f3a9d1e9c11434161e2dda4c9183c692382d07076d40013bce48c91aa` |
| `scripts/playbook_changes/transport.py` | https://os.hz.egbe.dev/skills/egbe-os-playbook/resources/scripts/playbook_changes/transport.py | `1eb9744354b4296b76e782af1693b9faa65d46a7674d2ee3de4e1479441b6827` |
