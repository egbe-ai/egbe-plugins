# Meta video operations

Use the source/format covered by the task; generation can incur cost.
This helper does not require video or a static/video mix.
Preserve generation request ID, selected model and eventual asset URL.

```text
POST /tools/videos/generations
GET  /tools/videos/generations/{request_id}?model=<selected-model>
POST /tools/videos/generations/{request_id}/meta-upload
```

Read the OS video capability for current inputs/models. Poll the same request;
do not regenerate after a failed status read. Meta upload takes the generation
model and desired filename. For a supplied finished MP4 use
`/ads/meta/raw/advideos` with `video_base64` and `filename`.

Save `video_id`. A video ad also needs a thumbnail: extract the selected still
from that video, upload via `adimages`, and preserve `image_hash`.
Inspect video/audio/subtitles for defects and fidelity to the selected script.
Never present synthetic customer speech as a real testimonial.

The declarative image spec cannot express `video_data`. An authorized raw
build uses `object_story_spec.video_data` with `video_id`, thumbnail
`image_hash`, selected copy and destination CTA. Create every level PAUSED.
Raw creation lacks apply compensation; record each result and use
[recovery](../workflows/recovery.md) for partial failure.
Verify `/state?expect=PAUSED`; processing does not authorize activation.
