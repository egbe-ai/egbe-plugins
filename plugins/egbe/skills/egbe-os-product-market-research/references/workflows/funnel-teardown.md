# Funnel Teardown

Internal section 05 inspects the creative sample selected in 04. Its unit is
creative + channel + market + verified destination + observed buyer path.
Never run a separate weight ranking or use accessible homepages to fill
unknown ad destinations. Every distinct selected funnel is investigated;
unfinished work is resumed, not silently capped.

## 1. Prepare the inputs

Require completed current 01/03/04 publications and the canonical 04
`creative-selection.v1.json` manifest. Use buyer/offer-card context from 01,
explicit own destination URLs from intake/product context and the shared
research mailbox identity registry. Keep concrete product routes, persona names
and mailbox values in runtime, not in this skill.

Write `egbe-docs/research/market/work/funnel_teardown/research-context.json`, for example:

```json
{
  "persona": {"id": "buyer", "name": "Sam Researcher", "buyer_context": "The agreed buyer and offer card"},
  "own_destinations": [{"url": "https://product.example/start", "country": "US"}],
  "mailbox": "research@example.org"
}
```

```bash
BUNDLE=/path/to/product-market-research
WS=/path/to/product-workspace
python3 "$BUNDLE/scripts/run-funnel-teardown.py" --workspace "$WS" --phase prepare
```

Prepare is deterministic and makes no provider calls or plain fetches. It pins
04, policy, manifest and context, writes `candidates.json`, allocates stable
per-funnel aliases under the shared registry lock, creates empty private form
journals and exits 2. Missing persona/own destinations remain explicit pending
inputs; the runner does not infer `/backend` or a competitor's generic page.
The campaign cutoff is inherited from 04 and does not advance with browser or
email observation time.

For selected creatives missing destination, perform a bounded source lookup:
open the native ad and its visible CTA or read native destination metadata;
use Google/SpyFu ad-history rows attributable to that selected ad. Follow the assigned
scope and preserve channel/market identity. Record attempts,
source availability and candidate URLs in `destinations.json`; promote only a
verified ad-to-URL relation under the contract. YouTube description and LinkedIn
site links remain candidates until that relation is established. If bounded
lookup fails, keep `destination_unknown` with the actual reason and source refs.
Reprepare after enrichment; enrichment may fill URLs, not change the selected
campaigns or their upstream sample.

## 2. Scout, list forms and obtain human confirmation

Open entries in a real browser at 390×844 without sending contact forms.
Identify the main CTA implied by the creative and scout available steps. Capture
real screenshots and page content, including lower-page proof/price blocks.
Keep consent and optional discount popups separate from the main route.
Preserve HTTP(S) ad entries and record an observed redirect chain when the
browser opens another URL; a redirect is not permission to merge destinations.

Prepare one combined list of known forms with exact fields, data, aliases,
competitor/campaign/funnel/path, purpose and screenshot reference. Populate
`approval-plan.json` following the v2 contract. Present that concrete list to
the founder and wait for actual confirmation. Record the human chat reference
and exact fingerprints in `approvals.json`. A JSON file you wrote is not human
confirmation. New forms, fields or data require a supplement and new approval.

A caller that sends no forms skips the list and
the approval: each walk captures the first contact screen with its fields and
stops there as `boundary` / `form_not_submitted`. Nothing is submitted, so no
mail check follows.

## 3. Walk deeply and preserve progress

The bundled driver keeps one mobile Chrome (390×844) open for the whole walk
and records each screen where the report can publish it:

```bash
python3 "$BUNDLE/scripts/walk-funnels.py" serve --workspace "$WS" &
python3 "$BUNDLE/scripts/walk-funnels.py" call open '{"funnel_id": "<id>", "url": "<address>"}'
python3 "$BUNDLE/scripts/walk-funnels.py" call screen '{"funnel_id": "<id>", "screen_id": "s01-landing", "kind": "landing", "slices": 2,
  "fields": {"headline": "...", "cta": "...", "offer": "...", "amounts": [], "notes": "..."}}'
python3 "$BUNDLE/scripts/walk-funnels.py" call click '{"funnel_id": "<id>", "text": "Get started"}'
python3 "$BUNDLE/scripts/walk-funnels.py" call finish '{"funnel_id": "<id>", "status": "boundary", "stop_reason": "form_not_submitted", "unknown": ["..."]}'
python3 "$BUNDLE/scripts/walk-funnels.py" build --workspace "$WS"
```

Every answer returns the page's text, inputs and buttons for the next
decision. Screenshots land under `egbe-docs/research/market/assets/funnel-teardown/`,
records under the runtime's `records/`; `build` writes `walks.json` from them.

