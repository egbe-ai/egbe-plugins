# Static-banner rendering QA

Check substituted fields against the selected schema; render at its canvas
dimensions. Inspect exported media at full/feed size for missing glyphs,
placeholders, clipped/overlapping text, broken CTA and unintended layout shifts.
Displayed claims/disclosures must match supplied content.

Repair the cause (fit, wrapping, spacing or layout), not by silently changing
the supplied message.

Use `file output.png` to verify dimensions; retain source, export and upload
URL. See [capture/upload](html-to-png-pipeline.md).
