# Research Artifact Contract

Resolve every path from the current workspace root.

The paths below use the default research ID `market`. Before independent work,
choose a stable slug and set `EGBE_RESEARCH_ID` for every runner and downstream
consumer; substitute that ID in the documented paths. Resume with the same ID.
Do not change it between sections or reuse it for a different study. Keep public
outputs and versioned `work/` state together under `egbe-docs/research/<research-id>/`.
For substantial research, keep its question, relevant context/evidence, gaps,
requested result and constraints in `egbe-docs/research/<research-id>/brief.md`.
A narrow operation can use an existing task record or explicit CLI inputs;
neither a new document nor fixed Markdown headings are execution prerequisites.

`--context-file` selects optional provider-safe additional context. Only this
explicit content and the operation's declared upstream evidence may enter the
provider request; unrelated project files and personal details are not inputs.
The shared IO helper freezes selected text and source hashes in
`work/<section-id>/input-context.json` before collection. Receipts bind it as
`research_context: {path, sha256}`. Resume uses the saved snapshot, not a fresh
search for context. A changed source can limit applicability without corrupting
the saved result or authorizing a new paid run; retain both evidence and receipts.
Narrative continuation also verifies and reuses the saved assignment, query,
system prompt and `input-provenance.json`; its receipt binds the latter with
`input_provenance_sha256`. Updated installed prompts or upstream evidence do not
replace an in-flight request. Missing or damaged saved inputs stop continuation
before provider calls, rather than resetting the request.

The table describes supported outputs, not a package required for every task.
A bounded research operation needs only its own output and recovery evidence.
Recommendation/preview/synthesis/render artifacts belong only to a requested
publication. A Product handoff reuses relevant existing findings, sources,
coverage and unresolved questions; it does not require that publication package.

## Canonical Artifacts

| Artifact | Path | Required title |
| --- | --- | --- |
| Recommendation selection | `egbe-docs/research/market/pre-prd-recommendations.md` | YAML contract with `explanation_format: plain_text`, followed by one short plain-text explanation |
| Incremental full report | `egbe-docs/research/market/full-report.md` | `# Market Research Report` |
| Founder preview | `egbe-docs/research/market/preview.md` | `# Market Research: Findings and Recommendations` |
| Preview synthesis | `egbe-docs/research/market/preview-synthesis.json` | Strict schema version 1 JSON |
| Founder summary | `egbe-docs/research/market/summary.md` | Deterministic compact Markdown projection |
| Preview render receipt | `egbe-docs/research/market/preview-render.json` | Strict schema version 1 JSON |
| Keyword economics evidence | `egbe-docs/research/market/evidence/keyword-economics.json` | Schema version 2 aggregate; typed rows carry `locale_key` and `locale` |
| Competitor set evidence | `egbe-docs/research/market/evidence/competitors.json` | Strict schema version 1 JSON |
| Channel footprint evidence | `egbe-docs/research/market/evidence/channel-footprint.json` | Strict schema version 1 JSON |
| Creative patterns evidence | `egbe-docs/research/market/evidence/creative-patterns.json` | Strict schema version 1 JSON |
| Funnel teardown evidence | `egbe-docs/research/market/evidence/funnel-teardown.json` | Strict schema version 1 JSON |
| Lifecycle capture evidence | `egbe-docs/research/market/evidence/lifecycle-capture.json` | Strict schema version 1 JSON |
| Competitor ads evidence | `egbe-docs/research/market/evidence/competitor-ads.json` | Strict schema version 1 JSON |
| Competitor reviews evidence | `egbe-docs/research/market/evidence/review-mining.json` | Strict schema version 1 JSON |
| Communities analysis evidence | `egbe-docs/research/market/evidence/community-demand.json` | Strict schema version 1 JSON |
| Fleet benchmarks evidence | `egbe-docs/research/market/evidence/fleet-prior.json` | Strict schema version 1 JSON |
| Geography comparison analysis | `egbe-docs/research/market/evidence/geography-comparison.json` | Agent-authored schema version 1 comparison; not provider measurements |

