# Session And Credential Security

## Credentials

- Normalize email consistently and enforce uniqueness in the database.
- For an email/password profile, hash passwords with a maintained implementation
  such as Argon2id, scrypt, or bcrypt with an appropriate work factor and store
  only the hash.
- For a provider or passwordless profile, store only the provider identity or
  hashed one-time credential state that profile requires. Do not invent a local
  password or placeholder password hash.
- Never log passwords, provider secrets, one-time credentials, session tokens,
  or complete auth request bodies.
- Keep credential and account-entry failures account-neutral. For passwords,
  return the same invalid-credentials response for unknown email and wrong
  password.
- Apply bounded rate limiting to signup, login, and recovery mutations.

## Sessions

- Generate a cryptographically random opaque session id.
- Store revocable server-side session state; prefer storing a hash of the token.
- For a new custom Node/Postgres profile, hash the raw token as SHA-256
  hexadecimal in `sessions.token_hash` and default to the `egbe_session`
  cookie. Keep the request-time resolver and the bundled private validation
  helper on one contract. If an existing working resolver already uses this
  authoritative state and hash contract under another cookie name, preserve
  it and pass that real name through the helper's `--cookie-name` option; do
  not rename a working session solely for validation setup.
- Rotate/create a new session after signup and login.
- Set the browser cookie with `HttpOnly`, `Secure` on HTTPS,
  `SameSite=Lax` or stricter, `Path=/`, and an explicit expiry.
- Validate expiry and revocation on every protected request.
- On logout, revoke the server record before clearing the cookie.
- Do not use localStorage, readable client tokens, a user id, or an email address
  as proof of authentication.

## Request And Redirect Safety

- Protect state-changing requests with the framework's same-origin/CSRF
  mechanism.
- Check that response privacy headers and request protection work together for
  the transport actually used. A native form POST can send `Origin: null` under
  `Referrer-Policy: no-referrer`, even to its own origin; a direct HTTP probe
  supplying the expected `Origin` does not exercise that browser behavior.
  Choose a compatible policy for ordinary forms or use the framework's complete
  supported CSRF mechanism. Keep the stricter privacy policy on one-time
  credential exchange responses. Do not fix a rejected form by disabling CSRF
  checks or trusting `null` as a same-origin identity. See the
  [Fetch origin-header rules](https://fetch.spec.whatwg.org/#append-a-request-origin-header).
- Accept return destinations only when they are safe same-origin relative paths.
- Do not place passwords, session ids, or user identity in URLs. A short-lived
  one-time email credential may appear only in its intended HTTPS exchange link;
  redact it from logs and analytics and remove it from the browser URL after
  exchange.
- Keep authentication and authorization checks on the server. Client state may
  render UX, but it cannot grant access.
- Do not add demo users, in-memory fallback sessions, public route bypasses, or
  fail-open behavior when the database is unavailable.

## Private Validation Identity

After real account entry has been proved, dependent Product and Billing work
may create or reuse one isolated validation identity directly through the
server-side session authority. The raw token must exist only in a private
mode-`0600` state file, while the database stores only its hash. Load that
cookie into an isolated browser session; never add a public test-login route,
fixed credential, committed secret, or production bypass.

The validation identity is authenticated setup for exercising protected
behavior. Its existence is not evidence for signup, login, credential or email
exchange, logout, or recovery. Those flows still require their real Auth-owned
proof.
