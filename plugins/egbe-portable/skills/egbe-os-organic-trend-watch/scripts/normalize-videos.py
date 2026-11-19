#!/usr/bin/env python3
"""Normalize source observations without deciding their cause or business value."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _contract import (
    ANALYSIS_CONTRACT_VERSION,
    ContractError,
    SCHEMA_VERSION,
    TIKTOK_COMMENTS_BUNDLE_PATH,
    atomic_write_json,
    extract_rows,
    load_run_state,
    parse_rfc3339,
    read_json,
    resolve_relative,
    sha256_file,
    validate_linked_tiktok_comments_bundle,
    validate_raw_manifest,
    validate_context,
)
from _provider_inputs import validate_collection_window


AD_MARKERS = ("#ad", "#sponsored", "#partnership", "paid partnership", "thanks @")


def _nested(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _first(value: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        candidate = _nested(value, path)
        if candidate is not None:
            return candidate
    return None


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _number(value: Any) -> float | int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result) or result < 0:
        return None
    return int(result) if result.is_integer() else result


def _handle(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    return text.lstrip("@").strip().casefold() or None


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            result = datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
        return result
    text = _text(value)
    if text is None:
        return None
    if text.isdigit():
        return _timestamp(int(text))
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        result = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _safe_ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _canonical_url(platform: str, row: dict[str, Any], video_id: str, handle: str) -> str:
    candidates = (
        _text(_first(row, "webVideoUrl")),
        _text(_first(row, "postUrl")),
        _text(_first(row, "inputUrl")),
        _text(_first(row, "url")),
    )
    for explicit in candidates:
        if not explicit or not explicit.startswith(("https://", "http://")):
            continue
        host = (urllib.parse.urlparse(explicit).hostname or "").casefold()
        if platform == "tiktok" and (host == "tiktok.com" or host.endswith(".tiktok.com")):
            return explicit
        if platform == "instagram" and (
            host == "instagram.com" or host.endswith(".instagram.com")
        ):
            return explicit
    if platform == "tiktok":
        return f"https://www.tiktok.com/@{handle}/video/{video_id}"
    short_code = _text(_first(row, "shortCode", "shortcode", "code")) or video_id
    return f"https://www.instagram.com/reel/{short_code}/"


def _comments(row: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _first(row, "comments", "latestComments", "topComments")
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            text, likes, provider_id = item.strip(), None, None
        elif isinstance(item, dict):
            text = _text(_first(item, "text", "comment", "content")) or ""
            likes = _number(_first(item, "diggCount", "likesCount", "likes", "likeCount"))
            provider_id = _text(
                _first(item, "cid", "id", "commentId", "comment_id")
            )
        else:
            continue
        if not text or text in seen:
            continue
        seen.add(text)
        comment_id = (
            f"provider:{provider_id}"
            if provider_id
            else f"text-sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
        )
        result.append({"comment_id": comment_id, "text": text, "likes": likes})
    result.sort(key=lambda item: (item["likes"] is None, -(item["likes"] or 0), item["text"]))
    return result[:20]


def _merge_comments(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = {item["text"]: item for item in left}
    for item in right:
        merged[item["text"]] = item
    return sorted(
        merged.values(),
        key=lambda item: (item["likes"] is None, -(item["likes"] or 0), item["text"]),
    )[:20]


def _hashtags(row: dict[str, Any], caption: str) -> list[str]:
    values = _first(row, "hashtags", "hashTags")
    result: list[str] = []
    if isinstance(values, list):
        for item in values:
            if isinstance(item, dict):
                item = _first(item, "name", "title")
            text = _text(item)
            if text:
                result.append(text.lstrip("#").casefold())
    for token in caption.split():
        if token.startswith("#") and len(token) > 1:
            result.append(token[1:].strip(".,!?;:()[]{}").casefold())
    return sorted(set(result))


def _normalize_row(
    *,
    platform: str,
    row: dict[str, Any],
    accounts: dict[tuple[str, str], dict[str, Any]],
    collected_at: datetime,
) -> dict[str, Any] | None:
    video_id = _text(_first(row, "id", "videoId", "aweme_id", "shortCode", "code"))
    handle = _handle(
        _first(
            row,
            "authorMeta.name",
            "authorMeta.uniqueId",
            "author.uniqueId",
            "ownerUsername",
            "owner.username",
            "username",
            "profileName",
        )
    )
    if not video_id or not handle:
        raise ContractError("provider observation is missing its video ID or account handle")
    account = accounts.get((platform, handle))
    if account is None:
        return None

    posted = _timestamp(_first(row, "createTime", "timestamp", "takenAt", "publishedAt"))
    age_days: int | None = None
    if posted is not None:
        age_days = max(0, (collected_at.date() - posted.date()).days)
    caption = _text(_first(row, "text", "caption", "description")) or ""
    hashtags = _hashtags(row, caption)

    views = _number(_first(row, "playCount", "videoViewCount", "videoPlayCount", "views", "viewCount"))
    likes = _number(_first(row, "diggCount", "likesCount", "likes", "likeCount"))
    comments_count = _number(_first(row, "commentCount", "commentsCount", "commentsTotal"))
    shares = _number(_first(row, "shareCount", "sharesCount", "shares"))
    saves = _number(_first(row, "collectCount", "saveCount", "savesCount", "saves"))
    duration = _number(_first(row, "videoMeta.duration", "videoDuration", "duration"))
    followers = _number(
        _first(
            row,
            "authorMeta.fans",
            "authorMeta.followers",
            "ownerFollowersCount",
            "followersCount",
            "owner.followersCount",
        )
    )
    if followers is None:
        followers = _number(account.get("followers"))

    sound_id = _text(
        _first(
            row,
            "musicMeta.musicId",
            "musicInfo.id",
            "musicInfo.musicId",
            "musicInfo.audio_id",
            "audio.id",
        )
    )
    sound_name = _text(
        _first(
            row,
            "musicMeta.musicName",
            "musicInfo.title",
            "musicInfo.name",
            "musicInfo.song_name",
            "audio.name",
        )
    )
    sound_author = _text(
        _first(
            row,
            "musicMeta.musicAuthor",
            "musicInfo.artist",
            "musicInfo.author",
            "musicInfo.artist_name",
            "audio.author",
        )
    )
    matched = sorted(
        keyword
        for keyword in account.get("product_keywords", [])
        if keyword.casefold().lstrip("#") in caption.casefold()
        or keyword.casefold().lstrip("#") in hashtags
    )
    paid_signals = [
        marker for marker in AD_MARKERS
        if (marker.lstrip("#") in hashtags if marker.startswith("#")
            else marker in caption.casefold())
    ]
    if row.get("paidPartnership") is True:
        paid_signals.append("provider-paid-partnership")

    transcript = _text(
        _first(row, "transcript", "subtitlesText", "subtitleText", "videoTranscript")
    )
    media_url = _text(
        _first(
            row,
            "videoUrl",
            "videoMeta.downloadAddr",
            "videoMeta.playAddr",
            "videoPlayUrl",
            "downloadedVideo",
            "downloadedVideoUrl",
        )
    )
    if media_url is not None and not media_url.startswith(("https://", "http://")):
        media_url = None
    cover_url = _text(
        _first(
            row,
            "displayUrl",
            "coverUrl",
            "videoMeta.coverUrl",
            "videoMeta.cover",
            "thumbnailUrl",
        )
    )
    if cover_url is not None and not cover_url.startswith(("https://", "http://")):
        cover_url = None
    return {
        "observation_id": f"{platform}:{video_id}",
        "platform": platform,
        "video_id": video_id,
        "url": _canonical_url(platform, row, video_id, handle),
        "account": {
            "handle": handle,
            "account_type": account["account_type"],
            "followers": followers,
            "collected_median_views": None,
        },
        "posted_at": posted.isoformat().replace("+00:00", "Z") if posted else None,
        "age_days": age_days,
        "caption": caption,
        "hashtags": hashtags,
        "metrics": {
            "views": views,
            "likes": likes,
            "comments": comments_count,
            "saves": saves,
            "shares": shares,
            "duration_seconds": duration,
        },
        "sound": {
            "id": sound_id,
            "name": sound_name,
            "author": sound_author,
        },
        "comparisons": {},
        "matched_keywords": matched,
        "promotion_signals": sorted(set(paid_signals)),
        "comments": _comments(row),
        "evidence": {
            "video_path": None,
            "media_url": media_url,
            "cover_url": cover_url,
            "transcript": transcript,
            "frame_paths": [],
            "artifact_sha256": {},
            "visual_preparation": None,
        },
        "selected_for_analysis": False,
    }


def _prefer(left: Any, right: Any) -> Any:
    if right is None or right == "" or right == [] or right == {}:
        return left
    if right == "unknown" and left not in (None, "", "unknown"):
        return left
    if left is None or left == "" or left == [] or left == {}:
        return right
    return right


def _merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(left))
    for field in ("url", "posted_at", "age_days", "caption", "hashtags"):
        result[field] = _prefer(result.get(field), right.get(field))
    for section in ("account", "metrics", "sound"):
        for field, value in right[section].items():
            result[section][field] = _prefer(result[section].get(field), value)
    for field in (
        "video_path",
        "media_url",
        "cover_url",
        "transcript",
        "frame_paths",
        "visual_preparation",
    ):
        result["evidence"][field] = _prefer(
            result["evidence"].get(field), right["evidence"].get(field)
        )
    evidence_hashes = {
        **(left["evidence"].get("artifact_sha256") or {}),
        **(right["evidence"].get("artifact_sha256") or {}),
    }
    evidence_refs = (
        ([result["evidence"]["video_path"]] if result["evidence"].get("video_path") else [])
        + list(result["evidence"].get("frame_paths") or [])
    )
    result["evidence"]["artifact_sha256"] = {
        relative: evidence_hashes[relative]
        for relative in evidence_refs
        if relative in evidence_hashes
    }
    result["comments"] = _merge_comments(result["comments"], right["comments"])
    result["matched_keywords"] = sorted(
        set(result["matched_keywords"])
        | set(right["matched_keywords"])
    )
    result["promotion_signals"] = sorted(
        set(result["promotion_signals"]) | set(right["promotion_signals"])
    )
    return result


def _describe_and_select(videos: list[dict[str, Any]], limit: int | None) -> list[str]:
    """Describe the collected sample; never infer a winning format from ratios."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for video in videos:
        grouped.setdefault((video["platform"], video["account"]["handle"]), []).append(video)
    for account_videos in grouped.values():
        views = [v["metrics"]["views"] for v in account_videos
                 if v["metrics"]["views"] is not None]
        median = statistics.median(views) if views else None
        for video in account_videos:
            metrics = video["metrics"]
            video["account"]["collected_median_views"] = median
            video["comparisons"] = {
                **{f"{metric}_per_view": _safe_ratio(metrics[metric], metrics["views"])
                   for metric in ("likes", "comments", "saves", "shares")},
                "views_per_follower": _safe_ratio(metrics["views"], video["account"]["followers"]),
                "vs_collected_account_median": _safe_ratio(metrics["views"], median),
            }
    # A requested resource cap is a deterministic sample, not a quality ranking.
    groups = [sorted(grouped[key], key=lambda v: v["observation_id"])
              for key in sorted(grouped)]
    ordered = [group[index] for index in range(max(map(len, groups), default=0))
               for group in groups if index < len(group)]
    selected = ordered if limit is None else ordered[:limit]
    selected_ids = {video["observation_id"] for video in selected}
    for video in videos:
        video["selected_for_analysis"] = video["observation_id"] in selected_ids
    if len(selected) < len(videos):
        return [f"Analysis resource cap selected {len(selected)} of {len(videos)} collected observations; "
                "the account-balanced sample is not a performance ranking."]
    return []