The recommendation, synthesis, summary, render receipt, and evidence files are
machine-facing support artifacts. The full report and preview are durable
founder documents.

Section evidence files under `egbe-docs/research/market/evidence/` carry the
machine-readable rows behind a deterministic section: typed entries (keyword
metrics, SERP observations, competitor domains, budget simulations) each with
provenance and an evidence-tier marker. They are written only by the owning
section runner, verified together with the
report section they back, and consumed by downstream hypothesis tooling.
Narrative workflows must not edit them.

Geography Comparison is a separate analysis artifact, not one of those measured
datasets. `scripts/geography-comparison.py` prepares validated prior inputs and
publishes its structured comparison and exact report section together. Its
`request.json` binds context, source inputs and published files. It has no OS
Research job ID or Completion Review. Structural completion can include an
explicit `not_compared` scope decision or an uncertain comparison; consumers
must preserve that distinction, not call either a validated market winner.

The Preview workflow also reads the execution state at
`egbe-docs/research/market/work/preview-context.json`. It is the authoritative selected and
research outcomes projected by the runtime. It is versioned and must
not be rewritten by the workflow. Its ordered section IDs
and canonical labels are the immutable execution-plan snapshot; a newer skill
catalog must not expand work that is already running.
For standalone work, `scripts/build-preview-context.py` is the producer: it
freezes explicit selection and derives completion from receipts. See
`../workflows/local-research.md`; do not hand-author completed statuses.
Section entries contain `id`, `label`, `status`, optional verified `coverage`,
and `closed_by_caller: true` only for an explicit `--failed` decision.
`partial` and `no_data` are distinct outcomes, not manual closures. Their Preview
meaning and evidence use are defined in `../workflows/preview.md`.

## Section Isolation

Use the exact H2 from `references/catalog.v1.json`. A section workflow owns only
that H2 and its body. It must not create, rewrite, or remove another section.

Run `scripts/upsert-markdown-section.py` from this skill bundle to create or
replace the owned section. The helper preserves all other report content and
keeps repeated execution idempotent. Supply non-empty content and never edit
the report with an unconstrained whole-file rewrite.

From the workspace root, invoke it as:

```bash
python <skill-root>/scripts/upsert-markdown-section.py \
  --report egbe-docs/research/market/full-report.md \
  --heading "<exact catalog heading>" \
  --content "<non-empty section content>"
```

Resolve `<skill-root>` to the extracted directory containing this skill's
`SKILL.md`. For multiline future content, pass `--content-file` instead of
`--content`.

