# Live Auth Interface Contract

These attributes are stable test interfaces. They do not replace semantic HTML
or visible labels, and they must not appear in user-facing copy.

## Routes

New products expose:

- `/signup` for account creation;
- `/login` for durable login;
- one protected continuation selected by the shared navigation.

Present the selected account-entry methods. When Google exists, its control
carries `data-auth-google` and calls a same-origin product start route; it never
contains `OS_API_KEY` or links directly to a provider token endpoint. These
markers describe real controls, not a requirement to add a provider or form.

Existing products may retain their working routes. A bounded repair preserves
them rather than adding entry routes for verification. Any exposed canonical
routes or aliases must resolve to the working flow, not a disconnected duplicate.

The authorized protected continuation renders `data-auth-protected` on its
stable page root. A signed-out request must redirect to the product's working
login entry or return an explicit 401/403 response; merely rendering signed-out
navigation on otherwise public content is not route protection.

For the primary protected browser UI, redirect signed-out users to that login
entry and preserve the same-origin continuation in that redirect. Explicit
401/403 responses are suitable for protected API endpoints, not the main UI
continuation.

## Email forms, when selected

Signup:

- email input: `data-signup-email`;
- password input when used: `data-signup-password`;
- submit control: `data-signup-submit`;
- visible error container: `data-auth-error`.

An email path has only the fields it requires: email and password
for email/password, or email alone for passwordless email. Do not ask
for name, full name, company, username, password confirmation, or profile data
during signup. Hidden CSRF, attribution, and safe return-path inputs are
allowed. Use the account email as the initial signed-in identity until a later
profile flow collects additional data.

Login:

- email input: `data-login-email`;
- password input when used: `data-login-password`;
- submit control: `data-login-submit`;
- visible error container: `data-auth-error`.

Use real `label` associations, `type`, `name`, and `autocomplete` values in
addition to these attributes.

The verification interface does not require native HTML form submission. A
native form may expose its real same-origin POST `action`. A JavaScript-enhanced
form instead exposes the real production endpoint used by its submit handler as
`data-auth-action` on the form or marked submit control. When that endpoint
expects JSON rather than form data, add `data-auth-encoding="json"`; form encoding
is the default. Inputs still need stable `name` values so the same payload can be
verified without browser automation.

`data-auth-action` must point to the same server implementation used by the
product UI. Do not add a test-only endpoint, skip credential validation, or
manufacture authenticated responses for verification. The action must remain on
the product origin and accept POST requests. A JSON action should return a
same-origin `next` path when navigation is handled by the client; native redirects
already provide that destination.

For passwordless email, the signup/login action requests the real message; it
does not claim an authenticated session. Authentication completes only when the
one-time live link establishes server-verified state. The request response and
visible pending state must distinguish an accepted request from an immediate
mail-provider failure without exposing account existence.

## Shared Navigation

Render one state marker in the shared navigation:

```html
<nav data-auth-state="signed-out">...</nav>
<nav data-auth-state="signed-in">...</nav>
```

The signed-in state contains:

- `data-auth-user-menu` on the menu trigger or stable wrapper;
- `data-auth-identity` on the displayed non-sensitive identity;
- `data-auth-continue` on a same-origin link to the protected continuation;
- `data-auth-signout` on the logout control.

Logout may be a native POST form or a JavaScript control. A JavaScript logout
control exposes its real same-origin endpoint with `data-auth-action` and, when
needed, `data-auth-encoding="json"`. It does not need to be wrapped in a form.

The signed-out state links to the same working login entry and retains the
product's normal primary CTA.

## Behavioral Meaning

The signed-in marker may render only after the server has verified the session.
It must survive reload. Logout must switch the navigation back to signed-out and
make the continuation inaccessible. Do not set signed-in UI state from an email,
query parameter, localStorage value, or unverified cookie payload.
