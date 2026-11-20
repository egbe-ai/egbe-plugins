# Read results and edit a campaign

Read [artifacts](../runtime/artifacts.md) and [API reference](../runtime/api-reference.md).
An audit/monitor request is read-only unless it explicitly includes optimization
or a standing policy authorizes specific changes and safety stops.

## Observe

Resolve exact campaign ID and read previous checks/change-log before acting.
Retrieve current campaign/child statuses and review/account blockers using the
[serving diagnostic reads](../runtime/api-reference.md#read-serving-diagnostics).
Read the affected campaign, groups and ads with `include_serving_issues=true`;
retain each returned code and distinguish missing diagnostics, an empty list
and a failed read. For a rejected destination change, compare the currently
saved URL/review state with the rejected request and preserve its error code.
Do not turn approval of an old creative into approval of the rejected URL or
promise a domain-review ETA. Diagnostics alone do not authorize a URL retry,
recreation, activation or budget/bid change. Then:

1. Read `/campaigns/{id}/results` for the requested Unix time window. Follow all
   pages before totals; preserve currency, timezone, window, fetched time and
   `available/no_rows/error`. Do not add cumulative snapshots from overlapping
   periods. Calculate CTR/CPC only from real counts and nonzero denominators.
2. Read `/campaigns/{id}/conversion-results` only when needed and available.
   Separate click-through from view-through; accepted CAPI receipts are not
   attributed conversions. Do not manufacture per-ad or search-term breakdowns
   from campaign-only results.
3. Read `/analytics/<product_slug>/campaigns` and `/stats` with supported periods;
   match the stable UTM campaign. Compare visits and applicable funnel events.
   Label unmatched time windows or site-wide metrics rather than presenting them
   as exact campaign outcomes.
4. Check destination/tracking defects when evidence points there. Missing metrics
   are not zero, and active configuration without impressions is not delivery.

## Edit an existing campaign

For a direct instruction such as “change this ad's headline,” target the exact ad,
read its full creative and preserve unaffected image/body/URL fields. The API accepts
the full creative object; write it back to that ad, not a replacement campaign.
Use a new durable operation for the approved change; unknown outcomes retain its
key. Read back and record before/after plus rationale. Keep budget/targeting edits
inside approved bounds. Measurement selections on clicks/impressions campaigns
can be edited through the [conversions workflow](conversions.md) without changing
bidding. Immutable bidding/oCPC optimization-goal changes require a separately approved
new campaign, not a hidden workaround. Follow the API's pause-first requirement
when activating children; a pause/relaunch interruption also needs authorization.

## Preserve observations

Return query/returned windows, fetch time, sources, currency, metrics, current
status and availability/attribution gaps. When durable observations are needed,
save them in `monitoring/check-<timestamp>.md`; `--phase monitoring` checks these
records. Simple reads need no new files. After a mutation append change-log,
refresh factual state/readback and use `--phase edit`.