Market Size And Dynamics, Target Audience, Competitive Landscape, Value
Proposition, Pricing And Monetization, Acquisition Channels, Demand Validation,
and Unit Economics write cited research through their section runners. Organic
Trend Watch delegates provider work and analysis to the dedicated
`egbe-os-organic-trend-watch` skill while retaining this bundle's report ownership.
Keyword Economics writes its section and evidence file exclusively through
`scripts/run-keyword-economics.py`: the runner calls metered OS DataForSEO
tools, renders deterministic tables, caches every upstream response under
`egbe-docs/research/market/work/keyword_economics/`, and persists the report and evidence
in one verified publication. Its completion proof is the runtime state receipt
(`request.json` with result and evidence SHA-256 hashes); it has no LLM-based
Research Completion Review.
Competitor Set (catalog ID `competitor_set`, internal) follows the same
deterministic contract through `scripts/run-competitor-set.py`: inputs from
optional typed `egbe-docs/research/market/intake.json` or explicit CLI inputs
(the supplied offer and distinct founder-named/page-mentioned competitors),
candidate discovery from the offer via OS tools
(DataForSEO Google results, SpyFu keyword ad history) and OS search, then the
keyword overlap and SpyFu PPC competitors of the confirmed direct
competitors, an ad check (SpyFu domain stats, home-page ad pixels, the
official Meta Ad Library), the executing agent's listicle reading, profiles,
classification decisions and optional review recorded in
`egbe-docs/research/market/work/competitor_set/` (`listicles.json`, `profiles.json`,
`decisions.json`, `review.json`), cache and receipts in the same directory,
evidence at `egbe-docs/research/market/evidence/competitors.json`, one verified publication,
and no Research Completion Review. Until the files cover every domain the
runner asks for the receipt stays `pending`, never `completed`.
Channel Footprint (catalog ID `channel_footprint`, internal) follows the
same deterministic contract through `scripts/run-channel-footprint.py`:
tracking tags fetched from competitor pages and tag-manager containers,
ad-library presence via OS scrape actors and the official Meta Ad Library
endpoint, SpyFu's modeled Google Ads spend via OS tools, the public
traffic-source split, web search partner signals and Wayback Machine page
history, cache and receipts under
`egbe-docs/research/market/work/channel_footprint/`, evidence at
`egbe-docs/research/market/evidence/channel-footprint.json`, one verified publication, and
no Research Completion Review. Its v2 evidence preserves competitor tiers,
normalized advertisements, per-country observations, native delivery date
scope, sampling limits, coverage and effective shared policy with its hash.
The agent supplies hashed relevance decisions for the collected candidates;
missing decisions leave the attempt pending. Finalization validates these
decisions before materializing the report and evidence. Explicit unknown
relevance remains a limitation, never program-level proof. Pixel-only or
undated channels remain candidates independently of campaign proof.
It takes its competitor domains and tier provenance from the Competitor Set
and Keyword Economics evidence files like the Ads runner.
Creative Patterns (catalog ID `creative_patterns`, internal) follows
the same deterministic contract through `scripts/run-creative-patterns.py`:
a creative corpus from OS scrape actors, the official Meta Ad Library
endpoint and SpyFu ad history, classification through OS
`/v1/media/classify-creative` against `references/config/creative-taxonomy.v1.json`,
cache, the fixed cutoff (`as-of.json`) and receipts under
`egbe-docs/research/market/work/creative_patterns/`, evidence at
`egbe-docs/research/market/evidence/creative-patterns.json`, one verified publication, and
no Research Completion Review. When completed Channel Footprint v2 is
available, reuse its relevant ad corpus and per-country observations,
validate its receipt and shared policy, and retain member-level lineage in
creative and pattern evidence. A stale/pending v2 input is not silently
replaced by global scraping. Legacy standalone collection remains unscoped
and cannot acquire country-specific eligibility without the channel gate.
It takes its competitor domains from the Competitor Set and Keyword
Economics evidence files like the Ads runner.
Competitor Ads follows the same deterministic contract through
`scripts/run-competitor-ads.py`: ad-transparency data via OS scrape actors
plus the official Meta Ad Library endpoint, cache and receipts under
`egbe-docs/research/market/work/competitor_ads/`, evidence at
`egbe-docs/research/market/evidence/competitor-ads.json`, one verified publication, and no
Research Completion Review. It consumes the Competitor Set evidence file
(caller-classified competitors, in stable inspection order) and the Keyword Economics evidence file
(discovered competitor domains) as optional inputs, never the accumulated full
report.
Competitor Reviews follows the same contract through
`scripts/run-review-mining.py`: G2 and Trustpilot review pulls via OS scrape
actors, cache and receipts under `egbe-docs/research/market/work/review_mining/`,
evidence at `egbe-docs/research/market/evidence/review-mining.json`, one verified
publication, no Research Completion Review, and the same receipt-validated
Competitor Set and Keyword Economics domain inputs.
Communities Analysis (catalog ID `community_demand`) follows the same contract through
`scripts/run-community-demand.py`: Hacker News via the keyless Algolia
API, fresh Reddit via an OS scrape actor, and best-effort YouTube comments
via OS tools, cache and receipts under
`egbe-docs/research/market/work/community_demand/`, evidence at
`egbe-docs/research/market/evidence/community-demand.json`, one verified publication, no
Research Completion Review. Its queries come from `--seed-keywords` (seed-
derived category AND problem phrases, per its workflow) merged with the
receipt-validated Keyword Economics keyword rows when that section has
completed; `--product-context` mechanism tokens flag which quotes speak to
this product's mechanics rather than the bare category.

