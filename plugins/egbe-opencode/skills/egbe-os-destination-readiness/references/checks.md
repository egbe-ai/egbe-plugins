# Inspect the promise, not just the URL

Use these questions on the mapped visitor paths. Record what you inspected,
including satisfactory evidence and unavailable portions, so an empty findings
list is not confused with a complete check. Deepen an investigation when it can
change the conclusion; avoid unrelated routes and speculative improvements.

## Start with the project source

When application source is available in the product repository, inspect it before
browsing the mapped paths. Trace the relevant route definitions, redirects, CTA
destinations, legal-page content and link placement, forms (including autosave
and submit handlers), and pricing/booking configuration. Follow referenced
definitions and conditions far enough to establish the active code path; a
search match alone may be unused code. Limit reading to the visitor paths under
review, not a general review of the application.

Use this map to locate defects, explain their cause and identify the files to
change, then confirm the consequential deployed entry, CTA and document paths.
Code inspection can establish an implementation defect without sending a real
request; runtime-dependent effects remain unverified until supported by evidence.
Reading a handler does not require executing it or submitting its form. A local
preview, if available, is evidence about that local version, not the deployment.

When only product documents or a URL are available, continue with public-site
inspection and state that application source was unavailable. Planning documents
describe intent; they do not establish how the application is implemented.

## Reach the intended next step

If the inspection also informs performance analysis, fix that analysis's cutoff
before live checks. Use a fresh browser context tagged `utm_source=smoke`, retain
the marker through navigation and verify its recording where available; exclude
known inspection sessions rather than guessing from country or device.

Open the exact supplied/deployed entry URL, including meaningful query parameters,
then follow its actual primary navigation. Record initial/final URL and important
redirects. Check that the page describes the intended offer, renders usable
content, and exposes the promised action. Note errors, persistent loading,
intrusive overlays, broken controls or redirects to an unrelated product.

Inspect desktop/mobile or language variants when the intended journey uses them
or a material difference is visible. State actual device, locale and access
context. A desktop fetch is not a mobile interaction test. An authenticated
screen does not prove that a first-time visitor can reach it.

For failures, distinguish a reproducible site problem from a transient fetch,
anti-bot or inspection-tool limitation. Retry once using another appropriate
read method when it can settle that distinction. Do not turn a tool's 403 into
a claim that every visitor is blocked. HTTP 200 can still be an error shell,
placeholder or wrong page. A safe page view is not evidence that submission,
booking confirmation or payment succeeds.

## Find and read the relevant documents

Inspect links visible in the footer, navigation, collection form, booking or
purchase step. Open the linked documents and read their substance. If none are
discoverable, a bounded check of plausible paths or supplied repository routes
can help locate them; distinguish **not found at guessed paths**, **exists but
not linked where needed**, and **linked but missing/irrelevant**.

Ask whether the visitor can learn, before committing:

- Who operates the product and handles the information being requested?
- What is collected, for what purpose, and with which relevant providers/recipients?
- What are they agreeing to or buying, including applicable renewal, cancellation,
  refund or service terms?

Check that the text actually covers this product and this action, not an empty
template or an unexplained different service. A parent's policy can cover several
brands when the relationship and coverage are clear. Privacy and terms may be
under nonstandard URLs or in a combined document; filenames are not requirements.
A payment provider's own policy alone does not explain the product's handling
of customer data or its offer.

When personal data is visibly collected but its handling is not explained at
the inspected collection point or reachable documents, report that observed
disclosure gap. When a purchase hides material commercial terms, identify those
terms. Cite the applicable network rule if supplied; otherwise state the visitor
trust/decision problem rather than inventing a universal legal violation.

## Make the identity chain understandable

Compare the brand on the entry page with the CTA destination's title/logo,
booking host, support address, legal entity and merchant identity where visible.
Look for an explanation a visitor can actually find before providing information
or money. Repository ownership knowledge alone does not provide that explanation.

A Stripe/Calendly host or a disclosed parent company is not itself a mismatch.
An unexplained second brand can create a real trust gap without proving fraud.
If a differing brand/domain is material, inspect its public site and relevant
relationship statements; a live separate product is evidence of ambiguity, not
proof that the businesses are unrelated. State what relationship is established,
what is not, and where an explanation would solve the problem.

## Carry the offer through the handoff

Compare the actual words/values at both ends, retaining a compact before/after
record instead of “CTA inconsistent.” Check what applies:

- Booking: promised purpose, host/team, title, duration, price and visible
  availability. “20-minute product demo” → “30-minute call for another brand”
  needs more than a working calendar URL. No slots in one visible week does not
  prove that bookings are permanently unavailable; state the inspected range.
- Signup: promised access/result, required data, payment/card requirements and
  whether the action is signup, a waitlist or a sales request.
- Purchase: product/plan, amount, currency, billing period, trial/renewal terms
  and material limitations visible before commitment. If checkout can only be
  opened by creating a session, inspect existing authorized evidence and leave
  the live handoff unverified rather than creating one.

Distinguish a disclosed change of step (for example, introductory call before a
quote) from an unexpected substitution. Identify which promise or destination
should change based on product intent; if that intent is unresolved, offer the
recommended option and one focused question. Do not rewrite the product strategy.

## Apply data and network requirements with their actual scope

Use visible collection fields, disclosures and task-authorized observations to
identify material data-handling concerns. Ground any consent or special-category
requirement in the relevant network rule or verified applicable requirement and
explain why it applies here. Absence of a banner alone is not evidence of unlawful
tracking. This inspection does not audit event delivery or implement consent UX.

When a caller supplies network-specific references, apply them only to the
matching entry paths/formats. Read the relevant official section for a policy
finding, record its URL and retrieval date, and distinguish a requirement from
best practice. If current wording cannot be obtained, disclose the source limit;
do not upgrade a suspected policy issue into a confirmed rejection. An observed
visitor problem remains reportable on its own evidence.
