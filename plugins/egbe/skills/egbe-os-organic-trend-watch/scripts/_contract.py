#!/usr/bin/env python3
"""Shared deterministic contracts for the organic-trend-watch skill."""

from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import fcntl
import hashlib
import json
import os
import re
import tempfile
import urllib.parse
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
SECTION_ID = "organic_trend_watch"
SECTION_HEADING = "TikTok/Reels market trend research for this product"
ANALYSIS_CONTRACT_VERSION = "evidence-v5"
MULTIMODAL_ANALYSIS_CONTRACT = "organic-video-evidence.v1"
MEDIA_PROMPT_CONTRACT_VERSION = "media-evidence-v1"
VISUAL_ANALYSIS_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "references/visual-analysis-prompt.md"
)
PROVIDER_INPUT_CONTRACT_VERSION = "apify-inputs-v1"
TERMINAL_PROVIDER_FAILURE_STATUSES = {"FAILED", "ABORTED", "TIMED-OUT", "TIMED_OUT"}
RUNTIME_RELATIVE = Path(_artifact_path("egbe-docs/research/market/work/organic_trend_watch"))
STEPS = (
    "discovery",
    "collection",
    "normalization",
    "visual_analysis",
    "synthesis",
    "render",
)
CANONICAL_PROVIDER_RUNS = {
    "tiktok-discovery": {
        "platform": "tiktok",
        "kind": "discovery",
        "actor_id": "clockworks/tiktok-scraper",
        "input_keys": (
            "oldestPostDateUnified",
            "profileSorting",
            "profiles",
            "resultsPerPage",
        ),
    },
    "instagram-discovery": {
        "platform": "instagram",
        "kind": "discovery",
        "actor_id": "apify/instagram-reel-scraper",
        "input_keys": ("onlyPostsNewerThan", "resultsLimit", "username"),
    },
    "tiktok-enrichment": {
        "platform": "tiktok",
        "kind": "enrichment",
        "actor_id": "clockworks/tiktok-scraper",
        "input_keys": (
            "commentsPerPost",
            "downloadSubtitlesOptions",
            "postURLs",
            "shouldDownloadVideos",
        ),
    },
    "instagram-enrichment": {
        "platform": "instagram",
        "kind": "enrichment",
        "actor_id": "apify/instagram-reel-scraper",
        "input_keys": (
            "includeDownloadedVideo",
            "includeSharesCount",
            "includeTranscript",
            "username",
        ),
    },
}
TIKTOK_COMMENTS_BUNDLE_PATH = "raw/tiktok-enrichment-comments.json"
TIKTOK_COMMENTS_LINK_KIND = "tiktok-comments"
VISUAL_EVIDENCE_METHOD = "provider-media-v2"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
APIFY_DATASET_ID_RE = re.compile(r"^[A-Za-z0-9_-]{5,128}$")


class ContractError(ValueError):
    """Raised when a runtime artifact violates the public contract."""


@contextmanager
def provider_run_lock(root: Path):
    """Serialize provider-input rebuilding with submission and recovery."""
    descriptor = os.open(root / ".apify-run.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ContractError("another provider operation holds this runtime; retry after it finishes") from exc
        yield
    finally:
        # Keep the inode in place; replacing it could let a concurrent caller
        # acquire a different lock for the same runtime.
        os.close(descriptor)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_visual_analysis_instructions() -> str:
    try:
        value = VISUAL_ANALYSIS_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"cannot read visual analysis prompt: {exc}") from exc
    if not value:
        raise ContractError("visual analysis prompt is empty")
    return value


def canonical_frame_seconds(duration: Any) -> tuple[float, ...]:
    opening = [0.0, 0.5, 1.5, 3.0, 5.0]
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
        return tuple(opening)
    seconds = [value for value in opening if value <= float(duration)]
    if duration > 6:
        seconds.extend(
            [
                round(float(duration) * 0.5, 3),
                round(float(duration) * 0.8, 3),
                round(max(0.0, float(duration) - 0.5), 3),
            ]
        )
    return tuple(sorted(set(seconds)))


def visual_analysis_receipt_path(root: Path, observation_id: str) -> Path:
    safe = "".join(
        character if character.isalnum() else "-" for character in observation_id
    ).strip("-") or "observation"
    suffix = sha256_bytes(observation_id.encode("utf-8"))[:12]
    return root / "visual-analysis" / f"{safe}-{suffix}.json"


def multimodal_input_sha256(
    *,
    analysis_contract: str,
    instructions: str,
    frames: list[dict[str, Any]],
    transcript: str | None,
) -> str:
    value = {
        "schema_version": SCHEMA_VERSION,
        "analysis_contract": analysis_contract,
        "instructions": instructions,
        "frames": [
            {
                "ref": frame["ref"],
                "timestamp_seconds": frame["timestamp_seconds"],
                "media_type": frame["media_type"],
                "sha256": frame["sha256"],
            }
            for frame in frames
        ],
        "transcript_sha256": (
            sha256_bytes(transcript.encode("utf-8")) if transcript else None
        ),
    }
    return sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"missing JSON artifact: {path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON artifact must contain an object: {path}")
    return value


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def require_string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ContractError(f"{field} must be a non-empty string")
    return value


