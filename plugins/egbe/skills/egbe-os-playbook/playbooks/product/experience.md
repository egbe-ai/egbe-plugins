# Design the experience

Turn the accepted [value](value.md) and applicable [offer](offer.md) into a path
people can understand and use. Start with existing research, product behavior,
materials and scoped design decisions. Use only the parts relevant to the change;
a page revision does not require redesigning the product.

## Follow the person through the result

Start with the person's job, recognizable objects and desired outcome, then derive
surfaces and navigation. Choose a dashboard when repeated overview or control is
central to that job, not because the database has tables. A useful path may include
an app, external channel, email or delivered file; it does not necessarily need a site.

Trace entry, action, result and meaningful continuation. Include how the person knows
what happened, where their work went and what to do next. Cover the relevant empty,
loading/progress, partial, success, error, permission, stale and recovery states.
Protect continuity through long work, account entry, payment, interruption and return.
An absent optional result is not a missing prerequisite for the primary result.

For a failure between steps, decide whether useful continuation remains possible
without the missing save or handoff, or whether recovery must come first. Explain
material trade-offs and implement the accepted behavior. Continuing to another
page, durably saving information and completing the intended action are different
outcomes; do not report one as proof of another.

Place the accepted preview, identity, sign-in methods and payment decisions;
do not choose them again here.
Choose inline or separate routes, navigation and CTA destinations from this path.
Keep the chosen object, plan and intent across transitions. Separate public,
authenticated, administrative and channel contexts where they genuinely differ.
Approval of a homepage's voice or visuals is not approval for the whole application.

Collect only the information needed for the result or agreed follow-up. Make clear
why contact details or other personal information are needed at that point; an
available form is not a reason to put another barrier before useful continuation.

## Experiences shaped by people's answers

Use a quiz, assessment, calculator or guided flow when answering helps someone
reach a useful result or decision better than a simpler page or form. Work from
the accepted offer and audience, not a borrowed funnel's question count.

Make each question earn its effort: it changes the result, route or follow-up,
or helps the person understand their situation. Start with what people can answer
from their own experience; make the reason for more personal questions clear.
Choose the length and progression for the value and commitment involved.

Check whether the intended people can answer truthfully. Handle uncertainty,
inapplicability or declining where relevant rather than forcing an invented answer.
Respect sensitive-data protections; if missing input limits the result, explain
that limit and offer a suitable continuation rather than pretending nothing changed.

Make each statement true for everyone who can reach it; use variants when answers
change what is true. Do not infer what the answers do not establish or claim
analysis, saved personalization or expert review that is not happening. If an offer
is unsuitable, explain the basis, skip questions that no longer serve a purpose and
offer a relevant alternative when available. Another suitable offer may still be paid.

Show representative paths, actual questions, results and continuations together
for meaningful review. A preview should be recognizable as a preview, with material
conditions clear before the person commits the effort it requires. Required terms
must remain visible on applicable paths even when optional answers are missing.

Use `egbe-os-quiz-funnel` for a flow its runtime supports and `egbe-os-product-build`
for another agreed implementation. A template's limits do not decide the offer
or justify silently changing the intended experience.

## Explain the proposal honestly

Use the product's actual materials and the audience's language. For each important
surface, make clear what is offered, why it matters here and what the next action
does. Build content around the visitor's questions and objections, not a preset
section count. Merge repetition without removing a distinct answer or important condition.

Use evidence relevant to this audience and promise. Resolve conflicting sources by
their scope, definition, provenance and freshness; neither the smallest number nor
a fixed source hierarchy is automatically correct. Qualify unsupported breadth and
keep material unresolved conflicts visible. Support material numbers and proof with
attributable records, including the founder's own records when applicable. Preserve
what they measure, for whom and over what period; distinguish estimates and exceptional
results from typical outcomes. Use testimonials and third-party material with the
appropriate permission and attribution. When a claim cannot be supported, use a truthful
explanation, real example or demonstration rather than inventing customers or results.
Do not invent product capabilities. Illustrations are not screenshots or customer proof;
amounts and depicted behavior must remain internally consistent. Export compatibility
is not an integration or ongoing sync. Availability and price must match the real offer.

For a campaign page, keep the test's audience, promise and intended outcome from
[Market and acquisition](../market-and-acquisition/run-test.md). That method owns
message match and readiness for traffic; this one owns common experience decisions.

## Give the interface a coherent visual language

Choose hierarchy, typography, density, rhythm, imagery and interaction that serve
this product's content and desired experience. Explain the important choices through
that context, not adjectives alone. Reuse a working visual system within its scope;
do not force novelty or a generic SaaS shell. Adapt reference patterns without copying
another brand. A common system can have deliberate differences across product contexts.

Use `egbe-os-design` to find concrete design references, `egbe-os-images` for needed
stock/generated assets and `egbe-os-product-demo-video` for actual product footage.
These are options, not asset quotas. Show enough actual copy, interactions and visual
material for meaningful founder review; `egbe-os-report-ui` can make alternatives or
a plan easier to compare without becoming another source of decisions.

## Review the whole experience

Check the proposed experience at the level of its claims:

- Can the intended person explain the offer and next action from the relevant
  entry surface, without knowing internal terms? Is the most important information
  visually prominent, with its material conditions legible nearby?
- Does every promised action lead to the right destination and preserve context?
  Does the journey deliver the result, including messages/files, rather than stop
  at a confirmation screen? Are failure and recovery understandable?
- Does the evidence support the depicted product and this audience? Would a
  knowledgeable customer find a misleading comparison, missing term or invented proof?
- Are navigation, language and visual choices coherent within their scope, and
  can the important path work on small screens, touch and keyboard?

Model judgment is not user research, and an approved mockup is not a working journey.
Keep meaningful proposals distinct from accepted decisions via
[collaboration](collaboration.md); unknown material policy blocks only dependent work.
Keep decisions in the existing requirements or, when useful, `egbe-docs/product/ux/`,
`product/design.md` and `product/pages/<page-id>/`. No duplicate structured plan or
mandatory document per screen is needed. Preserve deferred/nonvisual requirements
without inventing screens for them.

Use `egbe-os-design-landing-page` for the main page, `egbe-os-campaign-landing-page`
for campaign destinations and `egbe-os-product-build` for application implementation.
They own technical accessibility, integration and verification, not a replacement offer.
