# OS wiring

Read the current Deploy, Domains, Analytics and Mail contracts for the operations
used. Do not copy provider credentials or assume capability gaps from an old page.

## Hosting and main address

Reuse the product application and agreed host. Obtain actual serving URLs and
domain/TLS state from OS; do not synthesize a canonical hostname or assume every
project has a custom-domain allowance. Register/reuse analytics for the intended
host and preserve existing project bindings.

When aliases redirect to the main host, preserve path, query and fragment.
Redirect only known app hosts, not local previews or arbitrary supplied hosts.
Normalize the host comparison and test the main URL for redirect loops. Place
redirect handling before tracking to avoid counting an alias and its destination.
Use absolute canonical/OG metadata for the real main address.

Provision attached storage through Deploy/DB if the accepted capture needs it,
or use the app's existing durable backend. Apply migrations through its supported
deployment mechanism, not a public initialization endpoint. Do not deploy an empty
app simply to follow an ordering example.

## Credentials and data

Product servers use OS_URL and the platform-injected OS_API_KEY per Deploy;
do not mint a mail-scoped agent key and copy it into a product. No server credential
may enter HTML, client code, logs or committed configuration. Use current Mail
fields and supported delivery channels; report an observed capability failure,
not a presumed lack of reply-to, CRM support or conversion upload.

Use the recorded, approved lead recipient and delivery destination. If ambiguous,
ask; do not scrape an address and silently route customer data there. Before an
external test message, confirm the allowed recipient and test scope.

Apply the accepted privacy/consent policy to analytics, replay, attribution and
stored data. Do not infer legal consent from a UTM slug or assume all first-party
data can be collected regardless of choice. Configure masking and snippet behavior
from the current Analytics contract; missing policy is a decision for the caller,
not a reason to bypass controls.

## Protect write endpoints

- Enforce accepted content types, body/field size limits, an allowlist of fields
  and server-side validation. For small lead payloads, an 8–10 KB cap is a useful
  starting point; adjust deliberately for the actual data.
- Apply origin/CSRF protection appropriate to the real transport and allowed app
  hosts; a browser-supplied identity or destination is not authority.
- Rate-limit per endpoint using the supported deployment state, not process-only
  counters when multiple instances serve it. Avoid storing raw IPs for analytics;
  use the minimum approved abuse-protection data.
- If a honeypot is used, its success-shaped bot response must not create a lead
  or trigger mail. Keep bot/test traffic distinguishable from customer outcomes.
- Do not acknowledge a lead as saved before durable storage succeeds. A failed
  notification is separately observable/retryable, not permission to lose the lead.

Serve/cache assets appropriately with licensed fonts and content-versioned names.
Keep project documents, credentials and private captures out of public builds.
