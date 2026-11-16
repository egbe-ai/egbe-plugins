#!/usr/bin/env python3
"""Seal completed organic trend artifacts into a content-addressed receipt."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _analysis import coverage, load_and_validate_analysis, render_body
from _contract import (
    ANALYSIS_CONTRACT_VERSION,
    ContractError,
    SCHEMA_VERSION,
    SECTION_HEADING,
    SECTION_ID,
    artifact_ref,
    atomic_write_json,
    load_run_state,
    parse_rfc3339,
    save_run_state,
    utc_now,
    validate_collection_fresh,
    validate_context,
    validate_manifest_against_state,
    validate_provider_run,
    validate_raw_manifest,
)


def finalize(root: Path) -> dict:
    validate_context(root / "context.json")
    manifest = validate_raw_manifest(root)
    validate_collection_fresh(manifest)
    analysis, normalized = load_and_validate_analysis(root)
    expected_result = render_body(analysis, normalized)
    try:
        actual_result = (root / "result.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"cannot read result.md: {exc}") from exc
    if actual_result != expected_result:
        raise ContractError("result.md is not the deterministic rendering of analysis.json")

    state = load_run_state(root)
    validate_manifest_against_state(root, manifest, state)
    incomplete = [
        step
        for step in state["steps"]
        if not isinstance(state["steps"].get(step), dict)
        or state["steps"][step].get("status") != "completed"
    ]
    if incomplete:
        raise ContractError(f"run-state has incomplete required steps: {', '.join(incomplete)}")

    runs = [
        validate_provider_run(item, f"provider_runs[{index}]")
        for index, item in enumerate(manifest["provider_runs"])
    ]
    collected_at = manifest["collection_completed_at"]
    parse_rfc3339(collected_at, "collection_completed_at")
    result_coverage = coverage(analysis, normalized)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "section_heading": SECTION_HEADING,
        "analysis_contract_version": ANALYSIS_CONTRACT_VERSION,
        "status": "completed" if result_coverage["status"] == "complete" else result_coverage["status"],
        "coverage": result_coverage,
        "collection_epoch": state["collection_epoch"],
        "collected_at": collected_at,
        "completed_at": utc_now(),
        "context": artifact_ref(root, "context.json"),
        "artifacts": {
            "raw_manifest": artifact_ref(root, "raw/manifest.json"),
            "normalized_videos": artifact_ref(root, "normalized/videos.json"),
            "analysis": artifact_ref(root, "analysis.json"),
            "result": artifact_ref(root, "result.md"),
        },
        "provider_runs": runs,
    }
    if parse_rfc3339(receipt["completed_at"], "completed_at") < parse_rfc3339(
        collected_at, "collected_at"
    ):
        raise ContractError("completed_at precedes collected_at")
    atomic_write_json(root / "receipt.json", receipt)
    state["status"] = "completed"
    state["completed_at"] = receipt["completed_at"]
    save_run_state(root, state)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        finalize(args.runtime_root.resolve())
    except (ContractError, OSError) as exc:
        print(f"organic trend receipt finalization failed: {exc}", file=sys.stderr)
        return 1
    print("finalized organic trend receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