Funnel Teardown (catalog ID `funnel_teardown`, internal) publishes through
`scripts/run-funnel-teardown.py`. Its v2 inputs are the completed 03 country/channel
proof, completed 04 creative corpus and the shared
`egbe-docs/research/market/evidence/creative-selection.v1.json` manifest. The runner prepares
all distinct selected campaign destinations and finalizes local browser observations;
it does not replace missing ad destinations with competitor homepages. Verified ad
CTA/history enrichment has its own lineage and pinned runtime record. Country and
channel belong to the campaign; a geolocation or language redirect is an observed
mismatch, not new market proof.

The executing agent records phone-viewport screenshots and main/auxiliary branches
in `egbe-docs/research/market/work/funnel_teardown/walks.json`, following
`references/contracts/funnel-teardown.md` and the shared `walk-mechanics.v2.json`.
`research-context.json` records the explicit buyer persona and own-product URLs.
`approval-plan.json`, `approvals.json` and `submissions.json` bind exact forms/data to
human chat authorization and submission intent/outcome. New fields require a
supplement; an unknown submission outcome must be checked before retrying.
The shared private `egbe-docs/research/market/work/identity-registry.json` allocates stable aliases;
`lifecycle-handoff.json` transfers approved submissions to 02, whose funnel-mail mode
captures same-day confirmations/results without claiming lifecycle completion.
Public evidence redacts private contacts and email verification links.

The evidence at `egbe-docs/research/market/evidence/funnel-teardown.json` contains linked
campaign, landing, path, pattern and coverage rows plus screenshot references/hashes.
Its receipt pins upstream receipts/evidence, selection, policy, persona, enrichment,
walks, approval/submission journals, email events and assets. Pending approval/email,
budget checkpoints and uncertain submissions remain `pending`. Permitted account,
CAPTCHA, SMS, payment and live-call boundaries can be published with explicit unknown
downstream. Own-product paths never submit and never enter competitor proof/counts.
Legacy v1 walks remain diagnostic context and require fresh collection for proof.
Advertising duration, native activity and observed recurrence are separate
measurements; none establishes conversion, profitability or permission to copy.

Lifecycle Capture (catalog ID `lifecycle_capture`, internal) follows
the same deterministic contract through `scripts/run-lifecycle-capture.py`:
research subscriptions at the competitors with plus-addressed aliases of
the claw mailbox, selected from early reviewed public entry discovery and
completed by the assigned human with verified access to the planned aliases and
mailbox, recorded by the executing agent in
`egbe-docs/research/market/work/lifecycle_capture/subscriptions.json`, the inbox read
through the OS mail routes by alias and start date, cache and receipts under
`egbe-docs/research/market/work/lifecycle_capture/`,
evidence at `egbe-docs/research/market/evidence/lifecycle-capture.json`, one verified
publication, and no Research Completion Review. It takes its competitor domains
from the Competitor Set and Keyword Economics evidence files like the Ads
runner. Until every competitor is subscribed or skipped with a reason the
start receipt stays `pending`; already recorded subscriptions may be harvested
explicitly while others await the assigned human. Day-3 partial and day-14 full
windows retain publication status `completed`, with separate observation and
coverage metadata. Later harvests replace current evidence and preserve
immutable private snapshots. The
sign-up policy of its workflow and exact human-approved Funnel Teardown
forms are the permitted research submissions on competitor sites.
Read [the Lifecycle Capture contract](lifecycle-capture.md) for discovery,
stable mailbox-wide allocation and human signup milestones. The caller supplies
scheduling and bounded reminders; scheduler ids stay outside domain artifacts.
Ordinary message bodies and campaign material remain in the versioned cache,
not in public reports. Before its first cache write, the runner separates
access-bearing links and credentials into
`egbe-docs/research/market/.local/lifecycle_capture/mail-cache/` and stores a
sanitized response in `work/`. Analysis and resume use that portable response;
authorized confirmation actions may use the local original. Live credentials
are not transferable through Git, and public-report scrubbing is not a
substitute for this cache boundary.

