#!/usr/bin/env python3
"""Verify published research files; the caller owns the product's Git workflow."""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from egbe_artifacts import artifact_path

REPORT_PATH = Path(artifact_path("egbe-docs/research/market/full-report.md"))
DEFAULT_COMMIT_MESSAGE = "research: update market report"


class ReportPersistenceError(RuntimeError):
    """A publication is missing or outside this research's public artifacts."""


@dataclass(frozen=True)
class PersistenceResult:
    commit_sha: str = ""
    committed: bool = False
    publication_mode: str = "local"


def _artifact_io():
    spec = importlib.util.spec_from_file_location("pmr_artifact_io", Path(__file__).with_name("research-artifact-io.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def persist_research_report(workspace: Path, *, commit_message: str = DEFAULT_COMMIT_MESSAGE,
                            extra_paths: Sequence[Path] = ()) -> PersistenceResult:
    workspace = workspace.resolve()
    lock = workspace / REPORT_PATH.parent / ".local" / "publication.lock"
    if not lock.resolve().is_relative_to(workspace):
        raise ReportPersistenceError("Research directory must stay inside the project")
    with _artifact_io().publication_lock(workspace / REPORT_PATH):
        return _persist_research_report(workspace, commit_message=commit_message, extra_paths=extra_paths)


def _persist_research_report(workspace: Path, *, commit_message: str = DEFAULT_COMMIT_MESSAGE,
                             extra_paths: Sequence[Path] = ()) -> PersistenceResult:
    # Preserve the receipt signature, not the old nested-repo workflow.
    # Publication never commits/pushes unrelated product work.
    workspace = workspace.resolve()
    public_root = (workspace / REPORT_PATH.parent).resolve()
    if not public_root.is_relative_to(workspace):
        raise ReportPersistenceError("Research directory must stay inside the project")
    for relative in (REPORT_PATH, *extra_paths):
        relative = Path(relative)
        target = (workspace / relative).resolve()
        if (relative.is_absolute() or any(part in ("..", ".local", "work") for part in relative.parts)
                or not target.is_relative_to(public_root)
                or any(part in (".local", "work") for part in target.relative_to(public_root).parts)):
            raise ReportPersistenceError(f"Not a public artifact of this research: {relative}")
        if not target.is_file():
            raise ReportPersistenceError(f"Research artifact does not exist: {relative}")
    return PersistenceResult()
