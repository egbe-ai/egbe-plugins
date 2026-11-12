#!/usr/bin/env python3
"""Run the deterministic Keyword Economics section against OS DataForSEO tools.

Unlike the OS Research sections, this runner performs NO free-form web
research: every number comes from a metered DataForSEO call through the OS
tools passthrough (`POST {OS_URL}/tools/dataforseo/<op>`), and the section
markdown plus a machine-readable evidence file are rendered deterministically
from those responses. The executing agent supplies only candidate seed
keywords (validated by auction data — a hallucinated seed returns zero volume
and is dropped); it never writes section prose.

Pipeline: seeds -> expansion (keywords_for_keywords + search_volume) ->
commercial filter -> SERP on top heads (who ranks, who pays) -> competitor
confirmation -> ranked-keywords enrichment per competitor -> test-budget
simulation (ad_traffic_by_keywords) -> evidence.json + report section.

Every upstream response is cached under the runtime directory keyed by request
hash, so re-runs replay from cache instead of re-spending the shared deposit.
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
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any, Callable
from urllib.parse import urlparse

SCHEMA_VERSION = 1
SECTION_ID = "keyword_economics"
SECTION_HEADING = "Keyword economics"
DISPLAY_NAME = "Keyword Economics"

DEFAULT_OS_URL = "https://os.hz.egbe.dev"
RUNTIME_REL = Path(_artifact_path("egbe-docs/research/market/work")) / SECTION_ID
EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/keyword-economics.json"))
REPORT_REL = Path(_artifact_path("egbe-docs/research/market/full-report.md"))

# Hard ceiling on metered upstream tasks per run (cache hits are free). The
# most expensive task is $0.09, so this bounds one run at ~$2.25 worst case;
# a normal run uses 8-16 tasks (~$0.50).
MAX_TASKS_PER_RUN = 25

# DataForSEO rate-limits google_ads live endpoints at 12 requests/minute and
# answers bursts with task status 50301 "Too many requests". Failed tasks are
# not billed, so a bounded backoff retry is safe; the window clears within a
# minute.
# Also used for structured internal errors explicitly confirmed as unpaid.
PROVIDER_MAX_RETRIES = 3
PROVIDER_BACKOFF_SECONDS = (20.0, 40.0, 60.0)
MAX_ERROR_RESPONSE_BYTES = 64 * 1024

MAX_SEED_KEYWORDS = 20
MAX_SEED_DOMAINS = 10
SERP_HEADS = 8
SERP_DEPTH = 20
CONFIRM_COMPETITORS = 4
RANKED_KEYWORDS_LIMIT = 200
BUDGET_SIM_KEYWORDS = 1000
TOP_TABLE_ROWS = 20

# Keywords containing one of these tokens carry commercial/search-to-buy
# intent and get priority in head selection and the report tables.
INTENT_TOKENS = {
    "software", "tool", "tools", "app", "apps", "platform", "service",
    "services", "pricing", "price", "cost", "best", "top", "alternative",
    "alternatives", "vs", "generator", "builder", "maker", "for", "buy",
    "online", "ai",
}

# Queries carrying these tokens signal free/education intent: real demand,
# but poor targets for PAID acquisition simulation, and their ad-free SERPs
# are partially self-explanatory.
FREE_EDU_TOKENS = {
    "free", "teacher", "teachers", "teaching", "classroom", "student",
    "students", "school", "kids",
}

# Lexical evidence, not a verdict that the query fits a particular offer.
# Google Ads compares these signals with the actual product and campaign goal.
VENDOR_TERMS = {"agency", "agencies", "consultant", "consultants", "consulting", "company", "companies", "services", "service", "hire"}
TOOL_TERMS = {"tool", "tools", "checker", "tracker", "software", "platform", "app", "apps"}
INFORMATION_TERMS = {"what", "how", "why", "meaning", "definition", "guide", "tutorial"}
JOB_TERMS = {"job", "jobs", "career", "careers", "salary", "salaries", "hiring"}

# SERP domains that are platforms/media, not product competitors.
NOISE_DOMAINS = {
    "google.com", "youtube.com", "reddit.com", "facebook.com",
    "instagram.com", "wikipedia.org", "amazon.com", "pinterest.com",
    "linkedin.com", "twitter.com", "x.com", "tiktok.com", "quora.com",
    "medium.com", "etsy.com", "ebay.com", "apple.com", "microsoft.com",
    "yelp.com", "github.com", "canva.com", "adobe.com",
}

# Function words never anchor topicality: a competitor keyword sharing ONLY
# one of these with the seed market (e.g. "from", "list", "and") must not
# merge into the demand pool. Found live: "best flavor wings from wingstop"
# merged into a meal-planning market via "from".
FUNCTION_TOKENS = {
    "the", "and", "from", "with", "your", "our", "you", "what", "when",
    "where", "how", "why", "this", "that", "near", "name", "list", "get",
    "make", "made", "does", "can", "will", "are", "was", "has", "have",
    "free", "new", "without", "using", "use",
}

# Review/listing directories: strong demand evidence, but not competitors.
DIRECTORY_DOMAINS = {
    "g2.com", "capterra.com", "getapp.com", "softwareadvice.com",
    "trustpilot.com", "producthunt.com", "sourceforge.net", "slashdot.org",
    "alternativeto.net", "trustradius.com",
}


class KeywordEconomicsError(RuntimeError):
    """Terminal runner failure; runtime state is preserved for resume."""


class DataForSeoError(KeywordEconomicsError):
    """Structured provider failure preserved through the OS tools envelope."""

    def __init__(self, operation: str, http_status: int, detail: dict[str, Any]):
        self.http_status = http_status
        self.detail = detail
        super().__init__(
            f"OS tools/dataforseo/{operation} failed: HTTP {http_status} "
            f"{detail.get('error')} status={detail.get('status_code')} "
            f"task={detail.get('task_id') or 'unknown'}: "
            f"{str(detail.get('message') or '')[:500]}"
        )


def _is_rate_limited(exc: Exception) -> bool:
    if isinstance(exc, DataForSeoError):
        return exc.detail.get("status_code") == 50301
    text = str(exc)
    return "50301" in text or "Too many requests" in text


def _is_unpaid_internal_error(exc: Exception) -> bool:
    if not isinstance(exc, DataForSeoError):
        return False
    detail = exc.detail
    return (
        exc.http_status == 503
        and detail.get("error") == "dataforseo_upstream_internal_error"
        and detail.get("status_code") == 50000
        and detail.get("retryable") is True
        and all(type(detail.get(key)) in (int, float) and detail[key] == 0
                for key in ("cost", "task_cost"))
    )


def _is_bid_rejection(exc: Exception) -> bool:
    if isinstance(exc, DataForSeoError):
        if (exc.http_status != 400 or exc.detail.get("error") != "dataforseo_task_error"
                or exc.detail.get("status_code") != 40501):
            return False
        message = str(exc.detail.get("message") or "")
    else:
        # Compatibility with older OS gateways, which stringify the error.
        message = str(exc)
        if not all(marker in message for marker in ("HTTP 400", "dataforseo_task_error", "40501")):
            return False
    return bool(re.search(r"\binvalid field\s*:\s*[\"'`]?bid[\"'`]?(?:[.!\s]|$)", message, re.I))


# ── bundled-script loading (same pattern as the other section runners) ─────

def _load_script(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise KeywordEconomicsError(f"cannot load bundled script {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


# ── OS tools client with response cache and task budget ───────────────────

@dataclass
class ToolsClient:
    os_url: str
    api_key: str
    cache_dir: Path
    max_tasks: int = MAX_TASKS_PER_RUN
    tasks_spent: int = 0
    estimated_cost_usd: float = 0.0
    cache_hits: int = 0
    request: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None
    sleep: Callable[[float], None] | None = None
    _ledger_entries: set[Path] = field(default_factory=set, init=False, repr=False)

    def _http(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.os_url.rstrip('/')}/tools/dataforseo/{operation}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            for _name, _value in _connection_headers(req.full_url).items():
                req.add_unredirected_header(_name, _value)
            with urllib.request.urlopen(req, timeout=180) as resp:
                envelope = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_ERROR_RESPONSE_BYTES + 1)
            detail = raw.decode("utf-8", errors="replace")
            if len(raw) <= MAX_ERROR_RESPONSE_BYTES:
                try:
                    envelope = json.loads(detail)
                except ValueError:
                    envelope = None
                error = envelope.get("data") if isinstance(envelope, dict) else None
                if isinstance(error, dict) and str(error.get("error", "")).startswith("dataforseo_"):
                    raise DataForSeoError(operation, exc.code, error) from exc
            raise KeywordEconomicsError(
                f"OS tools/dataforseo/{operation} failed: HTTP {exc.code} {detail[:500]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise KeywordEconomicsError(
                f"OS tools/dataforseo/{operation} unreachable: {exc.reason}"
            ) from exc
        data = envelope.get("data")
        if envelope.get("code") not in (None, 200) or not isinstance(data, dict):
            raise KeywordEconomicsError(
                f"OS tools/dataforseo/{operation} returned no data: "
                f"{str(envelope)[:300]}"
            )
        return data

    def call(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        key_raw = json.dumps({"op": operation, "payload": payload}, sort_keys=True)
        digest = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        if cache_file.is_file():
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            self.cache_hits += 1
            self._ledger_entries.add(cache_file)
            return cached["response"]

        if self.tasks_spent >= self.max_tasks:
            raise KeywordEconomicsError(
                f"task budget exhausted ({self.max_tasks} metered calls); "
                "narrow the seeds or raise --max-tasks"
            )
        transport = self.request or self._http
        attempt = 0
        while True:
            try:
                response = transport(operation, payload)
                break
            except KeywordEconomicsError as exc:
                if not (_is_rate_limited(exc) or _is_unpaid_internal_error(exc)):
                    raise
                if attempt >= PROVIDER_MAX_RETRIES:
                    raise KeywordEconomicsError(
                        f"{exc}; automatic retries exhausted ({attempt}). "
                        "Research is incomplete. Successful responses remain cached; "
                        "preserve the workspace and report the blocked section. "
                        "A later recovery attempt can rerun the same command from cache."
                    ) from exc
                delay = PROVIDER_BACKOFF_SECONDS[attempt]
                print(
                    f"{DISPLAY_NAME}: {exc}; retry {attempt + 1}/{PROVIDER_MAX_RETRIES} "
                    f"in {delay:g}s with unchanged parameters.", file=sys.stderr,
                )
                (self.sleep or time.sleep)(delay)
                attempt += 1
        self.tasks_spent += 1
        cost = response.get("cost")
        if isinstance(cost, (int, float)):
            self.estimated_cost_usd += float(cost)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        _write_atomic(cache_file,
            json.dumps(
                {
                    "operation": operation,
                    "payload": payload,
                    "response": response,
                    "retrieved_on": date.today().isoformat(),
                }
            ),
        )
        self._ledger_entries.add(cache_file)
        return response

    def ledger_totals(self) -> dict[str, Any]:
        """Durable spend provenance for calls used by this pipeline execution.

        Every used cache entry is one metered upstream call that actually
        happened, regardless of which attempt made it. A cache-only replay
        therefore reports the ORIGINAL spend without pulling unrelated entries
        from older runs with different inputs into the current section totals.
        """
        tasks = 0
        cost = 0.0
        dates: list[str] = []
        if self.cache_dir.is_dir():
            for entry_path in sorted(self._ledger_entries):
                try:
                    entry = json.loads(entry_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                tasks += 1
                entry_cost = (entry.get("response") or {}).get("cost")
                if isinstance(entry_cost, (int, float)):
                    cost += float(entry_cost)
                if isinstance(entry.get("retrieved_on"), str):
                    dates.append(entry["retrieved_on"])
        return {
            "tasks_spent": tasks,
            "estimated_cost_usd": round(cost, 4),
            "first_retrieved_on": min(dates) if dates else date.today().isoformat(),
            "last_retrieved_on": max(dates) if dates else date.today().isoformat(),
        }


# ── deterministic pipeline steps ───────────────────────────────────────────

def parse_terms(raw: str, cap: int) -> list[str]:
    """Split a comma/semicolon/newline separated list, dedupe, cap."""
    seen: dict[str, None] = {}
    for part in re.split(r"[,;\n]", raw or ""):
        term = " ".join(part.split()).strip().lower()
        if term and term not in seen:
            seen[term] = None
    return list(seen)[:cap]


# Second-level labels that make a public suffix under a country code
# (example.co.uk, example.com.au, example.edu.in, example.or.kr): the
# registrable name is the label before them.
SECOND_LEVEL_SUFFIX_LABELS = frozenset({
    "co", "com", "org", "net", "gov", "ac", "edu", "or", "ne", "go", "gob", "nic", "ltd", "plc", "sch", "res", "gen",
    "ind", "firm", "nom", "mil", "int", "biz", "info",
})
# Course and creator hosts that give every seller a subdomain: the subdomain
# is the seller (dair-ai.thinkific.com is DAIR.AI's school, not Thinkific's),
# so it is a domain of its own. The host's service subdomains still mean the host.
HOSTED_SELLER_PLATFORMS = frozenset({
    "thinkific.com", "teachable.com", "kajabi.com", "mykajabi.com", "podia.com", "learnworlds.com", "gumroad.com",
    "substack.com", "systeme.io", "circle.so", "mn.co", "github.io", "notion.site", "webflow.io", "framer.website",
    "carrd.co", "wixsite.com", "wordpress.com", "blogspot.com", "hashnode.dev",
})
HOST_SERVICE_LABELS = frozenset({"www", "app", "help", "support", "docs", "status", "api", "community", "blog"})


def registrable_domain(value: str) -> str:
    """Normalize a URL or hostname to its registrable domain (best effort);
    a seller's subdomain on a course or creator host is kept whole."""
    host = (value or "").strip().lower()
    if "//" in host:
        host = urlparse(host).hostname or ""
    host = host.split("/", 1)[0].removeprefix("www.")
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return ".".join(parts)
    # Collapse deep subdomains; keep two-level public suffixes intact.
    keep = 3 if parts[-2] in SECOND_LEVEL_SUFFIX_LABELS and len(parts[-1]) == 2 else 2
    if ".".join(parts[-keep:]) in HOSTED_SELLER_PLATFORMS and len(parts) > keep and parts[-keep - 1] not in HOST_SERVICE_LABELS:
        keep += 1
    return ".".join(parts[-keep:])


