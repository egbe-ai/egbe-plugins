#!/usr/bin/env python3
"""Render one founder research Preview and its compact chat summary."""

from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import argparse
from urllib.parse import urlsplit
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CONTEXT = Path(_artifact_path("egbe-docs/research/market/work/preview-context.json"))
DEFAULT_SYNTHESIS = Path(_artifact_path("egbe-docs/research/market/preview-synthesis.json"))
DEFAULT_FULL_REPORT = Path(_artifact_path("egbe-docs/research/market/full-report.md"))
DEFAULT_PREVIEW = Path(_artifact_path("egbe-docs/research/market/preview.md"))
DEFAULT_SUMMARY = Path(_artifact_path("egbe-docs/research/market/summary.md"))
DEFAULT_RECEIPT = Path(_artifact_path("egbe-docs/research/market/preview-render.json"))

PREVIEW_TITLE = "Market Research: Findings and Recommendations"
FULL_REPORT_TITLE = "Market Research Report"
MAX_PREVIEW_WORDS = 750
MAX_SUMMARY_VISIBLE_CHARS = 600
CONTEXT_STATUSES = frozenset(
    {"pending", "completed", "partial", "no_data", "could_not_complete", "not_selected"}
)
COVERAGE_LABEL_KEYS = frozenset({"partial", "no_data"})
LABEL_KEYS = frozenset(
    {
        "bottom_line",
        "what_matters",
        "what_this_means",
        "what_remains_open",
        "research_coverage",
        "researched",
        "not_included",
        "could_not_complete",
        "full_report",
        "recommended_direction",
        "biggest_open_question",
        "based_on",
    }
)
_STRUCTURAL_MARKDOWN = re.compile(
    r"(?:^\s{0,3}(?:#{1,6}|>|[-+*]|\d+[.)])\s)|"
    r"(?:!?\[[^\]]*\]\([^)]*\)|```|`|\*\*|__|~~|<[^>]+>)"
)
_CJK = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]"
)


class PreviewInputError(ValueError):
    pass


