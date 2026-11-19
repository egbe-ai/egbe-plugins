#!/usr/bin/env python3
"""Check saved evidence for one operation; no network calls or method gates."""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

CHANNEL = "meta"
GROUP_IDS = "adset_ids"
GROUP_ROWS = "adsets"
GROUP_KIND = "adset"
PHASES = ("build-paused", "launch-ready", "launch", "status", "monitoring", "pause")


def timestamp(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def observed_status(row: dict) -> str:
    keys = ("configured_status", "status") if CHANNEL == "reddit" else ("effective_status", "status")
    return next((str(row[key]).upper() for key in keys if row.get(key)), "")


def validate(state: Any, readback: Any, phase: str, campaign_id: str) -> list[str]:
    issues: list[str] = []
    if not isinstance(state, dict) or not isinstance(readback, dict):
        return ["state and readback must be JSON objects"]
    if state.get("channel") != CHANNEL:
        issues.append(f"campaign-state.json.channel must be {CHANNEL}")
    objects = state.get("objects")
    if not isinstance(objects, dict):
        return issues + ["campaign-state.json.objects must be an object"]
    if not identifier(campaign_id) or objects.get("campaign_id") != campaign_id:
        issues.append("campaign-state campaign_id must match the exact requested campaign ID")

    selected = {"campaign": [campaign_id]}
    for key, kind in ((GROUP_IDS, GROUP_KIND), ("ad_ids", "ad")):
        values = objects.get(key, [])
        if not isinstance(values, list) or any(not identifier(value) for value in values):
            issues.append(f"objects.{key} must contain string IDs")
            values = []
        if len(set(values)) != len(values):
            issues.append(f"objects.{key} contains duplicate IDs")
        if phase in {"build-paused", "launch-ready", "launch"} and not values:
            issues.append(f"objects.{key} must be non-empty for {phase}")
        selected[kind] = values

    observed_at = timestamp(readback.get("observed_at"))
    if observed_at is None:
        issues.append("readback.observed_at must be an ISO-8601 timestamp with timezone")
    rows = {}
    campaign = readback.get("campaign")
    if not isinstance(campaign, dict) or campaign.get("id") != campaign_id:
        issues.append("readback campaign ID must match the exact requested campaign")
    else:
        rows[("campaign", campaign_id)] = campaign
    for key, kind in ((GROUP_ROWS, GROUP_KIND), ("ads", "ad")):
        entries = readback.get(key, [])
        if not isinstance(entries, list):
            issues.append(f"readback.{key} must be a list")
            entries = []
        seen = set()
        for row in entries:
            if not isinstance(row, dict) or not identifier(row.get("id")):
                issues.append(f"readback.{key} contains an invalid object ID")
                continue
            identity = row["id"]
            if identity in seen:
                issues.append(f"readback.{key} contains duplicate ID {identity}")
            seen.add(identity)
            rows[(kind, identity)] = row
            parent_field = "campaign_id" if kind == GROUP_KIND else ("ad_group_id" if CHANNEL == "reddit" else "adset_id")
            parents = [campaign_id] if kind == GROUP_KIND else selected[GROUP_KIND]
            if parent_field in row and row[parent_field] not in parents:
                issues.append(f"readback {kind} {identity} has a mismatched parent")
        for identity in selected[kind]:
            if identity not in seen:
                issues.append(f"readback is missing selected {kind} ID {identity}")

    selected_rows = [rows[(kind, identity)] for kind, ids in selected.items()
                     for identity in ids if (kind, identity) in rows]
    paused = {"PAUSED", "ARCHIVED", "DELETED"}
    if phase in {"build-paused", "launch-ready"}:
        if any(observed_status(row) != "PAUSED" for row in selected_rows):
            issues.append("paused build/readiness requires PAUSED readback for every selected object")
    if phase == "pause" and isinstance(campaign, dict) and observed_status(campaign) not in paused:
        issues.append("pause requires confirmed non-serving campaign readback")
    if phase == "pause" and state.get("status") not in {"paused", "archived", "deleted"}:
        issues.append("pause state must reflect the confirmed non-serving campaign")
    active_claim = state.get("status") in {"active", "monitoring"}
    if active_claim and any(observed_status(row) != "ACTIVE" for row in selected_rows):
        issues.append("active state requires ACTIVE provider readback for every selected object")
    if phase == "launch" and state.get("status") not in {"active", "activation_pending"}:
        issues.append("launch status must be active or activation_pending")

    # These optional operational values are checked when recorded, not demanded
    # for a status/pause. The live API owns its configurable budget limits.
    budget = state.get("budget")
    if budget is not None:
        value = budget.get("daily_budget_usd") if isinstance(budget, dict) else None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            issues.append("recorded daily_budget_usd must be a finite positive number")
    if "create_payload" in state or "create_idempotency_key" in state:
        key = state.get("create_idempotency_key")
        if not identifier(key) or len(key) > 128 or not isinstance(state.get("create_payload"), dict):
            issues.append("campaign create recovery requires the saved key and exact payload")

    if CHANNEL == "reddit":
        activation = state.get("activation")
        pending = state.get("status") == "activation_pending"
        # Status-only reads can observe existing ACTIVE configuration without
        # claiming a new activation. New launch completion requires receipts.
        if phase == "launch" or pending:
            if not isinstance(activation, dict):
                issues.append("activation requires current-attempt mutation evidence")
            else:
                started = timestamp(activation.get("started_at"))
                receipts = activation.get("accepted_mutations")
                valid = (
                    started is not None and observed_at is not None
                    and started <= observed_at and isinstance(receipts, list)
                    and (bool(receipts) or pending)
                )
                for receipt in receipts if isinstance(receipts, list) else []:
                    if not isinstance(receipt, dict):
                        valid = False
                        continue
                    accepted = timestamp(receipt.get("mutation_accepted_at"))
                    valid = valid and (
                        (receipt.get("object_type"), receipt.get("object_id")) in rows
                        and receipt.get("object_id") in selected.get(receipt.get("object_type"), [])
                        and receipt.get("mutation_accepted") is True
                        and receipt.get("requested_status") == "ACTIVE"
                        and accepted is not None and started <= accepted <= observed_at
                    )
                if not valid:
                    issues.append("activation requires accepted ACTIVE mutation receipts for selected objects from this attempt, followed by timestamped readback")
                if pending and started is not None:
                    for field in ("launched_at", "restarted_at", "reactivated_at"):
                        value = timestamp(state.get(field))
                        if value is not None and value >= started:
                            issues.append(f"activation_pending must not record a successful {field}")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-root", type=Path, required=True)
    parser.add_argument("--campaign-path", required=True, help="Product-relative folder for this exact operation.")
    parser.add_argument("--campaign-id", required=True, help="Exact ID selected by the task, not inferred from a name.")
    parser.add_argument("--phase", required=True, choices=PHASES)
    args = parser.parse_args(argv)
    root = args.product_root.resolve()
    relative = Path(args.campaign_path)
    directory = (root / relative).resolve()
    try:
        if relative.is_absolute() or directory == root or not directory.is_relative_to(root):
            raise ValueError("campaign-path must be a folder inside product-root")
        state = json.loads((directory / "campaign-state.json").read_text(encoding="utf-8"))
        readback = json.loads((directory / "launch-readback.json").read_text(encoding="utf-8"))
        issues = validate(state, readback, args.phase, args.campaign_id)
    except (OSError, ValueError) as exc:
        issues = [str(exc)]
    if issues:
        print(f"FAIL {CHANNEL} operation evidence", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    print(f"OK {CHANNEL} operation evidence phase={args.phase}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
