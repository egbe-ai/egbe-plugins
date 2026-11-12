# Contact sourcing operations

## Connection and commands

Requires Node, `OS_URL` and `OS_API_KEY`. All commands accept
`--env-file <path>`; exported environment values take precedence. The shared
connection helper supplies agent identity headers when configured.

Authenticated routes:

```text
POST $OS_URL/outreach/apollo/people/search
POST $OS_URL/outreach/apollo/people/match
POST $OS_URL/outreach/apollo/people/bulk_match
POST $OS_URL/search/places
POST $OS_URL/tools/places/details
```

Use the installed skill directory for scripts and the project's durable output
directory for data. Shell wrappers with the same four names forward to Node.

```bash
node "$SKILL_DIR/scripts/search.js" --titles "VP Sales,Director of Sales" \
  --employee-ranges "11,50;51,200" --max-results 20 --output "$WORK_DIR/preview.json"
node "$SKILL_DIR/scripts/enrich.js" --input "$WORK_DIR/preview.json" \
  --output "$WORK_DIR/leads.json"
node "$SKILL_DIR/scripts/find-leads.js" --config "$WORK_DIR/search-config.json" \
  --max-results 20 --time-budget-ms 90000 --output "$WORK_DIR/leads.json"
node "$SKILL_DIR/scripts/places-leads.js" --queries "accountants in Lisbon;accountants in Porto" \
  --max-places 40 --email-preference generic --output "$WORK_DIR/places-leads.json"
```

These are live operations, not dry runs. No operation includes sending.
`--verbose` writes progress to stderr. Without `--output`, final JSON is stdout,
but there is no durable checkpoint if the process is killed.

## Search inputs

`search` and `find-leads` accept the same flags below. Lists are comma- or
semicolon-separated except employee ranges, which use semicolons between ranges.
Alternatively `--config` accepts a raw search object or `{"search": {...}}`;
config mode uses that object, not additional search-filter flags.

| Flag | Apollo field |
| --- | --- |
| `--titles`, `--not-titles` | `person_titles`, `person_not_titles` |
| `--seniorities` | `person_seniorities` |
| `--locations`, `--not-locations` | `person_locations`, `person_not_locations` |
| `--domains` | `q_organization_domains_list` |
| `--org-locations`, `--org-names` | `organization_locations`, `organization_names` |
| `--employee-ranges` | `organization_num_employees_ranges` (e.g. `["11,50","51,200"]`) |
| `--keywords`, `--industries` | `keywords`, `industry_tag_ids` |
| `--technologies` | `currently_using_any_of_technology_uids` |
| `--email-status` | `contact_email_status` (search filter) |

`--max-results` is a positive integer (default 50 for preview, 100 for combined
search/enrichment). The client requests pages of 100, caps pagination at 500 pages,
deduplicates IDs, honors supplied total pages and stops on short/empty pages.
Missing pagination does not mean there is only one page. A repeated page is an
incomplete result, not proof that the source is exhausted.

`search` outputs `{people: [...], meta: {...}}`, preserving provider records
including IDs and structured organization fields for enrichment. Display name
alone is not sufficient enrichment input.

## Enrichment and result contract

`enrich --input` accepts an array, `{people: [...]}`, compatible `{leads: [...]}`,
or the saved partial Apollo output. Each new input needs one of:

- `id` or `apollo_id`;
- `linkedin_url`;
- `first_name` and `last_name`, with a domain or company name.

Organization fields can be nested under `organization` or supplied as
`organization_name` / `company_name` / `company` and
`domain` / `company_domain` / `website`. Website URLs normalize to hostnames.
Unknown names are not fabricated from display names. The entire input is validated
before enrichment requests. An empty input is a valid completed empty operation.

The client batches at most ten people per call. `--email-status-filter` controls
retained enrichment results (default `verified,likely`; an empty string retains
all statuses). This is a selection setting, not a verification guarantee.
It is distinct from the search flag `--email-status`.

`find-leads` and `enrich` return:

```json
{
  "leads": [],
  "meta": {
    "source": "apollo",
    "complete": false,
    "stop_reason": "daily_quota",
    "enriched": 0,
    "enriched_count": 0,
    "processed_count": 0,
    "leads_with_email": 0,
    "email_status_filter": ["verified", "likely"],
    "drops": {"no_email": 0, "email_status": 0, "duplicate_email": 0},
    "not_enriched": 1,
    "not_enriched_people": [{"id": "provider-person-id"}]
  }
}
```

Leads have normalized `email`, available `first_name`, `last_name`,
`company_name`, `website`, `email_status`, `apollo_id`, and optional role,
location, company-size and LinkedIn fields. Empty fields stay empty. Addresses
are deduplicated, but a nonempty address is not a delivery check.

