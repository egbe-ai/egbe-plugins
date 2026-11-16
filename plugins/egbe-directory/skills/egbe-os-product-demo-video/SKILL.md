---
name: egbe-os-product-demo-video
description: Record a real product walkthrough and produce a video and poster.
metadata:
  egbe-when: "Offer when a homepage or pitch would benefit from showing the product in action."
  egbe-visible: "true"
  egbe-title: "Product demo video"
  egbe-description: "Show your product in action with a clear walkthrough video and a preview image."
  egbe-category: "Product & design"
---

<!-- egbe-mcp-connection:v1 -->
This skill comes with the Egbe plugin. If this project has its own installed copy
of the skill, use that copy instead. Otherwise make every Egbe API call it
describes with the Egbe connector: `egbe_read` for GET and `egbe_write` for POST,
PUT, PATCH and DELETE (with `method`). Pass the API path (for example
`/me/limits`), query parameters in `query` and the JSON body in `body`. Leave out `OS_URL`, the Authorization header, `.env.local`,
`egbe-curl.py` and catalog update checks; the connection authenticates and
identifies the request. Also pass the `business` that `egbe_setup` returned.
Files this skill refers to are next to this `SKILL.md`, except any listed under
"Files downloaded on demand".

A step that needs a local project key or a bundled script, such as a git push or
a local deploy command, needs a set-up project workspace. In a persistent
project workspace that is not set up yet, set it up as the `egbe-setup` skill's
project setup describes.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.

If the connector's tools (`egbe_read` and the other `egbe_*` tools) are not
available, the plugin's connector is not signed in on this Claude account. Tell
the founder how to connect it, as the `egbe-setup` skill describes, rather than
saying Egbe is unavailable.

The connector's tools work even where this environment's shell cannot reach
Egbe: their calls travel through Claude, not through the shell's network. A step
that runs in the shell, such as a bundled script, a `git push` to Egbe's Git
endpoint or a deploy upload, needs the shell to reach the Egbe host
(`os.hz.egbe.dev`). If a proxy or allowlist refuses that request before Egbe
answers, for example HTTP 403 on CONNECT or curl status `000`, follow the Claude
network recovery in
`egbe_skill(name="egbe-os-quickstart", resource="references/environment.md")`:
the founder allows that host for Claude's code execution or continues in Claude
Code on their own computer. Until the shell step succeeds, do not report the work
as published: a Claude Artifact or a local preview is not an Egbe deployment.


# Record a product demo

Keep the recording context, source captures, final media and checks together in
`egbe-docs/marketing/packs/<video-id>/`; version source captures in `work/` and use
the existing plan or asset notes rather than creating a separate document per step.
Keep credential-bearing captures out of Git and public exports.

Show the real path from customer intent to a useful result. Deliver a playable
video and poster; embedding or publishing them is a separate action unless
included in the request.

## Prepare the walkthrough

Read the requested or already agreed audience, destination and behavior, then
inspect the actual product. Resolve consequential gaps without reopening accepted
choices. Capture the shortest coherent journey that demonstrates the requested
result. Use a local or staging app when appropriate; for an existing
deployment, confirm its serving revision through `egbe-os-deploy` rather than guessing
a hostname.

Use synthetic, non-sensitive content and a test identity only if the journey
needs authentication. Reuse an authorized identity when possible. A public
tool needs neither signup nor a mailbox. Do not generate paid transactions,
send outreach or alter real customer records just to make a demo. Prepare any
necessary test state within the approved task scope.

## Capture real behavior

Use the harness's available browser/recording tools. If they cannot record,
follow [Recording options](references/recording.md). Identify the precise
missing dependency or permission if recording remains unavailable; screenshots
or AI-generated footage are not a completed recording.

Start from a ready page, perform meaningful actions and wait for visible
outcomes instead of relying only on fixed sleeps. Keep text legible at the
target size and let viewers see the result. If the app fails, record the defect
as a blocker; do not conceal it with a mock success screen. Cut idle/setup time,
not steps essential to understanding what the product really does.

## Verify and deliver

Inspect playback from start to finish and the poster at the intended display
size: content is readable, the promised result is visible, no private data is
exposed, and no black/error frames or accidental dialogs remain. Confirm file
duration, codec and dimensions, not just existence. Keep source revision/URL
and walkthrough steps with the project's existing asset records so another
session can reproduce the capture.

Store the video and poster in the requested destination; for embedding, use
the product's existing public asset convention. Check the actual browser
player, fallback poster and mobile layout. Provide controls or a pause option
for looping content; respect reduced motion and add captions when speech
carries meaning. Report local file paths, verified outcome and any limitations.
Publish only when authorized, using `egbe-os-git` and `egbe-os-deploy` for an Egbe-hosted app.
