# Start or resume a Dashboard loop

Use the selected business and the exact command from its Dashboard. Look in its `egbe-docs/` for an existing agreement and last verified result. Keep the pause state, permissions and limits. A repeated command can resume manual work.

## Find the right method

An exact ID or card URL selects the method even during an informal discussion. A bare ID or `/loops/<id>` card selects the published preset; `mine/<id>` or `/loops/mine/<id>` selects the business loop. Apply the requested method even if a related private copy or shared original exists. Use title matching only when the founder supplied neither an ID nor a link.

- **`Run Egbe Loop mine/<id>`** opens this business's saved loop. Read `GET /loops/<id>?format=markdown`, including on a fresh chat and before each scheduled continuation. With MCP pass `business` and `query={"format":"markdown"}` to `egbe_read`. Compare `data.revision` to the last revision in the plan. Apply the current method from `data.markdown` to the outstanding checkpoint. A changed diagram cannot approve new spending or restart a paused job.

  If the private definition is unavailable, tell the founder what local records establish and what still needs the named loop. A question about those records does not replace or complete the task. Keep the dependent step pending in the existing plan unless the founder changes it. Note who can restore access, what they need to do, and when to check the definition again under the latest agreement.
- **`Run Egbe Loop <preset-id>`** opens the published preset. Resume an existing plan even if the shared preset changed or left the catalog. For a new launch, read `references/presets/index.md` in `egbe-os-product-routines` and its linked `references/presets/<id>.md`. Use `egbe_skill(name="egbe-os-product-routines", resource=<path>)` or `GET /skills/egbe-os-product-routines/resources/<path>`; the installed copy also works offline.
- **A title** may match a saved plan, a business loop from `GET /loops`, or a shared preset. If distinct matches share a name, offer their commands and let the founder choose. If a catalog could not be read, say which one needs checking.

## Agree the launch

Use the loop and `egbe-docs/playbooks/product/business-loop.md` to choose a starting point that fits the project. Trying a shared preset with the founder's own audience, sources, budget or first check uses the existing preset and a local plan.

For a new launch, use **Scope and limits** to propose the work, time and budget. Propose a first action, its owner, and the result that determines the next step. Offer a manual launch or a schedule that matches the next evidence. Get the founder's agreement before starting. A planning-only conversation ends with the proposed plan. On resumption the recorded agreement applies. Bring only changes that need the founder's decision back for approval, such as raising a spending cap.

Save the agreement and checkpoint in the existing plan. For new plans use `egbe-docs/loops/<preset-id>.md` for a shared preset and `egbe-docs/loops/mine/<id>.md` for a private loop. Keep the full command, business ID, title and shared preset version or business revision. After an authorized action, record its result or the pending founder action. If results call for improving or adapting the definition, use **egbe-os-loop-engineering**.

For scheduled continuation use [Business Loop and reporting schedules](product-reporting.md) with the actual plan path. Identify the responsibility by both business and full loop command. Record and reconcile its own native job, pause state, last occurrence and next check in that loop's plan. Repeating the command reuses the same job. Two different loops can run on different cadences.
