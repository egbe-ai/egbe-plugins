# Channel Footprint

Read `../contracts/research-artifacts.md`. This internal section owns its
collection, normalized evidence and rendered prose. Do not manually edit those
outputs. The agent does write product relevance decisions in the separate
staged input described below; it does not invent provider facts.

## Inputs and planning

Use completed Competitor Set roles and their decision provenance. Explicit
or Keyword Economics domains without a role remain `unknown`, not direct.
Keep direct, indirect and unknown comparability roles separate in summaries;
these roles do not confer business priority or exclude assigned observations. Pass `--domains` to add domains and
`--product-domain` to exclude the product's own site.

Supply target countries with `--countries US,GB,DE` (alias `--target-countries`)
or `--country` for one country. Explicit flags take precedence over the optional
typed `intake.json` `markets` list; no geography is parsed from prose. Check every
country; UK becomes GB and EU/EEA requires an explicit list. The adapter's US
fallback is not a market choice. `--eu-country` does not replace target markets.
Supply optional provider-safe background through `--context-file`; relevance uses
that frozen text and the explicitly supplied typed offer, not unrelated files.

The runner records `egbe-docs/research/market/work/channel_footprint/collection-plan.json`
before collection: scoped checks, a bounded sample expansion and a cumulative paid-start limit. Domain tags, traffic,
history and undated libraries are queried once. Country-filterable libraries
are checked per country; unsupported countries get explicit coverage gaps.
Prices are shown only when known (otherwise `money_estimate: null`). The plan counts three partner searches per country, both Meta methods in supported EU countries, and a separate bounded retry reserve.

## Staged collection and product relevance

Resolve `<pmr>` to the extracted Product Market Research bundle. Set
`OS_API_KEY` and optionally `OS_URL` for collection. The caller owns Git publication.

```bash
python3 <pmr>/scripts/run-channel-footprint.py --workspace "$WS" \
  --product-domain product.com --countries US,GB --stage collect
```

Collection preserves the provider cache, `egbe-docs/research/market/work/channel_footprint/collected.json`
and `relevance-candidates.json`. The candidates contain the selected research/offer
context, competitor decisions and unique normalized ads with native IDs,
text, landing and source URLs, image/video URLs and observations. Inspect the
ad text and landing offer together with the buyer and task in the context.
If a landing page is available, use its content and record its URL as a
reasoning reference. A keyword match alone is not product relevance.

Write `egbe-docs/research/market/work/channel_footprint/relevance-decisions.json`:

```json
{
  "schema_version": 1,
  "product_context_sha256": "<copy from candidates>",
  "decisions": [
    {
      "ad_id": "<canonical ad_id>",
      "candidate_sha256": "<copy from this candidate>",
      "relevance": "relevant",
      "reason": "Comparable offer, buyer and job; the landing offer and copy show why.",
      "evidence_refs": ["<landing URL>", "<source URL or ad_id:ad_text>"]
    }
  ]
}
```

`--relevance-by-model` writes these decisions itself for every pending ad
with text or a downloadable image: the creative classifier
(`POST /v1/media/classify-creative`) judges the ad against the offer card and
returns relevant, irrelevant or unknown with its reason and a verbatim
excerpt, recorded as `decided_by: model`. The runner then collects again
(a decided sample may expand once) and leaves only ads with neither text nor
image pending for you.

Allowed decisions: `relevant`, `irrelevant`, `unknown`. Every decision needs a
reason and an `evidence_refs` array. Relevant/irrelevant decisions need at
least one reference. Use unknown when evidence is insufficient; it cannot
establish product comparability. Irrelevant ads stay in the corpus for
audit, never in product conclusions. Decisions are reused only for identical
candidate and product/intake context hashes. Native-ID deduplication merges
Meta actor/API observations and multi-country sightings; equal copy without
a native ID does not imply continuous delivery.

