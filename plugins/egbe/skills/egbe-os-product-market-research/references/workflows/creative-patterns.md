# Creative Patterns

Internal competitor research section: what competitors advertise,
where, in which form, and which comparable selling messages they keep using.
Longevity, active delivery, variants and library reach show observed use; they do
not establish conversion performance. Use it when the bounded assignment needs
creative evidence; the user need not name its internal catalog ID.

## Inputs and collection

Use the completed Competitor Set and Channel Footprint, retaining competitor tiers,
observed channels, source ad IDs, relevance decisions, markets and evidence-policy
hashes. Relevance uses the optional typed offer and explicitly selected
provider-safe `--context-file` text frozen by the shared input helper, not an
automatic scan of project files. Accepted languages come from explicit flags or
typed `intake.json` fields `languages` and `market_languages`; no headings or
country names imply a language. `--languages` overrides the typed global list
and suppresses typed per-market overrides unless `--market-languages` is also
supplied. Otherwise explicit per-market flags override the typed mapping.
Native dates and activity keep their source scope; the runner does not classify
creative success from age or recent sightings.

```bash
python3 scripts/run-creative-patterns.py \
  --workspace . \
  --product-domain product.com
```

The runner needs `OS_API_KEY` and optionally `OS_URL`. Read its `--help` for
attempt limits, section limits, accepted-language and video-cap options. Reuse
compatible Channel Footprint observations first, then enrich them through the
source that supports each assigned channel.
Maintain explicit channel × competitor × market coverage, including channels
without a collector. `no_data`, unavailable media, unsupported source, unknown
format, sample limits and `budget_deferred` remain distinct outcomes. A tracking
tag or traffic estimate alone does not become an observed creative.

`--max-channels N` limits the deep work to the express scope: in each market,
a stable-name sample of N observed comparable channels per market. This is
an execution bound, not a recommendation. Other cells get a
`not_deepened` coverage row; the evidence records `deepened_cells`. 0 (the
default) deepens every cell.

Keep strict advertiser identity. Destination plus advertiser identity can verify
the competitor; third-party advertisers pointing to its site remain excluded and
reported. A legal-entity match needs the source's supported identity evidence.
Do not treat affiliate creatives as the competitor's direct advertising.

Each native ad ID is an independent creative. Repeated observations of that ID
retain provenance and market scope, while different IDs with identical copy or
different images remain separate. Dynamic/carousel assets retain their actual
cards, texts and media associations; never synthesize a cartesian set of variants.
Similar-copy and media relationships describe variations without merging ads or
borrowing the oldest variant's serving history.

Download available images and video immediately after collection. Signed URLs
may expire; content hashes and local cached files preserve evidence for retries.
Do not silently convert a media download failure into a successful visual analysis.

## Video and classification

YouTube creatives resolve the native video ID from the Transparency creative
page when possible, then use YouTube metadata and available captions. Meta video
files can supply preview frames and extracted audio. Detailed analysis defaults
to five unique videos per competitor in each channel × market, with a configurable
cap. The cap limits detailed video analysis, not the number of collected ads.

Use captions first and OS `/v1/media/transcribe` for uncaptained speech when that
capability is configured. Supply extracted audio bytes and their hash; do not
send an arbitrary remote URL to the transcription endpoint. Send frames and
available transcript to `/v1/media/analyze`. Record the opening hook, visible
text, visible speaker treatment, visual approach and their frame/transcript
references. Missing captions, speech capability, video files or frames remain
explicit gaps. Official EU Meta rows with no assets can support their observed
text and scoped reach, not a visual format inferred from another market's ad.

Restore native text, legible OCR and available speech before judging relevance.
Relevance compares buyer, job and offer with the researched product; a shared
brand or keyword is insufficient. Unknown means unresolved, not irrelevant.
Retain previously grounded Footprint decisions; a grounded new disagreement
keeps both decisions and the supporting excerpt. Foreign-language exclusions
follow the intake policy for that ad's market.

Classify every relevant ad in the collected sample within the section budget;
there is no twelve-ad competitor/platform cap. The bounded collection interleaves observed groups before deepening one
large group; this is coverage sampling, not a recommendation ranking. Unknown relevance can be resolved through classification but does
not enter relevant tops or convergence until resolved. Unknown format remains
unknown. A missing URL does not establish a landing type or conversion path.

`POST /v1/media/classify-creative` retains `creative-taxonomy.v1` and adds optional
`semantic_context` under `creative-semantics.v1`. The generic taxonomy stays
category-independent. `scripts/creative-semantics.py` builds and validates the
full context and accepted languages. Compatible cutoffs reuse a frozen base
context; validated cached and earlier-batch meanings anchor subsequent requests.
The per-ad cache binds that base, market-language policy and full source/media
hashes; each batch receipt additionally binds its actual request-anchor hash. The classifier returns full available verbatim
`observed_text` with extraction provenance and category semantics:

- relevance and language with supporting ad excerpts;
- category angles on buyer/context, job, mechanism, outcome, proof, price/terms
  and action, with concrete meanings drawn from the offer and competitor text;
- a canonical message-family meaning with buyer, job, offer/mechanism, outcome
  and conversion details, plus a verbatim example.

Reuse known canonical meanings across batches only when they match. The helper
freezes angle/family IDs and dictionary hashes from validated observations,
retains their supporting ad IDs, and reports unclassified IDs as incomplete
dictionary discovery. Families group selling meaning, not exact headline text.
Generic labels such as “desired outcome” do not constitute a semantic family.
Different offers, guarantees, audiences or conversion paths remain distinguishable.
Stack names, cohorts and course duration are possible category data, not universal
requirements. SaaS and consumer-product categories use the same contract.

## Evidence, patterns and report

