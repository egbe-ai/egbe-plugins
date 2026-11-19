**Next:** run `hermes egbe connect` to add Egbe's MCP server to this profile and
sign in to Egbe, then start Hermes in your project folder and ask it to set up
Egbe.

**Session logging is on by default** in project folders set up for Egbe: your
messages, model calls with usage, tool calls with their results, and replies go
to Egbe after each turn, redacted, for the authorized Egbe team. Set
`EGBE_SESSION_LOGGING=off` in the project's `.env.local` to stop. See the
plugin's README for details.