def require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ContractError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def validate_visual_analysis_receipt(
    root: Path,
    observation: dict[str, Any],
    *,
    instructions: str,
) -> dict[str, Any]:
    observation_id = require_string(
        observation.get("observation_id"), "normalized observation_id"
    )
    path = visual_analysis_receipt_path(root, observation_id)
    value = read_json(path)
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"{path.name} schema_version must be 1")
    if value.get("observation_id") != observation_id:
        raise ContractError(f"{path.name} belongs to another observation")
    if value.get("analysis_contract") != MULTIMODAL_ANALYSIS_CONTRACT:
        raise ContractError(f"{path.name} analysis contract mismatch")

    evidence = observation.get("evidence")
    if not isinstance(evidence, dict):
        raise ContractError(f"{observation_id} has no evidence object")
    preparation = evidence.get("visual_preparation")
    samples = preparation.get("frame_samples") if isinstance(preparation, dict) else []
    if not isinstance(samples, list):
        raise ContractError(f"{observation_id} frame samples are invalid")
    hashes = evidence.get("artifact_sha256")
    if not isinstance(hashes, dict):
        raise ContractError(f"{observation_id} artifact hashes are invalid")
    frames: list[dict[str, Any]] = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ContractError(f"{observation_id} frame sample {index} is invalid")
        ref = require_string(sample.get("path"), f"{observation_id} frame ref")
        timestamp = sample.get("second")
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
            raise ContractError(f"{observation_id} frame timestamp is invalid")
        frame_path = resolve_relative(root, ref, f"{observation_id} frame ref")
        digest = require_sha256(hashes.get(ref), f"{observation_id} frame sha256")
        if not frame_path.is_file() or sha256_file(frame_path) != digest:
            raise ContractError(f"{observation_id} frame hash mismatch: {ref}")
        media_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(frame_path.suffix.casefold())
        if media_type is None:
            raise ContractError(f"{observation_id} frame media type is unsupported")
        frames.append(
            {
                "ref": ref,
                "timestamp_seconds": float(timestamp),
                "media_type": media_type,
                "sha256": digest,
            }
        )
    transcript_value = evidence.get("transcript")
    transcript = (
        transcript_value.strip()
        if isinstance(transcript_value, str) and transcript_value.strip()
        else None
    )
    expected_input = multimodal_input_sha256(
        analysis_contract=MULTIMODAL_ANALYSIS_CONTRACT,
        instructions=instructions,
        frames=frames,
        transcript=transcript,
    )
    if value.get("input_sha256") != expected_input:
        raise ContractError(f"{path.name} input hash is stale")
    if value.get("frames") != frames:
        raise ContractError(f"{path.name} frame provenance mismatch")
    expected_transcript = {
        "status": "available" if transcript else "unavailable",
        "sha256": sha256_bytes(transcript.encode("utf-8")) if transcript else None,
    }
    if value.get("transcript") != expected_transcript:
        raise ContractError(f"{path.name} transcript provenance mismatch")

    status = value.get("status")
    if status not in {"completed", "unavailable"}:
        raise ContractError(f"{path.name} status is invalid")
    analysis = value.get("analysis")
    if not isinstance(analysis, dict):
        raise ContractError(f"{path.name} analysis must be an object")
    expected_analysis_keys = {
        "frames",
        "sequence_summary",
        "transcript",
        "claims",
        "gaps",
    }
    if set(analysis) != expected_analysis_keys:
        raise ContractError(f"{path.name} analysis shape is invalid")
    analysis_frames = analysis.get("frames")
    if not isinstance(analysis_frames, list) or [
        item.get("ref") if isinstance(item, dict) else None for item in analysis_frames
    ] != [frame["ref"] for frame in frames]:
        raise ContractError(f"{path.name} analyzed frames mismatch")
    for index, item in enumerate(analysis_frames):
        if set(item) != {"ref", "visible_text", "observations"}:
            raise ContractError(f"{path.name} frame analysis {index} shape is invalid")
        for field in ("visible_text", "observations"):
            values = item.get(field)
            if not isinstance(values, list) or not all(
                isinstance(entry, str) and entry.strip() for entry in values
            ):
                raise ContractError(
                    f"{path.name} frame analysis {index}.{field} is invalid"
                )
    if not isinstance(analysis.get("sequence_summary"), str):
        raise ContractError(f"{path.name} sequence_summary must be a string")
    transcript_analysis = analysis.get("transcript")
    if not isinstance(transcript_analysis, dict) or set(transcript_analysis) != {
        "status",
        "observations",
    }:
        raise ContractError(f"{path.name} transcript analysis shape is invalid")
    if transcript_analysis.get("status") != expected_transcript["status"]:
        raise ContractError(f"{path.name} transcript analysis status mismatch")
    transcript_observations = transcript_analysis.get("observations")
    if not isinstance(transcript_observations, list) or not all(
        isinstance(entry, str) and entry.strip() for entry in transcript_observations
    ):
        raise ContractError(f"{path.name} transcript observations are invalid")
    if not transcript and transcript_observations:
        raise ContractError(f"{path.name} invented observations for a missing transcript")
    allowed_refs = {frame["ref"] for frame in frames}
    if transcript:
        allowed_refs.add("transcript")
    claims = analysis.get("claims")
    if not isinstance(claims, list):
        raise ContractError(f"{path.name} claims must be a list")
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict) or set(claim) != {
            "text",
            "modality",
            "evidence_refs",
        }:
            raise ContractError(f"{path.name} claim {index} shape is invalid")
        require_string(claim.get("text"), f"{path.name} claim {index}.text")
        modality = claim.get("modality")
        refs = claim.get("evidence_refs")
        if modality not in {"visual", "verbal", "mixed"}:
            raise ContractError(f"{path.name} claim {index} modality is invalid")
        if not isinstance(refs, list) or not refs or len(refs) != len(set(refs)):
            raise ContractError(f"{path.name} claim {index} refs are invalid")
        if any(ref not in allowed_refs for ref in refs):
            raise ContractError(f"{path.name} claim {index} cites unknown evidence")
        has_visual = bool(set(refs) & {frame["ref"] for frame in frames})
        has_verbal = "transcript" in refs
        if modality == "visual" and (not has_visual or has_verbal):
            raise ContractError(f"{path.name} visual claim refs are invalid")
        if modality == "verbal" and (has_visual or not has_verbal):
            raise ContractError(f"{path.name} verbal claim refs are invalid")
        if modality == "mixed" and (not has_visual or not has_verbal):
            raise ContractError(f"{path.name} mixed claim refs are invalid")
    gaps = analysis.get("gaps")
    if not isinstance(gaps, list) or not all(
        isinstance(gap, str) and gap.strip() for gap in gaps
    ):
        raise ContractError(f"{path.name} gaps are invalid")

    if status == "unavailable":
        if frames or transcript or analysis_frames or claims:
            raise ContractError(f"{path.name} unavailable receipt contains evidence")
        if value.get("model_role") is not None or value.get("effective_model") is not None:
            raise ContractError(f"{path.name} unavailable receipt cannot name a model")
        if value.get("prompt_contract_version") is not None:
            raise ContractError(f"{path.name} unavailable receipt cannot name a prompt")
    else:
        if not frames and not transcript:
            raise ContractError(f"{path.name} completed receipt has no evidence")
        if value.get("prompt_contract_version") != MEDIA_PROMPT_CONTRACT_VERSION:
            raise ContractError(f"{path.name} media prompt contract mismatch")
        require_string(value.get("model_role"), f"{path.name} model_role")
        require_string(value.get("effective_model"), f"{path.name} effective_model")
    parse_rfc3339(value.get("completed_at"), f"{path.name} completed_at")
    return value


