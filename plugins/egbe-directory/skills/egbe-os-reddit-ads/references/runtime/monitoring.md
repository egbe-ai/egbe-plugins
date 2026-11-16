# Reddit status, diagnostics and pause

Read the exact campaign ID and requested fields directly; no lifecycle/report
package is required. Metrics and diagnostics are read operations. Use the
relevant write endpoint only for an authorized change.

Read `/ads/reddit/campaigns/{id}/results`, direct campaign/group/ad readback
and separately attributed product analytics as relevant. Preserve query bounds,
report timezone, pagination and observation times. Configured ACTIVE, provider
approval and actual reported traffic are separate observations.

## Destination availability

Make a direct HTTP GET to the recorded URL including UTMs, without OS credentials.
Set `DESTINATION_URL` to that URL and run:

```bash
curl --silent --show-error --location --max-redirs 5 \
  --connect-timeout 5 --max-time 15 --output /dev/null \
  --write-out 'http_status=%{http_code}\nfinal_url=%{url_effective}\n' \
  "$DESTINATION_URL"
```

Use this HTTP check, not a paid actor/crawler. A timeout or blocked request is
inconclusive, not confirmed downtime. HTTP success alone proves neither tracking
nor the product journey. Apply the current task's stop conditions and authority.

## Sparse or flat delivery

Read `/ads/reddit/account`: check `provider_account.available`, individual
field availability, timezone, approval/suspension and separate funding readback.
Then read selected campaign/groups/ads by ID; retain configured/effective/
delivery status and rejection reasons, including disagreements.

Compare fully paginated reports using returned date/hour buckets and freshness
fields; see [API](api-reference.md). Distinguish last reported nonzero bucket,
provider update time and observation time. A later report may show renewed
delivery without explaining a quiet interval; a current parent pause does not
explain an earlier ACTIVE period. `modified_at` is not necessarily a
status-change time. Unknown metrics are not zero.

If no causal reason or budget-reset evidence is exposed, give Egbe the exact
IDs, query/returned bounds and timestamped facts for the account owner's history
check. Do not diagnose auction loss, outage or reset from ACTIVE plus underspend.
Diagnostic access does not authorize budget changes, toggles, replacements or
restarting a recorded stop.

## Pause

Use `POST /ads/reddit/campaigns/{campaign_id}/pause` for an authorized campaign
stop. Pause selected groups/ads via their status routes when that is the requested
scope. Read each affected object by exact ID. A paused parent can prevent delivery
while children stay configured ACTIVE; report that accurately. Do not delete or
archive as a substitute.

Save accepted mutations and actual confirmation time. Failed pause or stopped
monitoring alone is not confirmed campaign termination. Preserve the known stop
reason and evidence; if unavailable, say unknown. Do not infer a reason from a
later balance/deadline or copy a scheduled boundary into factual timestamps.
Missing results, research or reports never block stopping spend.

These operations do not install a monitoring job or scheduled pause. Use
[launch](../workflows/launch.md) for pending activation confirmation without
repeating accepted writes.
