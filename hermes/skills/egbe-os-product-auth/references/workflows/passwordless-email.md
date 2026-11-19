# Passwordless Email Authentication

Use this profile only when authoritative product requirements select email
sign-in links. It extends the common account, session, protected-route,
navigation, and continuation workflow in `build-auth.md`; it does not add a
second auth system.

## Account Entry

- Use the account-entry routes from the
  [live auth interface](../contracts/live-auth-interface.md), with a single
  visible email field. Signup and login may share one server implementation
  while preserving the appropriate product copy and continuation.
- Normalize email consistently, apply bounded rate limiting by identity and
  request source, and return responses that do not reveal account existence.
- A mail-provider failure must not be presented as a sent message. Keep the
  response account-neutral while giving an honest retry state.
- Create the authenticated session only after the emailed credential succeeds,
  never when the link is merely requested or accepted by the mail provider.

## One-Time Credential

- Generate a cryptographically random, purpose-bound, short-lived credential;
  store only its hash with user, expiry, and consumption state.
- Put the raw credential only in the intended HTTPS email link. Never log it,
  persist it in browser storage, expose it to analytics, or retain it in the
  browser URL after exchange. Send a no-referrer policy on the exchange response.
- Consume it atomically: exactly one request may transition an unexpired,
  unused credential to used and receive the associated account. A separate
  read followed by an unconditional update is not single-use enforcement.
- Choose one resend policy and make it truthful. Either keep a bounded set of
  unexpired links usable or invalidate older links and clearly tell the user
  that only the newest message works. Never leave an apparently current email
  failing without an explanation and a new-link path.
- On successful exchange, create a fresh server-side session and redirect to a
  validated relative continuation. Do not revoke unrelated active sessions
  unless the product has an explicit security reason to do so.

## Mail Delivery

Read the live Egbe OS `egbe-os-mail` skill and use its supported send path. Distinguish:

1. the product accepted the request;
2. the mail service accepted the message;
3. the message reached the verification inbox;
4. the live link established the intended authenticated session.

Only the fourth result completes this profile. A successful request endpoint or
mail API response alone is insufficient. Preserve a clear retry path for
immediate provider failure, delayed or missing delivery, expired links, used
links, and an invalid link.

## Live Verification

Use one private verification inbox and the deployed HTTPS product:

1. request a link and confirm the truthful pending state;
2. receive the actual newest message and open its live link;
3. confirm the protected continuation, server-verified navigation, and session
   persistence after refresh;
4. confirm reuse and expiry fail safely with a new-link path;
5. request another link according to the stated resend policy and use it;
6. sign out, confirm protected-route denial, and sign in again through email.

Do not claim success if inbox access or live-link verification is unavailable.
