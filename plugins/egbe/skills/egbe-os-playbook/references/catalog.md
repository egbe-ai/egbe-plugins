# Install and synchronize project playbooks

The editable files in `egbe-docs/playbooks/` are the project's active methods.
Egbe delivers fresh source material separately from skills. Delivery adds missing
files; it does not replace or delete existing project methods. The agent handles
their meaningful adaptation, including changes that span several files.

## Initial installation

If skills are not installed yet, use quickstart's
[catalog installation](../../egbe-os-quickstart/references/installation.md) in the
established project workspace. Otherwise reuse that installation result.
The installer obtains the manifest and version URL itself and uses the shared catalog
helper; do not build a second playbook downloader or install methods as skills.
If playbook delivery remains pending, finish it through the installed helper's
[catalog update](../../egbe-os-quickstart/references/skill-updates.md) before continuing.

Read `playbooks.added`, `preserved` and `skipped` in its result. Report a skipped
file with its reason; preserving a project method is expected, not a skill
conflict. The installation saves the project root and prepares Git/build
exclusions. Do not repoint an existing installation at another project.

Use the generated project-playbook index in `EGBE.md` to find the entry point.
For a new project copy, read its entry and the parts needed for the current work.
Installation alone does not establish that the method suits this project or
that its source release has been considered; complete the review below before
recording it as reviewed.

## Synchronize before method work

At the start of work using a project playbook, use the installed quickstart
helper's [catalog check](../../egbe-os-quickstart/references/skill-updates.md). Reuse the
result if already obtained for this entry into the work; do not make a second
version request. Check again on a later relevant task or an explicit refresh,
not on every turn or tool call. Follow [change delivery recovery](changes.md#resume-and-delivery)
for unfinished records from earlier method edits.

The shared read-only check reads both skills and playbooks versions. A skills-only
update does not require a new method review. If delivery is needed, run the same
helper without `--check`, supplying the established `--project-root` if requested.
Use `playbooks.source_directory` for the verified source to compare and
`playbooks.target` for its release. This is replaceable source material, not the
active method or a history of prior Egbe releases.

`playbooks.review_required` means that source release has not been fully
considered. It is distinct from successful delivery and from accepting any
particular recommendation. If delivery failed or remains partial, preserve
current methods and retry the reported problem; do not mark an unavailable
release reviewed. Existing usable methods can still guide independent work.
An unreviewed source does not invalidate the current project method or an agreed
plan. Continue that work when source review would interrupt it, leaving the marker
unchanged until consideration is complete. When review is not required, use the
current project method without another source review.

### Consider the current method as a whole

Compare the fresh method and its connected parts with
the current project copies. An improvement in evaluation can change the value
of an unchanged channel recommendation; do not limit consideration to changed
file bytes. Ordinary task work still reads only the relevant route.

Read relevant recent project commits/diffs and existing plans or decisions to
understand local adaptations. Without Git history, use the working files and
available context; neither a commit nor the original chat is required. Compare
the methods as they stand, not an invented reconstruction of Egbe's change
history. An unexplained local difference is not automatically obsolete.

Explain useful proposed changes, their basis, expected benefit and which local
decisions they affect. Keep established choices and useful exceptions. Revisit
an earlier rejection only with a new substantive reason, explaining what changed.
Keep unresolved differences explicit while progressing independent useful work.

Before accepted edits, follow
[catalog-update recording](changes.md#changes-prompted-by-a-catalog-update) to
capture the actual project files. Adapt them with targeted changes; source copying
is not semantic merge. A new source file may contain rules moved out of an older file: reconcile
navigation, overlap and contradictory guidance rather than leaving both methods
active. The installer preserves files; this is not a prohibition on agreed agent
edits, moves or removals. Do not silently change an already approved task plan.

### Record finished consideration

After the coherent review and its decisions are complete, record the reviewed
`playbooks.target` in tracked `egbe-docs/playbooks-sync.json`:

```json
{"reviewed_version": "<reviewed playbooks release>"}
```

Use the version actually considered, not a newer release that arrived during
the work. Declining all proposals can complete a review; interruption or pending
decisions cannot. Resume the remaining work before advancing the marker. Keep
the decision context in existing project plans/notes, not a new review register.
The marker travels with the repository so another agent need not repeat finished
consideration. It is not proof of accepted changes or the version of local text.

## Older installations

The legacy `version.txt` remains a single skills hash. Its updater first installs
the new skills; then run the newly installed helper as instructed by
[catalog updates](../../egbe-os-quickstart/references/skill-updates.md). It switches the
saved official endpoint to `versions.txt`, reads both versions and delivers
playbooks independently. Current skills do not prove playbooks are installed.

Complete both phases in the same task; no new chat is required between them.
Explicit custom/test version URLs stay explicit. Use the normal conflict and
permission recovery for an edited or protected quickstart, not a forced overwrite.
