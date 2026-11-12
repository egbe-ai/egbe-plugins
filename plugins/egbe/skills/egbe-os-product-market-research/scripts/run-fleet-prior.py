#!/usr/bin/env python3
"""Run the deterministic Fleet Benchmarks section against fleet GTM knowledge.

The fleet's own launches are the one dataset no competitor has: real spend,
clicks, sessions, and verdicts from campaigns we ran ourselves. This runner
projects ONLY the launches relevant to the product under research into the
report, via one OS endpoint:

  - `POST /gtm/comparables` — the OS gateway shows the whole agent-visible
    fleet pool (verified/directional records, PII-redacted at the source) to
    a server-side LLM judge (`gtm-comparables-judge` role) that keeps only
    experiments whose audience, problem, or product category genuinely
    matches the product context. Matching is semantic: differently-worded
    records still match, and keyword overlap alone is not enough.

Cross-niche aggregates are deliberately absent: pooled all-niche channel
medians and fleet-CPC-vs-auction comparisons said nothing about THIS product
and invited wrong conclusions, so this section renders comparable
experiments or an explicit "none relevant in our pool" statement — nothing
else.

No agent-side LLM: the semantic judgment runs inside the OS gateway and is
billed to the claw's own LLM key. Every response is cached in the runtime
directory for byte-stable replays; synthesis into decisions is a downstream
concern.
"""

from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import runpy as _egbe_runpy
from pathlib import Path as _EgbePath
_egbe_adapter = _EgbePath(__file__).with_name("connection_identity.py")
_connection_headers = _egbe_runpy.run_path(str(_egbe_adapter))["connection_headers"] if _egbe_adapter.is_file() else lambda _url: {}

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

SCHEMA_VERSION = 1
SECTION_ID = "fleet_prior"
SECTION_HEADING = "Fleet benchmarks"
DISPLAY_NAME = "Fleet Benchmarks"

DEFAULT_OS_URL = "https://os.hz.egbe.dev"
RUNTIME_REL = Path(_artifact_path("egbe-docs/research/market/work")) / SECTION_ID
EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/fleet-prior.json"))
REPORT_REL = Path(_artifact_path("egbe-docs/research/market/full-report.md"))

MAX_GTM_CALLS_PER_ATTEMPT = 4
MAX_QUERY_CHARS = 300
SEARCH_LIMIT = 10
STORED_CASES_CAP = 10
LEARNING_TRUNCATE = 400
RELEVANCE_TRUNCATE = 240
GTM_RETRY_DELAY_SECONDS = 5.0


class FleetPriorError(RuntimeError):
    """Terminal runner failure; runtime state is preserved for resume."""


