#!/usr/bin/env python3
"""Run one asynchronous OS Research job and atomically write Markdown."""

from __future__ import annotations

import runpy as _egbe_runpy
from pathlib import Path as _EgbePath
_egbe_adapter = _EgbePath(__file__).with_name("connection_identity.py")
_connection_headers = _egbe_runpy.run_path(str(_egbe_adapter))["connection_headers"] if _egbe_adapter.is_file() else lambda _url: {}

import argparse
import hashlib
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


DEFAULT_OS_URL = "https://os.hz.egbe.dev"
TERMINAL_FAILURES = {"failed", "cancelled", "canceled", "error"}


class ResearchRequestError(RuntimeError):
    def __init__(self, message: str, *, resume_safe: bool = True) -> None:
        super().__init__(message)
        self.resume_safe = resume_safe


@dataclass(frozen=True)
class ResearchResult:
    job_id: str
    markdown: str
    model_roles_revision: str = ""


def _envelope_data(payload: dict[str, Any], *, operation: str) -> dict[str, Any]:
    if payload.get("ok") is False:
        message = str(payload.get("message") or f"{operation} failed").strip()
        raise ResearchRequestError(message)
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ResearchRequestError(f"{operation} returned no data object")
    return data


def _request_json(
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        for _name, _value in _connection_headers(request.full_url).items():
            request.add_unredirected_header(_name, _value)
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        try:
            decoded = json.loads(detail)
            detail = str(decoded.get("message") or detail)
        except (AttributeError, json.JSONDecodeError):
            pass
        resume_safe = exc.code in {
            401,
            402,
            403,
            408,
            409,
            423,
            425,
            429,
        } or 500 <= exc.code < 600
        raise ResearchRequestError(
            f"OS request failed with HTTP {exc.code}: {detail}",
            resume_safe=resume_safe,
        ) from exc
    except (OSError, TimeoutError) as exc:
        raise ResearchRequestError(f"OS request failed: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise ResearchRequestError("OS returned a non-UTF-8 response") from exc
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ResearchRequestError("OS returned invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise ResearchRequestError("OS returned a non-object JSON response")
    return decoded


def _strip_outer_fence(value: str) -> str:
    text = value.strip()
    match = re.fullmatch(
        r"```(?:markdown|md)?\s*\n(.*)\n```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else text


def _demote_document_headings(value: str) -> str:
    lines: list[str] = []
    for line in value.splitlines():
        match = re.match(r"^(#{1,2})\s+(.+)$", line)
        lines.append(f"### {match.group(2)}" if match else line)
    return "\n".join(lines).strip()


def normalize_markdown(value: str) -> str:
    markdown = _demote_document_headings(_strip_outer_fence(value))
    if not markdown:
        raise ResearchRequestError("OS research completed without Markdown")
    if not re.search(r"https?://[^\s)>]+", markdown):
        raise ResearchRequestError("OS research Markdown contains no usable source URL")
    return f"{markdown.rstrip()}\n"


def idempotency_key(query: str, instructions: str, submission_attempt: int) -> str:
    if submission_attempt < 0:
        raise ResearchRequestError("submission attempt must not be negative")
    digest = hashlib.sha256(
        f"{submission_attempt}\0{instructions.strip()}\0{query.strip()}".encode("utf-8")
    ).hexdigest()
    return f"pmr:{digest}"


def run_async_research(
    *,
    query: str,
    system_prompt: str,
    base_url: str,
    api_key: str,
    depth: str = "deep",
    submission_attempt: int = 0,
    poll_interval_seconds: float = 30.0,
    timeout_seconds: float = 1800.0,
    request_json: Callable[..., dict[str, Any]] = _request_json,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    on_submitted: Callable[[str], None] | None = None,
    resume_job_id: str = "",
) -> ResearchResult:
    clean_query = query.strip()
    clean_instructions = system_prompt.strip()
    clean_api_key = api_key.strip()
    root = base_url.strip().rstrip("/")
    if not clean_query:
        raise ResearchRequestError("research query must not be empty")
    if not clean_instructions:
        raise ResearchRequestError("research instructions must not be empty")
    if not clean_api_key:
        raise ResearchRequestError("OS_API_KEY is required")
    if not root.startswith(("http://", "https://")):
        raise ResearchRequestError("OS_URL must be an HTTP or HTTPS URL")
    if depth not in {"standard", "deep"}:
        raise ResearchRequestError("research depth must be standard or deep")
    if timeout_seconds <= 0:
        raise ResearchRequestError("timeout must be greater than zero")

    job_id = resume_job_id.strip()
    if not job_id:
        submission = request_json(
            "POST",
            f"{root}/research",
            clean_api_key,
            {
                "query": clean_query,
                "instructions": clean_instructions,
                "depth": depth,
                "idempotency_key": idempotency_key(
                    clean_query,
                    clean_instructions,
                    submission_attempt,
                ),
            },
        )
        submission_data = _envelope_data(submission, operation="research submission")
        job_id = str(submission_data.get("id") or "").strip()
        if not job_id:
            raise ResearchRequestError("research submission returned no job id")
        if on_submitted is not None:
            on_submitted(job_id)

    deadline = monotonic() + timeout_seconds
    while True:
        if monotonic() >= deadline:
            raise ResearchRequestError(f"research job {job_id} timed out")
        response = request_json("GET", f"{root}/research/{job_id}", clean_api_key)
        data = _envelope_data(response, operation="research polling")
        status = str(data.get("status") or "").strip().lower()
        if status == "completed":
            result = data.get("result")
            if not isinstance(result, dict):
                raise ResearchRequestError(
                    "OS research completed without a result object",
                    resume_safe=False,
                )
            raw_markdown = str(result.get("markdown") or "")
            expected_hash = str(result.get("sha256") or "").strip()
            if expected_hash and hashlib.sha256(raw_markdown.encode("utf-8")).hexdigest() != expected_hash:
                raise ResearchRequestError(
                    "OS research result hash does not match its Markdown",
                    resume_safe=False,
                )
            try:
                markdown = normalize_markdown(raw_markdown)
            except ResearchRequestError as exc:
                raise ResearchRequestError(str(exc), resume_safe=False) from exc
            return ResearchResult(
                job_id=job_id,
                markdown=markdown,
                model_roles_revision=str(data.get("modelRolesRevision") or ""),
            )
        if status in TERMINAL_FAILURES:
            error = data.get("error")
            if isinstance(error, dict):
                code = str(error.get("code") or "research_failed")
                message = str(error.get("message") or code)
            else:
                code = "research_failed"
                message = str(error or "research engine failed")
            raise ResearchRequestError(
                f"research job {job_id} failed ({code}): {message}",
                resume_safe=False,
            )
        sleep(max(poll_interval_seconds, 0.0))


def write_atomic(path: Path, content: str) -> None:
    normalized = content.strip()
    if not normalized:
        raise ResearchRequestError("research output must not be empty")
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
            handle.write(f"{normalized}\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def run_research_to_file(*, output: Path, **kwargs: Any) -> ResearchResult:
    result = run_async_research(**kwargs)
    write_atomic(output, result.markdown)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-file", type=Path, required=True)
    parser.add_argument("--system-prompt-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--depth", choices=("standard", "deep"), default="deep")
    parser.add_argument("--submission-attempt", type=int, default=0)
    parser.add_argument("--poll-interval-seconds", type=float, default=30.0)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        run_research_to_file(
            output=args.output,
            query=args.query_file.read_text(encoding="utf-8"),
            system_prompt=args.system_prompt_file.read_text(encoding="utf-8"),
            base_url=os.environ.get("OS_URL") or DEFAULT_OS_URL,
            api_key=os.environ.get("OS_API_KEY", ""),
            depth=args.depth,
            submission_attempt=args.submission_attempt,
            poll_interval_seconds=args.poll_interval_seconds,
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, ResearchRequestError, UnicodeError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
