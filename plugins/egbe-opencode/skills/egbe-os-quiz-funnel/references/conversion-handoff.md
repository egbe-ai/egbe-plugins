# Conversion Handoff

The result screen ends the quiz and starts the conversion. The quiz hands the
visitor to a destination; it never creates an account, a checkout session, or
a booking itself.

## Every goal

- The runtime renders the specified result and its call to action; implement
  the accepted wording and destination without inventing a new product promise.
- The engine builds the destination: `quiz.cta(attribution)` returns the label,
  the destination, and the descriptor of the click. Pass it
  `window.__egbeAttribution.read()` from the shared tracking snippet.
- Never put answers, names, emails, phone numbers, or other personal data into
  an address.
- The answers stay in the browser's session storage under
  `quiz-funnel:<quiz-slug>`, on the origin of the product. They survive
  navigation in the same tab and nothing else. Visitors from ads often arrive
  in the browser of another application, where a sign-in may open elsewhere
  and the storage is then empty. Treat a restored result as a convenience,
  never as a promise.
- Answers to sensitive questions stay in the visitor's browser. Do not store
  or send them.

## `call` with `booking_url`

The call to action is a link to the scheduling page. The engine completes the
link in this order and never replaces a parameter that is already set:

1. the parameters the address already carries;
2. `result_param`, when set, with the value `<quiz-slug>.<result-id>`;
3. the first-touch `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`,
   and `utm_term` of the visitor;
4. `fallback_params`, only for a visitor who arrived without any campaign
   parameter. A real campaign is never completed with invented values.

Set `result_param` to a parameter the scheduling tool records, so the person
who takes the call sees the visitor's result. When that parameter is one of
the campaign parameters, such as `utm_content`, the result takes its place and
the value of the ad is not passed.

The booking happens in the scheduling tool, so the quiz measures the click and
not the booking. Count bookings from the records of the scheduling tool by
their campaign parameters, and say so in the report.

## `call` with `lead_form`

Use this destination when the accepted experience calls for contact collection.
The bundled binding opens it from the result CTA; it does not choose the fields
or insert a contact gate before a calendar by default. Render the accepted
labels, consent text and success/error behavior. On a failed save, retain the
entered values and allow correction/retry unless a different recovery is agreed.
Never show successful capture merely because navigation continued.

The form posts to an endpoint of the product on the same origin. Add that
endpoint as one route of the product's server, following its existing
conventions, when the product has a database; when it has none, stop and
report. The endpoint:

| | |
|---|---|
| Accepts | `POST` with JSON: `quiz_slug`, `result_id`, `answers`, `attribution`, and `contact` with the fields of the form |
| Checks | the quiz and the result exist, the contact fields are well formed and of reasonable length; it rejects anything else with a client error and stores nothing |
| Stores | one durable row with the contact, the quiz, the result, the answers, the first-touch fields of `attribution`, and the time |
| Tells the founder | through the Egbe OS `mail` capability, so that someone answers |
| Returns | success and the analytics descriptor of a completed lead capture, as the Egbe OS `egbe-os-analytics` skill describes it; the browser delivers the event |

The privacy page of the product must say what the form collects and why.

### Request form, then the scheduling page

The destination stays `lead_form`. The rules above apply, except for what
`success` says and for what a failure does. What `call` with `booking_url`
says about the result screen applies as well.

The specification has no field for the scheduling address. Keep the
address, the name of the parameter that carries the result, and the fallback
values together in one place of the application's source, next to the route.
Confirm the address as [inputs.md](inputs.md) describes for `booking_url`.
Keep the accepted continuation and failure behavior in the existing integration
plan or code; no research entry is required for it.

- `submit_label` names the next step, choosing a time. `success` says that
  the calendar opens. It promises an email with the link only when the
  product sends one.
- When the requests are passed on to a client, `consent_note` names the
  client: the visitor agrees to that before sending the form.
- After the form is sent, the page continues to the scheduling address in
  the same tab. The page completes the address in the order given for
  `booking_url`: what the address carries stays, then the result as
  `<quiz-slug>.<result-id>` under its parameter, then the campaign parameters
  of the first touch, and the fallback values only for a visitor without any
  campaign parameter. `destination.payload` of `quiz.cta(attribution)` holds
  the slug, the id of the result, and the first-touch fields of the visit.
- The contact does not travel in the address, as for every goal: an address
  stays in the history of the browser and can be read by the scripts of the
  page it opens. The scheduling page asks for the contact itself.
- Continue after a confirmed save. If the accepted recovery allows calendar
  access without saving, implement that as a distinct state, report the save
  failure to error tracking and do not report a completed capture. Do not add
  a silent timer-based bypass by default. A malformed contact remains editable.
- The completed request is reported only when the endpoint confirmed it, and
  before the page leaves: wait for the tracker for up to a second, then
  continue.
- A visitor who comes back from the calendar with the browser's back finds
  the result and its call to action, not the form that was sent.

Count requests from the rows the product stored and bookings from the records
of the scheduling tool, and match the two by email. A visitor may book with
another email than the one of the request, and a booking can exist without a
stored request. Both are still attributed by the campaign parameters and the
result in the records of the scheduling tool.

## `signup`

The call to action leads to the product's signup route.

Word the label and the result for what really happens. "Save my result" is
true only when the product stores the result with the account. When it does
not, name what the account gives instead.

When the accepted continuation uses the result after signup in the same tab,
restore it with `createQuiz(spec, { storage }).result()`. Handle a missing result
without breaking the product's normal first page. Storing the
result with the account is product development; hand it over with the fields
`quiz_slug`, `result_id`, and `answers`.

How accounts are created, verified, and signed in belongs to the Egbe OS
`egbe-os-product-auth` skill. Do not change it.

## `payment`

The call to action leads to the product's checkout route with the plan:
`<path>?<plan_param>=<plan_key>`. A signed-out visitor passes through signup
and returns to the same plan; that continuation belongs to the product's
signup and checkout. When checkout needs an account, say so in the note under
the button, so the account step is expected.

Every result that leads to the checkout shows `goal.destination.price`, the
price and period exactly as the product's plan catalog states them, in a text
that every visitor of that result reads, and says what the payment unlocks.
Show no former price, discount, or deadline that is not real.

The product may read the answers from session storage after the payment, as
after signup. Do not write that the product is set up from the answers unless
it is.

Checkout sessions, payment confirmation, and access belong to the Egbe OS
`egbe-os-payments` skill. A return address is navigation, not proof of payment.

## `not_fit` destinations

The runtime's `not_fit` result uses its own link or no CTA, not the primary goal.
Configure the accepted alternative; do not invent a destination or disqualification.
The engine may show it early only when remaining answers cannot change the result
and any headline/body answer tokens are already resolved.
