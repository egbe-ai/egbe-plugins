#!/usr/bin/env python3
"""Portable effective evidence settings owned by Product Market Research.

Other skill bundles consume the exported snapshot and its canonical hash;
they do not import this module from a sibling checkout.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def policy_from_taxonomy(taxonomy: dict[str, Any], direct_fallback_min=None) -> tuple[dict[str, Any], str]:
    """Version the observation contract, never business-success thresholds."""
    policy = {
        "schema_version": 2,
        "classification": "observations_only",
        "activity": "native_status_only",
        "duration": "native_delivery_scope",
    }
    return policy, canonical_hash(policy)


def load_policy(taxonomy_path: Path | None = None, sources_path: Path | None = None) -> tuple[dict[str, Any], str]:
    root = Path(__file__).resolve().parent.parent
    taxonomy = json.loads((taxonomy_path or root / "references/config/creative-taxonomy.v1.json").read_text(encoding="utf-8"))
    return policy_from_taxonomy(taxonomy)
