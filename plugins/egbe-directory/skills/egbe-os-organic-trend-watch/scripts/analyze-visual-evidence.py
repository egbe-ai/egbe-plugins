#!/usr/bin/env python3
"""Analyze selected video frames through OS and persist resumable receipts."""

from __future__ import annotations

import runpy as _egbe_runpy
from pathlib import Path as _EgbePath
_egbe_adapter = _EgbePath(__file__).with_name("connection_identity.py")
_connection_headers = _egbe_runpy.run_path(str(_egbe_adapter))["connection_headers"] if _egbe_adapter.is_file() else lambda _url: {}

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from _contract import (
    ContractError,
    MEDIA_PROMPT_CONTRACT_VERSION,
    MULTIMODAL_ANALYSIS_CONTRACT,
    SCHEMA_VERSION,
    atomic_write_json,
    load_visual_analysis_instructions,
    multimodal_input_sha256,
    read_json,
    sha256_bytes,
    sha256_file,
    utc_now,
    validate_visual_analysis_receipt,
    visual_analysis_receipt_path,
)

# Longer than the OS gateway's own media-analysis budget (300 s), so the
# gateway reports a slow upstream instead of the client giving up first.
DEFAULT_TIMEOUT_SECONDS = 330


def _frame_payloads(root: Path, observation: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = observation.get("evidence")
    if not isinstance(evidence, dict):
        raise ContractError("normalized observation evidence must be an object")
    preparation = evidence.get("visual_preparation")
    if preparation is None:
        return []
    if not isinstance(preparation, dict):
        raise ContractError("visual preparation must be an object or null")
    samples = preparation.get("frame_samples")
    if not isinstance(samples, list):
        raise ContractError("visual preparation frame_samples must be a list")
    hashes = evidence.get("artifact_sha256")
    if not isinstance(hashes, dict):
        raise ContractError("normalized observation artifact hashes are invalid")
    result: list[dict[str, Any]] = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ContractError(f"frame sample {index} must be an object")
        ref = sample.get("path")
        timestamp = sample.get("second")
        if not isinstance(ref, str) or not ref or ".." in Path(ref).parts:
            raise ContractError(f"frame sample {index} has an invalid ref")
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
            raise ContractError(f"frame sample {index} has an invalid timestamp")
        path = (root / ref).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ContractError(f"frame sample {index} escapes the runtime root") from exc
        digest = hashes.get(ref)
        if not isinstance(digest, str) or sha256_file(path) != digest:
            raise ContractError(f"frame sample {index} hash mismatch")
        media_type = mimetypes.guess_type(path.name)[0]
        if media_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ContractError(f"frame sample {index} has unsupported media type")
        result.append(
            {
                "ref": ref,
                "timestamp_seconds": float(timestamp),
                "media_type": media_type,
                "sha256": digest,
                "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
        )
    return result


def _transcript(observation: dict[str, Any]) -> str | None:
    evidence = observation.get("evidence")
    value = evidence.get("transcript") if isinstance(evidence, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _fingerprint_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ref": frame["ref"],
            "timestamp_seconds": frame["timestamp_seconds"],
            "media_type": frame["media_type"],
            "sha256": frame["sha256"],
        }
        for frame in frames
    ]


def _unavailable_receipt(
    observation_id: str,
    *,
    instructions: str,
) -> dict[str, Any]:
    frames: list[dict[str, Any]] = []
    return {
        "schema_version": SCHEMA_VERSION,
        "observation_id": observation_id,
        "analysis_contract": MULTIMODAL_ANALYSIS_CONTRACT,
        "prompt_contract_version": None,
        "status": "unavailable",
        "model_role": None,
        "effective_model": None,
        "input_sha256": multimodal_input_sha256(
            analysis_contract=MULTIMODAL_ANALYSIS_CONTRACT,
            instructions=instructions,
            frames=frames,
            transcript=None,
        ),
        "frames": frames,
        "transcript": {"status": "unavailable", "sha256": None},
        "analysis": {
            "frames": [],
            "sequence_summary": "",
            "transcript": {"status": "unavailable", "observations": []},
            "claims": [],
            "gaps": [
                "Media and transcript unavailable; no visual or verbal findings were produced."
            ],
        },
        "completed_at": utc_now(),
    }


def _post_json(url: str, api_key: str, payload: dict[str, Any], timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "EgbeOrganicTrendWatch/1",
        },
    )
    try:
        for _name, _value in _connection_headers(request.full_url).items():
            request.add_unredirected_header(_name, _value)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise ContractError(f"OS media analysis returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ContractError(f"OS media analysis is unreachable: {exc}") from exc
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ContractError("OS media analysis returned invalid JSON") from exc
    if not isinstance(value, dict) or value.get("code") != 200 or not isinstance(
        value.get("data"), dict
    ):
        raise ContractError("OS media analysis returned an invalid success envelope")
    return value["data"]


def analyze(
    root: Path,
    *,
    os_url: str,
    os_api_key: str,
    observation_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[int, int, int]:
    normalized = read_json(root / "normalized/videos.json")
    videos = normalized.get("videos")
    if not isinstance(videos, list):
        raise ContractError("normalized videos must be a list")
    selected = [
        video
        for video in videos
        if isinstance(video, dict)
        and video.get("selected_for_analysis") is True
        and (observation_id is None or video.get("observation_id") == observation_id)
    ]
    if observation_id is not None and len(selected) != 1:
        raise ContractError("observation ID must identify one selected video")
    if not selected:
        raise ContractError("no selected videos are available for multimodal analysis")
    selected.sort(key=lambda video: str(video.get("observation_id")))
    instructions = load_visual_analysis_instructions()
    completed = reused = unavailable = 0
    for video in selected:
        current_id = video.get("observation_id")
        if not isinstance(current_id, str) or not current_id:
            raise ContractError("selected video has no observation_id")
        frames = _frame_payloads(root, video)
        transcript = _transcript(video)
        receipt_path = visual_analysis_receipt_path(root, current_id)
        if receipt_path.is_file():
            try:
                validate_visual_analysis_receipt(
                    root,
                    video,
                    instructions=instructions,
                )
                reused += 1
                continue
            except ContractError:
                pass
        if not frames and not transcript:
            atomic_write_json(
                receipt_path,
                _unavailable_receipt(current_id, instructions=instructions),
            )
            unavailable += 1
            continue
        request_payload = {
            "schema_version": SCHEMA_VERSION,
            "analysis_contract": MULTIMODAL_ANALYSIS_CONTRACT,
            "instructions": instructions,
            "frames": frames,
            "transcript": transcript,
        }
        expected_input = multimodal_input_sha256(
            analysis_contract=MULTIMODAL_ANALYSIS_CONTRACT,
            instructions=instructions,
            frames=_fingerprint_frames(frames),
            transcript=transcript,
        )
        response = _post_json(
            f"{os_url.rstrip('/')}/v1/media/analyze",
            os_api_key,
            request_payload,
            timeout,
        )
        if response.get("input_sha256") != expected_input:
            raise ContractError("OS media analysis input hash mismatch")
        if response.get("analysis_contract") != MULTIMODAL_ANALYSIS_CONTRACT:
            raise ContractError("OS media analysis contract mismatch")
        if response.get("prompt_contract_version") != MEDIA_PROMPT_CONTRACT_VERSION:
            raise ContractError("OS media analysis prompt contract mismatch")
        analysis = response.get("analysis")
        if not isinstance(analysis, dict):
            raise ContractError("OS media analysis has no structured analysis")
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "observation_id": current_id,
            "analysis_contract": MULTIMODAL_ANALYSIS_CONTRACT,
            "prompt_contract_version": response["prompt_contract_version"],
            "status": "completed",
            "model_role": response.get("model_role"),
            "effective_model": response.get("effective_model"),
            "input_sha256": expected_input,
            "frames": _fingerprint_frames(frames),
            "transcript": {
                "status": "available" if transcript else "unavailable",
                "sha256": sha256_bytes(transcript.encode("utf-8")) if transcript else None,
            },
            "analysis": analysis,
            "completed_at": utc_now(),
        }
        if isinstance(response.get("usage"), dict):
            receipt["usage"] = response["usage"]
        atomic_write_json(receipt_path, receipt)
        validate_visual_analysis_receipt(
            root,
            video,
            instructions=instructions,
        )
        completed += 1
    return completed, reused, unavailable


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--observation-id")
    parser.add_argument("--os-url", default=os.environ.get("OS_URL"))
    parser.add_argument("--os-api-key", default=os.environ.get("OS_API_KEY"))
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()
    try:
        if not args.os_url or not args.os_api_key:
            raise ContractError("OS_URL and OS_API_KEY are required")
        if not 30 <= args.timeout_seconds <= 600:
            raise ContractError("timeout-seconds must be between 30 and 600")
        completed, reused, unavailable = analyze(
            args.runtime_root.resolve(),
            os_url=args.os_url,
            os_api_key=args.os_api_key,
            observation_id=args.observation_id,
            timeout=args.timeout_seconds,
        )
    except (ContractError, OSError, UnicodeDecodeError) as exc:
        print(f"organic multimodal analysis failed: {exc}", file=sys.stderr)
        return 1
    print(
        "organic multimodal analysis: "
        f"completed={completed} reused={reused} unavailable={unavailable}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
