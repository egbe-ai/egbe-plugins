# Analysis and output contract

## Normalized source evidence

`normalize-videos.py` writes `normalized/videos.json` with schema version 1,
`analysis_contract_version: "evidence-v5"`, generation time, source manifest hash,
selection gaps and stable observation IDs. Observations retain canonical URLs,
account context, publication time, caption, nullable provider metrics, comments,
sound metadata and media availability. Descriptive comparisons are not causal
attribution or an eligibility score.

`collection_window` records the frozen reference time and lower date;
`time_window_counts` separates `in_window`, `outside_window` and `unknown_date`.
Each observation has `time_window_status`. Out-of-window and unknown-date rows
remain inspectable but do not affect account medians or enter selection and
enrichment. Unknown dates are not represented as proven dates outside the window.

The requested sample is frozen in hash-bound `normalized/selection.json` before
enrichment. Its account-balanced resource cap is not a best-performing ranking
and has no minimum number per account. Enrichment may add evidence but cannot
silently replace selected IDs. Preserve normalized selection gaps in the analysis.

Media paths are runtime-relative and confined to that directory. Local video
and frames have exact `artifact_sha256` entries and `visual_preparation` proof
from `prepare-visual-evidence.py`. A provider `media_url` is distinct from its
`cover_url`; a cover cannot establish the video's opening. Validation checks
file hashes and provider-media provenance, not just path existence.

Every comment has a stable `comment_id`, derived from its provider ID or exact
text hash. Do not hand-edit normalized data or invent identities.

## Analysis evidence-v5

Write `analysis.json` using the actual normalized file hash:

```json
{
  "schema_version": 1,
  "analysis_contract_version": "evidence-v5",
  "source_normalized_sha256": "<sha256>",
  "generated_at": "2026-11-03T12:15:00Z",
  "summary": "Answer to the scoped question, with the main limitation",
  "videos": [
    {
      "observation_id": "tiktok:123",
      "url": "https://www.tiktok.com/@example/video/123",
      "message": {
        "status": "observed",
        "modality": "caption",
        "text": "The caption presents a product workflow",
        "evidence_refs": ["caption"]
      }
    }
  ],
  "synthesis": {
    "findings": [
      {
        "text": "A source-grounded finding, not an inferred performance cause",
        "supporting_evidence_refs": ["tiktok:123#message"]
      }
    ],
    "adaptations": [
      {
        "name": "An adaptation for this product",
        "text": "The proposed treatment, separate from the source observation",
        "reason": "Why the observed mechanism fits the question and available assets",
        "source_observation_ids": ["tiktok:123"]
      }
    ]
  },
  "evidence_gaps": ["Media was unavailable; no visual-opening claim is made"]
}
```

`summary`, `videos`, `synthesis` and `evidence_gaps` are required. Findings and
adaptations may be empty. Include the selected observations actually analyzed;
omitted selected observations make coverage partial. Unknown or duplicate IDs
and mismatched URLs/hashes are errors, not evidence gaps.

### Optional analytical fields

Use only fields relevant to the question and supported by evidence:

| Field | Shape and evidence |
| --- | --- |
| `thumb_stop` | `status`, `text`, `evidence_refs`; observed opening requires inspected frames. |
| `hook` | Same plus `modality: visual|verbal|mixed`; frames for visual, transcript for verbal, both for mixed. |
| `format`, `message`, `cta` | Same with `modality: visual|verbal|mixed|caption`; describe only what that modality establishes. A caption may describe a format but cannot prove unseen execution. |
| `proof_reference` | `status`, `claim`, `mechanism`, `evidence_refs`; preserve a source's attributed claim rather than endorsing it. |
| `sound` | Source `id`, `name`, `author` when present; no age-derived lifecycle label. |
| `comment_analysis` | Entries with actual `comment_id`, `relevance: relevant|uncertain|irrelevant`, `reason`; nonempty `insight` only for relevant comments. |

An unavailable axis has `status: unavailable`, empty text (or claim/mechanism),
and no refs. Alternatively omit an unused axis. There is no seven-axis quota,
required comment count, creative count or impact score.

When a canonical per-video media receipt exists, attach its
`multimodal_receipt_sha256` even when using only its source caption. Frame refs
must appear in it; `transcript` must be available
and hash-bound. The validator checks the current frames/transcript and rejects
forged or stale proof. Caption-only analysis does not need a media receipt.
Preserve the receipt's exact analysis gaps in `evidence_gaps`. The literal
`caption` reference is valid for a source caption, not speech or visual content.
A source proof remains independently unverified unless separate
evidence establishes it.

Findings cite `<observation_id>#<axis>` for an observed axis, or the source's
`metrics`, `caption`, `sound`, or `comment:<comment_id>` evidence. References
must exist; a convenient reference does not by itself justify a conclusion.
Adaptations cite real analyzed source IDs and explain the relevance in `reason`.
Source links and quoted audience comments are resolved from canonical IDs.

## Generated outputs and coverage

`render-result.py` produces a readable section body in `result.md`, including
findings, adaptations, source evidence and limitations. Do not expose provider
handles, raw receipt internals or model usage as founder-facing explanation.
PMR supplies its own enclosing heading; direct use can present the same body.

`finalize-receipt.py` validates and seals context, raw manifest, normalized data,
analysis and rendered result with hashes. Its `coverage` contains:

- `status: complete|partial|no_data`;
- `collected_count`, `selected_count`, `analyzed_count`;
- `gaps`, including sampling and missing evidence.

Receipt `status` is respectively `completed`, `partial` or `no_data`. A no-data
collection can explain that successful collection returned no observations. A partial
collection can still be useful; neither should be rewritten as full coverage by
a consumer. Terminal provider failures can be reported alongside valid successful
datasets with the exact gap `Provider collection <key> ended with <STATUS>.`.
No successful dataset, corrupt hashes, unsupported claims, and running or
uncertain provider operations remain validation failures, not no-data evidence.
