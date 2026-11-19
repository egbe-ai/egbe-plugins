# Recording options

Prefer a recording feature already available in the browser tool. Otherwise,
use an existing project-local Playwright installation or an approved isolated
tool environment. Do not change the product's dependencies or global browser
configuration just to capture a video.

With Playwright, create an isolated browser context with matching `viewport`
and `recordVideo.size` dimensions; the default recording may shrink the page
and make text unreadable. Inspect the live page and use its actual roles/selectors for
the planned actions. Save the `page.video()` handle, then **close the context**
before calling `video.saveAs(...)`: closing finalizes the WebM. Keep auth state
and credentials out of the saved assets. If browser binaries or recording
support are missing, report the dependency and use the harness's normal
installation/approval flow.

When FFmpeg is available, convert and create a poster from a useful frame:

```bash
ffmpeg -n -i capture.webm -c:v libx264 -pix_fmt yuv420p \
  -movflags +faststart -an demo.mp4
ffmpeg -n -ss 2 -i demo.mp4 -frames:v 1 demo-poster.jpg
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height \
  -of json demo.mp4
```

Choose the poster timestamp from the actual recording; the example's two
seconds is not a product requirement. Preserve audio when it is part of the
requested story (remove `-an` and encode compatible audio). Use unique output
paths or explicitly approve replacing old assets; `-n` avoids overwriting them.
Compression, cropping and speed changes must preserve readable content and
must not misrepresent actual product latency. Validate playback after editing.