def hosted_seller(domain: str) -> bool:
    """A seller's own subdomain on a course or creator host."""
    return domain.count(".") >= 2 and domain.split(".", 1)[1] in HOSTED_SELLER_PLATFORMS


def has_intent(keyword: str) -> bool:
    return any(token in keyword.split() for token in INTENT_TOKENS)


def content_tokens(keywords: list[str]) -> set[str]:
    """Category-bearing tokens of the seed market: everything except generic
    intent modifiers and short function words. These anchor the topical filter
    that keeps competitor footprints from contaminating the demand model."""
    tokens: set[str] = set()
    for keyword in keywords:
        for token in keyword.split():
            if len(token) >= 3 and token not in INTENT_TOKENS and token not in FUNCTION_TOKENS:
                tokens.add(token)
    return tokens


def brand_token(domain: str) -> str:
    """clickup.com -> clickup — the brand token used to keep competitor-brand
    queries out of the budget simulation."""
    stem = registrable_domain(domain).split(".")[0]
    return re.sub(r"[^a-z0-9]", "", stem)


def has_free_edu_intent(keyword: str) -> bool:
    """Note/flag marker: free OR education audience terms."""
    return any(token in FREE_EDU_TOKENS for token in keyword.split())


def has_free_intent(keyword: str) -> bool:
    """Simulation gate: ONLY explicit 'free' intent — education/audience
    terms mark verticals ('school management software' is commercial) and
    must not exclude a query from paid simulation."""
    return "free" in keyword.split()


