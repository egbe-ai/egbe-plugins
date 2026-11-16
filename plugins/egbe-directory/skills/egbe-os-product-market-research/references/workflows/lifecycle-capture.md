# Lifecycle Capture

Internal research of the email portion of competitors' conversion journeys.
Start immediately after Competitor Set so observation runs alongside other
research. Read the [input and observation contract](../contracts/lifecycle-capture.md).
Replicate plans do not consume lifecycle evidence.

## Policy

Assign registration, double opt-in and unsubscribe to a human with verified
access to the planned aliases and assigned mailbox. Any authorized human with
that verified access is eligible, regardless of role. If nobody with that access
is available, leave the actions pending and
continue other research. The agent inspects entry points without submitting
forms, records actual results, and
reads the assigned mailbox. Never pay, enter card details, supply a required
phone, bypass a CAPTCHA or bot check, or use a real third-party identity.
Leave optional phone fields empty. Never reply to sales representatives.
A rejected plus address or unavailable form needs a verified fallback or a skip.

Use one planned alias per competitor per capture: `<local>+NN@<domain>`, where
NN is random from 10–99. OS reserves numbers uniquely across captures sharing
the mailbox. A fresh research workspace creates a new capture; refresh retains
its UUID and mapping. Active legacy captures retain their existing aliases.
Exhaustion stops clearly; numbers are never silently reassigned.
The shared operational mailbox stays. Neutral tags do not conceal its address.
Attribution uses exact full To/Delivered-To matches, never sender or a prefix.

Bodies, mailbox addresses, aliases, message ids and personal links stay in the
private runtime. Every published string is scrubbed at one boundary: planned
addresses and the mailbox, plain or percent-encoded, become `[address]`;
message references become “a message”; unreadable messages disclose HTTP status
only. Published entry URLs lose query/fragment. Evidence carries subjects and
extracted facts, never bodies or excerpts. The list of signup actions also stays private.

## 1. Plan and discover entries

```bash
python3 scripts/run-lifecycle-capture.py --workspace . --product-domain product.com
```

Requires OS_API_KEY, optional OS_URL, and the deployed OS alias-reservation
endpoint. Domains come from --domains, receipt-backed Competitor Set, then
Keyword Economics excluding rejected domains; default maximum 10. This section
accepts the upstream selection as given.

The first call persists a capture id before reserving aliases, writes private
`egbe-docs/research/market/work/lifecycle_capture/plan.json`, and exits 2. URLs before review
are discovery seeds, not sign-up recommendations. Completed Funnel Teardown
may supply seeds but is not a prerequisite.

Inspect each competitor's comparable offer and public conversion path with the
available browser/source tools. Prefer details/materials, webinar/info session,
quiz/assessment, waitlist, free account or card-free trial, then newsletter.
Relevance to the current buyer and purchase matters: explain when a lower-ranked
entry is the closest usable path. A generic account or newsletter is not the
same sales journey without evidence.

Record selected and verified fallback entries in private entry-points.json
using the contract: fields, consent, phone/card requirements, instructions,
stopping point, sources and verification date. Unknown requirements stay
unknown. Hosted forms need the competitor's source/CTA, actual destination and
link/embed evidence. Record silent-waitlist risk rather than promising nurture.
Rerun: the runner validates discovery, incorporates it into plan.json and
renders private lifecycle-signups.md. Hand over that list early; do not rewrite
its choices independently.

## 2. Record signup results and continue research

The assigned human reports results in ordinary chat. Update subscriptions.json with
actual dates and the planned selected/fallback entry. Unknown phone/card needs
require verification by that human. Fallback use needs a reason; unavailable entries
go in skipped. Rerun to validate aliases, dates and entry binding, then publish
started when all competitors are accounted for. Pending sign-ups do not block
other research. An explicit harvest can read recorded
subscriptions while preserving outstanding ones as coverage limitations.

The runner writes private operator-actions.json with signup, confirmation and
unsubscribe actions plus day-3/day-14 harvest deadlines per actual subscription.
Unknown confirmation status does not imply double opt-in. If a confirmation
arrives, ask the assigned human to confirm through their authorized mailbox
access and record confirmed:false until they report success. Never expose
private confirmation links in published research.
Use the scheduling/runtime mechanism supplied by the caller to reconcile dates,
install harvest follow-ups and bounded reminders. Scheduler ids stay outside
domain artifacts. A manual caller without scheduling discloses that limitation
and hands over due dates: writing the file alone does not install reminders.
Cancel obsolete jobs when actions finish or captures change. Unsubscribe
reminders become actionable only after the full harvest.

## 3. Early and full harvest

```bash
python3 scripts/run-lifecycle-capture.py --workspace . --product-domain product.com --harvest
```

Run day 3 for early evidence and day 14 for the full window, separately from
each competitor's subscription date. Earlier confirmation reads are allowed.
The command derives partial/full from duration; successful publication is a
separate fact. Later snapshots replace current evidence/report and preserve
immutable private provenance for previously shared research.

List by full alias from the day before subscription through GET /mail/inbox
with to, since and limit=50; retain exact recipient hits. Read each message once
through GET /mail/message/{uid}. Record UTC arrival, subject, sender domain,
confirmation/welcome/nudge/offer/content signals, prices, discounts, deadlines
and unsubscribe availability. Nothing after cutoff/unsubscribe enters the data.
Bodies remain cached privately.
The cache stores portable message content without access-bearing links or
credentials; originals requiring those values stay under the research
`.local/lifecycle_capture/mail-cache/` boundary described in the artifact contract.

Observed positive behavior at two or more competitors may inform standalone
future email sequences with a partial badge and stated window; it does not
authorize a replicate option.
No offer by day 3 does not mean none in the
first week or full capture. Weekly cadence needs at least seven days; a welcome
burst is not a sustained schedule. Extracted structure/timing can inform future
email sequences while respecting current product claims and explicit limits.

