"""Local, portable checks of the files pinned by measured research receipts."""
from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def identity_binding(registry, *, funnel_ids=(), lifecycle_domains=()):
    """Pin the real mappings used by one section, without publishing addresses.

    The shared registry is append-only across independent research tasks. Its
    serialization and unrelated identities are not inputs to this section.
    """
    selection = {"funnel_ids": sorted(set(funnel_ids)), "lifecycle_domains": sorted(set(lifecycle_domains))}
    if not isinstance(registry, dict) or registry.get("schema_version") != 1 or not isinstance(registry.get("mailbox"), str) or not isinstance(registry.get("identities"), list):
        raise ValueError("Research identity registry needs schema 1, mailbox and identities")
    identities = registry["identities"]
    if any(not isinstance(item, dict) for item in identities):
        raise ValueError("Research identities must be objects")
    selected = []
    for field, values, kind in (("funnel_id", selection["funnel_ids"], "funnel"),
                                ("domain", selection["lifecycle_domains"], "lifecycle")):
        for value in values:
            matches = [item for item in identities if item.get(field) == value and item.get("kind") == kind]
            if len(matches) != 1:
                raise ValueError("Used research identity is missing or ambiguous")
            item = matches[0]
            if any(not isinstance(item.get(key), str) or not item[key] for key in ("identity_id", "domain", "alias")):
                raise ValueError("Used research identity mapping is incomplete")
            if kind == "lifecycle" and item.get("funnel_id") is not None:
                raise ValueError("Lifecycle identity cannot be a funnel identity")
            if sum(other.get("alias") == item["alias"] for other in identities) != 1:
                raise ValueError("Used research alias is ambiguous")
            selected.append({key: item.get(key) for key in ("identity_id", "domain", "funnel_id", "alias", "kind")})
    selected.sort(key=lambda item: (item["kind"], item["domain"], item["funnel_id"] or ""))
    return {"schema_version": 1, "selection": selection,
            "sha256": digest({"schema_version": 1, "mailbox": registry["mailbox"], "identities": selected})}


def validate_identity_binding(workspace, binding):
    if not isinstance(binding, dict) or binding.get("schema_version") != 1 or not isinstance(binding.get("selection"), dict):
        raise ValueError("Research identity binding needs a scoped selection")
    selection = binding["selection"]
    if set(selection) != {"funnel_ids", "lifecycle_domains"} or any(not isinstance(selection[key], list) or any(not isinstance(value, str) or not value for value in selection[key]) for key in selection):
        raise ValueError("Research identity selection must contain identity keys")
    try:
        registry = json.loads((Path(workspace) / _artifact_path("egbe-docs/research/market/work/identity-registry.json")).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("Research identity registry is missing or invalid") from exc
    actual = identity_binding(registry, **selection)
    if actual != binding:
        raise ValueError("Used research identity mapping changed")


def bound_sources(workspace, sources):
    if not isinstance(sources, dict) or not sources:
        raise ValueError("Research source_files must be a nonempty path/hash map")
    root = Path(workspace).resolve()
    for name, expected in sources.items():
        path = Path(name)
        if not isinstance(name, str) or path.is_absolute() or ".." in path.parts:
            raise ValueError("Research source paths must stay inside the workspace")
        actual_path = (root / path).resolve()
        if not actual_path.is_relative_to(root):
            raise ValueError("Research source path escapes the workspace")
        actual = hashlib.sha256(actual_path.read_bytes()).hexdigest() if actual_path.is_file() else None
        if expected != actual:
            raise ValueError(f"Research source changed or is missing: {name}")


def validate_funnel_receipt(workspace, evidence, state):
    if evidence.get("schema_version") != 2:
        return  # legacy rows are diagnostic context, never campaign proof
    inputs = evidence.get("inputs") or {}
    sources = inputs.get("source_files")
    if sources != state.get("source_files"):
        raise ValueError("Funnel receipt source_files differs from published evidence")
    bound_sources(workspace, sources)
    required = {_artifact_path("egbe-docs/research/market/work/funnel_teardown/input-context.json"), _artifact_path("egbe-docs/research/market/evidence/creative-patterns.json"),
                _artifact_path("egbe-docs/research/market/evidence/channel-footprint.json"),
                _artifact_path("egbe-docs/research/market/work/creative_patterns/request.json"), _artifact_path("egbe-docs/research/market/work/channel_footprint/request.json")}
    if not required.issubset(sources):
        raise ValueError("Funnel receipt does not pin its upstream research/context")
    policy = inputs.get("effective_policy")
    if not isinstance(policy, dict) or digest(policy) != inputs.get("policy_sha256") or state.get("policy_sha256") != inputs.get("policy_sha256"):
        raise ValueError("Funnel effective policy/receipt hash mismatch")
    resume = inputs.get("resume_inputs")
    if not isinstance(resume, dict) or digest(resume) != inputs.get("inputs_sha256") or state.get("inputs_sha256") != inputs.get("inputs_sha256"):
        raise ValueError("Funnel resume input fingerprint mismatch")
    bound_sources(workspace, resume.get("source_files"))
    binding = inputs.get("identity_registry_binding")
    if any(value is not None for value in (binding, state.get("identity_registry_binding"), resume.get("identity_registry_binding"))):
        if binding != state.get("identity_registry_binding") or binding != resume.get("identity_registry_binding"):
            raise ValueError("Funnel identity binding differs from receipt or resume inputs")
        validate_identity_binding(workspace, binding)
    selection_path = inputs.get("creative_selection_path")
    if not selection_path or not inputs.get("creative_selection_sha256") or sources.get(selection_path) != inputs.get("creative_selection_sha256"):
        raise ValueError("Funnel selected creative manifest is missing or stale")
    for asset in inputs.get("assets", []):
        if not isinstance(asset, dict) or sources.get(asset.get("path")) != asset.get("sha256") or not asset.get("sha256"):
            raise ValueError("Funnel screenshot is missing from the pinned asset map")


def validate_lifecycle_inputs(workspace, state):
    for key, name in (("funnel_handoff_sha256", _artifact_path("egbe-docs/research/market/work/funnel_teardown/lifecycle-handoff.json")),):
        if state.get(key):
            bound_sources(workspace, {name: state[key]})
    if state.get("identity_registry_binding") is not None:
        validate_identity_binding(workspace, state["identity_registry_binding"])
    elif state.get("identity_registry_sha256"):
        # Existing receipts keep their original byte binding until republished.
        bound_sources(workspace, {_artifact_path("egbe-docs/research/market/work/identity-registry.json"): state["identity_registry_sha256"]})