def query_intent_signal(keyword: str) -> str:
    """Return only a defensible lexical signal; unknown is a valid outcome."""
    tokens = set(keyword.lower().split())
    if tokens & JOB_TERMS:
        return "job_seeking"
    if "free" in tokens:
        return "free_intent"
    if tokens & INFORMATION_TERMS:
        return "informational"
    if tokens & VENDOR_TERMS:
        return "vendor_seeking"
    if tokens & TOOL_TERMS:
        return "tool_seeking"
    return "unknown"


def _tokens_match(a: str, b: str) -> bool:
    """Exact match, or simple plural-suffix equality (+s/+es) for stems of
    6+ characters: 'whiteboards' matches 'whiteboard', but 'canvas' does NOT
    match 'canva' (short stems collide — the live canva/canvas adversarial
    pair). Deliberately NOT a stemmer: irregular morphology ('categories')
    is out of scope and documented."""
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) < 6:
        return False
    return longer == shorter + "s" or longer == shorter + "es"


def is_topical(keyword: str, market_tokens: set[str]) -> bool:
    """A keyword joins the market pool only when it shares at least one
    category-bearing token (plural-tolerant) with the seed anchors. 'ai
    furniture staging' shares 'staging'; a broad competitor's 'best crm app'
    shares nothing and stays footprint-only evidence."""
    for token in keyword.split():
        if len(token) < 3 or token in INTENT_TOKENS or token in FUNCTION_TOKENS:
            continue
        if any(_tokens_match(token, anchor) for anchor in market_tokens):
            return True
    return False


def build_foreign_brand_veto(
    rejected_keywords: list[str], seed_tokens: set[str]
) -> set[str]:
    """Bounded foreign-brand detector using POSITION as brand evidence, not
    bare frequency: brands lead their phrases ('canva ai', 'canva ai
    generator'), while recurring category nouns trail ('brainstorm
    template', 'meeting template' must not veto 'template'). A non-seed
    content token LEADING 2+ drift-rejected phrases is treated as a foreign
    brand; keywords that slipped past the first pass on a weak shared token
    ('canva ai text' via seed token 'text') are removed only when the veto
    token leads them too."""
    counts: dict[str, int] = {}
    for keyword in rejected_keywords:
        tokens = keyword.split()
        if not tokens:
            continue
        first = tokens[0]
        if len(first) < 3 or first in INTENT_TOKENS or first in FUNCTION_TOKENS:
            continue
        if any(_tokens_match(first, anchor) for anchor in seed_tokens):
            continue
        counts[first] = counts.get(first, 0) + 1
    return {token for token, count in counts.items() if count >= 2}


def normalize_keyword_row(raw: dict[str, Any], source: str) -> dict[str, Any] | None:
    keyword = " ".join(str(raw.get("keyword") or "").split()).lower()
    if not keyword:
        return None
    return {
        "type": "keyword",
        "keyword": keyword,
        "intent_signal": query_intent_signal(keyword),
        "free_edu_intent": has_free_edu_intent(keyword),
        "search_volume": raw.get("search_volume"),
        "cpc": raw.get("cpc"),
        "cpc_low": raw.get("low_top_of_page_bid"),
        "cpc_high": raw.get("high_top_of_page_bid"),
        "competition": raw.get("competition"),
        "sources": [source],
        "tier": "A",
    }


def normalize_ranked_row(item: dict[str, Any], domain: str) -> dict[str, Any] | None:
    keyword_data = item.get("keyword_data") or {}
    info = keyword_data.get("keyword_info") or {}
    serp_item = (item.get("ranked_serp_element") or {}).get("serp_item") or {}
    row = normalize_keyword_row(
        {
            "keyword": keyword_data.get("keyword"),
            "search_volume": info.get("search_volume"),
            "cpc": info.get("cpc"),
            "low_top_of_page_bid": info.get("low_top_of_page_bid"),
            "high_top_of_page_bid": info.get("high_top_of_page_bid"),
            "competition": info.get("competition_level") or info.get("competition"),
        },
        source=f"ranked_keywords:{domain}",
    )
    if row is None:
        return None
    if serp_item.get("type") == "paid":
        # The competitor BUYS this query — the strongest channel evidence here.
        row["paid_by"] = [domain]
    return row


def merge_keyword_rows(*row_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for rows in row_lists:
        for row in rows:
            if row is None:
                continue
            existing = merged.get(row["keyword"])
            if existing is None:
                merged[row["keyword"]] = {**row, "sources": list(row["sources"])}
                continue
            for source in row["sources"]:
                if source not in existing["sources"]:
                    existing["sources"].append(source)
            for paid_domain in row.get("paid_by", []):
                existing.setdefault("paid_by", [])
                if paid_domain not in existing["paid_by"]:
                    existing["paid_by"].append(paid_domain)
            for key in ("search_volume", "cpc", "cpc_low", "cpc_high", "competition"):
                if existing.get(key) is None and row.get(key) is not None:
                    existing[key] = row[key]
    return list(merged.values())


def rank_keywords(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]):
        volume = row.get("search_volume") or 0
        return (1 if has_intent(row["keyword"]) else 0, volume)

    return sorted(
        (r for r in rows if (r.get("search_volume") or 0) > 0),
        key=sort_key,
        reverse=True,
    )