Read [`funnel-teardown.md`](../contracts/funnel-teardown.md) and the shared
mechanics JSON. Answer as the agreed buyer; record the actual answers per screen
and visible branch points. Investigate additional relevant paths only where the
offer, final result, price or conversion changes. Capture screenshots of every
logical screen, not fabricated placeholders. One real immediate gate is valid.
Review every screenshot for visible contact values, personalized names/phones
and private verification URLs. Capture before filling where possible. If a
later screen echoes private data, keep the original in private runtime and
declare a real privacy-redacted display derivative with source hash and
derivation; never treat a file hash as pixel sanitization or invent an observed
screen. Include lower-page captures in the same privacy review.

Before sending an approved lead/quiz/webinar form, append a submission intent.
Then submit exactly the approved data and record the browser response. Continue
after contact requests. If a crash leaves outcome unknown, inspect existing
state before any retry; preserve uncertainty until resolved. Resume must never
re-register automatically or allocate another alias for that funnel.
Keep all prior form revisions, approvals and submission events append-only.
An observed failed attempt needs a new human approval before a retry.

Complete permitted registrations and quizzes. Stop before creating an account,
payment/card entry, CAPTCHA/bot verification, required SMS, or booking a live
sales rep. Record account gate as `needs_account`; continue only after the
authorized account holder supplies access, recorded with a human chat reference.
A fictional full US phone ending 555-0100–0199 is used only if approved and
accepted; otherwise record a phone block. Own destinations
are walked under the same contract, with no sending or booking.

After 40 captured screens in an attempt, save a budget checkpoint and resume
under a new attempt ID. Persist full `walks.json` paths and journals. Do not
reinterpret a checkpoint or the contact screen as the funnel's terminal outcome.
Unknown, absent and not applicable differ; a teaser role/result example does
not count as the final personalized quiz result.

Read confirmation/result email through 02's same-day handoff, using the same
alias and funnel/campaign refs. Confirmation links can be followed only within
the approved registration's purpose. Do not expose private tokenized email URLs.
A received mail is a separate evidence event, not a website screenshot. Mail
waiting and terminal coverage gaps do not change the advertising cutoff or
the observed browser result.
Record `email_expectations` on the submitted path: `confirmation` and `result`
are true, false or unknown, with an actual `browser:<screen_id>` source for
known expectations. Finalize once to write the private handoff, then run:

```bash
python3 "$BUNDLE/scripts/run-lifecycle-capture.py" --workspace "$WS" --funnel-mail --refresh
```

Each new approved registration needs a successful attributable inbox check
after its latest submission on the same recorded local day. An earlier cached
snapshot does not satisfy it. Received confirmation is not confirmed; unknown
expectations remain visible as unknown. A successful attributable query closes
unknown expectations as `email_expectation_undetermined`. If the submission day
has already passed without its first check, record `same_day_check_missed`;
do not repeat the submission. Expected mail remains pending until its observed
`email_expectations.wait_until` (aware timestamp with the browser promise
source), otherwise the existing 14-day Lifecycle Capture boundary. Refresh the
inbox at that boundary before recording missing mail as a terminal coverage
gap. This does not complete an unseen final result or confirmation. Explicit
no-email expectations still require the inbox check and then record that review.

## 4. Validate and finalize

```bash
python3 "$BUNDLE/scripts/run-funnel-teardown.py" --workspace "$WS" --phase finalize
```

The runner validates hashes, mobile observations, exact approvals/data, intent
and outcome ordering, permitted boundaries, own no-submit, persona paths and
market scope. Queue/budget/approval/email/uncertain-submit states exit 2 and
retain all progress. A generic shortfall sentence cannot waive missing selected
paths. Legacy v1 is reported explicitly and requires fresh browser evidence.

Evidence v2 contains campaign lineage, browser page/screens, per-path walks,
country/channel patterns and specific coverage. Native delivery durations and
observed current activity remain separate; neither is a success verdict or a
copy recommendation. Shares count unique campaigns with known features and
show unknown counts; recurrence counts competitors, never paths. Own observations
and market mismatches remain visible but do not enter competitor aggregates.

The report renders both A (selected creative → campaign → every observed screen)
and B (per-channel/market funnel types, structure and category-angle links),
with screenshots, reached outcomes, boundaries, gaps and own comparison.
The runner writes the canonical evidence and report, pins all used sources and
assets, and persists the docs publication only when no active research remains.
Managed publication uses the established docs persistence; local workspaces
remain local. When sharing research, include its declared public assets and
preserve source references and gaps.

Replicate the observed structure and conversion sequence, never competitor
copy, claims or numbers. Advertising persistence does not establish measured
conversion or causal effectiveness. Borrowing another channel's structure must
be explicit in the planner and cannot prove a destination in the target channel.
