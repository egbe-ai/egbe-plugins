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
Where this skill sends an `Idempotency-Key` header, pass the same value as
`idempotency_key` and reuse it when retrying. A result with a `continuation`
holds one part of a long body; read the next part with `egbe_read`, the same
`path` and `business`, and that `continuation`.
Read bundled files beside this `SKILL.md`. For published skill resources on
Egbe OS, use `egbe_skill`. Follow "Files downloaded on demand" for listed downloads.

Publishing works through the connector: commit the app's files with the JSON
commit requests in `egbe-os-git` ("Without a terminal") and deploy the returned
commit SHA; no git push or workspace setup is needed. A step that needs a local
project key or a bundled script, such as a local `npx convex deploy`, needs a
set-up project workspace. In a persistent
project workspace that is not set up yet, set it up as the `egbe-setup` skill's
project setup describes.
Without such a workspace, or if it refuses, tell the founder that this step needs
an agent with a set-up project folder, and continue with the rest of the work.

If the connector's tools (`egbe_read` and the other `egbe_*` tools) are not
available, the plugin's connector is not signed in for this agent. Tell
the founder how to connect it, as the `egbe-setup` skill describes, rather than
saying Egbe is unavailable.

The connector's tools work even where this environment's shell cannot reach
Egbe: their calls travel through this agent's connection, not through the
shell's network. A step that runs in the shell, such as a bundled script, a `git
push` to Egbe's Git endpoint or a deploy upload, needs the shell to reach the
Egbe host (`os.hz.egbe.dev`). If a proxy or allowlist refuses that request
before Egbe answers, for example HTTP 403 on CONNECT or curl status `000`, tell
the founder: they allow that host in this agent's network settings or continue
with an agent on their own computer. Code can also be published without the
shell by committing through the connector (`egbe-os-git`, "Without a terminal").
Until the shell step or that commit and its deploy succeed, do not report the
work as published: a preview in this agent or on this computer is not an Egbe
deployment.

The harness can also refuse a step before Egbe answers: a denied file read or
command (`EPERM`, `operation not permitted`), a certificate error, or a
connector call that fails as a whole with HTTP 403. Egbe's own refusals of an
API request come back as a result with a `status` and Egbe's `message`, and the
`egbe_skill` tool never answers 403. Egbe refuses a whole call with 403 only for
a browser `Origin` it does not accept, so such a 403 most likely comes from the
harness, a proxy or a policy in front of Egbe. Don't retry it in a loop, route
around it or disable certificate verification. If `egbe_skill` was refused, read
that skill from an installed Egbe catalog or plugin copy, if this session has
one. Name the blocked file, command, host or tool and ask the founder to allow
it, or to trust the host through the environment's network setting. Then
continue the work that doesn't need it and say what waits on that permission.
While `egbe_skill` works, `egbe-os-quickstart`'s `references/environment.md`
lists these cases.


# Record a product demo

Keep the recording context, source captures, final media and checks together in
`egbe-docs/marketing/packs/<video-id>/`; version source captures in `work/` and use
the existing plan or asset notes rather than creating a separate document per step.
Keep credential-bearing captures out of Git and public exports.

Show the real path from customer intent to a useful result. Deliver a playable
video and poster; embedding or publishing them is a separate action unless
included in the request.

## Through the Egbe connector

Egbe does not record video. Through the connector you can plan the walkthrough,
confirm the serving revision with `egbe-os-deploy` and keep the notes in Egbe's
artifact store. Recording needs browser and recording tools in your own
environment, or a set-up project workspace (in a persistent project workspace
not set up yet, call `egbe_local_setup`). Without either, tell the founder;
screenshots or a description are not a recording.

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
