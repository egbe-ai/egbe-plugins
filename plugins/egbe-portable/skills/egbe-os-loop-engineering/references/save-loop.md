# Save a business loop

Work in the selected business. Use `business` on connected Egbe tools, or the project's existing authenticated HTTP connection. The schema is published by `egbe-os-product-routines` at `references/loop.schema.json`. Read it with `egbe_skill` or from the installed skill. A shipped `references/presets/<id>.json` is a complete example. Keep the structure and links valid when adapting it. Use a stable slug for the private definition's `id` and set its `command` to `Run Egbe Loop mine/<id>`. `schemaVersion` identifies the JSON format. `version` tracks the authored content version. The service assigns a separate `revision` to each business save.

| Operation | Request and result |
| --- | --- |
| Find existing work | `GET /loops` returns `data.loops` for this business. Compare ID and purpose before creating a second copy. |
| Open for editing | `GET /loops/<id>` returns the latest `data.definition`, revision, save reason and time, source preset, command and Dashboard URL. Use `?revision=N` to read the exact definition previously used as a base. |
| Open the agent guide | `GET /loops/<id>?format=markdown` returns the full guide, including when and why the revision was saved. With MCP, pass `format` and any `revision` in `query`. |
| Save | `PUT /loops/<id>` with `{ "definition": …, "baseRevision": 0, "reason": "…" }` creates a new loop. For an adapted preset, include `"sourcePreset": {"id": "<shared-id>", "version": 2}` using the actual source version. Send `sourcePreset` only on creation. Omit it on every update, including a conflict retry. On edit, send the revision just read and a short reason. Keep the same ID if the title changes. |

Use `egbe_write(method="PUT", path="/loops/<id>", body=…, business=…, idempotency_key=…)`. Generate one unique key per intended save. With HTTP, set `Idempotency-Key`. Keep the exact payload and key until the outcome is known.

- On success, read the saved definition, check the returned ID and revision, and give the founder the service's `dashboardUrl` and `command`.
- On a timeout, repeat the same request and key. If the service is still unavailable, keep the draft locally and say the Dashboard save is pending.
- On an access denial, check the selected business and the connection's `loops` permission. An older workspace key may need the normal local setup with the founder-approved connection. A restricted secondary key needs its owner to grant that capability. Wallet grace (402) requires a top-up. If the business is paused or archived, ask the founder about restoring access.
- For a validation error, correct the indicated field or link and send the corrected save with a fresh key. Long procedures and lists belong in `agentInstructions`.
- On a revision conflict during creation (`baseRevision = 0`), read `GET /loops/<id>`. If the saved loop already covers the intended decision, reuse it. If it needs an edit, use the revision you just read as the base. If the slug belongs to a different loop, create yours under a fresh ID and update its run command. Use a fresh key for a changed request.
- On a revision conflict during an edit (`baseRevision > 0`), read both `GET /loops/<id>?revision=<baseRevision>` and `GET /loops/<id>`. Compare the draft with both revisions and preserve independent edits. Ask the founder about incompatible decisions or a missing draft before writing. Save the reconciled edit against the latest revision with a fresh key.

Keep supporting evidence, agreements and run results in the project's working records. The central definition holds the repeatable method at its current revision.
