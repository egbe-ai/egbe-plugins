# Evidence and destination report

## One run, inspectable evidence

Use the caller's audit directory when supplied. Otherwise create a unique
`egbe-docs/audits/<YYYY-MM-DD-HHMMSSZ>-destination/` under the product repository using
the actual UTC time, with a suffix on collision. Resume only when explicitly
continuing that run. Do not overwrite previous runs or commit/push as part of
inspection. If the repo is unavailable, use a temporary run and state its path
and the missing repository handoff.

Keep the scoped conclusion and necessary sanitized evidence together. For a
standalone inspection, save `report.md` and a concise founder handoff; for a
nested check, use the caller's existing results and source index. Do not require
separate draft, review or duplicate summary files. Preserve previous work.

In the existing source record or report, record the question, product/URL, run time, known deployment,
selected paths/networks and selection basis, prior report, and completion limits.
For each read, retain URL or source path/line, time, method/context, saved evidence
file, relevant redirects, outcome and unavailable portions. For code evidence,
record the inspected revision and relevant uncommitted changes; note whether it
matches the deployed version or that the relationship is unknown. Save necessary
page/code excerpts, link inventories, screenshots or sanitized readbacks before
deriving findings.
Retain query parameters that affect the offer, but redact tokens, signed URLs
and personal values before writing. Do not save browser/session credentials or
customer records. Evidence capture is selective, not a full private-site export.

## Full report

Lead with the answer in ordinary language, then support it with these sections.
Use detail proportional to the actual paths/findings, not a word-count target.

### Decision and coverage

Give a conclusion for each distinct affected path and, when checked, network:

- **Ready within inspected scope:** the relevant checks are supported by
  evidence, with no material defect or unresolved uncertainty in that scope.
- **Changes needed:** an observed problem needs repair before recommending
  traffic through the affected path. Explain why; do not count cosmetic
  preferences as blockers. List consequential unknowns separately if also present.
- **Verification needed:** a consequential part cannot be concluded from the
  available evidence. Name the missing check and the smallest way to resolve it.

Show the inspection boundary, time and untested portions alongside the conclusion.
Distinguish defects established in local code, behavior observed on the deployed
site and unverified runtime effects. State any material version mismatch; a
source-only or local-preview check does not establish deployed readiness.
If only entry-to-form was verified, do not imply completed signup or payment.
Mark irrelevant checks **not applicable** with a short reason. Distinguish a
common-only result from a result including named network requirements. A clear
path can remain usable even when another path needs changes.

### Visitor path and observations

Map promise → entry → CTA → next step with exact safe URLs, meaningful values
(such as duration and price), and evidence links. Include enough positive checks
to explain the scope of a ready conclusion. Avoid a giant list of unchecked
pages; list material exclusions and why they matter instead.

### Findings and repairs

For each material finding provide:

- Expected vs observed behavior and links to both pieces of evidence.
- Visitor consequence: what becomes impossible, unclear or unexpectedly costly.
  Distinguish demonstrated behavior from a hypothesis about conversion impact.
- Basis: functional defect, trust/offer clarity, or specific network requirement
  with official source and applicability. Identify affected paths/networks once.
- Priority with rationale: repair before traffic, resolve before deciding, or
  non-blocking improvement. Do not infer severity from the number of networks.
- Smallest coherent correction, affected implementation file/line and responsible
  role when known, and a concrete observable recheck condition. Do not silently
  implement the recommendation.

Group shared root causes without losing distinct repairs. A missing disclosure
and wrong calendar duration may share a path but need different fixes. Questions
come with a recommended answer/action where applicable, not a bare list of unknowns.

### Limits and next decision

State what could change the conclusion, which source/access gaps need resolution,
and exactly what to recheck after repairs. Destination defects are conditions on
the path, not evidence that the market or product is unviable. Network approval
and overall campaign readiness remain outside this report.

## Review and founder handoff

Check evidence links, policy applicability, scope and counterevidence before
delivery. Correct the conclusion and retain consequential unresolved gaps in
the same record; derive the founder handoff from that checked result.
Keep both report and brief limited to visitor-path findings. Return incidental
ad configuration, conversion-binding, attribution or optimization findings to
the caller's channel analysis; an out-of-scope link is enough here, not repeated
diagnostics or readiness conditions. Functional form persistence and visitor
feedback remain destination checks, unlike recording that action as an ad conversion.

The brief answers: can we send visitors through the inspected path, why/why not,
what should change first, and what still needs checking? Include meaningful
positive results as well as blockers. Write in the founder's language: explain
what visitors experience, why it matters and what to do next in everyday words.
Keep inspection jargon and protocol details in the linked report; retain exact
URLs, names or identifiers in the brief when needed to locate or fix something.
Explain an unavoidable specialist term at first use. Link decisions, observations,
limits and recommendations to their exact report sections, not only to the
report's beginning. Do not replace the explanation with IDs or status jargon.

Make the brief scannable with short, meaningful subheadings and bullets for
parallel findings or conditions; number actions when their order matters. Keep
one main point per item, with its reason, qualification and supporting link.
Use short prose for the opening decision and transitions, and emphasis only for
key decisions or limits, rather than turning every sentence into a heading or list.

Return the brief and the
full report path; call an unfinished inspection incomplete.
