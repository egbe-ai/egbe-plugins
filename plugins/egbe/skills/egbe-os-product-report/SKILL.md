---
name: egbe-os-product-report
description: Package Business Loop results or requested status reviews as concise updates, Markdown and offline HTML.
metadata:
  egbe-when: "Offer when decisions need a business overview; use for on-demand and scheduled reports."
  egbe-visible: "true"
  egbe-title: "Your product at a glance"
  egbe-description: "See how your product, spending and customer acquisition are doing, what needs attention and what your agent can help improve."
  egbe-category: "Business operations"
---

<!-- egbe-mcp-connection:v1 -->
This skill was delivered through the Egbe MCP connection. Make every Egbe API
call it describes with the `egbe_request` tool: pass the HTTP method, the API
path (for example `/me/limits`), query parameters in `query` and the JSON body
in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Read a referenced file with
`egbe_skill(name=<skill>, resource=<relative path>)`.

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs the standard workspace setup. In a persistent
project workspace that is not set up yet, call `egbe_local_setup` and follow it.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.


# Product report

Help the founder understand what is happening, what matters and what to do next.
Reporting is read-only with respect to the product and external services; it does
not authorize fixes, campaign changes, spending or outreach. Use `egbe-os-product-routines`
to configure or change a schedule, not as a prerequisite for a manual report.

## Establish the context

Identify the business from the project's configured Egbe connection and existing
product records. Reuse local credentials without copying them into artifacts.
Select `brief` for a status request or agreed short update; select `detailed` for
the Business Loop result or an explicit request for a full report.

Use the requested period and project/user timezone. A status request concerns
the current state, with today's results where applicable. A Business Loop reports
its current checkpoint and each measure's actual window; an existing standalone
daily report retains its agreed previous-calendar-day period. Choosing detailed output does not
turn a current-state request into a historical review. Keep current balances
and availability separate from period totals. If the timezone is unknown,
disclose the harness timezone used.

Read [artifact storage](references/artifacts.md), the latest relevant snapshot
and summary, and the previous detailed report when useful. Use known goals,
open issues, agreed experiments and founder decisions to interpret the state;
include them in the report only when relevant to its conclusion or next step.
When a recommendation depends on an earlier decision, read the relevant plan,
audit or decision record and distinguish its findings from current evidence.
When the Business Loop supplies its result, reuse its conclusions, evidence and
current plan. Check coverage and presentation without starting a second business
review or inventing another next step. A contradiction or missing material fact
returns to the caller for resolution; retain useful partial results meanwhile.
For a standalone report needing product interpretation, read the project's `egbe-docs/playbooks/product.md`
and `product/evaluate.md`; use `product/diagnose.md` only when a consequential
question needs it. For market/acquisition interpretation use
`egbe-docs/playbooks/market-and-acquisition.md`, its `evaluate.md` and the relevant
channel supplement, together with the concrete plan. Apply local
adaptations, including how recommendations and decisions are handled. The report
may reason from fresh observations and recommend a next step without an existing
results file; it does not change the product, campaign, accepted plan or standing method.
If these files are inaccessible, disclose that gap and limit dependent judgments
instead of replacing them with a bundled business strategy.
Do not reread all history or imply that an unread audit supports the report.
Establish the product's stage from its records and owned deployed apps, not the
contents of the local folder: a new connection can belong to an existing product.

## Gather supporting evidence

Follow [sources and measurement](references/sources.md). Reuse recent evidence
only when its scope and time fit this report; fetch what is missing or changed.
Supplied Business Loop evidence is reusable under the same checks, without
repeating its collection.
Save the supporting facts and coverage in `snapshot.json`.

Read only the selected reporting guide:

- [Brief update](references/brief.md): a compact status and one useful next step.
- [Detailed result](references/daily.md): a complete `report.md` with the relevant
  findings, work status, decisions and their basis; no fixed business sections.

Keep the work proportional to the decision. A routine report is not a mandatory
full funnel audit, repository review or market study. When a finding needs deeper
investigation, identify the uncertainty and propose a focused next task.

## Prepare, verify and deliver

Write as the founder's partner: use first person for your recommendations and
offers of help. Explain technical findings by their effect on the product or
customer journey; keep implementation terms and diagnostic details in the
supporting evidence unless the founder needs them to decide.
Name pages and steps by their customer purpose, not internal routes; report
whether customers can reach them, not HTTP codes or serving revisions.

For a detailed run, finish `report.md` first. Derive `summary.md` and use `egbe-os-report-ui`
to create `report.html` from that report. Visual composition may differ; facts,
recommendations and material limitations must not. Correct content in Markdown
first, then update both derived outputs. For a brief run, `summary.md` is the
complete authored result; no full report or HTML is required.

Check arithmetic, links and agreement between formats. For each headline and
zero/absence claim, verify that the source's ownership, definition, period and
coverage support the whole claim; narrow it when they do not.
A failed source can still yield a useful partial report; disclose what
could not be checked. If HTML rendering fails, deliver the verified Markdown
and summary, explicitly leaving HTML unfinished.

For scheduled output, honor the caller's notification decision: prepare without
sending when notification is not required. Otherwise send the summary in the
founder's language with light formatting and links to the actual local
artifacts. A local path is not a public URL; use a supported
attachment when the recipient cannot access the file, without publishing it
elsewhere by default. Record the result under the artifact contract. For a
scheduled run, return the artifact path and coverage/delivery outcome to
`egbe-os-product-routines`; a manual report does not create or advance its schedule.
