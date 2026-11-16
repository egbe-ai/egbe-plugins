# Next.js Auth Integration

Apply the egbe-os-product-auth contracts using the app's installed Next.js version and
existing data layer.

- Keep marketing and signed-in layouts separate when the app already uses route
  groups, but render auth state through shared navigation components.
- Resolve session state on the server for layouts and protected pages. Do not
  trust a client-only context as authorization.
- Put credential/session operations in server-only modules. Keep database and
  cookie APIs out of client components.
- Use route handlers or server actions consistently with the existing app. For a
  new product without an established auth implementation, prefer stable route
  handlers for signup, login, and logout. Existing Server Action forms remain
  valid when their rendered POST form is directly usable.
- For passwordless email, consume the one-time credential in a server Route
  Handler or equivalent response boundary that can atomically update durable
  state, set the session cookie, and redirect to a clean URL. Do not consume it
  in a rendered page component or through a read followed by an unconditional
  update.
- When a Client Component submits auth with `fetch`, expose the same production
  route handler through the live auth interface `data-auth-action` contract. Do
  not create a verifier-only route or duplicate the credential/session logic.
- Use middleware/proxy only as an early redirect layer. The protected server
  route must still verify the session.
- Run idempotent migrations during a controlled build/deploy step, not through a
  public `/api/init` route.
- Mark session-dependent rendering dynamic according to the installed Next.js
  version so signed-in navigation is not cached as another user's state.

Prefer a maintained auth library already configured in the repository when it
supports the local account/session authority and selected account-entry paths.
If the product has no library, keep the custom implementation small and follow
the applicable method workflows and shared session-and-credentials contract.
