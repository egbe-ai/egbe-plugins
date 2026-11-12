---
name: egbe-os-domains
description: Assign/move .egbe.app addresses or arrange admin setup of custom domains.
metadata:
  egbe-when: "Use when a deployed app needs a named address or domain change."
  egbe-category: "Development & hosting"
  egbe-visible: "true"
  egbe-title: "Website addresses & domains"
  egbe-description: "Choose or move your .egbe.app address, or arrange a custom domain with help from the Egbe team."
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


# Your app's public address

Every app you deploy always has a **canonical host** — `my-app-e64a1fbe2153.n.egbe.app`.
It works, but it carries your instance id, so it reads like plumbing rather than
a product.

A **domain** is a second, prettier address layered on top: `my-app.egbe.app`.
Both point at the same app. The canonical host never stops serving, so attaching
or releasing a domain can't take your app down.

Base URL: `https://os.hz.egbe.dev`. Authenticate every call with
`Authorization: Bearer $OS_API_KEY`.

## You usually don't have to do anything

Your **first deploy claims a domain for you** from the app's slug: deploy
`my-app` and it comes up on `https://my-app.egbe.app`. The deploy response and
`GET /deploy/<slug>` both carry it:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/deploy/my-app" -s
# data: { "host": "my-app-e64a1fbe2153.n.egbe.app",   <- canonical, always serves
#         "domain": "my-app.egbe.app",                <- the alias, null if none
#         "url": "https://my-app.egbe.app" }          <- give THIS to customers
```

Always hand customers `url`. It is the domain when you have one and falls back to
the canonical host when you don't, so it is correct either way.

## Choosing a different name

Use the founder's selected name or recorded naming delegation. Otherwise suggest
available alternatives without claiming availability before verification,
recommend one and wait for a choice or delegation, once or throughout this
business. A taken name is not permission to silently choose another public brand.
Apply the same decision boundary before releasing or redirecting an established
customer-facing address; return unresolved choices to the caller when needed.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/domains" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"slug":"my-app","name":"acme"}'      # -> https://acme.egbe.app
```

`name` is the label only — letters, digits and dashes, no dots. `acme` becomes
`acme.egbe.app`. Names are first-come, first-served across the whole platform: a
name another business already holds comes back as `domain_taken`, and a handful
of platform names (`www`, `mail`, `api`, `admin`, …) are reserved.

## One domain per business

The limit is `site-gateway:domains`, **1**. It is an inventory limit — it never
resets; you free it by releasing the domain.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/me/limits?resource=site-gateway:domains" -s
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/domains" -s   # what you hold, and where it points
```

So a second app does **not** get a pretty address — it stays on its canonical
host, and the deploy response says so in `warnings`. That is deliberate: a
business ships one brand.

## Moving it to another app

Pointing your existing domain at a different app is a move, not a second claim —
it does not need a release first:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/domains" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"slug":"my-other-app","name":"acme"}'
```

To give the name up entirely and free your slot:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/domains/my-other-app" -s -X DELETE
```

Deleting an app (`DELETE /deploy/<slug>`) releases its domain for you.

## Bring your own domain (client landings, requires Egbe admin setup)

A paid-ads test for a **client** must land on the client's own domain
(`try.client.tld`), not on `*.egbe.app`: Meta verifies the destination domain
in the advertiser's Business Manager, Google rejects landings on an unrelated
domain, and attribution breaks when the funnel continues on the client's site.

This is a separate allowance, `site-gateway:external-domains`, and it is **0 by
default** — an Egbe admin raises it for the one business running the test. Until
then the call below comes back `external_domain_limit_reached`. It does not
touch your `<name>.egbe.app` alias: an app can carry both.

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/domains" -s -X POST  \
 -H 'Content-Type: application/json' \
  -d '{"slug":"landing","host":"try.client.tld"}'
# data: { "host": "try.client.tld", "url": "https://try.client.tld", "external": true,
#         "dns": [ { "type":"CNAME", "name":"try.client.tld",
#                    "value":"landing-e64a1fbe2153.n.egbe.app" },
#                  { "type":"CNAME", "name":"_acme-challenge.try.client.tld",
#                    "value":"_acme-challenge.try-client-tld.n.egbe.app" } ],
#         "tls": { "ready": false, "reason": "Pending", ... } }
```

Hand the domain owner **both** `dns` records, exactly as returned. If they use
Cloudflare or a similar proxy, the records must be **DNS only** (grey cloud) —
a proxied record breaks both the certificate and the routing. Use a subdomain;
an apex only works where the provider supports CNAME flattening.

The second record is how ownership is proven: only whoever controls the zone
can point it at us, and the certificate for the host is issued through it. Until
it issues, `tls.ready` is `false`, the host serves nothing and the app keeps
serving on its canonical host and alias. Poll `GET /domains` — once `tls.ready`
is `true`, `url` serves the app over HTTPS. `tls.reason` / `tls.message` say
what it is waiting for (almost always the `_acme-challenge` CNAME).

When an app has both an alias and an external host, `url` is the external host.
Release just the external one and keep the alias with
`DELETE /domains/landing?host=try.client.tld`; deleting the app releases both.

## When something goes wrong

| Response | What it means |
| --- | --- |
| `domain_taken` | Another business holds that name or host. Pick a different one. |
| `domain_limit_reached` | You already use your one domain. Release it, or move it instead. |
| `reserved_domain_name` | Platform-reserved label. Pick a different one. |
| `app_not_found` | Deploy the app first — a domain points at a live app. |
| `external_domain_limit_reached` | Bring-your-own domains are not enabled for this business. Contact the Egbe team. |
| `external_host_not_allowed` | `host` was under `egbe.app` / `egbe.dev`. Use `name` for a pretty alias. |
| `invalid_external_host` | Not a valid host name. Pass a full subdomain like `try.client.tld`. |
| deploy `warnings` mention the domain | The app is live on its canonical host; only the alias didn't attach. Nothing is down. |
