#!/usr/bin/env python3
"""Create or replace one canonical H2 in the market research report."""

from __future__ import annotations

import argparse
import importlib.util
import os
import tempfile
from pathlib import Path


REPORT_TITLE = "# Market Research Report"


def _write_atomic(path: Path, content: str) -> None:
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
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _canonical_content(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("section content must not be empty")
    return normalized


def _validate_heading(heading: str) -> str:
    value = heading.strip()
    if not value or "\n" in value or "\r" in value or value.startswith("#"):
        raise ValueError("heading must be a non-empty H2 title without Markdown markers")
    return value


def _h2_offsets(text: str) -> list[tuple[str, int]]:
    """Return exact column-zero H2 headings outside fenced code blocks."""

    offsets: list[tuple[str, int]] = []
    offset = 0
    fence_char: str | None = None
    fence_size = 0

    for line in text.splitlines(keepends=True):
        raw = line.rstrip("\r\n")
        stripped = raw.lstrip(" ")
        indent = len(raw) - len(stripped)
        if indent <= 3 and stripped.startswith(("```", "~~~")):
            marker = stripped.split(maxsplit=1)[0]
            char = marker[0]
            size = len(marker) - len(marker.lstrip(char))
            if size >= 3:
                if fence_char is None:
                    fence_char, fence_size = char, size
                elif char == fence_char and size >= fence_size:
                    fence_char, fence_size = None, 0
        elif fence_char is None and raw.startswith("## ") and raw[3:].strip():
            offsets.append((raw[3:].strip(), offset))
        offset += len(line)

    return offsets


def upsert_markdown_section(report: Path, heading: str, content: str) -> str:
    """Upsert one H2 and return the resulting report text."""

    spec = importlib.util.spec_from_file_location("pmr_artifact_io", Path(__file__).with_name("research-artifact-io.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with module.publication_lock(report):
        return _upsert_markdown_section(report, heading, content)


def _upsert_markdown_section(report: Path, heading: str, content: str) -> str:

    title = _validate_heading(heading)
    body = _canonical_content(content)

    if report.exists():
        text = report.read_text(encoding="utf-8")
        if text != REPORT_TITLE and not text.startswith(f"{REPORT_TITLE}\n"):
            raise ValueError(f"existing report must start with exact H1 `{REPORT_TITLE}`")
    else:
        text = REPORT_TITLE

    headings = _h2_offsets(text)
    matches = [(index, offset) for index, (name, offset) in enumerate(headings) if name == title]
    if len(matches) > 1:
        raise ValueError(f"report contains duplicate H2 `## {title}`")

    if matches:
        index, start = matches[0]
        end = headings[index + 1][1] if index + 1 < len(headings) else len(text)
        suffix = text[end:]
        block = f"## {title}\n\n{body}\n"
        if suffix:
            block += "\n"
        updated = text[:start] + block + suffix
    else:
        if text.endswith("\n\n"):
            prefix = text
        elif text.endswith("\n"):
            prefix = text + "\n"
        else:
            prefix = text + "\n\n"
        updated = f"{prefix}## {title}\n\n{body}\n"

    _write_atomic(report, updated)
    return updated


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--heading", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--content")
    source.add_argument("--content-file", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    content = (
        args.content_file.read_text(encoding="utf-8")
        if args.content_file is not None
        else args.content
    )
    try:
        upsert_markdown_section(args.report, args.heading, content)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
