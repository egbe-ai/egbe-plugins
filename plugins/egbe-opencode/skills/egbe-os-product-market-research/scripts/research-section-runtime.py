#!/usr/bin/env python3
"""Persist, resume, and materialize one OS Research section."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, workspace: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"runtime path must be inside workspace: {path}") from exc


def _read_state(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_state(path: Path, payload: dict[str, Any]) -> None:
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
            json.dump(payload, handle, indent=2, sort_keys=True)
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


def _state_payload(
    *,
    schema_version: int,
    status: str,
    query_sha256: str,
    system_prompt_sha256: str,
    result_path: str,
    job_id: str = "",
    submission_attempt: int = 0,
    next_submission_attempt: int | None = None,
    result_sha256: str = "",
    execution_revision: str = "",
    error: str = "",
    resume_safe: bool | None = None,
    input_provenance_sha256: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "status": status,
        "job_id": job_id or None,
        "submission_attempt": submission_attempt,
        "query_sha256": query_sha256,
        "system_prompt_sha256": system_prompt_sha256,
        "result_path": result_path,
        "result_sha256": result_sha256 or None,
        "execution_revision": execution_revision or None,
        "error": error or None,
    }
    if next_submission_attempt is not None:
        payload["next_submission_attempt"] = next_submission_attempt
    if resume_safe is not None:
        payload["resume_safe"] = resume_safe
    if input_provenance_sha256:
        payload["input_provenance_sha256"] = input_provenance_sha256
    return payload


def _matches_inputs(
    state: dict[str, Any] | None,
    *,
    schema_version: int,
    query_sha256: str,
    system_prompt_sha256: str,
    result_path: str,
) -> bool:
    return bool(
        state
        and state.get("schema_version") == schema_version
        and state.get("query_sha256") == query_sha256
        and state.get("system_prompt_sha256") == system_prompt_sha256
        and state.get("result_path") == result_path
    )


def _completed_result_available(
    state: dict[str, Any] | None,
    *,
    result_file: Path,
    schema_version: int,
    query_sha256: str,
    system_prompt_sha256: str,
    result_path: str,
) -> bool:
    if not _matches_inputs(
        state,
        schema_version=schema_version,
        query_sha256=query_sha256,
        system_prompt_sha256=system_prompt_sha256,
        result_path=result_path,
    ) or state.get("status") != "completed":
        return False
    if not str(state.get("job_id") or "").strip():
        return False
    expected_hash = str(state.get("result_sha256") or "")
    try:
        return bool(expected_hash) and _file_sha256(result_file) == expected_hash
    except OSError:
        return False


def require_matching_inputs(request_file: Path, *, query: str, system_prompt: str,
                            schema_version: int, result_path: str,
                            input_provenance_sha256: str = "") -> None:
    """Preserve prior requests/evidence rather than silently replacing paid work."""
    state = _read_state(request_file)
    if request_file.exists() and state is None:
        raise ValueError("research request state is unreadable; preserve and inspect it before retrying")
    if state and not _matches_inputs(state, schema_version=schema_version,
                                     query_sha256=_sha256(query), system_prompt_sha256=_sha256(system_prompt),
                                     result_path=result_path):
        raise ValueError("research inputs changed; existing evidence is preserved. Use a new research ID for a new assignment; do not automatically repeat paid work")
    if state and input_provenance_sha256 and state.get("input_provenance_sha256") != input_provenance_sha256:
        raise ValueError("Saved research input provenance is missing or damaged; do not start new paid work")


def _attempt_for_state(state: dict[str, Any] | None, *, matching: bool) -> int:
    if not matching or state is None:
        return 0
    if state.get("status") == "failed" and state.get("resume_safe") is not True:
        value = state.get("next_submission_attempt")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        current = state.get("submission_attempt")
        return (
            current + 1
            if isinstance(current, int)
            and not isinstance(current, bool)
            and current >= 0
            else 1
        )
    current = state.get("submission_attempt")
    return (
        current
        if isinstance(current, int)
        and not isinstance(current, bool)
        and current >= 0
        else 0
    )


def run_resumable_section(
    workspace: Path,
    *,
    query: str,
    system_prompt: str,
    section_heading: str,
    request_file: Path,
    result_file: Path,
    report_file: Path,
    schema_version: int,
    execute_research: Callable[..., Any],
    materialize: Callable[[Path, str, str], Any],
    input_provenance_sha256: str = "",
) -> dict[str, Any]:
    """Run one section or reuse its matching completed OS Research result."""

    workspace = workspace.resolve()
    relative_result = _relative(result_file, workspace)
    require_matching_inputs(request_file, query=query, system_prompt=system_prompt,
                            schema_version=schema_version, result_path=relative_result,
                            input_provenance_sha256=input_provenance_sha256)
    query_hash = _sha256(query)
    prompt_hash = _sha256(system_prompt)
    state = _read_state(request_file)
    matching = _matches_inputs(
        state,
        schema_version=schema_version,
        query_sha256=query_hash,
        system_prompt_sha256=prompt_hash,
        result_path=relative_result,
    )
    reused = _completed_result_available(
        state,
        result_file=result_file,
        schema_version=schema_version,
        query_sha256=query_hash,
        system_prompt_sha256=prompt_hash,
        result_path=relative_result,
    )

    if (
        not reused
        and matching
        and (state or {}).get("status") == "failed"
        and (state or {}).get("truncation_retry_exhausted") is True
    ):
        raise ValueError(
            "research response truncation retry limit is exhausted for these inputs"
        )

    if not reused:
        resume_job_id = ""
        if matching and (
            state.get("status") == "running"
            or (
                state.get("status") == "failed"
                and state.get("resume_safe") is True
            )
        ):
            resume_job_id = str(state.get("job_id") or "").strip()

        submission_attempt = _attempt_for_state(state, matching=matching)
        job_id = resume_job_id

        def mark_running(value: str) -> None:
            nonlocal job_id
            job_id = value
            _write_state(
                request_file,
                _state_payload(
                    schema_version=schema_version,
                    status="running",
                    query_sha256=query_hash,
                    system_prompt_sha256=prompt_hash,
                    result_path=relative_result,
                    job_id=value,
                    submission_attempt=submission_attempt,
                    input_provenance_sha256=input_provenance_sha256,
                ),
            )

        _write_state(
            request_file,
            _state_payload(
                schema_version=schema_version,
                status="running" if resume_job_id else "submitting",
                query_sha256=query_hash,
                system_prompt_sha256=prompt_hash,
                result_path=relative_result,
                job_id=resume_job_id,
                submission_attempt=submission_attempt,
                input_provenance_sha256=input_provenance_sha256,
            ),
        )
        try:
            result = execute_research(
                output=result_file,
                on_submitted=mark_running,
                resume_job_id=resume_job_id,
                submission_attempt=submission_attempt,
            )
            job_id = str(result.job_id or job_id).strip()
            if not job_id:
                raise ValueError("OS Research returned no job id")
            result_hash = _file_sha256(result_file)
            execution_revision = str(
                getattr(result, "model_roles_revision", "") or ""
            ).strip()
        except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
            declared_resume_safe = getattr(exc, "resume_safe", None)
            # An uncertain POST may have been accepted without returning its ID.
            # Preserve its attempt/key so a repeated POST recovers that same job.
            resume_safe = bool(job_id) if declared_resume_safe is None else bool(declared_resume_safe)
            _write_state(
                request_file,
                _state_payload(
                    schema_version=schema_version,
                    status="failed",
                    query_sha256=query_hash,
                    system_prompt_sha256=prompt_hash,
                    result_path=relative_result,
                    job_id=job_id,
                    submission_attempt=submission_attempt,
                    next_submission_attempt=(
                        submission_attempt if resume_safe else submission_attempt + 1
                    ),
                    error=str(exc),
                    resume_safe=resume_safe,
                    input_provenance_sha256=input_provenance_sha256,
                ),
            )
            raise
        _write_state(
            request_file,
            _state_payload(
                schema_version=schema_version,
                status="completed",
                query_sha256=query_hash,
                system_prompt_sha256=prompt_hash,
                result_path=relative_result,
                job_id=job_id,
                submission_attempt=submission_attempt,
                result_sha256=result_hash,
                execution_revision=execution_revision,
                input_provenance_sha256=input_provenance_sha256,
            ),
        )
        state = _read_state(request_file)

    content = result_file.read_text(encoding="utf-8")
    materialize(report_file, section_heading, content)
    return {
        "job_id": str((state or {}).get("job_id") or ""),
        "result_path": relative_result,
        "report_path": _relative(report_file, workspace),
        "reused": reused,
    }
