# Activate or resume Meta objects

Use current authorization and exact selected IDs. Refresh
[read-only checks](launch-ready.md); do not create during activation.
Preserve audience, destination, assets, objective and budget.

Activate selected ads, then ad sets, then campaign:

```text
POST /ads/meta/raw/ads/{ad_id}/status        {"status":"ACTIVE"}
POST /ads/meta/raw/adsets/{adset_id}/status {"status":"ACTIVE"}
POST /ads/meta/campaigns/{campaign_id}/launch
GET  /ads/meta/campaigns/{campaign_id}/state?expect=ACTIVE
```

Save mutation responses and timestamped live readback. Only the state response
establishes configured tree state; report `drift` when partial.
`delivering:true` is an all-levels-ACTIVE check, not observed spend/impressions.
Do not invent launch/restart time from intent or a later monitoring observation.

After an ambiguous response read first. Do not recreate or toggle to clear
uncertainty. Report unconfirmed state and the required recovery read.
Activation does not install a monitoring job or scheduled pause.
