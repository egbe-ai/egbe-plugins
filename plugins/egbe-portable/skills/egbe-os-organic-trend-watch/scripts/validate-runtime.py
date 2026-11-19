#!/usr/bin/env python3
"""Stable integration validator for organic trend runtime artifacts."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from _analysis import coverage, load_and_validate_analysis, render_body
from _contract import (
    ANALYSIS_CONTRACT_VERSION,
    ContractError,
    SCHEMA_VERSION,
    SECTION_HEADING,
    SECTION_ID,
    parse_rfc3339,
    read_json,
    require_sha256,
    resolve_relative,
    runtime_root_from_workspace,
    sha256_file,
    load_run_state,
    validate_collection_fresh,
    validate_context,
    validate_manifest_against_state,
    validate_provider_run,
    validate_raw_manifest,
)


ARTIFACT_PATHS = {
    "raw_manifest": "raw/manifest.json",
    "normalized_videos": "normalized/videos.json",
    "analysis": "analysis.json",
    "result": "result.md",
}


def _validate_ref(root: Path, value: Any, field: str, expected_path: str) -> None:
    if not isinstance(value, dict):
        raise ContractError(f"{field} must be an object")
    if value.get("path") != expected_path:
        raise ContractError(f"{field}.path must be {expected_path}")
    expected_hash = require_sha256(value.get("sha256"), f"{field}.sha256")
    path = resolve_relative(root, expected_path, f"{field}.path")
    if not path.is_file() or sha256_file(path) != expected_hash:
        raise ContractError(f"{field} hash mismatch")


def validate_runtime(root: Path) -> dict[str, Any]:
    validate_context(root / "context.json")
    manifest = validate_raw_manifest(root)
    validate_collection_fresh(manifest)
    state = load_run_state(root)
    validate_manifest_against_state(root, manifest, state)
    if state.get("status") != "completed" or any(
        step.get("status") != "completed" for step in state["steps"].values()
    ):
        raise ContractError("run-state is not fully completed")
    analysis, normalized = load_and_validate_analysis(root)
    receipt = read_json(root / "receipt.json")
    result_coverage = coverage(analysis, normalized)
    if receipt.get("coverage") != result_coverage:
        raise ContractError("receipt.coverage differs from the evidence")
    expected_scalars = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "section_heading": SECTION_HEADING,
        "analysis_contract_version": ANALYSIS_CONTRACT_VERSION,
        "status": "completed" if result_coverage["status"] == "complete" else result_coverage["status"],
        "collection_epoch": state["collection_epoch"],
    }
    for field, expected in expected_scalars.items():
        if receipt.get(field) != expected:
            raise ContractError(f"receipt.{field} must be {expected!r}")
    collected = parse_rfc3339(receipt.get("collected_at"), "receipt.collected_at")
    completed = parse_rfc3339(receipt.get("completed_at"), "receipt.completed_at")
    if receipt.get("collected_at") != manifest.get("collection_completed_at"):
        raise ContractError("receipt.collected_at must equal raw manifest completion time")
    if completed < collected:
        raise ContractError("receipt.completed_at precedes collected_at")
    if state.get("completed_at") != receipt.get("completed_at"):
        raise ContractError("run-state and receipt completion times differ")
    _validate_ref(root, receipt.get("context"), "receipt.context", "context.json")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(ARTIFACT_PATHS):
        raise ContractError("receipt.artifacts must contain exactly the four canonical artifacts")
    for name, path in ARTIFACT_PATHS.items():
        _validate_ref(root, artifacts.get(name), f"receipt.artifacts.{name}", path)

    receipt_runs = receipt.get("provider_runs")
    if not isinstance(receipt_runs, list) or not receipt_runs:
        raise ContractError("receipt.provider_runs must be a non-empty list")
    canonical_receipt_runs = [
        validate_provider_run(item, f"receipt.provider_runs[{index}]")
        for index, item in enumerate(receipt_runs)
    ]
    canonical_manifest_runs = [
        validate_provider_run(item, f"manifest.provider_runs[{index}]")
        for index, item in enumerate(manifest["provider_runs"])
    ]
    if canonical_receipt_runs != canonical_manifest_runs:
        raise ContractError("receipt provider provenance differs from raw manifest")

    expected_result = render_body(analysis, normalized)
    try:
        result = (root / "result.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"cannot read result.md: {exc}") from exc
    if result != expected_result:
        raise ContractError("result.md differs from its deterministic rendering")
    if re.search(r"(?m)^#{1,2}\s", result) or f"## {SECTION_HEADING}" in result:
        raise ContractError("result.md must contain the section body without an H1/H2 wrapper")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--workspace", type=Path)
    target.add_argument("--runtime-root", type=Path)
    args = parser.parse_args()
    root = args.runtime_root.resolve() if args.runtime_root else runtime_root_from_workspace(args.workspace)
    try:
        validate_runtime(root)
    except (ContractError, OSError) as exc:
        print(f"invalid organic trend runtime: {exc}", file=sys.stderr)
        return 1
    print("organic trend runtime is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
