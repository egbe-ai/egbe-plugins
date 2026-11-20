#!/usr/bin/env python3
"""Prepare reusable evidence, then publish one agent-authored geography comparison."""
from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(_artifact_path("egbe-docs/research/market/work/geography_comparison"))
EVIDENCE = Path(_artifact_path("egbe-docs/research/market/evidence/geography-comparison.json"))
REPORT = Path(_artifact_path("egbe-docs/research/market/full-report.md"))


def load(name):
    spec = importlib.util.spec_from_file_location("pmr_" + name.replace("-", "_"), Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    # Dataclass-based existing helpers expect their module to be registered.
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def current_files(workspace: Path, files: dict) -> bool:
    io = load("research-artifact-io")
    for name, digest in files.items():
        path = workspace / name
        if not path.resolve().is_relative_to(workspace.resolve()):
            raise ValueError("Geography input files must remain inside the workspace")
        if not path.is_file() or io.sha256(path) != digest:
            return False
    return True


def prepare(workspace: Path, *, context_file=None) -> dict:
    evidence, io = load("research-evidence"), load("research-artifact-io")
    path = workspace / ROOT / "context.json"
    with io.file_lock(workspace / ROOT / ".run.lock", timeout=1):
        selected = io.bind_context(workspace, "geography_comparison", context_file=context_file)
        binding = io.context_binding(workspace, "geography_comparison")
        files = {binding["path"]: binding["sha256"]}
        sections = []
        selection_path = workspace / evidence.RUNTIME / "preview-context.json"
        selection = evidence.read_json(selection_path) if selection_path.exists() else {}
        statuses = {row["id"]: row["status"] for row in selection.get("sections", [])}
        for section, spec in evidence.catalog().items():
            if section in {"geography_comparison", "fleet_prior"}:
                continue
            status = statuses.get(section)
            outcome = {"status": status} if status == "could_not_complete" else evidence.inspect_section(workspace, section)
            if status == "not_selected" and outcome["status"] == "pending":
                outcome = {"status": "not_selected"}
            entry = {"id": section, "label": spec["label"], "status": outcome["status"], "reason": outcome.get("reason")}
            if outcome["status"] == "completed":
                entry["body"] = outcome["body"]
                root = workspace / evidence.RUNTIME / section
                # Bind only existing proof files; never copy private Fleet data or provider credentials.
                for filename in ("request.json", "integration-receipt.json", "receipt.json", "result.md", "completion-review.json", "input-provenance.json", "publication.json"):
                    source = root / filename
                    if source.is_file():
                        files[source.relative_to(workspace).as_posix()] = io.sha256(source)
                if section in evidence.MEASURED:
                    source = workspace / evidence.EVIDENCE / evidence.MEASURED[section]
                    files[source.relative_to(workspace).as_posix()] = io.sha256(source)
            sections.append(entry)
        context = {"schema_version": 1, "product_context": selected["text"], "research_context": binding,
                   "input_files": files, "sections": sections}
        if not path.exists() or evidence.read_json(path) != context:
            io.write_json(workspace / ROOT / "request.json", {
                "schema_version": 1, "section_id": "geography_comparison", "status": "pending", "error": None,
                "research_context": binding,
            })
            io.write_json(path, context)
        return {"context_path": str(path), "context_sha256": io.sha256(path)}


def finalize(workspace: Path, input_path: Path, *, persist=None) -> dict:
    io, evidence, contract = load("research-artifact-io"), load("research-evidence"), load("geography-comparison-contract")
    with io.section_attempt(workspace, "geography_comparison"):
        context_path = workspace / ROOT / "context.json"
        context = evidence.read_json(context_path)
        data = evidence.read_json(input_path)
        available = {s["id"] for s in context["sections"] if s["status"] == "completed"}
        contract.validate(data, available_sections=available)
        source_files = {}
        for source in data["sources"]:
            if source["reference"].startswith("artifact:"):
                relative = contract.artifact_path(source["reference"])
                path = workspace / relative
                if not path.resolve().is_relative_to(workspace.resolve()):
                    raise ValueError("Artifact source escapes the workspace")
                source_files[relative.as_posix()] = io.sha256(path)
        if data["context_sha256"] != io.sha256(context_path) or not current_files(workspace, context["input_files"]):
            raise ValueError("Prepared geography context changed; rerun --prepare and review the comparison before publishing")
        for section in available:
            if evidence.inspect_section(workspace, section)["status"] != "completed":
                raise ValueError(f"Supporting {section} is no longer completed; rerun --prepare and review")
        result = contract.render(data)
        result_path = workspace / ROOT / "result.md"
        with io.publication_lock(workspace / REPORT):
            io.write_json(workspace / EVIDENCE, data)
            io.write_atomic(result_path, result)
            load("upsert-markdown-section")._upsert_markdown_section(workspace / REPORT, contract.HEADING, result)
            # Already under the shared report lock; use the lock-free persistence boundary.
            publisher = persist or load("persist-research-report")._persist_research_report
            publication = publisher(workspace, extra_paths=[EVIDENCE,
                                    *(Path(name) for name in source_files)])
            state = {"schema_version": 1, "section_id": contract.SECTION_ID, "status": "completed", "error": None,
                     "research_context": context["research_context"],
                     "context_sha256": io.sha256(context_path), "input_files": context["input_files"],
                     "source_files": source_files,
                     "result_path": (ROOT / "result.md").as_posix(), "result_sha256": io.sha256(result_path),
                     "evidence_path": EVIDENCE.as_posix(), "evidence_sha256": io.sha256(workspace / EVIDENCE),
                     "publication_mode": publication.publication_mode, "report_commit_sha": publication.commit_sha}
            evidence._publication(state)
            io.write_json(workspace / ROOT / "request.json", state)
        return state


def inspect(workspace: Path, state: dict) -> tuple[str, dict]:
    """Validate the same portable boundary used by standalone preview."""
    evidence, io, contract = load("research-evidence"), load("research-artifact-io"), load("geography-comparison-contract")
    if state.get("schema_version") != 1 or state.get("section_id") != contract.SECTION_ID:
        raise ValueError("Invalid geography receipt")
    evidence._publication(state)
    context = evidence.read_json(workspace / ROOT / "context.json")
    io.verify_context(workspace, "geography_comparison", state.get("research_context"))
    if (state.get("context_sha256") != io.sha256(workspace / ROOT / "context.json")
        or state.get("input_files") != context["input_files"]
        or not current_files(workspace, context["input_files"])
        or not current_files(workspace, state["source_files"])):
        raise ValueError("Geography comparison inputs changed; prepare and review again")
    result = evidence._bound_file(workspace, state, ROOT / "result.md", "result")
    data = evidence.read_json(evidence._bound_file(workspace, state, EVIDENCE, "evidence"))
    available = {s["id"] for s in context["sections"] if s["status"] == "completed"}
    contract.validate(data, available_sections=available)
    for section in available:
        if evidence.inspect_section(workspace, section)["status"] != "completed":
            raise ValueError(f"Geography input {section} is no longer completed")
    if data["context_sha256"] != state["context_sha256"] or result.read_text().strip() != contract.render(data).strip():
        raise ValueError("Geography comparison rendering/context does not match its analysis")
    return result.read_text().strip(), data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--context-file", type=Path, help="Explicit context for the comparison.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--input", type=Path, help="Agent-authored JSON; validates and publishes without provider calls")
    args = parser.parse_args()
    try:
        workspace = args.workspace.resolve()
        outcome = prepare(workspace, context_file=args.context_file) if args.prepare else finalize(workspace, args.input)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.exit(1, f"Geography comparison: {exc}\n")
    print(json.dumps(outcome, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
