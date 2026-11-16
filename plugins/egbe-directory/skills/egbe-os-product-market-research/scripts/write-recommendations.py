#!/usr/bin/env python3
"""Build the canonical pre-PRD recommendation artifact from a small JSON input."""

from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path(_artifact_path("egbe-docs/research/market/pre-prd-recommendations.md"))
CATALOG_PATH = Path(__file__).resolve().parents[1] / "references" / "catalog.v1.json"
MAX_EXPLANATION_CHARS = 400
# The reason renders as one short line under an option in the chat widget.
MAX_REASON_CHARS = 180
_MARKDOWN_PATTERN = re.compile(
    r"(?:^\s{0,3}(?:#{1,6}|>|[-+*]|\d+[.)])\s)|"
    r"(?:!?\[[^\]]*\]\([^)]*\)|`|\*\*|__|~~)"
)


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
        raise ValueError(f"cannot read {label} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON: {exc.msg}") from exc
    except _DuplicateJsonKeyError as exc:
        raise ValueError(f"{label} contains {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _catalog_sections(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the founder-selectable sections; internal sections are omitted.

    Internal sections (``"internal": true``) stay in the catalog so a caller
    can still invoke their workflow by ID, but they never appear in the
    founder-facing recommendation artifact.
    """
    if catalog.get("schema_version") != 1:
        raise ValueError("catalog schema_version must be 1")
    raw_sections = catalog.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise ValueError("catalog sections must be a non-empty list")

    sections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_sections:
        if not isinstance(raw, dict):
            raise ValueError("catalog sections must contain objects")
        option_id = str(raw.get("id") or "").strip()
        label = str(raw.get("label") or "").strip()
        description = str(raw.get("description") or "").strip()
        tag = str(raw.get("tag") or "").strip()
        estimated_minutes = raw.get("estimated_minutes")
        if not option_id or not label:
            raise ValueError("catalog sections require non-empty id and label")
        if option_id in seen:
            raise ValueError(f"catalog contains duplicate section id {option_id!r}")
        seen.add(option_id)
        if raw.get("internal") is True:
            continue
        if not description or not tag:
            raise ValueError(
                f"catalog section {option_id!r} requires non-empty description and tag"
            )
        if (
            not isinstance(estimated_minutes, int)
            or isinstance(estimated_minutes, bool)
            or estimated_minutes <= 0
        ):
            raise ValueError(
                f"catalog section {option_id!r} requires a positive integer estimated_minutes"
            )
        sections.append(
            {
                "id": option_id,
                "label": label,
                "description": description,
                "tag": tag,
                "estimated_minutes": estimated_minutes,
            }
        )
    if not sections:
        raise ValueError("catalog contains no founder-selectable sections")
    return sections


def _recommendation_input(value: dict[str, Any]) -> tuple[dict[str, str], str]:
    unknown_fields = set(value) - {"recommendations", "explanation"}
    if unknown_fields:
        raise ValueError(
            "recommendation input contains unsupported fields: "
            + ", ".join(sorted(unknown_fields))
        )

    raw_recommendations = value.get("recommendations")
    if not isinstance(raw_recommendations, dict):
        raise ValueError("recommendations must be an object of option id to reason")
    recommendations: dict[str, str] = {}
    for raw_id, raw_reason in raw_recommendations.items():
        option_id = str(raw_id).strip()
        if not option_id or not isinstance(raw_reason, str) or not raw_reason.strip():
            raise ValueError("every recommended option requires a non-empty string reason")
        reason = raw_reason.strip()
        if "\n" in reason or "\r" in reason:
            raise ValueError(
                f"reason for {option_id!r} must be a single line"
            )
        if len(reason) > MAX_REASON_CHARS:
            raise ValueError(
                f"reason for {option_id!r} must be one sentence of at most "
                f"{MAX_REASON_CHARS} characters (got {len(reason)})"
            )
        if _MARKDOWN_PATTERN.search(reason):
            raise ValueError(
                f"reason for {option_id!r} must not contain Markdown formatting"
            )
        recommendations[option_id] = reason

    explanation = value.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("explanation must be a non-empty plain-text string")
    explanation = explanation.strip()
    if "\n" in explanation or "\r" in explanation:
        raise ValueError("explanation must be one plain-text paragraph")
    if len(explanation) > MAX_EXPLANATION_CHARS:
        raise ValueError(
            f"explanation must be at most {MAX_EXPLANATION_CHARS} characters"
        )
    if _MARKDOWN_PATTERN.search(explanation):
        raise ValueError("explanation must not contain Markdown formatting")
    return recommendations, explanation


def build_recommendation_document(
    catalog: dict[str, Any],
    recommendation_input: dict[str, Any],
) -> str:
    """Return the complete canonical artifact without performing I/O."""

    sections = _catalog_sections(catalog)
    recommendations, explanation = _recommendation_input(recommendation_input)
    known_ids = {section["id"] for section in sections}
    unknown_ids = sorted(set(recommendations) - known_ids)
    if unknown_ids:
        raise ValueError(
            "recommendations contain unknown catalog option ids: "
            + ", ".join(unknown_ids)
        )

    options: list[dict[str, Any]] = []
    for section in sections:
        option_id = str(section["id"])
        recommended = option_id in recommendations
        item: dict[str, Any] = {
            "id": option_id,
            "label": section["label"],
            "description": section["description"],
            "tag": section["tag"],
            "estimated_minutes": section["estimated_minutes"],
            "recommended": recommended,
        }
        if recommended:
            item["reason"] = recommendations[option_id]
        options.append(item)

    metadata = {
        "schema_version": 1,
        "explanation_format": "plain_text",
        "options": options,
    }
    # JSON is a strict subset of YAML. Using the standard-library serializer
    # prevents generated reasons, punctuation, or Unicode from breaking the
    # YAML frontmatter consumed by the workflow runtime.
    encoded = json.dumps(metadata, ensure_ascii=False, indent=2)
    document = f"---\n{encoded}\n---\n\n{explanation}\n"

    # Self-validate the exact bytes before the caller can replace an artifact.
    frontmatter, body = document[4:].split("\n---\n", 1)
    if json.loads(frontmatter) != metadata or body.strip() != explanation:
        raise RuntimeError("generated recommendation artifact failed self-validation")
    return document


def write_recommendation_document(
    output: Path,
    catalog: dict[str, Any],
    recommendation_input: dict[str, Any],
) -> str:
    """Atomically replace ``output`` only after the document validates."""

    document = build_recommendation_document(catalog, recommendation_input)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(document)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        if temporary_path.read_text(encoding="utf-8") != document:
            raise RuntimeError("recommendation artifact changed during atomic write")
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, output)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        catalog = _read_json_object(args.catalog, label="catalog")
        recommendation_input = _read_json_object(
            args.input,
            label="recommendation input",
        )
        write_recommendation_document(args.output, catalog, recommendation_input)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
