"""Structure and rendering for agent-authored geography analysis, not market scoring."""
from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import re
from datetime import date
from pathlib import PurePosixPath
from urllib.parse import urlparse

SECTION_ID = "geography_comparison"
HEADING = "Geography comparison"
SOURCE_ROOT = PurePosixPath(_artifact_path("egbe-docs/research/market/evidence/geography-comparison-sources"))


def artifact_path(reference: str) -> PurePosixPath:
    path = PurePosixPath(reference.removeprefix("artifact:"))
    if ".." in path.parts or not path.is_relative_to(SOURCE_ROOT) or path.suffix not in {".md", ".json", ".txt"}:
        raise ValueError(_artifact_path("Artifact sources must be sanitized notes under egbe-docs/research/market/evidence/geography-comparison-sources/"))
    return path


def text(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    return value


def fields(value, required: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"{label} requires exactly: {', '.join(sorted(required))}")


def items(value, label: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def validate(data: dict, *, available_sections: set[str]) -> None:
    fields(data, {"schema_version", "section_id", "context_sha256", "decision",
                  "geography_basis", "reason", "countries", "criteria", "sources",
                  "rows", "recommendation", "limitations"}, "comparison")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1 or data["section_id"] != SECTION_ID:
        raise ValueError("Expected geography_comparison schema version 1")
    if not re.fullmatch(r"[0-9a-f]{64}", text(data["context_sha256"], "context_sha256")):
        raise ValueError("context_sha256 must identify the prepared context")
    if data["decision"] not in ("compare", "not_compared"):
        raise ValueError("decision must be compare or not_compared")
    if data["geography_basis"] not in ("founder_constraint", "preference", "open", "evidence_supported"):
        raise ValueError("Invalid geography_basis")
    text(data["reason"], "reason")
    countries = set()
    for entry in items(data["countries"], "countries"):
        fields(entry, {"code", "reason"}, "country")
        code = text(entry["code"], "country.code")
        if not re.fullmatch(r"[A-Z]{2}", code) or code in countries:
            raise ValueError("Countries need unique uppercase two-letter codes")
        countries.add(code)
        text(entry["reason"], "country.reason")
    if not countries:
        raise ValueError("Declare the country scope; a comparison needs at least two")
    criteria = items(data["criteria"], "criteria")
    for criterion in criteria:
        text(criterion, "criterion")
    if len(set(criteria)) != len(criteria):
        raise ValueError("Criteria must be unique")
    sources = set()
    for source in items(data["sources"], "sources"):
        fields(source, {"id", "reference", "accessed_on", "period", "limitation"}, "source")
        identifier = text(source["id"], "source.id")
        if not re.fullmatch(r"S[1-9][0-9]*", identifier) or identifier in sources:
            raise ValueError("Source IDs must be unique S1, S2, …")
        sources.add(identifier)
        reference = text(source["reference"], "source.reference")
        if any(character.isspace() for character in reference):
            raise ValueError("Source reference must be one URL or research ID without whitespace")
        if reference.startswith("research:"):
            if reference.removeprefix("research:") not in available_sections:
                raise ValueError("Research source is not completed in the prepared context")
        elif reference.startswith("artifact:"):
            artifact_path(reference)
        else:
            parsed = urlparse(reference)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError("Source must be a public URL, prepared research:<id>, or owned artifact:<path>")
        date.fromisoformat(text(source["accessed_on"], "source.accessed_on"))
        text(source["period"], "source.period")
        text(source["limitation"], "source.limitation")
    covered = set()
    for row in items(data["rows"], "rows"):
        fields(row, {"type", "country", "criterion", "classification", "statement", "source_ids", "limitation"}, "finding")
        if row["type"] != "geography_finding" or row["country"] not in countries or row["criterion"] not in criteria:
            raise ValueError("Finding must reference a declared country and criterion")
        key = (row["country"], row["criterion"])
        if key in covered:
            raise ValueError("Use one finding per country/criterion; combine evidence or state disagreement")
        covered.add(key)
        classification = row["classification"]
        if classification not in ("observation", "estimate", "hypothesis", "unknown"):
            raise ValueError("Finding classification must distinguish observations, estimates, hypotheses and unknowns")
        refs = items(row["source_ids"], "source_ids")
        if any(not isinstance(ref, str) or ref not in sources for ref in refs):
            raise ValueError("Finding cites an unknown source ID")
        if classification == "observation" and not refs:
            raise ValueError("An observation needs a source; use hypothesis/unknown for unsupported claims")
        text(row["statement"], "finding.statement")
        text(row["limitation"], "finding.limitation")
    recommendation = data["recommendation"]
    fields(recommendation, {"primary_country", "runner_up_country", "rationale", "changes_choice_when", "next_step"}, "recommendation")
    for key in ("primary_country", "runner_up_country"):
        if recommendation[key] is not None and recommendation[key] not in countries:
            raise ValueError("Recommendation must reference a shortlisted country or null")
    if recommendation["runner_up_country"] is not None and (
        recommendation["primary_country"] is None or recommendation["runner_up_country"] == recommendation["primary_country"]
    ):
        raise ValueError("Runner-up requires a distinct primary recommendation")
    for key in ("rationale", "changes_choice_when", "next_step"):
        text(recommendation[key], f"recommendation.{key}")
    for limitation in items(data["limitations"], "limitations"):
        text(limitation, "limitation")
    if data["decision"] == "compare":
        if len(countries) < 2 or not criteria or covered != {(c, k) for c in countries for k in criteria}:
            raise ValueError("Compare every shortlisted country on the same criteria; unknown is a valid cell")
    elif criteria or covered or recommendation["primary_country"] is not None or recommendation["runner_up_country"] is not None:
        raise ValueError("not_compared must not contain a comparison or a market winner")


def cell(value: str) -> str:
    # Agent strings are literal content, never fences/headings or table syntax.
    # Normalize every line separator, including Unicode separators from sources.
    plain = " ".join(value.split())
    escaped = re.sub(r"([\\`*_{}\[\]()#+\-.!~])", r"\\\1", plain)
    return escaped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;")


def render(data: dict) -> str:
    rec = data["recommendation"]
    lines = ["Agent-authored comparison; source facts and judgments are distinguished below.", "",
             f"**Geography basis:** {cell(data['geography_basis'])}. {cell(data['reason'])}", "",
             f"**Coverage:** {data['decision']}. This is advice, not an approved market change.", "",
             "### Recommendation for the next test", "",
             f"Primary: {rec['primary_country'] or 'Undetermined'}. Runner-up: {rec['runner_up_country'] or 'Undetermined'}.", "",
             cell(rec["rationale"]), "", f"Reconsider when: {cell(rec['changes_choice_when'])}", "",
             f"Next step: {cell(rec['next_step'])}", "", "### Shortlist", ""]
    lines.extend(f"- **{entry['code']}** — {cell(entry['reason'])}" for entry in data["countries"])
    if data["rows"]:
        lines.extend(["", "### Comparable findings", "", "| Country | Criterion | Finding and basis | Limitations |", "| --- | --- | --- | --- |"])
        for row in data["rows"]:
            refs = ", ".join(row["source_ids"])
            lines.append(f"| {row['country']} | {cell(row['criterion'])} | {row['classification']}: {cell(row['statement'])} [{refs or 'no source'}] | {cell(row['limitation'])} |")
    lines.extend(["", "### Sources", ""])
    for source in data["sources"]:
        reference = source["reference"]
        if reference.startswith("research:"):
            reference = f"Previously published research: {reference.removeprefix('research:')}"
        elif reference.startswith("artifact:"):
            path = artifact_path(reference)
            reference = f"[{path.name}]({path.relative_to(SOURCE_ROOT.parent.parent).as_posix()})"
        else:
            reference = f"<{reference.replace('<', '%3C').replace('>', '%3E')}>"
        lines.append(f"- {source['id']}: {reference}. Accessed {source['accessed_on']}; period: {cell(source['period'])}. {cell(source['limitation'])}")
    if not data["sources"]:
        lines.append("No sourced observations available; do not treat this as market validation.")
    lines.extend(["", "### Evidence gaps and limitations", ""])
    lines.extend(f"- {cell(value)}" for value in data["limitations"])
    if not data["limitations"]:
        lines.append("See the per-finding limitations; no additional gap was recorded.")
    return "\n".join(lines).strip() + "\n"