def _apply_collection_window(videos: list[dict[str, Any]], window: dict[str, Any]) -> list[str]:
    lower = parse_rfc3339(window["oldest_post_date"] + "T00:00:00Z", "collection lower bound")
    upper = parse_rfc3339(window["reference_at"], "collection reference_at")
    counts = {"outside_window": 0, "unknown_date": 0}
    for video in videos:
        posted = _timestamp(video.get("posted_at"))
        status = ("unknown_date" if posted is None else
                  "in_window" if lower <= posted <= upper else "outside_window")
        video["time_window_status"] = status
        if status in counts:
            counts[status] += 1
    gaps = []
    if counts["outside_window"]:
        gaps.append(f"Excluded {counts['outside_window']} observations outside the frozen collection window; raw evidence retained.")
    if counts["unknown_date"]:
        gaps.append(f"Excluded {counts['unknown_date']} observations with unknown publication dates from the time-window sample; raw evidence retained.")
    return gaps


def _discovery_sources(manifest: dict[str, Any]) -> list[dict[str, str]]:
    return sorted(
        [
            {"path": item["path"], "sha256": item["sha256"]}
            for item in manifest["datasets"]
            if item["kind"] == "discovery"
        ],
        key=lambda item: item["path"],
    )


def _freeze_selection(
    root: Path,
    manifest: dict[str, Any],
    videos: list[dict[str, Any]],
    computed_gaps: list[str],
    window: dict[str, Any],
) -> tuple[list[str], dict[str, str]]:
    path = root / "normalized/selection.json"
    current_sources = _discovery_sources(manifest)
    by_id = {video["observation_id"]: video for video in videos}
    if path.is_file():
        value = read_json(path)
        if value.get("schema_version") != SCHEMA_VERSION:
            raise ContractError("selection schema_version must be 1")
        if value.get("collection_epoch") != manifest["collection_epoch"]:
            raise ContractError("selection belongs to a different collection epoch")
        if value.get("discovery_sources") != current_sources:
            raise ContractError("selection discovery evidence changed")
        if value.get("collection_window") != window:
            raise ContractError("selection collection window changed")
        selected_ids = value.get("selected_observation_ids")
        selection_gaps = value.get("selection_gaps")
        if (
            not isinstance(selected_ids, list)
            or len(selected_ids) != len(set(selected_ids))
            or not all(isinstance(item, str) and item in by_id
                       and by_id[item]["time_window_status"] == "in_window"
                       for item in selected_ids)
        ):
            raise ContractError("selection contains invalid observation IDs")
        if (
            not isinstance(selection_gaps, list)
            or selection_gaps != sorted(selection_gaps)
            or not all(isinstance(item, str) and item.strip() for item in selection_gaps)
        ):
            raise ContractError("selection gaps are invalid")
    else:
        if any(item["kind"] == "enrichment" for item in manifest["datasets"]):
            raise ContractError(
                "normalize discovery and freeze selection before collecting enrichment"
            )
        selected_ids = sorted(
            video["observation_id"]
            for video in videos
            if video["selected_for_analysis"]
        )
        selection_gaps = sorted(computed_gaps)
        atomic_write_json(
            path,
            {
                "schema_version": SCHEMA_VERSION,
                "collection_epoch": manifest["collection_epoch"],
                "discovery_sources": current_sources,
                "collection_window": window,
                "selected_observation_ids": selected_ids,
                "selection_gaps": selection_gaps,
            },
        )
    selected_set = set(selected_ids)
    for video in videos:
        video["selected_for_analysis"] = video["observation_id"] in selected_set
    return selection_gaps, {
        "path": "normalized/selection.json",
        "sha256": sha256_file(path),
    }


