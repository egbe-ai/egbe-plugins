# Provider contract

## Boundary

Call Apify only through:

```text
GET  $OS_URL/scrape/apify/actors/{actor_id}
POST $OS_URL/scrape/apify/run
GET  $OS_URL/scrape/apify/runs/{run_id}
GET  $OS_URL/scrape/apify/datasets/{dataset_id}?limit={bounded_limit}
```

Authenticate with `Authorization: Bearer $OS_API_KEY`. Use asynchronous runs
and a stable `Idempotency-Key` derived from the context hash, collection epoch,
logical run key, actor ID, and actor-input hash. Record the returned run and
dataset IDs before polling.

The idempotency header identifies one logical start but is not a local
exactly-once guarantee. If the initial POST succeeds upstream and its response
is lost before `run_id` is persisted, this skill cannot prove locally whether a
run exists; retry safety then depends on durable gateway/upstream idempotency.
The runner persists the exact request and attempt before POST. A retry with no
handle replays only that saved request/key through the gateway's durable
submission record; pending reconciliation must not be bypassed with a new key.

`scripts/build-provider-inputs.py` is the only actor-input adapter. It emits the
exact keys in `apify-inputs-v1`, which were verified against the current public
actor contracts. `scripts/run-apify.py` rejects missing or extra keys and saves
a hash-bound actor-details snapshot before a paid start. Actor-details metadata
is provenance, not a promise of a machine-readable input schema; when an actor
contract changes, update and version the adapter rather than asking the agent
to guess fields.

## Actors and bounded run plan

- TikTok: `clockworks/tiktok-scraper`
- Instagram Reels: `apify/instagram-reel-scraper`

Use at most four logical runs:

1. `tiktok-discovery`: the bounded requested TikTok accounts and recent videos.
2. `instagram-discovery`: the bounded requested Instagram accounts and recent Reels.
3. `tiktok-enrichment`: selected TikTok URLs, with video,
   transcript/subtitles, and up to 20 comments.
4. `instagram-enrichment`: selected Reel URLs, with downloaded video,
   transcript, and shares where the actor exposes them.

These four keys and actor/platform/kind combinations are enforced by
`scripts/run-apify.py`; arbitrary keys or actors fail before a paid run starts.
`raw/manifest.json` and `receipt.json` retain each `logical_key`, allow no more
than four entries, and reject duplicate logical keys, run IDs, or dataset IDs.
Discovery is required for every platform with declared accounts. Enrichment is
optional: request it only when additional evidence is needed for the scoped
question, within the authorized collection budget. Discovery-only evidence can
answer a caption or metric question without another paid call. If needed comments,
transcript or visual evidence remain unavailable, disclose that gap instead of
claiming complete coverage of the question.

A terminal failed run can be disclosed as partial coverage alongside valid
successful datasets. Missing required discovery, or any running/uncertain saved
handle, blocks sealing. Once enrichment has started, preserve and settle its
handle too; optional does not mean it can disappear from the record.

The v1 adapter supports at most six account records total, 1–30 discovery results
per account, and 30 enrichment URLs total across both platforms. These are
execution limits, not evidence sufficiency rules.
Set the requested sample to fit the task and paid-call budget; disclose sampling
gaps. There is no required number of examples per account or quality score.

Do not start discovery without declared accounts or enrichment without frozen
selected observations. Batch the applicable accounts or selected URLs for a
platform into its one logical run. Cap actor results and dataset reads; enrichment
uses the frozen selection rather than silently replacing it with new examples.

The versioned actor-input builder accepts only the current fields needed for:

- TikTok discovery by profile and enrichment by post URL;
- TikTok video/cover downloads, subtitles or transcript, and comments;
- Instagram Reels discovery by usernames/profile URLs and enrichment by Reel
  URLs;
- Instagram transcript, downloaded video, and shares when the actor
  exposes them.

The exact input JSON is saved under `raw/`; `run-state.json` binds its path,
hash, contract version, sorted key list, and actor-metadata snapshot.

