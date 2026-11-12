#!/usr/bin/env python3
"""Validate caller-owned organic trend context."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _contract import ContractError, validate_context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate_context(args.context.resolve())
    except ContractError as exc:
        print(f"invalid organic trend context: {exc}", file=sys.stderr)
        return 1
    print("organic trend context is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