`processed_count` counts inputs in completed enrichment batches; `enriched`
and its `enriched_count` alias count non-null provider matches, before output
filtering. Null matches and matched people without emails are not queued for
automatic re-enrichment. `not_enriched` and `not_enriched_people` describe only
unprocessed inputs, not unmatched or status-filtered people. Zero results use
the same fields, rather than a special success shape.

Combined search includes `total_found`, `search_params`, `max_results`,
`search_complete`, `search_stop_reason`, `search_next_page` and `searched_at`.
Preview completion describes search only; its `not_enriched` is zero because no
enrichment was requested. `max_results` means the requested bound was met, not
that the entire audience was exhausted.

## Bounded execution and recovery

All commands accept a positive `--time-budget-ms` (default 90000). Apollo allows
at most four transport retries, honors Retry-After within that budget, and has no
second unbounded batch retry loop. Daily quota/configuration limits stop without
retrying. Transient HTTP failures may retry; transport/network uncertainty stops
the operation with pending inputs. A request may already have incurred cost when
its response is lost; recovery cannot promise exactly-once provider billing.

Exit codes:

- `0`: requested operation completed, including a genuine zero-result search.
- `2`: structured incomplete result; inspect the saved JSON even with no leads.
- `1`: invalid input/credentials or a local execution failure. Inspect an existing
  checkpoint rather than assuming it contains nothing or blindly replacing it.

Reasons include `completed`, `search_exhausted`, `max_results`, `daily_quota`,
`rate_limited`, `time_budget`, `authorization`, `provider_error`,
`network_error`, `invalid_response`, `repeated_page`, and `max_pages`.
A checkpoint left with `in_progress` means the process did not finish; it is
never success. Missing OS credentials fail before requests. Check the OS key,
scope or upstream configuration for 401/403 or Apollo configuration failures.
Do not widen the audience or increase spending merely to turn an empty result
into a nonempty one.

With `--output`, writes replace JSON atomically before work and after every
completed page/batch. To continue already-found inputs:

```bash
node "$SKILL_DIR/scripts/enrich.js" --input "$WORK_DIR/leads.json" \
  --output "$WORK_DIR/leads.json" --time-budget-ms 90000
```

This keeps existing leads and processes only `meta.not_enriched_people`; it
does not repeat search or successful batches. Preserve the existing email filter
when resuming: prior filtered provider matches are not stored for re-filtering.
If search itself was incomplete, enrichment does not claim the missing search
pages finished. `search_next_page` is diagnostic context, not an automatic
search-resume token.

Subprocess callers must give the client a smaller budget than their own timeout
(e.g. 90 seconds inside 120 seconds), read output on exit 2 and on interruption,
and preserve partial state before removing temporary directories. A hard kill
can leave the in-flight batch uncertain; completed checkpoints remain available.

## Places inputs, status and limits

`--queries` is a required semicolon-separated list; each search requests up to
20 results. `--exclude-categories` supplies optional name/type substring
exclusions. `--max-places` defaults to 60 and is clamped to a local cap of 200
unique places across the run. These are work bounds, not remaining provider quota.

Registry defaults are separate daily resources: Apollo searches 100 and
enrichments 200 people; Places searches, details and reviews each 200. Actual
project limits and operation charges may differ. One search and one details
request consume their respective resource, not a shared 200-request pool.
This script does not call reviews. A live preview and a Places sweep are not
free workarounds for quota or cost approval.

The pipeline gets listings, details and the website homepage, `/contact` and
`/about`. Each website/redirect is checked for public DNS/IPs and pinned to the
checked address; private, internal and credential-bearing URLs are refused.
Website requests carry no OS credentials. Trap-address and malformed-address
filters remain separate from optional ranking.

`--email-preference personal|generic|first` selects a ranking heuristic (default
`personal`). “Personal” only describes the local-part shape; it does not prove
ownership, recipient suitability or that a role mailbox is inferior. Name
extraction is an English-text heuristic: candidates are in `name_candidate` and
`name_candidate_source`, not silently filled into `first_name`. Address parsing
is also labeled heuristic. Check these candidates before using them in copy.

Places returns `leads/meta` with `source: "places"` and every email
`email_status: "unverified"`. It does not enrich Apollo people:
`enriched` and `not_enriched` are zero; `sites_scraped` is a separate counter.
`drops` separates details failures, unreadable websites, category exclusions,
missing websites/emails and duplicates. `pending_queries` and
`not_processed_places` retain unfinished work, with `complete: false` for
provider/website failures. Empty completed search, all failed searches and
filtered results are distinct. Places checkpoints are retained evidence;
`enrich` is not a Places recovery command. No automatic Places replay is
implemented; review the pending items before another paid sweep.