Run collect again with the same arguments. It reuses cached direct checks,
validates their decisions and expands a capped sample once if it contains
no comparable ads. All assigned competitor roles are collected; no direct-count
threshold decides whether an indirect competitor may be inspected. Review any new
candidates and repeat until collection is complete. The expansion can fill
an empty field (an image, text or URL) of an ad you already decided; collect
then lists that ad in `pending_ad_ids` again with a new `candidate_sha256`,
so decide it again. A collected expansion stays in later collects even if
that review finds the ad relevant. A source without
pagination uses one configured increased limit; expansion never grows
without a bound.

```bash
python3 <pmr>/scripts/run-channel-footprint.py --workspace "$WS" \
  --product-domain product.com --countries US,GB --stage finalize
```

Finalize is offline and uses collected data; it never starts providers or
needs `OS_API_KEY`. Missing/stale decisions do not produce a completed receipt.
Exit 2 and `awaiting_relevance`, `awaiting_collection` or `awaiting_finalize`
identify the next required step. Explicit unknown decisions allow completion
with clearly recorded gaps. Default `--stage all` collects and completes only
when the current decision set and collection are ready. Pixel-only/free-only
runs with no ads require no relevance decisions.

## Evidence and meaning

Evidence v2 is `egbe-docs/research/market/evidence/channel-footprint.json`; the
receipt remains schema 1 and binds output, effective policy, current intake,
Competitor Set and relevance decisions. It contains `channel_ad` corpus,
`library_presence` aggregates, `channel_country`, direct `channel_observation`, tags,
modeled traffic/spend, partner/history measurements and coverage. The renderer
preserves the direct matrix, separate indirect/unclassified tables, country
observations, source samples, measurements and explicit coverage statuses.

The observation contract and its hash travel with evidence and receipts.
Native dates, scoped served duration and days since last delivery remain
measurements. Only explicit native status establishes observed activity;
a recent last-seen date is not an active flag. A confirmed past delivery end
wins over an active flag except the documented provider capture-day grace.
Global ad-level dates never become country delivery dates merely because the
query supplied a country. Durations are bounded by capture and never add
separate runs together. No duration proves profitability or channel success.

Native placement, not VIDEO/IMAGE format, is required to assert YouTube or
Display delivery. LinkedIn listing sightings and Reddit creation dates cannot
supply served duration. Repeated dated sightings are repeated presence
only. Reddit Inspiration cannot verify current campaigns, even at zero.
Source capabilities and native scope constraints live in the sources config.
Additional platforms need verified source/signature support; never invent an
OpenAI Ads pixel signature or unseen advertising data.

Channel summaries report distinct observed competitors and preserve evidence
kinds: pixel, listing, native activity, modeled traffic/spend and partner signal.
They do not rank channel merit or decide campaign eligibility. Direct, indirect
and unknown denominators stay separate. Missing values remain unknown, not zero.
The project assignment/method interprets these observations.

## Budgets, samples and failures

Per-attempt defaults remain 12 actors, 10 official Meta calls, 30 searches,
12 SpyFu lookups, 40 page fetches and 25 CDX calls. Attempt exhaustion stops
and cached answers resume on rerun. `--max-total-paid-starts` additionally
bounds metered actor, Meta, web-search and SpyFu starts across attempts in a durable `budget.json`,
including failures and retries. Restarting does not raise the stored cap.
Legacy actor start journals are counted when the budget ledger is created.
Cumulative exhaustion preserves collected data and marks remaining checks
`budget_deferred`; no silent proxy or limitless rerun spending.

Sampling records request limits, raw rows before identity/relevance,
matched/unique ads and unknown completeness/pagination. At the cap show
`≥N` for the raw sample only; comparable/active subsets are found counts,
never total lower bounds. Duration is the maximum observed native duration
in this sample with its actual scope, not a campaign's full lifetime.

Core Google/Meta provider failures stop with their subject; supplementary
failures retain other observations and apply the existing source breaker.
Cached input rejections do not re-spend. An unreachable gateway stops rather
than claiming missing evidence. Free HTTP failures are not valid observations.
Coverage distinguishes no matches, not checked, not verifiable, unsupported
market, budget deferred and source unavailable; none means absent advertising.
