# Fleet Benchmarks

Read `../contracts/research-artifacts.md`. This section uses NO OS Research
job and no free-form web research: the bundled deterministic runner asks one
OS GTM knowledge endpoint — `POST /gtm/comparables` — for the fleet's own
past experiments that are genuinely comparable to THIS product, and renders
the section body plus a machine-readable evidence file itself. On the OS
side the whole verified/directional pool (PII-redacted at the source) is
reviewed by a server-side LLM judge (`gtm-comparables-judge` role) that
matches semantically — differently-worded launches still match, keyword
overlap alone does not. Do not write or edit section prose, tables, or the
evidence file by hand.

The section deliberately contains ONLY comparable experiments. Aggregate
cross-niche channel benchmarks (`GET /gtm/benchmarks`) and fleet-CPC-vs-
auction comparisons were removed from it: pooled all-niche medians say
nothing about the product under research and invite wrong conclusions. When
no comparable experiment exists, the section states that explicitly as a
coverage fact about our own pool — never as evidence against the idea.

## 1. Inputs

- `--seed-keywords "phrase one, phrase two"` — up to 5 category or problem
  phrases selected from the assignment and relevant evidence (lowercase, no
  boolean operators or own-product brand names). They are
  the product context the judge matches experiments against.
- `--geo "US"` — optional launch geography, passed to the judge as context
  (not a hard filter: an otherwise comparable experiment from another geo
  is kept, with the mismatch noted); pass the geography supplied for this question.

## 2. Run the deterministic runner

From the workspace root, resolve `<skill-root>` to the extracted directory
containing this skill's `SKILL.md`, then run:

```bash
python3 <skill-root>/scripts/run-fleet-prior.py --workspace . \
  --seed-keywords "<category phrase>, <problem phrase>"
```

The runner needs `OS_API_KEY` (and optional `OS_URL`) in the environment.
It requests the judged comparable experiments and:

- writes fleet_case and coverage rows to
  `egbe-docs/research/market/evidence/fleet-prior.json`;
- materializes the exact section under `## Fleet benchmarks` in
  `egbe-docs/research/market/full-report.md`;
- verifies the report and evidence together; Git remains caller-owned;
- records the completed state receipt under
  `egbe-docs/research/market/work/fleet_prior/`.

The judge call runs inside the OS gateway and is billed to the claw's own
LLM key; the runner itself calls no LLM. Every response is cached in the
runtime directory, so re-running the same command replays cached data with
zero new reads.

## 3. Known limits and failure handling

The fleet prior is evidence of what WE measured — biased toward the niches
and budgets the fleet has tried. Small-n results are directional. An empty
comparable-experiment result is a coverage fact about our own pool, never
evidence against the idea, and the section says so explicitly. The judge is
instructed to be conservative (exclude when unsure) and the runner never
invents fleet records: only record ids that exist in the pool can be
returned. Large pools are judged in bounded chunks server-side; if the
review was partial (the judge did not see the whole pool) and returned no
match, the runner refuses to record a no-match conclusion and stops — rerun
later. A partial review that did return matches renders them and names the
gap explicitly.

If the runner reports no seed terms, supply `--seed-keywords` from the assignment
and relevant evidence. If no suitable category or problem phrase is known,
record the section as could-not-complete with that reason.
For any other failure (including an unconfigured judge model or an
unavailable LLM upstream), preserve the runtime state and stop; a later
attempt resumes from cache. Do not substitute web search, generic OS
Research, `POST /gtm/search`, or an agent-written result, and do not edit
`egbe-docs/research/market/full-report.md` or the evidence file manually. Completion is
validated deterministically from the runtime receipt; this section has no
LLM-based Research Completion Review step.
