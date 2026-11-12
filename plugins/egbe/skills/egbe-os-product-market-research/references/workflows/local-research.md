# Standalone local research

Use the full bundle in an ordinary product repository with a prepared research
assignment and OS credentials. Scripts publish files and receipts in the workspace;
the caller owns Git. No hosted runtime, instance ID or separate docs repository
is required. Choose one stable research ID for the work and retain it on resume.

For a requested multi-section preview, record the task's selected
scope once (the user need not name internal workflow IDs):

```bash
export EGBE_RESEARCH_ID="${EGBE_RESEARCH_ID:-market}"
python <skill-root>/scripts/build-preview-context.py --workspace . \
  --sections keyword_economics,acquisition_channels
```

Run only the operations needed by that scope. Respect actual receipt-backed
input dependencies; there is no mandatory catalog sequence. For narrative
research, pass the bounded question with `--assignment` or `--assignment-file`.
An optional `--context-file` provides only the relevant provider-safe background
chosen for that question. Measured operations can use their explicit CLI inputs
without a context file; the shared snapshot records the context actually used.
Read each selected workflow and the artifact contract; metered calls stay within
the caller's authorized budget. For US and UK, run
the same keyword runner separately with `--location-code 2840` and `2826`.
Repeating US preserves UK and reuses the request cache.

After each workflow (and the required AI completion review), refresh outcomes:

```bash
python <skill-root>/scripts/build-preview-context.py --workspace .
```

Absent work stays pending. To close genuinely failed or intentionally skipped
work, pass `--failed <section-id>`; use `--retry <section-id>` to reopen it.
Only that explicit closure stays fixed. Receipt-derived outcomes, including
`partial`, `no_data` and validation failures, are checked again on refresh.
Do not mark success manually. Refresh checks input/file hashes and the
materialized report. Changed scope or selected context needs a new research ID
for new collection so existing research remains available. Source drift does
not erase saved observations or itself authorize another paid run.

If a preview is requested, once no selected section is pending, follow `preview.md` to write the synthesis
and render it from the workspace root:

```bash
python <skill-root>/scripts/write-preview.py --local-report-link full-report.md
```

This creates local documents, not hosted links. No instance registration, fake
public ID, provider call or manual `preview-context.json` construction is needed.

For product definition or another decision, link the relevant existing findings
and their evidence boundary into the caller's requirements or plan. No separate
PRD-context adapter, rendered preview or receipt-binding step is required.
