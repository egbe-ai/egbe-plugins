#!/usr/bin/env python3
"""Validate qualitative analysis and render deterministic report-section body."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from _contract import (
    ANALYSIS_CONTRACT_VERSION,
    CANONICAL_PROVIDER_RUNS,
    ContractError,
    SCHEMA_VERSION,
    TERMINAL_PROVIDER_FAILURE_STATUSES,
    parse_rfc3339,
    read_json,
    load_visual_analysis_instructions,
    load_run_state,
    require_sha256,
    require_string,
    resolve_relative,
    sha256_bytes,
    sha256_file,
    VISUAL_EVIDENCE_METHOD,
    canonical_frame_seconds,
    validate_visual_analysis_receipt,
    visual_analysis_receipt_path,
    validate_context,
)
from _provider_inputs import validate_collection_window


def _require_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractError(f"{field} must be a list")
    return value


def _require_refs(
    value: Any,
    field: str,
    videos: dict[str, dict[str, Any]],
) -> list[str]:
    refs = _require_list(value, field)
    if not refs or not all(isinstance(item, str) and item for item in refs):
        raise ContractError(f"{field} must contain observation IDs")
    if len(refs) != len(set(refs)):
        raise ContractError(f"{field} contains duplicate observation IDs")
    for ref in refs:
        if ref not in videos:
            raise ContractError(f"{field} references unknown observation {ref}")
    return refs


def _validate_normalized(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    path = root / "normalized/videos.json"
    value = read_json(path)
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("normalized schema_version must be 1")
    if value.get("analysis_contract_version") != ANALYSIS_CONTRACT_VERSION:
        raise ContractError("normalized analysis contract version mismatch")
    require_sha256(value.get("source_manifest_sha256"), "source_manifest_sha256")
    if value["source_manifest_sha256"] != sha256_file(root / "raw/manifest.json"):
        raise ContractError("normalized source_manifest_sha256 mismatch")
    selection_source = value.get("selection_source")
    if not isinstance(selection_source, dict) or selection_source.get("path") != "normalized/selection.json":
        raise ContractError("normalized.selection_source must reference normalized/selection.json")
    selection_path = resolve_relative(
        root, selection_source.get("path"), "normalized.selection_source.path"
    )
    selection_hash = require_sha256(
        selection_source.get("sha256"), "normalized.selection_source.sha256"
    )
    if not selection_path.is_file() or sha256_file(selection_path) != selection_hash:
        raise ContractError("normalized selection source hash mismatch")
    selection = read_json(selection_path)
    window = validate_collection_window(
        validate_context(root / "context.json"), load_run_state(root).get("collection_window")
    )
    if selection.get("collection_window") != window or value.get("collection_window") != window:
        raise ContractError("normalized collection window differs from the frozen selection")
    window_start = parse_rfc3339(window["oldest_post_date"] + "T00:00:00Z", "collection lower bound")
    window_end = parse_rfc3339(window["reference_at"], "collection reference_at")
    manifest = read_json(root / "raw/manifest.json")
    expected_discovery_sources = sorted(
        [
            {"path": item["path"], "sha256": item["sha256"]}
            for item in manifest.get("datasets", [])
            if isinstance(item, dict) and item.get("kind") == "discovery"
        ],
        key=lambda item: item["path"],
    )
    if (
        selection.get("schema_version") != SCHEMA_VERSION
        or selection.get("collection_epoch") != manifest.get("collection_epoch")
        or selection.get("discovery_sources") != expected_discovery_sources
    ):
        raise ContractError("frozen selection provenance is invalid")
    parse_rfc3339(value.get("generated_at"), "normalized.generated_at")
    rows = _require_list(value.get("videos"), "normalized.videos")
    by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(rows):
        if not isinstance(item, dict):
            raise ContractError(f"normalized.videos[{index}] must be an object")
        observation_id = require_string(
            item.get("observation_id"), f"normalized.videos[{index}].observation_id"
        )
        if observation_id in by_id:
            raise ContractError(f"duplicate normalized observation: {observation_id}")
        require_string(item.get("url"), f"normalized.videos[{index}].url")
        if not isinstance(item.get("selected_for_analysis"), bool):
            raise ContractError(
                f"normalized.videos[{index}].selected_for_analysis must be boolean"
            )
        posted_at = (parse_rfc3339(item["posted_at"], "observation posted_at")
                     if item.get("posted_at") is not None else None)
        expected_window_status = ("unknown_date" if posted_at is None else
                                  "in_window" if window_start <= posted_at <= window_end
                                  else "outside_window")
        if item.get("time_window_status") != expected_window_status:
            raise ContractError("normalized observation time-window status is invalid")
        if item["selected_for_analysis"] and expected_window_status != "in_window":
            raise ContractError("selected observation is outside the time-window sample")
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            raise ContractError(f"normalized.videos[{index}].evidence must be an object")
        video_path = evidence.get("video_path")
        if video_path is not None and not isinstance(video_path, str):
            raise ContractError(
                f"normalized.videos[{index}].evidence.video_path must be a string or null"
            )
        frame_paths = evidence.get("frame_paths")
        if not isinstance(frame_paths, list) or not all(
            isinstance(path, str) and path for path in frame_paths
        ):
            raise ContractError(
                f"normalized.videos[{index}].evidence.frame_paths must be a list of paths"
            )
        local_refs = ([video_path] if video_path else []) + frame_paths
        hashes = evidence.get("artifact_sha256")
        if not isinstance(hashes, dict) or set(hashes) != set(local_refs):
            raise ContractError(
                f"normalized.videos[{index}].evidence.artifact_sha256 must cover exactly local evidence"
            )
        for relative in local_refs:
            artifact = resolve_relative(
                root,
                relative,
                f"normalized.videos[{index}].evidence artifact",
            )
            expected_hash = require_sha256(
                hashes.get(relative),
                f"normalized.videos[{index}].evidence.artifact_sha256[{relative}]",
            )
            if not artifact.is_file() or sha256_file(artifact) != expected_hash:
                raise ContractError(
                    f"normalized.videos[{index}] local evidence hash mismatch: {relative}"
                )
        preparation = evidence.get("visual_preparation")
        if local_refs:
            if not isinstance(preparation, dict):
                raise ContractError(
                    f"normalized.videos[{index}] local visual evidence has no provider preparation proof"
                )
            if set(preparation) != {
                "method",
                "source_media_url_sha256",
                "video_path",
                "frame_samples",
            }:
                raise ContractError(
                    f"normalized.videos[{index}] visual preparation shape is invalid"
                )
            if preparation.get("method") != VISUAL_EVIDENCE_METHOD:
                raise ContractError(
                    f"normalized.videos[{index}] visual preparation method is invalid"
                )
            media_url = require_string(
                evidence.get("media_url"),
                f"normalized.videos[{index}].evidence.media_url",
            )
            expected_media_url_hash = sha256_bytes(media_url.encode("utf-8"))
            if preparation.get("source_media_url_sha256") != expected_media_url_hash:
                raise ContractError(
                    f"normalized.videos[{index}] visual preparation media URL hash mismatch"
                )
            if preparation.get("video_path") != video_path or video_path is None:
                raise ContractError(
                    f"normalized.videos[{index}] visual preparation video path mismatch"
                )
            frame_samples = preparation.get("frame_samples")
            if not isinstance(frame_samples, list) or not frame_samples:
                raise ContractError(
                    f"normalized.videos[{index}] visual preparation frame samples are empty"
                )
            prepared_frame_paths: list[str] = []
            prior_second = -1.0
            for sample_index, sample in enumerate(frame_samples):
                if not isinstance(sample, dict) or set(sample) != {"path", "second"}:
                    raise ContractError(
                        f"normalized.videos[{index}] frame sample {sample_index} is invalid"
                    )
                path_value = require_string(
                    sample.get("path"),
                    f"normalized.videos[{index}].frame_samples[{sample_index}].path",
                )
                second = sample.get("second")
                if (
                    not isinstance(second, (int, float))
                    or isinstance(second, bool)
                    or float(second)
                    not in set(
                        canonical_frame_seconds(
                            item.get("metrics", {}).get("duration_seconds")
                        )
                    )
                    or float(second) <= prior_second
                ):
                    raise ContractError(
                        f"normalized.videos[{index}] frame sample timing is invalid"
                    )
                prior_second = float(second)
                prepared_frame_paths.append(path_value)
            if prepared_frame_paths != frame_paths:
                raise ContractError(
                    f"normalized.videos[{index}] visual preparation frame paths mismatch"
                )
        elif preparation is not None:
            raise ContractError(
                f"normalized.videos[{index}] has visual preparation without local evidence"
            )
        comments = _require_list(
            item.get("comments"), f"normalized.videos[{index}].comments"
        )
        comment_ids: set[str] = set()
        for comment_index, comment in enumerate(comments):
            comment_field = f"normalized.videos[{index}].comments[{comment_index}]"
            if not isinstance(comment, dict):
                raise ContractError(f"{comment_field} must be an object")
            if set(comment) != {"comment_id", "text", "likes"}:
                raise ContractError(f"{comment_field} has an invalid shape")
            comment_id = require_string(
                comment.get("comment_id"), f"{comment_field}.comment_id"
            )
            require_string(comment.get("text"), f"{comment_field}.text")
            if comment_id in comment_ids:
                raise ContractError(
                    f"normalized.videos[{index}] contains duplicate comment IDs"
                )
            comment_ids.add(comment_id)
        by_id[observation_id] = item
    selection_gaps = _require_list(
        value.get("selection_gaps"), "normalized.selection_gaps"
    )
    if selection_gaps != sorted(selection_gaps) or not all(
        isinstance(item, str) and item.strip() for item in selection_gaps
    ):
        raise ContractError("normalized.selection_gaps must be sorted non-empty strings")
    if selection.get("selection_gaps") != selection_gaps:
        raise ContractError("normalized selection gaps differ from frozen selection")
    selected_ids = sorted(
        observation_id
        for observation_id, item in by_id.items()
        if item["selected_for_analysis"]
    )
    if selection.get("selected_observation_ids") != selected_ids:
        raise ContractError("normalized selected observations differ from frozen selection")
    return value, by_id


def _validate_axis(
    axis: Any,
    field: str,
    normalized: dict[str, Any],
    *,
    hook: bool,
    receipt: dict[str, Any],
) -> None:
    if not isinstance(axis, dict):
        raise ContractError(f"{field} must be an object")
    status = axis.get("status")
    if status not in {"observed", "unavailable"}:
        raise ContractError(f"{field}.status must be observed or unavailable")
    text = axis.get("text")
    refs = axis.get("evidence_refs")
    if not isinstance(text, str) or not isinstance(refs, list) or not all(
        isinstance(item, str) and item for item in refs
    ):
        raise ContractError(f"{field} text/evidence_refs are invalid")
    if status == "unavailable":
        if text.strip() or refs:
            raise ContractError(f"{field} unavailable axes cannot contain claims")
        return
    if not text.strip() or not refs:
        raise ContractError(f"{field} observed axis needs text and evidence")

    evidence = normalized["evidence"]
    frames = set(evidence.get("frame_paths") or [])
    video_path = evidence.get("video_path")
    visual_refs = frames | ({video_path} if isinstance(video_path, str) and video_path else set())
    transcript_available = bool(evidence.get("transcript"))
    receipt_refs = {
        frame["ref"] for frame in receipt["analysis"]["frames"]
    }
    if receipt["transcript"]["status"] == "available":
        receipt_refs.add("transcript")
    for ref in refs:
        if ref != "transcript" and ref not in visual_refs:
            raise ContractError(f"{field} cites evidence not attached to its observation: {ref}")
        if ref == "transcript" and not transcript_available:
            raise ContractError(f"{field} cites a missing transcript")
        if ref not in receipt_refs:
            raise ContractError(f"{field} cites evidence absent from multimodal analysis")
    if not hook:
        if not visual_refs.intersection(refs):
            raise ContractError(f"{field} requires frame evidence")
        return

    modality = axis.get("modality")
    if modality not in {"visual", "verbal", "mixed"}:
        raise ContractError(f"{field}.modality must be visual, verbal, or mixed")
    if modality in {"visual", "mixed"} and not visual_refs.intersection(refs):
        raise ContractError(f"{field} visual claim requires frame evidence")
    if modality in {"verbal", "mixed"} and "transcript" not in refs:
        raise ContractError(f"{field} verbal claim requires transcript evidence")


def _validate_proof_reference(
    proof: Any,
    field: str,
    normalized: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    if not isinstance(proof, dict):
        raise ContractError(f"{field} must be an object")
    status = proof.get("status")
    if status not in {"observed", "unavailable"}:
        raise ContractError(f"{field}.status must be observed or unavailable")
    claim = proof.get("claim")
    mechanism = proof.get("mechanism")
    refs = proof.get("evidence_refs")
    if not isinstance(claim, str) or not isinstance(mechanism, str):
        raise ContractError(f"{field} claim/mechanism must be strings")
    if not isinstance(refs, list) or not all(
        isinstance(item, str) and item for item in refs
    ):
        raise ContractError(f"{field}.evidence_refs must be a list of strings")
    if status == "unavailable":
        if claim.strip() or mechanism.strip() or refs:
            raise ContractError(f"{field} unavailable proof cannot contain claims")
        return
    if not claim.strip() or not mechanism.strip() or not refs:
        raise ContractError(f"{field} observed proof needs claim, mechanism, and evidence")

    evidence = normalized["evidence"]
    frames = set(evidence.get("frame_paths") or [])
    video_path = evidence.get("video_path")
    attached_refs = frames | (
        {video_path} if isinstance(video_path, str) and video_path else set()
    )
    if evidence.get("transcript"):
        attached_refs.add("transcript")
    if normalized.get("caption"):
        attached_refs.add("caption")
    if any(ref not in attached_refs for ref in refs):
        raise ContractError(f"{field} cites evidence not attached to its observation")
    receipt_refs = {
        frame["ref"] for frame in receipt["analysis"]["frames"]
    }
    if receipt["transcript"]["status"] == "available":
        receipt_refs.add("transcript")
    if normalized.get("caption"):
        receipt_refs.add("caption")
    if any(ref not in receipt_refs for ref in refs):
        raise ContractError(f"{field} cites evidence absent from multimodal analysis")


def _validate_evidence_statement(
    value: Any,
    field: str,
    normalized: dict[str, Any],
    receipt: dict[str, Any],
    *,
    allowed_modalities: set[str],
) -> None:
    if not isinstance(value, dict):
        raise ContractError(f"{field} must be an object")
    status = value.get("status")
    text = value.get("text")
    modality = value.get("modality")
    refs = value.get("evidence_refs")
    if status not in {"observed", "unavailable"}:
        raise ContractError(f"{field}.status must be observed or unavailable")
    if not isinstance(text, str) or not isinstance(refs, list) or not all(
        isinstance(ref, str) and ref for ref in refs
    ):
        raise ContractError(f"{field} text/evidence_refs are invalid")
    if status == "unavailable":
        if text.strip() or modality is not None or refs:
            raise ContractError(f"{field} unavailable statement cannot contain a claim")
        return
    if not text.strip() or not refs or len(refs) != len(set(refs)):
        raise ContractError(f"{field} observed statement needs text and evidence")
    if modality not in allowed_modalities:
        raise ContractError(f"{field}.modality is invalid")

    frame_refs = {frame["ref"] for frame in receipt["analysis"]["frames"]}
    transcript_available = receipt["transcript"]["status"] == "available"
    caption_available = bool(normalized.get("caption"))
    allowed_refs = set(frame_refs)
    if transcript_available:
        allowed_refs.add("transcript")
    if caption_available:
        allowed_refs.add("caption")
    if any(ref not in allowed_refs for ref in refs):
        raise ContractError(f"{field} cites unavailable evidence")
    has_visual = bool(set(refs) & frame_refs)
    has_verbal = "transcript" in refs
    has_caption = "caption" in refs
    expected = {
        "visual": (True, False, False),
        "verbal": (False, True, False),
        "mixed": (True, True, False),
        "caption": (False, False, True),
    }[modality]
    if (has_visual, has_verbal, has_caption) != expected:
        raise ContractError(f"{field} evidence refs do not match its modality")


def load_and_validate_analysis(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    normalized_payload, normalized = _validate_normalized(root)
    analysis = read_json(root / "analysis.json")
    if analysis.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("analysis.schema_version must be 1")
    if analysis.get("analysis_contract_version") != ANALYSIS_CONTRACT_VERSION:
        raise ContractError("analysis contract version mismatch")
    require_sha256(analysis.get("source_normalized_sha256"), "source_normalized_sha256")
    if analysis["source_normalized_sha256"] != sha256_file(root / "normalized/videos.json"):
        raise ContractError("analysis source_normalized_sha256 mismatch")
    parse_rfc3339(analysis.get("generated_at"), "analysis.generated_at")
    require_string(analysis.get("summary"), "analysis.summary")
    selected = {key for key, value in normalized.items() if value["selected_for_analysis"]}
    analyzed: dict[str, dict[str, Any]] = {}
    required_gaps = set(normalized_payload["selection_gaps"])
    for key, run in load_run_state(root)["provider_runs"].items():
        status = str(run.get("status", "")).upper() if isinstance(run, dict) else ""
        if status == "SUCCEEDED":
            continue
        if status not in TERMINAL_PROVIDER_FAILURE_STATUSES:
            raise ContractError(f"provider collection {key} is running or uncertain")
        required_gaps.add(f"Provider collection {key} ended with {status}.")
    instructions = load_visual_analysis_instructions()
    for index, item in enumerate(_require_list(analysis.get("videos"), "analysis.videos")):
        field = f"analysis.videos[{index}]"
        if not isinstance(item, dict):
            raise ContractError(f"{field} must be an object")
        observation_id = require_string(item.get("observation_id"), f"{field}.observation_id")
        if observation_id not in selected or observation_id in analyzed:
            raise ContractError(f"{field} references unselected or duplicate observation")
        source = normalized[observation_id]
        if item.get("url") != source["url"]:
            raise ContractError(f"{field}.url does not match normalized evidence")
        receipt_path = visual_analysis_receipt_path(root, observation_id)
        # Caption/metrics/comment analysis does not require a vision request.
        receipt = {"analysis": {"frames": []}, "transcript": {"status": "unavailable"}}
        if receipt_path.exists():
            receipt = validate_visual_analysis_receipt(root, source, instructions=instructions)
            if item.get("multimodal_receipt_sha256") != sha256_file(receipt_path):
                raise ContractError(f"{field}.multimodal_receipt_sha256 mismatch")
            required_gaps.update(receipt["analysis"]["gaps"])
        elif "multimodal_receipt_sha256" in item:
            raise ContractError(f"{field} references a missing multimodal receipt")
        for axis in ("thumb_stop", "hook"):
            if axis in item:
                _validate_axis(item[axis], f"{field}.{axis}", source,
                               hook=axis == "hook", receipt=receipt)
        if "proof_reference" in item:
            _validate_proof_reference(item["proof_reference"], f"{field}.proof_reference", source, receipt)
        for axis in ("format", "message", "cta"):
            if axis in item:
                _validate_evidence_statement(
                    item[axis], f"{field}.{axis}", source, receipt,
                    allowed_modalities={"visual", "verbal", "mixed", "caption"},
                )
        if "sound" in item and item["sound"] != source.get("sound"):
            raise ContractError(f"{field}.sound must equal normalized sound metadata")
        seen_comments: set[str] = set()
        comments = {comment["comment_id"]: comment for comment in source["comments"]}
        for number, insight in enumerate(_require_list(item.get("comment_analysis", []), f"{field}.comment_analysis")):
            label = f"{field}.comment_analysis[{number}]"
            if not isinstance(insight, dict) or not {"comment_id", "relevance", "reason"} <= set(insight) <= {"comment_id", "relevance", "reason", "insight"}:
                raise ContractError(f"{label} has an invalid shape")
            comment_id = require_string(insight.get("comment_id"), f"{label}.comment_id")
            if comment_id not in comments or comment_id in seen_comments:
                raise ContractError(f"{label} references absent or duplicate comment")
            seen_comments.add(comment_id)
            if insight.get("relevance") not in {"relevant", "uncertain", "irrelevant"}:
                raise ContractError(f"{label}.relevance is invalid")
            require_string(insight.get("reason"), f"{label}.reason")
            if insight["relevance"] == "relevant":
                require_string(insight.get("insight"), f"{label}.insight")
            elif insight.get("insight") not in (None, ""):
                raise ContractError(f"{label}.insight must be empty unless the comment is relevant")
        analyzed[observation_id] = item
    synthesis = analysis.get("synthesis")
    if not isinstance(synthesis, dict) or set(synthesis) != {"findings", "adaptations"}:
        raise ContractError("analysis.synthesis must contain findings and adaptations")
    for index, finding in enumerate(_require_list(synthesis["findings"], "synthesis.findings")):
        field = f"synthesis.findings[{index}]"
        if not isinstance(finding, dict) or set(finding) != {"text", "supporting_evidence_refs"}:
            raise ContractError(f"{field} has an invalid shape")
        require_string(finding["text"], f"{field}.text")
        refs = _require_list(finding["supporting_evidence_refs"], f"{field}.supporting_evidence_refs")
        if not refs or not all(isinstance(ref, str) for ref in refs) or len(refs) != len(set(refs)):
            raise ContractError(f"{field} needs unique evidence references")
        for ref in refs:
            observation_id, separator, axis = ref.rpartition("#")
            if not separator or observation_id not in analyzed:
                raise ContractError(f"{field} cites an unknown or unanalyzed observation")
            source, row = normalized[observation_id], analyzed[observation_id]
            if axis == "caption":
                present = bool(source.get("caption"))
            elif axis == "metrics":
                present = any(value is not None for value in source.get("metrics", {}).values())
            elif axis == "sound":
                present = any(source.get("sound", {}).values())
            elif axis.startswith("comment:"):
                comment_id = axis.removeprefix("comment:")
                present = any(comment["comment_id"] == comment_id for comment in source["comments"])
            else:
                present = axis in {"thumb_stop", "hook", "proof_reference", "format", "message", "cta"} and row.get(axis, {}).get("status") == "observed"
            if not present:
                raise ContractError(f"{field} cites unavailable or unobserved evidence: {ref}")
    for index, adaptation in enumerate(_require_list(synthesis["adaptations"], "synthesis.adaptations")):
        field = f"synthesis.adaptations[{index}]"
        if not isinstance(adaptation, dict) or set(adaptation) != {"name", "text", "reason", "source_observation_ids"}:
            raise ContractError(f"{field} has an invalid shape")
        for name in ("name", "text", "reason"):
            require_string(adaptation.get(name), f"{field}.{name}")
        _require_refs(adaptation.get("source_observation_ids"), f"{field}.source_observation_ids", analyzed)
    gaps = _require_list(analysis.get("evidence_gaps"), "analysis.evidence_gaps")
    if not all(isinstance(gap, str) and gap.strip() for gap in gaps):
        raise ContractError("analysis.evidence_gaps must contain non-empty strings")
    if not required_gaps.issubset(gaps):
        raise ContractError("analysis.evidence_gaps must preserve selection and media evidence gaps, including failed collection")
    return analysis, normalized


def coverage(analysis: dict[str, Any], normalized: dict[str, dict[str, Any]]) -> dict[str, Any]:
    selected = {key for key, item in normalized.items() if item["selected_for_analysis"]}
    analyzed = {item["observation_id"] for item in analysis["videos"]}
    gaps = list(analysis["evidence_gaps"])
    failed_collection = bool(set(gaps) & {
        f"Provider collection {key} ended with {status}."
        for key in CANONICAL_PROVIDER_RUNS for status in TERMINAL_PROVIDER_FAILURE_STATUSES
    })
    gaps.extend(f"{observation_id}: selected observation was not analyzed"
                for observation_id in sorted(selected - analyzed))
    for item in analysis["videos"]:
        for axis in ("thumb_stop", "hook", "proof_reference", "format", "message", "cta"):
            if item.get(axis, {}).get("status") == "unavailable":
                gaps.append(f"{item['observation_id']}: requested {axis.replace('_', ' ')} evidence unavailable")
    if not normalized:
        gaps.append("The collected provider results contain no matching observations.")
    if not normalized and not failed_collection:
        status = "no_data"
    else:
        status = "partial" if gaps else "complete"
    return {
        "status": status,
        "collected_count": len(normalized),
        "selected_count": len(selected),
        "analyzed_count": len(analyzed),
        "gaps": sorted(set(gaps)),
    }


def _sources(refs: Iterable[str], normalized: dict[str, dict[str, Any]]) -> str:
    return ", ".join(f"[@{normalized[ref]['account']['handle']}]({normalized[ref]['url']})"
                     for ref in refs)


def render_body(analysis: dict[str, Any], normalized: dict[str, dict[str, Any]]) -> str:
    result_coverage = coverage(analysis, normalized)
    lines = ["### Findings", "", analysis["summary"], ""]
    for finding in analysis["synthesis"]["findings"]:
        ids = list(dict.fromkeys(ref.rpartition("#")[0] for ref in finding["supporting_evidence_refs"]))
        lines.append(f"- {finding['text']} Sources: {_sources(ids, normalized)}")
    if analysis["synthesis"]["adaptations"]:
        lines.extend(["", "### Possible adaptations", ""])
        for item in analysis["synthesis"]["adaptations"]:
            lines.extend([f"- **{item['name']}:** {item['text']}",
                          f"  - Why: {item['reason']}",
                          f"  - Source references: {_sources(item['source_observation_ids'], normalized)}"])
    relevant_comments = [
        (row["observation_id"], insight)
        for row in analysis["videos"] for insight in row.get("comment_analysis", [])
        if insight["relevance"] == "relevant"
    ]
    if relevant_comments:
        lines.extend(["", "### Audience language", ""])
        for observation_id, insight in relevant_comments:
            source = normalized[observation_id]
            comment = next(comment for comment in source["comments"] if comment["comment_id"] == insight["comment_id"])
            lines.append(f"- “{comment['text']}” — {insight['insight']}. Source: {_sources([observation_id], normalized)}")
    lines.extend(["", "### Evidence coverage", "",
                  f"Collected {result_coverage['collected_count']} observations; "
                  f"selected {result_coverage['selected_count']}; analyzed {result_coverage['analyzed_count']}.",
                  f"Coverage: {result_coverage['status']}."])
    if result_coverage["gaps"]:
        lines.extend(["", *[f"- {gap}" for gap in result_coverage["gaps"]]])
    return "\n".join(lines).rstrip() + "\n"
