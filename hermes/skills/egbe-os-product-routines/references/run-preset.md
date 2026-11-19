# Start or resume a Dashboard preset

For `Run Egbe Loop <ID or title>`, first look under this business's `egbe-docs/`
for an existing plan matching the requested ID or saved title. Resume it from
the last verified result or outstanding decision, even if the preset has since
changed or left the catalog. Keep its agreed scope and paused jobs. A repeat
command can continue manual work without repeating completed actions.

For a new launch, look up the ID or title in the published
`references/presets/index.md` of `egbe-os-product-routines` and read the
linked `references/presets/<id>.md`. Through the connector, use
`egbe_skill(name="egbe-os-product-routines", resource=<path>)`. With HTTP,
read `GET /skills/egbe-os-product-routines/resources/<path>` on the connected
OS. If the service is unavailable, use the installed copies when present.
If neither is available, explain that the catalog could not be read. Offer
available choices for an unknown or ambiguous name. If a title
resolves to an ID already in a project plan, continue that plan.

**Agree the launch.** Use the preset's suggested sequence and the project's
`egbe-docs/playbooks/product/business-loop.md` to choose a starting point.
Propose the first action, who owns it, what the agent may do independently,
material time or spending limits, and the result that will guide the next
decision. Incorporate corrections and get the founder's agreement before
starting. Offer a manual launch or a schedule suited to the next evidence.

**Carry it forward.** Save the agreement, preset ID, title and version, next
action and checkpoint in the project's existing plan. For a new plan, use
`egbe-docs/loops/<preset-id>.md`. Do the first agreed agent-owned action and
record its result, or note what the founder needs to do first. Use the relevant
project playbooks for execution. If the founder wants scheduled continuation,
follow [Business Loop and reporting schedules](product-reporting.md) with the
actual plan path. The same chat command resumes the agreement.
