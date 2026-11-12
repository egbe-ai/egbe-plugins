# Campaign operations

## Connection and scope

Scripts authenticate to `$OS_URL/outreach/instantly/{path}` with
`Authorization: Bearer $OS_API_KEY`. They use the installed connection-identity
helper; no provider API key or hosted-agent boot environment is assumed.
`launch-campaign.js` materializes available credentials and identity in the
private run `.env` (0600). Workers load that file or an explicit `--env-file`.

The gateway exposes project-owned campaigns, leads and campaign emails.
`GET /accounts` is a shared workspace account list, not tenant-filtered sender
authorization. Registry ownership is authoritative. Manifest IDs and run/agent
tags are local scope/conflict checks; best-effort tag assignment is recorded and
does not replace server ownership. Never use a name match or tag to adopt another
project's campaign.

The bundled client wraps provider POST/PATCH bodies as `{"payload": {...}}`.
The semantic exclusion call below uses its own fixed intent body.
Bodyless activate/pause calls have no body. Use the client or supported scripts;
raw provider-shaped writes to OS can fail 422.

## Paginated and date-filtered reads

Paths below are relative to `$OS_URL/outreach/instantly`. The bundled
`scripts/lib/instantly-client.js` exposes the same reads:

| GET path | Query parameters | Client method |
| --- | --- | --- |
| `/campaigns` | `limit` (default 100), `starting_after` | `listCampaigns(limit, startingAfter)` |
| `/accounts` | `limit` (default 100), `starting_after`, `status_filter` | `listAccounts(limit, {starting_after, status_filter})` |
| `/campaigns/{id}/analytics/overview` | `start_date`, `end_date` | `analyticsOverview([id], {start_date, end_date})` |

For lists, pass the response's `next_starting_after` unchanged as
`starting_after` on the next read. Campaign pages are filtered to this project
after provider pagination: even an empty `items` array can have a next cursor.
Continue until the cursor is absent; stop and report a repeated cursor or read
failure instead of claiming the list is complete. Account reads preserve
`warmup_status` and `stat_warmup_score`; restrict observations to the campaign's
assigned senders. The SDK also accepts `status` as an alias for `status_filter`.

