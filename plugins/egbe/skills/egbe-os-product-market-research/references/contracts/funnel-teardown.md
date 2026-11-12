# Funnel walk contract v2

`funnel-walk.v2` is the shared mechanics version. The closed values live in
[`walk-mechanics.v2.json`](walk-mechanics.v2.json); egbe-os-quiz-funnel ships an identical
copy and retains its standalone selection task. This contract describes the
05 JSON artifacts. Legacy v1 observations stay legacy; missing screenshots and
post-contact screens cannot be reconstructed by schema migration.

## Identities and scope

A campaign is one competitor + channel + country + verified semantic ad
destination. It is a research grouping, not an ad-account campaign ID. Prepare
inherits the exact ordered `creative_selection.v1` list published by 04, without
its own landing ranking or cap. `campaign_id`, `funnel_id`, `path_id` and
`walk_id` are separate identities; extra persona paths do not add competitors
or campaign votes. Own destinations have `role: own`, no campaign refs and no
submissions. Unknown ad destinations remain per-channel coverage gaps.

Original ad URLs, opened URLs, redirects and semantic query/fragment values
are retained. HTTP and HTTPS schemes remain distinct; when the initial browser
URL differs, `redirect_chain` records continuous `{from,to,source_ref}` browser
observations from the ad entry to that opened URL. Even UTM may change the offer.
No tracking removal or shared walk
across campaigns is assumed without browser evidence of equivalent country,
content and route. Destination recovery in runtime `destinations.json` requires
schema 1 records `{creative_id,status,url,relation,source_ref,verified_on}`;
`relation` is `native_ad_destination`, `observed_ad_cta` or
`provider_ad_history`. A generic program URL or YouTube-description link is a
candidate, not verification of a particular ad's destination.

Runtime `equivalences.json`, schema 1, may reuse a walk only within the same
competitor, country and channel. Each `equivalences` record has `equivalence_id`,
all original `campaign_ids` and `addresses`, `verified_on`, `source_ref`, explicit
`verification: {country:true,content:true,route:true}` and real hashed
`screenshots` covering those entries. Campaign IDs, original URLs and counts
remain distinct; `equivalence_ref` records the verified reuse. Private-data
captures cannot be exported as equivalence assets.

## walks.json

The root has `schema_version: 2`, `contract: funnel-walk.v2`, the current
`inputs_sha256` from candidates.json, and `walks`. A walk names exactly its
selected `funnel_id`, the candidate's `campaign_ids`, `path_id` (primary path
`buyer`), `address`, `role`, `persona_id`, `walked_on`, `viewport: 390x844`,
`observed_market`, `status`, `stop_reason`, `observed_outcome`, `unknown` and
`screens`.
The primary path uses `research-context.json`'s persona ID. Additional personas
must be declared in `additional_personas` and used only for meaningful branches.

`walked_on` is the actual recent browser date, independent of the frozen
`campaign_as_of`. Record country as unknown if the site does not establish it;
currency alone does not establish country. `observed_market` includes language,
currency, country selector and consent/banner choice when visible. A mismatch
is reported and excluded from target-country patterns.

Closed research statuses: `queued`, `in_progress`, `needs_approval`,
`needs_account`, `needs_email`, `blocked`, `completed`, `boundary`.
Closed stop reasons are in the mechanics JSON. Only observed permitted outcomes
are accepted: `lead_submitted`, `webinar_registered`, `quiz_completed`,
`result_observed`, `public_content_end`, `not_observed`. A boundary is not a
reached registration. Full length of every partial path stays unknown; the
runner records the number of observed main steps and the last observed screen.

Each logical screen has:

- unique `screen_id`, `attempt_id`, page/state `url`, `kind`, `branch_role`
  (`main` or `auxiliary`) and `advance`;
- actual observed `headline`, `headline_words`, `options`, `words_per_option`,
  `notes`, available options, selected `answer`, `cta`, `offer`, `proof`,
  `lead_fields`, progress/skip controls and relevant other content;
- `screenshot: {path,sha256}`, an existing raster file within the workspace,
  with its verified SHA-256. Optional `screenshots` add full-page or significant
  lower-page blocks without increasing logical step count;
- typed `amounts` with `kind: price|discount|financing|salary_claim|other` and
  actual visible `text` and `context`, never a mixed bag of regex numbers;
- `result_type: teaser|final|not_observed|absent|not_applicable` where relevant.
  A `teaser` screen is an intermediate example, not the final quiz result.

