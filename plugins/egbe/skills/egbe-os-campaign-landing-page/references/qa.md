# Campaign page QA

Check the owned implementation on the appropriate local or serving revision.
Use `egbe-os-product-build` → `references/interface-quality.md` for rendering,
accessibility and interaction proof. Record concise evidence and remaining gaps,
not a report for every section or word-count target.

## Routing and collection

- Exercise every planned variant and the default URL. Main/alias redirects preserve
  path, query and fragment without loops; local preview is not redirected to production.
- Test distinct CTA destinations, keyboard/touch actions, copied links and actual
  redirects. Verify preserved attribution without leaking credentials, QA markers
  or personal data to another host.
- Verify the configured consent/masking and tracking behavior on the relevant
  granted/denied/unknown states. Intercept test analytics delivery where supported
  so QA does not contaminate production metrics; inspect the intended payload.
- Test write validation, foreign origins, body limits, abuse controls and any
  honeypot. Check the actual browser transport, not only an artificial HTTP request.
- Confirm link-scanner HEAD requests and ordinary navigation work without causing
  a lead, booking, notification or other state-changing action.

## Relevant real paths

For a form, use a marked authorized test: verify stored fields/attribution,
success and failure behavior, and the separate notification result. An external
test message needs recipient authorization.

For a calendar, exercise opening, widget failure/fallback and context association
without reserving a real slot. Test callbacks in the provider's supported test
facility or with isolated fixtures; distinguish that from a live verified booking.

For a product handoff, verify destination parameters and continuation through
accessible redirects. Test accounts, paid actions or sending are not implied by
permission to inspect the page. State any downstream boundary not exercised.

Inspect accepted content, actual price and actions against the implemented page.
A proposed ad change goes back to the campaign owner; page QA does not edit provider
objects or grant launch permission. Clean up only identified authorized test records
and report the precise remaining operational gap.