Keyword Economics is optional for these three runners, and Competitor Set is
optional for the Ads and Reviews runners: absent, failed, incomplete or
invalid evidence is omitted, with a warning and the reason in their
`keyword-inputs.json` or `competitor-set-inputs.json`. Explicit
domains/queries still work. Without any usable inputs, the runner stops
rather than treating missing evidence as zero demand.

Fleet Benchmarks follows the same contract through
`scripts/run-fleet-prior.py`: past fleet experiments genuinely comparable
to this product via the OS GTM knowledge endpoint `POST /gtm/comparables`
(the whole verified/directional pool reviewed semantically by the OS-side
`gtm-comparables-judge` LLM — the judge runs in the gateway, never in the
runner), cache and receipts under `egbe-docs/research/market/work/fleet_prior/`,
evidence at `egbe-docs/research/market/evidence/fleet-prior.json`, one verified
publication, no Research Completion Review. Cross-niche aggregate channel
benchmarks and fleet-CPC-vs-auction comparisons are intentionally excluded
from this section; an empty comparable result is recorded as a coverage
fact about our own pool, never invented around, and a partial (bounded)
review that returned no match is refused rather than recorded as no-match.

Value Proposition, Pricing And Monetization, Acquisition Channels, and Demand
Validation, and Unit Economics may read only the completed supporting results
declared by their bundled runners. The shared deterministic loader validates
each section-keyed runtime receipt and file hashes, preserves the declared
order, omits missing or invalid results, and never reads this accumulated full
report as provider input.

The same receipt reader supplies bounded structured measurements to AI queries.
Keyword, ad, review and community observations retain locale, source hashes,
retrieval dates, contrary signals and omitted-row counts. Failed/skipped inputs
are explicit limitations. Without
a supplied selection, missing data is unknown, not evidence of absent demand.
`input-provenance.json` records these inputs. Changed measurements affect current
applicability; an explicitly authorized new study incorporates them into its new
query. Continuation retains the original query and inputs. No changed file launches
a paid rerun by itself. Fleet internals are not sent to external research.
The caller owns scheduling from its immutable execution order; the
bundle reports pending measurements without changing that order. Local selection
defers dependent work until selected measurements finish or are closed explicitly.

Organic Trend Watch uses
`egbe-docs/research/market/work/organic_trend_watch/context.json`, built only by
`scripts/build-organic-trend-context.py` for this PMR adapter. Its schema-version-1
manifest requires a scoped `assignment`, contains only explicitly selected
provider-safe context and may contain full validated
results for Target Audience, Competitive Landscape, Value Proposition, and
Acquisition Channels in that fixed order. Missing, skipped, failed, stale, or
tampered supporting results are omitted. The manifest records the relative
source path and SHA-256 for selected inputs and every included result; it never reads
the accumulated full report. The dedicated skill owns the manifest consumer,
provider runtime, analysis, `result.md`, and receipt contracts.

Before report materialization,
`scripts/finalize-organic-trend-watch.py` invokes the validator shipped in the
same downloaded `egbe-os-organic-trend-watch` bundle. Product Market Research does not
duplicate or reinterpret that receipt schema. Only after successful validation
does the finalizer upsert the exact runtime `result.md` under the canonical
Organic Trend Watch H2 and invoke the shared report persistence helper.

After report materialization and persistence succeed, the finalizer atomically
writes the PMR-owned
`egbe-docs/research/market/work/organic_trend_watch/integration-receipt.json`. This stable
boundary binds the opaque dedicated-skill receipt, exact `result.md`, exact
materialized report section, collection epoch and timestamps, coverage/status,
and local publication. It does not require or invent a Git commit SHA.
`partial` and `no_data` remain limited evidence, not completed coverage.
Downstream completion consumers validate this integration receipt
and the published section only; they must not duplicate provider,
normalization, media, or analysis rules owned by `egbe-os-organic-trend-watch`. A failed
validation, materialization, or persistence must not publish the integration
receipt.