def parse_rfc3339(value: Any, field: str) -> datetime:
    text = require_string(value, field)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        result = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractError(f"{field} must be RFC3339: {text}") from exc
    if result.tzinfo is None:
        raise ContractError(f"{field} must include a timezone")
    return result.astimezone(timezone.utc)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def resolve_relative(root: Path, value: Any, field: str) -> Path:
    text = require_string(value, field)
    relative = Path(text)
    if relative.is_absolute() or ".." in relative.parts or relative == Path("."):
        raise ContractError(f"{field} must be a safe relative path")
    root_resolved = root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ContractError(f"{field} escapes runtime root") from exc
    return candidate


def validate_context(path: Path) -> dict[str, Any]:
    value = read_json(path)
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("context.schema_version must be 1")
    if value.get("section_id") != SECTION_ID:
        raise ContractError(f"context.section_id must be {SECTION_ID}")
    require_string(value.get("assignment"), "context.assignment")
    require_string(value.get("product_context"), "context.product_context")
    collection_parameters(value)
    limit = value.get("max_analysis_videos")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 30):
        raise ContractError("context.max_analysis_videos must be an integer from 1 to 30 (adapter resource ceiling)")

    supporting = value.get("supporting_sections", [])
    if not isinstance(supporting, list):
        raise ContractError("context.supporting_sections must be a list")
    ids: list[str] = []
    for index, item in enumerate(supporting):
        if not isinstance(item, dict):
            raise ContractError(f"context.supporting_sections[{index}] must be an object")
        section_id = require_string(
            item.get("id"), f"context.supporting_sections[{index}].id"
        )
        require_string(item.get("label"), f"context.supporting_sections[{index}].label")
        require_string(
            item.get("content"), f"context.supporting_sections[{index}].content"
        )
        if section_id in ids:
            raise ContractError(f"duplicate supporting section: {section_id}")
        ids.append(section_id)
    sources = value.get("sources", {})
    if not isinstance(sources, dict):
        raise ContractError("context.sources must be an object")
    context_source = sources.get("context")
    if context_source is not None:
        if not isinstance(context_source, dict):
            raise ContractError("context.sources.context must be an object")
        require_string(context_source.get("path"), "context.sources.context.path")
        require_sha256(context_source.get("source_sha256"), "context.sources.context.source_sha256")
    source_sections = sources.get("supporting_sections", [])
    if not isinstance(source_sections, list):
        raise ContractError("context.sources.supporting_sections must be a list")
    source_ids: list[str] = []
    for index, item in enumerate(source_sections):
        if not isinstance(item, dict):
            raise ContractError(
                f"context.sources.supporting_sections[{index}] must be an object"
            )
        section_id = require_string(
            item.get("id"), f"context.sources.supporting_sections[{index}].id"
        )
        require_string(
            item.get("path"), f"context.sources.supporting_sections[{index}].path"
        )
        require_sha256(
            item.get("source_sha256"),
            f"context.sources.supporting_sections[{index}].source_sha256",
        )
        source_ids.append(section_id)
    if source_ids and source_ids != ids:
        raise ContractError(
            "context supporting content and source metadata must name the same sections"
        )
    return value


