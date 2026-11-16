# Signup Lifecycle Tracking

Use this workflow when a product has signup, registration, account creation, or
lead-capture flow.

## Source Of Truth

Always read the live event contract first:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/analytics/events" -s
```

`canonical-events.v1.json` remains the source of truth for event names,
required payload fields, recommended attribution fields, and delivery policy.

## Events

Use the canonical signup lifecycle events from the contract:

- `signup_started`: emit from the browser when the visitor intentionally enters
  the signup flow.
- `signup_submitted`: emit from the browser after client-side validation passes
  and immediately before or at submit.
- `signup_completed`: confirm only after durable account, registration,
  subscriber, or accepted lead-capture persistence succeeds.
- `email_verified`: include only when verification or a magic-link return
  establishes verified email/account state; prefer delivery from that browser
  return after backend confirmation.

Do not invent product-specific signup event names.

## Browser Payload

Read first-touch attribution from the shared snippet:

```js
const attribution = window.__egbeAttribution?.read?.() || {};
```

Include the required payload from the event contract and pass attribution fields
through the signup request when the backend creates durable state.

```js
const signupAnalyticsPayload = {
  product_slug: "my-product",
  path: "/signup",
  surface: "signup_form",
  visitor_id: attribution.visitor_id,
  visit_id: attribution.visit_id,
  first_utm_source: attribution.first_utm_source,
  first_utm_medium: attribution.first_utm_medium,
  first_utm_campaign: attribution.first_utm_campaign,
};

window.umami?.track("signup_started", signupAnalyticsPayload);
window.umami?.track("signup_submitted", signupAnalyticsPayload);
```

## Completed Delivery

For `signup_completed`, separate the durable confirmation source from Umami
delivery:

1. Browser sends attribution with the signup request.
2. Backend creates the durable account, registration, subscriber, or accepted
   lead row and stores the first-touch fields on that same row.
3. Backend returns an analytics descriptor only after success.
4. Browser emits that descriptor with `window.umami.track(...)`.

Backend response shape:

```json
{
  "ok": true,
  "analytics": {
    "name": "signup_completed",
    "data": {
      "product_slug": "my-product",
      "path": "/signup",
      "surface": "signup_form",
      "account_id": "acct_123",
      "visitor_id": "visitor_123",
      "visit_id": "visit_123",
      "first_utm_source": "reddit"
    }
  }
}
```

Browser delivery:

```js
const result = await response.json();

if (result.analytics?.name && window.umami?.track) {
  window.umami.track(result.analytics.name, result.analytics.data || {});
}
```

If the signup flow redirects immediately, store the descriptor in a short-lived
`sessionStorage` pending queue, navigate, then flush it from the next browser
page with `window.umami.track(...)`.

Do not use direct backend Umami `/api/send` or `trackServerEvent` as the primary
delivery path for `signup_completed`; it can attach the event to a different
Umami session than the visitor's browser session.

## Practical Rules

- Keep auth behavior intact; add analytics around the existing flow.
- Put no raw emails, passwords, tokens, or payment details in Umami payloads.
- Use non-sensitive internal IDs such as `account_id` only when useful.
- Persist first-touch attribution with durable signup/user metadata when a
  backend exists, so later purchase and retention reporting can join back to
  acquisition channel.

## Durable Signup Attribution Contract

Store first-touch acquisition data on the same durable row that contains the
signup email. Use these canonical nullable text columns (snake_case in SQL;
camelCase ORM field names are also discovered by Site Gateway):

```sql
first_utm_source text,
first_utm_medium text,
first_utm_campaign text,
first_utm_content text,
first_utm_term text,
first_gclid text,
first_fbclid text,
first_msclkid text,
first_ttclid text
```

At minimum, persist `first_utm_source` and `first_utm_campaign` whenever they
are present. Copy the values from `window.__egbeAttribution.read().firstTouch`
inside the same transaction that creates the user/signup/waitlist/subscriber
row. Never overwrite non-empty first-touch fields during login, profile edits,
or later visits.

The Site Gateway product-metrics fallback discovers these fields automatically
on `users`, `signups`, `waitlist`, and `subscribers` tables. It prefers
`first_utm_*`, supports their camelCase ORM equivalents, and falls back to
legacy `utm_*` columns. Rows without a complete source/campaign pair remain in
the report's `other` bucket.

Do not send raw email addresses to Umami. The email-to-UTM join happens inside
the product database and is exposed only through the authenticated internal
Product Metrics endpoint.

## Bounded Verification

Use the smallest existing verification surface for each producer:

- for `signup_started` and `signup_submitted`, use an existing component/helper
  test or focused handler test that proves the canonical event and payload are
  reached from the intended interaction;
- for `signup_completed`, verify that the durable-success branch returns the
  descriptor and that validation, persistence failure, and other unsuccessful
  branches do not;
- verify browser delivery with the existing descriptor consumer or one focused
  test around it; test the pending redirect queue only when the product actually
  uses that queue.

Do not replay the complete signup or magic-link journey once per event, build a
new browser harness, send synthetic production events, or deploy solely to prove
logic already covered by focused source/component/handler evidence. Reuse an
already-available broader flow only when it proves several owned boundaries more
cheaply than focused checks.

### Dashboard acquisition and session reporting

Keep the signup record's first-touch identity and acquisition fields with the
confirmed account: `visitor_id`, `visit_id`, every `first_utm_*` field (including
term/content), `first_landing_path`, `first_referrer` and `first_seen_at`. First
touch includes direct landings; keep later touch fields separately. These stored
fields let the business Analytics page link pre-signup sessions and confirmed
payments without sending email or payment records to Umami. Use an opaque
`account_id` in canonical browser events; never use an email address as that ID.
If the app stores test/internal/bot records, persist explicit `is_test`,
`is_internal` or `is_bot` flags so reports can exclude them consistently.
