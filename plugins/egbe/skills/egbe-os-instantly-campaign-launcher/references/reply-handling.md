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
all known project campaigns from DB and recovery artifacts, via tenant-authorized
gateway reads. It reads stop-on-reply/auto-reply/unsubscribe-header settings, but
these settings alone do not prove that this recipient stopped. With current
read surfaces, a present or unknown membership is contained by scoped campaign
pause unless pause is already confirmed; readback must show status 2. Complete
membership proving absence requires no pause. No global account/campaign action
or foreign-campaign access is attempted.

The queue retains `opt_out_confirmed: true` and `opt_out_provider` evidence.
A nonzero exit or `provider.ok: false` means the local refusal was saved but
provider containment is unresolved. Report that unfinished action. Repeating the
same `--mark opt_out` safely retries the check without duplicating the event;
already-paused campaigns are not paused again. Do not resume a contained campaign
until the opted-out recipient's future sending is resolved.

This protects known local project refusals only. It is not a provider-wide
blocklist and does not promise coverage of header/link opt-outs, unsynchronized
copies or other projects. The gateway has no new recipient-suppression endpoint.
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
