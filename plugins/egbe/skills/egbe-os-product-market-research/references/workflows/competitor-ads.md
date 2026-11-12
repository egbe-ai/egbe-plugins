# Competitor Ads

Read `../contracts/research-artifacts.md`. This section uses NO OS Research
job and no free-form web research: the bundled deterministic runner collects
ad-transparency data (Google Ads Transparency and the Meta Ads Library) for
the market's competitors and renders the section body plus a machine-readable
evidence file itself. Do not write or edit section prose, tables, or the
evidence file by hand.

## 1. Inputs

Competitor domains come from completed sections automatically: first the
tiered Competitor Set (`egbe-docs/research/market/evidence/competitors.json`, in
stable inspection order), then the Keyword Economics evidence file
(`egbe-docs/research/market/evidence/keyword-economics.json`, the best
`competitor_domain` rows discovered on the demand surface). When neither
section has run (or they missed a competitor the founder named), pass
domains explicitly from the assignment — founder-named competitors first:

- `--domains "competitor.com, other.io"` — merged ahead of discovered ones;
  a domain the Competitor Set recorded as excluded is never refilled from
  Keyword Economics automatically; naming it here is the founder's override;
- at most 3 competitors are examined per run (`--max-competitors`; each one
  costs two actor runs, and the list is trimmed to fit `--max-actor-runs`).

If the founder stated a launch geography inside the EU, pass the matching
`--eu-country` ISO code (default `DE`) so official Meta EU delivery data
matches the intended market.

## 2. Run the deterministic runner

From the workspace root, resolve `<skill-root>` to the extracted directory
containing this skill's `SKILL.md`, then run:

```bash
python3 <skill-root>/scripts/run-competitor-ads.py \
  --workspace . \
  --eu-country DE
```

The runner needs `OS_API_KEY` (and optional `OS_URL`) in the environment.
Per competitor it runs one Google Ads Transparency actor run and one Meta
Ads Library actor run through OS scrape (each actor run places a temporary
wallet hold), plus one official Meta Ad Library search (EU delivery data).
It preserves native ad duration, advertiser observation spans and price
mentions without interpreting them as profitable campaigns, and:

- writes evidence rows to `egbe-docs/research/market/evidence/competitor-ads.json`;
- materializes the exact section under `## Competitor ads` in
  `egbe-docs/research/market/full-report.md`;
- verifies the report and evidence together; Git remains caller-owned;
- records the completed state receipt under
  `egbe-docs/research/market/work/competitor_ads/`.

Every provider response is cached in the runtime directory, so re-running the
same command replays cached data instead of spending actor runs again.

## 3. Known limits and failure handling

Identity is destination-verified: Google ads are collected by the domain
their ads point to (advertiser legal names — e.g. ClickUp advertising as
"Mango Technologies, Inc." — are found automatically), and Meta ads count
only when their landing destination resolves to the target domain or the
page name is an exact brand match. Same-name lookalikes are excluded from
the scoped sample and listed separately — never hand-patch them back in.
A presence span may include gaps and creative rotation. An empty sample means
no matches in the reviewed scope, not absent advertising or absent demand.

If the runner reports no competitor domains: pass `--domains` with
competitors supplied for the assignment when they exist. When the workspace has
neither a completed Keyword Economics run nor any named competitor, this
section is not executable — record it as could-not-complete with that reason
instead of retrying or inventing a competitor. For any other failure,
preserve the runtime state and stop;
a later attempt resumes from cache. Do not substitute Brave search, generic
OS Research, direct provider access, or an agent-written result, and do not
edit `egbe-docs/research/market/full-report.md` or the evidence file manually.
Completion is validated deterministically from the runtime receipt; this
section has no LLM-based Research Completion Review step.

The exported observation contract/hash preserves identity and provenance; it
contains no duration-to-success threshold or country eligibility decision.
