# Reddit execution constraints

- Use OS and owned exact IDs; ownership failure is not permission to mutate.
- Build PAUSED; campaign activation does not cascade to children.
- Campaign creation has durable same-key/same-payload recovery; child-create
  success caches are short-lived. Preserve uncertainty and read before retrying.
- Ad-group creation reserves `ceil(goal_value / 10000)` USD cents before the
  provider call, including PAUSED groups. A hold is not spend and is not
  multiplied by scheduled days.
- Update rejects `goal_value`/`goal_type` because it does not refresh the
  hold. No in-place budget update is available. Do not automatically create a
  replacement to change budget.
- Update rejects `configured_status`; use the status route so Registry's
  status/hold bookkeeping stays synchronized.
- Community relevance is not Ads eligibility or forecast reach. Use current
  returned interest IDs; no validate-only group endpoint is exposed.
  Never create real objects merely to learn a schema.

See [API](api-reference.md) for units, payloads and retries.
