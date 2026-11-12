#!/usr/bin/env python3
"""Build canonical current-actor inputs without agent-authored field names."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _analysis import _validate_normalized
from _contract import (
    ContractError,
    atomic_write_json,
    load_run_state,
    provider_run_lock,
    read_json,
    sha256_file,
    validate_context,
)
from _provider_inputs import (
    INPUT_CONTRACT_VERSION,
    build_discovery_inputs,
    build_enrichment_inputs,
    validate_provider_input,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("discovery", "enrichment"), required=True)
    parser.add_argument("--accounts-file", type=Path)
    args = parser.parse_args()
    root = args.runtime_root.resolve()
    try:
        with provider_run_lock(root):
            outputs = _build(args, root)
        print(json.dumps(outputs, indent=2, sort_keys=True))
        return 0
    except (ContractError, OSError) as exc:
        print(f"could not build provider inputs: {exc}", file=sys.stderr)
        return 1


def _build(args: argparse.Namespace, root: Path) -> dict[str, dict[str, str]]:
    context = validate_context(root / "context.json")
    state = load_run_state(root)
    if state.get("accounts_source") is not None and state["accounts_source"] != {
        "path": "raw/accounts.json", "sha256": sha256_file(root / "raw/accounts.json"),
    }:
        raise ContractError("raw/accounts.json changed within this collection epoch")
    if args.mode == "discovery":
        source = args.accounts_file or (root / "raw/accounts.json")
        value = read_json(source.resolve())
        accounts = value.get("accounts")
        if not isinstance(accounts, list):
            raise ContractError("accounts file must contain an accounts list")
        payloads = build_discovery_inputs(accounts, context, state.get("collection_window"))
    else:
        normalized, _ = _validate_normalized(root)
        videos = normalized.get("videos")
        if not isinstance(videos, list):
            raise ContractError("normalized videos must be a list")
        payloads = build_enrichment_inputs(videos)
    if not payloads:
        raise ContractError(f"no {args.mode} provider inputs are applicable")
    outputs = {}
    for logical_key, payload in payloads.items():
        validate_provider_input(logical_key, payload)
        relative = f"raw/{logical_key}-input.json"
        existing = state["provider_runs"].get(logical_key)
        if existing is not None:
            if (not isinstance(existing, dict)
                    or existing.get("input_sha256") != sha256_file(root / relative)
                    or read_json(root / relative) != payload):
                raise ContractError(f"cannot replace attempted provider input {logical_key}")
        else:
            atomic_write_json(root / relative, payload)
        outputs[logical_key] = {
            "path": relative,
            "input_contract_version": INPUT_CONTRACT_VERSION,
        }
    return outputs


if __name__ == "__main__":
    raise SystemExit(main())