Duration, dates and coverage remain visible. Fourteen days is a target duration,
not proof no mail was missed. A full 50-message page, missing body, failed listing,
unconfirmed opt-in or pending signup remains a limitation. Zero messages applies
only to its observed window, not a claim that the competitor does no email.
Budgets: 30 inbox listings and 60 message reads per invocation. Cached bodies
are reused; same-cutoff listings replay and the next day refreshes. --as-of is
never before the first subscription or after today, and cannot replace a newer
publication. Refused keys, rate limits and unreachable OS stop. No successful
listing means failure rather than an empty published harvest.

## 4. Publish

Write egbe-docs/research/market/evidence/lifecycle-capture.json with subscription,
lifecycle_sequence, lifecycle_message, lifecycle_pattern and coverage rows;
materialize Lifecycle capture in egbe-docs/research/market/full-report.md and record a
hash-backed receipt. The runner verifies report and evidence together; Git belongs to the caller. completed means publication succeeded;
phase and observation metadata determine whether the window was harvested.

A caller that indexes lifecycle evidence rebuilds its evidence index after
each harvest and carries the windows and coverage through.

## 5. Funnel handoff and same-day mail

05 reserves one numeric plus alias per funnel in the shared runtime registry
`egbe-docs/research/market/work/identity-registry.json` (schema 1, mailbox, identities with
identity_id, domain, funnel_id, alias and kind). Ordinary 02 capture aliases, including active legacy aliases, remain
reserved too; their OS reservation policy is unchanged. The registry is private, stable across resume and protected by
`identity-registry.json.lock`; never allocate a different alias on a retry.
Receipts use a canonical `identity_registry_binding` for only the identities
that section uses, including the real private mappings in its digest. Adding
unrelated identities or reformatting the shared file preserves those receipts;
changing a used mapping invalidates them.

05 writes `egbe-docs/research/market/work/funnel_teardown/lifecycle-handoff.json`, schema 1:
subscriptions and events. Each imported subscription names domain, alias,
funnel_id, campaign_refs, path_refs, entry_url, kind (`lead_form`, `quiz` or
`webinar_registration`), subscribed_on, confirmed, submission_ref and approval_ref.
`email_expectations` records confirmation and result as true, false or null,
with `source_ref: browser:<screen_id>` for a determined expectation. False means
the browser observation explicitly established that no such mail is expected;
null preserves uncertainty. Do not infer false from an empty inbox.
An observed delivery promise may supply `email_expectations.wait_until` as an
aware timestamp with the same browser source. Private `submission_checks`
preserve each submission's time, path and original campaign refs.
Only registrations already submitted with the exact data approved by the human
approver are imported. They account for that competitor without requiring another 02 sign-up.
Several funnels from one competitor remain separate subscriptions. Their later
messages retain funnel/campaign/path attribution; lifecycle recurrence counts
unique competitors, never aliases.

Read the mailbox on the day of the walk, before the normal capture window:

```bash
python3 scripts/run-lifecycle-capture.py --workspace . --funnel-mail
python3 scripts/run-lifecycle-capture.py --workspace . --funnel-mail --refresh
```

This mode works even when ordinary 02 subscriptions are still missing. It lists
only reserved funnel aliases and writes runtime
`egbe-docs/research/market/work/lifecycle_capture/funnel-events.json` (schema 1, events,
checks, pending, coverage, checked_at). It neither publishes 02 nor marks capture complete.
`--refresh` takes a new inbox snapshot within the same day; already read bodies
stay cached. Use it after an expected confirmation/result has not arrived yet.
Each check attributes funnel_id, path_refs, campaign_refs and alias, with
checked_at, inbox_since, query_succeeded and an inbox_snapshot source_ref.
The timestamp retains the actual query time and local timezone, including when
replaying a cached snapshot. A new approved submission needs a check after that
submission; refresh an earlier snapshot. The check history is retained across
refreshes and days. Equivalent campaign refs added to an already checked
physical funnel do not require a second submission or cancel its original
attributed check. Old caches without a query timestamp
remain pending until refreshed. No expected mail after an explicit false/false
browser observation still needs an attributable successful same-day check.

Events carry event_id, type (`email_confirmation` or `email_result`), funnel_id,
path_id (null when multiple paths share the alias), campaign_refs, alias,
occurred_at, source_ref, message_ref and verification_status. A result has a short
runtime subject/excerpt; the body stays in the cached message. Automatic result
classification is a candidate observation: verify the message content before
claiming a final result. Receiving a confirmation sets `received`, never
`confirmed`. The browser agent uses the locally retained original confirmation
link only within the approved continuation, then records its observed outcome
in the handoff events. If that local original is unavailable after a clone, use
authorized mailbox access; do not recreate a signup to recover credentials.

While the submission day is open, its first same-day check remains required.
A missed day closes as terminal `same_day_check_missed`; unknown expectations
close as `email_expectation_undetermined` after an attributable successful
query, retaining their unknown values. Promised mail continues pending
(`email_not_received` or `confirmation_required`) until an observed delivery
deadline, otherwise the existing 14-day capture boundary. A fresh successful
query at or after that boundary can close missing mail as
`expected_email_not_received` or `confirmation_unverified`. These gaps preserve the unseen browser result and unverified confirmation. Failed or
undated queries cannot establish absence. Never repeat a lead submission to
repair coverage. Email receipt time stays separate from campaign
cutoff and walk time. The imported aliases use the existing capture/unsubscribe
procedure when the capture ends. Public evidence keeps attribution and scrubbed
facts; exact aliases, receipt refs, message IDs and recipient links stay runtime.
