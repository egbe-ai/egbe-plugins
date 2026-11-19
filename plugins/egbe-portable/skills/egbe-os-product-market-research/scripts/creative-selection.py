"""Canonical bounded creative inspection sample for portable readers."""
from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import hashlib
import json
from collections import defaultdict
from pathlib import Path

SELECTION_REL = Path(_artifact_path("egbe-docs/research/market/evidence/creative-selection.v1.json"))
TYPE_ORDER = {"text": 0, "static_image": 1, "video": 2, "unknown": 3}
ROLE_ORDER = {"direct": 0, "indirect": 1, "unknown": 2}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def eligible(row):
    return row.get("relevance") == "relevant" and row.get("language_status") == "allowed" and row.get("language_allowed") is True


def citable(row, countries=None):
    """A comparable source row in a researched market, not proof of performance."""
    country = row.get("country")
    return (eligible(row) and bool(country) and bool(row.get("channel"))
            and (not countries or country in countries))


def strength_key(row):
    # Stable bounded inspection sample, not a recommendation or success score.
    return (str(row.get("creative_id") or ""),)


def top_cells(creatives, countries=None, limit=3):
    groups = defaultdict(list)
    for row in creatives:
        groups[(row.get("country"), row.get("channel"), row.get("creative_type", "unknown"), row.get("domain"))].append(row)
    country_order = {country: pos for pos, country in enumerate(countries or [])}
    def key(pair):
        (country, channel, typ, domain), members = pair
        role = members[0].get("competitor_tier", "unknown")
        return (country_order.get(country, 999), str(country or ""), str(channel or ""), TYPE_ORDER.get(typ, 3), ROLE_ORDER.get(role, 2), str(domain or ""))
    cells = []
    for scope, members in sorted(groups.items(), key=key):
        country, channel, typ, domain = scope
        candidates = [r for r in members if eligible(r)]
        selected = sorted(candidates, key=strength_key)[:limit]
        cells.append({"country": country, "channel": channel, "creative_type": typ, "domain": domain,
                      "competitor_tier": members[0].get("competitor_tier", "unknown"), "total": len(members),
                      "eligible_total": len(candidates), "selected_count": len(selected),
                      "creative_ids": [r["creative_id"] for r in selected]})
    return cells


def build_selection(evidence, workspace=None):
    rows = evidence.get("rows") or []
    creatives = [r for r in rows if r.get("type") == "creative"]
    inputs = {k: v for k, v in (evidence.get("inputs") or {}).items() if k not in ("creative_selection_path", "creative_selection_sha256")}
    cells = top_cells(creatives, inputs.get("target_countries"))
    lookup = {(r.get("country"), r.get("channel"), r.get("creative_type", "unknown"), r.get("domain"), r.get("creative_id")): r for r in creatives}
    selected = []
    for cell_rank, cell in enumerate(cells, 1):
        for rank, cid in enumerate(cell["creative_ids"], 1):
            row = lookup[(cell["country"], cell["channel"], cell["creative_type"], cell["domain"], cid)]
            selected.append({**{k: row.get(k) for k in ("creative_id", "country", "channel", "creative_type", "domain", "competitor_tier", "landing_url", "footprint_ad_id", "source_members", "longevity_status", "running_at_capture", "served_days", "strength_components")},
                             "rank": rank, "cell_rank": cell_rank})
    hashes = {"corpus_sha256": digest(creatives),
              "classifications_sha256": digest([r for r in rows if r.get("type") == "creative_classification"]),
              "angle_dictionary_sha256": digest(evidence.get("angle_dictionary") or {}),
              "inputs_sha256": digest(inputs), "policy_sha256": inputs.get("policy_sha256"),
              "competitor_set_sha256": None, "channel_footprint_sha256": None}
    if workspace is not None:
        for key, filename in (("competitor_set_sha256", "competitors.json"), ("channel_footprint_sha256", "channel-footprint.json")):
            path = Path(workspace) / SELECTION_REL.parent / filename
            if path.is_file():
                hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"schema_version": 1, "artifact": "creative_selection.v1", "cells": cells,
            "selection_basis": "stable_id_inspection_sample", "selected_creatives": selected, "source_hashes": hashes}


def validate_selection(evidence, manifest, workspace=None):
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("artifact") != "creative_selection.v1":
        raise ValueError("unsupported creative selection manifest")
    expected = build_selection(evidence, workspace)
    for field in ("cells", "selected_creatives"):
        if manifest.get(field) != expected[field]:
            raise ValueError(f"creative selection {field} differs from the canonical inspection sample")
    hashes = manifest.get("source_hashes") or {}
    for key, value in expected["source_hashes"].items():
        if key in ("competitor_set_sha256", "channel_footprint_sha256") and workspace is None:
            continue
        if hashes.get(key) != value:
            raise ValueError(f"creative selection {key} is stale")
    if evidence.get("selection") is not None and evidence["selection"] != manifest:
        raise ValueError("embedded creative selection differs from its published manifest")
    return manifest


def read_selection(workspace, evidence):
    inputs = evidence.get("inputs") or {}
    rel = inputs.get("creative_selection_path")
    if rel != SELECTION_REL.as_posix():
        raise ValueError("creative selection path is missing or noncanonical; rerun Creative Patterns")
    path = Path(workspace) / SELECTION_REL
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != inputs.get("creative_selection_sha256"):
        raise ValueError("creative selection hash changed; rerun Creative Patterns")
    return validate_selection(evidence, json.loads(raw), workspace)
