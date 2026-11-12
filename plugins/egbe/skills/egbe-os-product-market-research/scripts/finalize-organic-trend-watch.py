#!/usr/bin/env python3
"""Validate Organic Trend Watch output, then persist its canonical report section."""

from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


SECTION_HEADING = "TikTok/Reels market trend research for this product"
RUNTIME_PATH = Path(_artifact_path("egbe-docs/research/market/work/organic_trend_watch"))
REPORT_PATH = Path(_artifact_path("egbe-docs/research/market/full-report.md"))
RESULT_FILENAME = "result.md"
SKILL_RECEIPT_FILENAME = "receipt.json"
INTEGRATION_RECEIPT_FILENAME = "integration-receipt.json"
VALIDATOR_PATH = Path("scripts/validate-runtime.py")
INTEGRATION_RECEIPT_SCHEMA_VERSION = 1
ORGANIC_RUNTIME_VALIDATION_TIMEOUT_SECONDS = 5 * 60


class OrganicTrendFinalizationError(RuntimeError):
    """The validated organic-trend result could not be materialized."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise OrganicTrendFinalizationError(
            f"cannot hash Organic Trend artifact {path}"
        ) from exc


def _read_skill_receipt(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OrganicTrendFinalizationError(
            "validated organic-trend-watch bundle left no readable receipt"
        ) from exc
    if not isinstance(value, dict):
        raise OrganicTrendFinalizationError(
            "validated organic-trend-watch receipt must be a JSON object"
        )
    collected_at = value.get("collected_at")
    collection_epoch = value.get("collection_epoch")
    if not isinstance(collected_at, str) or not collected_at.strip():
        raise OrganicTrendFinalizationError(
            "validated organic-trend-watch receipt has no collected_at"
        )
    if not isinstance(collection_epoch, str) or not collection_epoch.strip():
        raise OrganicTrendFinalizationError(
            "validated organic-trend-watch receipt has no collection_epoch"
        )
    coverage = value.get("coverage")
    expected = {"completed": "complete", "partial": "partial", "no_data": "no_data"}
    if value.get("status") not in expected or not isinstance(coverage, dict) or expected[value["status"]] != coverage.get("status"):
        raise OrganicTrendFinalizationError("organic-trend-watch receipt has missing or inconsistent coverage")
    return value


def _write_atomic_json(path: Path, value: dict[str, Any]) -> None:
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
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise OrganicTrendFinalizationError(
            "could not write Organic Trend integration receipt"
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write_integration_receipt(
    workspace: Path,
    *,
    result_body: str,
) -> Path:
    runtime = workspace / RUNTIME_PATH
    skill_receipt_path = runtime / SKILL_RECEIPT_FILENAME
    result_path = runtime / RESULT_FILENAME
    skill_receipt = _read_skill_receipt(skill_receipt_path)
    payload = {
        "schema_version": INTEGRATION_RECEIPT_SCHEMA_VERSION,
        "section_id": "organic_trend_watch",
        "section_heading": SECTION_HEADING,
        "status": skill_receipt["status"],
        "coverage": skill_receipt["coverage"],
        "collected_at": skill_receipt["collected_at"],
        "materialized_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "collection_epoch": skill_receipt["collection_epoch"],
        "skill_receipt": {
            "path": SKILL_RECEIPT_FILENAME,
            "sha256": _sha256_file(skill_receipt_path),
        },
        "result": {
            "path": RESULT_FILENAME,
            "sha256": _sha256_file(result_path),
        },
        "report_section_sha256": _sha256_bytes(result_body.encode("utf-8")),
        "publication_mode": "local",
        "context_sha256": _sha256_file(runtime / "context.json"),
    }
    output = runtime / INTEGRATION_RECEIPT_FILENAME
    _write_atomic_json(output, payload)
    return output


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


def validate_organic_runtime(
    workspace: Path,
    organic_skill_root: Path,
) -> None:
    """Delegate receipt validation to the skill that owns its contract."""

    organic_skill_root = organic_skill_root.resolve()
    validator = organic_skill_root / VALIDATOR_PATH
    if not organic_skill_root.joinpath("SKILL.md").is_file() or not validator.is_file():
        raise OrganicTrendFinalizationError(
            "organic-trend-watch bundle is missing SKILL.md or its receipt validator"
        )
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(validator),
                "--workspace",
                str(workspace),
            ],
            cwd=workspace,
            check=False,
            capture_output=True,
            text=True,
            timeout=ORGANIC_RUNTIME_VALIDATION_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise OrganicTrendFinalizationError(
            "could not run the organic-trend-watch receipt validator"
        ) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        suffix = f": {detail}" if detail else ""
        raise OrganicTrendFinalizationError(
            "organic-trend-watch receipt validation failed"
            f" (exit {completed.returncode}){suffix}"
        )


def validate_context_sources(workspace: Path) -> None:
    """PMR owns local source proof; the standalone skill owns runtime proof."""
    try:
        context = json.loads((workspace / RUNTIME_PATH / "context.json").read_text(encoding="utf-8"))
        builder = _load_script("build-organic-trend-context.py", "pmr_organic_finalizer_context")
        expected = builder.build_context_manifest(workspace, context["assignment"])
        source = context.get("sources", {}).get("context")
        if source:
            if ".." in Path(source["path"]).parts:
                raise ValueError("Declared source path is not canonical")
            source_path = workspace / source["path"]
            if source_path.is_file() and (
                _sha256_file(source_path) != source["source_sha256"]
                or source_path.read_text(encoding="utf-8").strip() != context.get("product_context")
            ):
                raise ValueError("Declared source differs from the collected context; review applicability")
        elif context.get("product_context") != context["assignment"].strip():
            raise ValueError("Unattributed context differs from the research assignment")
        expected_sections = {item["id"]: item for item in expected["supporting_sections"]}
        expected_sources = {item["id"]: item for item in expected["sources"]["supporting_sections"]}
        sections = context.get("supporting_sections", [])
        sources = context.get("sources", {}).get("supporting_sections", [])
        if (not isinstance(sections, list) or not isinstance(sources, list)
            or len(sections) != len(sources)
            or len({item["id"] for item in sections}) != len(sections)
            or {item["id"] for item in sections} != {item["id"] for item in sources}
            or any(item != expected_sections.get(item["id"]) for item in sections)
            or any(item != expected_sources.get(item["id"]) for item in sources)):
            raise ValueError("Supporting source is missing, changed or unverified")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise OrganicTrendFinalizationError(f"Organic Trend context source validation failed: {exc}") from exc


RuntimeValidator = Callable[[Path, Path], None]
Materializer = Callable[[Path, str, str], Any]
Persister = Callable[[Path], Any]


def finalize_organic_trend_watch(
    workspace: Path,
    organic_skill_root: Path,
    *,
    runtime_validator: RuntimeValidator = validate_organic_runtime,
    materialize: Materializer | None = None,
    persist: Persister | None = None,
) -> Any:
    """Validate first, then materialize and persist exactly one report section."""

    workspace = workspace.resolve()
    runtime_validator(workspace, organic_skill_root)
    validate_context_sources(workspace)
    _read_skill_receipt(workspace / RUNTIME_PATH / SKILL_RECEIPT_FILENAME)

    result_path = workspace / RUNTIME_PATH / RESULT_FILENAME
    try:
        result = result_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise OrganicTrendFinalizationError(
            f"cannot read validated organic-trend result {result_path}"
        ) from exc
    if not result:
        raise OrganicTrendFinalizationError(
            "validated organic-trend result must not be empty"
        )

    if materialize is None:
        upsert = _load_script("upsert-markdown-section.py", "pmr_organic_upsert")
        materialize = upsert.upsert_markdown_section
    if persist is None:
        persistence = _load_script(
            "persist-research-report.py",
            "pmr_organic_persistence",
        )
        persist = persistence.persist_research_report
    materialize(workspace / REPORT_PATH, SECTION_HEADING, result)
    persistence = persist(workspace)
    _write_integration_receipt(
        workspace,
        result_body=result,
    )
    return persistence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--organic-skill-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        finalize_organic_trend_watch(
            args.workspace,
            args.organic_skill_root,
        )
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print("Organic trend research materialized locally")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
