# Paused build and recovery

Read [artifacts](../runtime/artifacts.md) and [API operations](../runtime/api-reference.md).
For new or changed images also read [Chat-card production](../creative/chat-card.md).
This workflow creates/repairs only the authorized planned objects, all paused.
It does not activate them or expand the approved campaign scope.
Check the [minimum-budget note](readiness.md#minimum-daily-budget) before creation.

1. Resolve the selected campaign, requested configuration, creatives, tracking and
   recorded operations. If resuming, read existing owned objects before creating.
2. Resolve outstanding `prepared/unconfirmed` operations with their saved exact
   key and payload. Reconstruct missing local evidence from owned readbacks;
   never reset the operation journal to escape a conflict.
3. Create or reuse the paused campaign with the approved daily budget, geo IDs and
   immutable bidding choice. Save the returned ID immediately. Provider name
   suffixes are expected; keep the local slug and UTM stable.
4. Upload/reuse the approved images; save file IDs. Create only missing planned
   ad groups, then ads with those file IDs and tracked destinations. Journal every
   write before sending and persist each successful result before the next write.
5. Read campaign, children, budgets, creatives and destinations through OS. List
   owned children with pagination and filter exact campaign/group parents to find
   drift beyond recorded IDs. An extra active/unapproved object is not permission
   to adopt or delete it silently.
   Preserve `parent_binding_source`: `registry` is durable creation linkage, not
   independent provider confirmation; `provider_verified_against_registry` means
   both agree. Either supports the structural parent check. Conflicts are errors,
   not fields the agent should repair in local evidence.
6. Write the factual state, readback and change log. Run `--phase build-paused`
   when the planned tree is complete; use `--phase recovery` for a partial result.

On partial failure preserve IDs, exact pending requests and successful observations.
Stop blind retries on unknown outcome; source/upload recovery may require Egbe team
reconciliation. An empty paused campaign is incomplete but does not spend; do not
create a replacement shell to make the task look successful. If an unexpected live
object can spend, apply an authorized safety pause and record it, or urgently request
founder action if pause is outside the task authority.

Done means the planned objects exist and have matching paused readback, not merely
a successful campaign-create response. Return incomplete work honestly with the
specific unfinished operation and its recovery instructions.
