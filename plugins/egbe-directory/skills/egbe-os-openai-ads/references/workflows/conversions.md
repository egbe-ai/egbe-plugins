# Optional browser and server conversions

Read the conversion section of [API reference](../runtime/api-reference.md) for
the exact fields, supported event types, units, consent and delivery retries.
Ordinary traffic campaign build/launch does not require this workflow.

1. Map the requested canonical product event to an OpenAI event
   without confusing signup start with completed signup,
   Checkout redirect with payment, or trial start with a purchase.
2. Find the recorded owned source/pixel and goal. Reuse them when compatible;
   do not create a new source per follow-up. For new setup, journal creation,
   save IDs immediately and record account-access failures without borrowing
   another product's pixel or requesting provider keys.
3. Select campaign measurement explicitly. Creating source/event settings alone
   does not attach them to an existing campaign. For `clicks`/`impressions`, use
   the [measurement update](../runtime/api-reference.md#select-campaign-measurement-goals-without-changing-bidding)
   to set the intended complete list, then save readback of its IDs and unchanged
   bidding, budget and status. Do not switch to conversion bidding to add tracking.
   For oCPC, select one optimization goal at creation; it cannot be changed later.
4. Implement browser Pixel through official instructions when requested, with
   consent. Implement server delivery through OS at the product's authoritative
   outcome point, using its existing server storage for event identity, consent
   and retries. Persist `oppref`/`obref` only as allowed; never put them in campaign
   files. Preserve ordinary product events and existing app conventions.
5. Browser and server for the same event share a stable business event ID.
   Validate first with `validate_only:true`. Record configuration and redacted
   verification evidence in tracking; protected runtime storage retains actual
   event bodies, IDs and receipts. Delivery retry is bounded and caller-driven,
   not provided by an invisible OS worker. Inspect receipts on uncertain responses.
6. Separate integration verification, provider acceptance and attributed results.
   A test delivery cannot prove an ad-attributed sale. If setup/report access is
   unavailable, report that limit and keep an ordinary traffic campaign independent.
   Campaign conversion totals are not event-specific signup/purchase counts.
   Finish integration with evidence of source, event delivery and campaign selection;
   confirm ad attribution separately when eligible traffic and reports are available.

Only select conversion bidding when explicitly intended and owned setup is suitable.
It must be chosen at campaign creation; measurement added to an existing traffic
campaign does not change bidding or authorize creating a replacement campaign.
Do not automatically generate customer events or send them without valid consent.
