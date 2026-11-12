"""Publish independent keyword locales into one receipt-bound report section."""
from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(_artifact_path("egbe-docs/research/market/work/keyword_economics"))
EVIDENCE = Path(_artifact_path("egbe-docs/research/market/evidence/keyword-economics.json"))
REPORT = Path(_artifact_path("egbe-docs/research/market/full-report.md"))


def locale_key(location: int, language: str) -> str:
    if type(location) is not int or location <= 0 or not re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2})?", language):
        raise ValueError("Invalid keyword locale; use a positive location code and normalized language")
    return f"{location}-{language}"


def _read(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def ensure_current_format(workspace: Path) -> None:
    path = workspace / EVIDENCE
    if path.exists() and _read(path).get("schema_version") != 2:
        raise ValueError("Existing Keyword Economics evidence uses an old format. Preserve it in a separate "
                         "research workspace and rerun with the updated bundle; it will not be overwritten.")


def begin(workspace: Path, key: str, context_hash: dict, io) -> None:
    ensure_current_format(workspace)
    io.write_json(workspace / ROOT / "locales" / key / "request.json", {
        "status": "pending", "research_context": context_hash, "locale_key": key,
    })
    with io.publication_lock(workspace / REPORT):
        io.write_json(workspace / ROOT / "request.json", {"schema_version": 1,
                      "section_id": "keyword_economics", "status": "pending", "error": None,
                      "research_context": context_hash})


def failed(workspace: Path, key: str, context_hash: dict, io) -> None:
    # Do not store upstream exception text: it can contain provider request details.
    with io.publication_lock(workspace / REPORT):
        io.write_json(workspace / ROOT / "locales" / key / "request.json", {
            "status": "failed", "research_context": context_hash, "locale_key": key,
            "error": "Collection or publication failed; retry this locale using its cache.",
        })
        io.write_json(workspace / ROOT / "request.json", {"schema_version": 1,
                      "section_id": "keyword_economics", "status": "failed",
                      "research_context": context_hash,
                      "error": f"Locale {key} failed; last successful files are retained, not current completion."})


def aggregate(workspace: Path, context_hash: dict, io) -> tuple[dict, str, list[Path]]:
    locales, rows, body, paths, hashes = [], [], [], [], set()
    for request_path in sorted((workspace / ROOT / "locales").glob("*/request.json")):
        state = _read(request_path)
        key = request_path.parent.name
        path = EVIDENCE.parent / "keyword-economics" / f"{key}.json"
        entry = {"key": key, "status": state["status"], "evidence_path": path.as_posix()}
        if state.get("research_context") != context_hash:
            entry["status"] = "stale"
        elif state["status"] in {"collected", "completed"}:
            if not (workspace / path).is_file() or io.sha256(workspace / path) != state.get("evidence_sha256"):
                entry["status"] = "invalid"
            else:
                data = _read(workspace / path)
                entry.update({"locale": data["locale"], "retrieved_on": data["retrieved_on"],
                              "evidence_sha256": state["evidence_sha256"], "simulation": data["simulation"],
                              "inputs_sha256": data["inputs_sha256"], "status": "completed"})
                rows.extend({**r, "locale_key": key, "locale": data["locale"]} for r in data["rows"])
                hashes.update(data["request_hashes"])
                paths.append(path)
                nested = re.sub(r"(?m)^(#{3,5}) ", r"\1# ", data["section_markdown"])
                body.append(f"### Locale {key}\n\n{nested.strip()}")
        locales.append(entry)
        if entry["status"] != "completed":
            body.append(f"### Locale {key}\n\nCurrent outcome: **{entry['status']}**. "
                        "Previous results, if any, are not evidence of successful current coverage.")
    cost = 0.0
    for digest in sorted(hashes):
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid provider request hash")
        cache = _read(workspace / ROOT / "cache" / f"{digest}.json")
        value = cache["response"].get("cost")
        if isinstance(value, (int, float)):
            cost += value
    evidence = {"schema_version": 2, "section_id": "keyword_economics",
                "research_context": context_hash, "locales": locales, "rows": rows,
                "request_hashes": sorted(hashes), "totals": {"tasks_spent": len(hashes), "estimated_cost_usd": round(cost, 4)}}
    intro = ("Country scenarios are separate alternatives: volumes and CPCs are not pooled. "
             "The same test budget is not an allocation funding every country.\n\n")
    return evidence, intro + "\n\n".join(body) + "\n", paths


def publish(workspace: Path, key: str, context_hash: dict, outcome: dict, io, upsert, persist) -> dict:
    with io.publication_lock(workspace / REPORT):
        data = {**outcome["evidence"], "research_context": context_hash,
                "section_markdown": outcome["section_markdown"]}
        data["inputs_sha256"] = hashlib.sha256(json.dumps(data["inputs"], sort_keys=True).encode()).hexdigest()
        path = workspace / EVIDENCE.parent / "keyword-economics" / f"{key}.json"
        io.write_json(path, data)
        state = {"locale_key": key, "research_context": context_hash, "status": "collected",
                 "evidence_sha256": io.sha256(path), "attempt": outcome["attempt"]}
        state_path = workspace / ROOT / "locales" / key / "request.json"
        io.write_json(state_path, state)
        evidence, markdown, locale_paths = aggregate(workspace, context_hash, io)
        io.write_json(workspace / EVIDENCE, evidence)
        io.write_atomic(workspace / ROOT / "result.md", markdown)
        upsert._upsert_markdown_section(workspace / REPORT, "Keyword economics", markdown)
        persistence = persist._persist_research_report(
            workspace, commit_message="research: update keyword economics locales",
            extra_paths=[EVIDENCE, *locale_paths])
        state.update(status="completed", report_commit_sha=persistence.commit_sha,
                     publication_mode=persistence.publication_mode)
        io.write_json(state_path, state)
        complete = all(x["status"] == "completed" for x in evidence["locales"])
        receipt = {"schema_version": 1, "section_id": "keyword_economics",
                   "status": "completed" if complete else "incomplete", "error": None,
                   "research_context": context_hash, "locales": evidence["locales"],
                   "evidence_path": EVIDENCE.as_posix(), "evidence_sha256": io.sha256(workspace / EVIDENCE),
                   "result_path": (ROOT / "result.md").as_posix(), "result_sha256": io.sha256(workspace / ROOT / "result.md"),
                   **evidence["totals"], "attempt_tasks_spent": outcome["attempt"]["tasks_spent"],
                   "attempt_cache_hits": outcome["attempt"]["cache_hits"],
                   "report_commit_sha": persistence.commit_sha, "publication_mode": persistence.publication_mode}
        io.write_json(workspace / ROOT / "request.json", receipt)
        return receipt
