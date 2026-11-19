# Platform capabilities and credentials

Before choosing an integration, find the capability in public `GET /` and read
its `instruction_url` (or the corresponding installed skill):

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/" -fsS
curl -fsS "${OS_URL}<instruction_url-from-catalog>"
```

Use the configured OS_URL, normally https://os.hz.egbe.dev. Do not substitute a
guessed endpoint, provider host, copied stale schema or canned local result for
an unclear capability. Establish a credible implementation or report the exact
missing contract.

The local agent's OS_API_KEY is for discovery and authorized control-plane actions.
Never copy it into product code, APP_ENV_JSON, plans or client bundles. Product
server code uses OS_URL and OS_API_KEY supplied by the Site Gateway's product-runtime
identity. Do not mint, rename or deploy an agent key or invent per-capability keys.
Missing runtime identity is a platform deployment fault, not a reason to bypass it.

Keep the repository, deployment slug, database and other existing bindings unless
the task requires a deliberate change. Use the current Deploy contract for build,
runtime environment and release verification; use domain skills for their schemas,
authorization, errors and recovery instead of duplicating them here.