Screens use browser observations, not page-source configuration or email
content. Long pages need captures covering headline, offer, proof, price and
CTA. Save forms before filling (`captured_before_fill: true` when submitted).
Review screenshot pixels before publication. If the primary capture has
`contains_private_data: true`, supply a real `display_screenshot` with `path`,
`sha256`, the original `source_sha256` and `derivation: privacy_redaction`.
The raw capture stays private; the public `screenshot` is that display derivative.
Additional captures with private data must be recaptured safely. Hash validation
confirms file identity, not pixel privacy. Never fabricate a browser observation.
One real screen is valid, including an immediate account or technical gate.
Each attempt records at most 40 screens; an explicit budget stop remains
pending and can resume under a new attempt ID. Do not invent extra screens.

A discount popup or consent state is auxiliary and cannot replace the main
route implied by the selected creative. A required contact screen continuing
onwards has `submission_required: true` and
`action: {type: submit, submission_ref: <intent event id>}`. Account-gated
continuation requires `operator_access_ref: chat:<human access reference>`;
the agent never creates an account. Stop before payment/card entry, CAPTCHA,
required SMS verification and live-sales-call booking. Capture the booking
tool, questions and visible slots without submitting a booking. A walk that
sends no forms ends at the first contact screen with status `boundary` and
stop reason `form_not_submitted`, after capturing that screen and its fields.
`completed` cannot end at a contact/account/payment/verification gate, loader or
booking. `quiz_completed` requires a final result or an approved submitted
completion with browser confirmation; `lead_submitted` and `webinar_registered`
require both a submitted journal outcome and observed confirmation/result.
`public_content_end` requires explicit `completion_observed: true` on its last
main screen. An account continuation requires access provided by an authorized account holder.

`branch_points` records a screen, reason, `meaningful_change` and
`alternate_path_id`. A relevant alternate branch changing offer, result, price
or conversion must be observed; a missing required path keeps research pending.
Cosmetic personalization does not require another full path. Reusing a known
post-form outcome must carry observation refs and must not repeat a lead
submission automatically.

## Approval and submission journals (private runtime only)

Before any sending, prepare the combined known form list in
`approval-plan.json`, schema 2, `forms`. Each immutable form revision has
`form_id`, integer `revision`, `funnel_id`, `path_id`, `campaign_ids`, `screen_id`,
`url`, `purpose: lead_form|quiz|webinar_registration`, stable `alias` and the
exact `fields` map. The fingerprint covers these exact values via
`funnel-model.form_fingerprint`. New forms, fields or values require a new
revision and supplement human approval; no broad approval authorizes them.

`approvals.json`, schema 2, contains `approvals` with `approval_id`,
`confirmed_by: human_operator`, `source_ref: chat:<actual confirmation>`,
`approved_at` ISO timestamp with timezone and exact `forms` references
`{form_id,revision,form_sha256}`. The runner never writes human approvals;
an agent-authored approval file alone is not human confirmation.

`submissions.json`, schema 2, is a chronological `events` journal:

1. Before sending: `type: intent`, unique `event_id`, `form_id`, `revision`,
   `approval_id`, `form_sha256`, exact `fields`, `occurred_at`.
2. After observing the response: `type: outcome`, unique `event_id`,
   `submission_ref` to the intent, `outcome: submitted|not_submitted|unknown`,
   `source_ref` to the browser observation and `occurred_at`.
3. After uncertainty: inspect without sending, then append `type: resolution`
   with the observed outcome and source. An unresolved intent stays pending.
   Retry is permitted only after observed `not_submitted` and an explicit
   `retry_authorization_ref` with a new human approval ID; never automatically
   on resume. Form revisions, approvals and events are append-only against
   `journal-checkpoint.json`; an interrupted attempt cannot be erased.

Email equals the stable per-funnel alias; names follow the approved persona.
An accepted phone uses a full US fiction number ending `555-0100`–`555-0199`.
A rejected format is `blocked: phone`, never a random real number. This rule
applies only to 05; Lifecycle Capture's own phone rule is unchanged. Password,
card and payment fields cannot be planned. Own forms cannot be planned/sent.

