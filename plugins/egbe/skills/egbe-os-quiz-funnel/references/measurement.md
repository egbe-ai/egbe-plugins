# Measurement

The Egbe OS `egbe-os-analytics` skill owns event names, payload fields, attribution,
and delivery. Read the live contract first:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/analytics/events" -s
```

Reuse the product's registered analytics site and the tracker already in the
application shell. Do not register another site and do not invent event names.

## What the engine reports

The engine uses two canonical events of that contract and fills them with
values of the quiz. When the live contract no longer defines one of them with
these fields, stop and report the difference; do not rename events yourself.

| Moment | Event | Values of the quiz |
|---|---|---|
| An option of a single-choice question is chosen | `button_click` | `surface: "quiz"`, `button_id: "<screen>.<option>"`, `button_role: "quiz_answer"`, `position` |
| A multi-select question is confirmed | `button_click` | `button_id: "<screen>.continue"`, `button_role: "quiz_answer"`, `state: "<option>+<option>"`, `position` |
| An interstitial screen is passed | `button_click` | `button_id: "<screen>.continue"`, `button_role: "quiz_continue"`, `position` |
| The call to action of a result is pressed | `cta_click` | `surface: "quiz_result"`, `cta_id: "<result>"`, `cta_role`, `label`, `destination` |

- Every event carries `product_slug` and `path`, the route of the quiz.
- `position` is the number of the screen that was passed, starting at 1.
- `cta_role` is `call_primary`, `signup_primary`, or `checkout_primary` for
  the goal and `alternative` for a result with its own destination.
- For a sensitive question the chosen option is left out: a single-choice
  question reports `"<screen>.answered"`, a multi-select question reports no
  `state`.

The opening of the quiz is the native page view of the route. Going back,
switching an option of a multi-select question, and viewing a screen are not
events.

A request form follows the signup and lead capture workflow of the `egbe-os-analytics`
skill, with `surface: "quiz_lead_form"`. Signup, checkout, and purchase keep
the events of the product's own flows.

Emit the activation event of the contract only when the product requirements
define the quiz result as the product's first useful output; then follow the
activation workflow of the `egbe-os-analytics` skill.

## Delivery

The engine describes the events and passes them to `onEvent`, the function
given to `createQuiz`; it does not send them. The page delivers each
descriptor with the browser tracker and adds
`visitor_id`, `visit_id`, and the first-touch campaign fields from
`window.__egbeAttribution.read()`.

- The tracker loads after the page. The first answer of a fast visitor must
  not be lost, and no answer may be counted twice: hand each event over
  exactly once. How an event waits for the tracker depends on what the
  product's pages send through.
  - Through `window.umami.track`, as the reference binding does: keep the
    events that occur before the tracker is ready in a queue of your own, and
    send each of them when it is.
  - Through `window.__egbeAttribution.track(name, data)`, the runtime of the
    shared tracking snippet: hand the event over and leave the waiting to the
    runtime. While the tracker is still loading, that call returns `false`,
    but it has kept the event and sends it when the tracker is ready, with
    the campaign fields that it adds itself. A binding that repeats an event
    after `false` counts one answer twice. Keep a queue of your own only
    while neither `window.__egbeAttribution` nor `window.umami` exists, and
    hand its events over as soon as one of them does.
- A call to action that is a link leaves the page. Render its descriptor as
  attributes on the link, as the landing click workflow of the `egbe-os-analytics`
  skill describes, so the tracker delivers the event before the navigation.
  Do not also send it from code. A result's own destination and the
  destinations `booking_url`, `signup`, and `checkout` are links. The button
  that opens a request form is not, and its click is handed over from code.
- The tracker sends the click of a link as the attributes spell it and adds
  nothing to it. Its keys arrive in kebab-case: `cta-id`, `cta-role`,
  `product-slug`, `visitor-id`. An event handed over from code arrives in
  snake_case: `cta_id`. The first-touch campaign fields reach the click of a
  link only when the page wrote them as attributes, as the reference binding
  does; the runtime adds them to the events it is handed and to nothing else.
  Verified live on 2026-09-29: the click of a link arrived with kebab-case
  keys and, on a page that left the campaign to the runtime, without the
  campaign fields that its events from code carried.
- The completion of a request is confirmed by the product's endpoint after the
  request is stored, and delivered by the browser from the descriptor in the
  response.

Never put contact details, names, or free text into an event.

## Reading the quiz

Count sessions, not events. An event at position N means that screen N was
passed. Give these readings to the caller with the report: whoever reads the
statistics has not read this file.

- **Reach of screen 1**: the page views of the route.
- **Completion of screen N**: sessions with an event at position N.
- **Reach of screen N**, for N of 2 or more: the completion of screen N − 1.
- **Loss at screen N**: its reach minus its completion.
- **Answers**: sessions by `button_id` of one screen.
- **Result reached**: the completion of the last screen, and the sessions
  whose answers decided a `not_fit` result earlier. Such a session ends its
  events at the position of the deciding answer, so the sessions that reach
  a result early are counted by that answer, not as a loss at the next
  screen. Count them by the answers that decide each `not_fit` result, as
  `QUIZ.md` lists them.
- **Call to action**: sessions with `cta_click` by `cta_id`, against the
  sessions that reached the result. Read both spellings of every key of
  `cta_click`: the click of a link carries `cta-id` and `cta-role`, the click
  of a button carries `cta_id` and `cta_role`. A report that reads one
  spelling counts only a part of the clicks. Where the click of a link
  carries no campaign field, take the campaign from the other events of the
  same visit.
- **Conversion**: the records of the destination. Bookings come from the
  scheduling tool, requests from the rows the product stored, accounts and
  payments from the product's own records.

## Advertising pixels

The conversion event of an advertising channel is set up by the Egbe OS skill
of that channel and fires where the conversion happens, not on quiz screens.
The quiz adds no pixel code of its own.
