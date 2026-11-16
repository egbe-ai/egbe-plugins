# Lifecycle Capture contracts

Files live in private egbe-docs/research/market/work/lifecycle_capture/ unless explicitly
published. plan.json is the canonical signup plan. entry-points.json is
agent-reviewed discovery input; the runner validates it and renders the private
lifecycle-signups.md from the final plan.

## Reviewed entry points

```json
{
  "schema_version": 1,
  "competitors": [{
    "domain": "competitor.com",
    "selected": {
      "id": "product-details",
      "comparable_offer": "Software for the same buyer and job",
      "source_url": "https://competitor.com/product",
      "entry_url": "https://forms.example.com/product-details",
      "handoff_evidence": "The source page Request details CTA opens this form.",
      "kind": "lead_form",
      "entry_type": "details",
      "fields": [{"name": "email", "required": true}],
      "needs_phone": false,
      "needs_card": false,
      "reason": "Product-specific sales entry without phone or payment.",
      "instructions": ["Choose the comparable product", "Submit the planned email"],
      "stop_condition": "Stop at required phone, card, payment or CAPTCHA bypass.",
      "evidence": [{"url": "https://competitor.com/product", "observed_on": "2026-10-06", "detail": "Browser inspection of CTA and required fields."}]
    },
    "fallback": null,
    "skip_reason": null
  }]
}
```

Selected/fallback have the same shape and distinct ids. selected:null requires
skip_reason. Each competitor occurs once. source_url belongs to the competitor;
an external entry_url additionally needs handoff_evidence of the link/embed.
Evidence has URL, detail and non-future observed_on. Full URLs stay private.
needs_phone/needs_card are boolean or null (unknown). Fields have name and
boolean required; instructions include consent choices and the stopping point.
Phone/card-required entries cannot be subscribed to.
kind: newsletter, account, trial, waitlist, lead_form.
entry_type: details, materials, webinar, quiz, waitlist, account, trial, newsletter.

## Plan and subscriptions

plan.json contains schema_version:1, section_id, stable UUID capture_id, mailbox,
product_domain, subscriptions_path, day-3/day-14 targets and competitor entries
with domain, alias, selected, fallback, skip_reason, discovery_status, entry_points.
Before review, entry_points are search seeds only. Fresh workspace = new capture;
refresh preserves its id. OS POST /mail/lifecycle-aliases/reserve receives
capture_id/domains, resolves the authenticated mailbox, and returns mailbox and
aliases (domain-to-full-address mapping). Registry atomically reserves random
10–99 numbers uniquely per mailbox across products/hosts. Same capture/domain
is idempotent. HTTP409 means the pool cannot satisfy the batch. No Mailu accounts
are created. Already active legacy plans retain their existing aliases.

```json
{
  "schema_version": 1,
  "subscriptions": [{
    "domain": "competitor.com",
    "alias": "claw.name+98@egbe.app",
    "subscribed_on": "2026-10-06",
    "entry_id": "product-details",
    "entry_url": "https://forms.example.com/product-details",
    "kind": "lead_form",
    "confirmed": null,
    "notes": "The assigned human reported successful submission."
  }],
  "skipped": [{"domain": "other.com", "reason": "Relevant forms require a phone."}]
}
```

Alias matches the plan exactly. entry_url/kind match one selected/fallback;
entry_id can disambiguate. Fallback use needs fallback_reason. Unknown phone/card
needs require requirements_verified:true from the assigned human, whose access
to the planned aliases and mailbox has been verified. confirmed is
true/false/null (unknown or not observed). Optional unsubscribed_on falls between
subscription and today. Duplicate domains/aliases are invalid; a competitor
cannot be subscribed and skipped. Domains outside this capture are ignored.

## Human signup actions and portable milestones

operator-actions.json has schema_version:1, section_id, capture_id, product_domain,
actions and harvests. Each item has id, domain, kind, status
(pending/completed/skipped), due_on YYYY-MM-DD. Action kinds: signup, confirm,
unsubscribe. Harvest kinds: early, full. Stable ids: <domain>:<kind>.
No scheduler ids belong here.

Signup is due one day after reviewed handoff, preserving its deadline on rerun.
Confirmation action exists only when recorded as required/confirmed. Harvest
is due subscription date+3/+14. Successful per-domain listings at the due cutoff
complete milestones, including reported body/page gaps; failed listings leave
them pending. Unsubscribing before a target skips that later target.
Unsubscribe actions carry blocked_by:<domain>:full; reminders wait for the full
harvest. The caller installs bounded reminders and follow-ups. The file alone
is not proof they were installed.

## Published observations

Publication receipt status stays completed, phase started/harvested. Evidence
inputs/receipts add capture_id, observation_status (pending/partial/full),
target_days:14, observed_from, observed_through, days_covered, coverage_complete,
early_harvest_due_on and full_harvest_due_on. Sequences carry their own windows,
dates, listing_succeeded, listing_truncated and coverage_complete. Patterns carry
supporting windows/minimum days_covered, observation_status, coverage_complete
and eligible; recurring requires two distinct competitors. Eligible early
positive patterns can inform standalone future email sequences inside their
window; cadence needs at least seven days. They are not sources for the
replicate planner.

Full means the target duration was reached; coverage is separate. Skipped,
unsubscribed, awaiting signup and failed reads remain visible. Later harvests
replace current public evidence/report. Private immutable snapshots under
snapshots/<cutoff>/<evidence-sha256>/ retain evidence.json, result.md and
request.json for provenance of previously shared research.
