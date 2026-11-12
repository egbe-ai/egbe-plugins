#!/usr/bin/env python3
"""Run or resume Market Size research, then materialize its cached result."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


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


workflow = _load_script("research-section-workflow.py", "pmr_section_workflow")
SPEC = workflow.SectionWorkflowSpec(
    section_id="market_size_dynamics",
    section_heading="Market size and dynamics",
    display_name="Market Size",
    system_prompt_filename="market-size-and-dynamics.md",
    user_prompt_filename="market-size-and-dynamics.user.md",
)


def run_workflow(
    workspace: Path,
    *,
    assignment: str | None = None,
    context_file: Path | None = None,
    research_run: Callable[..., Any] | None = None,
    materialize: Callable[[Path, str, str], Any] | None = None,
) -> dict[str, Any]:
    return workflow.run_section_workflow(
        workspace,
        spec=SPEC,
        assignment=assignment,
        context_file=context_file,
        research_run=research_run,
        materialize=materialize,
    )


def main() -> int:
    return workflow.run_cli(
        description=__doc__ or "",
        display_name=SPEC.display_name,
        runner=run_workflow,
    )


if __name__ == "__main__":
    raise SystemExit(main())