Overview dates accept `YYYY-MM-DD` or full ISO 8601 timestamps; date-only values
mean UTC midnight. For a UTC calendar day, specify explicit bounds such as
`2026-01-15T00:00:00.000Z` through `2026-01-15T23:59:59.999Z`. The gateway passes
the supplied strings to Instantly without normalization. Omitting both dates
retains the lifetime overview. Range-filtered fields include `emails_sent_count`
and `bounced_count`; keep these observations separate from lifetime totals.
Invalid ranges return the provider's error, not an empty or lifetime report.
The campaign ID comes from the owned path, not caller-supplied `id`/`ids`
parameters. See the [provider overview contract](https://developer.instantly.ai/api-reference/campaign/get-campaigns-analytics-overview).

## Prepare or activate an existing run

```bash
node "$SKILL_DIR/scripts/launch-campaign.js" --run-spec "$RUN_DIR/run-spec.json"
```

See [run-state](run-state.md) for the spec and paths. The launcher validates the
input, resolves specified senders, creates/reuses its campaign, uploads rendered
sequence and missing leads, checks import/verification, and writes state.
Preparation defaults to a non-activated draft. Activation occurs only with
`campaign.activate_on_launch: true`, after the applicable decision and gates.
A rerun does not mean a new experiment: it resumes the manifest. A genuinely new
test needs a new run identity, even if the audience and offer are the same.

The launcher fingerprints rendered sequence plus senders. A changed fingerprint
requires an intentional `--allow-sequence-update`; do not add this flag merely
to silence drift on an existing campaign. Use supported rendering when updating:
raw `{{senderName}}` in a provider patch is not a provider variable.

Create/import calls are not blindly replayed after uncertain outcomes. On a
create timeout/5xx, inspect scoped campaign IDs and creation times before retrying.
For an uncertain import, a complete live membership read establishes what is
missing; malformed, unavailable or incomplete membership stops the import.
Keep manifests, hashes and carry-over files through recovery.

## Senders, sequence and payload checks

Specify exactly one of `campaign.email_list` (owned exact addresses) or
`campaign.sender_domains` (owned cold domains). Named missing/inactive accounts
fail. Domain-selected accounts are sorted and may be limited by
`max_sending_accounts`. The launcher excludes `egbe.app` and `egbe.dev` trust
domains and fails if no eligible sender remains. This is a client-side safeguard;
the shared account listing is not a server-side proof of sender ownership.

Use a true sender identity. `reply_policy.sender_name` or `sender_name` takes
precedence over the selected account's recorded name; the code does not infer a
person from an email local part. If `{{senderName}}` is used, an explicit or
recorded account name is required. It is compiled once, not per sending account:
with rotating senders verify it is truthful for every mailbox (the launcher
warns). Unknown names must not be invented.

Plain text bodies become Instantly editor-native HTML: each line is a `<div>`,
blank lines are `<div><br /></div>`. Markdown links and bare URLs are rendered
with run UTMs in hrefs, while visible text stays readable. Review the rendered
output rather than manually copying unrendered spec text to provider PATCH.

Empty subjects on later steps continue the preceding thread; a nonempty subject
chooses a new thread. Either is supported. `delay_days` is the wait before that
step; the launcher maps it to the preceding provider step's delay. A delay on
step one is ignored with a warning; use the campaign schedule for a delayed start.
The final provider delay has no following step.

Used merge variables must resolve for every new lead. Missing/unresolved values
are payload errors; unusual capitalization, short names or long company names
are review warnings, not proof that real data is invalid. Exact title/credential
tokens used as first names (such as Dr or CA) are rejected unless the actual name
has been checked and marked `first_name_confirmed: true`. No merge token, fixed
sequence length or first-message link ban is required. Placeholder CTA URLs
(`example.com`, `*.example`, unreplaced product/instance tokens) still fail.

`campaign.daily_limit` is an explicit positive campaign-wide cap, not a minimum
recommended volume or inferred per-mailbox capacity. Validate the selected
schedule, nonempty sending days and timezone. The launcher maps its known
`America/New_York` alias to `America/Detroit` with a warning because of the
provider's enum; a valid IANA zone alone does not prove provider acceptance.
Read back the campaign's actual schedule and sender assignment.

`open_tracking` and `link_tracking` default off; either can be explicitly set.
`stop_on_reply`, `stop_on_auto_reply` and `insert_unsubscribe_header` default
true. Activation requires confirmed readback of the configured safeguards;
missing readback is not success. Known opt-outs and unknown project history also
block unsafe import/send/activation; see [reply handling](reply-handling.md).

## Import verification

Source status is not import verification. By default the launcher uploads with
verification enabled and waits before activation. It reads campaign
`lead_stats`, falling back to per-lead `verification_status` across the whole
campaign; imported but not yet visible leads remain pending. Valid is status 1;
-1 is invalid; 11/12 pending; other verification codes count as invalid/risky.
Missing/null read surfaces are not a successful zero.

Current execution settings (these are adjustable client defaults, not market
success thresholds):

| Setting | Current default / meaning |
| --- | --- |
| `verify_leads_on_import` | true; asks provider to verify |
| `wait_for_verification` | true; blocking wait gate, distinct from requesting verification |
| `max_invalid_lead_pct` | 5 percent invalid/risky; records rejected IDs/addresses |
| `verification_timeout_minutes` | 45 |
| `verification_stuck_polls` | 8 unchanged polls |
| `allow_unverified_activation` | false; explicit override of incomplete verification, not other safeguards |

The older `verify_leads` field is a fallback for the two verification flags.
Do not change either flag as an automatic workaround. Pending/unread verification
normally leaves the campaign unactivated with exit 2 and
`verification_pending` / `verification_unread` in the launch result.
Read `launch-summary.json` and `state/verification-state.json`; rerun the same
run when its state can be checked. A readable empty provider lead list after an
import is an import failure, not merely a stuck verifier.

If the invalid percentage exceeds the configured value, inspect
`state/invalid-leads.json`. After deliberately removing unwanted entries from
the source list, a rerun attempts eligible deletion and records
`state/deleted-leads.json`, removes deleted entries from carry-over, then
rechecks the whole campaign. Failed/unknown cleanup blocks activation.

Success requires provider readback: activation response alone does not establish
that the campaign is active. Inspect `activation.confirmed`, `launch_status`,
verification outcome and safeguard readbacks. Creating a draft is not sending.
A preparation-only rerun is not itself a pause request: inspect `actual_state` /
`campaign_status`, not the absence of a new activation request. Confirmed-refusal
protection still applies when membership is unreadable. Its attempts and readbacks
remain in `opt_out_stop_results` even if the launcher subsequently exits with an error.

## Narrow cleanup and correction

These existing gateway operations are project-scoped; foreign objects return
404. Do not bypass a refusal by directly calling Instantly.

- `DELETE /campaigns/{id}`: only draft status 0 with demonstrated zero sends.
  Returns 409 `campaign_not_draft`, `campaign_has_sends` or
  `campaign_sends_unknown` otherwise.
- `DELETE /leads/{id}`: only never-contacted leads. Activity counters/timestamps
  or nonzero interest block with `lead_contacted`; absent activity evidence
  blocks with `lead_contact_unknown`. A status label alone is insufficient.
- `PATCH /leads/{id}`: only first/last name, company, website, personalization
  and custom variables. Changing email/campaign/status is unsupported.
- Pause an owned campaign that has sent; retain its replies and history.

Campaign delete and lead patch consume update quota. Lead deletion uses its own
resource (Registry default 500/day); project configuration controls the current
limit. Pause is not blocked by campaign-update quota. A cleanup timeout/5xx may
already have changed the provider: read back before repeating. Cleanup is not
recipient suppression and does not erase confirmed opt-out events.


## Recipient exclusion

Relative to `$OS_URL/outreach/instantly`:

- `GET /campaigns/{campaign_id}/leads/{lead_id}/exclusion` reads fresh owned
  evidence. It is available with `outreach:read` / project read access.
- `POST` to the same resource accepts only `{"intent":"confirmed_opt_out"}`.
  It requires existing privileged outreach writer access; read-only keys cannot
  mutate. The bundled client exposes `getRecipientExclusion` and `excludeRecipient`.

Tools checks Registry campaign ownership before native lead access and verifies
ID/campaign identity. In the supported profile it sets only native
`lt_interest_status=-1` via exact lead-ID PATCH and verifies Completed (3) /
Not Interested (-1). Reply/contact/history data remain retained. Existing generic
lead PATCH stays limited to personalization. This safety operation, like scoped
pause, is independent of the ordinary campaign-update quota.

Inspect `state`: `confirmed` is observed native main-sequence exclusion;
`eligible` is a GET result that still needs action; `unsupported`, `rejected` and
`unknown` do not authorize resuming. `scope`, `observed_at`, `lead_status`,
`interest_status` and `write_attempted` describe the bounded observation, not
permanent suppression. The initial profile requires complete empty subsequences,
automation and webhook collections; an omitted lead attachment field by itself
is insufficient. Global collection details are never returned to the project.

There is no fallback to email-based interest updates (which can propagate to
other campaigns), a global blocklist, deletion or activation. A timeout/5xx may
follow a committed PATCH: use GET for recovery before considering another write.
Neither the client nor Tools automatically retries that write. HTTP success
without `state: confirmed` is not proof. Read failures expose safe status and
bounded numeric `retry_after` where available, without provider response bodies.
The shared request deadline is 22 seconds, including ownership; native attempts
are bounded to 5 seconds each. This does not cancel queued/in-flight mail or
qualify active subsequences; retain containment for unverified cases.

`listLeadRows` and `listLeadEmails` follow native continuation even on short pages,
reject invalid identity/duplicate IDs/repeated cursors and report incomplete reads
as `ok: false`. Multiple same-email IDs are retained and assessed individually.
Legacy responses without an explicit cursor use last-ID continuation on full
pages; they do not gain a recipient-exclusion exception without new semantic
readback. The old/new server transition therefore remains contained.
