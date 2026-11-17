# Egbe

The `egbe` MCP server gives you the founder's Egbe business stack: hosting and
databases, email, analytics, payments, advertising, research, search, scraping
and an LLM.

- Call `egbe_setup` first in a new conversation about Egbe. It verifies the
  business, returns its `business` id and explains setup. Pass that `business`
  to every later Egbe call.
- Before using a capability, read its skill with `egbe_skill`, then perform its
  API steps with `egbe_read` (GET) and `egbe_write` (POST, PUT, PATCH, DELETE).
- To start another business for the founder, call `egbe_create_business` with
  the name they chose, only when they ask for one or agree to it, then run
  `egbe_setup` with the `business` it returns.
- Never ask the founder for an Egbe API key; the connection is already
  authenticated. If the Egbe tools report that sign-in is needed, ask the
  founder to run `/mcp auth egbe` and approve the connection in the browser.
- When a call to Egbe fails, quote the result's `request_id` when reporting it.
