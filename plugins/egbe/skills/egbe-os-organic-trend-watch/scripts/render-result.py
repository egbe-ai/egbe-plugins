#!/usr/bin/env python3
"""Render the canonical report-section body from validated analysis JSON."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _analysis import load_and_validate_analysis, render_body
from _contract import ContractError, atomic_write_text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.runtime_root.resolve()
    try:
        analysis, normalized = load_and_validate_analysis(root)
        atomic_write_text(root / "result.md", render_body(analysis, normalized))
    except (ContractError, OSError) as exc:
        print(f"organic trend result render failed: {exc}", file=sys.stderr)
        return 1
    print("rendered organic trend result body")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
