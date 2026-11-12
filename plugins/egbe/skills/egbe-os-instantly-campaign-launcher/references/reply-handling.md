# Reply queue and send recovery

`reply-worker.js` collects campaign-scoped inbound emails and adds unseen IDs to
`reply-queue.json` and project `outreach.db`. It never sends.
The collector requires the matching existing DB run/campaign before provider
calls; it does not reconstruct missing sending history by initializing an empty DB.
Read the original message and current run context; `intent_hint` is a keyword heuristic, not a
confirmed refusal, qualification or business outcome. Content decisions use the
current task/plan, not a second permission matrix in this tool.

```bash
node "$SKILL_DIR/scripts/reply-worker.js" --run-dir "$RUN_DIR" --env-file "$RUN_DIR/.env"
node "$SKILL_DIR/scripts/send-reply.js" --run-dir "$RUN_DIR" --email-id MESSAGE_ID --text-file "$RUN_DIR/replies/draft.txt"
node "$SKILL_DIR/scripts/send-reply.js" --run-dir "$RUN_DIR" --email-id MESSAGE_ID --mark owner_review
node "$SKILL_DIR/scripts/send-reply.js" --run-dir "$RUN_DIR" --email-id MESSAGE_ID --mark no_reply
```

These scripts also accept `--env-file`. Work one queue item at a time; do not run
concurrent senders. `owner_review` records a handoff but does not itself notify
the owner or send a draft. Use the agreed channel if a decision is needed.
`no_reply` closes a message without sending; it does not confirm an opt-out or
prove provider sends stopped. Automatic and out-of-office messages are not
interchangeable with explicit refusal.

## Confirmed refusal and stopping

After reading a clear opt-out, use:

```bash
node "$SKILL_DIR/scripts/send-reply.js" --run-dir "$RUN_DIR" --email-id MESSAGE_ID --mark opt_out
```

For a forwarded/ambiguous reply, inspect the original thread and pass
`--recipient-email <original-campaign-recipient>` if necessary. The selected
recipient must be a known member of this campaign. A forwarder's From address
is not automatically the person who must stop receiving outreach.

The command commits an idempotent `opt_out_confirmed` event to the existing
project `lead_events` before closing the queue as `no_reply`. It records the
normalized original recipient and source message ID. Failed event persistence
does not close the queue. Generic `no_reply` and old regex hints are not migrated
into confirmed refusals.

Launch, replenishment and reply sends consult confirmed events. A missing,
unreadable or incomplete DB after known sending is a recovery blocker, not an
empty suppression list. A genuinely new project is allowed; known sending runs
missing from the DB or confirmed queue events missing from it require restoration
and checking. A new run/upsert or run cleanup does not erase an earlier refusal.

Local filtering cannot stop a recipient already imported. The command checks
all known project campaigns from DB and recovery artifacts through owned gateway
reads and complete, validated lead pagination. Absence needs no provider write.
For each retained copy it reads the semantic recipient exclusion resource; a
confirmed main-sequence result can preserve the lead and history without pausing
the other recipients. An eligible copy uses only the exact-ID exclusion operation.
Settings such as stop-on-reply alone do not establish recipient exclusion.

The initial supported profile requires no attached or campaign subsequences and
complete empty workspace automation/webhook collections, checked internally by
Tools. Nonempty, unreadable or incomplete coverage remains unsupported/unknown.
The command then preserves the existing scoped campaign pause (readback status 2).
A pause proves containment, not per-recipient exclusion. No global blocklist,
email-based interest update, foreign campaign or automatic activation is used.

The queue retains `opt_out_confirmed: true` and `opt_out_provider` evidence,
including per-campaign `recipient_exclusion`. A nonzero exit or `provider.ok: false`
means local refusal was saved but containment is unresolved. Repeating the same
`--mark opt_out` rechecks without duplicating the local event; confirmed native
3/-1 copies need no write and already-paused campaigns need no repeat pause.
An uncertain mutation is recovered by GET, never automatically replayed.

Before a separately authorized activation, the launcher checks every retained
confirmed refusal against fresh owned main-sequence evidence. Missing local
history, partial/invalid pages, unsupported coverage or unknown results block.
A recovery attempt that had to establish exclusion leaves that launch attempt
blocked; a later explicit rerun rechecks all gates. The exclusion operation does
not itself activate a campaign.

This covers known local project refusals and the supported native main-sequence
state only. It does not cancel in-flight mail, qualify active subsequences or
promise workspace-wide suppression, header/link opt-outs, unsynchronized copies
or other projects. See [the endpoint contract](instantly-ops.md#recipient-exclusion).
Keep sensitive client files/credentials out of cold-email replies; use a suitable
protected product path if those inputs are actually needed.

## Same-thread send and uncertainty

A send uses the original message/thread and the mailbox that received it.
Unknown receiving mailbox blocks the send; do not substitute another sender.
The script checks campaign scope and known opt-outs, then claims the item as
`sending` before the external call.

- Confirmed success records `sent`.
- Rejected 4xx returns it to `pending`; inspect the reason before another attempt.
- Timeout, interrupted process or 5xx leaves `sending`: the message may have
  gone out. The client never blindly repeats a reply.

Inspect the provider thread and resolve a `sending` item explicitly:

```bash
node "$SKILL_DIR/scripts/send-reply.js" --run-dir "$RUN_DIR" --email-id MESSAGE_ID --mark sent
node "$SKILL_DIR/scripts/send-reply.js" --run-dir "$RUN_DIR" --email-id MESSAGE_ID --mark pending
```

Those marks are recovery assertions after evidence, not a way to force a resend.
An opt-out cannot be marked while a send remains uncertain; resolve that state
first. Keep the queue and DB together across handoff. Direct Unix cron only
collects; it does not read messages, compose replies or make these decisions.