class _DuplicateJsonKeyError(ValueError):
    pass


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonKeyError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
        )
    except OSError as exc:
        raise PreviewInputError(f"cannot read {label} {path}: {exc}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PreviewInputError(f"{label} must be valid UTF-8 JSON") from exc
    except _DuplicateJsonKeyError as exc:
        raise PreviewInputError(f"{label} contains {exc}") from exc
    if not isinstance(value, dict):
        raise PreviewInputError(f"{label} must be a JSON object")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_context(value: dict[str, Any]) -> dict[str, str]:
    expected_fields = {
        "schema_version",
        "selection_id",
        "source_revision",
        "selected_option_ids",
        "sections",
    }
    if set(value) != expected_fields or value.get("schema_version") != 1:
        raise PreviewInputError(
            "Preview context must use the exact schema_version 1 contract"
        )
    for key in ("selection_id", "source_revision"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise PreviewInputError(
                f"Preview context {key} must be a non-empty string"
            )

    raw_sections = value.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise PreviewInputError("Preview context sections must be a non-empty list")
    outcomes: dict[str, str] = {}
    for raw in raw_sections:
        required = {"id", "label", "status"}
        optional = {"coverage", "closed_by_caller"}
        if not isinstance(raw, dict) or not required <= set(raw) <= required | optional:
            raise PreviewInputError(
                "Preview context section entries require id, label, and status; "
                "only coverage and closed_by_caller are optional"
            )
        option_id = raw.get("id")
        label = raw.get("label")
        status = raw.get("status")
        if not isinstance(option_id, str) or not option_id.strip():
            raise PreviewInputError("Preview context contains an invalid section id")
        _plain_text(label, field=f"sections.{option_id}.label", maximum=120)
        if option_id in outcomes:
            raise PreviewInputError(f"Preview context repeats section {option_id!r}")
        if status not in CONTEXT_STATUSES:
            raise PreviewInputError(
                f"Preview context has invalid status for {option_id!r}"
            )
        if "closed_by_caller" in raw and (
            raw["closed_by_caller"] is not True or status != "could_not_complete"
        ):
            raise PreviewInputError("Caller closure requires could_not_complete status")
        if "coverage" in raw and (
            not isinstance(raw["coverage"], dict)
            or status not in {"completed", "partial", "no_data"}
            or raw["coverage"].get("status") != {"completed": "complete"}.get(status, status)
        ):
            raise PreviewInputError("Preview context coverage must match section status")
        if status == "pending":
            raise PreviewInputError(
                "Preview cannot render while selected research is still pending"
            )
        outcomes[option_id] = status

    expected_selected = [
        option_id for option_id, status in outcomes.items() if status != "not_selected"
    ]
    if value.get("selected_option_ids") != expected_selected or not expected_selected:
        raise PreviewInputError(
            "Preview context selected IDs do not match section outcomes"
        )
    return outcomes


def _plain_text(value: Any, *, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise PreviewInputError(f"{field} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise PreviewInputError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise PreviewInputError(f"{field} must be at most {maximum} characters")
    if _STRUCTURAL_MARKDOWN.search(normalized):
        raise PreviewInputError(
            f"{field} must be plain text without Markdown structure"
        )
    return normalized


def _source_ids(
    value: Any,
    *,
    field: str,
    evidence_ids: set[str],
    allow_empty: bool,
) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PreviewInputError(f"{field} must be a list of section IDs")
    if len(value) != len(set(value)):
        raise PreviewInputError(f"{field} must not repeat section IDs")
    if not value and not allow_empty:
        raise PreviewInputError(f"{field} must reference usable research evidence")
    unsupported = [item for item in value if item not in evidence_ids]
    if unsupported:
        raise PreviewInputError(
            f"{field} references research without usable evidence: "
            + ", ".join(unsupported)
        )
    return list(value)


def _validate_synthesis(
    value: dict[str, Any],
    *,
    known_ids: list[str],
    evidence_ids: set[str],
    coverage_statuses: set[str],
) -> dict[str, Any]:
    expected_fields = {
        "schema_version",
        "labels",
        "section_labels",
        "bottom_line",
        "findings",
        "product_implications",
        "open_questions",
    }
    if set(value) != expected_fields or value.get("schema_version") != 1:
        raise PreviewInputError(
            "Preview synthesis must use the exact schema_version 1 contract"
        )

    raw_labels = value.get("labels")
    required_labels = LABEL_KEYS | (coverage_statuses & COVERAGE_LABEL_KEYS)
    if (
        not isinstance(raw_labels, dict)
        or not required_labels <= set(raw_labels) <= LABEL_KEYS | COVERAGE_LABEL_KEYS
    ):
        raise PreviewInputError(
            "Preview synthesis labels do not match the required contract"
        )
    labels = {
        key: _plain_text(raw_labels[key], field=f"labels.{key}", maximum=80)
        for key in sorted(raw_labels)
    }
    if len(set(labels.values())) != len(labels):
        raise PreviewInputError("Preview synthesis labels must be distinct")

    raw_section_labels = value.get("section_labels")
    if not isinstance(raw_section_labels, dict) or set(raw_section_labels) != set(
        known_ids
    ):
        raise PreviewInputError(
            "Preview synthesis section_labels must contain every runtime section ID"
        )
    section_labels = {
        option_id: _plain_text(
            raw_section_labels[option_id],
            field=f"section_labels.{option_id}",
            maximum=120,
        )
        for option_id in known_ids
    }
    if len(set(section_labels.values())) != len(section_labels):
        raise PreviewInputError("Preview synthesis section_labels must be distinct")

    raw_bottom = value.get("bottom_line")
    bottom_fields = {
        "summary",
        "detail",
        "source_section_ids",
        "confidence_note",
    }
    if not isinstance(raw_bottom, dict) or set(raw_bottom) != bottom_fields:
        raise PreviewInputError(
            "Preview synthesis bottom_line does not match the required contract"
        )
    bottom_line = {
        "summary": _plain_text(
            raw_bottom.get("summary"),
            field="bottom_line.summary",
            maximum=240,
        ),
        "detail": _plain_text(
            raw_bottom.get("detail"),
            field="bottom_line.detail",
            maximum=900,
        ),
        "source_section_ids": _source_ids(
            raw_bottom.get("source_section_ids"),
            field="bottom_line.source_section_ids",
            evidence_ids=evidence_ids,
            allow_empty=not evidence_ids,
        ),
        "confidence_note": _plain_text(
            raw_bottom.get("confidence_note"),
            field="bottom_line.confidence_note",
            maximum=240,
        ),
    }

    raw_findings = value.get("findings")
    if not isinstance(raw_findings, list) or len(raw_findings) > 5:
        raise PreviewInputError(
            "Preview synthesis findings must contain at most five items"
        )
    finding_fields = {
        "title",
        "finding",
        "why_it_matters",
        "source_section_ids",
        "limitation",
    }
    findings: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_findings):
        if not isinstance(raw, dict) or set(raw) != finding_fields:
            raise PreviewInputError(
                f"findings[{index}] does not match the required contract"
            )
        findings.append(
            {
                "title": _plain_text(
                    raw.get("title"),
                    field=f"findings[{index}].title",
                    maximum=100,
                ),
                "finding": _plain_text(
                    raw.get("finding"),
                    field=f"findings[{index}].finding",
                    maximum=500,
                ),
                "why_it_matters": _plain_text(
                    raw.get("why_it_matters"),
                    field=f"findings[{index}].why_it_matters",
                    maximum=400,
                ),
                "source_section_ids": _source_ids(
                    raw.get("source_section_ids"),
                    field=f"findings[{index}].source_section_ids",
                    evidence_ids=evidence_ids,
                    allow_empty=False,
                ),
                "limitation": _plain_text(
                    raw.get("limitation"),
                    field=f"findings[{index}].limitation",
                    maximum=240,
                ),
            }
        )

    raw_implications = value.get("product_implications")
    if not isinstance(raw_implications, list) or len(raw_implications) > 4:
        raise PreviewInputError(
            "Preview synthesis product_implications must contain at most four items"
        )
    implication_fields = {
        "title",
        "direction",
        "rationale",
        "source_section_ids",
        "reconsider_if",
    }
    implications: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_implications):
        if not isinstance(raw, dict) or set(raw) != implication_fields:
            raise PreviewInputError(
                f"product_implications[{index}] does not match the required contract"
            )
        implications.append(
            {
                "title": _plain_text(
                    raw.get("title"),
                    field=f"product_implications[{index}].title",
                    maximum=100,
                ),
                "direction": _plain_text(
                    raw.get("direction"),
                    field=f"product_implications[{index}].direction",
                    maximum=360,
                ),
                "rationale": _plain_text(
                    raw.get("rationale"),
                    field=f"product_implications[{index}].rationale",
                    maximum=500,
                ),
                "source_section_ids": _source_ids(
                    raw.get("source_section_ids"),
                    field=f"product_implications[{index}].source_section_ids",
                    evidence_ids=evidence_ids,
                    allow_empty=False,
                ),
                "reconsider_if": _plain_text(
                    raw.get("reconsider_if"),
                    field=f"product_implications[{index}].reconsider_if",
                    maximum=300,
                ),
            }
        )

    raw_questions = value.get("open_questions")
    if not isinstance(raw_questions, list) or not 1 <= len(raw_questions) <= 4:
        raise PreviewInputError(
            "Preview synthesis open_questions must contain 1-4 items"
        )
    questions: list[dict[str, str]] = []
    for index, raw in enumerate(raw_questions):
        if not isinstance(raw, dict) or set(raw) != {"question", "why_it_matters"}:
            raise PreviewInputError(
                f"open_questions[{index}] does not match the required contract"
            )
        questions.append(
            {
                "question": _plain_text(
                    raw.get("question"),
                    field=f"open_questions[{index}].question",
                    maximum=300,
                ),
                "why_it_matters": _plain_text(
                    raw.get("why_it_matters"),
                    field=f"open_questions[{index}].why_it_matters",
                    maximum=300,
                ),
            }
        )

    if not evidence_ids and (findings or implications):
        raise PreviewInputError(
            "Research with no usable evidence cannot produce findings or "
            "product implications"
        )
    return {
        "schema_version": 1,
        "labels": labels,
        "section_labels": section_labels,
        "bottom_line": bottom_line,
        "findings": findings,
        "product_implications": implications,
        "open_questions": questions,
    }


def _evidence_line(
    synthesis: dict[str, Any],
    source_ids: Iterable[str],
    trailing_note: str,
) -> str:
    rendered_sources = ", ".join(
        synthesis["section_labels"][item] for item in source_ids
    )
    return f"_{synthesis['labels']['based_on']}: {rendered_sources}. {trailing_note}_"


def _render_preview(
    synthesis: dict[str, Any],
    outcomes: dict[str, str],
    *,
    full_report_url: str,
) -> str:
    labels = synthesis["labels"]
    bottom = synthesis["bottom_line"]
    bottom_evidence = (
        _evidence_line(
            synthesis,
            bottom["source_section_ids"],
            bottom["confidence_note"],
        )
        if bottom["source_section_ids"]
        else f"_{bottom['confidence_note']}_"
    )
    blocks = [
        f"# {PREVIEW_TITLE}",
        f"## {labels['bottom_line']}\n\n**{bottom['summary']}**\n\n"
        f"{bottom['detail']}\n\n{bottom_evidence}",
    ]

    if synthesis["findings"]:
        finding_blocks = [
            f"### {item['title']}\n\n{item['finding']}\n\n"
            f"{item['why_it_matters']}\n\n"
            f"{_evidence_line(synthesis, item['source_section_ids'], item['limitation'])}"
            for item in synthesis["findings"]
        ]
        blocks.append(
            f"## {labels['what_matters']}\n\n" + "\n\n".join(finding_blocks)
        )

    if synthesis["product_implications"]:
        implication_blocks = [
            f"### {item['title']}\n\n{item['direction']}\n\n"
            f"{item['rationale']}\n\n"
            f"{_evidence_line(synthesis, item['source_section_ids'], item['reconsider_if'])}"
            for item in synthesis["product_implications"]
        ]
        blocks.append(
            f"## {labels['what_this_means']}\n\n"
            + "\n\n".join(implication_blocks)
        )

    question_bullets = "\n".join(
        f"- **{item['question']}** {item['why_it_matters']}"
        for item in synthesis["open_questions"]
    )
    blocks.append(f"## {labels['what_remains_open']}\n\n{question_bullets}")

    coverage_lines = []
    for status, label_key in (
        ("completed", "researched"),
        ("partial", "partial"),
        ("no_data", "no_data"),
        ("not_selected", "not_included"),
        ("could_not_complete", "could_not_complete"),
    ):
        values = [
            synthesis["section_labels"][option_id]
            for option_id, outcome in outcomes.items()
            if outcome == status
        ]
        if values:
            coverage_lines.append(f"- **{labels[label_key]}:** {', '.join(values)}")
    coverage_lines.append(f"[{labels['full_report']}]({full_report_url})")
    blocks.append(
        f"## {labels['research_coverage']}\n\n" + "\n".join(coverage_lines)
    )
    return "\n\n".join(blocks) + "\n"


def _render_summary(synthesis: dict[str, Any]) -> str:
    labels = synthesis["labels"]
    parts = [
        f"**{labels['bottom_line']}**\n\n{synthesis['bottom_line']['summary']}"
    ]
    implications = synthesis["product_implications"][:2]
    if implications:
        bullets = "\n".join(f"- {item['direction']}" for item in implications)
        parts.append(f"**{labels['recommended_direction']}**\n\n{bullets}")
    parts.append(
        f"**{labels['biggest_open_question']}**\n\n"
        f"{synthesis['open_questions'][0]['question']}"
    )
    return "\n\n".join(parts) + "\n"


def _word_count(value: str) -> int:
    cjk = _CJK.findall(value)
    without_cjk = _CJK.sub(" ", value)
    words = re.findall(r"\b[\w’'-]+\b", without_cjk, flags=re.UNICODE)
    return len(words) + len(cjk)


def _visible_markdown_chars(value: str) -> int:
    visible = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", value)
    visible = re.sub(r"(?m)^\s{0,3}(?:#{1,6}|[-+*>])\s*", "", visible)
    visible = visible.replace("**", "").replace("__", "").replace("`", "")
    visible = re.sub(r"\s+", " ", visible).strip()
    return len(visible)


def build_preview_documents(
    context: dict[str, Any],
    synthesis: dict[str, Any],
    *,
    full_report_url: str,
) -> tuple[str, str]:
    outcomes = _validate_context(context)
    known_ids = list(outcomes)
    evidence_ids = {
        section["id"] for section in context["sections"]
        if _has_usable_evidence(section)
    }
    normalized = _validate_synthesis(
        synthesis,
        known_ids=known_ids,
        evidence_ids=evidence_ids,
        coverage_statuses=set(outcomes.values()),
    )
    preview = _render_preview(
        normalized,
        outcomes,
        full_report_url=full_report_url,
    )
    summary = _render_summary(normalized)
    if _word_count(preview) > MAX_PREVIEW_WORDS:
        raise PreviewInputError(
            f"Preview must be at most {MAX_PREVIEW_WORDS} words or CJK reading units"
        )
    if _visible_markdown_chars(summary) > MAX_SUMMARY_VISIBLE_CHARS:
        raise PreviewInputError(
            "Founder chat summary must be at most "
            f"{MAX_SUMMARY_VISIBLE_CHARS} visible characters"
        )
    return preview, summary


def _has_usable_evidence(section: dict[str, Any]) -> bool:
    if section["status"] == "completed":
        return True
    if section["status"] != "partial":
        return False
    # A failed source plus an empty successful source is still a partial run,
    # but neither an empty nor an unanalyzed collection can support findings.
    coverage = section.get("coverage", {})
    collected = coverage.get("collected_count")
    analyzed = coverage.get("analyzed_count")
    return type(collected) is int and type(analyzed) is int and 0 < analyzed <= collected


def _atomic_write(path: Path, value: str, *, mode: int = 0o644) -> None:
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
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _ensure_full_report(path: Path) -> None:
    if path.exists():
        return
    _atomic_write(path, f"# {FULL_REPORT_TITLE}\n")


def write_preview_documents(
    *,
    context_path: Path,
    synthesis_path: Path,
    full_report_path: Path,
    preview_path: Path,
    summary_path: Path,
    receipt_path: Path,
    local_report_link: str = "full-report.md",
) -> tuple[str, str, dict[str, Any]]:
    context = _read_json_object(context_path, label="Preview context")
    synthesis = _read_json_object(synthesis_path, label="Preview synthesis")
    parsed = urlsplit(local_report_link)
    if (not local_report_link or any(c.isspace() or c in "()\\<>" for c in local_report_link)
        or parsed.username or parsed.password or local_report_link.startswith(("/", "."))
        or ".." in parsed.path.split("/")
        or (parsed.scheme and (parsed.scheme not in {"http", "https"} or not parsed.netloc))
        or (not parsed.scheme and parsed.netloc)):
        raise PreviewInputError("Use a safe relative report link or HTTP(S) URL")
    full_report_url = local_report_link
    _ensure_full_report(full_report_path)
    preview, summary = build_preview_documents(
        context,
        synthesis,
        full_report_url=full_report_url,
    )
    _atomic_write(preview_path, preview)
    _atomic_write(summary_path, summary)
    receipt = {
        "schema_version": 1,
        "context_sha256": _file_sha256(context_path),
        "synthesis_sha256": _file_sha256(synthesis_path),
        "full_report_sha256": _file_sha256(full_report_path),
        "preview_sha256": _file_sha256(preview_path),
        "summary_sha256": _file_sha256(summary_path),
        "full_report_url": full_report_url,
        "publication_mode": "local",
    }
    _atomic_write(
        receipt_path,
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return preview, summary, receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, default=DEFAULT_CONTEXT)
    parser.add_argument("--input", type=Path, default=DEFAULT_SYNTHESIS)
    parser.add_argument("--full-report", type=Path, default=DEFAULT_FULL_REPORT)
    parser.add_argument("--preview", type=Path, default=DEFAULT_PREVIEW)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--local-report-link", default="full-report.md", help="Report link (default: full-report.md); no instance required")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        write_preview_documents(
            context_path=args.context,
            synthesis_path=args.input,
            full_report_path=args.full_report,
            preview_path=args.preview,
            summary_path=args.summary,
            receipt_path=args.receipt,
            local_report_link=args.local_report_link,
        )
    except (OSError, PreviewInputError, RuntimeError, UnicodeError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
