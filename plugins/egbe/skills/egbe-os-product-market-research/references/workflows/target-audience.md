# Target audience

Read `../contracts/research-artifacts.md` and `../prompts/target-audience.md`
for evidence checks and output mechanics. The current assignment, not the
bundled topic brief, defines the question and depth.

```bash
python <skill-root>/scripts/run-target-audience.py --workspace . \
  --assignment "The bounded question, scope and comparison criteria from the current task"
```

Use `--assignment-file` for existing task text when convenient; no new format
is required. The runner keeps provider-safe product context and includes only
valid completed supporting results/measurements. Missing optional inputs are
limitations, not reasons to collect unrequested sections. A selected unfinished
measurement used by this section must finish or be closed before it can be cited.

The actual assignment, query, system prompt, job state and result live under
`egbe-docs/research/<id>/work/target_audience/`. The result materializes under
`## Target audience` in the existing incremental report. Retrying unchanged inputs
resumes/reuses the job before publication; changed inputs preserve that work
and require a separate research ID, not a silent new provider call.

After success, complete the shared Research Completion Review for
`target_audience`. Preserve failed/uncertain state; do not replace a provider response
with invented output. The caller owns Git publication and may continue the
surrounding task when this operation finishes.
