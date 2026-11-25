# Offer, start or resume a loop

Offer a fitting loop at setup or after a verified milestone. Start or resume
a loop the founder names or opens from the Dashboard.

## Offer a Business Loop

Use this at setup and whenever project work reaches a verified milestone that a
loop could carry forward. Examples of such milestones:

- a product or page is first served to visitors;
- sign-in, analytics or payments first work in the live product;
- an ad or cold email campaign is built or launched;
- market, competitor or customer research is delivered;
- the first signups, replies or sales arrive.

A milestone counts once its own verification has passed, not when it is only
planned or drafted. The offer is the reply's next step, not an extra list of
recommendations. Offer at most one loop per milestone. Offer only in a
conversation with the founder: a scheduled or unattended run records the
milestone in the existing plan for the next conversation instead.

### Check what already exists

Read this business's `loop_offers` record in the project's
`egbe-docs/routines.json`, the plans in `egbe-docs/loops/` and, when the
business has a connected OS, its saved loops with `GET /loops`. A good saved
match already has a command and Dashboard link.

Make no offer when the founder asked you to stop suggesting things, declined or
paused recurring work in general, or declined two offers in a row, or when the
business's `product_reporting` entry has `enabled: false`. Wait until they ask.
Otherwise:

- If an active or `accepted` loop covers the goal, don't offer a new one. Record
  the milestone in that loop's plan and offer to continue it at its next
  checkpoint.
- If the founder declined or paused this loop, don't offer it again unless they
  ask. A different loop that fits a new milestone can still be offered.
- An unanswered offer stays open. Don't repeat it; you can mention it once when
  a later milestone makes it more useful.
- A `no-signal` entry means the loop was set aside because no useful signal
  existed yet. Offer it once the milestone provides that signal.
- If the private loop list is unavailable, use the local records and mention the
  missing lookup only if it affects the choice.

### Choose the loop

Read the published `references/presets/index.json` from
`egbe-os-product-routines` with `egbe_skill(name="egbe-os-product-routines",
resource="references/presets/index.json")`, or with
`GET /skills/egbe-os-product-routines/resources/references/presets/index.json`
on the connected OS. An installed copy of the skill also works. Each preset's
`offerWhen` lists the project states it fits. Compare them with what was just
verified and with the founder's goal; the milestone alone does not decide it.
Consider evidence from outside Egbe too: an existing website may already have
paying customers.

The same skill's `references/catalog.md` lists operations for custom loops. When
the fitting routine has a clear decision specific to the business, describe that
custom loop in the offer. For example, repeated objections to a pilot can guide
the next invitation. If **egbe-os-loop-engineering** already saved it during the
work, include its Dashboard link. If no loop fits or the index is unavailable,
suggest a suitable routine in words. If a missing fact changes the choice, ask
one focused question. If there is no useful recurring signal yet, suggest a
first action that could produce one and record `no-signal` for the loop it
would lead to.

### Make the offer

Write one short message in the founder's language. Put it where the reply gives
its next step.

1. If the founder has not used a loop before, explain in one sentence what it
   is: a repeating cycle in which I do the work, check one concrete result, and
   choose the next step from what happened. Its diagram is in the Dashboard.
2. Explain why now: connect it to what was just done and the observation behind
   the choice.
3. Describe what I would do in each cycle, what the founder gets and when the
   first result can be checked.
4. Name what stays with the founder: decisions, spending, publishing, outreach.
5. Link the diagram and ask one direct question, such as "Shall I set it up?"

Offer one loop. Name an alternative in the same message only when it serves a
clearly different need, and say in one line what it would do instead. Record
each named loop under its own key; one "no" declines both.

Link a preset to its Dashboard diagram. Read `data.create_project.url` from
`GET /` on the connected OS; reuse an earlier response. Replace its trailing
`/new` with `/businesses/{public_id}/loops/{preset_id}`. Take `data.public_id`
from authenticated `GET /context/product` and the ID from the catalog. Through
MCP, use `egbe_read` for both requests with the selected `business`. URL-encode
each path segment. If either value is unavailable, omit the link.

### Record the outcome

Keep `loop_offers` in versioned `egbe-docs/routines.json`, keyed by verified
business ID and then by the offered loop's ID: the preset ID, or `mine/<id>`
for a custom loop. Preserve unrelated entries:

```json
{
  "loop_offers": {
    "<business-id>": {
      "first-user-result": {
        "status": "accepted",
        "at": "2026-11-24",
        "milestone": "Signup form live with analytics; 3 of 14 new users created a first invoice",
        "command": "Run Egbe Loop mine/first-user-result"
      }
    }
  }
}
```

`status` is `offered`, `accepted`, `declined` or `no-signal`. Update the same
entry when the founder answers; after an accepted preset, `command` holds the
saved business command. Synchronize project files as `EGBE.md` describes.
Without a project workspace, keep the outcome in the project's records through
the connector's artifact exchange when it is available.

### After the founder answers

