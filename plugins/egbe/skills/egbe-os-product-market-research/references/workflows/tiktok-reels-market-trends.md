# TikTok/Reels Market Trend Research

Read `../contracts/research-artifacts.md`. Resolve `<pmr-skill-root>` to the
installed directory containing this workflow and the Product Market Research
`SKILL.md`.

1. State the scoped research question from this study. Build provider-safe context
   from it, explicitly selected context (optional `--context-file`) and any
   validated supporting sections:

```bash
python3 <pmr-skill-root>/scripts/build-organic-trend-context.py --workspace . \
  --assignment "The specific question this study should answer"
```

2. Use the installed Egbe OS `egbe-os-organic-trend-watch` skill. Read its `SKILL.md`
   and the collection/analysis workflow it names. The skill also supports direct
   use; PMR sections are optional evidence, not prerequisites.
3. Execute only that workflow against
   `egbe-docs/research/market/work/organic_trend_watch/context.json`. The dedicated skill
   owns provider selection, collection, resumability, analysis, `result.md`,
   and its completion receipt. Do not replace its workflow with manual web
   research or author its runtime result outside its contracts.
4. After it seals a complete, partial or no-data result, delegate validation to the
   same installed skill and materialize its result through Product Market
   Research:

```bash
python3 <pmr-skill-root>/scripts/finalize-organic-trend-watch.py \
  --workspace . \
  --organic-skill-root <organic-skill-root>
```

The finalizer invokes the dedicated skill's authoritative runtime validator
before it reads the result. It then upserts only
`## TikTok/Reels market trend research for this product` into the canonical
full report and persists that report through the product repository
boundary. It writes the PMR-owned `integration-receipt.json` after successful
materialization and persistence, preserving coverage rather than upgrading
partial evidence to completed research. Publication is local and requires no Git
commit proof; the caller owns normal project synchronization. Stop after the
finalizer succeeds; never create or edit that integration receipt manually.

The PMR Preview preserves `partial` and `no_data` with their coverage. Use verified
partial findings with their limitations; no-data results cannot support findings.
Follow `preview.md` for the shared synthesis and display contract.
