# Delivery state, launch and pause

Use the returned campaign ref and current provider state. Do not infer that a
campaign is live from a successful write or an ENABLED campaign flag.

## Inspect

```http
GET /ads/google/campaigns/{ref}/children
GET /ads/google/campaigns/{ref}/readback?expect=ENABLED
```

Children returns the current campaign, geo_targets, ad_groups, keywords,
negative_keywords, ads and responsive_search_ads under `data.raw`.
Readback adds `data.delivering` and `data.drift` (also in raw).

`delivering: true` means the campaign can serve and at least one complete
group → one of its keywords → one of its ads is ENABLED and eligible according
to Google's primary_status. It is capability to serve, not proof impressions
have already occurred. PENDING review or NOT_ELIGIBLE ads cannot establish that
path. Intentionally paused siblings do not block a different eligible path.

Drift identifies concrete blockers, including level, ID, status, expected status,
group and primary_status when relevant. If delivering is absent/null, state is
unconfirmed, not false or true.

Compare the observed objects, destinations, targeting and budget with the intended
operation. Unexpected serving objects or another product's destination require
attention, not silent adoption or broad activation. Report them and follow the
user's stop instructions.

## Launch or resume

```http
POST /ads/google/campaigns/{ref}/launch
Content-Type: application/json
```

```json
{"children":"auto"}
```

Check the current paused campaign, serving inputs and destination against the
authorized activation scope. This operation does not create missing objects.

The provider applies the selected campaign/child status changes in one atomic
mutation. Child modes are:

- `auto` (default): enable children only if there is no CONFIGURED ENABLED
  group → keyword → ad path. This test is about status, not review eligibility;
  an enabled but pending-review path still preserves all current child choices.
- `keep`: change only the campaign flag; preserve every child as-is. Use this
  for a requested resume that must not re-enable intentionally paused children,
  including when all serving paths were paused.
- `activate`: explicitly enable all nonremoved groups, positive keywords and
  ads. This is broad activation, not a substitute for a selected keyword/ad edit.

Negative keywords have no serving status and are not changed. If auto finds no
configured path, it can enable every child, including previously paused ones:
choose the mode from the actual intended change, not just the endpoint default.

The launch response carries delivering/drift. Independently verify
`GET .../readback?expect=ENABLED`. Report pending review as pending, not live.
Structural PAUSED/missing-object drift needs a scoped repair; it does not justify
blind campaign-wide activation. Preserve deliberately disabled objects.

## Pause

```http
POST /ads/google/campaigns/{ref}/pause
GET /ads/google/campaigns/{ref}/readback?expect=PAUSED
```

Pause changes the campaign only. Enabled children under a paused campaign are
harmless and are NOT drift for expect=PAUSED; do not spend extra writes pausing
them. The default readback expectation is ENABLED, so use PAUSED explicitly.

Record a successful pause's actual confirmation time, not a planned deadline.
If the cause of a confirmed stop is unknown, say unknown rather than infer
manual stop or budget exhaustion. A failed pause or stopped monitor is not
proof the campaign stopped. Preserve the observed reason in the campaign result
rather than replacing it when balances or time later change.

Launch/pause have no durable idempotency receipt through these routes. Repeating
campaign status still sends a mutation and uses quota. A failed post-write
readback can return delivering=null after successful mutation. After an uncertain
response, read state and reconcile before repeating the requested change.

## Set all child statuses

```http
POST /ads/google/campaigns/{ref}/children/status
Content-Type: application/json
```

```json
{"status":"PAUSED"}
```

This changes every nonremoved group, positive keyword and ad, not just missing
or newly created objects. It does not change the campaign. Use only when that
whole scope is intended; use [Search asset controls](search-assets.md) for exact
keywords or one RSA. Matching child statuses skip provider work/quota increment.
There is no durable operation receipt. The response is mutation results, not a
post-write delivery verdict; obtain fresh readback afterwards. Never replay an
old enable after a later intentional pause.

## State versus performance

Read metrics using [Reporting](reporting.md); a fresh configuration check is not
a campaign performance result. These launch routes do not install a total-spend
cap, future pause or monitoring job.