def _load_script(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise FleetPriorError(f"cannot load bundled script {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


# ── OS client: bounded GTM reads with byte-stable replay cache ─────────────

@dataclass
class OsClient:
    os_url: str
    api_key: str
    cache_dir: Path
    max_gtm_calls: int = MAX_GTM_CALLS_PER_ATTEMPT
    gtm_calls: int = 0
    cache_hits: int = 0
    touched: set[str] = None  # type: ignore[assignment]  # set in __post_init__
    request: Callable[..., dict[str, Any]] | None = None
    sleep: Callable[[float], None] | None = None

    def __post_init__(self) -> None:
        if self.touched is None:
            self.touched = set()

    def _http(self, method: str, path: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        url = f"{self.os_url.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            for _name, _value in _connection_headers(req.full_url).items():
                req.add_unredirected_header(_name, _value)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                envelope = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise FleetPriorError(f"OS {path} failed: HTTP {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise FleetPriorError(f"OS {path} unreachable: {exc.reason}") from exc
        data_obj = envelope.get("data")
        if envelope.get("code") not in (None, 200) or not isinstance(data_obj, dict):
            raise FleetPriorError(f"OS {path} returned no data: {str(envelope)[:300]}")
        return data_obj

    def gtm_call(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        should_cache: Callable[[dict[str, Any]], bool] | None = None,
    ) -> tuple[dict[str, Any], str]:
        key_raw = json.dumps(
            {"kind": "gtm", "method": method, "path": path, "payload": payload},
            sort_keys=True,
        )
        digest = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        self.touched.add(digest)
        if cache_file.is_file():
            try:
                entry = json.loads(cache_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                cache_file.unlink(missing_ok=True)
                entry = None
            if entry is not None:
                self.cache_hits += 1
                response = entry["response"]
                return (
                    response if isinstance(response, dict) else {}
                ), entry.get("retrieved_on") or date.today().isoformat()

        transport = self.request or self._http
        attempts = 0
        while True:
            # The judged read is metered against the claw's own LLM key, and
            # even free reads are bounded: a broken loop must not hammer the
            # gateway.
            if self.gtm_calls >= self.max_gtm_calls:
                raise FleetPriorError(
                    f"GTM call budget exhausted ({self.max_gtm_calls} per attempt)"
                )
            self.gtm_calls += 1
            try:
                response = transport(method, path, payload, 180.0)
                break
            except FleetPriorError as exc:
                if attempts >= 1 or not re.search(r"HTTP 5\d\d", str(exc)):
                    raise
                attempts += 1
                (self.sleep or time.sleep)(GTM_RETRY_DELAY_SECONDS)
        retrieved_on = date.today().isoformat()
        normalized = response if isinstance(response, dict) else {}
        # A provisional state must not be frozen into the replay cache.
        if should_cache is not None and not should_cache(normalized):
            self.touched.discard(digest)
            return normalized, retrieved_on
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = cache_file.with_suffix(".json.tmp")
        tmp_file.write_text(
            json.dumps(
                {
                    "kind": "gtm",
                    "method": method,
                    "path": path,
                    "payload": payload,
                    "response": response,
                    "retrieved_on": retrieved_on,
                }
            ),
            encoding="utf-8",
        )
        tmp_file.replace(cache_file)
        return normalized, retrieved_on

    def ledger_totals(self) -> dict[str, Any]:
        """Durable provenance over entries THIS execution touched."""
        gtm_entries = 0
        dates: list[str] = []
        if self.cache_dir.is_dir():
            for digest in sorted(self.touched):
                entry_path = self.cache_dir / f"{digest}.json"
                try:
                    entry = json.loads(entry_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                gtm_entries += 1
                if isinstance(entry.get("retrieved_on"), str):
                    dates.append(entry["retrieved_on"])
        today = date.today().isoformat()
        return {
            "gtm_calls": gtm_entries,
            "first_retrieved_on": min(dates) if dates else today,
            "last_retrieved_on": max(dates) if dates else today,
        }


# ── deterministic helpers ──────────────────────────────────────────────────

def parse_terms(raw: str, cap: int) -> list[str]:
    seen: dict[str, None] = {}
    for part in re.split(r"[,;\n]", raw or ""):
        term = " ".join(part.strip().lower().split())
        if term and term not in seen:
            seen[term] = None
    return list(seen)[:cap]


def build_search_query(seed_terms: list[str]) -> str:
    query = ", ".join(seed_terms)[:MAX_QUERY_CHARS].strip().rstrip(",")
    return query


def _truncate(text: str, cap: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= cap:
        return text
    cut = text[:cap].rsplit(" ", 1)[0].rstrip()
    return (cut or text[:cap].rstrip()) + "…"


def _cents_to_usd(value: Any) -> str:
    try:
        return f"${float(value) / 100:.2f}"
    except (TypeError, ValueError):
        return "—"


def _scalar_or_field(value: Any, field: str) -> Any:
    """The GTM contract serves both structured objects and plain scalars for
    channel/segment/learning — normalize both, never assume."""
    if isinstance(value, dict):
        return value.get(field)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _metric_value(entry: Any) -> Any:
    """Metrics arrive either as {value, unit, ...} objects or as flat
    numbers; bool is an int subclass and is not a metric."""
    if isinstance(entry, dict):
        entry = entry.get("value")
    if isinstance(entry, bool) or not isinstance(entry, (int, float)):
        return None
    return entry


def normalize_fleet_case(result: dict[str, Any]) -> dict[str, Any] | None:
    """Trim one /gtm/comparables result into a bounded evidence row. The
    endpoint already redacts PII and hides inconclusive records."""
    if not isinstance(result, dict):
        return None
    metrics = result.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    metric_values: dict[str, Any] = {}
    for key in ("cpc_cents", "ctr_percent", "cpm_cents", "cost_per_session_cents", "spend_cents", "clicks", "impressions", "attributed_sessions"):
        value = _metric_value(metrics.get(key))
        if value is not None:
            metric_values[key] = value
    snapshot = result.get("product_snapshot")
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    case = {
        "type": "fleet_case",
        "record_id": result.get("record_id"),
        "experiment_id": result.get("experiment_id"),
        "product": snapshot.get("name") or result.get("product_id"),
        "channel_id": _scalar_or_field(result.get("channel"), "channel_id"),
        "verdict": result.get("verdict"),
        "trust_tier": result.get("trust_tier"),
        "window_days": result.get("window_days"),
        "sample_size": result.get("sample_size"),
        "started_at": str(result.get("started_at") or "")[:10] or None,
        "segment": _truncate(
            _scalar_or_field(result.get("segment"), "description") or "", 200
        )
        or None,
        "metrics": metric_values,
        "learning": _truncate(
            _scalar_or_field(result.get("learning"), "claim") or "",
            LEARNING_TRUNCATE,
        )
        or None,
        "relevance": _truncate(
            str(result.get("relevance_reason") or ""), RELEVANCE_TRUNCATE
        )
        or None,
        "tier": "A" if result.get("trust_tier") == "verified" else "B",
    }
    if not case["experiment_id"] or not case["channel_id"]:
        return None
    return case


# ── rendering ──────────────────────────────────────────────────────────────

def render_section(
    *,
    query: str,
    geo: str | None,
    cases: list[dict[str, Any]],
    coverage: dict[str, Any],
    totals: dict[str, Any],
    retrieved_on: str,
) -> str:
    lines: list[str] = []
    add = lines.append

    add(
        f"The fleet's own launch evidence retrieved {retrieved_on} from the "
        "GTM knowledge projection: past experiments judged genuinely "
        "comparable to THIS product (`/gtm/comparables` — the whole "
        "verified/directional pool, PII-redacted at the source, filtered "
        "semantically by an LLM judge, not by keyword overlap). These are "
        "OUR measured numbers, not industry averages: check n, dates, and "
        "windows before leaning on any figure — small-n results are "
        "directional. This section deliberately carries no cross-niche "
        "aggregate channel benchmarks: pooled all-niche medians say nothing "
        "about this product."
    )
    add("")
    context_line = f"Product context given to the judge: `{query}`"
    if geo:
        context_line += f"; launch geography `{geo}`"
    add(context_line + ".")
    add("")

    add("### Comparable fleet experiments")
    add("")
    if cases:
        add("| Product | Channel | Verdict | Trust | Key metrics | Started | Why comparable | Learning |")
        add("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for case in cases:
            metrics = case.get("metrics") or {}
            parts = []
            if metrics.get("cpc_cents") is not None:
                parts.append(f"CPC {_cents_to_usd(metrics['cpc_cents'])}")
            if metrics.get("ctr_percent") is not None:
                parts.append(f"CTR {float(metrics['ctr_percent']):.1f}%")
            if metrics.get("spend_cents") is not None:
                parts.append(f"spend {_cents_to_usd(metrics['spend_cents'])}")
            learning = (case.get("learning") or "").replace("|", "/")
            relevance = (case.get("relevance") or "").replace("|", "/")
            add(
                f"| {case.get('product') or '—'} | {case['channel_id']} | "
                f"{case.get('verdict') or '—'} | {case.get('trust_tier') or '—'} | "
                f"{'; '.join(parts) or '—'} | {case.get('started_at') or '—'} | "
                f"{_truncate(relevance, 160) or '—'} | "
                f"{_truncate(learning, 160) or '—'} |"
            )
    else:
        pool_size = coverage.get("pool_size") or 0
        judged = coverage.get("judged") or 0
        if pool_size == 0:
            add(
                "No relevant comparable experiment exists yet: our fleet "
                "pool holds no verified or directional experiment records at "
                "all. This is a coverage fact about our own launches, not "
                "evidence against the idea."
            )
        else:
            add(
                f"No relevant comparable experiment was found in our fleet "
                f"pool ({judged} of {pool_size} experiment(s) reviewed by "
                "the judge). The pool covers only what WE have launched, and "
                "the judge is instructed to exclude when unsure, so this is "
                "a coverage fact — not evidence against the idea."
            )
    add("")

    add("### Method and coverage")
    add("")
    add(
        f"- Reads recorded: {totals['gtm_calls']} OS GTM call(s), "
        "accumulated across attempts; cached replays add no new reads."
    )
    selection_line = (
        f"- Selection: the OS-side `{coverage.get('model_role') or 'gtm-comparables-judge'}` "
        f"LLM judge reviewed {coverage.get('judged') or 0} of "
        f"{coverage.get('pool_size') or 0} pool experiment(s) against the "
        f"product context and kept {coverage['agent_records_returned']} "
        f"(limit {SEARCH_LIMIT}); matching is semantic, conservative by "
        "instruction, and never invents records."
    )
    if coverage.get("partial"):
        selection_line += (
            " REVIEW INCOMPLETE: the judge did not see the whole pool, so "
            "unlisted comparable experiments may exist."
        )
    add(selection_line)
    add(
        "- The fleet prior is evidence of what WE measured, biased toward "
        "the niches and budgets we tried; it complements — never replaces "
        "— the external market sections. Aggregate cross-niche channel "
        "benchmarks and pooled-CPC comparisons are intentionally excluded."
    )
    add("")
    add("### Sources")
    add("")
    add(
        "- OS `/gtm/comparables` over the fleet GTM knowledge projection — "
        f"retrieved {retrieved_on}; the rows in "
        f"`{EVIDENCE_REL.as_posix()}` are exactly the set the table above "
        "is computed from."
    )
    return "\n".join(lines).strip() + "\n"


# ── orchestration ──────────────────────────────────────────────────────────

@dataclass
class RunInputs:
    seed_terms: list[str]
    geo: str | None


def run_pipeline(client: OsClient, inputs: RunInputs, workspace: Path) -> dict[str, Any]:
    if not inputs.seed_terms:
        raise FleetPriorError(
            "no seed terms available: pass --seed-keywords with 1-5 category "
            "or problem phrases derived from the research assignment (see the workflow doc)"
        )
    query = build_search_query(inputs.seed_terms)

    payload: dict[str, Any] = {"query": query, "limit": SEARCH_LIMIT}
    if inputs.geo:
        payload["geo"] = inputs.geo
    # A partial review (the judge saw only part of the pool) must never be
    # frozen into the replay cache: the next attempt has to re-ask.
    data, _ = client.gtm_call(
        "POST",
        "/gtm/comparables",
        payload,
        should_cache=lambda response: not response.get("partial"),
    )
    results = data.get("results")
    results = results if isinstance(results, list) else []
    cases = [c for c in (normalize_fleet_case(r) for r in results) if c]
    cases = cases[:STORED_CASES_CAP]

    partial = bool(data.get("partial"))
    if partial and not cases:
        # "Nothing relevant" is only a safe conclusion over the WHOLE pool.
        raise FleetPriorError(
            "comparables review was partial (the judge saw only part of the "
            "fleet pool) and returned no match; refusing to record a no-match "
            "conclusion — rerun later"
        )

    def _count(value: Any) -> int:
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    coverage = {
        "type": "coverage",
        "agent_records_returned": len(cases),
        "pool_size": _count(data.get("pool_size")),
        "judged": _count(data.get("judged")),
        "partial": partial,
        "selection": "llm_judged",
        "model_role": str(data.get("model_role") or "") or None,
        "search_query": query,
        "geo": inputs.geo,
        "tier": "A",
    }

    totals = client.ledger_totals()
    retrieved_on = (
        totals["first_retrieved_on"]
        if totals["first_retrieved_on"] == totals["last_retrieved_on"]
        else f"{totals['first_retrieved_on']}..{totals['last_retrieved_on']}"
    )

    evidence = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "generated_by": Path(__file__).name,
        "retrieved_on": retrieved_on,
        "inputs": {
            "seed_terms": inputs.seed_terms,
            "geo": inputs.geo,
            "search_query": query,
        },
        "rows": cases + [coverage],
        "totals": {"gtm_calls": totals["gtm_calls"]},
    }

    section_markdown = render_section(
        query=query,
        geo=inputs.geo,
        cases=cases,
        coverage=coverage,
        totals=totals,
        retrieved_on=retrieved_on,
    )
    return {
        "evidence": evidence,
        "section_markdown": section_markdown,
        "totals": totals,
        "attempt": {
            "gtm_calls": client.gtm_calls,
            "cache_hits": client.cache_hits,
        },
    }


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def run(workspace: Path, args: argparse.Namespace) -> dict[str, Any]:
    workspace = workspace.resolve()
    io = _load_script("research-artifact-io.py", "pmr_artifact_io")
    with io.section_attempt(workspace, SECTION_ID, context_file=getattr(args, "context_file", None)):
        return _run(workspace, args)


def _run(workspace: Path, args: argparse.Namespace) -> dict[str, Any]:
    workspace = workspace.resolve()
    runtime = workspace / RUNTIME_REL
    cache_dir = runtime / "cache"
    runtime.mkdir(parents=True, exist_ok=True)

    api_key = (os.environ.get("OS_API_KEY") or "").strip()
    if not api_key:
        raise FleetPriorError("OS_API_KEY is required")
    os_url = (os.environ.get("OS_URL") or DEFAULT_OS_URL).strip() or DEFAULT_OS_URL

    inputs = RunInputs(
        seed_terms=parse_terms(args.seed_keywords or "", 5),
        geo=(args.geo or "").strip() or None,
    )
    client = OsClient(
        os_url=os_url,
        api_key=api_key,
        cache_dir=cache_dir,
        max_gtm_calls=args.max_gtm_calls,
    )

    outcome = run_pipeline(client, inputs, workspace)

    evidence_path = workspace / EVIDENCE_REL
    evidence_json = json.dumps(outcome["evidence"], indent=1, ensure_ascii=False)
    _write_atomic(evidence_path, evidence_json)

    section_file = runtime / "result.md"
    _write_atomic(section_file, outcome["section_markdown"])

    upsert = _load_script("upsert-markdown-section.py", "pmr_upsert_markdown_section")
    report_path = workspace / REPORT_REL
    report_path.parent.mkdir(parents=True, exist_ok=True)
    upsert.upsert_markdown_section(report_path, SECTION_HEADING, outcome["section_markdown"])

    persist = _load_script("persist-research-report.py", "pmr_persist_research_report")
    persistence = persist.persist_research_report(
        workspace,
        commit_message=f"research: update {SECTION_HEADING.lower()} section",
        extra_paths=(Path(_artifact_path("egbe-docs/research/market/evidence/fleet-prior.json")),),
    )

    state = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "status": "completed",
        "seed_terms": inputs.seed_terms,
        "geo": inputs.geo,
        "evidence_path": EVIDENCE_REL.as_posix(),
        "evidence_sha256": hashlib.sha256(evidence_json.encode("utf-8")).hexdigest(),
        "result_path": (RUNTIME_REL / "result.md").as_posix(),
        "result_sha256": hashlib.sha256(outcome["section_markdown"].encode("utf-8")).hexdigest(),
        "gtm_calls": outcome["totals"]["gtm_calls"],
        "attempt_gtm_calls": outcome["attempt"]["gtm_calls"],
        "attempt_cache_hits": outcome["attempt"]["cache_hits"],
        "report_commit_sha": persistence.commit_sha,
        "publication_mode": persistence.publication_mode,
        "research_context": _load_script("research-artifact-io.py", "pmr_input_io").context_binding(workspace, SECTION_ID),
        "error": None,
    }
    _write_atomic(runtime / "request.json", json.dumps(state, indent=1))
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-file", type=Path, help="Explicit context for this study; no project files are discovered implicitly.")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--seed-keywords",
        default="",
        help="Comma-separated category and problem phrases derived from "
        "the research assignment; they are the product context the comparables judge "
        "matches experiments against.",
    )
    parser.add_argument(
        "--geo",
        default="",
        help="Optional launch geography given to the judge as context (e.g. US).",
    )
    parser.add_argument("--max-gtm-calls", type=int, default=MAX_GTM_CALLS_PER_ATTEMPT)
    args = parser.parse_args()

    try:
        state = run(args.workspace, args)
    except FleetPriorError as exc:
        print(f"{DISPLAY_NAME}: {exc}", file=sys.stderr)
        return 1
    print(
        f"{DISPLAY_NAME}: completed — {state['gtm_calls']} GTM call(s), "
        f"evidence at {state['evidence_path']}, report commit "
        f"{state['report_commit_sha'][:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