The shared `egbe-docs/research/market/work/identity-registry.json` is schema 1 with mailbox
and identities (`identity_id,domain,funnel_id,alias,kind`). Numeric +NN aliases
are stable, reserved once under the shared `.lock`, and coexist with 02 aliases.
Each receipt pins `identity_registry_binding`: schema 1, selection of used
`funnel_ids` and `lifecycle_domains`, and a canonical SHA-256 of those actual
mappings plus the mailbox. Only the digest and selection are public. Unrelated
allocations or JSON formatting do not invalidate a receipt; changing a used
alias, identity ID, domain, funnel mapping or mailbox does.
`lifecycle-handoff.json` exports private completed registrations and references
to 02. Same-day email events return through
`egbe-docs/research/market/work/lifecycle_capture/funnel-events.json`; received confirmation
is not confirmed, and received result does not invent browser completion.
Mail/browser/ad times stay separate; a closed mail coverage gap never changes
the observed browser outcome, partial path or feature measurements.
One handoff subscription per funnel merges all campaign/path/submission refs
and keeps its stable alias. A submitted path declares
`email_expectations: {confirmation: boolean|null,result: boolean|null,source_ref}`;
known expectations cite an actual `browser:<screen_id>`.
An observed promise can additionally specify an aware `wait_until` timestamp
with that browser source. Each private `submission_checks` entry retains
`submission_ref`, `submitted_at`, `path_id` and the originally submitted
`campaign_refs`, plus that path's observed `email_expectations` and confirmation
state; new submissions need their own post-submission check. Expected mail and
verification events must match that path and occur after its submission.
When a shared alias gives a mail event `path_id: null`, its timestamp must
still follow each submission whose expectation it is used to satisfy.
The returned file includes `checks` with `funnel_id`, `path_refs`,
`campaign_refs`, `alias`, `checked_at`, `inbox_since`, `query_succeeded` and
`source_ref`. A successful check must cover that subscription, occur after
the actual submitted path, occur after that intent and on the same date in the
recorded check timezone. The check history survives later refreshes. Widening
equivalent campaign refs for the same physical funnel does not erase a valid
check with the original campaign attribution.
While the submission day is open, a missing first check keeps 05 pending.
Afterward, record terminal `same_day_check_missed`; never resubmit to repair
that gap. Unknown expectations close as `email_expectation_undetermined` after
a successful attributable check and remain explicitly unknown. Required mail
continues pending until the observed `wait_until`, or the existing 14-day
Lifecycle Capture observation boundary when no delivery time was observed.
Closing missing mail requires a fresh successful query at or after that
boundary and records `expected_email_not_received` or
`confirmation_unverified`, never an observed final result. Explicit false/false
expectations still need a check and record `reviewed_no_expected_email`.

## Evidence, proof and publication

Evidence schema 2 rows: `campaign`, `landing_page`, `funnel_walk`,
`funnel_pattern`, `coverage`. Campaign and walk refs survive into planner and
report. Private exact approval/contact fields, aliases and email verification
URLs remain runtime; screenshot forms before filling and sanitize any additional
assets before publication. Exact approved names/phones, encoded contact values,
private mail IDs and tokenized verification URLs are removed from public text.
Public business-route query parameters retain their meaning.
Redaction applies to observed prose with whole-value word boundaries; it never
substring-rewrites IDs, row types, destinations, hashes or asset paths. Ordinary
`/activate` or `/confirm` business routes remain intact outside mail context.
If a pinned reference or source filename actually contains a known research
email/phone, use a safely named capture/public reference before publication;
validation rejects it rather than silently changing the bound provenance.

Campaign `observation_status` describes native activity. `dated_refs` preserve
native delivery intervals and `running_refs` preserve current scoped observations;
these are independent facts, not proof of business performance. Comparability
uses the assigned evidence scope, not an indirect-fallback threshold or copying
permission. Missing dates or activity stay unknown.

Patterns are scoped by country/channel and distinguish funnel types, structural
features and 04 category-angle → observed-funnel links. Each campaign votes
once. `known_campaigns_total` excludes undetermined observations;
`unknown_campaigns` and `selected_campaigns_total` remain visible. Extra paths
and creatives do not inflate shares or convergence. `observed_convergence`
counts competitors where the feature was seen; `dated_convergence` counts
those whose observed campaigns also expose native delivery dates. Own and mismatched-market observations
are excluded. Teaser is not final result; optional popups do not set main-flow
automatic advance; partial length does not prove short/full length.

Publication pins source files and screenshot hashes in `inputs.source_files`
and the receipt. `inputs.resume_inputs` hashes stable upstream/context inputs;
mutable observation/journal files are pinned separately to avoid circular
hashes. Changes invalidate dependent evidence, without repeating submissions.
All selected paths need observation to a permitted boundary or an explicit
per-campaign gap. Queued work, approval, email, budget and unknown submission
outcomes remain pending; an account boundary can be published as limited
observation and resumed after access is supplied.