def pick_serp_heads(ranked: list[dict[str, Any]], count: int = SERP_HEADS) -> list[str]:
    heads: list[str] = []
    seen_first_tokens: set[str] = set()
    # First pass prefers lexical diversity so eight heads don't all probe the
    # same phrase family; second pass fills remaining slots by rank.
    for row in ranked:
        first = row["keyword"].split()[0]
        if first not in seen_first_tokens:
            heads.append(row["keyword"])
            seen_first_tokens.add(first)
        if len(heads) >= count:
            return heads
    for row in ranked:
        if row["keyword"] not in heads:
            heads.append(row["keyword"])
        if len(heads) >= count:
            break
    return heads


def extract_serp_observation(keyword: str, serp_result: list[dict[str, Any]]) -> dict[str, Any]:
    entry = (serp_result or [{}])[0]
    available = bool(serp_result) and isinstance(entry.get("items"), list)
    items = entry.get("items") or []
    paid: list[str] = []
    organic: list[str] = []
    for item in items:
        domain = registrable_domain(item.get("domain") or item.get("url") or "")
        if not domain:
            continue
        if item.get("type") == "paid" and domain not in paid:
            paid.append(domain)
        elif item.get("type") == "organic" and len(organic) < 10 and domain not in organic:
            organic.append(domain)
    return {
        "type": "serp_observation",
        "keyword": keyword,
        "intent_signal": query_intent_signal(keyword),
        "paid_advertisers": paid,
        "ads_count": len(paid) if available else None,
        "response_status": "available" if available else "unavailable",
        "organic_top": organic,
        "se_results_count": entry.get("se_results_count"),
        "tier": "A",
    }


def classify_domain(domain: str) -> str:
    if domain in NOISE_DOMAINS:
        return "noise"
    if domain in DIRECTORY_DOMAINS:
        return "directory"
    return "candidate"


