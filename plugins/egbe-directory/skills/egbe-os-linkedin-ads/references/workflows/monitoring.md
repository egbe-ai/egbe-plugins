# Read results and change settings

Resolve the selected campaign from artifacts or owned lists. Read the campaign,
group, creatives and results for explicit inclusive UTC dates. Today is supported
but partial. Return fetched_at, requested dates, provider ranges, currency and
any error/unknown status with the observations.

Inspect delivery/moderation/serving-hold fields first when spend or impressions
are missing. Account eligibility, schedule, audience, CPC and creative review
can each prevent serving despite ACTIVE configuration. Do not infer the cause
from zero alone or automatically raise bids.

`metrics:null` / `data_status=unavailable` is not zero: LinkedIn can return an
empty report both for no activity and missing reporting access. A real provider
row containing zeros is observed zero. API failures remain failures.
Older ranges may be rounded to full months; inspect observed_ranges.
Clicks, product visits and product outcomes have different meanings; do not label
a UTM product signup as a provider-attributed conversion.
If provider conversions were configured, use the
[conversions workflow](conversions.md) for the selected campaign/rule report.
An accepted event receipt isn't a conversion count; report the two separately.

Registry periodically synchronizes cumulative actual campaign spend into wallet.
The launch hold is not a second charge. Report unsupported currency, missing
reporting permission or unavailable cumulative spend as a billing-sync blocker;
never settle missing data as zero. Historical data beyond provider retention
requires Egbe team reconciliation.

## Changes

Read before changing. `PATCH /campaigns/{id}` changes only supplied name, daily
budget, CPC, targeting or schedule; it does not change status, format or objective.
Preserve omitted settings. Confirm fresh readback and append the reason/evidence
and authorization to change-log. Monitoring alone authorizes no mutations.
Use the build workflow for creative replacement; do not guess a raw PATCH body.