## Preview Link

The preview links to `full-report.md` beside it by default; no instance ID or
Dashboard route is needed. Use `--local-report-link` only to override it with a
safe relative link or an explicit HTTP(S) report URL. The render receipt records
local materialization and file hashes, not remote publication or Git proof.

## Preview Assembly

Run `scripts/write-preview.py` to render the Preview and founder summary from
the validated synthesis and runtime context. The workflow owns semantic
synthesis; the writer owns Markdown structure, research coverage, the full
report link, length limits, and render hashes. When no successful section has
created the full report, the writer initializes only its canonical H1 so the
founder still receives an honest failure Preview. Never author the Preview or
chat summary independently.

## Persistence Boundary

Each completed section materializes and verifies its report and evidence in the
selected research folder. Runners do not commit or push: use the product's normal
Git workflow for both outputs and `work/`: scope, decisions, raw provider results,
paid job IDs, receipts and review state must survive handoff. Keep credentials
and process locks out of Git; report exports still exclude internal/private data.
No Git repository is required to collect research. Receipts record
`publication_mode: local` with no invented commit SHA.
AI publication proof remains in the section's `publication.json`; its accepted
completion review is still required. Preserve caches and receipts on retry.

The Competitor Set, Channel Footprint and Creative Patterns runners store each
provider cache entry gzip-compressed as `<digest>.json.gz` and read an older
plain `<digest>.json` as well, so earlier workspaces replay from their cache
with no new provider call. `python3 scripts/research-artifact-io.py --compact
"$WS"` compresses an existing workspace's entries of those sections and
hard-links byte-identical images named by their SHA-256 (cache images and
`egbe-docs/research/market/assets/`); nothing is re-fetched. Public evidence stays
plain JSON for every reader.

The Competitor Set, Channel Footprint, Creative Patterns, Funnel Teardown, Lifecycle Capture, Ads, Reviews, Communities and Fleet runners mark a new attempt `pending`
before input validation or collection, and `failed` on error. They retain cached
responses and collected files for retry, but only successful publication restores
`completed`; a previous result does not prove that the new attempt succeeded.

Recommendation and Preview writers follow the same publication boundary.
Preserve unrelated local changes. Do not create or modify
`egbe-docs/product/prd.md` from this skill.

Provider queries, job metadata, and completed temporary results under
`egbe-docs/research/market/work/` are portable execution state, not founder documents
or public exports. Each OS Research section runner owns its
section-keyed runtime state and reuses a completed matching result before
attempting report materialization again.

## Research Completion Review

After a OS Research runner succeeds, review the cached
`egbe-docs/research/market/work/<section-id>/result.md` before finishing the workflow. Review
only whether the research answer is physically cut off. Ignore the
final `### Sources` appendix added by the runner.

Record exactly one classification with
`scripts/review-research-completion.py`:

- `complete`: the answer ends at a normal semantic boundary;
- `uncertain`: the ending is abrupt or imperfect, but there is no direct proof
  of a physical cutoff;
- `definitely_truncated`: the answer ends mid-word or mid-sentence; leaves an
  open Markdown link, fence, table, or equivalent construct; ends with a
  heading, list marker, or colon without its content; or starts an explicitly
  bounded list and is cut off inside the current item.

Do not classify a response as definitely truncated merely because it is short,
misses a requested section, has weak evidence or sources, violates the desired
format, or ends abruptly after a grammatically complete statement. Those are
content or compliance problems, not proof of transport truncation. Use
`uncertain` when the physical cutoff cannot be proven; uncertainty never starts
another research submission.

For an accepted ending, run one of:

```bash
python <skill-root>/scripts/review-research-completion.py \
  --workspace . \
  --section-id <section-id> \
  --classification complete
```

```bash
python <skill-root>/scripts/review-research-completion.py \
  --workspace . \
  --section-id <section-id> \
  --classification uncertain
```

