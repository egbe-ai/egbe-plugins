# Launch and pause

Launch requires authorization for the selected campaign(s), targeting,
daily USD budgets and delivery schedule. Read current provider state and resolve
pending mutations. Recheck wallet availability and provider moderation/serving
holds; report blocked eligibility instead of claiming the ads are running.

Activate in this order:
1. Group launch from DRAFT or PAUSED, with all child campaigns DRAFT or PAUSED.
2. Selected campaign launch with wallet authorization.
3. Selected creatives launch; this also starts their moderation.

For a DRAFT group or campaign whose start has passed, OS moves the start to
approximately one minute after the launch request, preserving its end, budget
and other settings. Future starts and PAUSED resumes stay unchanged. An expired
end window requires a newly authorized schedule; OS never extends it. Retry a
refused launch with the same key; no replacement objects are needed.

Activating a group containing active campaigns is rejected: first pause those
campaigns, activate the group, then explicitly launch selected campaigns. This
prevents group activation from bypassing campaign wallet authorization.
Campaign activation, a live campaign budget change, or creative activation beneath
an already active campaign reserves two daily budgets in Egbe wallet before the
provider change. A hold is a reservation, not a charge or a LinkedIn spend cap.
Daily budgets are pacing controls, not a promise of exact daily spend.

Read back group, campaign and creatives after launch and record intended status
separately from actual serving. Do not wait in a loop for impressions to call
configuration verified. This operation does not schedule future checks.

Pause the exact campaign with `POST /campaigns/{id}/pause` and a durable key.
Pause remains available when the mutation quota is exhausted. Campaign pause
releases its current reserve after readback; delayed actual spend can still settle.
Group pause stops its children and releases owned campaign holds, but preserves
their native individual status. Pause on an already DRAFT group, campaign or
creative is a verified no-op and returns DRAFT; it never activates an object
to make PAUSED attainable.
Pausing one creative may leave others delivering:
use campaign pause for a complete stop.
Record the requested trigger/authority in the existing change-log, then append
the affected ID, actual confirmation time and readback after success. Preserve
the known cause for this run; later balance or deadline changes do not replace it.
If the provider exposes no cause, record it as unknown. A later relaunch does not
reuse the earlier stop timestamp. A failed pause or stopped monitoring alone is
not a confirmed stop.

Archive/cleanup leaves DRAFT objects non-serving, pauses other owned
groups/campaigns/creatives and retains image/history
resources; it never changes another product's objects or deletes the Page.
