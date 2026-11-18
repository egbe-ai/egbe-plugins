---
name: egbe-os-git
description: Create an Egbe repository, push local code or commit files without a terminal, and read code back.
metadata:
  egbe-when: "Use when code needs versioning or a repository for publication."
  egbe-visible: "true"
  egbe-title: "Code repositories"
  egbe-description: "Create an Egbe-hosted repository to store, version and publish your app's code."
  egbe-category: "Development & hosting"
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
Read bundled files beside this `SKILL.md`. For published skill resources on
Egbe OS, use `egbe_skill`. Follow "Files downloaded on demand" for listed downloads.

Publishing works through the connector: commit the app's files with the JSON
commit requests in `egbe-os-git` ("Without a terminal") and deploy the returned
commit SHA; no git push or workspace setup is needed. A step that needs a local
project key or a bundled script, such as a local `npx convex deploy`, needs a
set-up project workspace. In a persistent
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
Code on their own computer. Code can also be published without the shell by
committing through the connector (`egbe-os-git`, "Without a terminal"). Until
the shell step or that commit and its deploy succeed, do not report the work as
published: a Claude Artifact or a local preview is not an Egbe deployment.


# Git

Native Git can push, fetch and clone through `https://os.hz.egbe.dev/git/http/<repo>.git`
using `Authorization: Bearer $OS_API_KEY` with the `git` scope. OS resolves your
account's Forgejo owner and credential internally. The remote contains no secret;
no Forgejo token export or credential helper is required for this transport.
Git and Forgejo handle commits, history, branch protection and push conflicts.

## Start from your local project

A local branch such as `master`, uncommitted changes, a missing remote or absent
Vercel/Netlify files are normal setup, not evidence Egbe deployment is blocked.
Within the founder's existing publishing/deployment authorization:

1. Inspect `git status`, the current branch and remote names with `git remote`. Preserve existing
   history and remotes. Do not print remote URLs or Git config: older remotes may
   contain credentials. Initialize Git only if absent. Read `/deploy/skill` for the
   Dockerfile/build requirements; configure `.gitignore` and `.dockerignore` before
   staging so `.env.local`, credentials, dependencies and build output stay private.
2. List repositories with `GET /git/repos`; reuse the intended repository or create
   an empty private one with `POST /git/repos`. Paginate with `page` and `limit`
   (1–50, default 50) until a page has fewer than `limit` items; match the exact
   `owner`/`name` or `full_name`, not a substring. Check HTTP success before proceeding.
   Both operations return clean metadata and `os_http_url`. This URL is available
   for the authenticated account’s own namespace; it is null for collaborator-owned
   repositories, whose issues remain accessible according to repository permissions.
   Do not substitute a same-named repository from another owner.
3. Check author and committer identities with `git var GIT_AUTHOR_IDENT` and
   `git var GIT_COMMITTER_IDENT`. If missing, choose identities approved for this
   project and save them with `git config --local user.name` / `user.email`.
   Preserve existing identities. These are commit metadata, never API credentials.
4. Review and commit the intended files, then push the current branch through the
   OS HTTP remote. Use the exact full pushed SHA from `git rev-parse HEAD` as the
   `ref` in `POST /deploy`. No branch rename or force push is needed.
5. Verify deployment status, deployed revision and public URL per `/deploy/skill`.

```bash
# OS_URL and OS_API_KEY come from the existing quickstart connection.
# List first; create only if the intended repository is absent.
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/git/repos" -fsS
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/git/repos" -fsS -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"name":"my-app","private":true}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["os_http_url"])'
# No Forgejo credentials or direct transport addresses are returned.

# Add a dedicated remote without replacing an existing origin.
REMOTE="$OS_URL/git/http/my-app.git"
# Replace all fetch and push targets on this dedicated remote. A legacy pushurl
# otherwise overrides url and can silently push directly to Forgejo.
git config --local --replace-all remote.egbe.url "$REMOTE"
git config --local --replace-all remote.egbe.pushurl "$REMOTE"
git config --local --replace-all remote.egbe.fetch '+refs/heads/*:refs/remotes/egbe/*'
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
# Review git status/diff, stage intended source files, and commit before pushing.

# Pass the key via a temporary environment variable, scoped to this remote.
# Do not enable shell tracing, store this header in Git config, or print it.
REMOTE="$OS_URL/git/http/my-app.git"
export OS_GIT_AUTH="Authorization: Bearer $OS_API_KEY"
git --config-env="http.$REMOTE.extraHeader=OS_GIT_AUTH" push -u egbe HEAD
unset OS_GIT_AUTH
git rev-parse HEAD
```

For an existing project with a legacy Forgejo origin, select the same repository
from the paginated list and use its OS URL on the dedicated `egbe` remote above.
Keep `origin` unchanged; use `egbe` explicitly for push/fetch. Never expose a legacy
URL while comparing remotes, and do not rotate keys or recreate the repository.
Preserve the current branch name. For an intentional differently named remote
branch use `HEAD:<approved-branch>`; do not overwrite unrelated history. On a
rejected push, fetch and inspect the remote changes or publish a new branch.
After a timeout/disconnect, inspect remote refs before deciding whether to retry;
a lost response does not prove the push failed.

## Clone or fetch

Use the same temporary, remote-scoped header with every authenticated Git call:

```bash
REMOTE="$OS_URL/git/http/my-app.git"
export OS_GIT_AUTH="Authorization: Bearer $OS_API_KEY"
git --config-env="http.$REMOTE.extraHeader=OS_GIT_AUTH" clone "$REMOTE"
# Inside an existing clone whose egbe remote matches REMOTE:
# git --config-env="http.$REMOTE.extraHeader=OS_GIT_AUTH" fetch egbe
unset OS_GIT_AUTH
```

