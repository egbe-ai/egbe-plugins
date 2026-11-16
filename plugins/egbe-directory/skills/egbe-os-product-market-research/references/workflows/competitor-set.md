# Competitor Set

Read `../contracts/research-artifacts.md`. This section uses NO OS Research
job: the bundled deterministic runner discovers candidates from measured
sources, you enrich and tier them in four bounded files, and the runner
validates the files, checks who buys ads, composes the list and renders the
section plus a machine-readable evidence file. Do not write or edit section
prose, tables, or the evidence file by hand. The caller supplies the comparison scope and criteria. Choose this operation
when the assignment needs a sourced, bounded comparison sample.

Source the offer identity carefully: a product page can live on the domain of a
different product. Provider domain-wide traffic must not be attributed to a
seller or a small feature merely because they share a host.

## 1. Inputs

Use explicit CLI inputs or optional typed
`egbe-docs/research/market/intake.json` (`--intake` selects another path). The agent
can write or edit that JSON directly from the relevant evidence; there is no
required intake interview, separate offer file or prose-heading parser. Include
only fields useful to the assignment:

- the offer card: job (the pain it solves), buyer, offer class (what kind of
  purchase it is) and the classes that count as comparable, duration, price
  (`price_usd`, the cost to the result), the comparable price floor
  (`price_floor_usd`, only when supplied; descriptive, not an eligibility gate) and 1-3
  category phrases a buyer would search. Three is this adapter's paid-query
  ceiling, not an evidence-sufficiency rule;
- `operator_named`: competitors the caller named (explicit scope: always
  profiled, always kept in the final list, the only seeds of alternatives
  queries);
- `page_mentioned`: competitors the product page mentions (comparison tables,
  "vs" sections). They are ordinary candidates: no bonus, no default tier,
  never a query seed;
- `product_domain` (excluded from the candidates, never a search seed),
  `markets` (country codes, primary first), and explicit `languages` or
  `market_languages` when needed by later selected operations;
- `ltv_usd`, with explicit `ltv_provenance` (`given`, `estimated` or `unknown`)
  and `ltv_basis` when relevant. An absent source is unknown, not an estimate.

For example, a selected comparison can use:

```json
{
  "schema_version": 1,
  "offer": {
    "job": "Run remote workshops", "buyer": "Facilitators",
    "offer_class": "Whiteboard software", "category_phrases": ["online whiteboard"],
    "confirmed_by_operator": true, "basis": "Founder confirmed the current offer in this task."
  },
  "operator_named": [], "operator_named_asked": true,
  "page_mentioned": ["comparison.example"],
  "markets": ["US", "GB"], "languages": ["en"],
  "market_languages": {"US": ["en", "es"]}
}
```

An empty named list with `operator_named_asked: true` means explicitly none;
omitted/false means unknown. Mark an offer `confirmed_by_operator` only from
actual confirmation, or `inferred: true` for an explicit inference, retaining
the supporting `basis`. Without a basis neither status is established. Do not
infer these labels from prose or invent an offer/amount to fill optional fields.
The validator checks supplied types and conflicts before any provider call.

Flags override the intake for manual runs: `--domains` (competitors named by the founder),
`--page-domains`, `--seed-keywords` (category phrases), `--price-floor-usd`,
`--product-domain`, `--country`. Domains from a completed Keyword Economics
section join as ordinary candidates. Without category phrases and without
competitors named by the founder the runner stops rather than inventing a market.
Pass `--context-file` only for relevant provider-safe background beyond these
inputs. The operation freezes effective inputs in `work/competitor_set/inputs.json`
before collection and records their hash. Resume uses the same input; changing
the question or collection inputs requires separately scoped work under another
research ID, not an automatic paid rerun. The local `--max-competitors` output
limit may change without recollecting. A clone retains the frozen inputs even
when an original external source path is unavailable.

## 2. Round 1: discovery from the offer

From the workspace root, resolve `<skill-root>` to the extracted directory
containing this skill's `SKILL.md`, then run:

```bash
python3 <skill-root>/scripts/run-competitor-set.py --workspace .
```

The runner needs `OS_API_KEY` (and optional `OS_URL`). It runs, each with its
own budget:

- Google results, paid and organic (DataForSEO `serp`), for every category
  phrase and its "best" list: who pays for and ranks on the offer's own
  search, and the listicle pages that compare such offers;
- SpyFu's keyword ad history for every category phrase: the domains that
  bought Google ads on it within the last 12 months (older advertisers do not
  count);
- Brave web search for the same queries as a second engine;
- "<brand> alternatives" for up to three competitors named by the founder.

There is no keyword-overlap or PPC lookup in this round: relationships come
from confirmed competitors in round 2. Review and listing directories are
recorded, never promoted; listicle pages are recorded for reading.