- **Yes to a preset.** The answer authorizes saving the loop for this business
  so that the founder sees it in the Dashboard. Read the preset's
  `references/presets/<id>.json` and save it with **egbe-os-loop-engineering** →
  `references/save-loop.md` under the same ID: base revision `0`, `command` set
  to `Run Egbe Loop mine/<id>`, `sourcePreset` with the preset's `id` and
  `version`, and a reason that quotes the founder's agreement. Leave out
  `offerWhen`; keep the rest of the method unchanged. The business's audience,
  budget and first check belong in the launch plan. If that ID already holds a
  loop that covers the decision, reuse it. Then follow
  [Start or resume a Dashboard loop](#start-or-resume-a-dashboard-loop) with the
  saved `mine/<id>` command to agree the first action and any schedule.
- **Yes to a custom loop.** Save it, or its agreed limits, with
  **egbe-os-loop-engineering**, then continue with
  [Start or resume a Dashboard loop](#start-or-resume-a-dashboard-loop).
- **No.** Record `declined` with the founder's reason, if they gave one, and
  continue the product work. A custom loop that loop-engineering saved earlier
  stays in the Dashboard unless the founder asks to remove it.

The founder's yes covers saving the loop and agreeing its launch. Starting
work, enabling a schedule, spending, publishing and outreach still need the
agreement that [Start or resume a Dashboard loop](#start-or-resume-a-dashboard-loop)
and the project's decision rules require. If the founder's answer explicitly
includes them, record it as that agreement; don't ask again.

Without a persistent project workspace, the connector can still save the loop.
For running it, offer a manual review in this chat and give the founder the
loop's command to take to their project agent.

## Start or resume a Dashboard loop

Use the selected business and the exact command from its Dashboard. Look in its `egbe-docs/` for an existing agreement and last verified result. Keep the pause state, permissions and limits. A repeated command can resume manual work.

### Find the right method

An exact ID or card URL selects the method even during an informal discussion. A bare ID or `/loops/<id>` card selects the published preset; `mine/<id>` or `/loops/mine/<id>` selects the business loop. Apply the requested method even if a related private copy or shared original exists. Use title matching only when the founder supplied neither an ID nor a link.

- **`Run Egbe Loop mine/<id>`** opens this business's saved loop. Read `GET /loops/<id>?format=markdown`, including on a fresh chat and before each scheduled continuation. With MCP pass `business` and `query={"format":"markdown"}` to `egbe_read`. Compare `data.revision` to the last revision in the plan. When `data.sourcePreset.version` is older than that preset's version in the catalog, mention the newer method once and offer to apply it with **egbe-os-loop-engineering**. Apply the current method from `data.markdown` to the outstanding checkpoint. A changed diagram cannot approve new spending or restart a paused job.

  If the private definition is unavailable, tell the founder what local records establish and what still needs the named loop. A question about those records does not replace or complete the task. Keep the dependent step pending in the existing plan unless the founder changes it. Note who can restore access, what they need to do, and when to check the definition again under the latest agreement.
- **`Run Egbe Loop <preset-id>`** opens the published preset. Resume an existing plan even if the shared preset changed or left the catalog. If the business already has a saved `mine/<id>` whose `sourcePreset.id` matches, for example from an accepted offer, tell the founder and ask whether to continue that loop or try the published method; don't switch silently. For a new launch, read `references/presets/index.md` in `egbe-os-product-routines` and its linked `references/presets/<id>.md`. Use `egbe_skill(name="egbe-os-product-routines", resource=<path>)` or `GET /skills/egbe-os-product-routines/resources/<path>`; the installed copy also works offline.
- **A title** may match a saved plan, a business loop from `GET /loops`, or a shared preset. If distinct matches share a name, offer their commands and let the founder choose. If a catalog could not be read, say which one needs checking.

### Agree the launch

Use the loop and `egbe-docs/playbooks/product/business-loop.md` to choose a starting point that fits the project. Trying a shared preset with the founder's own audience, sources, budget or first check uses the existing preset and a local plan. A preset the founder accepted through [Offer a Business Loop](#offer-a-business-loop) is already saved for the business; continue under its `mine/<id>` command.

For a new launch, use **Scope and limits** to propose the work, time and budget. Propose a first action, its owner, and the result that determines the next step. Offer a manual launch or a schedule that matches the next evidence. Get the founder's agreement before starting. A planning-only conversation ends with the proposed plan. On resumption the recorded agreement applies. Bring only changes that need the founder's decision back for approval, such as raising a spending cap.

Save the agreement and checkpoint in the existing plan. For new plans use `egbe-docs/loops/<preset-id>.md` for a shared preset and `egbe-docs/loops/mine/<id>.md` for a private loop. Keep the full command, business ID, title and shared preset version or business revision. After an authorized action, record its result or the pending founder action. If results call for improving or adapting the definition, use **egbe-os-loop-engineering**.

For scheduled continuation use [Business Loop and reporting schedules](product-reporting.md) with the actual plan path. Identify the responsibility by both business and full loop command. Record and reconcile its own native job, pause state, last occurrence and next check in that loop's plan. Repeating the command reuses the same job. Two different loops can run on different cadences.
