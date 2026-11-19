#!/usr/bin/env python3
"""Record an agent's bounded review of one cached research response ending."""

from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
REQUEST_SCHEMA_VERSION = 3
ACCEPTED_CLASSIFICATIONS = {"complete", "uncertain"}
CLASSIFICATIONS = (*sorted(ACCEPTED_CLASSIFICATIONS), "definitely_truncated")
SOURCES_HEADING = "\n### Sources\n"
MAX_RETRIES = 1
MIN_EVIDENCE_CHARS = 12
MAX_EVIDENCE_CHARS = 500
EVIDENCE_TAIL_CHARS = 2000


class CompletionReviewError(RuntimeError):
    """Raised when completion review cannot be bound to current runtime state."""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CompletionReviewError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise CompletionReviewError(f"{label} must be a JSON object: {path}")
    return value


def _write_object(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
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
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


def _research_answer(markdown: str) -> str:
    """Exclude the deterministic source appendix from the reviewed answer tail."""

    answer, separator, _ = markdown.rpartition(SOURCES_HEADING)
    return answer.rstrip() if separator and answer.strip() else markdown.rstrip()


def _validated_current_state(
    workspace: Path,
    section_id: str,
) -> tuple[Path, Path, Path, dict[str, Any], str]:
    if not re.fullmatch(r"[a-z0-9_]+", section_id):
        raise CompletionReviewError("section id must use lowercase snake_case")

    runtime_dir = workspace / _artifact_path('egbe-docs/research/market/work') / section_id
    request_path = runtime_dir / "request.json"
    query_path = runtime_dir / "query.md"
    prompt_path = runtime_dir / "system-prompt.md"
    result_path = runtime_dir / "result.md"
    state = _read_object(request_path, label="research request state")
    try:
        result = result_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CompletionReviewError(f"cannot read research result: {result_path}") from exc

    expected_result_path = (
        Path(_artifact_path("egbe-docs/research/market/work")) / section_id / "result.md"
    ).as_posix()
    if (
        state.get("schema_version") != REQUEST_SCHEMA_VERSION
        or state.get("status") != "completed"
        or not str(state.get("job_id") or "").strip()
        or state.get("result_path") != expected_result_path
        or state.get("query_sha256") != _file_sha256(query_path)
        or state.get("system_prompt_sha256") != _file_sha256(prompt_path)
        or state.get("result_sha256") != _file_sha256(result_path)
        or state.get("error") not in (None, "")
        or not result.strip()
    ):
        raise CompletionReviewError(
            "completion review requires a matching completed research result"
        )
    return runtime_dir, request_path, result_path, state, result


def _prior_retry_count(
    review_path: Path,
    *,
    query_sha256: str,
    system_prompt_sha256: str,
) -> int:
    try:
        review = _read_object(review_path, label="completion review")
    except CompletionReviewError:
        return 0
    if (
        review.get("schema_version") != SCHEMA_VERSION
        or review.get("query_sha256") != query_sha256
        or review.get("system_prompt_sha256") != system_prompt_sha256
    ):
        return 0
    value = review.get("retry_count")
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _archive_attempt(
    runtime_dir: Path,
    *,
    query_sha256: str,
    attempt: int,
    request_path: Path,
    result_path: Path,
    review: dict[str, Any],
) -> None:
    archive = (
        runtime_dir
        / "attempts"
        / query_sha256[:16]
        / f"definitely-truncated-{attempt}"
    )
    if archive.exists():
        raise CompletionReviewError(
            f"truncated research attempt archive already exists: {archive}"
        )
    archive.mkdir(parents=True)
    shutil.copy2(request_path, archive / "request.json")
    shutil.copy2(result_path, archive / "result.md")
    _write_object(archive / "completion-review.json", review)


def record_completion_review(
    workspace: Path,
    *,
    section_id: str,
    classification: str,
    evidence: str = "",
) -> dict[str, Any]:
    """Bind an agent decision to the current result and prepare one bounded retry."""

    if classification not in CLASSIFICATIONS:
        raise CompletionReviewError(
            f"classification must be one of: {', '.join(CLASSIFICATIONS)}"
        )
    workspace = workspace.resolve()
    runtime_dir, request_path, result_path, request, markdown = (
        _validated_current_state(workspace, section_id)
    )
    review_path = runtime_dir / "completion-review.json"
    retry_count = _prior_retry_count(
        review_path,
        query_sha256=str(request["query_sha256"]),
        system_prompt_sha256=str(request["system_prompt_sha256"]),
    )

    clean_evidence = _normalized_text(evidence)
    if classification == "definitely_truncated":
        if not MIN_EVIDENCE_CHARS <= len(clean_evidence) <= MAX_EVIDENCE_CHARS:
            raise CompletionReviewError(
                "definite truncation requires a 12-500 character answer-tail excerpt"
            )
        answer_tail = _normalized_text(_research_answer(markdown)[-EVIDENCE_TAIL_CHARS:])
        if clean_evidence not in answer_tail:
            raise CompletionReviewError(
                "truncation evidence must be an exact excerpt from the research answer tail"
            )
    elif clean_evidence:
        raise CompletionReviewError(
            "evidence is accepted only for definitely_truncated"
        )

    retry_exhausted = (
        classification == "definitely_truncated" and retry_count >= MAX_RETRIES
    )
    next_retry_count = (
        retry_count + 1
        if classification == "definitely_truncated" and not retry_exhausted
        else retry_count
    )
    review = {
        "schema_version": SCHEMA_VERSION,
        "section_id": section_id,
        "job_id": request["job_id"],
        "query_sha256": request["query_sha256"],
        "system_prompt_sha256": request["system_prompt_sha256"],
        "result_sha256": request["result_sha256"],
        "classification": classification,
        "evidence": clean_evidence or None,
        "retry_count": next_retry_count,
        "retry_exhausted": retry_exhausted,
    }

    if classification == "definitely_truncated":
        _archive_attempt(
            runtime_dir,
            query_sha256=str(request["query_sha256"]),
            attempt=retry_count + 1,
            request_path=request_path,
            result_path=result_path,
            review=review,
        )
        failed_request = dict(request)
        failed_request.update(
            {
                "status": "failed",
                "error": (
                    "research response was definitely truncated after one fresh retry"
                    if retry_exhausted
                    else "research response was definitely truncated; one fresh retry is required"
                ),
                "resume_safe": False,
                "next_submission_attempt": int(
                    request.get("submission_attempt") or 0
                )
                + 1,
                "truncation_retry_exhausted": retry_exhausted,
            }
        )
        _write_object(request_path, failed_request)

    _write_object(review_path, review)
    if retry_exhausted:
        raise CompletionReviewError(
            "research response was definitely truncated again; retry limit exhausted"
        )
    return review


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--section-id", required=True)
    parser.add_argument("--classification", choices=CLASSIFICATIONS, required=True)
    parser.add_argument("--evidence-file", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        evidence = (
            args.evidence_file.read_text(encoding="utf-8")
            if args.evidence_file is not None
            else ""
        )
        review = record_completion_review(
            args.workspace,
            section_id=args.section_id,
            classification=args.classification,
            evidence=evidence,
        )
    except (CompletionReviewError, OSError, UnicodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    if review["classification"] == "definitely_truncated":
        print("Definite truncation recorded; rerun the same section workflow once.")
    else:
        print(f"Research completion recorded as {review['classification']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
