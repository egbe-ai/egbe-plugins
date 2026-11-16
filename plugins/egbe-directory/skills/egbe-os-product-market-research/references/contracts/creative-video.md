# Paid creative video evidence

`scripts/creative-video.py` is a deterministic helper for Creative Patterns.
The caller selects at most five unique videos per competitor × channel × market
by default, and owns durable per-attempt and whole-section provider budgets.
`preserve_video_media(creative, runtime, config, client=client)` preserves only
selected videos after native-copy/preview relevance and language classification.
`analyze_video(client, creative, runtime, config)` enriches a copy of the native
ad without merging IDs. Unknown-language videos without readable copy can
receive bounded analysis; explicit irrelevant or excluded-language videos do not.
Enriched frames and speech receive a new source-bound classification.

The client supplies `media_call(path, payload, kind=..., timeout=...)`,
`run_actor(actor_id, input, limit)`, `fetch_image(url)` and `image_bytes(image)`.
Paid transports must persist receipts and enforce the caller's section ledger.
The helper propagates budget exhaustion; provider and modality gaps remain
explicit on the creative. The caller writes those gaps to coverage rows.

For YouTube, use an exact video ID from provider metadata or the Transparency
creative page. An optional explicitly configured resolver actor can inspect
pages whose video ID is unavailable in the fetched HTML. Exact title,
description and thumbnail come from `POST /tools/youtube/videos` with
`{"video_ids": ["the11charID"]}`. Search results cannot replace this ID.
Captions take precedence over speech recognition. Configure actors through
`video.transcript_actor`, `video.resolver_actor`, or `video.download_actor`:

```json
{
  "actor_id": "founder-selected/provider",
  "input": {"provider_supported_field": ["{video_url}"]},
  "source_kind": "provider_captions",
  "limit": 1
}
```

This is an input-shape illustration, not a default actor contract. Supply the
actor's actual documented input fields. Templates support `{video_id}`,
`{video_url}` and, for the resolver, `{creative_url}`. Transcript outputs must
contain `transcript`, `captions`, `subtitles` or `text`; timestamped segments
carry `text`, `start` and `end` (or `duration`). Download outputs must carry
`video_url` or `download_url`. No actor is chosen or billed implicitly.

Label `source_kind` as captions only when the configured actor establishes that
origin. Otherwise returned text is `provider_transcript`, with its actor ID
recorded; a transcript field alone does not prove a caption source.

For downloadable files, pinned public HTTPS download checks every redirect.
Defaults bound files to 250 MiB and newly downloaded bytes per attempt to 1 GiB;
existing shared blobs do not consume the new attempt allowance. Preserve and
analyze share `download_budget(client)`; failed partial downloads count too.
`video.max_media_bytes` and `video.max_total_media_bytes` can lower the bounds.
FFmpeg samples 0, 0.5, 1.5, 3 and 5 seconds plus middle and end where available.
FFmpeg/FFprobe absence becomes a media gap. Mono 16 kHz WAV feeds the common
`POST /v1/media/transcribe` capability only when no transcript is available.
Audio exceeding 24 MiB is a stated gap, not a silently truncated transcript.
The local file, frames, transcript source, language, timestamps and hashes
remain attached to workspace-relative evidence references.

`POST /v1/media/analyze` receives up to eight frames and an available transcript.
A video preview is explicitly labelled `preview_only`; it cannot establish a
first-seconds hook or motion. Frames alone can establish on-screen text and
visible treatment; missing speech cannot establish spoken hooks. Analysis and
transcription requests use stable media hashes and frame references so the
client's shared content cache reuses one video across markets and native ads.

The speech capability requires the optional `media-transcription` role in
`runtime-models/roles.v1.json` to resolve to a catalog model with
`audio_transcription` capability. Deployment derives the effective model from
that role; an arbitrary model environment override does not select it. A missing
configuration returns 503 and keeps frame-only analysis available. A new skill
version is therefore not evidence that every deployed provider is configured.
