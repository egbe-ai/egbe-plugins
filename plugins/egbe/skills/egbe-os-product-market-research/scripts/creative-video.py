#!/usr/bin/env python3
"""Bounded paid-ad video evidence, shared by native ads and market observations.

The runner owns ordering/budgets; this module owns safe media preparation.
Provider actors are used only with explicitly configured IDs and input shapes.
No YouTube search result is substituted for the precise Transparency video.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any


VIDEO_CONTRACT = "paid-creative-video.v1"
MAX_MEDIA_BYTES = 250 * 1024 * 1024
MAX_TOTAL_MEDIA_BYTES = 1024 * 1024 * 1024
MAX_AUDIO_BYTES = 24 * 1024 * 1024
MAX_FRAME_BYTES = 5 * 1024 * 1024
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
INSTRUCTIONS = """Extract paid-ad evidence from the supplied sampled frames and transcript.
Record the visible first-seconds hook, literal on-screen text, visible speakers
and presentation treatment. Attribute each observation to its frame or transcript.
Describe a person's visible role or clothing; do not guess identity or job title.
A thumbnail is a preview, not an opening frame; never infer the temporal hook,
motion, sound or unseen action from a preview. Spoken hooks require transcript
evidence. Keep whole observable promise sentences, prices and discounts as
attributed competitor information, never as proven results or product adaptation.
Explicitly report missing modalities and gaps between sampled frames."""


class VideoEvidenceError(ValueError):
    pass


class VideoDownloadBudget:
    """Network bytes and verified blobs for one client/attempt, never a cache cap."""
    def __init__(self):
        self.downloaded_bytes = 0
        self.verified_files: dict[tuple, str] = {}

    def charge(self, size: int, limit: int) -> None:
        self.downloaded_bytes += size
        if self.downloaded_bytes > limit:
            raise VideoEvidenceError("aggregate downloaded-video byte budget exhausted for this attempt")


def download_budget(client) -> VideoDownloadBudget:
    budget = getattr(client, "_creative_video_download_budget", None)
    if budget is None:
        budget = VideoDownloadBudget()
        client._creative_video_download_budget = budget
    return budget


def _file_key(path: Path) -> tuple:
    stat = path.stat()
    return (str(path.resolve()), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _file_sha256(path: Path, budget: VideoDownloadBudget | None = None) -> str:
    key = _file_key(path)
    if budget is not None and key in budget.verified_files:
        return budget.verified_files[key]
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    # A changed blob cannot acquire a trusted fingerprint from a partial read.
    if _file_key(path) != key:
        raise VideoEvidenceError("media changed during hash verification")
    sha = digest.hexdigest()
    if budget is not None:
        budget.verified_files[key] = sha
    return sha


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def _public_target(url: str):
    if not isinstance(url, str) or any(ord(character) < 33 for character in url) or "\\" in url:
        raise VideoEvidenceError("media URL contains unsafe whitespace or escape characters")
    parsed = urllib.parse.urlparse(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.fragment or parsed.hostname.casefold() in {"localhost", "localhost.localdomain"}):
        raise VideoEvidenceError("media URL must be a public HTTPS URL without credentials or fragment")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise VideoEvidenceError("media URL resolves to a non-public address")
    except (OSError, ValueError) as exc:
        raise VideoEvidenceError(f"cannot validate media host: {exc}") from exc
    family, _, _, _, sockaddr = addresses[0]
    return parsed, family, sockaddr


def _download_public(url: str, destination: Path, max_bytes: int, timeout: float = 120, *,
                     budget: VideoDownloadBudget | None = None, max_total_bytes: int = MAX_TOTAL_MEDIA_BYTES) -> dict:
    """Resolve and pin every redirect to public DNS; stream within a hard bound."""
    deadline = time.monotonic() + timeout
    temp = destination.with_suffix(".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        for redirects in range(6):
            parsed, family, sockaddr = _public_target(url)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise VideoEvidenceError("media download deadline exhausted")
            raw = socket.socket(family, socket.SOCK_STREAM)
            raw.settimeout(min(30, remaining))
            connection = None
            response = None
            try:
                raw.connect(sockaddr)
                connection = ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname)
                host = parsed.hostname
                if ":" in host:
                    host = f"[{host}]"
                if parsed.port and parsed.port != 443:
                    host += f":{parsed.port}"
                target = urllib.parse.urlunparse(("", "", parsed.path or "/", "", parsed.query, ""))
                connection.sendall((f"GET {target} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: EgbeCreativeVideo/1\r\n"
                                    "Accept: */*\r\nConnection: close\r\n\r\n").encode("ascii"))
                response = http.client.HTTPResponse(connection)
                response.begin()
                if response.status in (301, 302, 303, 307, 308):
                    location = response.getheader("Location")
                    if not location or redirects == 5:
                        raise VideoEvidenceError("media redirect missing or limit exceeded")
                    url = urllib.parse.urljoin(url, location)
                    continue
                if not 200 <= response.status < 300:
                    raise VideoEvidenceError(f"media download returned HTTP {response.status}")
                total = 0
                digest = hashlib.sha256()
                with temp.open("wb") as handle:
                    while True:
                        if time.monotonic() >= deadline:
                            raise VideoEvidenceError("media download deadline exhausted")
                        chunk = response.read(min(65536, max_bytes - total + 1))
                        if not chunk:
                            break
                        total += len(chunk)
                        if budget is not None:
                            budget.charge(len(chunk), max_total_bytes)
                        if total > max_bytes:
                            raise VideoEvidenceError(f"media exceeds {max_bytes} bytes")
                        handle.write(chunk)
                        digest.update(chunk)
                if not total:
                    raise VideoEvidenceError("media download is empty")
                temp.replace(destination)
                return {"sha256": digest.hexdigest(), "bytes": total, "media_type": response.getheader("Content-Type", "").split(";")[0]}
            finally:
                if response:
                    response.close()
                if connection:
                    connection.close()
                else:
                    raw.close()
        raise VideoEvidenceError("media redirect limit exceeded")
    except (OSError, ValueError, http.client.HTTPException) as exc:
        temp.unlink(missing_ok=True)
        if isinstance(exc, VideoEvidenceError):
            raise
        raise VideoEvidenceError(f"media download failed: {exc}") from exc


def _cached_download(url: str, root: Path, *, kind: str, max_bytes: int,
                     max_total_bytes: int = MAX_TOTAL_MEDIA_BYTES,
                     budget: VideoDownloadBudget | None = None) -> tuple[Path, dict]:
    budget = budget or VideoDownloadBudget()
    index = root / "downloads" / f"{_hash({'url': url, 'kind': kind})}.json"
    if index.is_file():
        try:
            item = json.loads(index.read_text())
            path = root / item["file"]
            path.resolve().relative_to(root.resolve())
            if path.is_file() and 0 < path.stat().st_size <= max_bytes and _file_sha256(path, budget) == item["sha256"]:
                return path, item
        except (ValueError, KeyError, OSError):
            pass
    temp = root / "downloads" / f"{index.stem}.bin"
    if kind == "video":
        max_bytes = min(max_bytes, max_total_bytes - budget.downloaded_bytes)
        if max_bytes <= 0:
            raise VideoEvidenceError("aggregate downloaded-video byte budget exhausted for this attempt")
    before = budget.downloaded_bytes
    item = _download_public(url, temp, max_bytes, budget=budget if kind == "video" else None,
                            max_total_bytes=max_total_bytes)
    if kind == "video":
        # Also account for custom download transports that return byte counts.
        budget.charge(max(0, int(item["bytes"]) - (budget.downloaded_bytes - before)), max_total_bytes)
    if not 0 < temp.stat().st_size <= max_bytes or temp.stat().st_size != item["bytes"]:
        temp.unlink(missing_ok=True)
        raise VideoEvidenceError("downloaded media is empty, oversized or has inconsistent byte metadata")
    path = root / "blobs" / f"{item['sha256']}.{'mp4' if kind == 'video' else 'html'}"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp.replace(path)
    budget.verified_files[_file_key(path)] = item["sha256"]
    item["file"] = path.relative_to(root).as_posix()
    _write(index, item)
    return path, item


def youtube_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if VIDEO_ID.fullmatch(value):
        return value
    # JSON escapes and HTML entities frequently occur on Transparency pages.
    value = value.replace("\\/", "/").replace("&amp;", "&")
    match = re.search(r"(?:youtube(?:-nocookie)?\.com/(?:embed/|shorts/|v/|watch\?[^\s\"'<>]*?v=)|youtu\.be/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])", value)
    return match.group(1) if match else None


def _template(value: Any, replacements: dict) -> Any:
    if isinstance(value, str):
        for key, replacement in replacements.items():
            value = value.replace("{" + key + "}", str(replacement))
        return value
    if isinstance(value, list):
        return [_template(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _template(item, replacements) for key, item in value.items()}
    return value


def _actor(client, spec: Any, replacements: dict) -> list[dict]:
    if not isinstance(spec, dict) or not spec.get("actor_id") or not isinstance(spec.get("input"), dict):
        raise VideoEvidenceError("actor needs an explicit actor_id and input template")
    result = client.run_actor(spec["actor_id"], _template(spec["input"], replacements), int(spec.get("limit", 1)))
    rows = result[0] if isinstance(result, tuple) else result
    return [item for item in rows if isinstance(item, dict)] if isinstance(rows, list) else []


def _transcript(row: dict) -> tuple[str | None, list[dict], str | None]:
    raw = row.get("transcript") or row.get("subtitles") or row.get("captions") or row.get("text")
    segments = row.get("segments") if isinstance(row.get("segments"), list) else raw if isinstance(raw, list) else []
    normalized = []
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            continue
        start = segment.get("start")
        end = segment.get("end")
        if end is None and isinstance(start, (int, float)) and isinstance(segment.get("duration"), (int, float)):
            end = start + segment["duration"]
        if (isinstance(start, (int, float)) and not isinstance(start, bool) and isinstance(end, (int, float))
                and not isinstance(end, bool) and 0 <= start <= end <= 86400):
            normalized.append({"start": start, "end": end, "text": segment["text"]})
    text = raw if isinstance(raw, str) else " ".join(item["text"] for item in normalized)
    language = row.get("language") if isinstance(row.get("language"), str) else None
    return text.strip() if text and text.strip() else None, normalized, language


def _workspace(runtime: Path) -> Path:
    for parent in runtime.resolve().parents:
        if parent.name == "egbe-docs":
            return parent.parent
    # Standalone callers and tests may explicitly use their runtime directory.
    return runtime.resolve()


def _asset(path: Path, workspace: Path, kind: str, *, sha256: str | None = None,
           budget: VideoDownloadBudget | None = None, **extra) -> dict:
    relative = path.resolve().relative_to(workspace.resolve()).as_posix()
    return {"path": relative, "ref": relative, "kind": kind,
            "sha256": sha256 or _file_sha256(path, budget), **extra}


def _run(args: list[str], timeout: float = 120) -> bytes:
    try:
        result = subprocess.run(args, check=True, capture_output=True, timeout=timeout)
        return result.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise VideoEvidenceError(f"local media preparation unavailable: {type(exc).__name__}") from exc


def _prepare(path: Path, sha: str, root: Path, workspace: Path) -> tuple[list[dict], Path | None, list[str]]:
    directory = root / "prepared" / sha
    directory.mkdir(parents=True, exist_ok=True)
    gaps = []
    try:
        duration = float(_run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]).strip())
        if not 0 < duration <= 86400:
            raise VideoEvidenceError("invalid video duration")
    except (VideoEvidenceError, ValueError):
        duration = None
        gaps.append("Video duration unavailable; later sequence frames may be missing.")
    seconds = [0.0, 0.5, 1.5, 3.0, 5.0]
    if duration:
        seconds = [value for value in seconds if value < duration]
        seconds.extend([duration / 2, max(0, duration - .5)])
    frames = []
    for second in sorted(set(seconds))[:8]:
        frame = directory / f"frame-{int(second * 1000):08d}.jpg"
        try:
            if not frame.is_file():
                _run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-ss", str(second), "-i", str(path),
                      "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", "-q:v", "3", "-y", str(frame)])
            if not 0 < frame.stat().st_size <= MAX_FRAME_BYTES:
                raise VideoEvidenceError("frame is empty or exceeds frame byte bound")
            content = frame.read_bytes()
            frames.append(_asset(frame, workspace, "frame", sha256=hashlib.sha256(content).hexdigest(), timestamp_seconds=second, media_type="image/jpeg"))
        except (OSError, VideoEvidenceError) as exc:
            gaps.append(f"Frame at {second:g}s unavailable: {exc}")
    audio = directory / "speech.wav"
    try:
        if not audio.is_file():
            _run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                  "-c:a", "pcm_s16le", "-fs", str(MAX_AUDIO_BYTES + 1), "-y", str(audio)])
        if not 0 < audio.stat().st_size <= MAX_AUDIO_BYTES:
            raise VideoEvidenceError("Audio exceeds transcription byte bound; complete speech needs segmentation.")
    except (OSError, VideoEvidenceError) as exc:
        audio = None
        gaps.append(f"Speech audio unavailable: {exc}")
    return frames, audio, gaps


def _call(client, path: str, payload: dict, kind: str, timeout: float = 300) -> dict:
    result = client.media_call(path, payload, kind=kind, timeout=timeout)
    return result[0] if isinstance(result, tuple) else result


def preserve_video_media(creative: dict, runtime: Path, config: dict, *, client=None) -> dict:
    """Preserve a selected video, sharing the client's per-attempt byte budget."""
    row = json.loads(json.dumps(creative))
    runtime = Path(runtime).resolve()
    options = config.get("video") if isinstance(config.get("video"), dict) else config
    url = row.get("video_url") or next((value for value in row.get("video_urls", []) if isinstance(value, str)), None)
    if not isinstance(url, str) or youtube_id(url):
        return row
    budget = download_budget(client) if client is not None else VideoDownloadBudget()
    try:
        media, info = _cached_download(url, runtime / "cache/shared/video", kind="video",
                                       max_bytes=min(MAX_MEDIA_BYTES, int(options.get("max_media_bytes", MAX_MEDIA_BYTES))),
                                       max_total_bytes=int(options.get("max_total_media_bytes", MAX_TOTAL_MEDIA_BYTES)), budget=budget)
        asset = _asset(media, _workspace(runtime), "video", sha256=info["sha256"])
        row["media_assets"] = list(row.get("media_assets") or []) + [asset]
        row["video_file"] = asset["path"]
        row["video_sha256"] = info["sha256"]
    except (VideoEvidenceError, OSError) as exc:
        row["video_gaps"] = list(row.get("video_gaps") or []) + [f"Selected video preservation unavailable: {exc}"]
    return row


