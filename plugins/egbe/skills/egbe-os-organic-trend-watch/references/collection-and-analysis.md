# Collection and analysis

Use the absolute roots from `SKILL.md`; script paths belong to the installed
skill and mutable paths to the product study.

## 1. Initialize or resume

For direct use, initialize with the scoped question and product context:

```bash
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/run-state.py" --runtime-root "$RUNTIME_ROOT" \
  init --assignment "Compare demonstrations that explain this product's workflow" \
  --product-context "The product, intended audience and relevant constraints" \
  --discovery-limit-per-account 12 --lookback-days 21
```

For an existing caller-provided `context.json`, validate it and run `init`
without replacing it. Inspect `status` before continuing:

```bash
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/validate-context.py" --context "$RUNTIME_ROOT/context.json"
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/run-state.py" --runtime-root "$RUNTIME_ROOT" init
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/run-state.py" --runtime-root "$RUNTIME_ROOT" status
```

Resume saved steps and matching provider handles. `init` does not refresh data
or authorize another paid collection. A changed assignment needs a new study;
an explicit refresh is separate from retrying. See `runtime-contract.md`.
Choose the per-account limit and lookback from the assignment and budget; the
flags above are examples, not a required sample. Omitted values default to 30/60.
Existing caller-provided context already owns these parameters; `init` does not
override them. `--max-analysis-videos` separately caps total selected observations.

## 2. Identify and collect sources

Find public TikTok/Reels accounts relevant to the question. Competitors, adjacent
products, creators or partners may provide evidence; no account class is
mandatory. OS search may locate handles, not substitute for collected video data.

Write `raw/accounts.json` as `{"accounts":[...]}` using the schema in
`runtime-contract.md`. Mark discovery complete with `complete-step --step discovery`.
Build discovery inputs:

```bash
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/build-provider-inputs.py" --runtime-root "$RUNTIME_ROOT" --mode discovery
```

Read `provider-contract.md`, then run each applicable platform's canonical run:

```bash
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/run-apify.py" \
  --runtime-root "$RUNTIME_ROOT" --key tiktok-discovery \
  --actor-id clockworks/tiktok-scraper --platform tiktok --kind discovery \
  --input-file "$RUNTIME_ROOT/raw/tiktok-discovery-input.json" \
  --accounts-file "$RUNTIME_ROOT/raw/accounts.json" --output raw/tiktok-discovery.json
```

`--start-only` saves the handle before returning; repeat the same command to poll
and retrieve its dataset. Never replace a started run's input. Normalize once
to freeze the requested analysis sample after time-window filtering. Unknown-date
and out-of-window observations remain in raw/normalized evidence with explicit
counts, but do not enter account medians, selection, or paid enrichment.
If the question needs evidence not already
available from discovery, build `--mode enrichment` inputs and run the needed
batches within the collection budget. Otherwise continue with discovery evidence;
there is no mandatory extra paid call. Preserve needed but unavailable evidence
as gaps rather than broadening the conclusion. The runner maintains the raw manifest;
do not hand-author provenance or mark provider failures as successes. A terminal
failure may support a partial result alongside successful datasets; record its
gap as specified in `provider-contract.md`. Active/uncertain runs block sealing.

```bash
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/normalize-videos.py" --runtime-root "$RUNTIME_ROOT"
```

Normalize again if enrichment added evidence, without changing the frozen sample.
Mark `collection` and `normalization` complete once required discovery and all
started runs have settled. The same
`run-state.py ... complete-step --step <name>` command records each step; sealing
validates evidence and provider state, not just these progress flags.

## 3. Inspect available evidence

When audiovisual evidence is needed, use the canonical preparation pipeline for
the selected observations to inspect. Skip media calls for questions fully
answered by available captions, metrics or comments:

```bash
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/prepare-visual-evidence.py" \
  --runtime-root "$RUNTIME_ROOT" --observation-id "$OBSERVATION_ID"
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/analyze-visual-evidence.py" \
  --runtime-root "$RUNTIME_ROOT" --observation-id "$OBSERVATION_ID"
```

Preparation records provider-media/frame provenance; the analyzer uses OS and
reuses matching content-bound receipts. Do not replace these receipts with
agent-written claims or another tool's output. Media failure remains a coverage
gap, not evidence of an unsuccessful creative. Captions, metrics and comments
can still support their own narrower findings.

Apply `analysis-and-adaptation.md` and write `analysis.json` per
`output-contract.md`. Include only analytical fields actually supported. Missing
selected observations remain explicit partial coverage, not fabricated entries.
Record missing evidence and contrary observations.
Mark `visual_analysis` and `synthesis` complete after validating that analysis.

## 4. Render and seal

```bash
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/render-result.py" --runtime-root "$RUNTIME_ROOT"
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/run-state.py" --runtime-root "$RUNTIME_ROOT" complete-step --step render
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/finalize-receipt.py" --runtime-root "$RUNTIME_ROOT"
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/validate-runtime.py" --workspace "$WORKSPACE_ROOT"
```

Return `result.md` with its complete, partial or no-data coverage. A valid sealed
receipt certifies provenance, not universal research completeness or causality.
