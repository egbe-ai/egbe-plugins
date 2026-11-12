# Read Meta state and metrics

Resolve the approved campaign, ad-set and ad cohorts from the saved plan,
including intentionally paused or retired objects and the existing stop latch.
A read never authorizes restarting a safety pause.

For a running safety check, reuse two observations:

```bash
GET $OS_URL/ads/meta/campaigns/{id}/state?include_configuration=true
GET $OS_URL/ads/meta/campaigns/{id}/results?period=MAXIMUM
```

The state response's `configuration` contains the campaign and fully paginated
ad-set/ad details with `complete=true`; `observed_at` and `provider_diagnostics`
accompany that snapshot.
Reuse it for the approved configuration checks (budget, targeting, creative and
URL identity) and exact cohort statuses; do not GET every object again for each
assertion. Preserve the frozen checks: missing fields or incomplete enumeration
remain uncertainty. A retired PAUSED ad is not an unexpected pause in an approved
ACTIVE ad, and it must not be restarted to make the whole-tree verdict green.
The existing `delivering` flag tests whether the entire returned tree is ACTIVE;
it does not prove impressions or override the approved cohort map.

Use the chosen-window report once for all spend, impression and link-click
checks. Check `metric_availability` for every field needed by the existing guard;
one available metric does not make the others available. MAXIMUM is suitable for a lifetime counter; choose an explicit range
when the approved counter has another scope. Check `report.query`, returned
bounds, native currency, availability and the actual account-local day before
comparing with the existing stop thresholds. Do not reset counters or use TODAY
as a replacement for a lifetime cap. Empty data is unknown. A configured ACTIVE
tree does not resolve missing or delayed metrics.

`configuration.campaign.account_id` identifies the actual campaign account.
Retain verified account currency/timezone with that identity. The generic
`/ads/meta/account` describes the currently configured fleet account, which may
differ for a legacy campaign; do not borrow its timezone for another account.
If matching account context is unavailable, retain the safety stop and request
the missing read-only account context.

On a one-page tree these two observations use four Graph reads: campaign,
ad sets, ads, and insights. Extra pages increase this; inspect the actual
`provider_diagnostics.request_count` rather than equating one OS request to one
Meta call. The full configuration read is bounded and fails unavailable on
cycles, invalid continuation or exhausted pagination; partial trees never count
as a verified configuration.

On Meta code 17/subcode 2446079 or HTTP 429, save the error and its safe usage
context. OS retains the native HTTP status (including 400), with machine-readable
`data.error=meta_api_rate_limited`, native codes and any `retry_after_seconds`.
Honor a returned Retry-After before another diagnostic read. Native usage fields
and `estimated_time_to_regain_access` are observations, not an absolute allowance
or a recovery promise; an absent retry hint or a zero native estimate does not
certify that another call is safe. Do not blindly retry, perform another complete
audit to explain the same throttle, or toggle the campaign. Preserve the existing
pause-only response to uncertain status/cost coverage and verify the stop through
its established recovery path.

There is no universal supported five-minute cadence. Account for pagination,
other shared-identity traffic, observed usage and the approved safety requirement
when scheduling the next read. Once a stop is confirmed and latched, avoid
repeated full-tree/configuration polling; retain required stop verification,
late-cost reconciliation and the approved next check. Do not disable those
obligations or loosen thresholds to reduce calls.

[Insights](../runtime/insights-reference.md) defines window/currency/availability;
[attribution](../runtime/shared-analytics-attribution.md) covers separately sourced
product outcomes. Preserve request windows, observation times and limitations.

These are read operations. For an explicitly requested change use its write
endpoint and save the response/readback. A metrics read does not establish a new
activation timestamp. Preserve missing metrics as unavailable, not zero.
