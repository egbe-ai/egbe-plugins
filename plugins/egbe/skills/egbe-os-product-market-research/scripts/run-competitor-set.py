#!/usr/bin/env python3
"""Collect a bounded competitor comparison sample for caller-scoped research.

Discovery records offer-query results, related-domain reports, supplied profiles,
comparison roles and ad observations. Collection caps and sample order are not
business-priority rules. The caller owns comparison criteria and interpretation;
source identity, profile URLs, aliases, cache and receipts remain validated.

Caching, spend provenance, budgets and retries mirror the other measured
runners: every provider response is cached, starts are journaled before the
call, replays add no spend.
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
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

SCHEMA_VERSION = 1
SECTION_ID = "competitor_set"
SECTION_HEADING = "Competitor set"
DISPLAY_NAME = "Competitor Set"

DEFAULT_OS_URL = "https://os.hz.egbe.dev"
RUNTIME_REL = Path(_artifact_path("egbe-docs/research/market/work")) / SECTION_ID
EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/competitors.json"))
REPORT_REL = Path(_artifact_path("egbe-docs/research/market/full-report.md"))
INTAKE_REL = Path(_artifact_path("egbe-docs/research/market/intake.json"))
CANDIDATES_FILENAME = "candidates.json"
LISTICLES_FILENAME = "listicles.json"
PROFILES_FILENAME = "profiles.json"
DECISIONS_FILENAME = "decisions.json"
REVIEW_FILENAME = "review.json"
DECISIONS_SCHEMA_VERSION = 2

MAX_COMPETITORS = 10
MAX_NAMED_DOMAINS = 10
MAX_PAGE_DOMAINS = 10
MAX_KEYWORD_DOMAINS = 20
MAX_CATEGORY_PHRASES = 3
MAX_BRAND_QUERIES = 3
MAX_CANDIDATES = 150
# Bounds of the agent's enrichment work (profiles per round, domains it may
# add from its own reading, listicle pages it reads).
# At most 40 profiles in all: the agent's reading, not the pool, is the cost.
MAX_PROFILES_ROUND1 = 25
MAX_PROFILES_ROUND2 = 10
MAX_AGENT_ADDITIONS = 5
MAX_LISTICLES_TO_READ = 12
LISTICLES_PER_QUERY = 5
MAX_LISTICLE_ENTRIES = 60
ROUND2_SEEDS = 3
MAX_AD_CHECKS = 25
AD_CHECK_MONTHS = 6
AD_CHECK_EXTRA_MARKETS = 2
KEYWORD_ADS_ROWS = 50
# SpyFu's keyword ad history reaches back years; only an advertiser seen on a
# phrase within this window counts as buying traffic on it now.
KEYWORD_ADS_RECENT_DAYS = 365
LISTICLES_PER_SITE = 2
COMPETITORS_DOMAIN_LIMIT = 20
SPYFU_COMPETITORS = 20
# One result page: deeper SERP tasks are assembled from several pages and
# DataForSEO rejects the whole task when one page cannot be retrieved
# (status 40106, "partial results"), observed live on 2026-10-01.
SERP_DEPTH = 10
BRAVE_COUNT = 20
META_ADS_LIMIT = 25
GTM_CONTAINERS_PER_SITE = 2
FETCH_MAX_BYTES = 1_000_000
FETCH_TIMEOUT_SECONDS = 25.0
RETRY_DELAY_SECONDS = 20.0
EXCLUDED_ROWS_RENDERED = 25
PROFILED_ROWS_RENDERED = 40
_TASK_ERROR_RE = re.compile(r"HTTP 400 .*dataforseo_task_error", re.DOTALL)

MAX_DATAFORSEO_TASKS_PER_ATTEMPT = 15
MAX_SEARCH_CALLS_PER_ATTEMPT = 12
MAX_SPYFU_CALLS_PER_ATTEMPT = 40
MAX_META_SEARCHES_PER_ATTEMPT = 25
MAX_FETCHES_PER_ATTEMPT = 60

DEFAULT_LOCATION_CODE = 2840
DEFAULT_LANGUAGE_CODE = "en"
DEFAULT_MARKET = "US"
DEFAULT_EU_COUNTRY = "DE"
# DataForSEO location codes for the markets an offer card usually names.
LOCATION_CODES = {
    "US": 2840, "UK": 2826, "CA": 2124, "AU": 2036, "NZ": 2554, "IE": 2372, "DE": 2276, "FR": 2250,
    "ES": 2724, "IT": 2380, "NL": 2528, "SE": 2752, "CZ": 2203, "PL": 2616, "PT": 2620, "AT": 2040,
    "CH": 2756, "BE": 2056, "DK": 2208, "NO": 2578, "FI": 2246, "IN": 2356, "SG": 2702, "ZA": 2710,
    "BR": 2076, "MX": 2484,
}
# SpyFu research markets (SpyFu says UK, not GB).
SPYFU_MARKETS = frozenset({
    "AR", "AT", "AU", "BE", "BR", "CA", "CH", "DE", "DK", "ES", "FR", "IE", "IN", "IT", "JP", "MX",
    "NL", "NO", "NZ", "PL", "PT", "SE", "SG", "TR", "UA", "UK", "US", "ZA",
})
EU_COUNTRIES = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT",
    "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
})

DECISION_TIERS = ("direct", "indirect", "substitute", "excluded")
OFFER_MATCHES = ("same", "comparable", "different", "none")
RESOLUTIONS = ("accepted", "rejected")
MISSING_RESOLUTIONS = ("added", "rejected")
PROVENANCE_ORDER = ("operator_named", "product_page", "discovered", "keyword_economics", "agent_research")
AD_ORDER = {"ads_seen": 0, "pixels_only": 1, "unknown": 2, "none_detected": 3}
AD_LABELS = {"ads_seen": "ads seen", "pixels_only": "ad pixels only", "unknown": "ad check inconclusive", "none_detected": "no ads detected"}
GROUP_LABELS = {0: "direct", 1: "indirect", 2: "other scoped"}
# Tag channels from the Channel Footprint signature list that mean paid media.
AD_TAG_CHANNELS = frozenset({
    "meta_ads", "google_ads", "reddit_ads", "linkedin_ads", "tiktok_ads", "microsoft_ads", "x_ads",
    "pinterest_ads", "snap_ads", "quora_ads", "display_native",
})

# Signal strength: offer signals (ads and rankings on the offer's own search
# phrases, listicle mentions) outweigh relationship hits. It orders the
# profiling list and breaks ties; it never decides a tier, and naming a
# competitor (founder or product page) adds nothing.
SCORE_CATEGORY_PAID = 3.0
SCORE_KEYWORD_ADS = 2.0
SCORE_CATEGORY_ORGANIC = 2.0
SCORE_SECOND_ENGINE = 1.0
SCORE_BRAND_QUERY = 1.0
SCORE_LISTICLE = 1.0
SCORE_RELATIONSHIP = 1.0
SCORE_KEYWORD_ECONOMICS = 1.0
CAP_CATEGORY_PAID = 2
CAP_KEYWORD_ADS = 3
CAP_CATEGORY_ORGANIC = 3
CAP_SECOND_ENGINE = 3
CAP_BRAND_QUERY = 2
CAP_LISTICLE = 3
CAP_RELATIONSHIP = 4

_LISTICLE_RE = re.compile(r"\b(alternatives?|best|top \d+|vs\.?|comparison|compare)\b", re.IGNORECASE)
_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,251}\.[a-z]{2,24}$")
_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SEARCH_PAGE_KEYS = {"q", "query", "search", "keyword", "keywords", "term"}
PAGES_PER_CANDIDATE = 3


class CompetitorSetError(RuntimeError):
    """Terminal runner failure; runtime state is preserved for resume."""


class BudgetExhausted(CompetitorSetError):
    """A per-attempt call budget is spent; always propagates so a rerun
    resumes from the cache instead of publishing a partial search."""


def _load_script(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise CompetitorSetError(f"cannot load bundled script {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


# Cache entries are stored gzip-compressed; plain entries of older runs replay too.
IO = _load_script("research-artifact-io.py", "pmr_competitor_set_io")
_KEYWORD_ECONOMICS: ModuleType | None = None
_CHANNEL_FOOTPRINT: ModuleType | None = None


def _keyword_economics() -> ModuleType:
    """Domain normalization and the noise/directory lists live in the Keyword
    Economics runner; load them from there instead of copying the lists."""
    global _KEYWORD_ECONOMICS
    if _KEYWORD_ECONOMICS is None:
        _KEYWORD_ECONOMICS = _load_script("run-keyword-economics.py", "pmr_keyword_economics_for_competitor_set")
    return _KEYWORD_ECONOMICS


def _channel_footprint() -> ModuleType:
    """The ad-tag signatures, the SpyFu spend row and the Meta identity rules
    live in the Channel Footprint runner; the ad check reuses them."""
    global _CHANNEL_FOOTPRINT
    if _CHANNEL_FOOTPRINT is None:
        _CHANNEL_FOOTPRINT = _load_script("run-channel-footprint.py", "pmr_channel_footprint_for_competitor_set")
    return _CHANNEL_FOOTPRINT


def registrable_domain(value: str) -> str:
    return _keyword_economics().registrable_domain(value)


def classify_domain(domain: str) -> str:
    return _keyword_economics().classify_domain(domain)


def brand_token(domain: str) -> str:
    return _keyword_economics().brand_token(domain)


def hosted_seller(domain: str) -> bool:
    """A seller's own subdomain on a course or creator host (kept whole by
    the shared domain normalization)."""
    return _keyword_economics().hosted_seller(domain)


def _domain(value: Any) -> str:
    domain = registrable_domain(str(value or ""))
    return domain if domain and _DOMAIN_RE.match(domain) else ""


def _text(value: Any, cap: int = 240) -> str:
    text = " ".join(str(value if value is not None else "").split())
    return text if len(text) <= cap else text[: cap - 1] + "…"


def _url(value: Any) -> str:
    text = str(value or "").strip()
    return text if _URL_RE.match(text) and len(text) <= 800 else ""


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("not a non-negative number")
    return float(value)


def _money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:,.0f}"


# ── OS client: metered provider calls + free page fetches ───────────────────

@dataclass
class OsClient:
    os_url: str
    api_key: str
    cache_dir: Path
    max_dataforseo_tasks: int = MAX_DATAFORSEO_TASKS_PER_ATTEMPT
    max_search_calls: int = MAX_SEARCH_CALLS_PER_ATTEMPT
    max_spyfu_calls: int = MAX_SPYFU_CALLS_PER_ATTEMPT
    max_meta_searches: int = MAX_META_SEARCHES_PER_ATTEMPT
    max_fetches: int = MAX_FETCHES_PER_ATTEMPT
    dataforseo_tasks: int = 0
    search_calls: int = 0
    spyfu_calls: int = 0
    meta_searches: int = 0
    fetches: int = 0
    cache_hits: int = 0
    touched: set[str] = field(default_factory=set)
    request: Callable[..., dict[str, Any]] | None = None
    fetch: Callable[[str], tuple[int, str]] | None = None
    sleep: Callable[[float], None] | None = None

    def _http(self, path: str, payload: dict[str, Any], timeout: float, *, idempotency_key: str | None = None) -> dict[str, Any]:
        url = f"{self.os_url.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            for _name, _value in _connection_headers(req.full_url).items():
                req.add_unredirected_header(_name, _value)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                envelope = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise CompetitorSetError(f"OS {path} failed: HTTP {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise CompetitorSetError(f"OS {path} unreachable: {exc.reason}") from exc
        except (OSError, ValueError) as exc:
            raise CompetitorSetError(f"OS {path} failed in transit: {type(exc).__name__}: {str(exc)[:200]}") from exc
        data = envelope.get("data")
        if envelope.get("code") not in (None, 200) or not isinstance(data, dict):
            raise CompetitorSetError(f"OS {path} returned no data: {str(envelope)[:300]}")
        return data

    def _fetch_url(self, url: str) -> tuple[int, str]:
        """Plain GET of a public page; the status and a bounded body."""
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/javascript;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        try:
            for _name, _value in _connection_headers(req.full_url).items():
                req.add_unredirected_header(_name, _value)
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
                body = resp.read(FETCH_MAX_BYTES + 1)
                status = int(getattr(resp, "status", 200) or 200)
        except urllib.error.HTTPError as exc:
            return exc.code, ""
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise CompetitorSetError(f"fetch of {url} failed: {getattr(exc, 'reason', exc)}") from exc
        return status, body[:FETCH_MAX_BYTES].decode("utf-8", errors="replace")

    def _cache_read(self, cache_file: Path) -> dict[str, Any] | None:
        try:
            return IO.read_cache_entry(cache_file)
        except (OSError, ValueError, EOFError):
            IO.drop_cache_entry(cache_file)
            return None

    def _cache_write(self, cache_file: Path, entry: dict[str, Any]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        IO.write_cache_entry(cache_file, entry)

    def _journal_start(self, digest: str) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with (self.cache_dir / "starts.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{date.today().isoformat()} {digest}\n")

    def _prior_start_count(self, digest: str) -> int:
        try:
            lines = (self.cache_dir / "starts.log").read_text(encoding="utf-8").splitlines()
        except OSError:
            return 0
        return sum(1 for line in lines if line.endswith(f" {digest}"))

    def _metered(self, kind: str, path: str, payload: dict[str, Any], timeout: float, *, budget_attr: str, budget_max: int, label: str) -> tuple[dict[str, Any], str]:
        key_raw = json.dumps({"kind": kind, "path": path, "payload": payload}, sort_keys=True)
        digest = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        self.touched.add(digest)
        entry = self._cache_read(cache_file)
        if entry is not None:
            self.cache_hits += 1
            response = entry.get("response")
            return (response if isinstance(response, dict) else {}), entry.get("retrieved_on") or date.today().isoformat()

        transport = self.request or self._http
        attempts = 0
        wire_key = f"{digest}-{self._prior_start_count(digest)}"
        while True:
            # Metered starts count BEFORE the transport call (fail closed) and
            # are journaled durably: a failed start may still have billed.
            if getattr(self, budget_attr) >= budget_max:
                raise BudgetExhausted(
                    f"{label} budget exhausted ({budget_max} per attempt); rerun the same command to "
                    "continue from the cache"
                )
            setattr(self, budget_attr, getattr(self, budget_attr) + 1)
            self._journal_start(digest)
            try:
                response = transport(path, payload, timeout, idempotency_key=wire_key)
                break
            except CompetitorSetError as exc:
                if (kind == "dataforseo" and _TASK_ERROR_RE.search(str(exc))) or (
                    kind in ("spyfu", "meta") and re.search(r"HTTP 4(?:00|22)\b", str(exc))
                ):
                    # A rejected task (bad input, partial result pages, a
                    # market SpyFu does not cover) is a fact about this query,
                    # not a transient failure: cache it so replays stay
                    # byte-stable and never re-spend.
                    response = {"unavailable": str(exc)[:300]}
                    break
                if attempts >= 1 or not re.search(r"HTTP 5\d\d", str(exc)):
                    raise
                attempts += 1
                (self.sleep or time.sleep)(RETRY_DELAY_SECONDS)
        retrieved_on = date.today().isoformat()
        self._cache_write(cache_file, {"kind": kind, "path": path, "payload": payload, "response": response, "retrieved_on": retrieved_on})
        return (response if isinstance(response, dict) else {}), retrieved_on

    def dataforseo(self, operation: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        return self._metered(
            "dataforseo", f"/tools/dataforseo/{operation}", payload, 180.0,
            budget_attr="dataforseo_tasks", budget_max=self.max_dataforseo_tasks, label="DataForSEO task",
        )

    def brave(self, query: str, count: int, country: str) -> tuple[dict[str, Any], str]:
        return self._metered(
            "search", "/search/web/brave", {"query": query, "count": count, "country": country}, 60.0,
            budget_attr="search_calls", budget_max=self.max_search_calls, label="web search",
        )

    def spyfu(self, operation: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        return self._metered(
            "spyfu", f"/tools/spyfu/{operation}", payload, 90.0,
            budget_attr="spyfu_calls", budget_max=self.max_spyfu_calls, label="SpyFu lookup",
        )

    def meta_library(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        return self._metered(
            "meta", "/tools/meta-ad-library/search", payload, 90.0,
            budget_attr="meta_searches", budget_max=self.max_meta_searches, label="Meta Ad Library search",
        )

    def fetch_page(self, url: str) -> tuple[dict[str, Any], str]:
        """Free, cached GET of a public page. A timeout, a rate limit or a
        server error is reported for this attempt and never cached."""
        key_raw = json.dumps({"kind": "fetch", "url": url}, sort_keys=True)
        digest = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        self.touched.add(digest)
        entry = self._cache_read(cache_file)
        if entry is not None:
            self.cache_hits += 1
            cached = entry.get("response")
            return (cached if isinstance(cached, dict) else {}), entry.get("retrieved_on") or date.today().isoformat()
        if self.fetches >= self.max_fetches:
            raise BudgetExhausted(f"page fetch budget exhausted ({self.max_fetches} per attempt); rerun the same command to continue from the cache")
        self.fetches += 1
        transport = self.fetch or self._fetch_url
        retrieved_on = date.today().isoformat()
        try:
            status, body = transport(url)
        except CompetitorSetError as exc:
            return {"status": None, "body": "", "error": str(exc)[:200]}, retrieved_on
        if status == 429 or status >= 500:
            return {"status": status, "body": "", "error": f"HTTP {status}"}, retrieved_on
        response = {"status": status, "body": body}
        self._cache_write(cache_file, {"kind": "fetch", "url": url, "response": response, "retrieved_on": retrieved_on})
        return response, retrieved_on

    def ledger_totals(self) -> dict[str, Any]:
        """Durable provenance over entries THIS execution touched. A cached
        provider rejection is a journaled start, not a successful call: it
        never counts as evidence that the market was searched."""
        counts = {"dataforseo": 0, "search": 0, "spyfu": 0, "meta": 0, "fetch": 0}
        rejected = 0
        dates: list[str] = []
        if self.cache_dir.is_dir():
            for digest in sorted(self.touched):
                try:
                    entry = IO.read_cache_entry(self.cache_dir / f"{digest}.json")
                except (OSError, ValueError, EOFError):
                    continue
                if not isinstance(entry, dict):
                    continue
                kind = entry.get("kind")
                response = entry.get("response") if isinstance(entry.get("response"), dict) else {}
                if response.get("unavailable"):
                    rejected += 1
                elif kind in counts:
                    counts[kind] += 1
                if isinstance(entry.get("retrieved_on"), str):
                    dates.append(entry["retrieved_on"])
        today = date.today().isoformat()
        try:
            starts_recorded = sum(1 for line in (self.cache_dir / "starts.log").read_text(encoding="utf-8").splitlines() if line)
        except OSError:
            starts_recorded = 0
        provider_calls = counts["dataforseo"] + counts["search"] + counts["spyfu"] + counts["meta"]
        return {
            "dataforseo_calls": counts["dataforseo"],
            "search_calls": counts["search"],
            "spyfu_calls": counts["spyfu"],
            "meta_searches": counts["meta"],
            "page_fetches": counts["fetch"],
            "provider_calls": provider_calls,
            "rejected_calls": rejected,
            "provider_starts_recorded": starts_recorded,
            "first_retrieved_on": min(dates) if dates else today,
            "last_retrieved_on": max(dates) if dates else today,
        }


def _call_with_context(client: OsClient, subject: str, label: str, fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except BudgetExhausted:
        raise
    except CompetitorSetError as exc:
        raise CompetitorSetError(
            f"{label} for `{subject}` failed: {exc} — this attempt had already started "
            f"{client.dataforseo_tasks}/{client.max_dataforseo_tasks} DataForSEO task(s) and "
            f"{client.search_calls}/{client.max_search_calls} web search(es); see "
            "GET /me/limits?resource=dataforseo:tasks for remaining daily quota."
        ) from exc


# ── inputs: the offer card and the two kinds of named competitors ───────────

def parse_terms(raw: str, cap: int) -> list[str]:
    seen: list[str] = []
    for term in (raw or "").split(","):
        value = " ".join(term.split()).strip().lower()
        if value and value not in seen:
            seen.append(value)
    return seen[:cap]


def parse_domains(raw: Any, cap: int) -> list[str]:
    terms = raw if isinstance(raw, list) else str(raw or "").split(",")
    domains: list[str] = []
    for term in terms:
        domain = _domain(term)
        if domain and domain not in domains:
            domains.append(domain)
    return domains[:cap]


def normalize_market(value: Any) -> str:
    code = str(value or "").strip().upper()
    return "UK" if code == "GB" else code


def _brave_country(market: str) -> str:
    return "gb" if market == "UK" else market.lower()


def load_intake(path: Path) -> dict[str, Any] | None:
    """Read optional typed operation inputs; never infer labels from prose."""
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompetitorSetError(f"{path.name} is not valid JSON: {exc}") from exc
    return validate_intake(raw)


def validate_intake(raw: Any) -> dict[str, Any]:
    """Validate supplied fields, not the completeness of a research brief."""
    if not isinstance(raw, dict) or type(raw.get("schema_version")) is not int or raw["schema_version"] != 1:
        raise CompetitorSetError("intake must be an object with schema_version 1")

    def text(value, field):
        if value is not None and not isinstance(value, str):
            raise CompetitorSetError(f"intake {field} must be text or null")
        return " ".join((value or "").split()) or None

    def strings(value, field):
        if value is None:
            return []
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            raise CompetitorSetError(f"intake {field} must be a list of nonempty strings")
        return list(dict.fromkeys(item.strip() for item in value))

    def boolean(value, field):
        if value is not None and type(value) is not bool:
            raise CompetitorSetError(f"intake {field} must be boolean or null")
        return value

    def domains(value, field, cap):
        values = strings(value, field)
        if any(not _domain(item) for item in values):
            raise CompetitorSetError(f"intake {field} contains an invalid domain")
        normalized = parse_domains(values, len(values))
        if len(normalized) > cap:
            raise CompetitorSetError(f"intake {field} exceeds the collection limit of {cap}")
        return normalized

    def languages(value, field):
        values = list(dict.fromkeys(item.lower() for item in strings(value, field)))
        if len(values) > 40 or any(not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", item) for item in values):
            raise CompetitorSetError(f"intake {field} must contain explicit ISO/BCP-47 language codes")
        return values

    offer_raw = raw.get("offer")
    if offer_raw is not None and not isinstance(offer_raw, dict):
        raise CompetitorSetError("intake offer must be an object or null")
    offer_raw = offer_raw or {}
    offer: dict[str, Any] = {}
    for key in ("name", "job", "buyer", "offer_class", "comparable_classes", "duration", "price_text", "price_floor_basis", "basis"):
        value = text(offer_raw.get(key), f"offer.{key}")
        if value is not None:
            offer[key] = value
    offer["url"] = _url(offer_raw.get("url"))
    if offer_raw.get("url") and not offer["url"]:
        raise CompetitorSetError("intake offer.url must be an HTTP(S) address")
    for key in ("price_usd", "price_floor_usd"):
        value = offer_raw.get(key)
        if value is None:
            offer[key] = None
            continue
        try:
            offer[key] = _number(value)
        except ValueError:
            raise CompetitorSetError(f"intake offer.{key} must be a finite non-negative number or null") from None
    phrases = strings(offer_raw.get("category_phrases"), "offer.category_phrases")
    phrases = parse_terms(",".join(p.replace(",", " ") for p in phrases), len(phrases))
    if len(phrases) > MAX_CATEGORY_PHRASES:
        raise CompetitorSetError(f"intake offer.category_phrases exceeds the paid-query limit of {MAX_CATEGORY_PHRASES}")
    offer["category_phrases"] = phrases
    offer["confirmed_by_operator"] = boolean(offer_raw.get("confirmed_by_operator"), "offer.confirmed_by_operator")
    offer["inferred"] = boolean(offer_raw.get("inferred"), "offer.inferred")
    if offer["confirmed_by_operator"] and offer["inferred"]:
        raise CompetitorSetError("intake offer cannot be both confirmed and inferred")
    # Without a stated basis, neither a confirmation nor an inference is established.
    if not offer.get("basis"):
        offer["confirmed_by_operator"] = None
        offer["inferred"] = None
    markets: list[str] = []
    for market in strings(raw.get("markets"), "markets"):
        code = normalize_market(market)
        if not re.fullmatch(r"[A-Z]{2}", code) or code == "EU":
            raise CompetitorSetError("intake markets must contain explicit two-letter country codes")
        if code not in markets:
            markets.append(code)
    market_languages = raw.get("market_languages") or {}
    if not isinstance(market_languages, dict):
        raise CompetitorSetError("intake market_languages must be an object")
    by_market = {}
    for country, values in market_languages.items():
        code = normalize_market(country).replace("UK", "GB")
        if not re.fullmatch(r"[A-Z]{2}", code) or code == "EU" or code in by_market:
            raise CompetitorSetError("intake market_languages needs unique explicit country codes")
        by_market[code] = languages(values, f"market_languages.{country}")
        if not by_market[code]:
            raise CompetitorSetError(f"intake market_languages.{country} cannot be empty")
    named = domains(raw.get("operator_named"), "operator_named", MAX_NAMED_DOMAINS)
    asked = boolean(raw.get("operator_named_asked"), "operator_named_asked")
    if named and asked is False:
        raise CompetitorSetError("intake operator_named contradicts operator_named_asked=false")
    ltv = raw.get("ltv_usd")
    if ltv is not None:
        try:
            ltv = _number(ltv)
        except ValueError:
            raise CompetitorSetError("intake ltv_usd must be a finite non-negative number or null") from None
    ltv_provenance = raw.get("ltv_provenance")
    if ltv_provenance not in (None, "given", "estimated", "unknown"):
        raise CompetitorSetError("intake ltv_provenance must be given, estimated, unknown or null")
    if ltv is None and ltv_provenance in ("given", "estimated"):
        raise CompetitorSetError("intake ltv_provenance has no amount")
    ltv_basis = text(raw.get("ltv_basis"), "ltv_basis")
    if not ltv_basis:
        ltv_provenance = None
    return {
        "offer": offer,
        "operator_named": named,
        "operator_named_asked": asked,
        "page_mentioned": domains(raw.get("page_mentioned"), "page_mentioned", MAX_PAGE_DOMAINS),
        "product_domain": _domain(raw.get("product_domain")),
        "markets": markets,
        "languages": languages(raw.get("languages"), "languages"),
        "market_languages": by_market,
        "ltv_usd": ltv,
        "ltv_provenance": ltv_provenance,
        "ltv_basis": ltv_basis,
    }


def domains_from_keyword_evidence(workspace: Path, cap: int) -> list[str]:
    evidence = _load_script("research-evidence.py", "pmr_evidence_for_competitor_set")
    return evidence.keyword_inputs(workspace, consumer=SECTION_ID, row_type="competitor_domain", field="domain", cap=cap)


def category_queries(phrases: list[str]) -> list[str]:
    """Per category phrase: the phrase itself (who pays for and ranks on the
    offer's own search) and its "best" list (listicles)."""
    queries: list[str] = []
    for phrase in phrases:
        for query in (phrase, f"best {phrase}"):
            if query not in queries:
                queries.append(query)
    return queries


def brand_queries(named_domains: list[str]) -> list[str]:
    """Alternatives queries for competitors named by the founder only, with their
    own budget so they never displace the category queries."""
    queries: list[str] = []
    for domain in named_domains:
        brand = brand_token(domain)
        query = f"{brand} alternatives" if brand else ""
        if query and query not in queries:
            queries.append(query)
    return queries[:MAX_BRAND_QUERIES]


@dataclass
class RunInputs:
    named_domains: list[str]
    page_domains: list[str]
    keyword_domains: list[str]
    product_domain: str
    category_phrases: list[str]
    category_queries: list[str]
    brand_queries: list[str]
    offer: dict[str, Any]
    price_floor_usd: float | None
    markets: list[str]
    location_code: int
    language_code: str
    country: str
    spyfu_market: str
    eu_country: str
    intake_path: str | None
    intake_sha256: str | None
    input_annotations: dict[str, Any] = field(default_factory=dict)


def _arg(args: argparse.Namespace, name: str, default: Any) -> Any:
    value = getattr(args, name, None)
    return default if value is None else value


def resolve_inputs(workspace: Path, args: argparse.Namespace) -> RunInputs:
    intake_arg = str(_arg(args, "intake", "") or "")
    intake_path = Path(intake_arg) if intake_arg else workspace / INTAKE_REL
    if not intake_path.is_absolute():
        intake_path = workspace / intake_path
    if intake_arg and not intake_path.is_file():
        raise CompetitorSetError(f"the supplied intake file does not exist: {intake_arg}")
    intake = load_intake(intake_path) or {}
    offer = dict(intake.get("offer") or {})

    product_domain = _domain(_arg(args, "product_domain", "")) or intake.get("product_domain") or _domain(offer.get("url"))
    named_flag = str(_arg(args, "domains", "") or "")
    named = parse_domains(named_flag, MAX_NAMED_DOMAINS) if named_flag.strip() else list(intake.get("operator_named") or [])
    page_flag = str(_arg(args, "page_domains", "") or "")
    page = parse_domains(page_flag, MAX_PAGE_DOMAINS) if page_flag.strip() else list(intake.get("page_mentioned") or [])
    named = [d for d in named if d != product_domain][:MAX_NAMED_DOMAINS]
    page = [d for d in page if d != product_domain and d not in named][:MAX_PAGE_DOMAINS]
    keyword_domains = [d for d in domains_from_keyword_evidence(workspace, MAX_KEYWORD_DOMAINS) if d != product_domain and d not in named and d not in page]
    phrases_flag = str(_arg(args, "seed_keywords", "") or "")
    phrases = parse_terms(phrases_flag, MAX_CATEGORY_PHRASES) if phrases_flag.strip() else list(offer.get("category_phrases") or [])
    if not named and not phrases:
        raise CompetitorSetError(
            "no competitor domains or seed queries available: supply typed operation inputs "
            f"in {INTAKE_REL.as_posix()}, or pass --seed-keywords and/or --domains "
            "for the assigned comparison (see the workflow doc)"
        )
    floor_flag = _arg(args, "price_floor_usd", None)
    try:
        floor = _number(floor_flag) if floor_flag is not None else offer.get("price_floor_usd")
    except ValueError:
        raise CompetitorSetError("--price-floor-usd must be a non-negative number") from None
    offer["category_phrases"] = phrases

    markets = list(intake.get("markets") or [])
    country_flag = normalize_market(_arg(args, "country", ""))
    if country_flag:
        markets = [country_flag] + [m for m in markets if m != country_flag]
    if not markets:
        markets = [DEFAULT_MARKET]
    primary = markets[0]
    location_flag = _arg(args, "location_code", None)
    location_code = int(location_flag) if location_flag is not None else LOCATION_CODES.get(primary, DEFAULT_LOCATION_CODE)
    eu_flag = normalize_market(_arg(args, "eu_country", ""))
    eu_country = eu_flag or next((m for m in markets if m in EU_COUNTRIES), DEFAULT_EU_COUNTRY)
    intake_sha = hashlib.sha256(intake_path.read_bytes()).hexdigest() if intake_path.is_file() else None
    try:
        intake_rel = intake_path.relative_to(workspace).as_posix()
    except ValueError:
        intake_rel = intake_path.as_posix()
    return RunInputs(
        named_domains=named,
        page_domains=page,
        keyword_domains=keyword_domains,
        product_domain=product_domain,
        category_phrases=phrases,
        category_queries=category_queries(phrases),
        brand_queries=brand_queries(named),
        offer=offer,
        price_floor_usd=floor,
        markets=markets,
        location_code=location_code,
        language_code=str(_arg(args, "language_code", DEFAULT_LANGUAGE_CODE) or DEFAULT_LANGUAGE_CODE),
        country=_brave_country(primary),
        spyfu_market=primary,
        eu_country=eu_country,
        intake_path=intake_rel if intake_sha else None,
        intake_sha256=intake_sha,
        input_annotations={
            key: intake.get(key)
            for key in ("operator_named_asked", "languages", "market_languages", "ltv_usd", "ltv_provenance", "ltv_basis")
        } | {"operator_named_asked": True if named_flag.strip() else intake.get("operator_named_asked")},
    )


def validate_resume_inputs(workspace: Path, args: argparse.Namespace, inputs: RunInputs) -> None:
    """Check explicit changes without rebuilding the saved collection scope."""
    comparisons = {
        "domains": (inputs.named_domains, lambda value: [d for d in parse_domains(value, MAX_NAMED_DOMAINS) if d != inputs.product_domain]),
        "page_domains": (inputs.page_domains, lambda value: [d for d in parse_domains(value, MAX_PAGE_DOMAINS) if d != inputs.product_domain and d not in inputs.named_domains]),
        "product_domain": (inputs.product_domain, _domain),
        "seed_keywords": (inputs.category_phrases, lambda value: parse_terms(value, MAX_CATEGORY_PHRASES)),
        "price_floor_usd": (inputs.price_floor_usd, _number),
        "location_code": (inputs.location_code, int),
        "language_code": (inputs.language_code, str),
        "country": (inputs.markets[0], normalize_market),
        "eu_country": (inputs.eu_country, normalize_market),
    }
    for name, (expected, normalize) in comparisons.items():
        supplied = _arg(args, name, None)
        if supplied in (None, ""):
            continue
        try:
            matches = normalize(supplied) == expected
        except (TypeError, ValueError):
            matches = False
        if not matches:
            raise CompetitorSetError("competitor collection inputs changed; retain this study and use a new research ID")

    # Source applicability is separate from replay identity. Retained sources
    # must still match, but a clone need not carry the original source file.
    if inputs.intake_path:
        source = Path(inputs.intake_path)
        source = source if source.is_absolute() else workspace / source
        if source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() != inputs.intake_sha256:
            raise CompetitorSetError("competitor collection inputs changed: declared intake source changed; review saved evidence applicability")
    intake_arg = str(_arg(args, "intake", "") or "")
    if intake_arg:
        source = Path(intake_arg)
        source = source if source.is_absolute() else workspace / source
        if not source.is_file():
            raise CompetitorSetError(f"the supplied intake file does not exist: {intake_arg}")
        if hashlib.sha256(source.read_bytes()).hexdigest() != inputs.intake_sha256:
            raise CompetitorSetError("competitor collection inputs changed; retain this study and use a new research ID")


def bind_inputs(workspace: Path, args: argparse.Namespace) -> RunInputs:
    """Freeze the collection inputs before provider calls; output caps are not inputs."""
    path = workspace / RUNTIME_REL / "inputs.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    if saved is not None:
        if not isinstance(saved, dict) or saved.get("schema_version") != 1 or not isinstance(saved.get("inputs"), dict):
            raise CompetitorSetError("invalid saved competitor inputs; preserve the state and inspect it")
        digest = hashlib.sha256(json.dumps(saved["inputs"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if saved.get("sha256") != digest:
            raise CompetitorSetError("saved competitor inputs failed their integrity check")
        inputs = RunInputs(**saved["inputs"])
        validate_resume_inputs(workspace, args, inputs)
        return inputs
    inputs = resolve_inputs(workspace, args)
    payload = asdict(inputs)
    current = {"schema_version": 1, "inputs": payload,
               "sha256": hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
    _write_atomic(path, json.dumps(current, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return inputs


# ── candidates ──────────────────────────────────────────────────────────────

@dataclass
class Candidate:
    domain: str
    provenance: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    paid_queries: list[str] = field(default_factory=list)
    organic_queries: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    brand_pairs: list[str] = field(default_factory=list)
    keyword_ads_phrases: list[str] = field(default_factory=list)
    keyword_ads_rows: int = 0
    keyword_ads_last_seen: str | None = None
    listicle_pages: list[str] = field(default_factory=list)
    overlap_seeds: list[str] = field(default_factory=list)
    overlap_intersections: int = 0
    ppc_seeds: list[str] = field(default_factory=list)
    spyfu_common_keywords: int = 0
    listed_for: list[str] = field(default_factory=list)
    found_in: str | None = None
    round: int = 1
    aliases: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)

    def add_provenance(self, kind: str) -> None:
        if kind not in self.provenance:
            self.provenance.append(kind)

    def add_source(self, source: str) -> None:
        if source not in self.sources:
            self.sources.append(source)

    def listed(self, query: str) -> None:
        if query not in self.listed_for:
            self.listed_for.append(query)

    def seen_on(self, url: str) -> None:
        """The first pages that ranked or advertised: profiling starts there
        (a reseller's or host's page shows what the domain really sells)."""
        page = _url(url.split("#", 1)[0])
        if page and page not in self.pages and len(self.pages) < PAGES_PER_CANDIDATE:
            self.pages.append(page)

    @staticmethod
    def _add(values: list[str], value: str) -> None:
        if value not in values:
            values.append(value)

    @property
    def serp_paid_hits(self) -> int:
        return len(self.paid_queries)

    @property
    def serp_organic_hits(self) -> int:
        return len(self.organic_queries)

    @property
    def search_hits(self) -> int:
        return len(self.search_queries)

    @property
    def brand_hits(self) -> int:
        return len(self.brand_pairs)

    def offer_signals(self) -> int:
        """Distinct offer signals: one per query and engine, one per phrase a
        recent advertiser bought."""
        return self.serp_paid_hits + self.serp_organic_hits + self.search_hits + len(self.keyword_ads_phrases)

    def relationship_hits(self) -> int:
        return len(set(self.overlap_seeds)) + len(set(self.ppc_seeds))

    def round1_score(self) -> float:
        score = SCORE_CATEGORY_PAID * min(self.serp_paid_hits, CAP_CATEGORY_PAID)
        score += SCORE_KEYWORD_ADS * min(len(self.keyword_ads_phrases), CAP_KEYWORD_ADS)
        score += SCORE_CATEGORY_ORGANIC * min(self.serp_organic_hits, CAP_CATEGORY_ORGANIC)
        score += SCORE_SECOND_ENGINE * min(self.search_hits, CAP_SECOND_ENGINE)
        score += SCORE_BRAND_QUERY * min(self.brand_hits, CAP_BRAND_QUERY)
        score += SCORE_LISTICLE * min(len(self.listicle_pages), CAP_LISTICLE)
        if "keyword_economics" in self.provenance:
            score += SCORE_KEYWORD_ECONOMICS
        return round(score, 2)

    def score(self) -> float:
        return round(self.round1_score() + SCORE_RELATIONSHIP * min(self.relationship_hits(), CAP_RELATIONSHIP), 2)

    def signal_count(self) -> int:
        """Independent places the domain showed up: offer signals, listicle
        pages and alternatives-query hits."""
        return self.offer_signals() + len(self.listicle_pages) + self.brand_hits

    def offer_signal(self) -> bool:
        """Worth profiling: ranks or pays on Google for the offer's own
        search, or shows up in two independent places (two queries, two
        engines, an advertised phrase plus a listicle, two listicles); a
        single second-engine result, a single advertised phrase or a single
        listicle mention alone is a weak hit."""
        return bool(self.serp_paid_hits or self.serp_organic_hits or self.signal_count() >= 2)

    def absorb(self, alias: "Candidate") -> None:
        """Take over the discovery facts of another domain of the same
        company (idempotent: every list is a set)."""
        for name in ("provenance", "sources", "paid_queries", "organic_queries", "search_queries", "brand_pairs", "keyword_ads_phrases",
                     "listicle_pages", "overlap_seeds", "ppc_seeds", "listed_for"):
            values = getattr(self, name)
            for value in getattr(alias, name):
                Candidate._add(values, value)
        for page in alias.pages:
            self.seen_on(page)
        if alias.keyword_ads_last_seen and (self.keyword_ads_last_seen is None or alias.keyword_ads_last_seen > self.keyword_ads_last_seen):
            self.keyword_ads_last_seen = alias.keyword_ads_last_seen
        self.overlap_intersections = max(self.overlap_intersections, alias.overlap_intersections)
        self.spyfu_common_keywords = max(self.spyfu_common_keywords, alias.spyfu_common_keywords)
        Candidate._add(self.aliases, alias.domain)

    def round1_signal(self) -> bool:
        return bool(self.serp_paid_hits or self.keyword_ads_phrases or self.serp_organic_hits or self.search_hits
                    or self.brand_hits or self.listicle_pages or "keyword_economics" in self.provenance)

    def primary_provenance(self) -> str:
        return next((p for p in PROVENANCE_ORDER if p in self.provenance), "discovered")

    def ordered_provenance(self) -> list[str]:
        return [p for p in PROVENANCE_ORDER if p in self.provenance]

    def row(self) -> dict[str, Any]:
        return {
            "type": "candidate",
            "domain": self.domain,
            "provenance": self.ordered_provenance(),
            "round": self.round,
            "sources": list(self.sources),
            "source_count": len(self.sources),
            "serp_paid_hits": self.serp_paid_hits,
            "serp_organic_hits": self.serp_organic_hits,
            "search_hits": self.search_hits,
            "brand_hits": self.brand_hits,
            "keyword_ads_hits": len(self.keyword_ads_phrases),
            "listicle_pages": len(self.listicle_pages),
            "relationship_hits": self.relationship_hits(),
            "overlap_intersections": self.overlap_intersections,
            "spyfu_ppc_hits": len(set(self.ppc_seeds)),
            "spyfu_common_keywords": self.spyfu_common_keywords,
            "listed_for": list(self.listed_for[:8]),
            "pages": list(self.pages),
            "found_in": self.found_in,
            "aliases": list(self.aliases),
            "score": self.score(),
            "tier": "B",
        }


def _candidate(pool: dict[str, Candidate], domain: str, round_no: int = 1) -> Candidate:
    if domain not in pool:
        pool[domain] = Candidate(domain=domain, round=round_no)
    return pool[domain]


def _serp_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    result = response.get("result")
    entry = (result or [{}])[0] if isinstance(result, list) else {}
    items = entry.get("items") if isinstance(entry, dict) else None
    return [item for item in (items or []) if isinstance(item, dict)]


def _listicle(url: str, title: str) -> bool:
    return bool(_LISTICLE_RE.search(title or "")) or bool(_LISTICLE_RE.search(url or ""))


def _summary(round_no: int, query: str, kind: str, source: str, retrieved: int, found: int, listicles: list[str], unavailable: str | None = None) -> dict[str, Any]:
    row = {"type": "search_summary", "round": round_no, "query": query, "query_kind": kind, "source": source,
           "retrieved": retrieved, "candidates": found, "listicles": listicles, "tier": "A"}
    if unavailable:
        row["unavailable"] = unavailable[:200]
    return row


@dataclass
class Discovery:
    pool: dict[str, Candidate]
    directories: dict[str, list[str]]
    summaries: list[dict[str, Any]]


def run_round1(client: OsClient, inputs: RunInputs) -> Discovery:
    """Discovery from the offer: category phrases first, then the founder's
    brands; core Google results fail the attempt, SpyFu and Brave are best
    effort."""
    pool: dict[str, Candidate] = {}
    directories: dict[str, list[str]] = {}
    summaries: list[dict[str, Any]] = []
    for domain in inputs.named_domains:
        _candidate(pool, domain).add_provenance("operator_named")
    for domain in inputs.page_domains:
        _candidate(pool, domain).add_provenance("product_page")
    for domain in inputs.keyword_domains:
        candidate = _candidate(pool, domain)
        candidate.add_provenance("keyword_economics")
        candidate.add_source("keyword_economics")

    locale = {"location_code": inputs.location_code, "language_code": inputs.language_code}
    queries = [(q, "category") for q in inputs.category_queries] + [(q, "brand") for q in inputs.brand_queries]

    def admit(domain: str, query: str) -> str:
        """`candidate`, `skip` or `directory` for a result domain."""
        if not domain or domain == inputs.product_domain:
            return "skip"
        kind = classify_domain(domain)
        if kind == "noise":
            return "skip"
        if kind == "directory":
            directories.setdefault(domain, []).append(query)
            return "directory"
        return "candidate"

    for query, kind in queries:
        response, _ = _call_with_context(client, query, "DataForSEO serp", lambda q=query: client.dataforseo(
            "serp", {"keyword": q, "depth": SERP_DEPTH, **locale}
        ))
        if response.get("unavailable"):
            summaries.append(_summary(1, query, kind, "dataforseo_serp", 0, 0, [], str(response["unavailable"])))
            continue
        retrieved = found = 0
        listicles: list[str] = []
        for item in _serp_items(response):
            item_type = item.get("type")
            if item_type not in ("paid", "organic"):
                continue
            retrieved += 1
            url = str(item.get("url") or "")
            domain = _domain(item.get("domain") or url)
            verdict = admit(domain, query)
            if verdict == "skip":
                continue
            if verdict == "directory" or (item_type == "organic" and _listicle(url, str(item.get("title") or ""))):
                if url and len(listicles) < LISTICLES_PER_QUERY and url not in listicles:
                    listicles.append(url)
                continue
            candidate = _candidate(pool, domain)
            candidate.add_provenance("discovered")
            if kind == "category":
                if item_type == "paid":
                    candidate.add_source("serp_paid")
                    Candidate._add(candidate.paid_queries, query)
                else:
                    candidate.add_source("serp_organic")
                    Candidate._add(candidate.organic_queries, query)
            else:
                candidate.add_source("brand_query")
                Candidate._add(candidate.brand_pairs, f"serp:{query}")
            candidate.listed(query)
            candidate.seen_on(url)
            found += 1
        summaries.append(_summary(1, query, kind, "dataforseo_serp", retrieved, found, listicles))

    # SpyFu: the domains that bought Google ads on the offer's own phrases.
    for phrase in inputs.category_phrases if client.max_spyfu_calls > 0 else []:
        query = f"ads:{phrase}"
        try:
            response, retrieved_on = client.spyfu("keyword-ads", {"keyword": phrase, "country_code": inputs.spyfu_market, "max_rows": KEYWORD_ADS_ROWS})
        except BudgetExhausted:
            raise
        except CompetitorSetError as exc:
            summaries.append(_summary(1, query, "category", "spyfu_keyword_ads", 0, 0, [], str(exc)))
            continue
        if response.get("unavailable"):
            summaries.append(_summary(1, query, "category", "spyfu_keyword_ads", 0, 0, [], str(response["unavailable"])))
            continue
        # Recency is measured from the day the answer was retrieved, so a
        # cached replay classifies the same advertisers the same way.
        try:
            cutoff = (date.fromisoformat(retrieved_on) - timedelta(days=KEYWORD_ADS_RECENT_DAYS)).isoformat()
        except ValueError:
            cutoff = (date.today() - timedelta(days=KEYWORD_ADS_RECENT_DAYS)).isoformat()
        retrieved = 0
        advertisers: list[str] = []
        for item in response.get("rows") or []:
            if not isinstance(item, dict):
                continue
            retrieved += 1
            seen = str(item.get("seen_on") or "")[:10]
            if not _DATE_RE.match(seen) or seen < cutoff:
                continue  # an advertiser of years ago does not buy this traffic now
            urls = item.get("urls") if isinstance(item.get("urls"), list) else []
            domain = _domain(item.get("advertiser") or (urls[0] if urls else ""))
            if admit(domain, query) != "candidate":
                continue
            candidate = _candidate(pool, domain)
            candidate.add_provenance("discovered")
            candidate.add_source("spyfu_keyword_ads")
            Candidate._add(candidate.keyword_ads_phrases, phrase)
            candidate.keyword_ads_rows += 1
            if candidate.keyword_ads_last_seen is None or seen > candidate.keyword_ads_last_seen:
                candidate.keyword_ads_last_seen = seen
            candidate.listed(query)
            for ad_url in urls[:1]:
                candidate.seen_on(str(ad_url))
            Candidate._add(advertisers, domain)
        summaries.append(_summary(1, query, "category", "spyfu_keyword_ads", retrieved, len(advertisers), []))

    for query, kind in queries:
        try:
            response, _ = client.brave(query, BRAVE_COUNT, inputs.country)
        except BudgetExhausted:
            raise  # the attempt stops; the next invocation finishes the queries from the cache
        except CompetitorSetError as exc:
            # Best-effort second engine: an undeployed provider or a provider
            # rate limit is recorded, never a failed section.
            summaries.append(_summary(1, query, kind, "brave", 0, 0, [], str(exc)))
            continue
        retrieved = found = 0
        listicles = []
        for item in response.get("results") or []:
            if not isinstance(item, dict):
                continue
            retrieved += 1
            url = str(item.get("url") or "")
            domain = _domain(url)
            verdict = admit(domain, query)
            if verdict == "skip":
                continue
            if verdict == "directory" or _listicle(url, str(item.get("title") or "")):
                if url and len(listicles) < LISTICLES_PER_QUERY and url not in listicles:
                    listicles.append(url)
                continue
            candidate = _candidate(pool, domain)
            candidate.add_provenance("discovered")
            if kind == "category":
                candidate.add_source("brave")
                Candidate._add(candidate.search_queries, query)
            else:
                candidate.add_source("brand_query")
                Candidate._add(candidate.brand_pairs, f"brave:{query}")
            candidate.listed(query)
            candidate.seen_on(url)
            found += 1
        summaries.append(_summary(1, query, kind, "brave", retrieved, found, listicles))
    return Discovery(pool=pool, directories=directories, summaries=summaries)


def listicles_to_read(summaries: list[dict[str, Any]], product_domain: str) -> list[str]:
    """The bounded reading list: "best" lists of the category phrases first,
    then the other category results, then the brand queries; directories and
    the product's own pages are never on it."""
    def priority(row: dict[str, Any]) -> tuple[int, int]:
        if row.get("query_kind") == "brand":
            group = 2
        else:
            group = 0 if str(row.get("query") or "").startswith("best ") else 1
        return group, 0 if row.get("source") == "dataforseo_serp" else 1

    urls: list[str] = []
    per_site: dict[str, int] = {}
    for row in sorted((s for s in summaries if s.get("round") == 1), key=priority):
        for url in row.get("listicles") or []:
            domain = _domain(url)
            if not domain or domain == product_domain or classify_domain(domain) == "directory" or url in urls:
                continue
            if _search_page(url) or per_site.get(domain, 0) >= LISTICLES_PER_SITE:
                continue  # a site's own search results are no list; two pages per site keep the views varied
            per_site[domain] = per_site.get(domain, 0) + 1
            urls.append(url)
    return urls[:MAX_LISTICLES_TO_READ]


def _search_page(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    keys = {key.lower() for key in urllib.parse.parse_qs(parsed.query)}
    return bool(keys & _SEARCH_PAGE_KEYS) or "/search" in parsed.path.lower()


def run_round2(client: OsClient, inputs: RunInputs, discovery: Discovery, seeds: list[str]) -> None:
    """Keyword overlap and PPC competitors of the confirmed direct domains.
    The overlap report is core evidence; SpyFu is best effort."""
    pool, summaries = discovery.pool, discovery.summaries
    locale = {"location_code": inputs.location_code, "language_code": inputs.language_code}

    def admit(domain: str, seed: str, query: str) -> Candidate | None:
        if not domain or domain in (seed, inputs.product_domain):
            return None
        kind = classify_domain(domain)
        if kind == "noise":
            return None
        if kind == "directory":
            discovery.directories.setdefault(domain, []).append(query)
            return None
        candidate = _candidate(pool, domain, 2)
        candidate.add_provenance("discovered")
        return candidate

    for seed in seeds:
        query = f"overlap:{seed}"
        response, _ = _call_with_context(client, seed, "DataForSEO competitors-domain", lambda s=seed: client.dataforseo(
            "competitors-domain", {"target": s, "limit": COMPETITORS_DOMAIN_LIMIT, **locale}
        ))
        if response.get("unavailable"):
            summaries.append(_summary(2, query, "relationship", "dataforseo_competitors_domain", 0, 0, [], str(response["unavailable"])))
            continue
        retrieved = found = 0
        for item in _serp_items(response):
            retrieved += 1
            candidate = admit(_domain(item.get("domain")), seed, query)
            if candidate is None:
                continue
            candidate.add_source("dataforseo_overlap")
            if seed not in candidate.overlap_seeds:
                candidate.overlap_seeds.append(seed)
            intersections = item.get("intersections")
            if isinstance(intersections, int) and not isinstance(intersections, bool):
                candidate.overlap_intersections = max(candidate.overlap_intersections, intersections)
            candidate.listed(query)
            found += 1
        summaries.append(_summary(2, query, "relationship", "dataforseo_competitors_domain", retrieved, found, []))

    for seed in seeds if client.max_spyfu_calls > 0 else []:
        query = f"ppc:{seed}"
        try:
            response, _ = client.spyfu("ppc-competitors", {"domain": seed, "country_code": inputs.spyfu_market, "max_rows": SPYFU_COMPETITORS})
        except BudgetExhausted:
            raise
        except CompetitorSetError as exc:
            summaries.append(_summary(2, query, "relationship", "spyfu_ppc_competitors", 0, 0, [], str(exc)))
            continue
        if response.get("unavailable"):
            summaries.append(_summary(2, query, "relationship", "spyfu_ppc_competitors", 0, 0, [], str(response["unavailable"])))
            continue
        retrieved = found = 0
        for item in response.get("rows") or []:
            if not isinstance(item, dict):
                continue
            retrieved += 1
            candidate = admit(_domain(item.get("domain")), seed, query)
            if candidate is None:
                continue
            candidate.add_source("spyfu_ppc")
            if seed not in candidate.ppc_seeds:
                candidate.ppc_seeds.append(seed)
            common = item.get("common_paid_keywords")
            if isinstance(common, int) and not isinstance(common, bool):
                candidate.spyfu_common_keywords = max(candidate.spyfu_common_keywords, common)
            candidate.listed(query)
            found += 1
        summaries.append(_summary(2, query, "relationship", "spyfu_ppc_competitors", retrieved, found, []))


# ── the agent's enrichment files ────────────────────────────────────────────

def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompetitorSetError(f"{path.name} is not valid JSON: {exc}") from exc


def load_listicles(path: Path) -> dict[str, dict[str, Any]]:
    raw = _load_json(path)
    if raw is None:
        return {}
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or not isinstance(raw.get("pages"), list):
        raise CompetitorSetError(f"{path.name} must be an object with schema_version 1 and a pages list")
    pages: dict[str, dict[str, Any]] = {}
    for index, page in enumerate(raw["pages"]):
        if not isinstance(page, dict):
            raise CompetitorSetError(f"{path.name} page #{index + 1} must be an object")
        url = _url(page.get("url"))
        if not url:
            raise CompetitorSetError(f"{path.name} page #{index + 1} needs the listicle address as url")
        if url in pages:
            raise CompetitorSetError(f"{path.name} records {url} twice")
        status = page.get("status")
        if status not in ("read", "unreadable"):
            raise CompetitorSetError(f"{path.name} page {url} needs status read or unreadable")
        reason = _text(page.get("reason"), 200)
        if status == "unreadable" and not reason:
            raise CompetitorSetError(f"{path.name} page {url} is unreadable without a reason")
        entries_raw = page.get("entries") or []
        if not isinstance(entries_raw, list) or len(entries_raw) > MAX_LISTICLE_ENTRIES:
            raise CompetitorSetError(f"{path.name} page {url} needs at most {MAX_LISTICLE_ENTRIES} entries in a list")
        entries = []
        for entry in entries_raw:
            if not isinstance(entry, dict) or not _text(entry.get("name")):
                raise CompetitorSetError(f"{path.name} page {url} has an entry without a name")
            domain_raw = entry.get("domain")
            domain = _domain(domain_raw) if domain_raw else ""
            if domain_raw and not domain:
                raise CompetitorSetError(f"{path.name} page {url} has an entry with an invalid domain {domain_raw!r}")
            entries.append({
                "name": _text(entry.get("name"), 80), "domain": domain or None,
                **{key: _text(entry.get(key), 160) or None for key in ("offer", "format", "price_text", "duration", "audience")},
            })
        pages[url] = {"url": url, "status": status, "reason": reason or None, "entries": entries}
    return pages


def load_profiles(path: Path) -> dict[str, dict[str, Any]]:
    raw = _load_json(path)
    if raw is None:
        return {}
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or not isinstance(raw.get("profiles"), list):
        raise CompetitorSetError(f"{path.name} must be an object with schema_version 1 and a profiles list")
    profiles: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw["profiles"]):
        if not isinstance(item, dict):
            raise CompetitorSetError(f"{path.name} profile #{index + 1} must be an object")
        domain = _domain(item.get("domain"))
        if not domain:
            raise CompetitorSetError(f"{path.name} profile #{index + 1} has no valid domain")
        if domain in profiles:
            raise CompetitorSetError(f"{path.name} profiles `{domain}` twice")
        for flag in ("operating", "same_buyer", "same_job"):
            if not isinstance(item.get(flag), bool):
                raise CompetitorSetError(f"{path.name} profile for `{domain}` needs a boolean {flag}")
        if item.get("offer_match") not in OFFER_MATCHES:
            raise CompetitorSetError(f"{path.name} profile for `{domain}` needs offer_match in {', '.join(OFFER_MATCHES)}")
        price = item.get("price_usd")
        try:
            price_usd = None if price is None else _number(price)
        except ValueError:
            raise CompetitorSetError(f"{path.name} profile for `{domain}` needs price_usd as a non-negative number or null") from None
        for flag in ("marketplace", "focused"):
            if item.get(flag) is not None and not isinstance(item.get(flag), bool):
                raise CompetitorSetError(f"{path.name} profile for `{domain}` has a non-boolean {flag}")
        urls = item.get("evidence_urls")
        evidence = [u for u in (_url(x) for x in urls) if u] if isinstance(urls, list) else []
        if not evidence:
            raise CompetitorSetError(f"{path.name} profile for `{domain}` needs at least one evidence URL (the pages read)")
        found_raw = item.get("found_in")
        found_in = _url(found_raw) if found_raw else ""
        if found_raw and not found_in:
            raise CompetitorSetError(f"{path.name} profile for `{domain}` has found_in that is not an address")
        profiles[domain] = {
            "domain": domain,
            "name": _text(item.get("name"), 80) or None,
            "operating": item["operating"],
            "offer": _text(item.get("offer"), 200) or None,
            "offer_url": _url(item.get("offer_url")) or None,
            "offer_class": _text(item.get("offer_class"), 120) or None,
            "offer_match": item["offer_match"],
            "price_text": _text(item.get("price_text"), 160) or None,
            "price_usd": price_usd,
            "duration": _text(item.get("duration"), 120) or None,
            "buyer": _text(item.get("buyer"), 200) or None,
            "same_buyer": item["same_buyer"],
            "job": _text(item.get("job"), 200) or None,
            "same_job": item["same_job"],
            "marketplace": bool(item.get("marketplace")),
            # False when the offer is a side line of a big multi-product domain (a
            # university, a large platform): its neighbours are not the offer's.
            "focused": item.get("focused") is not False,
            "main_business": _text(item.get("main_business"), 200) or None,
            "markets": _text(item.get("markets"), 120) or None,
            "evidence_urls": evidence[:6],
            "found_in": found_in or None,
        }
    return profiles


def load_decisions(path: Path) -> dict[str, dict[str, Any]]:
    """Validate the agent's tiering file. Every decision names a domain the
    pool knows (discovered, named, listicle-backed or profiled with the page
    where the agent found it)."""
    raw = _load_json(path)
    if raw is None:
        return {}
    if isinstance(raw, dict) and raw.get("schema_version") == 1:
        raise CompetitorSetError(
            f"{path.name} has schema_version 1, which predates the offer-led rules: profile the candidates and "
            f"decide them again with schema_version {DECISIONS_SCHEMA_VERSION} (see the workflow doc)"
        )
    if not isinstance(raw, dict) or raw.get("schema_version") != DECISIONS_SCHEMA_VERSION or not isinstance(raw.get("decisions"), list):
        raise CompetitorSetError(f"{path.name} must be an object with schema_version {DECISIONS_SCHEMA_VERSION} and a decisions list")
    decisions: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(raw["decisions"]):
        if not isinstance(item, dict):
            raise CompetitorSetError(f"{path.name} decision #{index + 1} must be an object")
        domain = _domain(item.get("domain"))
        tier = item.get("competitor_tier")
        reason = _text(item.get("reason"), 240)
        if not domain:
            raise CompetitorSetError(f"{path.name} decision #{index + 1} has no valid domain")
        if domain in decisions:
            raise CompetitorSetError(f"{path.name} decides `{domain}` twice")
        if tier not in DECISION_TIERS:
            raise CompetitorSetError(f"{path.name} decision for `{domain}` needs competitor_tier in {', '.join(DECISION_TIERS)}")
        if not reason:
            raise CompetitorSetError(f"{path.name} decision for `{domain}` needs a reason")
        name = item.get("name")
        same_raw = item.get("same_as")
        same_as = _domain(same_raw) if same_raw else ""
        if same_raw and (not same_as or same_as == domain):
            raise CompetitorSetError(f"{path.name} decision for `{domain}` has same_as that is not another domain")
        if same_as and tier != "excluded":
            raise CompetitorSetError(f"{path.name} decision for `{domain}` folds it into `{same_as}`: its tier must be excluded")
        decisions[domain] = {
            "competitor_tier": tier,
            "reason": reason,
            "name": _text(name, 80) if isinstance(name, str) and name.strip() else None,
            "override_reason": _text(item.get("override_reason"), 240) or None,
            "same_as": same_as or None,
        }
    for domain, decision in decisions.items():
        target = decisions.get(decision["same_as"] or "")
        if target is not None and target["same_as"]:
            raise CompetitorSetError(f"{path.name} folds `{domain}` into `{decision['same_as']}`, which is folded itself; name the final domain")
    return decisions


def load_review(path: Path) -> dict[str, Any]:
    raw = _load_json(path)
    empty = {"rounds": [], "checked": set(), "objections": [], "missing": [], "checked_by_round": {1: set(), 2: set()}}
    if raw is None:
        return empty
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or not isinstance(raw.get("rounds"), list):
        raise CompetitorSetError(f"{path.name} must be an object with schema_version 1 and a rounds list")
    review = empty
    for index, item in enumerate(raw["rounds"]):
        if not isinstance(item, dict):
            raise CompetitorSetError(f"{path.name} round #{index + 1} must be an object")
        reviewer = _text(item.get("reviewer"), 120)
        if not reviewer:
            raise CompetitorSetError(f"{path.name} round #{index + 1} needs the reviewer (a separate agent or pass)")
        checked = item.get("checked")
        if not isinstance(checked, list) or not checked:
            raise CompetitorSetError(f"{path.name} round #{index + 1} needs the checked domains")
        domains = parse_domains(checked, 1000)
        review["checked"].update(domains)
        # The discovery round whose pool this review round looked through (1 when omitted).
        discovery_round = item.get("discovery_round", 1)
        if type(discovery_round) is not int or discovery_round not in (1, 2):
            raise CompetitorSetError(f"{path.name} round #{index + 1} has discovery_round {discovery_round!r}; use 1 or 2")
        review["checked_by_round"][discovery_round].update(domains)
        objections = item.get("objections") or []
        missing = item.get("missing") or []
        if not isinstance(objections, list) or not isinstance(missing, list):
            raise CompetitorSetError(f"{path.name} round #{index + 1} needs objections and missing as lists")
        for objection in objections:
            domain = _domain(objection.get("domain")) if isinstance(objection, dict) else ""
            if not domain or not _text(objection.get("objection")):
                raise CompetitorSetError(f"{path.name} round #{index + 1} has an objection without a domain or text")
            resolution = objection.get("resolution")
            if resolution not in (None, "", *RESOLUTIONS):
                raise CompetitorSetError(f"{path.name} objection on `{domain}` needs resolution accepted or rejected")
            note = _text(objection.get("note"), 240)
            review["objections"].append({"round": index + 1, "domain": domain, "objection": _text(objection.get("objection"), 240),
                                         "resolution": resolution or None, "note": note or None})
        for entry in missing:
            domain = _domain(entry.get("domain")) if isinstance(entry, dict) else ""
            if not domain:
                raise CompetitorSetError(f"{path.name} round #{index + 1} lists a missing rival without a valid domain")
            resolution = entry.get("resolution")
            if resolution not in (None, "", *MISSING_RESOLUTIONS):
                raise CompetitorSetError(f"{path.name} missing rival `{domain}` needs resolution added or rejected")
            review["missing"].append({"round": index + 1, "domain": domain, "why": _text(entry.get("why"), 240),
                                      "resolution": resolution or None, "note": _text(entry.get("note"), 240) or None})
        review["rounds"].append({"round": index + 1, "reviewer": reviewer, "reviewed_on": _text(item.get("reviewed_on"), 10) or None,
                                 "discovery_round": discovery_round, "checked": len(domains), "objections": len(objections),
                                 "missing": len(missing)})
    return review


@dataclass
class AgentFiles:
    listicles: dict[str, dict[str, Any]]
    profiles: dict[str, dict[str, Any]]
    decisions: dict[str, dict[str, Any]]
    review: dict[str, Any]
    paths: dict[str, Path]


def load_agent_files(runtime: Path, decisions_path: Path) -> AgentFiles:
    paths = {
        "listicles": runtime / LISTICLES_FILENAME,
        "profiles": runtime / PROFILES_FILENAME,
        "decisions": decisions_path,
        "review": runtime / REVIEW_FILENAME,
    }
    return AgentFiles(
        listicles=load_listicles(paths["listicles"]),
        profiles=load_profiles(paths["profiles"]),
        decisions=load_decisions(paths["decisions"]),
        review=load_review(paths["review"]),
        paths=paths,
    )


def add_agent_research(pool: dict[str, Candidate], files: AgentFiles, to_read: list[str], product_domain: str) -> list[str]:
    """Listicle entries and profiles the agent recorded become candidates
    with provenance `agent_research` and the page they came from; a profile
    of a domain no source recorded must say where it was found."""
    recorded = set(to_read)
    stray = sorted(url for url in files.listicles if url not in recorded)
    if stray:
        raise CompetitorSetError(
            "listicles.json reads pages the runner did not record: " + ", ".join(stray[:5])
            + " — keep the reading to the addresses in candidates.json `listicles_to_read`"
        )
    for url in to_read:
        page = files.listicles.get(url)
        if not page or page["status"] != "read":
            continue
        for entry in page["entries"]:
            domain = entry["domain"]
            if not domain or domain == product_domain or classify_domain(domain) in ("noise", "directory"):
                continue
            if domain not in pool:
                # Only a domain no source recorded gets the agent's provenance;
                # for a known one the listicle page is one more source.
                candidate = _candidate(pool, domain)
                candidate.add_provenance("agent_research")
                candidate.found_in = url
            candidate = pool[domain]
            candidate.add_source("listicle")
            if url not in candidate.listicle_pages:
                candidate.listicle_pages.append(url)
    additions: list[str] = []
    for domain, profile in sorted(files.profiles.items()):
        if domain == product_domain:
            raise CompetitorSetError(f"profiles.json profiles the product's own domain `{domain}`")
        if domain in pool or not profile["found_in"]:
            continue
        candidate = _candidate(pool, domain)
        candidate.add_provenance("agent_research")
        candidate.add_source("agent_research")
        candidate.found_in = profile["found_in"]
        additions.append(domain)
    return additions


def own_additions(pool: dict[str, Candidate], additions: list[str]) -> list[str]:
    """The agent's own finds, after round 2: a profiled domain that round 2
    also discovered is a discovery, whatever page the profile names."""
    own = [domain for domain in additions if "discovered" not in pool[domain].provenance]
    if len(own) > MAX_AGENT_ADDITIONS:
        raise CompetitorSetError(f"profiles.json adds {len(own)} domains the discovery never saw; at most {MAX_AGENT_ADDITIONS} per run")
    return own


# ── profiling list, tier rules and completeness ─────────────────────────────

def _capped(rows: list[Candidate], cap: int, decisions: dict[str, dict[str, Any]]) -> list[str]:
    """The first `cap` domains, not counting the ones already decided
    `excluded`: an obvious non-competitor costs no profile, so it frees its
    place for the next candidate."""
    chosen: list[str] = []
    counted = 0
    for candidate in rows:
        excluded = (decisions.get(candidate.domain) or {}).get("competitor_tier") == "excluded"
        if not excluded:
            if counted >= cap:
                continue
            counted += 1
        chosen.append(candidate.domain)
    return chosen


def required_round1(pool: dict[str, Candidate], inputs: RunInputs, decisions: dict[str, dict[str, Any]] | None = None) -> list[str]:
    """Domains the agent must profile and decide in round 1: every named
    competitor (founder or product page), then every domain worth
    profiling (see `offer_signal`), strongest first, up to the cap."""
    decisions = decisions or {}
    aliases = {d for d, dec in decisions.items() if dec.get("same_as")}
    named = [d for d in inputs.named_domains if d in pool]
    page = [d for d in inputs.page_domains if d in pool and d not in named]
    fixed = set(named) | set(page)
    discovered = [c for c in pool.values() if c.domain not in fixed and c.domain not in aliases and c.offer_signal()]
    # Advertisers on the offer's own search first: the list exists for the ones that buy ads.
    discovered.sort(key=lambda c: (not (c.serp_paid_hits or c.keyword_ads_phrases), -c.round1_score(), -c.signal_count(), -len(c.sources), c.domain))
    return named + page + _capped(discovered, MAX_PROFILES_ROUND1, decisions)


def required_round2(pool: dict[str, Candidate], required1: list[str], decisions: dict[str, dict[str, Any]] | None = None) -> list[str]:
    """A bounded stable-domain sample of relationship results; single hits remain eligible."""
    decisions = decisions or {}
    first = set(required1)
    rows = [
        c for c in pool.values()
        if c.domain not in first and not (decisions.get(c.domain) or {}).get("same_as")
        and c.relationship_hits()
    ]
    rows.sort(key=lambda c: c.domain)
    return _capped(rows, MAX_PROFILES_ROUND2, decisions)


def apply_aliases(pool: dict[str, Candidate], decisions: dict[str, dict[str, Any]]) -> None:
    """A decision with `same_as` folds a second domain of the same offer (a
    redirect, an academy domain, a university brand on a partner's program)
    into the canonical one: its discovery facts count there, and it is
    recorded as excluded."""
    for domain, decision in sorted(decisions.items()):
        canonical = decision.get("same_as")
        if not canonical or domain not in pool:
            continue
        if canonical not in pool:
            raise CompetitorSetError(
                f"decisions.json folds `{domain}` into `{canonical}`, which no source recorded: profile `{canonical}` with found_in first"
            )
        pool[canonical].absorb(pool[domain])


def price_band(price_usd: float | None, floor: float | None) -> str:
    if floor is None:
        return "no_floor"
    if price_usd is None:
        return "unknown"
    return "at_or_above_floor" if price_usd >= floor else "below_floor"


@dataclass
class Assessment:
    domain: str
    tier: str
    named: bool
    profile: dict[str, Any] | None
    decision: dict[str, Any]
    price_band: str
    meets_direct: bool
    comparable: bool
    unmet: list[str]
    group: int | None
    reason_code: str


def assess(domain: str, decision: dict[str, Any], profile: dict[str, Any] | None, named: bool, floor: float | None) -> Assessment:
    """Record caller-supplied comparison roles; prices and ad activity are facts,
    not automatic eligibility or business-priority rules."""
    tier = decision["competitor_tier"]
    band = price_band(profile["price_usd"] if profile else None, floor)
    group = None if tier == "excluded" else {"direct": 0, "indirect": 1}.get(tier, 2)
    code = ("same_as" if decision.get("same_as") else "excluded") if group is None else tier
    return Assessment(domain=domain, tier=tier, named=named, profile=profile, decision=decision, price_band=band,
                      meets_direct=tier == "direct", comparable=group is not None, unmet=[], group=group, reason_code=code)


def check_consistency(assessments: dict[str, Assessment]) -> None:
    """Decisions require reasons and sourced profiles in load_agent_files.
    No built-in price/buyer/offer formula overrides the caller's scope."""
    return None


def missing_items(*, domains: set[str], required: list[str], inputs: RunInputs, files: AgentFiles, to_read: list[str],
                  assessments: dict[str, Assessment]) -> dict[str, list[str]]:
    """Identify missing source records for this chosen collection operation."""
    listicles = [url for url in to_read if url not in files.listicles]
    profiles: list[str] = []
    decisions: list[str] = []
    for domain in required:
        decision = files.decisions.get(domain)
        if decision is None:
            decisions.append(domain)
        needs_profile = domain in inputs.named_domains or (decision is not None and decision["competitor_tier"] != "excluded") or decision is None
        if needs_profile and domain not in files.profiles:
            profiles.append(domain)
    for domain in sorted(d for d in files.profiles if d in domains):
        if domain not in files.decisions and domain not in decisions:
            decisions.append(domain)
    for domain in sorted(d for d, dec in files.decisions.items() if d in domains and dec["competitor_tier"] != "excluded"):
        if domain not in files.profiles and domain not in profiles:
            profiles.append(domain)
    missing = {"listicles": listicles, "profiles": profiles, "decisions": decisions}
    return {key: value for key, value in missing.items() if value}


def build_assessments(pool: dict[str, Candidate], files: AgentFiles, inputs: RunInputs) -> dict[str, Assessment]:
    return {
        domain: assess(domain, decision, files.profiles.get(domain), domain in inputs.named_domains, inputs.price_floor_usd)
        for domain, decision in files.decisions.items() if domain in pool
    }


def round2_seeds(pool: dict[str, Candidate], assessments: dict[str, Assessment], inputs: RunInputs) -> list[str]:
    """Up to three confirmed direct competitors (those named by the founder first, then
    by ads on the offer's phrases), topped up with comparable indirect ones.
    A domain whose profile says the offer is a side line of a big
    multi-product site (`focused: false`) is never a seed: its keyword and
    PPC neighbours are the rest of that site's business, not this offer's.
    Nor is a seller's subdomain on a course host: the tools measure the host."""
    def key(item: Assessment) -> tuple:
        candidate = pool[item.domain]
        ads = len(candidate.keyword_ads_phrases) + candidate.serp_paid_hits
        return (0 if item.named else 1, -ads, -candidate.round1_score(), item.domain)

    def usable(item: Assessment) -> bool:
        return bool(item.profile and item.profile.get("focused", True)) and not hosted_seller(item.domain)

    direct = sorted((a for a in assessments.values() if a.group == 0 and usable(a)), key=key)
    seeds = [a.domain for a in direct[:ROUND2_SEEDS]]
    if len(seeds) < ROUND2_SEEDS:
        comparable = sorted((a for a in assessments.values() if a.group == 1 and usable(a)), key=key)
        seeds += [a.domain for a in comparable[: ROUND2_SEEDS - len(seeds)]]
    return seeds


# ── ad check ────────────────────────────────────────────────────────────────

def scan_home(client: OsClient, domain: str) -> dict[str, Any]:
    """Home page plus up to two Google Tag Manager containers; the ad tags
    of the Channel Footprint signature list."""
    cf = _channel_footprint()
    page, _ = client.fetch_page(f"https://{domain}/")
    status = page.get("status")
    body = str(page.get("body") or "")
    if not isinstance(status, int):
        return {"fetch_status": "error", "tags": []}
    if status >= 400:
        return {"fetch_status": "blocked" if status in (401, 403, 429, 503) else "error", "tags": []}
    if not body.strip():
        return {"fetch_status": "empty", "tags": []}
    blobs = [body]
    for container in list(dict.fromkeys(cf.GTM_ID_RE.findall(body)))[:GTM_CONTAINERS_PER_SITE]:
        gtm, _ = client.fetch_page(f"https://www.googletagmanager.com/gtm.js?id={container}")
        blobs.append(str(gtm.get("body") or ""))
    tags = sorted({t["tag"] for t in cf.detect_tags(blobs) if t["channel"] in AD_TAG_CHANNELS})
    return {"fetch_status": "ok", "tags": tags}


def _meta_matches(rows: list[Any], domain: str) -> int:
    """Ads whose destination is the domain, or whose page name is the brand
    when the ad carries no usable destination (the Channel Footprint rule)."""
    cf = _channel_footprint()
    brand = brand_token(domain)
    matched = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        links = row.get("ad_creative_link_captions") or []
        if isinstance(links, str):
            links = [links]
        destinations = {cf.usable_destination(x) for x in links if x} - {""} if isinstance(links, list) else set()
        if destinations:
            matched += int(domain in destinations)
        elif cf._name_matches(str(row.get("page_name") or ""), brand):
            matched += 1
    return matched


def check_ads(client: OsClient, inputs: RunInputs, candidate: Candidate, *, focused: bool = True) -> dict[str, Any]:
    """Does the competitor buy media? The round-1 ad facts on the offer's
    phrases, SpyFu's modeled Google spend (the primary market, then up to two
    more target markets), ad pixels on the home page and, when nothing on
    Google shows, the official Meta Ad Library (EU delivery).

    For an offer that is a side line of a multi-product domain (`focused:
    false`) only the ads on the offer's own phrases count: the domain's
    overall spend, pixels and Meta ads promote the rest of its business."""
    cf = _channel_footprint()
    kinds: list[str] = []
    facts: list[str] = []
    lookups: list[str] = []
    budget: float | None = None
    answered = False
    if candidate.keyword_ads_phrases:
        kinds.append("category_keyword_ads")
        seen = f", last seen {candidate.keyword_ads_last_seen}" if candidate.keyword_ads_last_seen else ""
        facts.append("Google ads on " + ", ".join(f"'{p}'" for p in candidate.keyword_ads_phrases) + f" (SpyFu{seen})")
    if candidate.serp_paid_hits:
        kinds.append("category_paid_result")
        facts.append("paid result for " + ", ".join(f"'{q}'" for q in candidate.paid_queries[:3]))
    if not focused:
        lookups.append("domain-wide checks skipped: the offer is a side line of a multi-product domain")
        return {"ad_activity": "ads_seen" if kinds else "unknown", "ad_evidence": facts[:6], "ad_kinds": kinds,
                "ad_strength": len(kinds), "google_budget_usd": None, "pixel_tags": [], "lookup_gaps": lookups}
    markets = [m for m in inputs.markets if m in SPYFU_MARKETS][: 1 + AD_CHECK_EXTRA_MARKETS]
    if hosted_seller(candidate.domain):
        # SpyFu models the host's domain; that spend is not this seller's.
        markets = []
        lookups.append("spyfu: a seller's subdomain on a course host, not measured")
    for market in markets if client.max_spyfu_calls > 0 else []:
        try:
            data, retrieved_on = client.spyfu("domain-stats", {"domain": candidate.domain, "country_code": market, "months": AD_CHECK_MONTHS})
        except BudgetExhausted:
            raise
        except CompetitorSetError as exc:
            lookups.append(f"spyfu {market}: {str(exc)[:80]}")
            continue
        if data.get("unavailable"):
            lookups.append(f"spyfu {market}: rejected")
            continue
        row = cf._paid_search_row(candidate.domain, market, data, retrieved_on)
        if row["found"]:
            answered = True
        if row["months_with_spend"]:
            kinds.append("google_spend")
            budget = row["avg_monthly_budget_usd"]
            amount = f", about {_money(float(budget))}/month" if budget else ""
            facts.append(f"Google Ads spend in {row['months_with_spend']} of {row['months_checked']} month(s) in {market} (SpyFu{amount})")
            break
    scan = scan_home(client, candidate.domain)
    if scan["fetch_status"] == "ok":
        answered = True
    else:
        lookups.append(f"home page: {scan['fetch_status']}")
    if not kinds and client.max_meta_searches > 0:
        try:
            response, _ = client.meta_library({"query": brand_token(candidate.domain), "countries": [inputs.eu_country],
                                               "activeStatus": "ACTIVE", "limit": META_ADS_LIMIT})
        except BudgetExhausted:
            raise
        except CompetitorSetError as exc:
            lookups.append(f"meta: {str(exc)[:80]}")
        else:
            if response.get("unavailable"):
                lookups.append("meta: rejected")
            else:
                answered = True
                matched = _meta_matches(response.get("data") or [], candidate.domain)
                if matched:
                    kinds.append("meta_eu")
                    facts.append(f"{matched} active Meta ad(s) delivered in {inputs.eu_country} (EU library)")
    if scan["tags"]:
        facts.append("ad pixels on the home page: " + ", ".join(scan["tags"]))
    verdict = "ads_seen" if kinds else "pixels_only" if scan["tags"] else "none_detected" if answered else "unknown"
    return {"ad_activity": verdict, "ad_evidence": facts[:6], "ad_kinds": kinds, "ad_strength": len(kinds),
            "google_budget_usd": budget, "pixel_tags": scan["tags"], "lookup_gaps": lookups[:4]}


# ── composition ─────────────────────────────────────────────────────────────

def _order_key(item: Assessment, ads: dict[str, dict[str, Any]], pool: dict[str, Candidate]) -> tuple:
    # Stable inspection order, never a recommendation ranking.
    return (item.domain,)


def compose(eligible: list[Assessment], ads: dict[str, dict[str, Any]], pool: dict[str, Candidate], cap: int) -> tuple[list[Assessment], list[Assessment]]:
    """Preserve explicitly named scope, then take a stable-domain bounded sample."""
    ordered = sorted(eligible, key=lambda a: _order_key(a, ads, pool))
    reserved = [a for a in ordered if a.named]
    others = [a for a in ordered if not a.named]
    room = max(cap - len(reserved), 0)
    chosen = sorted(reserved + others[:room], key=lambda a: _order_key(a, ads, pool))
    return chosen, others[room:]


def _selection_text(item: Assessment, ad: dict[str, Any], cap: int, direct_count: int) -> str:
    return f"{item.tier}; caller-scoped inspection sample; {AD_LABELS[ad['ad_activity']]}"


def _not_eligible_reason(item: Assessment, floor: float | None) -> str:
    if item.reason_code == "same_as":
        return f"same offer as {item.decision['same_as']}: {item.decision['reason']}"
    return item.decision["reason"]


# ── rendering ───────────────────────────────────────────────────────────────

def _cell(value: Any, cap: int = 150) -> str:
    text = " ".join(str(value if value is not None and value != "" else "—").split()).replace("|", "\\|")
    return text if len(text) <= cap else text[: cap - 1] + "…"


def _offer_lines(inputs: RunInputs) -> list[str]:
    offer = inputs.offer
    lines = []
    if offer.get("name") or offer.get("url"):
        lines.append(f"- Offer: {_cell(offer.get('name') or 'the product', 120)}" + (f" ({offer['url']})" if offer.get("url") else ""))
    for key, label in (("job", "Job"), ("buyer", "Buyer"), ("offer_class", "Offer class"), ("comparable_classes", "Comparable offer classes"),
                       ("duration", "Duration"), ("price_text", "Price")):
        if offer.get(key):
            lines.append(f"- {label}: {_cell(offer[key], 300)}")
    if inputs.price_floor_usd is not None:
        basis = f" ({offer['price_floor_basis']})" if offer.get("price_floor_basis") else ""
        lines.append(f"- Caller-supplied comparison floor: {_money(inputs.price_floor_usd)}{basis}")
    else:
        lines.append("- Caller-supplied comparison floor: not set; no default is inferred")
    lines.append(f"- Category phrases: {', '.join(inputs.category_phrases) or 'none'}")
    named = ", ".join(inputs.named_domains) or ("explicitly none" if inputs.input_annotations.get("operator_named_asked") is True else "unknown")
    lines.append(f"- Competitors named by the founder: {named}; mentioned on the product page: {', '.join(inputs.page_domains) or 'not supplied'}")
    lines.append(f"- Markets: {', '.join(inputs.markets)}; product domain {inputs.product_domain or 'not given'} (excluded, never a search seed)")
    if inputs.offer.get("confirmed_by_operator"):
        lines.append("- The founder confirmed this offer: " + _cell(inputs.offer.get("basis"), 300))
    elif inputs.offer.get("inferred"):
        lines.append("- The offer is an inference: " + _cell(inputs.offer.get("basis"), 300))
    elif inputs.intake_path:
        lines.append("- The offer card is not marked as confirmed by the founder.")
    else:
        lines.append(f"- No offer card was recorded ({INTAKE_REL.as_posix()} is missing); the inputs came from the command line.")
    return lines


def render_section(*, inputs: RunInputs, cap: int, competitors: list[dict[str, Any]], profiled_out: list[dict[str, Any]],
                   excluded: list[dict[str, Any]], summaries: list[dict[str, Any]], pool_size: int, coverage: dict[str, Any],
                   totals: dict[str, Any], retrieved_on: str) -> str:
    lines: list[str] = []
    add = lines.append
    groups = {g: sum(1 for c in competitors if c["selection_group"] == g) for g in GROUP_LABELS.values()}
    add(
        f"Competitor discovery retrieved {retrieved_on}: {pool_size} candidate domain(s) from {len(summaries)} provider "
        f"query/report(s) in two rounds; {coverage['profiles']} profiled; {len(competitors)} competitor(s) kept "
        f"({groups['direct']} direct, {groups['indirect']} indirect, {groups['other scoped']} "
        f"other scoped); {len(excluded)} candidate(s) recorded as not included."
    )
    add("")
    add("### Offer searched from")
    add("")
    lines.extend(_offer_lines(inputs))
    add("")
    add("### Inspection scope")
    add("")
    add(f"- Up to {cap} caller-classified competitors, with explicitly named domains retained and the rest in stable domain order.")
    add("- Direct, indirect and substitute are recorded comparison roles. Price, ad activity and signal counts do not choose a business priority or exclude a substitute.")
    add("")
    add("### Competitor set")
    add("")
    if competitors:
        add("| # | Competitor | Tier | Provenance | Offer and format | Price | Ads | Why in the list |")
        add("| ---: | --- | --- | --- | --- | --- | --- | --- |")
        for row in competitors:
            offer = " — ".join(x for x in (row.get("offer"), row.get("offer_class")) if x) or None
            price = row.get("price_text") or _money(row.get("price_usd"))
            add(f"| {row['rank']} | {_cell(row['name'], 40)} ({_cell(row['domain'], 40)}) | {row['competitor_tier']} | {_cell(row['provenance_detail'], 60)} "
                f"| {_cell(offer, 110)} | {_cell(price, 50)} | {_cell('; '.join([AD_LABELS[row['ad_activity']]] + row['ad_evidence'][:2]), 120)} | {_cell(row['selection'], 140)} |")
    else:
        add("No competitor was confirmed in this run.")
    overrides = [row for row in competitors + profiled_out if row.get("override_reason")]
    if overrides:
        add("")
        add("Additional classification rationale: " + "; ".join(f"{r['domain']}: {_cell(r['override_reason'], 160)}" for r in overrides))
    add("")
    add("### Profiled, not included")
    add("")
    if profiled_out:
        add("| Domain | Tier | Offer and format | Price | Ads | Why not included |")
        add("| --- | --- | --- | --- | --- | --- |")
        for row in profiled_out[:PROFILED_ROWS_RENDERED]:
            offer = " — ".join(x for x in (row.get("offer"), row.get("offer_class")) if x) or None
            price = row.get("price_text") or _money(row.get("price_usd"))
            ads = AD_LABELS.get(row.get("ad_activity") or "", "not checked")
            add(f"| {_cell(row['domain'], 40)} | {row.get('competitor_tier') or '—'} | {_cell(offer, 110)} | {_cell(price, 50)} | {ads} | {_cell(row['reason'], 160)} |")
        if len(profiled_out) > PROFILED_ROWS_RENDERED:
            add("")
            add(f"{len(profiled_out) - PROFILED_ROWS_RENDERED} more profiled candidate(s) are recorded in the evidence file.")
    else:
        add("Every profiled candidate is in the list.")
    others = [row for row in excluded if not row.get("profiled") and row["reason_code"] not in ("directory", "over_cap")]
    if others:
        add("")
        counts: dict[str, int] = {}
        for row in others:
            counts[row["reason_code"]] = counts.get(row["reason_code"], 0) + 1
        add("Not profiled: " + ", ".join(f"{n} {code.replace('_', ' ')}" for code, n in sorted(counts.items())) + "; examples: "
            + ", ".join(row["domain"] for row in others[:EXCLUDED_ROWS_RENDERED]) + ".")
    directories = [row["domain"] for row in excluded if row["reason_code"] == "directory"]
    if directories:
        add("")
        add("Review and listing directories (recorded, never promoted): " + ", ".join(directories[:EXCLUDED_ROWS_RENDERED]) + ".")
    add("")
    add("### Discovery and enrichment coverage")
    add("")
    add("| Round | Query | Source | Items | Candidates |")
    add("| ---: | --- | --- | ---: | ---: |")
    for row in summaries:
        items = "unavailable" if row.get("unavailable") else str(row["retrieved"])
        add(f"| {row['round']} | {_cell(row['query'], 80)} | {row['source']} | {items} | {row['candidates']} |")
    if any(row.get("unavailable") for row in summaries):
        add("")
        add("Unavailable queries were rejected by the provider or failed; they are recorded, not retried silently.")
    add("")
    add(f"- Listicles: {coverage['listicles_read']} page(s) read, {coverage['listicles_unreadable']} unreadable, "
        f"{coverage['listicle_entries']} program entries recorded.")
    add(f"- Profiles: {coverage['profiles']} domain(s) profiled on their own sites; {coverage['agent_additions']} added by the agent "
        f"from its reading, each with the page it came from.")
    seeds = ", ".join(coverage["round2_seeds"]) or "none (no confirmed direct or comparable competitor)"
    add(f"- Round 2 seeds (confirmed direct competitors): {seeds}.")
    add(f"- Review: {coverage['review_rounds']} optional recorded review round(s); {coverage['objections_accepted']} objection(s) "
        f"accepted, {coverage['objections_rejected']} rejected; {coverage['missing_added']} missing rival(s) added, "
        f"{coverage['missing_rejected']} rejected.")
    add(f"- Ad check: {coverage['ad_checks']} domain(s); " + ", ".join(f"{n} {AD_LABELS[k]}" for k, n in coverage["ad_counts"].items() if n) + ".")
    add("")
    add("### Method and coverage")
    add("")
    add(
        f"- Spend recorded: {totals['dataforseo_calls']} answered DataForSEO task(s), {totals['spyfu_calls']} SpyFu lookup(s), "
        f"{totals['search_calls']} web search(es), {totals['meta_searches']} Meta Ad Library search(es) and {totals['page_fetches']} free page fetch(es)"
        + (f", plus {totals['rejected_calls']} rejected query(ies) that count as spend but not as evidence" if totals.get("rejected_calls") else "")
        + ", accumulated across attempts; cached replays add no new spend."
    )
    add(
        "- Signal strength orders the profiling list and breaks ties, never a tier: a paid result on a category query "
        f"{SCORE_CATEGORY_PAID:g} (up to {CAP_CATEGORY_PAID}), a Google advertiser on a category phrase {SCORE_KEYWORD_ADS:g} "
        f"(up to {CAP_KEYWORD_ADS}), an organic category result {SCORE_CATEGORY_ORGANIC:g} (up to {CAP_CATEGORY_ORGANIC}), a second-engine "
        f"result {SCORE_SECOND_ENGINE:g} (up to {CAP_SECOND_ENGINE}), an alternatives-query hit {SCORE_BRAND_QUERY:g} (up to {CAP_BRAND_QUERY}), "
        f"a listicle page {SCORE_LISTICLE:g} (up to {CAP_LISTICLE}), a round-2 relationship hit {SCORE_RELATIONSHIP:g} (up to {CAP_RELATIONSHIP}). "
        "Being named by the founder or on the product page adds nothing."
    )
    add(
        f"- Caps: {MAX_CATEGORY_PHRASES} category phrases (two queries each), {MAX_BRAND_QUERIES} alternatives queries for competitors named by the founder; "
        f"{MAX_LISTICLES_TO_READ} listicle pages read, {MAX_PROFILES_ROUND1} profiles in round 1 and {MAX_PROFILES_ROUND2} in round 2, "
        f"{MAX_AGENT_ADDITIONS} agent additions, {ROUND2_SEEDS} round-2 seeds, {MAX_AD_CHECKS} ad checks, {cap} competitors."
    )
    add("")
    add("### Sources")
    add("")
    add(
        "- DataForSEO Google SERP (paid and organic) and Labs `competitors_domain`, SpyFu keyword ad history, PPC competitors and "
        "domain stats, the official Meta Ad Library, Brave web search via OS tools, free home-page fetches, and the executing "
        f"agent's listicle reading, site profiles and optional review — retrieved {retrieved_on}; the candidate, competitor and "
        f"exclusion rows in `{EVIDENCE_REL.as_posix()}` are exactly the set every table above is computed from."
    )
    return "\n".join(lines).strip() + "\n"


# ── orchestration ───────────────────────────────────────────────────────────

def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def run(workspace: Path, args: argparse.Namespace) -> dict[str, Any]:
    workspace = workspace.resolve()
    io = _load_script("research-artifact-io.py", "pmr_artifact_io")
    with io.section_attempt(workspace, SECTION_ID, context_file=getattr(args, "context_file", None)):
        return _run(workspace, args)


def _inputs_block(inputs: RunInputs, cap: int) -> dict[str, Any]:
    return {
        "offer": inputs.offer,
        "operator_named": inputs.named_domains,
        "page_mentioned": inputs.page_domains,
        "keyword_domains": inputs.keyword_domains,
        "product_domain": inputs.product_domain,
        "category_phrases": inputs.category_phrases,
        "queries": inputs.category_queries + inputs.brand_queries,
        "price_floor_usd": inputs.price_floor_usd,
        "markets": inputs.markets,
        "location_code": inputs.location_code,
        "language_code": inputs.language_code,
        "max_competitors": cap,
        "intake_path": inputs.intake_path,
        "input_annotations": inputs.input_annotations,
    }


def _pending(workspace: Path, runtime: Path, decisions_path: Path, client: OsClient, reason: str, next_step: str, missing: dict[str, list[str]]) -> dict[str, Any]:
    state = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "status": "pending",
        "inputs_path": (RUNTIME_REL / "inputs.json").as_posix(),
        "inputs_sha256": _sha(runtime / "inputs.json"),
        "research_context": _load_script("research-artifact-io.py", "pmr_input_io").context_binding(workspace, SECTION_ID),
        "error": None,
        "reason": reason,
        "next_step": next_step,
        "missing": missing,
        "candidates_path": (RUNTIME_REL / CANDIDATES_FILENAME).as_posix(),
        "decisions_path": decisions_path.as_posix(),
        "undecided": missing.get("decisions", []),
        "attempt_dataforseo_tasks": client.dataforseo_tasks,
        "attempt_search_calls": client.search_calls,
        "attempt_spyfu_calls": client.spyfu_calls,
        "attempt_cache_hits": client.cache_hits,
    }
    _write_atomic(runtime / "request.json", json.dumps(state, indent=1))
    return state


def _write_candidates(runtime: Path, *, inputs: RunInputs, cap: int, files: AgentFiles, discovery: Discovery, to_read: list[str],
                      required1: list[str], required2: list[str] | None, seeds: list[str] | None, missing: dict[str, list[str]], status: str) -> None:
    profiled = set(files.profiles)
    rows = sorted(discovery.pool.values(), key=lambda c: (-c.score(), c.domain))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "status": status,
        "files": {name: path.as_posix() for name, path in files.paths.items()},
        "inputs": _inputs_block(inputs, cap),
        "listicles_to_read": to_read,
        "profile_required": {"round1": required1, "round2": required2 if required2 is not None else "after round 1 is complete"},
        "round2_seeds": seeds,
        "missing": missing,
        "rules": {
            "roles": "caller-supplied roles with sourced profile and reason",
            "price": "recorded comparison only; no automatic floor",
            "order": "explicitly named scope retained; stable domain inspection sample",
        },
        "candidates": [{**c.row(), "required": c.domain in required1 or c.domain in (required2 or []), "profiled": c.domain in profiled} for c in rows],
        "directories": sorted(discovery.directories),
        "search_summaries": discovery.summaries,
    }
    _write_atomic(runtime / CANDIDATES_FILENAME, json.dumps(payload, indent=1, ensure_ascii=False))


def _pending_message(missing: dict[str, list[str]]) -> str:
    parts = []
    for key, label in (("listicles", "listicle page(s) to read"), ("profiles", "domain(s) to profile"), ("decisions", "domain(s) to decide"),
                       ("review", "domain(s) for the reviewer"), ("objections", "objection(s) to resolve"), ("missing_rivals", "missing rival(s) to settle"),
                       ("round2_review", "round-2 domain(s) for a review round of the round-2 pool")):
        if missing.get(key):
            parts.append(f"{len(missing[key])} {label}")
    return ", ".join(parts)


def _run(workspace: Path, args: argparse.Namespace) -> dict[str, Any]:
    workspace = workspace.resolve()
    runtime = workspace / RUNTIME_REL
    cache_dir = runtime / "cache"
    runtime.mkdir(parents=True, exist_ok=True)

    api_key = (os.environ.get("OS_API_KEY") or "").strip()
    if not api_key:
        raise CompetitorSetError("OS_API_KEY is required")
    os_url = (os.environ.get("OS_URL") or DEFAULT_OS_URL).strip() or DEFAULT_OS_URL

    cap = max(1, int(_arg(args, "max_competitors", MAX_COMPETITORS)))
    inputs = bind_inputs(workspace, args)
    client = OsClient(
        os_url=os_url,
        api_key=api_key,
        cache_dir=cache_dir,
        max_dataforseo_tasks=int(_arg(args, "max_dataforseo_tasks", MAX_DATAFORSEO_TASKS_PER_ATTEMPT)),
        max_search_calls=int(_arg(args, "max_search_calls", MAX_SEARCH_CALLS_PER_ATTEMPT)),
        max_spyfu_calls=int(_arg(args, "max_spyfu_calls", MAX_SPYFU_CALLS_PER_ATTEMPT)),
        max_meta_searches=int(_arg(args, "max_meta_searches", MAX_META_SEARCHES_PER_ATTEMPT)),
        max_fetches=int(_arg(args, "max_fetches", MAX_FETCHES_PER_ATTEMPT)),
    )

    discovery = run_round1(client, inputs)
    if not discovery.summaries:
        raise CompetitorSetError("no discovery query could be formed from the inputs: give the offer's category phrases or competitors named by the founder")
    if not any(not s.get("unavailable") for s in discovery.summaries):
        # Nothing proves the market was searched: a provider that rejected or
        # failed every query must not become a "completed" section with an
        # empty or named-only competitor list.
        rejected = sum(1 for s in discovery.summaries if s.get("unavailable"))
        raise CompetitorSetError(
            f"discovery unavailable: none of the {len(discovery.summaries)} provider queries answered "
            f"({rejected} rejected or failed); the section cannot complete without a successful search. "
            "Rejected DataForSEO queries are cached and will not be retried unchanged: change the category phrases "
            "or retry later if the web search was rate-limited."
        )

    decisions_arg = str(_arg(args, "decisions", "") or "")
    decisions_path = Path(decisions_arg) if decisions_arg else runtime / DECISIONS_FILENAME
    if not decisions_path.is_absolute():
        decisions_path = workspace / decisions_path
    files = load_agent_files(runtime, decisions_path)
    to_read = listicles_to_read(discovery.summaries, inputs.product_domain)
    additions = add_agent_research(discovery.pool, files, to_read, inputs.product_domain)
    apply_aliases(discovery.pool, files.decisions)
    required1 = required_round1(discovery.pool, inputs, files.decisions)
    round1_domains = set(discovery.pool)
    assessments = build_assessments(discovery.pool, files, inputs)
    check_consistency(assessments)
    missing1 = missing_items(domains=round1_domains, required=required1, inputs=inputs, files=files, to_read=to_read, assessments=assessments)
    if missing1:
        _write_candidates(runtime, inputs=inputs, cap=cap, files=files, discovery=discovery, to_read=to_read, required1=required1,
                          required2=None, seeds=None, missing=missing1, status="enrich_round1")
        return _pending(workspace, runtime, decisions_path, client, "enrichment of round 1 incomplete: " + _pending_message(missing1), "enrich_round1", missing1)

    seeds = round2_seeds(discovery.pool, assessments, inputs)
    if seeds:
        run_round2(client, inputs, discovery, seeds)
    additions = own_additions(discovery.pool, additions)
    unknown = sorted(d for d in set(files.decisions) | {d for d, p in files.profiles.items() if not p["found_in"]} if d not in discovery.pool)
    if unknown:
        raise CompetitorSetError(
            "decisions or profiles name domains no source recorded: " + ", ".join(unknown[:10])
            + " — give a profile with found_in (the page where the agent found it), or remove them (the round-2 seeds may have changed)"
        )
    apply_aliases(discovery.pool, files.decisions)
    required2 = required_round2(discovery.pool, required1, files.decisions)
    assessments = build_assessments(discovery.pool, files, inputs)
    check_consistency(assessments)
    missing2 = missing_items(domains=set(discovery.pool), required=required1 + required2, inputs=inputs, files=files, to_read=to_read, assessments=assessments)
    if missing2:
        _write_candidates(runtime, inputs=inputs, cap=cap, files=files, discovery=discovery, to_read=to_read, required1=required1,
                          required2=required2, seeds=seeds, missing=missing2, status="enrich_round2")
        return _pending(workspace, runtime, decisions_path, client, "enrichment of round 2 incomplete: " + _pending_message(missing2), "enrich_round2", missing2)

    # Ad check for every domain that can enter the list (those named by the founder first, then in tier order).
    eligible = [a for a in assessments.values() if a.group is not None]
    eligible.sort(key=lambda a: (0 if a.named else 1, a.domain))
    ads: dict[str, dict[str, Any]] = {}
    checked_ads: list[str] = []
    for item in eligible[:max(MAX_AD_CHECKS, sum(1 for a in eligible if a.named))]:
        ads[item.domain] = check_ads(client, inputs, discovery.pool[item.domain], focused=(item.profile or {}).get("focused") is not False)
        checked_ads.append(item.domain)
    for item in eligible:
        ads.setdefault(item.domain, {"ad_activity": "unknown", "ad_evidence": [f"not checked: over the ad-check cap of {MAX_AD_CHECKS}"],
                                     "ad_kinds": [], "ad_strength": 0, "google_budget_usd": None, "pixel_tags": [], "lookup_gaps": []})
    chosen, over = compose(eligible, ads, discovery.pool, cap)
    _write_candidates(runtime, inputs=inputs, cap=cap, files=files, discovery=discovery, to_read=to_read, required1=required1,
                      required2=required2, seeds=seeds, missing={}, status="complete")

    direct_count = sum(1 for a in eligible if a.group == 0)
    pool = discovery.pool

    def profile_fields(domain: str) -> dict[str, Any]:
        profile = files.profiles.get(domain) or {}
        return {key: profile.get(key) for key in ("offer", "offer_url", "offer_class", "offer_match", "price_text", "price_usd",
                                                     "duration", "buyer", "job", "operating", "marketplace", "evidence_urls")}

    def provenance_detail(candidate: Candidate) -> str:
        primary = candidate.primary_provenance()
        if primary == "agent_research" and candidate.found_in:
            return f"agent research ({candidate.found_in})"
        if primary == "discovered":
            return "discovered (" + ", ".join(candidate.sources[:3]) + ")"
        return primary.replace("_", " ")

    competitors: list[dict[str, Any]] = []
    for rank, item in enumerate(chosen, start=1):
        candidate = pool[item.domain]
        ad = ads[item.domain]
        profile = files.profiles.get(item.domain) or {}
        competitors.append({
            "type": "competitor",
            "rank": rank,
            "domain": item.domain,
            "name": item.decision["name"] or profile.get("name") or default_name(item.domain),
            "competitor_tier": item.tier,
            "reason": item.decision["reason"],
            "icp_match": profile.get("same_buyer"),
            "jtbd_match": profile.get("same_job"),
            "provenance": candidate.ordered_provenance(),
            "provenance_detail": provenance_detail(candidate),
            "found_in": candidate.found_in,
            **profile_fields(item.domain),
            "price_band": item.price_band,
            "comparable": item.comparable,
            "ad_activity": ad["ad_activity"],
            "ad_evidence": ad["ad_evidence"],
            "selection_group": GROUP_LABELS[item.group],
            "selection": _selection_text(item, ad, cap, direct_count),
            "override_reason": item.decision.get("override_reason"),
            "reviewed": item.domain in files.review["checked"],
            "sources": list(candidate.sources),
            "source_count": len(candidate.sources),
            "score": candidate.score(),
            "decided_by": "agent",
            "tier": "B" if (candidate.sources and len(candidate.sources) >= 2) or ad["ad_activity"] == "ads_seen" else "C",
        })

    profiled_out: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for item in sorted(over, key=lambda a: _order_key(a, ads, pool)):
        ad = ads[item.domain]
        excluded.append({
            "type": "excluded_candidate", "domain": item.domain, "competitor_tier": item.tier, "reason_code": "over_cap",
            "reason": f"over the cap of {cap}: {GROUP_LABELS[item.group]}, {AD_LABELS[ad['ad_activity']]}",
            "decided_by": "cap", "provenance": pool[item.domain].ordered_provenance(), "profiled": item.domain in files.profiles,
            **profile_fields(item.domain), "price_band": item.price_band, "ad_activity": ad["ad_activity"], "ad_evidence": ad["ad_evidence"],
            "override_reason": item.decision.get("override_reason"), "listed_for": [], "score": pool[item.domain].score(), "tier": "C",
        })
    for domain in sorted(assessments, key=lambda d: (assessments[d].reason_code, -pool[d].score(), d)):
        item = assessments[domain]
        if item.group is not None:
            continue
        excluded.append({
            "type": "excluded_candidate", "domain": domain, "competitor_tier": item.tier, "reason_code": item.reason_code,
            "reason": _not_eligible_reason(item, inputs.price_floor_usd), "decided_by": "agent" if item.tier == "excluded" else "rule",
            "provenance": pool[domain].ordered_provenance(), "profiled": domain in files.profiles, **profile_fields(domain),
            "price_band": item.price_band, "override_reason": item.decision.get("override_reason"),
            "listed_for": list(pool[domain].listed_for[:8]), "score": pool[domain].score(), "tier": "C",
        })
    profiled_out = [row for row in excluded if row.get("profiled")]
    decided = set(assessments)
    required_all = set(required1) | set(required2)
    for candidate in sorted(pool.values(), key=lambda c: (-c.score(), c.domain)):
        if candidate.domain in decided:
            continue
        if candidate.domain in required_all:
            continue  # unreachable: completeness requires a decision
        if candidate.round == 2 and not candidate.round1_signal():
            code, why = "round2_single_hit", "one relationship hit in round 2; not profiled"
        elif candidate.offer_signal():
            code, why = "over_profile_cap", f"over the profiling cap of {MAX_PROFILES_ROUND1}; not profiled"
        else:
            code, why = "weak_signal", "a single weak discovery hit; not profiled"
        excluded.append({
            "type": "excluded_candidate", "domain": candidate.domain, "reason_code": code, "reason": why, "decided_by": "profiling_list",
            "provenance": candidate.ordered_provenance(), "profiled": False, "listed_for": list(candidate.listed_for[:8]),
            "score": candidate.score(), "tier": "C",
        })
    for domain, queries in sorted(discovery.directories.items()):
        excluded.append({"type": "excluded_candidate", "domain": domain, "reason_code": "directory", "reason": "directory",
                         "decided_by": "noise_filter", "profiled": False, "listed_for": sorted(set(queries))[:8], "score": None, "tier": "C"})

    # Every pool domain already has a competitor or exclusion row; the
    # candidate rows (discovery facts) keep the strongest MAX_CANDIDATES.
    candidate_rows = [c.row() for c in sorted(pool.values(), key=lambda c: (-c.score(), c.domain))][:MAX_CANDIDATES]
    totals = client.ledger_totals()
    retrieved_on = totals["first_retrieved_on"] if totals["first_retrieved_on"] == totals["last_retrieved_on"] else f"{totals['first_retrieved_on']}..{totals['last_retrieved_on']}"
    listicle_pages = [files.listicles[url] for url in to_read if url in files.listicles]
    ad_counts = {key: sum(1 for ad in ads.values() if ad["ad_activity"] == key) for key in AD_ORDER}
    coverage = {
        "listicles_read": sum(1 for p in listicle_pages if p["status"] == "read"),
        "listicles_unreadable": sum(1 for p in listicle_pages if p["status"] == "unreadable"),
        "listicle_entries": sum(len(p["entries"]) for p in listicle_pages),
        "profiles": sum(1 for d in files.profiles if d in pool),
        "agent_additions": len(additions),
        "round2_seeds": seeds,
        "review_rounds": len(files.review["rounds"]),
        "objections_accepted": sum(1 for o in files.review["objections"] if o["resolution"] == "accepted"),
        "objections_rejected": sum(1 for o in files.review["objections"] if o["resolution"] == "rejected"),
        "missing_added": sum(1 for m in files.review["missing"] if m["resolution"] == "added"),
        "missing_rejected": sum(1 for m in files.review["missing"] if m["resolution"] == "rejected"),
        "ad_checks": len(checked_ads),
        "ad_counts": ad_counts,
    }
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "generated_by": Path(__file__).name,
        "retrieved_on": retrieved_on,
        "inputs": _inputs_block(inputs, cap),
        "composition_rule": {
            "roles": "caller-supplied roles with sourced profile and reason",
            "price": "recorded comparison only; no automatic floor",
            "order": "stable domain inspection order, not business priority",
            "operator_named": "explicitly named scope retained within the requested sample",
            "max_competitors": cap,
        },
        "enrichment": {key: value for key, value in coverage.items() if key != "ad_counts"} | {"ad_counts": ad_counts},
        "rows": discovery.summaries + candidate_rows + competitors + excluded,
        "totals": {key: totals[key] for key in ("dataforseo_calls", "search_calls", "spyfu_calls", "meta_searches", "page_fetches", "provider_calls", "rejected_calls")}
        | {"answered_queries": sum(1 for s in discovery.summaries if not s.get("unavailable"))},
    }
    section_markdown = render_section(
        inputs=inputs, cap=cap, competitors=competitors, profiled_out=profiled_out, excluded=excluded, summaries=discovery.summaries,
        pool_size=len(pool), coverage=coverage, totals=totals, retrieved_on=retrieved_on,
    )

    evidence_path = workspace / EVIDENCE_REL
    evidence_json = json.dumps(evidence, indent=1, ensure_ascii=False)
    _write_atomic(evidence_path, evidence_json)
    section_file = runtime / "result.md"
    _write_atomic(section_file, section_markdown)

    upsert = _load_script("upsert-markdown-section.py", "pmr_upsert_markdown_section")
    report_path = workspace / REPORT_REL
    report_path.parent.mkdir(parents=True, exist_ok=True)
    upsert.upsert_markdown_section(report_path, SECTION_HEADING, section_markdown)

    persist = _load_script("persist-research-report.py", "pmr_persist_research_report")
    persistence = persist.persist_research_report(
        workspace,
        commit_message=f"research: update {SECTION_HEADING.lower()} section",
        extra_paths=(Path(_artifact_path("egbe-docs/research/market/evidence/competitors.json")),),
    )

    legacy_source = {"operator_named": "explicit"}
    state = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "status": "completed",
        "domains": [row["domain"] for row in competitors],
        "domain_sources": {row["domain"]: legacy_source.get(row["provenance"][0], row["provenance"][0]) if row["provenance"] else "discovered" for row in competitors},
        "explicit_domains": inputs.named_domains,
        "page_domains": inputs.page_domains,
        "product_domain": inputs.product_domain,
        "category_phrases": inputs.category_phrases,
        "queries": inputs.category_queries + inputs.brand_queries,
        "price_floor_usd": inputs.price_floor_usd,
        "round2_seeds": seeds,
        "evidence_path": EVIDENCE_REL.as_posix(),
        "evidence_sha256": hashlib.sha256(evidence_json.encode("utf-8")).hexdigest(),
        "result_path": (RUNTIME_REL / "result.md").as_posix(),
        "result_sha256": hashlib.sha256(section_markdown.encode("utf-8")).hexdigest(),
        "intake_sha256": inputs.intake_sha256,
        "intake_path": inputs.intake_path,
        "inputs_path": (RUNTIME_REL / "inputs.json").as_posix(),
        "inputs_sha256": _sha(runtime / "inputs.json"),
        "decisions_sha256": _sha(files.paths["decisions"]),
        "profiles_sha256": _sha(files.paths["profiles"]),
        "listicles_sha256": _sha(files.paths["listicles"]),
        "review_sha256": _sha(files.paths["review"]),
        "provider_calls": totals["provider_calls"],
        "dataforseo_calls": totals["dataforseo_calls"],
        "search_calls": totals["search_calls"],
        "spyfu_calls": totals["spyfu_calls"],
        "meta_searches": totals["meta_searches"],
        "page_fetches": totals["page_fetches"],
        "rejected_calls": totals["rejected_calls"],
        "answered_queries": evidence["totals"]["answered_queries"],
        "provider_starts_recorded": totals["provider_starts_recorded"],
        "attempt_dataforseo_tasks": client.dataforseo_tasks,
        "attempt_search_calls": client.search_calls,
        "attempt_spyfu_calls": client.spyfu_calls,
        "attempt_meta_searches": client.meta_searches,
        "attempt_cache_hits": client.cache_hits,
        "report_commit_sha": persistence.commit_sha,
        "publication_mode": persistence.publication_mode,
        "research_context": _load_script("research-artifact-io.py", "pmr_input_io").context_binding(workspace, SECTION_ID),
        "error": None,
    }
    _write_atomic(runtime / "request.json", json.dumps(state, indent=1))
    return state


def default_name(domain: str) -> str:
    stem = registrable_domain(domain).split(".")[0]
    return stem[:1].upper() + stem[1:] if stem else domain


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--context-file", default=None, help="Optional explicitly selected provider-safe research context.")
    parser.add_argument("--intake", default="", help=f"Optional typed operation inputs (default: {INTAKE_REL.as_posix()}).")
    parser.add_argument("--domains", default="", help="Competitor domains named by the founder; overrides the intake's list.")
    parser.add_argument("--page-domains", default="", help="Competitors the product page mentions; ordinary candidates. Overrides the intake's list.")
    parser.add_argument("--product-domain", default="", help="The product's own domain; never a candidate and never a search seed.")
    parser.add_argument("--seed-keywords", default="", help="1-3 category phrases of the offer; override the intake's offer card.")
    parser.add_argument("--price-floor-usd", type=float, default=None, help="Comparable price floor; overrides the intake's offer card.")
    parser.add_argument("--decisions", default="", help=f"Path to the tiering decisions file (default: {RUNTIME_REL.as_posix()}/{DECISIONS_FILENAME}).")
    parser.add_argument("--max-competitors", type=int, default=MAX_COMPETITORS)
    parser.add_argument("--location-code", type=int, default=None, help="DataForSEO location (default: the intake's first market, else US).")
    parser.add_argument("--language-code", default="", help="Provider query language (default: en); retain the saved language on resume.")
    parser.add_argument("--country", default="", help="Primary market as a two-letter code (default: the intake's first market, else US).")
    parser.add_argument("--eu-country", default="", help="EU country for the official Meta Ad Library check (default: the first EU market, else DE).")
    parser.add_argument("--max-dataforseo-tasks", type=int, default=MAX_DATAFORSEO_TASKS_PER_ATTEMPT)
    parser.add_argument("--max-search-calls", type=int, default=MAX_SEARCH_CALLS_PER_ATTEMPT)
    parser.add_argument("--max-spyfu-calls", type=int, default=MAX_SPYFU_CALLS_PER_ATTEMPT, help="SpyFu lookups per attempt (0 disables the source).")
    parser.add_argument("--max-meta-searches", type=int, default=MAX_META_SEARCHES_PER_ATTEMPT)
    parser.add_argument("--max-fetches", type=int, default=MAX_FETCHES_PER_ATTEMPT)
    args = parser.parse_args()

    try:
        state = run(args.workspace, args)
    except (CompetitorSetError, ValueError) as exc:
        print(f"{DISPLAY_NAME}: {exc}", file=sys.stderr)
        return 1
    if state["status"] == "pending":
        print(
            f"{DISPLAY_NAME}: {state['reason']} — read {state['candidates_path']} (`missing`, `profile_required`, "
            f"`listicles_to_read`), write the enrichment files next to it (see the workflow doc), then rerun the same "
            "command; cached discovery adds no new spend.",
            file=sys.stderr,
        )
        return 2
    print(
        f"{DISPLAY_NAME}: completed — {len(state['domains'])} competitor(s), {state['dataforseo_calls']} DataForSEO "
        f"task(s), {state['spyfu_calls']} SpyFu lookup(s), {state['search_calls']} web search(es), evidence at "
        f"{state['evidence_path']}, report commit {(state['report_commit_sha'] or '')[:12] or 'n/a'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