The run exits with code 2 and writes
`egbe-docs/research/market/work/competitor_set/candidates.json`: the pool with its
sources and signal strength, `profile_required.round1`, `listicles_to_read`
and `missing` (what the runner still needs). Each candidate carries up to
three `pages` where it ranked or advertised: start profiling there, because
a reseller's or a host's page shows what the domain really sells.

A seller's own subdomain on a course or creator host (thinkific.com,
teachable.com, kajabi.com, substack.com and the like) is a candidate of its
own, named by that subdomain, never the host. When the seller also has its
own site, profile that domain with `found_in` and fold the subdomain into it
with `same_as`. Such a subdomain is never a round-2 seed, and the ad check
does not read the host's Google spend as the seller's.

- The profiling list holds every named and page-mentioned competitor, then
  every domain worth profiling, up to 25: the ones that pay on Google for the
  offer's own search (paid results or SpyFu ad history) first, then the
  strongest of the rest. Worth profiling means it ranks or pays on Google for
  a category query, or shows up in two independent places
  (two queries, two engines, an advertised phrase plus a listicle, two
  listicle pages). A single second-engine result, a single advertised phrase
  or a single listicle mention is a weak hit. Signals are counted per query
  and engine, never per result row, so a site with many pages gets no extra
  weight. A domain you decide `excluded` costs no profile and frees its place
  for the next one, so rerun after excluding the obvious non-competitors.
- The reading list holds up to 12 listicle pages, "best" lists first, at most
  two pages per site, never a site's own search results.

Candidates outside the profiling list are recorded with the reason they were
not profiled.

## 3. Enrich: listicles, profiles, decisions, review

Write four files next to `candidates.json`. Keep the work bounded: the pages
listed, up to three pages per profiled site (home, offer, pricing), the
profiling list, at most 5 domains of your own (a domain round 2 also
records is a discovery, even with `found_in`). Profile in parallel batches
when your environment can run sub-agents, and decide obvious non-competitors
(publishers, job boards, Q&A sites, cloud vendors without paid training)
`excluded` without a profile: that frees their place on the list. These file formats are needed only by this chosen collection adapter, not by every research assignment. Review is optional.

**`listicles.json`.** Read every page in `listicles_to_read` (and only those)
and record each program it lists:

```json
{"schema_version": 1, "read_on": "2026-10-06", "pages": [
  {"url": "<address from listicles_to_read>", "status": "read", "entries": [
    {"name": "Program or product", "domain": "seller.com", "offer": "...", "format": "...", "price_text": "...", "duration": "...", "audience": "..."}]},
  {"url": "<address>", "status": "unreadable", "reason": "HTTP 404"}]}
```

A listed domain no source recorded joins the pool with provenance
`agent_research` and the page as `found_in`; a domain on two or more pages
joins the profiling list on the next run.

**`profiles.json`.** Profile every domain on the profiling list, and any
other domain you want to propose, on its own site: what it sells for this
job, in which format, at which price, to whom, and whether it still sells:

```json
{"schema_version": 1, "profiled_on": "2026-10-06", "profiles": [
  {"domain": "seller.com", "name": "Seller", "operating": true,
   "offer": "Closest offer to ours", "offer_url": "https://seller.com/program",
   "offer_class": "live online cohort", "offer_match": "same",
   "price_text": "$2,200 one-time", "price_usd": 2200, "duration": "8 weeks",
   "buyer": "...", "same_buyer": true, "job": "...", "same_job": true,
   "marketplace": false, "focused": true, "main_business": "...", "markets": "US, EU",
   "evidence_urls": ["https://seller.com/program", "https://seller.com/pricing"],
   "found_in": null}]}
```

- `offer_match`: `same` (our offer class), `comparable` (one of the classes
  the offer card lists as comparable), `different`, or `none` (nothing for
  this job).
- `price_usd` is the cost to the result: a one-time price, or a subscription
  times the time it takes to finish; `null` when the price is not public.
- `evidence_urls` are the pages you read (at least one).
- `focused: false` when the offer is a side line of a big multi-product
  domain (a university, a large platform, a company that sells mostly
  something else); such a domain is never a round-2 seed, and its ad check
  counts only ads on the offer's own phrases. Leave it out or `true` when
  the domain is mainly about offers like this one.
- `found_in` is required for a domain no source recorded: the page where you
  found it (a listicle, a marketplace listing, a search result). These
  additions carry provenance `agent_research`, never `operator_named`. Never
  pass them with `--domains`.
- Marketplaces: a marketplace whose catalog for this job is offers of our
  class for our buyer, and which buys traffic for them, is one competitor
  (its domain), profiled like any other. A seller on it with its own site and
  its own advertising is a separate candidate. That the product itself is
  also sold there is never a reason to exclude it. A marketplace of a
  different class (cheap self-paced video, for example) is profiled by its
  typical offer.

**`decisions.json`** (schema version 2). One decision per profiled or listed
domain:

