#!/usr/bin/env python3
"""Build and execute one configured OS Research section workflow."""

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
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


SCHEMA_VERSION = 3
REPORT_PATH = Path(_artifact_path("egbe-docs/research/market/full-report.md"))


@dataclass(frozen=True)
class SectionWorkflowSpec:
    section_id: str
    section_heading: str
    display_name: str
    system_prompt_filename: str
    user_prompt_filename: str
    supporting_section_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z0-9_]+", self.section_id):
            raise ValueError("research section id must use lowercase snake_case")
        if not self.section_heading.strip() or not self.display_name.strip():
            raise ValueError("research section heading and display name are required")
        for prompt_kind, prompt_filename in (
            ("system", self.system_prompt_filename),
            ("user", self.user_prompt_filename),
        ):
            prompt_path = Path(prompt_filename)
            if prompt_path.name != prompt_filename or prompt_path.suffix != ".md":
                raise ValueError(
                    f"research {prompt_kind} prompt must be one Markdown filename"
                )
        if self.user_prompt_filename == self.system_prompt_filename:
            raise ValueError("research user and system prompts must be different files")
        if len(set(self.supporting_section_ids)) != len(self.supporting_section_ids):
            raise ValueError("supporting research section ids must be unique")
        for section_id in self.supporting_section_ids:
            if not re.fullmatch(r"[a-z0-9_]+", section_id):
                raise ValueError(
                    "supporting research section ids must use lowercase snake_case"
                )
            if section_id == self.section_id:
                raise ValueError("a research section cannot support itself")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _completed_supporting_result(workspace: Path, section_id: str) -> str | None:
    evidence = _load_script("research-evidence.py", "pmr_evidence")
    outcome = evidence.inspect_section(workspace, section_id, require_materialized=False)
    return outcome.get("body") if outcome["status"] == "completed" else None


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


def _saved_inputs(workspace: Path, runtime_dir: Path, spec: SectionWorkflowSpec,
                  assignment: str | None, runtime, io) -> tuple[str, str, str]:
    """Recover the paid request's bytes, never rebuild them from current sources."""
    try:
        query = (runtime_dir / "query.md").read_text(encoding="utf-8")
        system_prompt = (runtime_dir / "system-prompt.md").read_text(encoding="utf-8")
        assignment_text = (runtime_dir / "assignment.md").read_text(encoding="utf-8")
        saved_assignment = assignment_text.removesuffix("\n")
        provenance_path = runtime_dir / "input-provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        state = runtime._read_state(runtime_dir / "request.json")
        if (not query.strip() or not system_prompt.strip() or not saved_assignment.strip()
            or assignment_text != saved_assignment.strip() + "\n"
            or not isinstance(provenance, dict) or provenance.get("schema_version") != 1
            or provenance.get("section_id") != spec.section_id
            or provenance.get("query_sha256") != hashlib.sha256(query.encode()).hexdigest()
            or provenance.get("assignment_sha256") != hashlib.sha256(saved_assignment.encode()).hexdigest()
            or provenance.get("research_context") != io.context_binding(workspace, spec.section_id)
            or not isinstance(provenance.get("measured_inputs"), dict)
            or not isinstance(state, dict)
            or state.get("status") not in {"submitting", "running", "failed", "completed"}
            or type(state.get("submission_attempt")) is not int or state["submission_attempt"] < 0
            or (state.get("status") in {"running", "completed"} and not state.get("job_id"))
            or state.get("input_provenance_sha256") != _file_sha256(provenance_path)):
            raise ValueError("Saved research input provenance is missing or damaged")
        runtime.require_matching_inputs(
            runtime_dir / "request.json", query=query, system_prompt=system_prompt,
            schema_version=SCHEMA_VERSION,
            result_path=runtime._relative(runtime_dir / "result.md", workspace),
            input_provenance_sha256=_file_sha256(provenance_path),
        )
        if state.get("status") == "completed" and (
            not state.get("job_id")
            or state.get("result_sha256") != _file_sha256(runtime_dir / "result.md")
        ):
            raise ValueError("Saved research result is missing or damaged; do not start new paid work")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Saved research inputs or result are missing or damaged; preserve evidence before retrying") from exc
    if assignment is not None and assignment.strip() != saved_assignment:
        raise ValueError("research inputs changed; existing evidence is preserved. Use a new research ID for a new assignment; do not automatically repeat paid work")
    return query, system_prompt, saved_assignment


def run_section_workflow(
    workspace: Path,
    *,
    spec: SectionWorkflowSpec,
    assignment: str | None = None,
    context_file: Path | None = None,
    research_run: Callable[..., Any] | None = None,
    materialize: Callable[[Path, str, str], Any] | None = None,
) -> dict[str, Any]:
    """Serialize preparation and execution for one narrative section."""
    spec.validate()
    if assignment is not None and not assignment.strip():
        raise ValueError("research assignment must not be empty")
    workspace = workspace.resolve()
    io = _load_script("research-artifact-io.py", "pmr_input_io")
    runtime_dir = workspace / _artifact_path('egbe-docs/research/market/work') / spec.section_id
    with io.file_lock(runtime_dir / ".run.lock", timeout=1):
        return _run_section_workflow(
            workspace, spec=spec, assignment=assignment, context_file=context_file,
            research_run=research_run, materialize=materialize,
        )


