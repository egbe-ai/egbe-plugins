# Competitor Reviews

Read `../contracts/research-artifacts.md`. This section uses NO OS Research
job and no free-form web research: the bundled deterministic runner collects
customer reviews of the market's competitors from G2 and Trustpilot and
renders the section body plus a machine-readable evidence file itself. Do
not write or edit section prose, tables, or the evidence file by hand.

## 1. Inputs

Competitor domains come from completed sections automatically (their
receipt-validated evidence files), exactly like Competitor Ads: first the
tiered Competitor Set in stable inspection order, then the Keyword Economics demand
surface. When neither section has run or they missed a competitor the
founder named, pass domains explicitly:

- `--domains "competitor.com, other.io"` — merged ahead of discovered ones;
  a domain the Competitor Set recorded as excluded is never refilled from
  Keyword Economics automatically; naming it here is the founder's override;
- at most 3 competitors per run (`--max-competitors`; each one costs four
  actor runs — two platforms × lowest-rated + top-rated pulls — and the list
  is trimmed to fit `--max-actor-runs`);
- `--g2-slugs "competitor.com=their-g2-slug"` — only when a competitor's G2
  slug differs from its brand token (the runner guesses `clickup` from
  `clickup.com` by default and EXCLUDES the platform when the slug resolves
  to a different product).

## 2. Run the deterministic runner

From the workspace root, resolve `<skill-root>` to the extracted directory
containing this skill's `SKILL.md`, then run:

```bash
python3 <skill-root>/scripts/run-review-mining.py --workspace .
```

The runner needs `OS_API_KEY` (and optional `OS_URL`) in the environment.
Per competitor it pulls the lowest-rated reviews (paying customers with
unmet needs — offer wedges) and the top-rated reviews (the language of
value) from each platform, keeps the platform-recorded analysis fields (G2
company-segment/industry codes, hate/love themes, switched-from and reason;
Trustpilot verification, country, company replies), counts billing/pricing
complaints deterministically, and:

- writes review rows to `egbe-docs/research/market/evidence/review-mining.json`;
- materializes the exact section under `## Competitor reviews` in
  `egbe-docs/research/market/full-report.md`;
- verifies the report and evidence together; Git remains caller-owned;
- records the completed state receipt under
  `egbe-docs/research/market/work/review_mining/`.

Every provider response is cached in the runtime directory, so re-running
the same command replays cached data instead of spending actor runs again.

## 3. Known limits and failure handling

G2 is slug-keyed: when the guessed slug resolves to a different product, the
platform is excluded from analysis and listed in the section — supply the
correct slug via `--g2-slugs` and re-run rather than hand-patching data.
Trustpilot is domain-keyed. Review volumes are biased toward products that
actively solicit reviews; an empty platform for a small competitor is weak
evidence, not proof of absence. Synthesis into wedge hypotheses is a
downstream concern — this section reports only platform-recorded data.

If the runner reports no competitor domains: pass `--domains` with
competitors supplied for the assignment when they exist; when the workspace has
neither a completed Keyword Economics run nor any named competitor, record
the section as could-not-complete with that reason instead of retrying (the
recommendations writer prevents this case for recommended scopes by
co-recommending Keyword Economics automatically). For any other failure,
preserve the runtime state and stop; a later attempt resumes from cache. Do
not substitute Brave search, generic OS Research, direct provider access, or
an agent-written result, and do not edit `egbe-docs/research/market/full-report.md` or
the evidence file manually. Completion is validated deterministically from
the runtime receipt; this section has no LLM-based Research Completion
Review step.