def normalize(root: Path) -> dict[str, Any]:
    context = validate_context(root / "context.json")
    state = load_run_state(root)
    window = validate_collection_window(context, state.get("collection_window"))
    manifest = validate_raw_manifest(root)
    collected_at = parse_rfc3339(
        manifest["collection_completed_at"], "collection_completed_at"
    )
    accounts: dict[tuple[str, str], dict[str, Any]] = {}
    for item in manifest["accounts"]:
        copy = dict(item)
        copy["handle"] = _handle(item["handle"])
        copy["product_keywords"] = sorted(
            {keyword.casefold().lstrip("#") for keyword in item["product_keywords"]}
        )
        accounts[(item["platform"], copy["handle"])] = copy

    linked_tiktok_comments: dict[str, list[dict[str, Any]]] = {}
    if any(
        item.get("platform") == "tiktok" and item.get("kind") == "enrichment"
        for item in manifest["datasets"]
    ):
        main_payload = read_json(root / "raw/tiktok-enrichment.json")
        linked_bundle = read_json(root / TIKTOK_COMMENTS_BUNDLE_PATH)
        linked_tiktok_comments = validate_linked_tiktok_comments_bundle(
            main_payload,
            linked_bundle,
        )

    normalized: dict[str, dict[str, Any]] = {}
    datasets = sorted(manifest["datasets"], key=lambda item: item["kind"] == "enrichment")
    for dataset in datasets:
        source_path = resolve_relative(root, dataset["path"], "dataset.path")
        try:
            raw_value = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractError(f"cannot read raw dataset {dataset['path']}: {exc}") from exc
        for row in extract_rows(raw_value):
            video = _normalize_row(
                platform=dataset["platform"],
                row=row,
                accounts=accounts,
                collected_at=collected_at,
            )
            if video is None:
                continue
            if video["platform"] == "tiktok":
                linked_rows = linked_tiktok_comments.get(video["video_id"], [])
                if linked_rows:
                    video["comments"] = _merge_comments(
                        video["comments"],
                        _comments({"comments": linked_rows}),
                    )
            existing = normalized.get(video["observation_id"])
            normalized[video["observation_id"]] = video if existing is None else _merge(existing, video)
    videos = list(normalized.values())
    computed_gaps = _apply_collection_window(videos, window)
    eligible = [video for video in videos if video["time_window_status"] == "in_window"]
    computed_gaps.extend(_describe_and_select(eligible, context.get("max_analysis_videos", 30)))
    selection_gaps, selection_source = _freeze_selection(
        root, manifest, videos, computed_gaps, window
    )
    videos.sort(
        key=lambda video: (
            video["platform"],
            video["account"]["handle"],
            not video["selected_for_analysis"],
            video["observation_id"],
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_contract_version": ANALYSIS_CONTRACT_VERSION,
        "generated_at": manifest["collection_completed_at"],
        "source_manifest_sha256": sha256_file(root / "raw/manifest.json"),
        "selection_source": selection_source,
        "selection_gaps": selection_gaps,
        "collection_window": window,
        "time_window_counts": {
            status: sum(video["time_window_status"] == status for video in videos)
            for status in ("in_window", "outside_window", "unknown_date")
        },
        "videos": videos,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.runtime_root.resolve()
    try:
        payload = normalize(root)
        atomic_write_json(root / "normalized/videos.json", payload)
    except (ContractError, OSError) as exc:
        print(f"organic trend normalization failed: {exc}", file=sys.stderr)
        return 1
    selected = sum(bool(video["selected_for_analysis"]) for video in payload["videos"])
    print(f"normalized {len(payload['videos'])} videos; selected {selected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
