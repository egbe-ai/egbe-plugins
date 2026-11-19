# Communities Analysis

The founder-facing name of this section is "Communities analysis"; its stable
catalog ID remains `community_demand`.

Read `../contracts/research-artifacts.md`. This section uses NO OS Research
job and no free-form web research: the bundled deterministic runner searches
Hacker News (keyless Algolia API), fresh Reddit (a pinned Apify actor,
posts and comments from the last 12 months), and YouTube comments under
the top videos per query (OS `/tools/youtube`; best-effort — a provider
failure is recorded as an excluded source, never a dead section) for
public demand language — payment mentions, tool-seeking asks, pain
descriptions, price-sensitivity language — and renders the section body
plus a machine-readable evidence file itself. Do not write or edit section
prose, tables, or the evidence file by hand.

## 1. Inputs

Search queries come from two places, merged in this order:

- `--seed-keywords "phrase one, phrase two"` — up to 5 phrases selected for
  the assignment, considering the category noun phrase
  (e.g. `ai whiteboard`, `virtual staging`) AND the problem phrasing
  without the category word (e.g. `brainstorm remotely with clients`) where useful —
  community demand is often written in problem language that category
  queries never match. Lowercase, no boolean operators, no brand names of
  the founder's own product. Stay within the assigned question and market.
- `--product-context "ai, agent"` — explicitly supplied mechanism tokens relevant
  to the comparison. Pass these when the distinction matters: quotes that
  mention these tokens are flagged as speaking to this product's mechanics;
  all other quotes are bare category demand that may belong to different
  mechanics (a request for human-to-human realtime collaboration is not
  evidence for an AI-agent product even when both say the category word).
- The top validated keywords discovered by a completed Keyword Economics
  run (its receipt-validated evidence file) fill any remaining query slots
  automatically — auction-validated category heads make good community
  queries (near-duplicate keyword variants are folded by token-set
  identity).

At most 5 queries per run (`--max-queries`); each costs one Reddit actor
run, two free HN calls, and up to three best-effort YouTube calls, and the
list is trimmed to fit `--max-actor-runs` (default 6).

## 2. Run the deterministic runner

From the workspace root, resolve `<skill-root>` to the extracted directory
containing this skill's `SKILL.md`, then run:

```bash
python3 <skill-root>/scripts/run-community-demand.py --workspace . \
  --seed-keywords "<category phrase>, <problem phrase>" \
  --product-context "<mechanism tokens>"
```

The runner needs `OS_API_KEY` (and optional `OS_URL`) in the environment.
Per query it searches HN stories and comments, Reddit posts and comments,
and YouTube comments, marker-matches every text against a fixed versioned
regex list (payment / seeking / pain / price-sensitivity language), and:

- writes quote and community rows to
  `egbe-docs/research/market/evidence/community-demand.json`;
- materializes the exact section under `## Communities analysis` in
  `egbe-docs/research/market/full-report.md`;
- verifies the report and evidence together; Git remains caller-owned;
- records the completed state receipt under
  `egbe-docs/research/market/work/community_demand/`.

Every provider response is cached in the runtime directory, so re-running
the same command replays cached data instead of spending actor runs again.

## 3. Known limits and failure handling

Marker matching is a deterministic heuristic: it misses paraphrased demand
and admits some noise, and category counts measure marker density, not
verified intent. The runner deterministically excludes seller posts
(Show HN/Launch HN stories, self-promo Reddit posts), jobs-thread comments
and classified-style listings, and bot accounts; a marker counts only near
a non-generic query token (long off-topic rants that mention the category
once do not qualify), and money mentions count as payment language only
near a payment word ($100M scale-talk is not a price). Price-sensitivity
counts remain source observations, without an automatic evidence-strength score. Communities over-represent complainers and early
adopters; a community absent from the table is weak evidence, not proof of
no demand. Product Hunt (its API cannot keyword-search launches), Arctic
Shift (historical Reddit), and Stack Exchange are deliberately excluded
and recorded as excluded_source rows; YouTube degrades to an
excluded_source row when its provider is unavailable. The community table is ordered by name and retains raw counts, dates, votes and
sample links. Stored quotes use a recent-first bounded sample with per-community
caps; this is collection coverage, not a ranking of business opportunity.
Interpret these observations for the caller's question.

If the runner reports no queries, supply `--seed-keywords` from the assignment
and relevant evidence. If no suitable category or problem phrase is known,
record the section as could-not-complete with that reason
instead of inventing queries. For any other failure, preserve the runtime
state and stop; a later attempt resumes from cache. Do not substitute
Brave search, generic OS Research, direct provider access, or an
agent-written result, and do not edit `egbe-docs/research/market/full-report.md` or
the evidence file manually. Completion is validated deterministically from
the runtime receipt; this section has no LLM-based Research Completion
Review step.
