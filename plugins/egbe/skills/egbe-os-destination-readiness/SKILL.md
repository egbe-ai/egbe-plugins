---
name: egbe-os-destination-readiness
description: Audit landing-page claims, visitor journey, identity, terms and data handling without changing the product.
metadata:
  egbe-when: "Use before traffic or after page changes; offer when the promise or visitor path is unclear."
  egbe-visible: "true"
  egbe-title: "Destination readiness"
  egbe-description: "Check your landing page and signup, booking or purchase path before sending traffic. Find broken steps, confusing promises and missing disclosures, with concrete fixes."
  egbe-category: "Marketing & growth"
---

<!-- egbe-mcp-connection:v1 -->
This skill comes with the Egbe plugin. Make every Egbe API call it describes with
the Egbe connector's `egbe_request` tool: pass the HTTP method, the API path (for
example `/me/limits`), query parameters in `query` and the JSON body in `body`.
For these calls leave out `OS_URL`, the Authorization header, `.env.local` and
`egbe-curl.py`, and skip catalog update checks; the connection authenticates and
identifies the request.
Also pass the `business` that `egbe_setup` returned. Files this skill refers to
are next to this `SKILL.md`, except any listed under "Files downloaded on demand".

A step that needs a local project key, such as a git push or a local deploy
command, works only in a persistent project workspace. There, if the project's
Git-ignored `.env.local` has no `OS_API_KEY` yet, call `egbe_local_setup` once
and save its `OS_URL` and `OS_API_KEY` there, preserving other entries. Use only
those two values: the plugin already provides Egbe's skills, so do not install
the Egbe catalog or follow the rest of that result. Never show the key in chat or
put it in logs, commits or URLs. Without such a workspace, tell the founder that
this step needs an agent with a project folder, and continue with the rest of
the work.


# Destination readiness

Answer: **Can the intended visitor understand this offer and safely reach the
promised next step on the current site? What must change, and why?** Think as a
careful prospective customer, not a checklist scorer. A technically reachable
page can still make the wrong promise or ask for trust it has not earned.

This is the network-independent check. It requires the product URL, intended
offer and next action, not an ad account or performance data. A caller may add
advertising-network destination references and supply an existing work folder;
apply those to the same evidence and result. For named or already planned networks,
use [network requirements](references/network-requirements.md); otherwise label
coverage common-only.

For an acquisition test, take the intended audience, promise and next step from
the caller's concrete plan. Verify that
journey; do not select a new offer, audience or test. Return a material conflict
to the same method/plan decision rather than resolving it through a redesign.

## Workflow

1. **Frame the actual path.** Identify the product repository and deployed URL,
   the visitor's promise and intended next action from the request, site and
   relevant product documents. Distinguish the advertised promise from what the
   current page says. Ask only when an ambiguity changes the check; give a
   recommended interpretation with the question. Prepare the run using
   [evidence and output](references/report.md).
2. **Map from the project first.** When application source is available, start
   with the [focused repository inspection](references/checks.md#start-with-the-project-source).
   Map each materially distinct route as promise → entry URL → primary CTA →
   signup, booking or purchase destination. Include meaningful offer, locale or
   device variants and where information, commitment or money is requested.
   With only documents or a URL, map the public path directly.
3. **Verify the deployed experience.** Read [checks](references/checks.md).
   Use the map for targeted checks of actual entry pages, links and next steps;
   capture evidence where expectations change or the implementation needs live
   confirmation. Use rendered pages for interactive or visual claims;
   source code and HTTP responses can corroborate but cannot prove those claims.
   Prior reports are leads, not evidence that today's deployment is unchanged.
4. **Explain the consequential gaps.** Separate observed failures, trust or
   clarity problems, policy requirements and uncertainties. For each finding
   explain the visitor consequence and the smallest coherent repair. A local
   mismatch may require aligning the promise and destination, not merely
   changing a label. Report the affected path, not a verdict about the whole
   product. Reuse common observations across supplied network checks.
5. **Check the conclusion.** Review the evidence before delivering: did a guessed URL become a claim of absence, a
   provider name become a false brand alarm, an inaccessible step become a
   failure, or a cosmetic preference become a blocker? Also check the reverse:
   did a 200 response or polished page hide missing substance or a broken CTA?
   Resolve contradictions where safe; otherwise preserve the uncertainty.
6. **Deliver a decision the founder can act on.** Use the
   [report contract](references/report.md): scope-specific conclusion, evidence,
   prioritized repairs and observable recheck conditions. Explain why each
   recommendation matters and link its supporting section in the founder brief.

## Inspection boundary

Browse and read existing authorized evidence only. Do not submit forms, create
accounts/bookings/checkout sessions, send messages, pay or alter the site or
campaigns to complete a check. Inspect a CTA's action before following it if it
could create state; stop at that boundary and name what remains unverified.
Use only public or task-authorized access, and sanitize evidence before saving.

The conclusion covers destination readiness, not targeting, bids, budgets,
campaign/ad-group/ad configuration, event instrumentation or optimization.
It is neither provider approval nor a legal certification or product-demand
assessment. Lack of traffic is not a reason to postpone this check.
