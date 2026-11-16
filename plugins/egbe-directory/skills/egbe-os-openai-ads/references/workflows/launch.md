# Launch an existing campaign

Read [artifacts](../runtime/artifacts.md), [API operations](../runtime/api-reference.md)
and [monitoring](monitoring.md). This workflow does not create missing objects.

Before activation:

- confirm explicit spending authority or the applicable product policy, with the
  intended daily budget, bidding, geo, destination and allowed changes;
- verify current paused campaign and intended child IDs, review state, creative,
  destinations and budgets against recorded evidence; resolve unknown writes;
- confirm account/payment readiness and tracking limitations; optional provider
  conversions are required only if the chosen bidding/measurement needs them.

Journal each operation. While the campaign is paused, enable only intended ad
groups/ads via their status endpoints; intentionally excluded children remain paused.
Then call `/campaigns/{id}/launch`, which uses the wallet. Do not retry an insufficient
funds rejection by changing budgets or using a raw endpoint.

Read the tree again independently. Record `active` only as observed configuration,
not proof of impressions. Record pending review/account blockers separately. On
partial or unknown activation preserve the actual state and saved operation;
do not report a successful launch from the intended action alone.

Update state/readback/change-log and run `--phase launch`. Return campaign IDs,
observed configuration, actual daily budget, delivery readiness limits and any
unconfirmed operation. Launching does not schedule future checks or stops.
