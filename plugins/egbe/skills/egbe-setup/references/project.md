# Set up a project folder with the Egbe plugin

The Egbe plugin gives every session in this folder Egbe's skills, so the project
needs only what belongs to it: saved credentials, editable playbooks and project
guidance. Do not install Egbe skills into the project, and do not download or
run Egbe's catalog installer. The steps below write small text files and copy
files that come with the plugin.

1. Call `egbe_local_setup` with the `business` that `egbe_setup` returned. Never
   show its `OS_API_KEY` in chat, and keep it out of logs, commits, URLs and
   search queries.
2. Follow the `instructions` it returns, with two changes:
   - Do quickstart step 3 (skills, playbooks and project guidance) as
     [project files](#project-files) below describes, not through the catalog
     installation.
   - Where quickstart or its connection setup uses the installed request helper
     (`egbe-curl.py`) or catalog helper (`sync-catalog.py`), use `egbe_request`
     and `egbe_complete_setup`, passing `business`.

## Project files

Work from the project root. "This skill's folder" is the folder holding the
`egbe-setup` skill's `SKILL.md`. Reuse what is already in place; ask the founder
before replacing a file that differs.

- **Credentials.** Save `OS_URL`, `OS_API_KEY` and this agent's connection ID in
  `.env.local` as quickstart's connection setup ("Save credentials and connection
  identity") describes, keeping other entries. Give the file permissions 600.
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
  paths under `egbe-docs/playbooks/`, for example with
  `rsync -a --ignore-existing <source>/ egbe-docs/playbooks/`. Add only files
  whose path does not exist yet; never replace or delete a project file, and
  report any file you could not add. These are the project's editable methods.
  Do not create `egbe-docs/playbooks-sync.json`: it records a finished method
  review, not delivery.
- **Project guidance.** Copy `EGBE.md` from this skill's folder to the project
  root as a regular file, for example with `rsync`, or by reading it and writing
  the same text with file tools. Add this exact line to the root `CLAUDE.md`, keeping
  existing instructions and reusing an equivalent entry:
  `Read and apply EGBE.md when working on this project.` Then read the whole
  `EGBE.md` once and use it for the rest of setup.

Later, the `egbe-os-playbook` skill's catalog guide delivers new playbooks and
keeps `EGBE.md` current from the plugin. Egbe's skills update with the plugin.