Retain native duration, source scope and date basis. Capture/listing history
is not serving duration; missing activity is not stopped activity. Compute
patterns within market, channel, creative type and format. Counts describe
distinct observed competitors, not successful campaigns; preserve direct/indirect
roles, relevance, language and source-member lineage. Active/stopped/unknown
statuses describe provider observations and do not predict performance.

The report has two views:

1. Market → channel → creative type → competitor, up to three examples in each
   cell. Show complete available ad text, image or video preview, confirmed age
   and its basis, running status, library link, market scope and media gaps.
   Types are text, static image and video; carousel/dynamic format stays noted
   within static image when supported by source evidence. Unknown format/type
   stays visible. Same-text ads with different images can occupy separate slots.
2. Patterns by channel, type and format within each market, including description,
   semantic families, angles, observed recurrence, dated competitors and concrete ads.
   A top channel with no extractable creatives states the reason explicitly.

The published inspection sample uses stable creative IDs within each cell;
it does not select winners from age, variants or source availability. Compare
reach only within compatible market/source scope when the assignment calls for it.

Show all observed prices, financing, discounts, guarantees and outcome/salary
promises per competitor, using whole sentences and source links. Preserve the
original image alongside OCR text where applicable. Label competitor promises
as information, not verified claims that a proposed campaign may repeat.
UI limits may paginate or expand details but must not discard promises silently.

Keep observed landing URLs. Funnel Teardown may later add a validated conversion
path (webinar, quiz, call, checkout, etc.); this section does not launch section 05.
The evidence index and downstream consumers retain creative/classification pairs, market scope,
dictionary meanings and exact `source_ad_ref` lineage. Verify actual Meta and
YouTube references through the consumers, not only platform-name presence.

## Cache, budgets and completion

The first attempt fixes the cutoff in `as-of.json`. Retries replay that cutoff's
raw provider responses and shared content cache; `--refresh` starts a new cutoff
after completion. Snapshots retain native identity and observation provenance.
Compatible source responses can survive changes to semantic policy, while
derived labels depend on full offer context, accepted languages, taxonomy,
semantic context/dictionary, policy and media hashes.

Detailed video analysis defaults to five unique videos per competitor/channel/
market. The cumulative ceiling defaults to 240 paid starts; classification and
media-call attempt limits default to 40 and 100. These are resource counts, not
a monetary estimate; actual provider tariffs determine cost. The rich semantic
classifier batches up to four ads and separates long text/speech into smaller
requests. Public input text bounds remain explicit coverage gaps when exceeded;
complete native text stays in the corpus and report.

Separate per-attempt limits from a persisted cumulative section ceiling. On a
ceiling, save the partial result, consumed resources and remaining tasks as
`budget_deferred`; a rerun cannot reset cumulative spend. Downloaded assets,
classification answers and unique video analyses are cached by their content.
Account refusals, exhausted upstream budgets and unavailable required endpoints
stop dependent paid calls; invalid batch answers get bounded retries and a
visible gap. Cached replays incur no new charge.

Legacy merged evidence cannot recover vanished visual variants. Rebuild from
compatible raw provider caches where available; otherwise mark legacy coverage
explicitly and collect missing raw evidence within budget. Do not relabel the
single merged row as a recovered set of independent ads.

On completion, the runner writes evidence to
`egbe-docs/research/market/evidence/creative-patterns.json`, materializes
`## Creative patterns` in `egbe-docs/research/market/full-report.md`, and records the receipt
under `egbe-docs/research/market/work/creative_patterns/`. Materialization verifies
local files; the caller owns their normal Git workflow. Hash-verified
previews are copied to `egbe-docs/research/market/assets/creative-patterns/` and
published with the Markdown; report refs resolve inside the project repository.
Partial
evidence remains distinguishable from complete coverage of the collected sample.

Preview publication covers two sets of creative rows:

1. The canonical top selection below, which the report shows.
2. Every citable original creative row, selected or not: it is
   relevant, its language is allowed (`language_status: allowed` and
   `language_allowed: true`), and it
   belongs to a researched market × channel cell (its country is one of the
   evidence `target_countries` and its channel is known).
   `creative-selection.py` `citable()` owns this rule, so a cited original
   never stays under the private runtime cache.

Each row publishes its image or video-preview assets, or else its first key
frame. The copy uses the same checks for both sets: the source must be inside
the workspace, 5 MiB or less, and match its recorded hash, and its bytes must
be JPEG, PNG or WebP. The file is named by its SHA-256. The evidence asset
then points at the `egbe-docs/` asset path and keeps the cache path as `source_path`.
A failed copy marks the asset `publication_status: unavailable` and adds a
`preview_publication` `media_gap` coverage row with the creative ID; the
section is then partial. Only collected public ad-library media is copied.
Rows outside both sets, such as irrelevant,
excluded-language or out-of-market rows, keep their cache paths. Rows are visited in evidence order and files are
content-addressed, so a replay produces the same evidence bytes.


## Published inspection sample for Funnel Teardown

The canonical selector in `scripts/creative-selection.py` owns the existing
three-example resource-bounded inspection sample and stable ID order. The report and
preview publication use that same choice; publication also covers the
citable rows described above. The runner publishes
`egbe-docs/research/market/evidence/creative-selection.v1.json` and embeds the same
manifest in evidence v2 as `selection`. Its cells and flattened
`selected_creatives` preserve market/channel/type/competitor, rank, landing
URL and source ad lineage. Source hashes pin the corpus, classifications,
angle dictionary, policy, input scope and completed competitor/channel files.
Both the evidence inputs and receipt pin its path and byte hash. Downstream
Funnel Teardown consumes these concrete selected IDs; it does not reconstruct
the choice from Markdown or introduce another ranking.
