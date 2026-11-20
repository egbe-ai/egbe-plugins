# Compose destination checks with network requirements

Use the requested or already planned networks and actual destination paths, not
every network available in Egbe. Read relevant offer/campaign records, resolving
material URL or promise conflicts through read-only readback when available.
No ad account or traffic is needed to inspect a known public destination.
Deduplicate identical paths while preserving locale, device or offer differences.

Read only the applicable destination reference from the installed bundle:

| Network | Skill | Reference |
| --- | --- | --- |
| Google | `egbe-os-google-ads` | `references/search-assets.md#destination-and-attribution` |
| Meta | `egbe-os-meta-ads` | `references/destination-requirements.md` |
| Reddit | `egbe-os-reddit-ads` | `references/destination-requirements.md` |
| LinkedIn | `egbe-os-linkedin-ads` | `references/destination-requirements.md` |
| OpenAI | `egbe-os-openai-ads` | `references/destination-requirements.md` |

Discover a missing bundle through `GET /skills` and its returned bundle URL.
If the delivered reference is still unavailable after refreshing it, complete
supported checks and name the missing coverage; do not invent policy or load
every launch workflow. For a material policy finding, verify the relevant
official source and record its date/applicability.

Reuse the common inspection evidence and return one scoped result. Inspect an
ad's promise/URL only as input to the visitor path; targeting, bids, configuration,
conversion instrumentation and optimization are not destination checks. Provider
moderation alone neither proves nor disproves path readiness. Policy uncertainty
is not confirmed rejection.

Keep the skill's read-only boundary, including forms, bookings and checkout.
Stop at unavailable or mutating steps and state what remains unverified instead
of marking the whole site broken. Reuse the caller's evidence/results when this
is a nested check; do not require another report pack or rerun unchanged paths.
