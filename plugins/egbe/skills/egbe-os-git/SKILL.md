---
name: egbe-os-git
description: Create an Egbe repository and push local code, including projects without a remote.
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

1. Inspect `git status`, the current branch and `git remote -v`. Preserve existing
   history and remotes. Initialize Git only if absent. Read `/deploy/skill` for the
   Dockerfile/build requirements; configure `.gitignore` and `.dockerignore` before
   staging so `.env.local`, credentials, dependencies and build output stay private.
2. List repositories with `GET /git/repos`; reuse the intended repository or create
   an empty private one with `POST /git/repos`. Check HTTP success before proceeding.
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
# Repo creation retains a legacy secret push_url; print only os_http_url.

# Add a dedicated remote without replacing an existing origin.
git remote add egbe "$OS_URL/git/http/my-app.git"
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

If the dedicated remote already exists, verify its URL instead of adding it again.
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

## Deprecated credential endpoint

`GET /git/credentials` is marked deprecated in OpenAPI and returns
`data.deprecation` with the OS HTTP remote template, authentication/scope and
this skill's URL. For Git push/clone/fetch, use the OS-key transport above;
do not fetch a Forgejo token or configure a credential-bearing remote.
Legacy credential fields remain available for compatibility. Native Forgejo
REST API operations such as issues/comments still need them until an OS API
replacement exists; `/git/http` transports Git and cannot accept REST requests.
Keep returned tokens and legacy authenticated URLs private.

Escalate the actual redacted authorization/provisioning/network/build error,
not missing configuration. A browser-only vault that cannot provide the OS key
to a Git process still needs a separate browser source-transfer path; this shell
transport does not resolve that constraint. Report that specific limitation.

## Product backlog

To read or update issues in this project's repository, follow
[Repository issues](references/issues.md). It uses these same project
credentials and Forgejo's native API.