For definite truncation, supply a literal 12–500 character excerpt from the
last 2,000 characters of the provider answer, before the generated Sources
appendix. Write that excerpt as UTF-8 to
`egbe-docs/research/market/work/<section-id>/truncation-evidence.txt` with the normal file
editing tool; do not interpolate provider text into a shell argument. Then run:

```bash
python <skill-root>/scripts/review-research-completion.py \
  --workspace . \
  --section-id <section-id> \
  --classification definitely_truncated \
  --evidence-file egbe-docs/research/market/work/<section-id>/truncation-evidence.txt
```

On the first definite truncation, the helper archives the rejected job and
result, invalidates its completed cache, and authorizes one fresh request. Run
the same section runner once more, then review and record the replacement
ending. If the replacement is also definitely truncated, invoke the review
helper with its exact tail excerpt; it records retry exhaustion and fails. Do
not start a third request.

The review receipt is runtime state bound to the exact query, system prompt,
request, and result hashes. A missing or stale receipt, or a current
`definitely_truncated` decision, does not qualify as completed supporting
research. The helper enforces state integrity and retry count; it does not make
the classification for the agent.


## Public media for research consumers

Research consumers use current receipt-validated evidence and available public
media. Section 04 Creative Patterns owns creative extraction and its native
`publish_previews` output: public files under
`egbe-docs/research/market/assets/creative-patterns/` and evidence `media_assets` with
their hashes; a published preview is a hard link to its cached bytes when
both sit on one filesystem. These native files do not require a `public_exports` wrapper.
Publication covers the canonical top selection and every creative row a
consumer may cite: relevant, language-allowed, with its country
in the evidence `target_countries` and a known channel. When such a preview
cannot be copied, its asset is marked `publication_status: unavailable` and a
`preview_publication` `media_gap` coverage row names the creative ID.
Section 05 Funnel Teardown owns campaign-linked walks, screen content,
screenshots and their provenance; consume its published native evidence
and declared media when available. Richer sanitized JSON may optionally be
declared by an evidence document as `public_exports`:

```json
{
  "public_exports": [
    {"path": "egbe-docs/research/market/creative-media/export.json", "sha256": "<file SHA-256>", "kind": "creative_media"}
  ]
}
```

This is an optional consumer boundary, not an assertion that every producer
already emits this field and not a new collection algorithm. The owning
section prepares sanitized JSON and local assets. Consumers use available
native evidence/media and declared exports; missing extraction stays a visible
gap. Work needed to supply missing creative or funnel material belongs to
sections 04/05, not to a report presentation step.
Export paths are workspace-relative under `egbe-docs/`,
resolve within it and cannot point into `cache`, `caches`, `snapshots` or
private runtime. The exact JSON SHA-256 is bound through the evidence and
its completed receipt. Declare updated hashes when content changes.

An export object may contain `rows` (preserving each row's type), `creatives`
(default type `creative`), `funnels`/`walks` (`funnel_walk`), `sequences`
(`lifecycle_sequence`) and `gaps` (`extraction_gap`). Keep complete fields,
including stable IDs, full text, reasons/priority from the founder, channel,
competitor/domain, format/funnel type, target market or EU-proxy scope,
observation/verification status and source URLs (`link`, `landing_url`,
`address`). A funnel has an ordered `screens` array of full screen records,
with copy, screenshots and walk/source links. Local public media is declared
in `media` or `assets` as `{role, path, sha256}`. Convenient `image_path`,
`asset_path`, `preview_path`, `screenshot_path`, `keyframe_path` fields and
matching `*_sha256` may identify the corresponding media. Use public
workspace-relative paths with exact hashes; source URLs do not replace local
media dependencies.

Record extraction gaps explicitly with `domain`, `channel`, `status` and
`reason`/`detail`, or per-record `extraction_status` and `extraction_reason`.
Missing pictures/screens stay gaps; presentation must not invent replacements.
Keep lifecycle exports to sanitized public sequence observations and dates.
Never export mailbox addresses, aliases, raw email bodies, private signup
plans, credentials or snapshots. No runtime directory is copied wholesale
into a shared report or ZIP. Existing section collection and publication
ownership remains unchanged.