```json
{"schema_version": 2, "decided_on": "2026-10-06", "decisions": [
  {"domain": "seller.com", "name": "Seller", "competitor_tier": "direct", "reason": "Same buyer, same job, same format and price band."},
  {"domain": "library.example", "competitor_tier": "indirect", "reason": "Self-paced subscription for the same buyer."}]}
```

Use `direct`, `indirect`, `substitute` or `excluded` for the caller's
comparison roles and explain the role using sourced profile facts. No fixed
buyer/job/price formula overrides that judgment. Substitutes may be relevant
when the question asks about alternatives; low price is an observation, not an
automatic exclusion. Explicit exclusions need a reason; named domains still
need a profile so the exclusion is inspectable.

A second domain of the same offer (a redirect, an academy domain, a
university brand on a program a partner runs and sells elsewhere) is folded
into the canonical one with `"same_as": "canonical.com"` on an `excluded`
decision: its discovery facts, ads on the offer's phrases included, count for
the canonical domain, and one program never takes two places in the list.

**Optional `review.json`.** Record an additional review if it is useful for the
assignment. It does not gate the operation or require a separate agent. Retain
the checked domains, objections and resolutions when provided:

```json
{"schema_version": 1, "rounds": [
  {"reviewer": "separate agent", "reviewed_on": "2026-10-06",
   "discovery_round": 1, "checked": ["seller.com", "library.example"],
   "objections": [{"domain": "library.example", "objection": "...", "resolution": "accepted", "note": "..."}],
   "missing": [{"domain": "rival.com", "why": "...", "resolution": "added", "note": "..."}]}]}
```

Resolve every objection (`accepted` or `rejected`; a rejection needs a note)
and every missing rival (`added` means profiled and decided; `rejected` needs
a note), then rerun the same command.

## 4. Round 2: relationships of the confirmed direct competitors

When round 1 is complete, the runner takes up to three confirmed direct
competitors whose domain is focused on such offers (those named by the founder first,
then those that advertise on the offer's phrases), tops them up with comparable indirect ones when there are
fewer, and runs the DataForSEO keyword-overlap report and SpyFu's PPC
competitors for each. A stable-domain sample of new related domains forms
`profile_required.round2` (up to 10); single hits are eligible. Record sourced
profiles and decisions for the chosen sample, or explicit exclusions for
out-of-scope hits. There is no third automatic collection round and no mandatory
review gate.

## 5. Ad check, composition and publication

With everything decided, the runner checks every domain that can enter the
list (up to 25): the round-1 ad facts (Google ads on the offer's phrases,
paid results on its queries), SpyFu's modeled Google spend over six months in
the primary market and, when it shows none, up to two more target markets,
ad pixels on the home page (a free fetch) and, when nothing on Google shows,
the official Meta Ad Library for EU delivery. Each competitor gets
`ads_seen`, `pixels_only`, `unknown` (the lookups failed) or
`none_detected`. For an offer that is a side line of a multi-product domain
(`focused: false`) only the ads on the offer's own phrases count, and
without them the verdict is `unknown`: the domain's overall spend, pixels and
Meta ads promote the rest of its business. Channel Footprint measures the
channels in depth later; these observations do not choose the sample or a business priority.

The output preserves explicitly named scope, then takes a stable-domain sample
of caller-classified non-excluded candidates. Direct, indirect and substitute
roles remain visible. Ad activity, modeled spend and price do not determine
which business opportunity is best. The `rank` field records this
inspection order.

Up to `--max-competitors` (default 10); a shorter list stays short. The
runner then:

- writes evidence rows to `egbe-docs/research/market/evidence/competitors.json`:
  every competitor with its provenance (`operator_named`, `product_page`,
  `discovered`, `keyword_economics` or `agent_research` with the page),
  offer, format, price against the floor, ad activity with its facts and why
  it is in the list; every other candidate with the reason it is not;
- materializes the exact section under `## Competitor set` in
  `egbe-docs/research/market/full-report.md`;
- verifies the report and evidence together; Git remains caller-owned;
- records the completed state receipt under
  `egbe-docs/research/market/work/competitor_set/`, with the hashes of the intake and the
  provided enrichment files.

Rerunning with the same files replays the cache and changes nothing.

## 6. Known limits and failure handling

Discovery covers the primary market; the ad check looks at up to two more
target markets. SpyFu covers Google search only, and the Meta check sees EU
delivery only: an advertiser that runs Meta outside the EU and no Google ads
shows as `pixels_only` at best. A provider failure on the core Google results
stops the attempt with the query that failed and the budget already spent;
rerunning continues from the cache. A query the provider rejects is cached
as unavailable and never retried unchanged; it is reported in
`rejected_calls`, apart from the answered calls in `provider_calls`. SpyFu,
Brave and the Meta check are best effort: an unavailable provider is
recorded and the run continues, but exhausting any per-attempt budget stops
the attempt so the next one resumes. When no discovery query answered at
all, the attempt stops `failed`: an unsearched market never becomes a
completed section. A `decisions.json` with schema version 1 is rejected: it
predates these rules, so profile and decide again.
