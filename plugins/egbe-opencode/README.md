# Egbe for OpenCode

Egbe is an AI co-founder's business stack. This plugin connects
[OpenCode](https://opencode.ai) to the business you run with Egbe, so OpenCode
can build, launch and grow it for you: hosting and databases, email, analytics,
payments, advertising, market research, web search and scraping, and an LLM,
all billed to your Egbe wallet.

It works with OpenCode 1.x (1.18.29 or later) and OpenCode 2.x.

## Get started

1. Add the plugin for every project:

   ```bash
   opencode plugin @egbe-ai/opencode -g
   ```

   Without `-g` it goes into the current project's `opencode.json`. You can
   also add it to the configuration by hand:

   ```jsonc
   // OpenCode 2.x
   { "plugins": ["@egbe-ai/opencode"] }
   ```

   ```jsonc
   // OpenCode 1.x
   { "plugin": ["@egbe-ai/opencode"] }
   ```

   OpenCode installs the package from npm when it starts.
2. Sign in to Egbe once: run `opencode mcp auth egbe` in a terminal (in OpenCode
   2.x, `/mcps` in OpenCode works too), sign in in the browser that opens and
   select **Connect**. Then restart OpenCode.
3. Ask OpenCode to set up Egbe.

You need an Egbe account. The sign-in covers all your Egbe businesses; in each
conversation OpenCode works on the business you name. Manage or disconnect
connected assistants at <https://dashboard.egbe.ai/settings/connections>.

## What the plugin contains

- **The Egbe connector** (`https://os.hz.egbe.dev/mcp`), a remote MCP server
  named `egbe` that OpenCode calls to read your project and perform the work you
  ask for. It signs in through your Egbe account with OpenCode's own MCP sign-in;
  the plugin holds no key. If your configuration already defines an `egbe` MCP
  server, for example one connected with a business key, the plugin keeps yours.
- **Skills** that teach OpenCode how to use each Egbe capability, in the
  package's `skills/` folder. A project's own installed copy of a skill takes
  precedence.
- **Session logging**, described below.

The plugin runs no local server. A skill's scripts run only when OpenCode runs
one for a step in a project folder set up for Egbe.

**In a project folder**, OpenCode also sets the project up for Egbe, which plain
chats skip. It saves your project's Egbe key in the folder's Git-ignored
`.env.local` and copies Egbe's project guidance (`EGBE.md`) and editable working
methods (`egbe-docs/playbooks/`) from the plugin into the project. Egbe's skills
stay in the plugin and update with it.

## What it sends and where

OpenCode sends the requests it makes on your behalf, such as a page to publish,
an email to send or a search to run, to Egbe at `https://os.hz.egbe.dev` over
the connector. Egbe acts only for the business you approved, within your wallet
limits, and records these requests so you can review activity and spending in
Egbe's dashboard. The authorized Egbe team can also read each connector call,
with its inputs and results, to support you and improve Egbe. Some capabilities
pass requests on to the provider that performs them, for example a payment,
email or advertising provider. Egbe's [privacy policy](https://egbe.ai/privacy/)
describes how this data is handled.

**Session logging is on by default.** By installing the plugin you agree that
Egbe records your OpenCode sessions in project folders set up for Egbe;
OpenCode also tells you when it sets up a folder. When a run of a session ends,
the plugin sends that run's turn (your message, model calls with usage, tool
calls with their inputs and results, and the reply) to Egbe at
`https://observe.hz.egbe.dev/telemetry`, authenticated with the project's Egbe
key. Images and attachments are not sent, and secrets are redacted on a
best-effort basis. The authorized Egbe team can read these records. The plugin
sends nothing from a folder that is not set up for Egbe (no private
`.env.local` with Egbe's settings) and never sends anywhere but Egbe. It records
each run's result, never a secret, under `lastSessionLog` in
`~/.local/state/egbe/opencode-plugin.json`.

To stop, ask OpenCode to turn session logging off, or set
`EGBE_SESSION_LOGGING=off` in the project's `.env.local`. To turn it off for
every project, set the plugin's `sessionLogging` option to `false`:

```jsonc
// OpenCode 2.x; in 1.x: { "plugin": [["@egbe-ai/opencode", { "sessionLogging": false }]] }
{ "plugins": [{ "package": "@egbe-ai/opencode", "options": { "sessionLogging": false } }] }
```

## Updates

The plugin updates itself from npm when OpenCode runs for a while: a minute
after it loads and every six hours, it checks npm for a newer `@egbe-ai/opencode`,
verifies the download against npm's SHA-512 integrity and checks that the new
version loads, then installs it. OpenCode 1.x loads it at its next start;
OpenCode 2.x installs and reloads it with `opencode plugin update`. A version
that would change what the plugin can do (its MCP servers, tools, commands or
hooks) is not installed automatically: update it yourself with
`opencode plugin update @egbe-ai/opencode` in OpenCode 2, or in 1.x by deleting
`~/.cache/opencode/packages/@egbe-ai/opencode@latest` and restarting OpenCode.
A pinned version (`@egbe-ai/opencode@0.1.2`) and a plugin loaded from a folder are
not updated; update a cloned folder with `git pull`. Each check is recorded
under `update` in `~/.local/state/egbe/opencode-plugin.json`. To turn updates
off, set the `autoUpdate` option to `false`, as for `sessionLogging` above.

## What it downloads

The plugin itself downloads nothing, and setting up a project folder copies
files that come with the plugin.

Files that exceed the plugin directory's size limits are listed in their
skill; OpenCode downloads one from Egbe only when a step needs it and checks its
SHA-256:

- `egbe-os-design-landing-page/assets/lockfiles/accounts/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/lockfiles/accounts/package-lock.json
- `egbe-os-design-landing-page/assets/lockfiles/auth-db/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/lockfiles/auth-db/package-lock.json
- `egbe-os-design-landing-page/assets/scaffold/package-lock.json` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/package-lock.json
- `egbe-os-design-landing-page/assets/scaffold/.gitignore` from https://os.hz.egbe.dev/skills/egbe-os-design-landing-page/resources/assets/scaffold/.gitignore

## Support

Questions and problems: ask OpenCode to open an Egbe support ticket, or email
<support@egbe.ai>.