This requires Git with `--config-env` support (2.31+). Git smart HTTP uses raw
protocol responses, while repository management APIs use the normal OS envelope.
The adapter supports discovery, upload-pack and receive-pack only; Git LFS and
dumb HTTP are outside this transport. OS keys are valid here, not as direct
Forgejo passwords.

## One OS contract

Repository management, issues and comments use the same OS API and authentication
in REST and MCP. `GET /git/credentials` returns 410 and no credentials. Refresh
this skill and use the OS operations; do not request a Forgejo token, construct
a direct Forgejo URL or send the OS key to Forgejo. Internal credentials stay on
the server. Existing repositories and saved remotes are not deleted or revoked.

If a shell network policy blocks OS, follow quickstart’s environment recovery for
`os.hz.egbe.dev` (or the configured OS host), or commit through the API below.
Direct Forgejo access is not required and is not the recovery path. MCP cannot
carry Git smart HTTP bytes, but it carries every repository, issue and commit
operation in this skill.

Escalate the actual redacted authorization/provisioning/network/build error,
not missing configuration. When the OS key cannot reach a Git process, commit
through the API below instead of reporting publication as blocked.

## Without a terminal: commit through the Egbe connector

Use this when the agent has no shell or Git, or its shell cannot reach Egbe (for
example a chat in claude.ai, Cowork or ChatGPT). Every step is a JSON request,
so it works through `egbe_read`/`egbe_write`; nothing contains `.git`. A
workspace with Git can keep using the push flow above.

1. Pick the repository from `GET /git/repos` (one with a non-null `os_http_url`,
   your own namespace) or create it with `POST /git/repos`.
2. Read what is there. `GET /git/repos/<owner>/<repo>/tree` with `ref` (default:
   the default branch) returns `commit`, the branch head's full SHA, and
   `entries` (`path`, `type`, `mode`, `size`, `sha`); request `page=<next_page>`
   until `next_page` is null. A repository without commits answers 404 with
   `data.empty: true`: its base is `""`. Read a file with
   `GET /git/repos/<owner>/<repo>/file` and `path`, `ref=<commit>`: `content` is
   UTF-8 text or, with `encoding: "base64"`, binary. Repeat with
   `offset=<next_offset>` until `next_offset` is null. Files over 10 MB are not
   readable here.
3. Commit. A small change is one request:

   ```json
   POST /git/repos/<owner>/<repo>/commits
   {"base": "<commit>", "message": "Add pricing page",
    "files": [{"path": "src/pricing.html", "content": "<h1>Pricing</h1>\n"}],
    "delete": ["src/old.html"]}
   ```

   For more files, send the same request without `message` to open a session
   (response `session_id`), add batches with
   `POST /git/commit-sessions/<session_id>/files` (`files`, `delete`), then
   `POST /git/commit-sessions/<session_id>/commit` with `{"message": "..."}`.
   Nothing reaches the branch until that call, which makes one commit.
   - `base` is required: the branch head SHA you read, or `""` for an empty
     repository or a new branch. `branch` defaults to the repository's default
     branch. With `"base": ""` and `from_branch`, a new branch starts from that
     branch's head.
   - `encoding` is `utf-8` (default) or `base64` for images, fonts and other
     binary files. `executable: true` marks scripts; an existing file keeps its
     mode otherwise. `delete` removes files or whole folders of the base.
   - Paths are relative and `/`-separated, without `..` or `.git`. Send source
     files only: never `.env*` with real values, `node_modules/` or build output.
   - Keep each request under 700,000 bytes (base64 grows content by a third; aim
     for about 450 KB of file content per batch). For a larger file, send its
     first part, then the rest in later batches with `"append": true` on the same
     path. A later batch replaces a path staged earlier.
   - Optional `author: {"name", "email"}` on the commit uses an identity approved
     for this project; the default is Egbe OS.
   - A template or other file bundled with an Egbe skill is copied on the server
     instead of sent: give the entry `from_skill` in place of `content`, such as
     `{"path": "src/quiz/quiz-engine.mjs", "from_skill": {"skill": "egbe-os-quiz-funnel",
     "path": "assets/engine/quiz-engine.mjs"}}`. A `from_skill.path` ending in `/`
     copies every file of that skill folder into the folder `path` names (`""`
     for the repository root), each counting as one batch entry. The connector's
     `egbe_skill` with `resource: ""` (or a folder ending in `/`) lists a skill's
     files with their size and SHA-256; copies are byte-exact, keep a script's
     executable mode and count toward the same limits.
   - Product Build's shipped application and account foundations install into a
     session with `POST /git/commit-sessions/<session_id>/scaffold`; see its
     `references/foundations.md`.
4. The result's `sha` is the full commit SHA: pass it as `ref` to `POST /deploy`
   (see `/deploy/skill`). `changed: false` means the files matched the base and
   no commit was made.

Limits: 10 MB per file, 50 MB and 2,000 paths per commit, 500 entries per batch,
3 open sessions per business. A session expires 30 minutes after its last request
(2 hours at most); `GET /git/commit-sessions/<session_id>` shows its state, staged
paths and result, and `DELETE` discards it.

A 409 whose `data.head` differs from your `base` means the branch moved; nothing
was written. Read the changed files at `data.head`, reapply your edits where
needed, then repeat the commit call with `"base": "<data.head>"`: the staged files
replace those paths at that head. Egbe never force-pushes. After a timeout or a
lost response, repeat the same session's commit call: a finished session returns
its commit again with `replayed: true`. For a one-shot request, read the tree
first; if its `commit` differs from your base, check whether your change is
already there before committing again.

## Product backlog

To read or update issues in this project's repository, follow
[Repository issues](references/issues.md). It uses the same OS connection; no direct Forgejo access is needed.