def _run_section_workflow(
    workspace: Path, *, spec: SectionWorkflowSpec, assignment: str | None,
    context_file: Path | None, research_run: Callable[..., Any] | None,
    materialize: Callable[[Path, str, str], Any] | None,
) -> dict[str, Any]:
    """Build canonical inputs once, then delegate saved execution to the runtime."""
    scripts_dir = Path(__file__).resolve().parent
    skill_root = scripts_dir.parent
    builder = _load_script("build-research-query.py", "pmr_query_builder")
    research = _load_script("run-os-research.py", "pmr_os_research")
    runtime = _load_script("research-section-runtime.py", "pmr_section_runtime")
    upsert = _load_script("upsert-markdown-section.py", "pmr_section_upsert")

    runtime_dir = workspace / _artifact_path('egbe-docs/research/market/work') / spec.section_id
    query_file = runtime_dir / "query.md"
    request_file = runtime_dir / "request.json"
    result_file = runtime_dir / "result.md"
    report_file = workspace / REPORT_PATH
    system_prompt_file = skill_root / "references" / "prompts" / spec.system_prompt_filename
    user_prompt_file = skill_root / "references" / "prompts" / spec.user_prompt_filename

    io = _load_script("research-artifact-io.py", "pmr_input_io")
    selected_context = io.bind_context(workspace, spec.section_id, context_file=context_file)
    provenance_path = runtime_dir / "input-provenance.json"
    if request_file.exists():
        query, system_prompt, assignment = _saved_inputs(
            workspace, runtime_dir, spec, assignment, runtime, io,
        )
    else:
        catalog = builder._read_json_object(
            skill_root / "references/catalog.v1.json", label="catalog",
        )
        supporting_evidence = tuple(
            (builder._catalog_label(catalog, section_id), body)
            for section_id in spec.supporting_section_ids
            if (body := _completed_supporting_result(workspace, section_id)) is not None
        )
        measured = _load_script("research-evidence.py", "pmr_evidence")
        measured_inputs, measured_manifest = measured.measured_context(workspace, spec.section_id)
        supporting_evidence += measured_inputs
        # The bundled brief is only a scope default for API callers on first use.
        assignment = (builder._read_text(user_prompt_file, label=f"{spec.display_name} user prompt")
                      if assignment is None else assignment.strip())
        if not assignment:
            raise ValueError("research assignment must not be empty")
        query = builder.build_query(
            context=selected_context["text"], section_label=builder._catalog_label(catalog, spec.section_id),
            reason=None, assignment=assignment, supporting_evidence=supporting_evidence,
        )
        system_prompt = system_prompt_file.read_text(encoding="utf-8").strip()
        if not system_prompt:
            raise ValueError(f"{spec.display_name} system prompt must not be empty")
        builder.write_atomic(query_file, query)
        builder.write_atomic(runtime_dir / "assignment.md", assignment + "\n")
        builder.write_atomic(provenance_path, json.dumps({
            "schema_version": 1, "section_id": spec.section_id,
            "research_context": io.context_binding(workspace, spec.section_id),
            "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
            "assignment_sha256": hashlib.sha256(assignment.encode()).hexdigest(),
            "measured_inputs": measured_manifest,
        }, indent=2, sort_keys=True) + "\n")
        builder.write_atomic(runtime_dir / "system-prompt.md", system_prompt)

    run_research = research_run or research.run_research_to_file

    def execute_research(**kwargs: Any) -> Any:
        return run_research(
            **kwargs,
            query=query,
            system_prompt=system_prompt,
            base_url=os.environ.get("OS_URL") or research.DEFAULT_OS_URL,
            api_key=os.environ.get("OS_API_KEY", ""),
        )

    materializer = materialize or (
        lambda path, heading, body: upsert.upsert_markdown_section(path, heading, body)
    )
    return runtime.run_resumable_section(
        workspace,
        query=query,
        system_prompt=system_prompt,
        section_heading=spec.section_heading,
        request_file=request_file,
        result_file=result_file,
        report_file=report_file,
        schema_version=SCHEMA_VERSION,
        input_provenance_sha256=_file_sha256(provenance_path),
        execute_research=execute_research,
        materialize=materializer,
    )


def run_cli(
    *,
    description: str,
    display_name: str,
    runner: Callable[[Path], dict[str, Any]],
) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    task = parser.add_mutually_exclusive_group(required=True)
    task.add_argument("--assignment", help="Bounded research question and scope from the project method/current task.")
    task.add_argument("--assignment-file", type=Path, help="Existing UTF-8 task text; no special format required.")
    parser.add_argument("--context-file", type=Path, help="Explicit additional context safe to send to the research provider.")
    args = parser.parse_args()
    try:
        assignment_path = args.assignment_file if not args.assignment_file or args.assignment_file.is_absolute() else args.workspace / args.assignment_file
        assignment = assignment_path.read_text(encoding="utf-8") if assignment_path else args.assignment
        result = runner(args.workspace, assignment=assignment, context_file=args.context_file)
        persistence = _load_script(
            "persist-research-report.py",
            "pmr_report_persistence",
        )
        persisted = persistence.persist_research_report(args.workspace)
        result_path = args.workspace.resolve() / result["result_path"]
        state = json.loads((result_path.parent / "request.json").read_text())
        io = _load_script("research-artifact-io.py", "pmr_artifact_io")
        io.write_json(result_path.parent / "publication.json", {
            "schema_version": 1, "result_sha256": state["result_sha256"],
            "report_commit_sha": persisted.commit_sha, "publication_mode": persisted.publication_mode,
        })
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    mode = "reused" if result["reused"] else "completed"
    print(
        f"{display_name} research {mode}; materialized {result['report_path']}; "
        "local files written; caller owns git publication"
    )
    return 0
