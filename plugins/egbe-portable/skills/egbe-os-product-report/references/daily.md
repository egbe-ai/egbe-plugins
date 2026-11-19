# Detailed product result

Package the Business Loop's supplied result, or prepare a requested standalone
review using the method and plan loaded by the entrypoint. Do not recompute the
loop's priorities as an independent reporting task. Product, advertising and analytics are possible topics,
not mandatory output sections. Apply the method to current evidence and explain
the supported conclusions; reporting does not authorize changes or require a
full audit. Keep existing decisions, observed state and proposed work distinct.

## Write the canonical report

Select the useful conclusions before writing `report.md`: what is happening,
why it matters and what decision or next step follows. For a loop result, make
the current focus, meaningful changes, progress and any founder decision clear;
link to the existing work record instead of maintaining another task list.
Include the facts and
reasoning needed to support those conclusions. Add depth for genuine tradeoffs
or contested interpretations, not merely because the requested format is full.

Use direct, scoped statements. A precise label or time basis is often enough
to avoid an overclaim; it does not need a paragraph listing everything the
number is not. Explain a material limitation once beside the affected claim.
Other possible interpretations or things that were not checked belong in
evidence unless they change the decision. Group areas sharing one status.
Do not teach the reader how every source works or argue against mistakes the
report never makes. For each area, keep the useful result, its consequence and
any needed action; put reconciliation detail and secondary measurements in the
snapshot. A precise metric label can replace a repeated “this does not mean…”
explanation.

Keep source IDs, query details, arithmetic checks and execution/validation
logs in `snapshot.json`. The Markdown should be useful on its own, with links
to that evidence, not a narration of the reporting process.

Edit the report before deriving other formats. Every block must answer a
founder question or justify a consequential conclusion. Remove a passage if
it adds neither a fact needed to understand the situation nor a reason to
choose an action. Merge repeated qualifications; omit inapplicable metrics and
sections instead of filling them with explanations of their absence.
Detailed means adequately explained, not necessarily longer than the brief.
When little has started or changed, the canonical report may be close to the
summary in length; do not expand an uneventful status into a catalogue of
possible concerns.

Make the next step actionable: name the concrete result you can produce,
the founder's necessary input or decision, and how the result determines what
happens next. Separate work that can start now from work waiting on that input.
Offer a simple way to continue in chat; distinguish preparation from authorized
execution. A copyable instruction can help, but does not itself start the work.

## Derive the founder-facing outputs

Create `summary.md` from the completed report. Use short titled blocks and
bullets for distinct facts and proposals, with selective emphasis, so the
founder can understand the outcome and important decisions in about a minute.
Length follows useful content, not a word quota. Retain limitations that change
a decision, preserve the reason behind the main recommendation, and link to
the relevant sections, not only beside recommendations.
Explain necessary metric terms in plain language.
Use a separate bullet for each distinct result or action rather than stacking
long paragraphs under bold opening sentences. Keep test and rendering logs out
of this message; mention an output limitation once, briefly, if it affects use.

Use `egbe-os-report-ui` for the visual edition of the report. Supply the content's
relative importance: what the founder should understand at a glance and what
supports closer reading. Let presentation express those relationships rather
than map every Markdown heading or paragraph to a screen block.

Verify semantic agreement, not identical wording: findings, values, priorities,
evidence and material limitations must remain accessible. Add working anchors
for summary links. If HTML is unavailable, link to Markdown and say so.

Read the result as the founder: is it clear what to improve first and why,
what remains a hypothesis, what you will deliver next, and how to ask for it?
Revise vague investigations or task menus that leave those decisions to the
reader; do not invent a diagnosis to make the answer sound decisive.
