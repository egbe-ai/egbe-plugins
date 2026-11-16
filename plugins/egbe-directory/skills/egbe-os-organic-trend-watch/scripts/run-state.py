#!/usr/bin/env python3
"""Manage resumable organic trend workflow state without hidden side effects."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from _contract import (
    CANONICAL_PROVIDER_RUNS,
    ContractError,
    STEPS,
    SCHEMA_VERSION,
    SECTION_ID,
    TERMINAL_PROVIDER_FAILURE_STATUSES,
    atomic_write_json,
    collection_parameters,
    load_run_state,
    new_run_state,
    save_run_state,
    utc_now,
)


def _state_path(root: Path) -> Path:
    return root / "run-state.json"


def _archive_and_reset(root: Path, label: str) -> None:
    state = load_run_state(root)
    unsafe = [
        key for key, run in state["provider_runs"].items()
        if not isinstance(run, dict)
        or str(run.get("status", "")).upper()
        not in TERMINAL_PROVIDER_FAILURE_STATUSES | {"SUCCEEDED"}
    ]
    if unsafe:
        raise ContractError(
            "cannot refresh running or uncertain provider handles: " + ", ".join(unsafe)
        )
    archive = root / "archive" / label
    suffix = 1
    while archive.exists():
        archive = root / "archive" / f"{label}-{suffix}"
        suffix += 1
    archive.mkdir(parents=True)
    shutil.copy2(root / "context.json", archive / "context.json")
    for relative in (
        "run-state.json",
        "raw",
        "normalized",
        "analysis.json",
        "result.md",
        "receipt.json",
        "media",
        "frames",
        "visual-analysis",
    ):
        source = root / relative
        if source.exists():
            shutil.move(str(source), str(archive / source.name))
    state = new_run_state(root)
    state["supersedes_archive"] = archive.relative_to(root).as_posix()
    save_run_state(root, state)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    assignment = init.add_mutually_exclusive_group()
    assignment.add_argument("--assignment")
    assignment.add_argument("--assignment-file", type=Path)
    init.add_argument("--product-context")
    init.add_argument("--max-analysis-videos", type=int)
    init.add_argument("--discovery-limit-per-account", type=int)
    init.add_argument("--lookback-days", type=int)
    sub.add_parser("refresh")
    sub.add_parser("status")
    for command in ("begin-step", "complete-step", "fail-step"):
        command_parser = sub.add_parser(command)
        command_parser.add_argument("--step", choices=STEPS, required=True)
        if command == "fail-step":
            command_parser.add_argument("--error", required=True)
    restart = sub.add_parser("restart-failed-collection")
    restart.add_argument("--key", choices=sorted(CANONICAL_PROVIDER_RUNS), required=True)
    restart.add_argument("--run-id", required=True)
    args = parser.parse_args()
    root = args.runtime_root.resolve()

    try:
        if args.command == "init":
            path = _state_path(root)
            if args.assignment is not None or args.assignment_file is not None:
                if (root / "context.json").exists() or path.exists():
                    raise ContractError("context already exists; resume it or use a new runtime root")
                assignment_text = (
                    args.assignment_file.read_text(encoding="utf-8")
                    if args.assignment_file else args.assignment
                )
                context = {
                    "schema_version": SCHEMA_VERSION,
                    "section_id": SECTION_ID,
                    "assignment": assignment_text,
                    "product_context": args.product_context,
                }
                if args.max_analysis_videos is not None:
                    context["max_analysis_videos"] = args.max_analysis_videos
                context["collection"] = collection_parameters({"collection": {
                    key: value for key, value in {
                        "discovery_limit_per_account": args.discovery_limit_per_account,
                        "lookback_days": args.lookback_days,
                    }.items() if value is not None
                }})
                # Validate before publishing any state.
                if (not isinstance(assignment_text, str) or not assignment_text.strip()
                        or not args.product_context or not args.product_context.strip()):
                    raise ContractError("assignment and product context must be non-empty")
                if (args.max_analysis_videos is not None
                        and not 1 <= args.max_analysis_videos <= 30):
                    raise ContractError("max analysis videos must be from 1 to 30 (adapter resource ceiling)")
                atomic_write_json(root / "context.json", context)
            elif any(value is not None for value in (
                args.product_context, args.max_analysis_videos,
                args.discovery_limit_per_account, args.lookback_days,
            )):
                raise ContractError("context flags require a new assignment; existing context is immutable")
            if path.exists():
                state = load_run_state(root)
            else:
                state = new_run_state(root)
                save_run_state(root, state)
            print(json.dumps(state, indent=2, sort_keys=True))
            return 0

        state = load_run_state(root)
        if args.command == "refresh":
            _archive_and_reset(root, "refresh-" + state["collection_epoch"][:12])
            print(json.dumps(load_run_state(root), indent=2, sort_keys=True))
            return 0
        if args.command == "status":
            print(json.dumps(state, indent=2, sort_keys=True))
            return 0

        if args.command == "restart-failed-collection":
            run = state["provider_runs"].get(args.key)
            if not isinstance(run, dict):
                raise ContractError(f"no saved provider run for {args.key}")
            if run.get("run_id") != args.run_id:
                raise ContractError("saved provider run ID does not match --run-id")
            status = str(run.get("status") or "").upper()
            if status not in TERMINAL_PROVIDER_FAILURE_STATUSES:
                raise ContractError(
                    f"provider run {args.key} is {status or 'unknown'}, not terminal"
                )
            safe_run_id = "".join(
                character if character.isalnum() else "-"
                for character in args.run_id[:12]
            )
            label = f"failed-{args.key}-{safe_run_id}"
            _archive_and_reset(root, label)
            print(json.dumps(load_run_state(root), indent=2, sort_keys=True))
            return 0

        if args.command in {"begin-step", "complete-step", "fail-step"}:
            step = state["steps"].get(args.step)
            if not isinstance(step, dict):
                raise ContractError(f"run-state is missing step {args.step}")
            if args.command == "begin-step":
                step.update({"status": "running", "started_at": utc_now()})
                step.pop("error", None)
            elif args.command == "complete-step":
                step.update({"status": "completed", "completed_at": utc_now()})
                step.pop("error", None)
            else:
                step.update({"status": "failed", "failed_at": utc_now(), "error": args.error})
                state["status"] = "failed"
            save_run_state(root, state)
            return 0

        raise ContractError(f"unsupported run-state command: {args.command}")
    except (ContractError, OSError) as exc:
        print(f"organic trend run-state error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
