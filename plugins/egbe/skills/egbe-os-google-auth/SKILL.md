---
name: egbe-os-google-auth
description: Add Google signup and login to a deployed product.
metadata:
  egbe-when: "Use when customers need Google sign-in."
  egbe-visible: "true"
  egbe-title: "Google sign-in"
  egbe-description: "Let customers sign up and sign in with Google without managing your own Google OAuth credentials."
  egbe-category: "Payments & accounts"
---

<!-- egbe-mcp-connection:v1 -->
This skill comes with the Egbe plugin. Make every Egbe API call it describes with
the Egbe connector's `egbe_request` tool: pass the HTTP method, the API path (for
example `/me/limits`), query parameters in `query` and the JSON body in `body`.
For these calls leave out `OS_URL`, the Authorization header, `.env.local` and
`egbe-curl.py`, and skip catalog update checks; the connection authenticates and
identifies the request.
Also pass the `business` that `egbe_setup` returned. Files this skill refers to
are next to this `SKILL.md`, except any listed under "Files downloaded on demand".

A step that needs a local project key, such as a git push or a local deploy
command, works only in a persistent project workspace. There, if the project's
Git-ignored `.env.local` has no `OS_API_KEY` yet, call `egbe_local_setup` once
and save its `OS_URL` and `OS_API_KEY` there, preserving other entries. Use only
those two values: the plugin already provides Egbe's skills, so do not install
the Egbe catalog or follow the rest of that result. Never show the key in chat or
put it in logs, commits or URLs. Without such a workspace, tell the founder that
this step needs an agent with a project folder, and continue with the rest of
the work.


# Product Google Sign-in

Egbe OS owns the Google OAuth client and verifies the external identity. The
product owns its local user, provider link, session, authorization, and logout.
Product code needs only its normal server-side `OS_URL` and `OS_API_KEY`.
The HTTP examples below describe requests from that backend to its configured
Egbe URL, using its product-runtime credential. Implement them with the
product's HTTP client; no agent catalog, workspace helper or connection identity
belongs in the deployed application.

Never put the OS key in browser code. Never add Google client credentials to the
product, call Google's token endpoint from the product, or treat an email/query
parameter as authenticated identity.

## Start from the product backend

Create a same-origin product route such as `/api/auth/google/start`. It calls:

```http
POST /auth/google/intents HTTP/1.1
Host: <configured Egbe host>
Authorization: Bearer <server-side product key>
Content-Type: application/json

{
    "app_slug": "<deployed-slug>",
    "return_path": "/auth/google/complete?next=%2Fdashboard"
  }
```

Redirect the browser to `data.start_url`. `return_path` is relative and must be
handled by the same product backend. When a product deliberately serves more
than one registered host, pass `return_origin`; Egbe OS accepts it only when it
exactly matches an authoritative deployed origin.

## Exchange on the product backend

Egbe OS returns the browser to `return_path` with either
`egbe_auth_code=<opaque-code>` or `egbe_auth_error=<safe-code>`. Exchange the
opaque code immediately from the server:

```http
POST /auth/google/exchange HTTP/1.1
Host: <configured Egbe host>
Authorization: Bearer <server-side product key>
Content-Type: application/json

{"app_slug":"<deployed-slug>","code":"<egbe_auth_code>"}
```

The result contains `provider`, immutable Google `subject`, verified `email`,
`email_verified`, optional `name`, and optional `picture`. Use
`(provider, subject)` as the external identity key. In one database transaction:

1. return the user already linked to that identity;
2. otherwise link the identity to the existing account with the same normalized
   verified email;
3. otherwise create the local user and identity link;
4. only then create the product's ordinary opaque server-side session.

Unique constraints must make concurrent callbacks converge on one identity and
one user. Do not overwrite an existing password hash when linking Google. Clean
the callback code from the browser URL after the session is established.

## Optional: Google One Tap

One Tap shows Google's floating sign-in prompt (top-right) without a redirect.
It is an addition to the redirect flow above, not a replacement — always keep
the button flow as the fallback: One Tap silently shows nothing when the
visitor has no Google session, dismissed it recently, or the browser blocks it.

How it works: Egbe OS hosts the actual GSI widget in an iframe on its own
origin (`os.hz.egbe.dev`, registered with Google once — product domains never
need Google Console changes). The product page embeds that frame through
Google's intermediate-iframe parent library, the frame posts the signed
credential back to the page, and the product backend exchanges it through
Egbe OS for the same verified identity as the redirect flow.

### 1. Backend: mint an intent

Create a same-origin route (e.g. `GET /api/auth/google/onetap/intent`) that
calls:

```http
POST /auth/google/onetap/intents HTTP/1.1
Host: <configured Egbe host>
Authorization: Bearer <server-side product key>
Content-Type: application/json

{"app_slug":"<deployed-slug>"}
```

and returns to the browser: the `nonce`, the frame URL
`https://os.hz.egbe.dev/auth/google/onetap/frame?nonce=<nonce>`, and the frame
origin `https://os.hz.egbe.dev`. The nonce is single-use and expires with the
intent — mint a fresh one per page load, never cache it.