def analyze_video(client, creative: dict, runtime: Path, config: dict) -> dict:
    """Return an enriched copy. Budget exhaustion propagates to the runner."""
    row = json.loads(json.dumps(creative))
    runtime = Path(runtime).resolve()
    workspace = _workspace(runtime)
    root = runtime / "cache" / "shared" / "video"
    budget = download_budget(client)
    options = config.get("video") if isinstance(config.get("video"), dict) else config
    gaps = list(row.get("video_gaps") or [])
    assets = list(row.get("media_assets") or [])
    metadata = dict(row.get("video_metadata") or {})
    transcript, segments, language = _transcript(row)
    transcript_source = row.get("transcript_source") or ("provider_transcript" if transcript else None)
    transcript_provider = row.get("transcript_provider")
    platform = row.get("platform")
    vid = youtube_id(row.get("youtube_video_id")) or youtube_id(row.get("video_url"))
    if not vid and platform in {"youtube", "google"}:
        vid = youtube_id(row.get("video_id"))
    if platform == "youtube" or vid or (platform == "google" and not row.get("video_url")):
        if not vid:
            link = row.get("link") or row.get("library_url")
            vid = youtube_id(link)
            if not vid and isinstance(link, str) and urllib.parse.urlparse(link).hostname == "adstransparency.google.com":
                try:
                    page, _ = _cached_download(link, root, kind="page", max_bytes=2 * 1024 * 1024, budget=budget)
                    vid = youtube_id(page.read_text(errors="replace"))
                except VideoEvidenceError as exc:
                    gaps.append(f"Transparency video ID fetch unavailable: {exc}")
            if not vid and options.get("resolver_actor"):
                try:
                    resolved = _actor(client, options["resolver_actor"], {"creative_url": link or ""})
                    vid = next((youtube_id(item.get("video_id") or item.get("video_url") or item.get("url")) for item in resolved
                                if youtube_id(item.get("video_id") or item.get("video_url") or item.get("url"))), None)
                except Exception as exc:
                    if "budget" in type(exc).__name__.lower() or "budget" in str(exc).lower():
                        raise
                    gaps.append(f"Configured video-ID resolver unavailable: {str(exc)[:200]}")
        if vid:
            row["youtube_video_id"] = vid
            replacements = {"video_id": vid, "video_url": f"https://www.youtube.com/watch?v={vid}"}
            try:
                result = _call(client, "/tools/youtube/videos", {"video_ids": [vid]}, "video_metadata", 90)
                exact = next((item for item in result.get("rows", []) if item.get("video_id") == vid), None)
                if exact:
                    metadata.update(exact)
                    if exact.get("thumbnail_url") and not row.get("image_url"):
                        row["image_url"] = exact["thumbnail_url"]
                else:
                    gaps.append("YouTube metadata unavailable for exact video ID.")
            except Exception as exc:
                if "budget" in type(exc).__name__.lower() or "budget" in str(exc).lower():
                    raise
                gaps.append(f"YouTube metadata unavailable: {str(exc)[:200]}")
            if not transcript and options.get("transcript_actor"):
                try:
                    source_rows = _actor(client, options["transcript_actor"], replacements)
                    for source_row in source_rows:
                        transcript, segments, language = _transcript(source_row)
                        if transcript:
                            transcript_source = source_row.get("transcript_source") or options["transcript_actor"].get("source_kind") or "provider_transcript"
                            transcript_provider = options["transcript_actor"]["actor_id"]
                            break
                except Exception as exc:
                    if "budget" in type(exc).__name__.lower() or "budget" in str(exc).lower():
                        raise
                    gaps.append(f"Configured captions actor unavailable: {str(exc)[:200]}")
            elif not transcript:
                gaps.append("YouTube captions actor is not configured; captions were not retrieved.")
            if (not row.get("video_url") or youtube_id(row["video_url"])) and options.get("download_actor"):
                try:
                    source_rows = _actor(client, options["download_actor"], replacements)
                    row["video_url"] = next((url for item in source_rows for url in (item.get("download_url"), item.get("video_url"))
                                             if isinstance(url, str) and url and not youtube_id(url)), None)
                except Exception as exc:
                    if "budget" in type(exc).__name__.lower() or "budget" in str(exc).lower():
                        raise
                    gaps.append(f"Configured video download actor unavailable: {str(exc)[:200]}")
        else:
            gaps.append("YouTube video ID not resolved from Transparency; exact video evidence unavailable.")
    frames = []
    audio = None
    preserved = next((item for item in assets if item.get("kind") == "video" and item.get("path")), None)
    media_url = row.get("video_url") or next((url for url in row.get("video_urls", []) if isinstance(url, str)), None)
    if isinstance(media_url, str) and youtube_id(media_url):
        # A public player URL is not a downloadable video file.
        media_url = None
    if not media_url:
        media_url = next((item.get("url") for item in assets if item.get("kind") == "video" and item.get("url")), None)
    if preserved:
        try:
            media = (workspace / preserved["path"]).resolve()
            media.relative_to(workspace.resolve())
            if not 0 < media.stat().st_size <= min(MAX_MEDIA_BYTES, int(options.get("max_media_bytes", MAX_MEDIA_BYTES))):
                raise VideoEvidenceError("preserved video is empty or exceeds the per-file byte bound")
            sha = _file_sha256(media, budget)
            if sha != preserved.get("sha256"):
                raise VideoEvidenceError("preserved video hash mismatch")
            row["video_sha256"] = sha
            frames, audio, prep_gaps = _prepare(media, sha, root, workspace)
            gaps.extend(prep_gaps)
            assets.extend(frames)
        except (ValueError, OSError) as exc:
            gaps.append(f"Preserved video unavailable: {exc}")
    elif media_url:
        try:
            media, info = _cached_download(media_url, root, kind="video", max_bytes=min(MAX_MEDIA_BYTES, int(options.get("max_media_bytes", MAX_MEDIA_BYTES))),
                                          max_total_bytes=int(options.get("max_total_media_bytes", MAX_TOTAL_MEDIA_BYTES)), budget=budget)
            assets.append(_asset(media, workspace, "video", sha256=info["sha256"]))
            row["video_sha256"] = info["sha256"]
            frames, audio, prep_gaps = _prepare(media, info["sha256"], root, workspace)
            gaps.extend(prep_gaps)
            assets.extend(frames)
        except (VideoEvidenceError, OSError) as exc:
            gaps.append(f"Video file unavailable: {exc}")
    else:
        gaps.append("Downloadable video file unavailable; temporal visual analysis is incomplete.")
    if not transcript and audio:
        content = audio.read_bytes()
        assets.append(_asset(audio, workspace, "audio", sha256=hashlib.sha256(content).hexdigest()))
        try:
            result = _call(client, "/v1/media/transcribe", {"schema_version": 1, "media_type": "audio/wav",
                           "sha256": hashlib.sha256(content).hexdigest(), "content_base64": base64.b64encode(content).decode()}, "video_transcription")
            transcript, segments, language = _transcript(result)
            transcript_source = "speech_recognition" if transcript else None
            transcript_provider = result.get("effective_model") if transcript else None
        except Exception as exc:
            if "budget" in type(exc).__name__.lower() or "budget" in str(exc).lower():
                raise
            gaps.append(f"Speech recognition unavailable: {str(exc)[:200]}")
    preview_only = False
    if not frames and row.get("image_url"):
        try:
            preview = client.fetch_image(row["image_url"])
            if preview and preview.get("sha256"):
                preview_path = root / "prepared" / preview["sha256"] / "preview.jpg"
                preview_path.parent.mkdir(parents=True, exist_ok=True)
                preview_path.write_bytes(client.image_bytes(preview))
                frames = [_asset(preview_path, workspace, "preview", timestamp_seconds=0, media_type=preview["media_type"])]
                assets.extend(frames)
                preview_only = True
                gaps.append("Only a still video preview was available; opening hook and motion are unobserved.")
        except Exception as exc:
            if "budget" in type(exc).__name__.lower() or "budget" in str(exc).lower():
                raise
            gaps.append(f"Video preview unavailable: {str(exc)[:200]}")
    if not transcript:
        gaps.append("Speech transcript unavailable; spoken content is unobserved.")
    row.update(video_metadata=metadata, transcript=transcript, transcript_source=transcript_source,
               transcript_provider=transcript_provider, transcript_language=language, transcript_segments=segments, video_frames=frames,
               media_assets=list({(item.get('path') or item.get('url'), item.get('kind')): item for item in assets}.values()))
    if frames or transcript:
        # Persist speech independently so reports need not recover it from a paid response.
        if transcript:
            speech = root / "transcripts" / f"{_hash({'text': transcript, 'source': transcript_source, 'segments': segments})}.json"
            _write(speech, {"text": transcript, "source": transcript_source, "provider": transcript_provider, "language": language, "segments": segments})
            row["transcript_ref"] = speech.relative_to(workspace).as_posix()
        payload = {"schema_version": 1, "analysis_contract": VIDEO_CONTRACT,
                   "instructions": INSTRUCTIONS + ("\nAll supplied frames are STILL PREVIEWS, not temporal samples." if preview_only else ""),
                   "frames": [{"ref": item["ref"], "timestamp_seconds": item["timestamp_seconds"], "media_type": item["media_type"],
                               "sha256": item["sha256"], "content_base64": base64.b64encode((workspace / item["path"]).read_bytes()).decode()}
                              for item in frames], "transcript": transcript[:50000] if transcript else None}
        if transcript and len(transcript) > 50000:
            gaps.append("Transcript exceeds media analysis limit; only the first 50,000 characters were analyzed.")
        try:
            analyzed = _call(client, "/v1/media/analyze", payload, "video_analysis")
            row["media_analysis"] = analyzed.get("analysis") if isinstance(analyzed.get("analysis"), dict) else analyzed
            row["video_analysis_receipt"] = {key: value for key, value in analyzed.items() if key != "analysis"}
            row["video_analysis_status"] = "preview_only" if preview_only else "frames_and_speech" if frames and transcript else "frames_only" if frames else "speech_only"
        except Exception as exc:
            if "budget" in type(exc).__name__.lower() or "budget" in str(exc).lower():
                raise
            row["video_analysis_status"] = "unavailable"
            gaps.append(f"Multimodal video analysis unavailable: {str(exc)[:200]}")
    else:
        row["video_analysis_status"] = "unavailable"
    row["video_gaps"] = sorted(set(gaps))
    return row