def collection_parameters(context: dict[str, Any]) -> dict[str, int]:
    """Resolve the one caller-owned collection scope; not an evidence threshold."""
    supplied = context.get("collection", {})
    defaults = {"discovery_limit_per_account": 30, "lookback_days": 60}
    if not isinstance(supplied, dict) or set(supplied) - set(defaults):
        raise ContractError("context.collection has unsupported fields")
    result = {**defaults, **supplied}
    for name, value in result.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ContractError(f"context.collection.{name} must be a positive integer")
    if result["discovery_limit_per_account"] > 30:
        raise ContractError("context.collection.discovery_limit_per_account must be from 1 to 30")
    return result


def validate_accounts(value: Any, field: str = "accounts") -> list[dict[str, Any]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 6:
        raise ContractError(f"{field} must contain 1–6 accounts")
    seen: set[tuple[str, str]] = set()
    for index, account in enumerate(value):
        item_field = f"{field}[{index}]"
        if not isinstance(account, dict):
            raise ContractError(f"{item_field} must be an object")
        if set(account) - {
            "platform",
            "handle",
            "account_type",
            "product_keywords",
            "followers",
        }:
            raise ContractError(f"{item_field} contains unsupported fields")
        platform = require_string(account.get("platform"), f"{item_field}.platform")
        if platform not in {"tiktok", "instagram"}:
            raise ContractError(f"{item_field}.platform is unsupported")
        handle = require_string(account.get("handle"), f"{item_field}.handle")
        account_type = require_string(
            account.get("account_type"), f"{item_field}.account_type"
        )
        if account_type not in {
            "official",
            "shadow",
            "partner",
            "shadow-or-partner",
            "viral",
        }:
            raise ContractError(f"{item_field}.account_type is unsupported")
        keywords = account.get("product_keywords")
        if not isinstance(keywords, list) or not all(
            isinstance(item, str) and item.strip() for item in keywords
        ):
            raise ContractError(f"{item_field}.product_keywords must be strings")
        followers = account.get("followers")
        if followers is not None and (
            not isinstance(followers, (int, float))
            or isinstance(followers, bool)
            or followers < 0
        ):
            raise ContractError(f"{item_field}.followers must be non-negative or null")
        identity = (platform, handle.casefold().lstrip("@"))
        if identity in seen:
            raise ContractError(f"duplicate account: {platform}/{handle}")
        seen.add(identity)
    return value


def validate_accounts_file(root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    relative = "raw/accounts.json"
    path = resolve_relative(root, relative, "accounts source")
    value = read_json(path)
    if set(value) != {"accounts"}:
        raise ContractError("raw/accounts.json must contain exactly an accounts field")
    accounts = validate_accounts(value.get("accounts"), "raw accounts")
    return accounts, {"path": relative, "sha256": sha256_file(path)}


def runtime_root_from_workspace(workspace: Path) -> Path:
    return workspace.resolve() / RUNTIME_RELATIVE


def artifact_ref(root: Path, relative: str) -> dict[str, str]:
    path = resolve_relative(root, relative, relative)
    if not path.is_file():
        raise ContractError(f"missing runtime artifact: {relative}")
    return {"path": relative, "sha256": sha256_file(path)}


def extract_rows(value: Any) -> list[dict[str, Any]]:
    """Recognize an empty dataset, but do not turn invalid responses into no-data."""
    rows: Any = None
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        data = value.get("data")
        if isinstance(data, dict) and "rows" in data:
            rows = data["rows"]
        elif "rows" in value:
            rows = value["rows"]
        elif "items" in value:
            rows = value["items"]
        elif isinstance(data, list):
            rows = data
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ContractError("provider dataset must contain an explicit list of row objects")
    return rows


def _nested_value(value: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        current: Any = value
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if current is not None:
            return current
    return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def apify_dataset_id_from_url(value: Any) -> str:
    text = require_string(value, "commentsDatasetURL")
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ContractError("commentsDatasetURL must be an HTTP(S) URL")
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    try:
        dataset_index = parts.index("datasets")
        dataset_id = parts[dataset_index + 1]
    except (ValueError, IndexError) as exc:
        raise ContractError("commentsDatasetURL does not identify an Apify dataset") from exc
    if APIFY_DATASET_ID_RE.fullmatch(dataset_id) is None:
        raise ContractError("commentsDatasetURL contains an invalid Apify dataset ID")
    return dataset_id


def linked_tiktok_comment_requests(
    main_payload: Any,
) -> list[dict[str, Any]]:
    """Return the exact linked comment datasets declared by TikTok video rows."""

    grouped: dict[str, dict[str, Any]] = {}
    for row_index, row in enumerate(extract_rows(main_payload)):
        dataset_url = _nested_value(row, "commentsDatasetURL", "commentsDatasetUrl")
        if dataset_url is None:
            continue
        dataset_id = apify_dataset_id_from_url(dataset_url)
        video_id = _optional_text(
            _nested_value(row, "id", "videoId", "aweme_id")
        )
        if video_id is None:
            raise ContractError(
                f"TikTok row {row_index} has commentsDatasetURL but no video identity"
            )
        video_url = _optional_text(
            _nested_value(row, "webVideoUrl", "postUrl", "inputUrl", "url")
        )
        parent = {"video_id": video_id, "video_url": video_url}
        entry = grouped.setdefault(
            dataset_id,
            {
                "dataset_id": dataset_id,
                "source_urls": [],
                "parents": [],
            },
        )
        source_url = str(dataset_url).strip()
        if source_url not in entry["source_urls"]:
            entry["source_urls"].append(source_url)
        if parent not in entry["parents"]:
            entry["parents"].append(parent)
    for entry in grouped.values():
        entry["source_urls"].sort()
        entry["parents"].sort(
            key=lambda parent: (parent["video_id"], parent.get("video_url") or "")
        )
    return [grouped[dataset_id] for dataset_id in sorted(grouped)]


def validate_linked_tiktok_comments_bundle(
    main_payload: Any,
    bundle: Any,
) -> dict[str, list[dict[str, Any]]]:
    """Validate linked raw responses and group their comment rows by parent video."""

    if not isinstance(bundle, dict) or bundle.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("TikTok linked comments bundle schema_version must be 1")
    if bundle.get("source_logical_key") != "tiktok-enrichment":
        raise ContractError("TikTok linked comments bundle has the wrong source run")
    expected_source_hash = sha256_bytes(
        (json.dumps(main_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
    )
    if bundle.get("source_dataset_sha256") != expected_source_hash:
        raise ContractError("TikTok linked comments source dataset hash mismatch")
    expected = linked_tiktok_comment_requests(main_payload)
    datasets = bundle.get("datasets")
    if not isinstance(datasets, list) or len(datasets) != len(expected):
        raise ContractError("TikTok linked comments datasets differ from actor output")

    comments_by_video: dict[str, list[dict[str, Any]]] = {}
    for index, (actual, expected_entry) in enumerate(zip(datasets, expected, strict=True)):
        if not isinstance(actual, dict):
            raise ContractError(f"TikTok linked comments dataset {index} must be an object")
        for field in ("dataset_id", "source_urls", "parents"):
            if actual.get(field) != expected_entry[field]:
                raise ContractError(
                    f"TikTok linked comments dataset {index} changed {field}"
                )
        response = actual.get("response")
        if not isinstance(response, dict):
            raise ContractError(
                f"TikTok linked comments dataset {index} has no raw OS response"
            )
        parents = expected_entry["parents"]
        parent_ids = {parent["video_id"] for parent in parents}
        parent_urls = {
            parent["video_url"]: parent["video_id"]
            for parent in parents
            if parent.get("video_url")
        }
        for comment in extract_rows(response):
            comment_video_id = _optional_text(
                _nested_value(comment, "videoId", "aweme_id")
            )
            comment_video_url = _optional_text(
                _nested_value(comment, "videoWebUrl", "webVideoUrl", "postUrl")
            )
            if comment_video_id not in parent_ids:
                comment_video_id = parent_urls.get(comment_video_url or "")
            if comment_video_id is None and len(parent_ids) == 1:
                comment_video_id = next(iter(parent_ids))
            if comment_video_id is None or comment_video_id not in parent_ids:
                raise ContractError(
                    f"TikTok linked comment in dataset {actual['dataset_id']} "
                    "cannot be bound to a parent video"
                )
            comments_by_video.setdefault(comment_video_id, []).append(comment)
    return comments_by_video


def validate_provider_run(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{field} must be an object")
    result = {
        "logical_key": require_string(
            value.get("logical_key"), f"{field}.logical_key"
        ),
        "provider": require_string(value.get("provider"), f"{field}.provider"),
        "actor_id": require_string(value.get("actor_id"), f"{field}.actor_id"),
        "run_id": require_string(value.get("run_id"), f"{field}.run_id"),
        "dataset_id": require_string(value.get("dataset_id"), f"{field}.dataset_id"),
        "status": require_string(value.get("status"), f"{field}.status"),
        "input_sha256": require_sha256(
            value.get("input_sha256"), f"{field}.input_sha256"
        ),
        "input_contract_version": require_string(
            value.get("input_contract_version"), f"{field}.input_contract_version"
        ),
    }
    if result["provider"] != "apify" or result["status"] != "SUCCEEDED":
        raise ContractError(f"{field} must be a successful Apify run")
    expected = CANONICAL_PROVIDER_RUNS.get(result["logical_key"])
    if expected is None or result["actor_id"] != expected["actor_id"]:
        raise ContractError(f"{field} is not a canonical organic trend run")
    if result["input_contract_version"] != PROVIDER_INPUT_CONTRACT_VERSION:
        raise ContractError(f"{field} input contract version mismatch")
    input_keys = value.get("input_keys")
    if not isinstance(input_keys, list) or input_keys != sorted(expected["input_keys"]):
        raise ContractError(f"{field}.input_keys do not match the canonical adapter")
    result["input_keys"] = input_keys
    metadata = value.get("actor_metadata")
    if not isinstance(metadata, dict):
        raise ContractError(f"{field}.actor_metadata must be an object")
    result["actor_metadata"] = {
        "path": require_string(metadata.get("path"), f"{field}.actor_metadata.path"),
        "sha256": require_sha256(
            metadata.get("sha256"), f"{field}.actor_metadata.sha256"
        ),
    }
    return result


def validate_raw_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / "raw/manifest.json"
    value = read_json(manifest_path)
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("raw manifest schema_version must be 1")
    require_string(
        value.get("collection_epoch"), "raw manifest collection_epoch"
    )
    started = parse_rfc3339(value.get("collection_started_at"), "collection_started_at")
    completed = parse_rfc3339(
        value.get("collection_completed_at"), "collection_completed_at"
    )
    if completed < started:
        raise ContractError("collection_completed_at precedes collection_started_at")

    accounts = validate_accounts(value.get("accounts"), "raw manifest accounts")
    file_accounts, accounts_source = validate_accounts_file(root)
    if value.get("accounts_source") != accounts_source:
        raise ContractError("raw manifest accounts_source hash mismatch")
    if accounts != file_accounts:
        raise ContractError("raw manifest accounts differ from raw/accounts.json")

    datasets = value.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ContractError("raw manifest datasets must be a non-empty list")
    dataset_shapes_seen: set[tuple[str, str]] = set()
    for index, dataset in enumerate(datasets):
        if not isinstance(dataset, dict):
            raise ContractError(f"datasets[{index}] must be an object")
        platform = require_string(dataset.get("platform"), f"datasets[{index}].platform")
        if platform not in {"tiktok", "instagram"}:
            raise ContractError(f"datasets[{index}].platform is unsupported")
        kind = require_string(dataset.get("kind"), f"datasets[{index}].kind")
        if kind not in {"discovery", "enrichment"}:
            raise ContractError(f"datasets[{index}].kind is unsupported")
        shape = (platform, kind)
        logical_key = f"{platform}-{kind}"
        if shape in dataset_shapes_seen:
            raise ContractError(f"duplicate raw manifest dataset: {logical_key}")
        dataset_shapes_seen.add(shape)
        if logical_key not in CANONICAL_PROVIDER_RUNS:
            raise ContractError(f"datasets[{index}] is not a canonical provider run")
        if dataset.get("path") != f"raw/{logical_key}.json":
            raise ContractError(
                f"datasets[{index}].path must be raw/{logical_key}.json"
            )
        path = resolve_relative(root, dataset.get("path"), f"datasets[{index}].path")
        expected = require_sha256(dataset.get("sha256"), f"datasets[{index}].sha256")
        if not path.is_file() or sha256_file(path) != expected:
            raise ContractError(f"datasets[{index}] file hash mismatch")

    runs = value.get("provider_runs")
    if not isinstance(runs, list) or not 1 <= len(runs) <= len(CANONICAL_PROVIDER_RUNS):
        raise ContractError("raw manifest provider_runs must contain 1–4 runs")
    logical_keys: set[str] = set()
    run_ids: set[str] = set()
    dataset_ids: set[str] = set()
    for index, run in enumerate(runs):
        canonical = validate_provider_run(run, f"provider_runs[{index}]")
        metadata_path = resolve_relative(
            root,
            canonical["actor_metadata"]["path"],
            f"provider_runs[{index}].actor_metadata.path",
        )
        if (
            not metadata_path.is_file()
            or sha256_file(metadata_path) != canonical["actor_metadata"]["sha256"]
        ):
            raise ContractError(
                f"provider_runs[{index}].actor_metadata hash mismatch"
            )
        expected_metadata_path = (
            f"raw/{canonical['logical_key']}-actor-metadata.json"
        )
        if canonical["actor_metadata"]["path"] != expected_metadata_path:
            raise ContractError(
                f"provider_runs[{index}].actor_metadata.path must be "
                f"{expected_metadata_path}"
            )
        if canonical["logical_key"] in logical_keys:
            raise ContractError("raw manifest provider_runs contains a duplicate logical_key")
        if canonical["run_id"] in run_ids or canonical["dataset_id"] in dataset_ids:
            raise ContractError("raw manifest provider_runs contains duplicate provider IDs")
        logical_keys.add(canonical["logical_key"])
        run_ids.add(canonical["run_id"])
        dataset_ids.add(canonical["dataset_id"])
    run_shapes = {
        (
            CANONICAL_PROVIDER_RUNS[key]["platform"],
            CANONICAL_PROVIDER_RUNS[key]["kind"],
        )
        for key in logical_keys
    }
    dataset_shapes = {
        (dataset["platform"], dataset["kind"])
        for dataset in datasets
        if isinstance(dataset, dict)
    }
    if dataset_shapes != run_shapes:
        raise ContractError("raw manifest datasets do not match canonical provider runs")

    required_discovery_keys = {
        f"{account['platform']}-discovery" for account in accounts
    }
    if not required_discovery_keys.issubset(logical_keys):
        state = load_run_state(root)
        missing = []
        for key in sorted(required_discovery_keys - logical_keys):
            run = state["provider_runs"].get(key)
            if (not isinstance(run, dict)
                    or run.get("status") not in TERMINAL_PROVIDER_FAILURE_STATUSES
                    or not isinstance(run.get("run_id"), str)
                    or not run["run_id"].strip()):
                missing.append(key)
        if missing:
            raise ContractError(
                f"raw manifest is missing required discovery runs: {', '.join(missing)}"
            )

    linked_datasets = value.get("linked_datasets")
    if not isinstance(linked_datasets, list):
        raise ContractError("raw manifest linked_datasets must be a list")
    expected_linked_count = 1 if "tiktok-enrichment" in logical_keys else 0
    if len(linked_datasets) != expected_linked_count:
        raise ContractError(
            "raw manifest must contain exactly one TikTok comments bundle when "
            "TikTok enrichment is present"
        )
    if linked_datasets:
        linked = linked_datasets[0]
        if not isinstance(linked, dict):
            raise ContractError("raw manifest linked dataset must be an object")
        if (
            linked.get("kind") != TIKTOK_COMMENTS_LINK_KIND
            or linked.get("parent_logical_key") != "tiktok-enrichment"
            or linked.get("path") != TIKTOK_COMMENTS_BUNDLE_PATH
        ):
            raise ContractError("raw manifest TikTok comments bundle identity is invalid")
        linked_path = resolve_relative(
            root,
            linked.get("path"),
            "linked_datasets[0].path",
        )
        linked_hash = require_sha256(
            linked.get("sha256"),
            "linked_datasets[0].sha256",
        )
        if not linked_path.is_file() or sha256_file(linked_path) != linked_hash:
            raise ContractError("raw manifest TikTok comments bundle hash mismatch")
        main_dataset = read_json(root / "raw/tiktok-enrichment.json")
        bundle = read_json(linked_path)
        validate_linked_tiktok_comments_bundle(main_dataset, bundle)

    return value


def validate_collection_fresh(manifest: dict[str, Any]) -> None:
    """Validate the collection clock, not a methodological expiry date."""
    completed = parse_rfc3339(
        manifest.get("collection_completed_at"), "collection_completed_at"
    )
    age_seconds = (datetime.now(timezone.utc) - completed).total_seconds()
    if age_seconds < -300:
        raise ContractError("collection completion time is in the future")


def validate_manifest_against_state(
    root: Path, manifest: dict[str, Any], state: dict[str, Any]
) -> None:
    from _provider_inputs import build_discovery_inputs, validate_collection_window

    context = validate_context(root / "context.json")
    window = validate_collection_window(context, state.get("collection_window"))
    if manifest.get("collection_started_at") != window["reference_at"]:
        raise ContractError("raw manifest collection start differs from the first attempt")
    discovery_inputs = build_discovery_inputs(manifest["accounts"], context, window)
    if manifest.get("collection_epoch") != state.get("collection_epoch"):
        raise ContractError("raw manifest belongs to a different collection epoch")
    if manifest.get("accounts_source") != state.get("accounts_source"):
        raise ContractError("raw manifest accounts source differs from run-state")
    manifest_runs = {
        item["logical_key"]: item
        for item in (
            validate_provider_run(run, f"manifest.provider_runs[{index}]")
            for index, run in enumerate(manifest["provider_runs"])
        )
    }
    completed_state_runs = {
        key: value
        for key, value in state["provider_runs"].items()
        if isinstance(value, dict) and value.get("status") == "SUCCEEDED"
    }
    if set(manifest_runs) != set(completed_state_runs):
        raise ContractError("raw manifest provider runs differ from completed run-state handles")
    datasets = {
        (item["platform"], item["kind"]): item for item in manifest["datasets"]
    }
    for key, manifest_run in manifest_runs.items():
        state_run = completed_state_runs[key]
        for field in (
            "actor_id",
            "run_id",
            "dataset_id",
            "status",
            "input_sha256",
            "input_contract_version",
            "input_keys",
            "actor_metadata",
        ):
            if state_run.get(field) != manifest_run.get(field):
                raise ContractError(f"provider run {key} differs from run-state field {field}")
        input_path = resolve_relative(root, state_run.get("input_path"), f"{key}.input_path")
        if state_run.get("input_path") != f"raw/{key}-input.json":
            raise ContractError(f"provider run {key} input path is not canonical")
        if not input_path.is_file() or sha256_file(input_path) != manifest_run["input_sha256"]:
            raise ContractError(f"provider run {key} input hash mismatch")
        if key in discovery_inputs and read_json(input_path) != discovery_inputs[key]:
            raise ContractError(f"provider run {key} input differs from the frozen collection scope")
        expected_idempotency_key = provider_idempotency_key(
            state["context_sha256"],
            state["collection_epoch"],
            key,
            manifest_run["actor_id"],
            manifest_run["input_sha256"],
        )
        if state_run.get("idempotency_key") != expected_idempotency_key:
            raise ContractError(f"provider run {key} idempotency key mismatch")
        spec = CANONICAL_PROVIDER_RUNS[key]
        dataset = datasets[(spec["platform"], spec["kind"])]
        if state_run.get("raw_path") != dataset["path"] or state_run.get("raw_sha256") != dataset["sha256"]:
            raise ContractError(f"provider run {key} raw dataset differs from run-state")


def provider_idempotency_key(
    context_hash: str,
    collection_epoch: str,
    key: str,
    actor_id: str,
    input_hash: str,
) -> str:
    raw = (
        "organic-trend-watch:"
        f"{context_hash}:{collection_epoch}:{key}:{actor_id}:{input_hash}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_run_state(root: Path) -> dict[str, Any]:
    context_path = root / "context.json"
    validate_context(context_path)
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "analysis_contract_version": ANALYSIS_CONTRACT_VERSION,
        "context_sha256": sha256_file(context_path),
        "collection_epoch": uuid.uuid4().hex,
        "status": "running",
        "created_at": now,
        "updated_at": now,
        "steps": {name: {"status": "pending"} for name in STEPS},
        "provider_runs": {},
    }


def load_run_state(root: Path) -> dict[str, Any]:
    value = read_json(root / "run-state.json")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("run-state schema_version must be 1")
    if value.get("section_id") != SECTION_ID:
        raise ContractError(f"run-state section_id must be {SECTION_ID}")
    if value.get("analysis_contract_version") != ANALYSIS_CONTRACT_VERSION:
        raise ContractError("run-state analysis contract version mismatch")
    expected = sha256_file(root / "context.json")
    if value.get("context_sha256") != expected:
        raise ContractError("run-state belongs to a different context.json")
    require_string(value.get("collection_epoch"), "run-state.collection_epoch")
    if not isinstance(value.get("steps"), dict) or not isinstance(
        value.get("provider_runs"), dict
    ):
        raise ContractError("run-state has invalid steps or provider_runs")
    if set(value["steps"]) != set(STEPS):
        raise ContractError("run-state must contain exactly the canonical steps")
    for step, step_state in value["steps"].items():
        if not isinstance(step_state, dict) or step_state.get("status") not in {
            "pending",
            "running",
            "completed",
            "failed",
        }:
            raise ContractError(f"run-state step {step} has an invalid status")
    return value


def save_run_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    atomic_write_json(root / "run-state.json", state)