def tally_competitors(
    observations: list[dict[str, Any]],
    seed_domains: list[str],
    keyword_volumes: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Score competitors by VOLUME-WEIGHTED SERP presence: one appearance on
    a 165k/mo head outweighs several appearances on tiny queries (observed
    live: education micro-sites outranked figma.com on raw appearance
    counts). Weight = log10(head volume), ads-block presence x3."""
    volumes = keyword_volumes or {}
    tally: dict[str, dict[str, Any]] = {}

    def bump(domain: str, via: str, weight: float) -> None:
        kind = classify_domain(domain)
        if kind == "noise":
            return
        row = tally.setdefault(
            domain,
            {
                "type": "competitor_domain",
                "domain": domain,
                "kind": kind,
                "found_via": [],
                "serp_paid_appearances": 0,
                "serp_organic_appearances": 0,
                "serp_queries": [],
                "score": 0,
                "tier": "A",
            },
        )
        if via not in row["found_via"]:
            row["found_via"].append(via)
        if via == "serp_ads":
            row["serp_paid_appearances"] += 1
        elif via == "serp_organic":
            row["serp_organic_appearances"] += 1
        row["score"] = round(row["score"] + weight, 2)

    def head_weight(keyword: str) -> float:
        return math.log10(max(volumes.get(keyword, 0), 10))

    for domain in seed_domains:
        normalized = registrable_domain(domain)
        if normalized:
            bump(normalized, "seed", 2.0)
    for obs in observations:
        weight = head_weight(obs["keyword"])
        for domain in obs["paid_advertisers"]:
            # A paid appearance is evidence, not yet category confirmation.
            bump(domain, "serp_ads", 3.0 * weight)
            row = tally.get(domain)
            if row is not None:
                row["serp_queries"].append({"keyword": obs["keyword"], "via": "serp_ads"})
        for domain in obs["organic_top"]:
            bump(domain, "serp_organic", weight)
            row = tally.get(domain)
            if row is not None:
                row["serp_queries"].append({"keyword": obs["keyword"], "via": "serp_organic"})

    return sorted(tally.values(), key=lambda r: r["score"], reverse=True)


def confirmed_competitors(
    candidates: list[dict[str, Any]],
    seed_domains: list[str] | None = None,
    count: int = CONFIRM_COMPETITORS,
    seed_keywords: list[str] | None = None,
) -> list[str]:
    """Founder-named seed domains are reserved FIRST — volume-weighted
    discovery must not evict an explicitly supplied competitor from the
    footprint pulls."""
    ordered: list[str] = []
    for domain in seed_domains or []:
        normalized = registrable_domain(domain)
        if normalized and normalized not in ordered and classify_domain(normalized) == "candidate":
            ordered.append(normalized)
    for row in candidates:
        if len(ordered) >= count:
            break
        if (
            row["kind"] == "candidate"
            and row["domain"] not in ordered
            and (seed_keywords is None or competitor_category_evidence(row, seed_keywords))
        ):
            ordered.append(row["domain"])
    return ordered[:count]


def competitor_category_evidence(row: dict[str, Any], seeds: list[str]) -> bool:
    """Require evidence beyond an ambiguous one-word category SERP.

    One paid appearance on a category-qualified query, or two independent
    organic appearances on such queries, is enough. Generic query modifiers
    such as 'agency' are not category context. 'AI' can complete a two-token
    context only alongside a real seed anchor (e.g. 'AI visibility').
    """
    anchors = content_tokens(seeds) - VENDOR_TERMS
    relevant: dict[str, set[str]] = {}
    for match in row.get("serp_queries") or []:
        keyword = str(match.get("keyword") or "")
        tokens = set(keyword.split())
        category = tokens & anchors
        contextual = len(category) >= 2 or ("ai" in tokens and bool(category))
        if contextual:
            relevant.setdefault(keyword, set()).add(str(match.get("via") or ""))
    return any("serp_ads" in via for via in relevant.values()) or len(relevant) >= 2


def median(values: list[float]) -> float | None:
    cleaned = sorted(v for v in values if isinstance(v, (int, float)) and v > 0)
    if not cleaned:
        return None
    middle = len(cleaned) // 2
    if len(cleaned) % 2:
        return float(cleaned[middle])
    return (cleaned[middle - 1] + cleaned[middle]) / 2.0


def build_budget_rows(
    sim_keywords: list[str],
    bid: float,
    ad_traffic_result: list[dict[str, Any]],
    test_budget_usd: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in ad_traffic_result or []:
        clicks = raw.get("clicks")
        cost = raw.get("cost")
        keyword = raw.get("keyword")
        scale = None
        clicks_for_budget = None
        if test_budget_usd is not None and isinstance(clicks, (int, float)) and isinstance(cost, (int, float)) and cost > 0:
            scale = test_budget_usd / cost
            clicks_for_budget = round(clicks * min(scale, 1.0), 1) if scale < 1 else round(clicks, 1)
        elif test_budget_usd is not None and clicks == 0 and cost == 0:
            scale = 1.0
            clicks_for_budget = 0
        rows.append(
            {
                "type": "budget_simulation",
                "keyword": keyword or "(all simulated keywords)",
                "simulated_keywords": sim_keywords if keyword is None else None,
                "bid": bid,
                "match": raw.get("match"),
                "average_cpc": raw.get("average_cpc"),
                "monthly_clicks_at_bid": clicks,
                "monthly_cost_at_bid": cost,
                "test_budget_usd": test_budget_usd,
                "est_clicks_within_test_budget": clicks_for_budget,
                "budget_covers_full_month": scale >= 1 if scale is not None else None,
                "tier": "A",
            }
        )
    return rows


# ── rendering ──────────────────────────────────────────────────────────────

def _fmt(value: Any, money: bool = False) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"${value:,.2f}" if money else f"{value:,.1f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"${value:,}" if money else f"{value:,}"
    return str(value)


def render_section(
    *,
    locale: dict[str, Any],
    seeds: list[str],
    seed_rows_alive: int,
    keyword_rows: list[dict[str, Any]],
    footprint_rows: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    competitor_rows: list[dict[str, Any]],
    confirmed: list[str],
    budget_rows: list[dict[str, Any]],
    overlap_domains: list[str],
    totals: dict[str, Any],
    test_budget_usd: float,
    retrieved_on: str,
    expansion_rejected_count: int = 0,
    expansion_veto_rejected_count: int = 0,
    simulation_omitted_reason: str | None = None,
    simulation_coverage: dict | None = None,
) -> str:
    ranked = rank_keywords(keyword_rows)
    top_rows = ranked[:TOP_TABLE_ROWS]
    lines: list[str] = []
    add = lines.append

    add(
        f"Primary auction data retrieved {retrieved_on} via DataForSEO "
        f"(Google Ads / Labs / SERP endpoints) for location code "
        f"{locale['location_code']}, language `{locale['language_code']}`. "
        f"Seeds supplied by the workflow: {len(seeds)}; seeds surviving "
        f"volume validation: {seed_rows_alive}. All numbers below are "
        "measured or engine-estimated market data, not model knowledge."
    )
    add("")
    add("### Demand and click cost by keyword")
    add("")
    add("| Keyword | Monthly searches | CPC (avg) | Top-of-page bid low–high | Competition | Paid by competitor | Sources |")
    add("| --- | ---: | ---: | ---: | --- | --- | --- |")
    for row in top_rows:
        bid_range = (
            f"{_fmt(row.get('cpc_low'), money=True)}–{_fmt(row.get('cpc_high'), money=True)}"
            if row.get("cpc_low") is not None or row.get("cpc_high") is not None
            else "—"
        )
        add(
            f"| {row['keyword']} | {_fmt(row.get('search_volume'))} | "
            f"{_fmt(row.get('cpc'), money=True)} | {bid_range} | "
            f"{_fmt(row.get('competition'))} | "
            f"{', '.join(row.get('paid_by', [])) or '—'} | "
            f"{', '.join(sorted({s.split(':', 1)[0] for s in row['sources']}))} |"
        )
    add("")
    add(f"{len(ranked)} keywords with non-zero volume collected in total; the table shows the top {len(top_rows)} by commercial intent and volume. The full set is in the machine-readable evidence file.")
    add("")

    add("### Who occupies the results page")
    add("")
    add("| Head keyword | Advertisers in ads block | Organic top domains |")
    add("| --- | --- | --- |")
    for obs in observations:
        add(
            f"| {obs['keyword']} | "
            f"{', '.join(obs['paid_advertisers']) or ('unavailable' if obs.get('response_status') == 'unavailable' else 'none observed')} | "
            f"{', '.join(obs['organic_top'][:5])} |"
        )
    add("")
    zero_ads = [o["keyword"] for o in observations if o["ads_count"] == 0]
    if zero_ads:
        add(
            "No ads block was observed on: "
            + ", ".join(f"`{k}`" for k in zero_ads)
            + ". This sampled observation does not establish that nobody advertises "
            "or pays for these queries; competitor spending remains unproven here."
        )
        free_heads = [k for k in zero_ads if has_free_edu_intent(k)]
        if free_heads:
            add(
                "Note: "
                + ", ".join(f"`{k}`" for k in free_heads)
                + " carry free/education intent markers — an empty ads block "
                "there is partially self-explanatory."
            )
        add("")

    add("### Competitors on the demand surface")
    add("")
    add("| Domain | Kind | Found via | SERP paid | SERP organic |")
    add("| --- | --- | --- | ---: | ---: |")
    for row in competitor_rows[:12]:
        add(
            f"| {row['domain']} | {row['kind']} | {', '.join(row['found_via'])} | "
            f"{row['serp_paid_appearances']} | {row['serp_organic_appearances']} |"
        )
    add("")
    if confirmed:
        add(
            "Confirmed product competitors (keyword footprints pulled): "
            + ", ".join(f"`{d}`" for d in confirmed)
            + "."
        )
    if overlap_domains:
        add(
            "Additional keyword-overlap neighbors (Labs `competitors_domain`, "
            "not re-crawled): " + ", ".join(f"`{d}`" for d in overlap_domains[:10]) + "."
        )
    add("")

    if footprint_rows:
        add("### Competitor keyword footprints (separate evidence)")
        add("")
        add(
            "Footprints are competitor-scoped evidence: only rows sharing a "
            "category token with the seed market are merged into the demand "
            "table above; everything else stays here and in the evidence "
            "file, and none of it feeds the budget simulation."
        )
        add("")
        add("| Domain | Keyword | Monthly searches | CPC (avg) | Competitor pays for it | In market pool |")
        add("| --- | --- | ---: | ---: | --- | --- |")
        for domain in confirmed:
            domain_rows = sorted(
                (r for r in footprint_rows if r.get("domain") == domain),
                key=lambda r: r.get("search_volume") or 0,
                reverse=True,
            )[:5]
            for row in domain_rows:
                add(
                    f"| {domain} | {row['keyword']} | "
                    f"{_fmt(row.get('search_volume'))} | "
                    f"{_fmt(row.get('cpc'), money=True)} | "
                    f"{'yes' if row.get('paid_by') else 'no'} | "
                    f"{'yes' if row.get('topical') else 'no'} |"
                )
        add("")

    add("### Candidate-set forecast" + (f" — ${test_budget_usd:,.0f} test-budget arithmetic" if test_budget_usd is not None else " — provider monthly estimates; no test budget supplied"))
    add("")
    if simulation_coverage:
        c = simulation_coverage
        add(f"Scenario: {c['kind']}; {c['submitted_count']}/{c['requested_count']} requested keywords, "
            f"{len(c['excluded'])} excluded, {len(c['omitted_keywords'])} omitted by cap; "
            f"match `{c['match']}`, bid assumption ${c['bid']:g}, period `{c['forecast_period']}`.")
        add(c["limitations"])
        add("")
    if simulation_omitted_reason:
        add(
            f"Simulation omitted: {simulation_omitted_reason}. Rather than "
            "simulating on excluded queries, this run reports the limitation "
            "explicitly — revise seeds toward commercial category phrasing "
            "and re-run if a paid-search estimate is needed."
        )
        add("")
    if budget_rows:
        add("| Simulated keyword | Bid | Est. avg CPC | Est. clicks/month at bid | Est. cost/month | Est. clicks within test budget |")
        add("| --- | ---: | ---: | ---: | ---: | ---: |")
    elif not simulation_omitted_reason:
        add("Forecast unavailable: the provider returned no usable result for this keyword set. "
            "Expected clicks and cost are unknown, not zero. No budget feasibility estimate is available.")
    for row in budget_rows:
        add(
            f"| {row['keyword']} | {_fmt(row.get('bid'), money=True)} | "
            f"{_fmt(row.get('average_cpc'), money=True)} | "
            f"{_fmt(row.get('monthly_clicks_at_bid'))} | "
            f"{_fmt(row.get('monthly_cost_at_bid'), money=True)} | "
            f"{_fmt(row.get('est_clicks_within_test_budget'))} |"
        )
    add("")
    if budget_rows:
        add(
            "Estimates come from Google's ad-traffic forecast at the stated bid "
            "(`ad_traffic_by_keywords`); clicks within the test budget are a "
            "linear pro-rata of the monthly forecast and ignore learning-phase "
            "effects. They anchor feasibility math; they do not guarantee auction "
            "outcomes."
        )
    if simulation_coverage and simulation_coverage["kind"] == "explicit_scenario":
        add("This forecast uses the caller's explicit scenario, not an automatically selected seed pool.")
    else:
        add("Simulation keywords are drawn only from the eligible seed and expansion pool — "
            "never from competitor footprints, competitor-brand queries, or free/education-intent queries.")
    add("")

    add("### Method and coverage")
    add("")
    add(
        f"- Metered DataForSEO tasks recorded for this section: "
        f"{totals['tasks_spent']} (≈ ${totals['estimated_cost_usd']:.2f}), "
        "accumulated across attempts; cached replays add no new spend."
    )
    add(
        f"- Coverage caps: {SERP_HEADS} SERP heads at depth {SERP_DEPTH}, "
        f"{CONFIRM_COMPETITORS} competitor keyword footprints at "
        f"{RANKED_KEYWORDS_LIMIT} keywords each, {BUDGET_SIM_KEYWORDS} "
        "budget-simulation keywords."
    )
    if expansion_rejected_count or expansion_veto_rejected_count:
        add(
            f"- Expansion drift guard rejected {expansion_rejected_count} "
            "Google-suggested keywords sharing no seed content token, plus "
            f"{expansion_veto_rejected_count} more via the leading-brand "
            "veto (both groups listed with their reasons in the evidence "
            "file) — foreign-brand drift like 'ai canvas' -> 'canva ai' "
            "stays out of the demand model."
        )
    add(
        "- Not covered here: non-Google channels, organic difficulty, "
        "seasonality time series, and any interpretation of which "
        "segment/offer/channel combination to pursue (downstream concern)."
    )
    add("")
    add("### Sources")
    add("")
    add(
        f"- DataForSEO Google Ads endpoints (`search_volume`, "
        f"`keywords_for_keywords`, `ad_traffic_by_keywords`), Labs "
        f"(`ranked_keywords`, `competitors_domain`), and SERP advanced — "
        f"retrieved {retrieved_on} via the OS tools gateway; evidence rows in "
        f"`{EVIDENCE_REL.as_posix()}`."
    )
    return "\n".join(lines).strip() + "\n"


# ── orchestration ──────────────────────────────────────────────────────────

@dataclass
class RunInputs:
    seeds: list[str]
    seed_domains: list[str]
    location_code: int
    language_code: str
    test_budget_usd: float
    scenario: dict | None = None


def run_pipeline(client: ToolsClient, inputs: RunInputs) -> dict[str, Any]:
    locale = {"location_code": inputs.location_code, "language_code": inputs.language_code}
    forecast = _load_script("keyword-forecast.py", "pmr_keyword_forecast")
    scenario = forecast.validate_scenario(inputs.scenario, locale) if inputs.scenario is not None else None
    if type(inputs.location_code) is not int or inputs.location_code <= 0 or not re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2})?", inputs.language_code):
        raise KeywordEconomicsError("location-code and normalized language-code are invalid")
    if inputs.test_budget_usd is not None and (not math.isfinite(inputs.test_budget_usd) or inputs.test_budget_usd <= 0):
        raise KeywordEconomicsError("test-budget-usd must be finite and positive")

    seed_volume = client.call("search-volume", {"keywords": inputs.seeds, **locale})
    expansion = client.call("keywords-for-keywords", {"keywords": inputs.seeds, **locale})

    seed_rows = [normalize_keyword_row(r, "search_volume") for r in seed_volume.get("result") or []]
    expansion_rows = [normalize_keyword_row(r, "keywords_for_keywords") for r in expansion.get("result") or []]
    # Google's expansion drifts into foreign brands ("ai canvas" -> "canva
    # ai", observed live at 135k volume): an expansion keyword joins the
    # market pool only when it shares a seed content token. Seeds themselves
    # are the declared market and always stay.
    seed_anchor_tokens = content_tokens(inputs.seeds)
    kept_expansion: list[dict[str, Any]] = []
    rejected_expansion: list[dict[str, Any]] = []
    for row in expansion_rows:
        if row is None:
            continue
        if is_topical(row["keyword"], seed_anchor_tokens):
            kept_expansion.append(row)
        else:
            rejected_expansion.append(row)
    # Second pass: tokens dominating the rejected set are foreign brands;
    # keywords that slipped through on a single shared seed token ('canva ai
    # text' via 'text') get vetoed too.
    veto_tokens = build_foreign_brand_veto(
        [row["keyword"] for row in rejected_expansion], seed_anchor_tokens
    )
    veto_rejected: list[dict[str, Any]] = []
    if veto_tokens:
        still_kept: list[dict[str, Any]] = []
        for row in kept_expansion:
            tokens = row["keyword"].split()
            if tokens and tokens[0] in veto_tokens:
                veto_rejected.append(row)
            else:
                still_kept.append(row)
        kept_expansion = still_kept
    rejected_expansion.sort(key=lambda r: r.get("search_volume") or 0, reverse=True)
    veto_rejected.sort(key=lambda r: r.get("search_volume") or 0, reverse=True)
    expansion_rejected_rows = [
        {
            "type": "expansion_rejected",
            "keyword": row["keyword"],
            "intent_signal": row["intent_signal"],
            "search_volume": row.get("search_volume"),
            "reason": "no_seed_token_overlap",
            "tier": "C",
        }
        for row in rejected_expansion[:20]
    ] + [
        {
            "type": "expansion_rejected",
            "keyword": row["keyword"],
            "intent_signal": row["intent_signal"],
            "search_volume": row.get("search_volume"),
            "reason": "foreign_brand_veto",
            "tier": "C",
        }
        for row in veto_rejected[:20]
    ]
    # The MARKET pool: seeds + the anchored part of Google's expansion. This
    # pool alone defines the demand model; competitor footprints may only
    # annotate it (topical intersection) and never replace it.
    market_pool = merge_keyword_rows(
        [r for r in seed_rows if r],
        kept_expansion,
    )
    base_ranked = rank_keywords(market_pool)
    if not base_ranked:
        raise KeywordEconomicsError(
            "no seed or expanded keyword has non-zero search volume; the seed "
            "list does not map to measurable demand — revise seeds in the "
            "workflow and re-run"
        )
    seed_rows_alive = sum(
        1
        for r in seed_rows
        if r and (r.get("search_volume") or 0) > 0
    )
    # Topicality anchors come from the SEEDS ONLY (same set that gates the
    # expansion above).
    market_tokens = seed_anchor_tokens

    heads = pick_serp_heads(base_ranked)
    observations = [
        extract_serp_observation(
            head,
            client.call("serp", {"keyword": head, "depth": SERP_DEPTH, **locale}).get("result") or [],
        )
        for head in heads
    ]

    keyword_volumes = {
        row["keyword"]: int(row.get("search_volume") or 0) for row in base_ranked
    }
    competitor_rows = tally_competitors(
        observations, inputs.seed_domains, keyword_volumes
    )
    confirmed = confirmed_competitors(
        competitor_rows, inputs.seed_domains, seed_keywords=inputs.seeds
    )
    named_domains = {registrable_domain(domain) for domain in inputs.seed_domains}
    for row in competitor_rows:
        row["confirmation_status"] = (
            "founder_seed" if row["domain"] in named_domains and row["domain"] in confirmed
            else "confirmed" if row["domain"] in confirmed
            else "unconfirmed"
        )
        if row["confirmation_status"] == "unconfirmed" and row["kind"] == "candidate":
            row["confirmation_reason"] = "insufficient_category_relevant_serp_overlap"

    # Competitor footprints stay a SEPARATE evidence set; only rows sharing a
    # category-bearing token with the market join the pool (annotated), so a
    # broad competitor cannot inject an unrelated high-volume query into the
    # demand tables (review finding #2).
    footprint_rows: list[dict[str, Any]] = []
    topical_rows: list[dict[str, Any]] = []
    for domain in confirmed:
        response = client.call(
            "ranked-keywords",
            {"target": domain, "limit": RANKED_KEYWORDS_LIMIT, **locale},
        )
        entry = (response.get("result") or [{}])[0]
        for item in entry.get("items") or []:
            row = normalize_ranked_row(item, domain)
            if row is None:
                continue
            topical = is_topical(row["keyword"], market_tokens) and not (
                set(row["keyword"].split()) & veto_tokens
            )
            footprint_rows.append(
                {
                    **row,
                    "type": "competitor_keyword",
                    "domain": domain,
                    "topical": topical,
                }
            )
            if topical:
                topical_rows.append({**row, "from_competitor_footprint": True})

    market_pool = merge_keyword_rows(market_pool, topical_rows)
    ranked_pool = rank_keywords(market_pool)

    overlap_domains: list[str] = []
    if confirmed:
        overlap = client.call(
            "competitors-domain",
            {"target": confirmed[0], "limit": 20, **locale},
        )
        entry = (overlap.get("result") or [{}])[0]
        for item in entry.get("items") or []:
            domain = registrable_domain(item.get("domain") or "")
            if domain and classify_domain(domain) == "candidate" and domain not in confirmed:
                overlap_domains.append(domain)

    # Budget-simulation keywords come STRICTLY from the seed+expansion pool —
    # never from competitor footprints, even topical ones. They also estimate
    # CATEGORY economics, so competitor-brand queries (bidding on 'miro …' is
    # a separate tactic) and explicit free-intent queries are excluded; when
    # nothing trustworthy remains the simulation is OMITTED rather than
    # silently bypassing the filters.
    competitor_brands = {
        brand_token(d)
        for d in confirmed + [registrable_domain(x) for x in inputs.seed_domains]
    }
    competitor_brands.discard("")
    # A brand token that is itself category vocabulary (whiteboard.chat ->
    # 'whiteboard') must not exclude core category queries.
    competitor_brands = {
        brand
        for brand in competitor_brands
        if not any(_tokens_match(brand, anchor) for anchor in seed_anchor_tokens)
    }
    _BRAND_SUFFIXES = ("com", "io", "app", "ai", "co", "net", "org")

    def _token_is_brand(token: str) -> bool:
        normalized = re.sub(r"[^a-z0-9]", "", token)
        for brand in competitor_brands:
            if normalized == brand:
                return True
            # 'monday.com' -> 'mondaycom' must match brand 'monday'.
            if normalized.startswith(brand) and normalized[len(brand):] in _BRAND_SUFFIXES:
                return True
        return False

    def sim_eligible(row: dict[str, Any]) -> bool:
        if any(_token_is_brand(token) for token in row["keyword"].split()):
            return False
        if has_free_intent(row["keyword"]):
            return False
        return True

    eligible = [r for r in base_ranked if sim_eligible(r)]
    sim_rows = eligible[:BUDGET_SIM_KEYWORDS]
    requested_keywords = scenario["keywords"] if scenario else [r["keyword"] for r in eligible]
    sim_keywords = requested_keywords[:BUDGET_SIM_KEYWORDS]
    simulation_omitted_reason = None
    if not sim_keywords:
        simulation_omitted_reason = (
            "no trustworthy simulation keywords remained after excluding "
            "competitor-brand and free-intent queries"
        )
    bid = median([r.get("cpc_high") for r in sim_rows]) or median(
        [r.get("cpc") for r in sim_rows]
    ) or 1.0
    bid = round(float(bid), 2)
    bid = scenario["bid"] if scenario else min(bid, 500)
    match = scenario["match"] if scenario else "exact"
    # Live evidence (2026-08-18) shows the endpoint accepts fractional bids
    # despite the docs declaring an integer; keep the precise bid but fall
    # back to whole dollars once if the upstream ever enforces the documented
    # contract (review finding #3).
    bid_normalized_to_int = False
    budget_rows: list[dict[str, Any]] = []
    if sim_keywords:
        try:
            ad_traffic = client.call(
                "ad-traffic",
                {"keywords": sim_keywords, "bid": bid, "match": match, **locale},
            )
        except KeywordEconomicsError as exc:
            if scenario or not _is_bid_rejection(exc):
                raise
            bid = float(math.ceil(bid)) or 1.0
            bid_normalized_to_int = True
            ad_traffic = client.call(
                "ad-traffic",
                {"keywords": sim_keywords, "bid": bid, "match": match, **locale},
            )
        budget_rows = build_budget_rows(
            sim_keywords, bid, ad_traffic.get("result") or [], inputs.test_budget_usd
        )
    simulation_coverage = forecast.coverage(
        requested=requested_keywords, submitted=sim_keywords, locale=locale, bid=bid, match=match, scenario=scenario,
        excluded=[] if scenario else [{"keyword": r["keyword"], "reason": "competitor_brand_or_free_education_intent"}
                                     for r in base_ranked if not sim_eligible(r)],
    )
    simulation_coverage["response_rows"] = len(budget_rows)
    simulation_coverage["response_status"] = "available" if budget_rows else "unavailable"

    for domain in overlap_domains:
        competitor_rows.append(
            {
                "type": "competitor_domain",
                "domain": domain,
                "kind": "candidate",
                "found_via": ["keyword_overlap"],
                "serp_paid_appearances": 0,
                "serp_organic_appearances": 0,
                "score": 0,
                "tier": "B",
            }
        )

    # Durable spend provenance comes from the response ledger, not this
    # attempt's counters — a cache-only replay reports the original metered
    # spend and renders byte-identical artifacts (review finding #1).
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
        "locale": locale,
        "simulation": simulation_coverage,
        "request_hashes": sorted(p.stem for p in client._ledger_entries),
        "inputs": {
            "seed_keywords": inputs.seeds,
            "seed_domains": inputs.seed_domains,
            "test_budget_usd": inputs.test_budget_usd,
            "bid_normalized_to_int": bid_normalized_to_int,
            "scenario_sha256": simulation_coverage["scenario_sha256"],
            "simulation_omitted_reason": simulation_omitted_reason,
            "expansion_rejected_count": len(rejected_expansion),
            "expansion_veto_rejected_count": len(veto_rejected),
        },
        "rows": (
            ranked_pool
            + footprint_rows
            + expansion_rejected_rows
            + observations
            + competitor_rows
            + budget_rows
        ),
        "totals": {
            "tasks_spent": totals["tasks_spent"],
            "estimated_cost_usd": totals["estimated_cost_usd"],
        },
    }

    section_markdown = render_section(
        locale=locale,
        seeds=inputs.seeds,
        seed_rows_alive=seed_rows_alive,
        keyword_rows=market_pool,
        footprint_rows=footprint_rows,
        observations=observations,
        competitor_rows=competitor_rows,
        confirmed=confirmed,
        budget_rows=budget_rows,
        overlap_domains=overlap_domains,
        totals=totals,
        test_budget_usd=inputs.test_budget_usd,
        retrieved_on=retrieved_on,
        expansion_rejected_count=len(rejected_expansion),
        expansion_veto_rejected_count=len(veto_rejected),
        simulation_omitted_reason=simulation_omitted_reason,
        simulation_coverage=simulation_coverage,
    )
    return {
        "evidence": evidence,
        "section_markdown": section_markdown,
        "totals": totals,
        "attempt": {
            "tasks_spent": client.tasks_spent,
            "cache_hits": client.cache_hits,
        },
    }


def _write_atomic(path: Path, content: str) -> None:
    _load_script("research-artifact-io.py", "pmr_artifact_io").write_atomic(path, content)


def run(workspace: Path, args: argparse.Namespace) -> dict[str, Any]:
    workspace = workspace.resolve()
    runtime = workspace / RUNTIME_REL
    cache_dir = runtime / "cache"
    runtime.mkdir(parents=True, exist_ok=True)

    api_key = (os.environ.get("OS_API_KEY") or "").strip()
    if not api_key:
        raise KeywordEconomicsError("OS_API_KEY is required")
    os_url = (os.environ.get("OS_URL") or DEFAULT_OS_URL).strip() or DEFAULT_OS_URL

    seeds = parse_terms(args.seed_keywords, MAX_SEED_KEYWORDS)
    if not seeds:
        raise KeywordEconomicsError(
            "at least one seed keyword is required for the assigned search scope"
        )
    seed_domains = parse_terms(args.seed_domains or "", MAX_SEED_DOMAINS)

    inputs = RunInputs(
        seeds=seeds,
        seed_domains=seed_domains,
        location_code=args.location_code,
        language_code=args.language_code,
        test_budget_usd=args.test_budget_usd,
        scenario=json.loads(Path(args.scenario).read_text()) if getattr(args, "scenario", None) else None,
    )
    client = ToolsClient(
        os_url=os_url,
        api_key=api_key,
        cache_dir=cache_dir,
        max_tasks=args.max_tasks,
    )

    io = _load_script("research-artifact-io.py", "pmr_artifact_io")
    publication = _load_script("keyword-locale-publication.py", "pmr_keyword_publication")
    upsert = _load_script("upsert-markdown-section.py", "pmr_upsert_markdown_section")
    persist = _load_script("persist-research-report.py", "pmr_persist_research_report")
    key = publication.locale_key(inputs.location_code, inputs.language_code)
    io.bind_context(workspace, "keyword_economics", context_file=getattr(args, "context_file", None))
    context_hash = io.context_binding(workspace, "keyword_economics")
    with io.file_lock(runtime / "locales" / key / ".run.lock", timeout=1):
        publication.begin(workspace, key, context_hash, io)
        try:
            outcome = run_pipeline(client, inputs)
            return publication.publish(workspace, key, context_hash, outcome, io, upsert, persist)
        except Exception:
            publication.failed(workspace, key, context_hash, io)
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-file", type=Path, help="Explicit additional context for this measurement.")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--seed-keywords",
        required=True,
        help="Comma/semicolon-separated candidate search phrases (3-20).",
    )
    parser.add_argument(
        "--seed-domains",
        default="",
        help="Comma-separated competitor domains supplied for this research.",
    )
    parser.add_argument("--location-code", type=int, default=2840)
    parser.add_argument("--language-code", default="en")
    parser.add_argument("--test-budget-usd", type=float, default=None, help="Optional task-specific budget for conditional arithmetic; no budget is chosen by this runner.")
    parser.add_argument("--max-tasks", type=int, default=MAX_TASKS_PER_RUN)
    parser.add_argument("--scenario", type=Path, help="Explicit homogeneous forecast scenario JSON; validated before paid calls")
    args = parser.parse_args()

    try:
        state = run(args.workspace, args)
    except (KeywordEconomicsError, ValueError, OSError, RuntimeError) as exc:
        print(f"{DISPLAY_NAME}: {exc}", file=sys.stderr)
        return 1
    print(
        f"{DISPLAY_NAME}: {state['status']} — {state['tasks_spent']} metered tasks "
        f"(≈ ${state['estimated_cost_usd']:.2f}), evidence at {state['evidence_path']}, "
        f"publication {state['publication_mode']} {state['report_commit_sha'][:12]}"
    )
    return 0 if state["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
