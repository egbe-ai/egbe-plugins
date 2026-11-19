# Repository issues and comments through OS

Use the project's existing repository for its backlog. Find its exact `owner` and
`name` in paginated `GET /git/repos`, retaining `full_name` to distinguish same-named
repositories. Never print a legacy remote URL: it may contain credentials.
Use the configured OS host and `Authorization: Bearer $OS_API_KEY`, as for repository
creation. Through MCP use `egbe_read`/`egbe_write` with the selected business.
The server resolves the upstream credential and applies the caller's repository
permissions. A repository shared with this account may support issues even when
its `os_http_url` is null; native OS Git transport covers the account's own namespace.

The OS prefix is `/git/repos/<owner>/<repo>/issues`:

| Operation | Method and relative path | JSON body / query |
|---|---|---|
| List | `GET` prefix | `state=open` (or `closed`, `all`), `page=1&limit=50` |
| Read | `GET /<number>` | — |
| Create | `POST` prefix | `{"title":"...","body":"..."}` |
| Edit or close | `PATCH /<number>` | Changed `title`, `body`, `state`; `{"state":"closed"}` to close |
| Read comments | `GET /<number>/comments` | `page=1&limit=50` |
| Comment | `POST /<number>/comments` | `{"body":"..."}` |

Responses use the normal OS envelope. Issue lists exclude pull requests. Use the
repository-local issue `number`, never its global database `id`. Comment `id` is
returned as metadata; these operations do not edit/delete comments. For repository,
issue and comment lists, increment `page` until fewer than `limit` items are returned
(`limit` 1–50, default 50). Search/read before creating to avoid duplicates.

Only make changes required by the founder's task. For a failed or disconnected
write, read back before retrying: the write may already have succeeded. A 401/403
is an access failure; a 404 may mean missing data or inaccessible private data.
Do not switch identity or create a different project's backlog to bypass it.
No Forgejo URL or token is required; the retired `/git/credentials` returns 410.
