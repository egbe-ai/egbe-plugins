#!/usr/bin/env python3
"""Build the deterministic, provider-safe input for Organic Trend Watch."""

from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


SCHEMA_VERSION = 1
SECTION_ID = "organic_trend_watch"
OUTPUT_PATH = Path(_artifact_path("egbe-docs/research/market/work/organic_trend_watch/context.json"))
SUPPORTING_SECTION_IDS = (
    "target_audience",
    "competitive_landscape",
    "value_proposition",
    "acquisition_channels",
)


def _load_script(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load bundled script {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_context_manifest(workspace: Path, assignment: str, *, context_file=None,
                           discovery_limit_per_account=30, lookback_days=60) -> dict[str, Any]:
    """Return one stable context manifest without interpreting research text."""

    workspace = workspace.resolve()
    scripts_dir = Path(__file__).resolve().parent
    skill_root = scripts_dir.parent
    builder = _load_script("build-research-query.py", "pmr_organic_query_builder")
    workflow = _load_script(
        "research-section-workflow.py",
        "pmr_organic_section_workflow",
    )

    if not isinstance(assignment, str) or not assignment.strip():
        raise ValueError("A scoped research assignment is required")
    if type(discovery_limit_per_account) is not int or not 1 <= discovery_limit_per_account <= 30:
        raise ValueError("discovery_limit_per_account must be between 1 and 30")
    if type(lookback_days) is not int or lookback_days <= 0:
        raise ValueError("lookback_days must be positive")
    io = _load_script("research-artifact-io.py", "pmr_organic_inputs")
    selected = io.resolve_context(workspace, context_file=context_file)
    product_context = selected["text"] or assignment.strip()
    catalog = builder._read_json_object(
        skill_root / "references/catalog.v1.json",
        label="catalog",
    )

    supporting_sections: list[dict[str, str]] = []
    supporting_sources: list[dict[str, str]] = []
    for section_id in SUPPORTING_SECTION_IDS:
        body = workflow._completed_supporting_result(workspace, section_id)
        if body is None:
            continue
        relative_path = Path(_artifact_path("egbe-docs/research/market/work")) / section_id / "result.md"
        source_path = workspace / relative_path
        supporting_sections.append(
            {
                "id": section_id,
                "label": builder._catalog_label(catalog, section_id),
                "content": body,
            }
        )
        supporting_sources.append(
            {
                "id": section_id,
                "path": relative_path.as_posix(),
                "source_sha256": _file_sha256(source_path),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "product_context": product_context,
        "assignment": assignment.strip(),
        "collection": {"discovery_limit_per_account": discovery_limit_per_account,
                       "lookback_days": lookback_days},
        "supporting_sections": supporting_sections,
        "sources": {
            **({"context": {"path": next(iter(selected["sources"])),
                             "source_sha256": next(iter(selected["sources"].values()))}}
               if selected["sources"] else {}),
            "supporting_sections": supporting_sources,
        },
    }


def write_context_manifest(workspace: Path, assignment: str, *, context_file=None,
                           discovery_limit_per_account=30, lookback_days=60) -> tuple[Path, dict[str, Any]]:
    workspace = workspace.resolve()
    manifest = build_context_manifest(workspace, assignment, context_file=context_file,
                                     discovery_limit_per_account=discovery_limit_per_account,
                                     lookback_days=lookback_days)
    output = workspace / OUTPUT_PATH
    if output.exists() and output.parent.joinpath("run-state.json").exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        if existing != manifest:
            raise ValueError("Existing study context differs; use a new EGBE_RESEARCH_ID instead of overwriting a resumable collection")
    builder = _load_script("build-research-query.py", "pmr_organic_context_writer")
    builder.write_atomic(
        output,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return output, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    question = parser.add_mutually_exclusive_group(required=True)
    question.add_argument("--assignment", help="The bounded question this research should answer")
    question.add_argument("--assignment-file", type=Path)
    parser.add_argument("--context-file", type=Path, help="Explicit additional provider-safe context.")
    parser.add_argument("--discovery-limit-per-account", type=int, default=30)
    parser.add_argument("--lookback-days", type=int, default=60)
    args = parser.parse_args()
    try:
        assignment_path = args.assignment_file if not args.assignment_file or args.assignment_file.is_absolute() else args.workspace / args.assignment_file
        assignment = assignment_path.read_text(encoding="utf-8") if assignment_path else args.assignment
        output, manifest = write_context_manifest(args.workspace, assignment, context_file=args.context_file,
            discovery_limit_per_account=args.discovery_limit_per_account, lookback_days=args.lookback_days)
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(
        f"Wrote {output} with {len(manifest['supporting_sections'])} "
        "validated supporting section(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
