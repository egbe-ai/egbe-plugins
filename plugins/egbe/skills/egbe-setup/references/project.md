# Set up a project folder with the Egbe plugin

The Egbe plugin gives every session in this folder Egbe's skills, so the project
needs only what belongs to it: saved credentials, editable playbooks and project
guidance. Do not install Egbe skills into the project, and do not download or
run Egbe's catalog installer. The steps below write small text files and copy
files that come with the plugin.

1. Call `egbe_local_setup` with the `business` that `egbe_setup` returned. Never
   show its `OS_API_KEY` in chat, and keep it out of logs, commits, URLs and
   search queries.
2. Follow the `instructions` it returns. Do their project files step as
   [project files](#project-files) below describes, from the plugin's own
   files, not with `egbe_workspace_files`: the plugin brings the same
   playbooks, and its `EGBE.md` indexes the skills the plugin provides.

## Project files

Work from the project root. "This skill's folder" is the folder holding the
`egbe-setup` skill's `SKILL.md`. Reuse what is already in place; ask the founder
before replacing a file that differs.

Use file tools to read and write files. Run each shell command on its own, with
absolute paths: no `&&`, `;` or pipes, no `cd`, no shell variables, and never the
key in a command. Claude Code then asks for fewer approvals, and a refused
compound command does not stall setup.

- **Credentials.** Save them as the instructions' credentials step describes:
  write `.env.local` with the file tools, then
  run `chmod 600 .env.local` as its own command.
- **Private files.** Make sure `.gitignore` ignores `.env.local`. Unless
  `.gitignore` already ends with the lines below, append them; they keep private
  working files in `egbe-docs/` out of Git:

  ```gitignore
  !/egbe-docs/marketing/campaigns/instantly/outreach.db
  /egbe-docs/**/.local/
  /egbe-docs/**/.env
  /egbe-docs/**/.env.*
  /egbe-docs/**/*.lock
  /egbe-docs/**/*.tmp
  /egbe-docs/**/*-wal
  /egbe-docs/**/*-shm
  /egbe-docs/**/*-journal
  ```

  Likewise end `.dockerignore` with these lines, which keep `egbe-docs/` out of
  builds:

  ```gitignore
  /egbe-docs/
  .git
  ```

- **Playbooks.** Copy the files in the `egbe-os-playbook` skill's `playbooks/`
  folder (`../egbe-os-playbook/playbooks/` from this skill's folder) to the same
  paths under `egbe-docs/playbooks/` with one command,
  `rsync -a --ignore-existing <source>/ egbe-docs/playbooks/`, where `<source>` is
  that folder's absolute path. Add only files
  whose path does not exist yet; never replace or delete a project file, and
  report any file you could not add. These are the project's editable methods.
  Do not create `egbe-docs/playbooks-sync.json`: it records a finished method
  review, not delivery.
- **Project guidance.** Copy `EGBE.md` from this skill's folder to the project
  root as a regular file: read it and write the same text with the file tools.
  Claude Code treats its plugin folder as protected, so `cp` from there can be
  refused. Add this exact line to the root `CLAUDE.md`, keeping
  existing instructions and reusing an equivalent entry:
  `Read and apply EGBE.md when working on this project.` Then read the whole
  `EGBE.md` once and use it for the rest of setup.

- **Session logging.** The plugin records this folder's sessions by default.
  Don't ask for consent: tell the founder once and record the choice as the
  `egbe-os-telemetry` skill's plugin section describes, unless a saved choice
  declines logging.

Later, the `egbe-os-playbook` skill's catalog guide delivers new playbooks and
keeps `EGBE.md` current from the plugin. Egbe's skills update with the plugin.
