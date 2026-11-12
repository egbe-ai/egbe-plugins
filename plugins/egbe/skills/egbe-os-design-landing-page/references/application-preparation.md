# Application preparation

Inspect the project before choosing a foundation. Preserve an existing framework,
lockfile, package manager, Dockerfile, source control, storage, analytics and deploy
bindings. Do not copy a scaffold over a working app or create a second repository.

For a new application that fits the bundled Next.js stack, use `assets/scaffold/`
from this skill. Copy only missing files and resolve collisions deliberately;
preserve the founder's files, installed skills and `.env.local`. The supplied
page is empty, not a layout to imitate. Another supported stack can use Deploy's
current contract without inheriting this scaffold.

Product Build's `references/foundations.md` documents the optional local
`scripts/scaffold.py` helper for previewing and copying this starter and any
selected compatible Auth/subscription foundations. Use its `plan` command before
`apply`; it preserves existing project guidance and rejects conflicting files.

Initialize Git if necessary and use the Git skill to connect the product repository
before publishing. Ignore secrets, dependency/build output and machine-only state;
keep resumable project documents versioned but outside public builds.

Install dependencies with the lockfile-safe command only when missing, changed
or demonstrably broken. Reuse them and the build output for subsequent lint/build
iterations; do not force-add or delete them in commit/push chains.

Configure Analytics and Errors through their current skills, reusing project
bindings. Prepare public build configuration as Deploy specifies. For the bundled
scaffold, populate `src/lib/egbe-observability.generated.ts` with the public
identifiers/snippets returned by those capabilities; its empty baseline is not
configured observability. The copied `AGENTS.md` describes this setup boundary;
it does not attest that a preset provisioned resources. Reuse verified existing
bindings, configure only missing ones and verify actual delivery through the
capabilities' readback. Never put OS credentials or server secrets there.

Use platform-injected runtime credentials as described by Product Build's
capability reference. A stateless page requires neither database nor signup;
attach them only for accepted behavior. Implement the page before publishing,
not an empty scaffold as an artificial prerequisite. Deploy the intended committed
revision through OS and verify the returned actual host when publication is authorized.
