# Leads, bookings and product handoffs

Implement the accepted collection and destination. Reuse the product's durable
backend; table names and form layout are not a cross-product schema.

## Forms and notifications

Store the accepted fields, form kind, relevant variant/attribution and a test marker.
Preserve entered values across recoverable validation failures and protect write
endpoints as described in [OS wiring](os-wiring.md). Display success only after the
server confirms durable storage. Mark notification delivery independently, using a
stable lead identity and safe retry so an attempt is not confused with delivered mail.

Read the current Mail contract for notification fields, delivery results and any
reply address. Use the approved recipient, not a guessed one. Include the submitted
information needed to handle the request and its permitted attribution; do not leak
it into analytics URLs. An authorized test notification is visibly marked as test.
Report undelivered requests and their recovery state. Do not claim a working contact
path solely because the row exists.

Implement the agreed fields, requiredness and form placement, with accessible errors.
Do not add a mandatory pre-calendar form, promise exactly one email, suppress required
consent or turn an optional request into an account signup by default.

## Calendar integrations

Use the chosen provider's actual contract. For an embedded widget, load it when
needed and retain a normal booking URL as a fallback. Preserve agreed context and
prefill only approved data through the provider's supported mechanism.

Correlate the launch and booking signal with a stable, validated reference. Validate
postMessage origin and event shape; store provider IDs/URLs only after checking their
expected host and format. For Calendly, `calendly.event_scheduled` from
`https://calendly.com` is a browser signal, not independently verified completion.
Use the provider's verified callback/read where available to confirm the booking.

Handle click and callback arriving out of order with idempotent storage. A browser
report is acknowledged only when stored; failures remain retryable. Do not emit a
server-confirmed conversion before that evidence exists. Opening a calendar is not
a booking, and QA must not reserve a real slot as a probe.

## Handoff to a product

Follow [routing](routing.md) for approved signup/checkout destinations and attribution.
Inspect the actual receiving flow where access permits, including redirects and
context retention. Do not assume a product uses Supabase or a particular analytics
SDK. Verify that the receiving application records the needed association; if it is
outside the owned work, return the precise missing behavior to its owner.

Clicks, registrations, first useful results and payments are separate observations.
Use real downstream events or an agreed export for the latter; lack of access is
an explicit gap, not zero conversions. Preserve the accepted customer journey rather
than inventing a signup or trial to make tracking convenient.

## Test data and measurement

Use canonical events from Analytics with the event's actual semantic meaning.
A lead request is not automatically an account registration and a client-side
booking message is not proof of paid value. Do not copy old event names to fit a
report. Keep test traffic out of customer/revenue metrics through the supported
test/collection controls, and verify event delivery with bounded test captures.

Mark permitted test records at creation. Remove only exact known test records
within the task's cleanup scope, or retain them excluded from reports; never delete
unmarked rows by guessing an address pattern. Keep technical evidence in the task's
existing records, without customer data in public reports.
