#!/usr/bin/env python3
"""Freeze standalone research selection, then derive outcomes from published receipts."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import uuid
from pathlib import Path


def _load(name):
    spec = importlib.util.spec_from_file_location("pmr_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_context(workspace: Path, *, selected: list[str] | None = None,
                  failed: list[str] = (), retry: list[str] = ()) -> dict:
    evidence = _load("research-evidence")
    io = _load("research-artifact-io")
    path = workspace / evidence.RUNTIME / "preview-context.json"
    with io.file_lock(path.with_suffix(".lock")):
        if path.exists():
            if selected is not None:
                raise ValueError("Selection is already frozen; use refresh without --sections")
            context = evidence.read_json(path)
            if not context.get("selection_id", "").startswith("local:"):
                raise ValueError("Unsupported selection receipt; preserve it and use a new research ID")
        else:
            catalog = evidence.catalog()
            if not selected or len(set(selected)) != len(selected) or any(s not in catalog for s in selected):
                raise ValueError("Initialize with unique known --sections IDs from references/catalog.v1.json")
            revision = hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest()
            # Freeze selection and catalog identity; each section binds its own inputs.
            context = {"schema_version": 1, "selection_id": "local:" + str(uuid.uuid4()),
                       "source_revision": revision,
                       "selected_option_ids": [s for s in catalog if s in selected],
                       "sections": [{"id": s, "label": c["label"], "status": "pending" if s in selected else "not_selected"}
                                    for s, c in catalog.items()]}
        ids = set(context["selected_option_ids"])
        if set(failed) & set(retry) or not set(failed).union(retry) <= ids:
            raise ValueError("--failed/--retry must name distinct selected sections")
        for entry in context["sections"]:
            section = entry["id"]
            if section not in ids:
                continue
            if section in failed:
                entry["status"] = "could_not_complete"
                entry["closed_by_caller"] = True
                entry.pop("coverage", None)
                continue
            # A caller's terminal decision remains closed until explicitly retried.
            if entry.get("closed_by_caller") and section not in retry:
                continue
            entry.pop("closed_by_caller", None)
            outcome = evidence.inspect_section(workspace, section)
            status = outcome["status"]
            if section == "organic_trend_watch":
                coverage = outcome.get("data", {}).get("coverage")
                if coverage is None:
                    entry.pop("coverage", None)
                else:
                    entry["coverage"] = coverage
            entry["status"] = (
                "pending" if section in retry and status == "could_not_complete" else status
            )
        io.write_json(path, context)
        return context


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--sections", help="Comma-separated IDs; initialization only")
    parser.add_argument("--failed", action="append", default=[], help="Explicitly close a skipped/failed selected section")
    parser.add_argument("--retry", action="append", default=[], help="Reopen a selected terminal section")
    args = parser.parse_args()
    try:
        context = build_context(args.workspace.resolve(), selected=args.sections.split(",") if args.sections else None,
                                failed=args.failed, retry=args.retry)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(context, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
