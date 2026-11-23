# Build a paused Meta tree

Read the [API](../runtime/api-reference.md) and save
[execution records](../runtime/artifacts.md). Resolve existing IDs or uncertain
attempts before creating. Do not recreate objects to repair local documentation.

Prepare the requested `CampaignSpec`: `name`, `product_slug`,
`objective`, `optimization_goal`, positive `daily_budget_usd`,
`budget_level` (`campaign` or `adset`), `destination_url`, `segment`,
`destination_language`, `destination_language_locales`, `targeting` and
`creatives`. Each image creative has an uploaded Meta `image_ref` hash,
`headline`, `primary_text` and supported `cta`. Resolve locale IDs through
targeting search and include matching IDs in `targeting.locales`.
Conversion optimization requires the verified product `custom_conversion_id`.

1. `POST /ads/meta/plan` validates without Meta writes, quota consumption or a
   wallet hold. Resolve returned blockers, not by probing creates.
2. Preserve the exact clean spec, returned plan and token. Check targeting,
   assets and budget against the authorized inputs. The token does not
   establish consent. A clean plan verifies configuration; its conversion
   eligibility does not prove live event matching. Use the
   [pixel checks](../runtime/pixel-install.md#verification) for tracking evidence.
3. Stop before apply: show the founder this clean plan (spec, daily budget,
   targeting, creatives, destination) and wait for their explicit approval of
   it, unless a recorded project approval covers these exact values. Only then
   send `POST /ads/meta/apply` with
   `{"spec": {...}, "plan_token": "...", "approved": true}`.
   OS derives the retry key from this token. Exactly one ad set is supported
   because there is no per-ad ad-set mapping.
4. Save campaign/ad-set/ad IDs immediately. Apply contains campaign-level
   readback only. Read `/ads/meta/campaigns/{id}/state?expect=PAUSED` plus
   raw configuration to verify parent IDs, budget, media and destination.
   Keep requested values separate from observations.

Per-operation budget guards and wallet reserves are server-owned. Do not impose
a local daily cap or bypass a rejected budget via raw calls.
Apply compensation is best-effort, not proof of an empty account.
After a 409 or 422 from apply, stop and report; do not change the spec, re-plan
or re-apply to get past it. After timeout or `apply_rolled_back`, use
[recovery](recovery.md) before its same-spec retry. The tree stays PAUSED;
building does not activate it.