### 2. Page: embed through Google's parent library

Load ONLY `https://accounts.google.com/gsi/intermediate` on the product page.
Never load `gsi/client` there (the product origin is not registered with
Google), never load `gsi/intermediatesupport` anywhere (it is for a separate
post-login page and crashes an active prompt), and never create the iframe
manually — GSI holds the prompt until Google's parent library completes its
handshake, so a hand-made iframe means the prompt never appears.

On an SPA (or any DOM rendered after load) use the JS API — the
`g_id_intermediate_iframe` div auto-scan only works on statically served HTML:

```js
// After fetching the intent from your backend:
window.addEventListener("message", (event) => {
  if (event.origin !== intent.frame_origin) return;   // https://os.hz.egbe.dev
  const m = event.data || {};
  if (m.type === "egbe:onetap:credential" && typeof m.credential === "string") {
    // POST {credential, nonce} to your backend exchange route (step 3),
    // then navigate on success. Do NOT verify or decode the JWT in the browser.
  }
  if (m.type === "egbe:onetap:closed") {
    console.debug("onetap not shown:", m.reason);      // keep for debugging
  }
});
const s = document.createElement("script");
s.src = "https://accounts.google.com/gsi/intermediate";
s.async = true;
s.onload = () => {
  google.accounts.id.initializeIntermediate({
    src: intent.frame_url,
    done: () => {},  // default `done` reloads the page mid-exchange — override it
  });
};
document.body.appendChild(s);
```

Static pages may instead place, before the script tag:

```html
<div id="g_id_intermediate_iframe" data-src="<frame_url>"></div>
<script src="https://accounts.google.com/gsi/intermediate" async defer></script>
```

Mount this only for logged-out visitors (landing, /login, /signup). Google's
library creates the iframe itself, sizes it as the prompt shows, and sets the
FedCM `allow="identity-credentials-get"` permission — none of that is your
code's job.

### 3. Backend: exchange the credential

The credential message carries a Google-signed JWT. Post it with the nonce to
the product backend, which exchanges it server-side:

```http
POST /auth/google/onetap/exchange HTTP/1.1
Host: <configured Egbe host>
Authorization: Bearer <server-side product key>
Content-Type: application/json

{"app_slug":"<deployed-slug>","nonce":"<nonce>","credential":"<credential>"}
```

The result is the same verified identity payload as `/auth/google/exchange` —
apply the identical linking transaction from the redirect flow, create the
ordinary session cookie, and return the post-login path for the page to
navigate to. A 404 means the nonce is invalid, expired, or already used
(exchanging burns it even when the credential is rejected — the page should
just fetch a fresh intent). Fire the same signup conversion events as the
redirect flow, with its own method label (e.g. `google_onetap`).

### Frame → page message protocol

The frame posts to the embedding page (always check
`event.origin === "https://os.hz.egbe.dev"` first):

| message | payload | meaning |
|---|---|---|
| `{type:"egbe:onetap:credential"}` | `credential` (JWT string) | user picked an account — exchange it now |
| `{type:"egbe:onetap:closed"}` | `reason` (string) | prompt not shown / dismissed |

### Why the prompt may not appear (all of these are normal)

- No Google session in the browser profile → nothing to offer.
- Cooldown: each dismissal (the ✕) suppresses One Tap on that site for
  progressively longer (minutes → hours). Test in an incognito window signed
  in to Google.
- `reason` in the `closed` message is often `unknown_reason` under FedCM —
  Chrome hides the real cause for privacy. That alone is not an error.
- The user is already logged in to the product — you should not have mounted
  the embed at all.
- GSI console warnings about "FedCM becoming mandatory" and "prompt UI status
  methods" on the page are advisory noise from the intermediate libraries —
  ignore them.

A working end-to-end reference lives in the `agent-canvas` product repo
(Forgejo `os-e64a1fbe2153/agent-canvas`): backend routes
`/auth/google/onetap/intent` + `/auth/google/onetap/session` in
`src/index.ts`, page component `GoogleOneTap` in `web/src/App.tsx`.

### Product button


Use Google's pre-approved button assets or follow the official branding
guidelines:

- Guidelines: https://developers.google.com/identity/branding-guidelines
- Assets: https://developers.google.com/static/identity/images/signin-assets.zip

## Product experience and verification

- Place Google on the selected account-entry surfaces with the agreed hierarchy.
  It may be the only method; this integration does not require email login.
- The visible Google control calls the product's same-origin start route, never
  Egbe OS with a browser-visible key.
- Preserve a validated relative continuation through the round trip.
- Show safe retry/cancel states without exposing provider details.
- Verify live Google signup, repeat login to the same account, session refresh,
  protected access, logout, and verified-email linking to an existing local
  account, including a controlled imported account in a Google-only product.
  Preserve its credentials and ownership without adding another login method.
  For a bounded repair, verify the affected behavior and shared dependencies.
  Another working login does not complete an agreed Google flow that is broken.