The context's `collection` parameters default to 30 results per account and a
60-day lookback. The builder can revise previews before submission, but the
runner fixes the actual lower date at the first POST attempt and preserves it
on resume. Both actors support a lower date; this adapter does not promise an
identical arbitrary provider start/end interval. See the official
[TikTok input schema](https://apify.com/clockworks/tiktok-scraper/input-schema) and
[Reels input schema](https://apify.com/apify/instagram-reel-scraper/input-schema).
TikTok's date filter is a charged option: changing result count alone is not a
complete price estimate. Dataset `--dataset-limit` bounds retrieval, not paid
collection.

The current TikTok actor exposes requested comments through each video's
`commentsDatasetURL`, not necessarily inline. `run-apify.py` resolves those
dataset IDs, reads them through OS, and stores the exact linked responses in
`raw/tiktok-enrichment-comments.json`. This is a secondary dataset read under
the existing TikTok enrichment run, not a fifth actor run. The actor shares one
comments dataset across all videos of the run, so it is read with the run's
`--dataset-limit`. The gateway grants that dataset only after the run's own
video dataset was read through OS. `run-apify.py` reads it before the comments,
and a retry from saved output reads it again so a failed grant is retried.
Normalization must not claim TikTok comment coverage unless that hash-bound
bundle was processed.

## Raw evidence

Save every OS response as a raw JSON file before normalization. Preserve actor
ID, run ID, dataset ID, collection time, input hash, and raw-file hash. Do not
strip provider fields before the raw file is persisted.

Continue polling transitional `READY`, `RUNNING`, `TIMING-OUT`, and `ABORTING`
states. Treat only final `FAILED`, `ABORTED`, `TIMED-OUT`, or `TIMED_OUT` states
as terminal failures eligible for the explicit restart flow below.

If a run fails, preserve its terminal status. Successful datasets may still
support a partial result; record the exact gap
`Provider collection <key> ended with <STATUS>.` in the analysis. If no dataset
was successfully collected, report a collection failure, not no-data research.
Do not replace missing evidence with generic web search, another actor, a direct
provider API, or invented observations. Discovery may use OS web search to
locate public account handles and canonical profile URLs; it is not substitute
trend evidence.

A normal provider retry keeps the saved terminal failure; it cannot silently
spend on a replacement run. After inspecting the failure, explicitly
start a clean collection epoch with the exact failed handle:

```bash
python3 "$ORGANIC_TREND_SKILL_ROOT/scripts/run-state.py" \
  --runtime-root "$RUNTIME_ROOT" restart-failed-collection \
  --key "$FAILED_LOGICAL_KEY" --run-id "$FAILED_RUN_ID"
```

The command refuses an active/successful or mismatched handle, archives the
whole failed collection, and resets every provider-derived step before any new
paid call.

## Media evidence

When audiovisual evidence is needed, run `scripts/prepare-visual-evidence.py` for
the selected observations to inspect that have a provider `media_url`. It downloads
the media into the runtime root and extracts dense opening frames at approximately 0.0, 0.5, 1.5,
3.0, and 5.0 seconds plus middle, later, and ending samples when duration is
known. The canonical OS multimodal analyzer inspects those frames before the
analysis is written. A transcript can support spoken words but cannot establish
what appeared on screen.

Only `prepare-visual-evidence.py` may establish local visual evidence for this
workflow. It binds the provider media URL, downloaded video, fixed frame
samples, and their hashes. The default aggregate downloaded-media budget is 1
GiB across the collection; an individual video remains capped at 250 MiB.

If media cannot be retrieved or inspected, set the visual fields to
`unavailable` and record the evidence gap. Never turn a caption, cover, metric,
or transcript into an observed visual claim.

## Freshness and cache

Reuse matching successful runs on retry without changing collection times.
Assess whether the evidence is recent enough for the question; age alone does
not authorize spending on another collection. An explicitly requested refresh
archives the previous epoch and uses new idempotency keys. `init` never does this
silently, and active/uncertain starts must be resolved before refresh.
