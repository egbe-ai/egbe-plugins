# Repository issues

Compatibility exception: `/git/credentials` is deprecated for native Git
push/clone/fetch; use the OS-key `/git/http/<repo>.git` transport for those.
Issue/comment operations below still use Forgejo's REST API and require its
credential. `/git/http` does not proxy REST; do not send these requests there.

Use the product's existing repository for its backlog. Resolve the repository
from its remote or `GET /git/repos`, and obtain `base_url`, `username`, `token`
from `GET /git/credentials`. Send `Authorization: token <token>` to that
Forgejo base URL, not the OS key. Keep the token out of issue bodies and logs.

The API prefix is `<base_url>/api/v1/repos/<owner>/<repo>`. Use the returned
repository owner/name, including when they differ from the credential username.

| Operation | Method and relative path | JSON body / query |
|---|---|---|
| List | `GET /issues` | `type=issues&state=open&page=1&limit=50` |
| Read | `GET /issues/<index>` | — |
| Create | `POST /issues` | `{"title":"...","body":"..."}` |
| Edit or close | `PATCH /issues/<index>` | Changed fields; `{"state":"closed"}` to close |
| Read comments | `GET /issues/<index>/comments` | `page=1&limit=50` |
| Comment | `POST /issues/<index>/comments` | `{"body":"..."}` |

Use the repository-local issue `number` as `<index>`, not its global database
`id`. Follow pagination when checking existing issues; search/read before
creating another report of the same problem. A timeout after a create/comment
is an unknown outcome: read back before retrying to avoid duplicates.

Only make the backlog changes required by the founder's task. A 401/403 is an
access failure, not a reason to switch identities. Check the repository and
permissions for a 404; do not replace a missing remote backlog with a different
project's repository. Request/response schemas are available from the
instance's `/swagger.v1.json` ([Forgejo API usage](https://forgejo.org/docs/latest/user/api/usage/)).
