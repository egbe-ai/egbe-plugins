#!/usr/bin/env python3
"""Run the deterministic Community Demand section against community sources.

People asking for tools, describing workarounds, or naming prices in public
communities are demand evidence that precedes any paid channel: the exact
pain language feeds offers, and the communities themselves are organic and
paid placements (subreddit ads target subreddits). This runner collects
both from two sources:

  - Hacker News via the keyless Algolia search API (stories + comments;
    free, longitudinal);
  - fresh Reddit (last 12 months) via the Apify actor
    `trudax/reddit-scraper-lite` (posts + comments across all of Reddit —
    the official Reddit API is commercially unviable and is never used);
  - YouTube comments under the top videos per query (OS `/tools/youtube`,
    metered per claw against a fleet-shared Google quota) — best-effort:
    a failure is recorded as an excluded source, never a dead section.

Quotes are selected by a fixed, versioned marker-regex list (payment
language, pain language, tool-seeking language) — deterministic heuristics,
not comprehension. The community observation table is computed over EXACTLY the
quote rows persisted in the evidence file, so every published number is
reproducible from it. No LLM anywhere; synthesis into segment/offer/channel
hypotheses is a downstream concern. Caching, spend provenance, budgets and
retries mirror the Competitor Reviews runner.

Deliberately excluded (recorded as excluded_source rows): Product Hunt
(its GraphQL API cannot keyword-search launches — live-probed), Arctic
Shift (its search API cannot keyword-search across all of Reddit), and
Stack Exchange (v2 scope).
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
import html
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

SCHEMA_VERSION = 1
SECTION_ID = "community_demand"
SECTION_HEADING = "Communities analysis"
# H2s written by bundles that predate the founder-facing rename. The runner
# folds them into the canonical heading before materializing, so the report
# never carries this section under two names.
LEGACY_SECTION_HEADINGS = ("Community demand",)
DISPLAY_NAME = "Communities Analysis"

DEFAULT_OS_URL = "https://os.hz.egbe.dev"
HN_API_URL = "https://hn.algolia.com/api/v1"
RUNTIME_REL = Path(_artifact_path("egbe-docs/research/market/work")) / SECTION_ID
EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/community-demand.json"))
REPORT_REL = Path(_artifact_path("egbe-docs/research/market/full-report.md"))

REDDIT_ACTOR = "trudax/reddit-scraper-lite"

# One Reddit actor run, two HN calls, and up to three best-effort YouTube
# calls (one search + comments of the top videos) per query.
MAX_QUERIES = 5
MAX_ACTOR_RUNS_PER_ATTEMPT = 6
MAX_HN_CALLS_PER_ATTEMPT = 16
MAX_YT_CALLS_PER_ATTEMPT = 18
# 60 items fits Apify's 300s sync-endpoint ceiling; 100 exceeded it on a
# live run (HTTP 408 run-timeout-exceeded). Recall scales via MORE QUERIES,
# not deeper single runs.
REDDIT_ITEMS_PER_QUERY = 60
HN_STORY_HITS = 30
HN_COMMENT_HITS = 50
HN_RECENCY_DAYS = 3 * 365
YT_RECENCY_DAYS = 2 * 365
YT_SEARCH_RESULTS = 5
YT_VIDEOS_PER_QUERY = 2
YT_COMMENTS_PER_VIDEO = 50
MIN_QUOTE_CHARS = 30
TEXT_TRUNCATE = 400
STORED_QUOTES_CAP = 120
STORED_PER_COMMUNITY_CAP = 15

ACTOR_RETRY_DELAY_SECONDS = 20.0
HN_RETRY_DELAY_SECONDS = 5.0

# Versioned deterministic marker list (v1). Quotes are MARKER MATCHES, not
# classified meaning: the categories name which list matched, nothing more.
# Payment language must be precise, not broad: a bare dollar amount matches
# marketing scale-talk ("$100M SaaS") and job listings ("$30-40/hr"), so a
# money mention counts only NEAR a payment word, and explicit first-person
# pay phrases count on their own (validated on a live HN pull).
MARKER_LIST_VERSION = 1
_PAY_PHRASE_RE = re.compile(
    r"\b(?:would|i'?d|happy to|willing to|gladly|happily)\s+pay\b"
    r"|\bpay(?:ing)?\s+for\b|\bworth paying\b"
    r"|\bpaid\s+(?:plan|version|tier|tool|app)\b"
    r"|\btake my money\b",
    re.IGNORECASE,
)
# $100M/$2B are scale brags, not prices — the money marker rejects M/B/k
# magnitude suffixes.
_MONEY_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d{1,2})?(?![\dkKmMbB])"
    r"|\b\d+\s?(?:usd|dollars|bucks)\b",
    re.IGNORECASE,
)
_PAY_CONTEXT_RE = re.compile(
    r"\bpay(?:s|ing|ment)?\b|\bpaid\b|\bcosts?\b|\bprices?\b|\bpriced\b"
    r"|\bpricing\b|\bcharge[sd]?\b|\bsubscription\b|\bsubscribe[d]?\b"
    r"|\bbill(?:ed|ing)?\b|/mo\b|\bper\s+(?:month|year|seat|user)\b"
    r"|\ba\s+month\b|\ba\s+year\b",
    re.IGNORECASE,
)
_MONEY_CONTEXT_WINDOW = 60


def _wtp_marker_positions(text: str) -> list[int]:
    positions = [match.start() for match in _PAY_PHRASE_RE.finditer(text)]
    for money in _MONEY_RE.finditer(text):
        start = max(0, money.start() - _MONEY_CONTEXT_WINDOW)
        end = min(len(text), money.end() + _MONEY_CONTEXT_WINDOW)
        if _PAY_CONTEXT_RE.search(text[start:end]):
            positions.append(money.start())
    return positions
_PAIN_RE = re.compile(
    r"\bfrustrat\w*|\bannoy\w*|\bhate[sd]?\b|\bpainful\b|\btedious\b"
    r"|\bclunky\b|\bnightmare\b|\bdrives me (?:crazy|nuts|insane)\b"
    r"|\bwaste[sd]? (?:of )?(?:so much )?time\b|\bhours every (?:day|week)\b"
    r"|\bmanually\b|\bstruggl\w*|\bcan'?t stand\b|\btoo (?:slow|complicated)\b"
    r"|\bbuggy\b|\bunusable\b|\bgave up\b",
    re.IGNORECASE,
)
_SEEKING_RE = re.compile(
    r"\blooking for (?:a|an|some|any)\b|\bis there (?:a|an|any)\b"
    r"|\bany (?:good )?(?:recommendations?|alternatives?|tools?)\b"
    r"|\brecommend (?:a|an|any|me)\b|\balternative to\b"
    r"|\bwish there (?:was|were)\b|\bi wish (?:it|there|someone)\b"
    r"|\bdoes anyone (?:know|use)\b|\bwhat (?:do you|does everyone) use\b"
    r"|\bhow do you (?:all )?(?:manage|track|handle)\b",
    re.IGNORECASE,
)
# Price-sensitivity is its own diagnostic category, not a WTP signal: a
# segment repeatedly asking for "free/cheap" tools is a monetization
# warning that must be visible in the tables, not buried inside a seeking
# quote (the tutors' "ideally free" lesson from the first live run).
_PRICE_SENS_RE = re.compile(
    r"\bfree\b|\bfreemium\b|\bfree tier\b|\bcheap(?:er|est)?\b"
    r"|\baffordable\b|\bbudget\b|\blow[- ]cost\b|\binexpensive\b"
    r"|\btoo expensive\b|\boverpriced\b|\bpricey\b|\bcan(?:'|no)t afford\b",
    re.IGNORECASE,
)
_BOT_USERNAMES = {"automoderator", "sneakpeekbot", "remindmebot", "savevideo"}
_TAG_RE = re.compile(r"<[^>]+>")
# Sellers pitching their own product are not demand; separator-formatted
# classifieds (HN "Who is hiring"/"Who wants to be hired" comments, job
# posts) are listings, not demand language. All observed dominating a live
# relevance-sorted pull.
_PROMO_TITLE_RE = re.compile(r"^\s*(?:show|launch)\s+hn\b", re.IGNORECASE)
_JOBS_THREAD_RE = re.compile(
    r"who is hiring|who wants to be hired|seeking freelancer", re.IGNORECASE
)
# Reddit self-promo posts are sellers, not askers ("wanted to share a
# little tool me and my SO have been building" — slipped through the first
# live run as a seeking quote).
_SELF_PROMO_RE = re.compile(
    r"\b(?:i|we)(?:'ve| have)? (?:built|made|created|launched)\b"
    r"|\bwanted to share\b|\bsharing (?:my|our)\b|\bcheck out (?:my|our)\b"
    r"|\bmy (?:side |latest )?project\b",
    re.IGNORECASE,
)
_LISTING_MIN_SEPARATORS = 3
_LISTING_LABELS = (
    "location:",
    "remote:",
    "willing to relocate:",
    "technologies:",
    "compensation:",
    "salary:",
    "resume:",
    "résumé:",
)
# Query tokens too generic to anchor topical relevance on their own.
_GENERIC_QUERY_TOKENS = {
    "ai",
    "app",
    "apps",
    "best",
    "for",
    "free",
    "online",
    "platform",
    "service",
    "software",
    "the",
    "tool",
    "tools",
    "top",
    "web",
}

HN_COMMUNITY = "news.ycombinator.com"


class CommunityDemandError(RuntimeError):
    """Terminal runner failure; runtime state is preserved for resume."""


def _load_script(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise CommunityDemandError(f"cannot load bundled script {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


# ── mixed client: paid OS actor runs + free keyless HN calls ───────────────

@dataclass
class OsClient:
    os_url: str
    api_key: str
    cache_dir: Path
    max_actor_runs: int = MAX_ACTOR_RUNS_PER_ATTEMPT
    max_hn_calls: int = MAX_HN_CALLS_PER_ATTEMPT
    max_yt_calls: int = MAX_YT_CALLS_PER_ATTEMPT
    hn_url: str = HN_API_URL
    actor_runs: int = 0
    hn_calls: int = 0
    yt_calls: int = 0
    cache_hits: int = 0
    touched: set[str] = None  # type: ignore[assignment]  # set in __post_init__
    request: Callable[..., dict[str, Any]] | None = None
    hn_request: Callable[[str], dict[str, Any]] | None = None
    sleep: Callable[[float], None] | None = None

    def __post_init__(self) -> None:
        if self.touched is None:
            self.touched = set()

    def _http(self, path: str, payload: dict[str, Any], timeout: float, *, idempotency_key: str | None = None) -> dict[str, Any]:
        url = f"{self.os_url.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            for _name, _value in _connection_headers(req.full_url).items():
                req.add_unredirected_header(_name, _value)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                envelope = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise CommunityDemandError(f"OS {path} failed: HTTP {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise CommunityDemandError(f"OS {path} unreachable: {exc.reason}") from exc
        data = envelope.get("data")
        if envelope.get("code") not in (None, 200) or not isinstance(data, dict):
            raise CommunityDemandError(f"OS {path} returned no data: {str(envelope)[:300]}")
        return data

    def _hn_http(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            for _name, _value in _connection_headers(req.full_url).items():
                req.add_unredirected_header(_name, _value)
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                value = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise CommunityDemandError(f"HN search failed: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise CommunityDemandError(f"HN search unreachable: {exc.reason}") from exc
        if not isinstance(value, dict):
            raise CommunityDemandError("HN search returned a non-object response")
        return value

    def _cache_read(self, cache_file: Path) -> dict[str, Any] | None:
        if not cache_file.is_file():
            return None
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # A torn write must not poison replay forever: discard the
            # corrupt entry and refetch.
            cache_file.unlink(missing_ok=True)
            return None

    def _cache_write(self, cache_file: Path, entry: dict[str, Any]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = cache_file.with_suffix(".json.tmp")
        tmp_file.write_text(json.dumps(entry), encoding="utf-8")
        tmp_file.replace(cache_file)

    def run_actor(self, actor: str, actor_input: dict[str, Any], limit: int) -> tuple[list[dict[str, Any]], str]:
        payload = {"actor": actor, "input": actor_input, "sync": True, "limit": limit}
        key_raw = json.dumps({"kind": "actor", "payload": payload}, sort_keys=True)
        digest = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        self.touched.add(digest)
        entry = self._cache_read(cache_file)
        if entry is not None:
            self.cache_hits += 1
            rows = entry["response"].get("rows")
            return (
                rows if isinstance(rows, list) else []
            ), entry.get("retrieved_on") or date.today().isoformat()

        transport = self.request or self._http
        attempts = 0
        # Salted ONCE per call, before the retry loop: a within-call
        # transient-5xx retry must reuse the SAME wire key (so the gateway
        # can dedupe an ambiguous sync failure into one upstream run), but a
        # fresh call — a prior attempt having already failed and journaled a
        # start for this digest — must get a NEW key. The cache key (digest)
        # stays the pure payload hash so replay lookups are unaffected.
        wire_key = f"{digest}-{self._prior_start_count(digest)}"
        while True:
            # Paid starts count BEFORE the transport call (fail closed) and
            # are journaled durably: a failed start may still have billed.
            if self.actor_runs >= self.max_actor_runs:
                raise CommunityDemandError(
                    f"actor-run budget exhausted ({self.max_actor_runs} per "
                    "attempt); narrow the query list or re-run to continue "
                    "from cache"
                )
            self.actor_runs += 1
            self._journal_start(digest)
            try:
                response = transport(
                    "/scrape/apify/run", payload, 330.0, idempotency_key=wire_key
                )
                break
            except CommunityDemandError as exc:
                if attempts >= 1 or not re.search(r"HTTP 5\d\d", str(exc)):
                    raise
                attempts += 1
                (self.sleep or time.sleep)(ACTOR_RETRY_DELAY_SECONDS)
        retrieved_on = date.today().isoformat()
        self._cache_write(
            cache_file,
            {
                "kind": "actor",
                "payload": payload,
                "response": response,
                "retrieved_on": retrieved_on,
            },
        )
        rows = response.get("rows")
        return (rows if isinstance(rows, list) else []), retrieved_on

    def hn_search(
        self, query: str, tags: str, hits_per_page: int, created_after_epoch: int
    ) -> tuple[list[dict[str, Any]], str]:
        # The recency window lives in the QUERY (and therefore the cache
        # key): an all-time relevance page can fill up with old hits and
        # silently hide newer demand.
        params = urllib.parse.urlencode(
            {
                "query": query,
                "tags": tags,
                "hitsPerPage": hits_per_page,
                "numericFilters": f"created_at_i>{created_after_epoch}",
            }
        )
        url = f"{self.hn_url.rstrip('/')}/search?{params}"
        key_raw = json.dumps({"kind": "hn", "url": url}, sort_keys=True)
        digest = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        self.touched.add(digest)
        entry = self._cache_read(cache_file)
        if entry is not None:
            self.cache_hits += 1
            hits = entry["response"].get("hits")
            return (
                hits if isinstance(hits, list) else []
            ), entry.get("retrieved_on") or date.today().isoformat()

        transport = self.hn_request or self._hn_http
        attempts = 0
        while True:
            # Free calls are still bounded: a broken loop must not hammer a
            # keyless public API.
            if self.hn_calls >= self.max_hn_calls:
                raise CommunityDemandError(
                    f"HN call budget exhausted ({self.max_hn_calls} per attempt)"
                )
            self.hn_calls += 1
            try:
                response = transport(url)
                break
            except CommunityDemandError as exc:
                if attempts >= 1 or not re.search(r"HTTP 5\d\d", str(exc)):
                    raise
                attempts += 1
                (self.sleep or time.sleep)(HN_RETRY_DELAY_SECONDS)
        retrieved_on = date.today().isoformat()
        self._cache_write(
            cache_file,
            {
                "kind": "hn",
                "url": url,
                "response": response,
                "retrieved_on": retrieved_on,
            },
        )
        hits = response.get("hits")
        return (hits if isinstance(hits, list) else []), retrieved_on

    def yt_call(self, operation: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """One OS `/tools/youtube/<operation>` call. Metered per claw but
        free in money terms; bounded so a broken loop cannot drain the
        fleet-shared Google quota."""
        key_raw = json.dumps(
            {"kind": "yt", "operation": operation, "payload": payload}, sort_keys=True
        )
        digest = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        self.touched.add(digest)
        entry = self._cache_read(cache_file)
        if entry is not None:
            self.cache_hits += 1
            response = entry["response"]
            return (
                response if isinstance(response, dict) else {}
            ), entry.get("retrieved_on") or date.today().isoformat()

        transport = self.request or self._http
        attempts = 0
        while True:
            if self.yt_calls >= self.max_yt_calls:
                raise CommunityDemandError(
                    f"YouTube call budget exhausted ({self.max_yt_calls} per attempt)"
                )
            self.yt_calls += 1
            try:
                response = transport(f"/tools/youtube/{operation}", payload, 60.0)
                break
            except CommunityDemandError as exc:
                if attempts >= 1 or not re.search(r"HTTP 5\d\d", str(exc)):
                    raise
                attempts += 1
                (self.sleep or time.sleep)(HN_RETRY_DELAY_SECONDS)
        retrieved_on = date.today().isoformat()
        self._cache_write(
            cache_file,
            {
                "kind": "yt",
                "operation": operation,
                "payload": payload,
                "response": response,
                "retrieved_on": retrieved_on,
            },
        )
        return (response if isinstance(response, dict) else {}), retrieved_on

    def _journal_start(self, digest: str) -> None:
        """Append-only durable record of every PAID start, successful or not
        — the cache holds only successes, but failed sync starts may still
        have billed upstream."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with (self.cache_dir / "starts.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{date.today().isoformat()} {digest}\n")

    def _prior_start_count(self, digest: str) -> int:
        """Paid starts already journaled for this digest by EARLIER
        invocations — the salt for the wire Idempotency-Key. A failed
        attempt's key must never be replayed verbatim: on the gateway (see
        #3715), a client key can poison a wallet hold, and a byte-identical
        retry of a poisoned key fails identically forever."""
        starts_log = self.cache_dir / "starts.log"
        try:
            lines = starts_log.read_text(encoding="utf-8").splitlines()
        except OSError:
            return 0
        return sum(1 for line in lines if line.endswith(f" {digest}"))

    def ledger_totals(self) -> dict[str, Any]:
        """Durable provenance over entries THIS execution touched."""
        actor_entries = 0
        hn_entries = 0
        yt_entries = 0
        dates: list[str] = []
        if self.cache_dir.is_dir():
            for digest in sorted(self.touched):
                entry_path = self.cache_dir / f"{digest}.json"
                try:
                    entry = json.loads(entry_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                kind = entry.get("kind")
                if kind == "hn":
                    hn_entries += 1
                elif kind == "yt":
                    yt_entries += 1
                else:
                    actor_entries += 1
                if isinstance(entry.get("retrieved_on"), str):
                    dates.append(entry["retrieved_on"])
        today = date.today().isoformat()
        starts_log = self.cache_dir / "starts.log"
        try:
            starts_recorded = sum(
                1 for line in starts_log.read_text(encoding="utf-8").splitlines() if line
            )
        except OSError:
            starts_recorded = 0
        return {
            "actor_runs": actor_entries,
            "provider_calls": actor_entries,
            "hn_calls": hn_entries,
            "youtube_calls": yt_entries,
            "actor_starts_recorded": starts_recorded,
            "first_retrieved_on": min(dates) if dates else today,
            "last_retrieved_on": max(dates) if dates else today,
        }


# ── deterministic helpers ──────────────────────────────────────────────────

def _clean(value: Any) -> Any:
    """Apify actors serialize empty fields as the literal string 'None'."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in ("", "None", "null"):
        return None
    return value


def _to_int(value: Any) -> int | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _plain_text(value: Any) -> str:
    """HTML-decode, strip tags (HN comment_text carries markup), collapse
    whitespace."""
    text = html.unescape(str(_clean(value) or ""))
    text = _TAG_RE.sub(" ", text)
    return " ".join(text.split())


def _truncate(text: str, cap: int) -> str:
    if len(text) <= cap:
        return text
    cut = text[:cap].rsplit(" ", 1)[0].rstrip()
    return (cut or text[:cap].rstrip()) + "…"


# A long comment can mention the category once and rant about something
# else: a marker is topical only NEAR a query anchor token (validated on a
# live pull where AI-industry rants outnumbered category demand).
_ANCHOR_PROXIMITY_WINDOW = 120


def _anchor_positions(text: str, query: str) -> list[int] | None:
    """None means the query is fully generic and imposes no anchor."""
    anchors = query_anchor_tokens(query)
    if not anchors:
        return None
    lowered = text.lower()
    return [
        match.start()
        for anchor in anchors
        for match in re.finditer(rf"\b{re.escape(anchor)}", lowered)
    ]


def _near_any(positions: list[int] | None, marker_positions: list[int]) -> bool:
    if not marker_positions:
        return False
    if positions is None:
        return True
    return any(
        abs(marker - anchor) <= _ANCHOR_PROXIMITY_WINDOW
        for marker in marker_positions
        for anchor in positions
    )


def matched_categories(text: str, query: str = "") -> list[str]:
    anchor_positions = _anchor_positions(text, query) if query else None
    if anchor_positions is not None and not anchor_positions:
        return []  # anchored query, text never mentions the category
    categories: list[str] = []
    if _near_any(anchor_positions, _wtp_marker_positions(text)):
        categories.append("wtp")
    if _near_any(
        anchor_positions, [m.start() for m in _SEEKING_RE.finditer(text)]
    ):
        categories.append("seeking")
    if _near_any(
        anchor_positions, [m.start() for m in _PAIN_RE.finditer(text)]
    ):
        categories.append("pain")
    if _near_any(
        anchor_positions, [m.start() for m in _PRICE_SENS_RE.finditer(text)]
    ):
        categories.append("price_sensitivity")
    return categories


def parse_context_tokens(raw: str) -> list[str]:
    tokens: list[str] = []
    for part in re.split(r"[,;\n]", raw or ""):
        token = re.sub(r"[^a-z0-9]", "", part.strip().lower())
        if len(token) >= 2 and token not in tokens:
            tokens.append(token)
    return tokens[:8]


def mentions_product_context(text: str, context_tokens: list[str]) -> bool:
    """Does the text speak to THIS product's mechanism (e.g. 'ai', 'agent')
    rather than the bare category? Short tokens match exact words ('ai'
    must not match 'aim'); longer ones are prefix-tolerant."""
    lowered = text.lower()
    for token in context_tokens:
        pattern = (
            rf"\b{re.escape(token)}\b" if len(token) <= 3 else rf"\b{re.escape(token)}"
        )
        if re.search(pattern, lowered):
            return True
    return False


def is_listing(text: str) -> bool:
    """Separator-formatted classifieds (job posts, 'Who is hiring' entries)
    and labeled hire-me templates."""
    if text.count(" | ") + text.count(" / ") >= _LISTING_MIN_SEPARATORS:
        return True
    lowered = text.lower()
    return sum(1 for label in _LISTING_LABELS if label in lowered) >= 2


def query_anchor_tokens(query: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if len(token) >= 3 and token not in _GENERIC_QUERY_TOKENS
    ]




def parse_terms(raw: str, cap: int) -> list[str]:
    seen: dict[str, None] = {}
    for part in re.split(r"[,;\n]", raw or ""):
        term = " ".join(part.strip().lower().split())
        if term and term not in seen:
            seen[term] = None
    return list(seen)[:cap]



def select_queries(
    explicit: list[str], discovered: list[str], cap: int
) -> tuple[list[str], dict[str, str]]:
    """Merge explicit seeds ahead of KWE-discovered keywords, dropping
    token-set duplicates ('online whiteboard online' is the same query as
    'online whiteboard' — a KWE keyword-variant artifact)."""
    queries: list[str] = []
    query_sources: dict[str, str] = {}
    seen_token_sets: set[frozenset[str]] = set()
    for query, source in [(q, "explicit") for q in explicit] + [
        (q, "keyword_economics") for q in discovered
    ]:
        if len(queries) >= cap:
            break
        token_set = frozenset(re.findall(r"[a-z0-9]+", query))
        if not token_set or token_set in seen_token_sets:
            continue
        seen_token_sets.add(token_set)
        queries.append(query)
        query_sources[query] = source
    return queries, query_sources


def queries_from_keyword_evidence(workspace: Path, cap: int) -> list[str]:
    evidence = _load_script("research-evidence.py", "pmr_evidence")
    return evidence.keyword_inputs(workspace, consumer=SECTION_ID, row_type="keyword", field="keyword", cap=cap)


# ── normalization: one raw item -> one candidate quote ─────────────────────

def normalize_hn_story(hit: dict[str, Any], query: str) -> dict[str, Any] | None:
    object_id = str(_clean(hit.get("objectID")) or "")
    title = _plain_text(hit.get("title"))
    body = _plain_text(hit.get("story_text"))
    text = " ".join(part for part in (title, body) if part)
    if not object_id or not text:
        return None
    if _PROMO_TITLE_RE.search(title):
        return None  # the author is selling, not asking
    return {
        "id": f"hn_{object_id}",
        "source": "hackernews",
        "community": HN_COMMUNITY,
        "kind": "story",
        "query": query,
        "text": text,
        "url": f"https://news.ycombinator.com/item?id={object_id}",
        "votes": _to_int(hit.get("points")) or 0,
        "replies": _to_int(hit.get("num_comments")),
        "created": str(_clean(hit.get("created_at")) or "")[:10] or None,
    }


def normalize_hn_comment(hit: dict[str, Any], query: str) -> dict[str, Any] | None:
    object_id = str(_clean(hit.get("objectID")) or "")
    text = _plain_text(hit.get("comment_text"))
    if not object_id or not text:
        return None
    if _JOBS_THREAD_RE.search(str(_clean(hit.get("story_title")) or "")):
        return None  # monthly jobs threads are classifieds, not demand
    return {
        "id": f"hn_{object_id}",
        "source": "hackernews",
        "community": HN_COMMUNITY,
        "kind": "comment",
        "query": query,
        "text": text,
        "url": f"https://news.ycombinator.com/item?id={object_id}",
        "votes": _to_int(hit.get("points")) or 0,
        "replies": None,
        "created": str(_clean(hit.get("created_at")) or "")[:10] or None,
    }


def normalize_reddit_row(row: dict[str, Any], query: str) -> dict[str, Any] | None:
    data_type = str(_clean(row.get("dataType")) or "")
    if data_type not in ("post", "comment"):
        return None
    row_id = str(_clean(row.get("id")) or "")
    community = str(
        _clean(row.get("parsedCommunityName"))
        or str(_clean(row.get("communityName")) or "").removeprefix("r/")
        or ""
    ).strip()
    username = str(_clean(row.get("username")) or "").strip().lower()
    title = _plain_text(row.get("title")) if data_type == "post" else ""
    body = _plain_text(row.get("body"))
    text = " ".join(part for part in (title, body) if part)
    if not row_id or not community or not text:
        return None
    if username in _BOT_USERNAMES or "i am a bot" in text.lower():
        return None
    if data_type == "post" and _SELF_PROMO_RE.search(text):
        return None  # the author is selling, not asking
    url = str(_clean(row.get("url")) or _clean(row.get("link")) or "")
    if not url:
        permalink = str(_clean(row.get("permalink")) or "")
        url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else ""
    return {
        "id": f"reddit_{row_id}",
        "source": "reddit",
        "community": f"r/{community}",
        "kind": data_type,
        "query": query,
        "text": text,
        "url": url or None,
        "votes": _to_int(row.get("upVotes")) or 0,
        "replies": _to_int(row.get("numberOfComments") if data_type == "post" else row.get("numberOfReplies")),
        "created": str(_clean(row.get("createdAt")) or "")[:10] or None,
    }


def normalize_youtube_comment(
    row: dict[str, Any], query: str, video: dict[str, Any]
) -> dict[str, Any] | None:
    comment_id = str(_clean(row.get("comment_id")) or "")
    video_id = str(_clean(row.get("video_id")) or _clean(video.get("video_id")) or "")
    text = _plain_text(row.get("text"))
    if not comment_id or not video_id or not text:
        return None
    return {
        "id": f"yt_{comment_id}",
        "source": "youtube",
        "community": "youtube.com",
        "kind": "comment",
        "query": query,
        "text": text,
        "url": f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
        "votes": _to_int(row.get("like_count")) or 0,
        "replies": _to_int(row.get("reply_count")),
        "created": str(_clean(row.get("published_at")) or "")[:10] or None,
        "video_title": _truncate(_plain_text(video.get("title")), 120) or None,
    }


def to_quote_row(
    candidate: dict[str, Any], hn_cutoff: str, context_tokens: list[str]
) -> dict[str, Any] | None:
    """Marker-match one normalized candidate into an evidence quote row."""
    text = candidate["text"]
    if len(text) < MIN_QUOTE_CHARS:
        return None
    if is_listing(text):
        return None
    if candidate["source"] == "hackernews":
        created = candidate.get("created")
        if created is not None and created < hn_cutoff:
            return None
    categories = matched_categories(text, candidate["query"])
    if not categories:
        return None
    quote = {
        "type": "community_quote",
        "id": candidate["id"],
        "source": candidate["source"],
        "community": candidate["community"],
        "kind": candidate["kind"],
        "query": candidate["query"],
        "categories": categories,
        "has_dollar_amount": bool(_MONEY_RE.search(text)),
        # Category demand vs THIS product's mechanism: a quote about
        # human-to-human realtime collaboration is not evidence for an
        # AI-agent whiteboard even when both say "whiteboard".
        "product_context": mentions_product_context(text, context_tokens)
        if context_tokens
        else None,
        "text": _truncate(text, TEXT_TRUNCATE),
        "url": candidate.get("url"),
        "votes": candidate.get("votes") or 0,
        "replies": candidate.get("replies"),
        "created": candidate.get("created"),
        "tier": "A",
    }
    if candidate.get("video_title"):
        quote["video_title"] = candidate["video_title"]
    return quote


def _created_recency_key(quote: dict[str, Any]) -> int:
    """Newest first, missing/unparsable dates last (0 sorts after every
    negated real date)."""
    digits = re.sub(r"[^0-9]", "", str(quote.get("created") or ""))[:8]
    return -int(digits) if len(digits) == 8 else 0


def select_stored_quotes(quotes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bounded observation sample: newest first, stable ID ties.
    Per-community caps prevent one thread population consuming the sample;
    payment markers and votes do not grant evidence priority."""
    ranked = sorted(quotes, key=lambda q: (_created_recency_key(q), q["id"]))
    stored: list[dict[str, Any]] = []
    per_community: dict[str, int] = {}
    for quote in ranked:
        if len(stored) >= STORED_QUOTES_CAP:
            break
        count = per_community.get(quote["community"], 0)
        if count >= STORED_PER_COMMUNITY_CAP:
            continue
        per_community[quote["community"]] = count + 1
        stored.append(quote)
    return stored


def summarize_communities(stored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_community: dict[str, list[dict[str, Any]]] = {}
    for quote in stored:
        by_community.setdefault(quote["community"], []).append(quote)
    rows: list[dict[str, Any]] = []
    for community, quotes in by_community.items():
        wtp = sum(1 for q in quotes if "wtp" in q["categories"])
        seeking = sum(1 for q in quotes if "seeking" in q["categories"])
        pain = sum(1 for q in quotes if "pain" in q["categories"])
        price_sens = sum(
            1 for q in quotes if "price_sensitivity" in q["categories"]
        )
        product_context = sum(1 for q in quotes if q.get("product_context"))
        votes = sum(q["votes"] for q in quotes)
        sample = min(quotes, key=lambda q: (_created_recency_key(q), q["id"]))
        rows.append(
            {
                "type": "community",
                "community": community,
                "source": quotes[0]["source"],
                "quotes": len(quotes),
                "wtp_quotes": wtp,
                "seeking_quotes": seeking,
                "pain_quotes": pain,
                "price_sensitivity_quotes": price_sens,
                "product_context_quotes": product_context,
                "votes_on_quotes": votes,
                "latest_quote_date": max((q.get("created") or "" for q in quotes), default="") or None,
                "sample_url": sample.get("url"),
                "tier": "A",
            }
        )
    rows.sort(key=lambda r: r["community"])
    return rows


def excluded_source_rows(youtube_failure: str | None) -> list[dict[str, Any]]:
    rows = [
        {
            "type": "excluded_source",
            "source": "product_hunt",
            "reason": "GraphQL API v2 cannot keyword-search launches (no "
            "post search, coarse topics, url filter does not match "
            "domains); excluded after live probes 2026-08-19",
            "tier": "C",
        },
        {
            "type": "excluded_source",
            "source": "arctic_shift",
            "reason": "search API cannot keyword-search across all of Reddit "
            "(per-subreddit only); deferred to v2",
            "tier": "C",
        },
        {
            "type": "excluded_source",
            "source": "stack_exchange",
            "reason": "v2 scope",
            "tier": "C",
        },
    ]
    if youtube_failure:
        # YouTube is best-effort: the fleet-shared Google quota or an
        # undeployed gateway must not fail the whole section, but the gap
        # is recorded, never silent.
        rows.append(
            {
                "type": "excluded_source",
                "source": "youtube",
                "reason": youtube_failure,
                "tier": "C",
            }
        )
    return rows


# ── rendering ──────────────────────────────────────────────────────────────

def _quote_cell(quote: dict[str, Any], cap: int = 200) -> str:
    text = _truncate(quote["text"], cap).replace("|", "/")
    if quote.get("url"):
        return f"[{text}]({quote['url']})"
    return text


def render_section(
    *,
    queries: list[str],
    query_sources: dict[str, str],
    product_context: list[str],
    search_summaries: list[dict[str, Any]],
    communities: list[dict[str, Any]],
    stored_quotes: list[dict[str, Any]],
    excluded_sources: list[dict[str, Any]],
    totals: dict[str, Any],
    retrieved_on: str,
) -> str:
    lines: list[str] = []
    add = lines.append

    add(
        f"Public community posts and comments retrieved {retrieved_on} from "
        "Hacker News (keyless Algolia search; stories and comments, last "
        f"{HN_RECENCY_DAYS // 365} years), Reddit (Apify actor search "
        "across all subreddits, posts and comments from the last 12 "
        "months), and YouTube (comments under the top videos for each "
        f"query, videos from the last {YT_RECENCY_DAYS // 365} years; "
        "best-effort). Quotes are selected by a fixed marker-regex list "
        f"(v{MARKER_LIST_VERSION}: payment language, tool-seeking language, "
        "pain language, price-sensitivity language) — deterministic keyword "
        "heuristics, not comprehension, so category counts measure marker "
        "density, not verified intent. All aggregates below are computed "
        "over exactly the quote rows persisted in the evidence file; "
        "hypothesis synthesis happens downstream."
    )
    add("")
    add(
        "Queries searched: "
        + ", ".join(f"`{q}` ({query_sources.get(q, 'explicit')})" for q in queries)
        + "."
    )
    add("")
    if product_context:
        add(
            "Product-context tokens: "
            + ", ".join(f"`{t}`" for t in product_context)
            + ". A quote marked product-context mentions this product's "
            "MECHANISM; all other quotes are bare category demand that may "
            "belong to different mechanics (for example human-to-human "
            "realtime collaboration versus working with an AI agent) — do "
            "not read them as segment evidence for this product without "
            "checking the quote itself."
        )
        add("")

    add("### Search coverage")
    add("")
    add("| Query | Source | Items retrieved | Marker-matched quotes | Stored |")
    add("| --- | --- | ---: | ---: | ---: |")
    for summary in search_summaries:
        add(
            f"| {summary['query']} | {summary['source']} | "
            f"{summary['retrieved']} | {summary['matched']} | "
            f"{summary['stored']} |"
        )
    add("")

    if communities:
        add("### Community observations")
        add("")
        context_col = " Product-context |" if product_context else ""
        add(
            "| Community | Quotes | Payment | Seeking | Pain | Price-sens |"
            f"{context_col} Votes on quotes | Latest |"
        )
        add(
            "| --- | ---: | ---: | ---: | ---: | ---: |"
            + (" ---: |" if product_context else "")
            + " ---: | --- |"
        )
        for row in communities:
            context_cell = (
                f" {row['product_context_quotes']} |" if product_context else ""
            )
            add(
                f"| {row['community']} | {row['quotes']} | {row['wtp_quotes']} | "
                f"{row['seeking_quotes']} | {row['pain_quotes']} | "
                f"{row['price_sensitivity_quotes']} |{context_cell} "
                f"{row['votes_on_quotes']} | {row['latest_quote_date'] or '—'} |"
            )
        add("")
        add(
            "Counts describe marker matches in the stored sample, not buyer intent, "
            "relative evidence strength or a channel recommendation. A "
            "community's absence here means the searched queries surfaced "
            "nothing marker-matched — weak evidence, not proof of no "
            "demand."
        )
        add("")

    wtp_quotes = [q for q in stored_quotes if "wtp" in q["categories"]]
    if wtp_quotes:
        add("### Payment-language quotes")
        add("")
        context_col = " Product-ctx |" if product_context else ""
        add(f"| Community | Date | Votes |{context_col} Quote |")
        add(
            "| --- | --- | ---: |"
            + (" :-: |" if product_context else "")
            + " --- |"
        )
        for quote in wtp_quotes[:6]:
            context_cell = (
                (" ✓ |" if quote.get("product_context") else " — |")
                if product_context
                else ""
            )
            add(
                f"| {quote['community']} | {quote['created'] or '—'} | "
                f"{quote['votes']} |{context_cell} {_quote_cell(quote)} |"
            )
        add("")

    other_quotes = [
        q for q in stored_quotes if "wtp" not in q["categories"]
    ]
    if other_quotes:
        add("### Seeking, pain, and price-sensitivity quotes")
        add("")
        context_col = " Product-ctx |" if product_context else ""
        add(f"| Community | Date | Votes | Markers |{context_col} Quote |")
        add(
            "| --- | --- | ---: | --- |"
            + (" :-: |" if product_context else "")
            + " --- |"
        )
        for quote in other_quotes[:10]:
            context_cell = (
                (" ✓ |" if quote.get("product_context") else " — |")
                if product_context
                else ""
            )
            add(
                f"| {quote['community']} | {quote['created'] or '—'} | "
                f"{quote['votes']} | {', '.join(quote['categories'])} |"
                f"{context_cell} {_quote_cell(quote)} |"
            )
        add("")

    add("### Method and coverage")
    add("")
    add(
        f"- Spend recorded: {totals['actor_runs']} Reddit actor run(s), "
        f"{totals['hn_calls']} free HN API call(s), and "
        f"{totals['youtube_calls']} metered YouTube API call(s), "
        "accumulated across attempts; cached replays add no new spend."
    )
    add(
        f"- Caps: {MAX_QUERIES} queries, {REDDIT_ITEMS_PER_QUERY} Reddit "
        f"items per query, {HN_STORY_HITS}+{HN_COMMENT_HITS} HN hits per "
        f"query, {YT_VIDEOS_PER_QUERY}×{YT_COMMENTS_PER_VIDEO} YouTube "
        f"comments per query, {STORED_QUOTES_CAP} stored quotes "
        f"({STORED_PER_COMMUNITY_CAP} per community)."
    )
    add(
        "- Excluded deterministically: Show HN/Launch HN stories and "
        "self-promo Reddit posts (sellers, not askers), jobs-thread "
        "comments and separator-formatted classifieds, known bots. A "
        f"marker counts only within {_ANCHOR_PROXIMITY_WINDOW} characters "
        "of a non-generic query token, and money mentions count as payment "
        "language only near a payment word ($100M scale-talk does not)."
    )
    add(
        "- Sources excluded from this run (recorded as excluded_source "
        "rows in the evidence file): "
        + "; ".join(f"{row['source']} — {row['reason']}" for row in excluded_sources)
        + ". Communities over-represent complainers and early adopters; "
        "marker matching misses paraphrased demand and admits some noise."
    )
    add("")
    add("### Sources")
    add("")
    add(
        f"- Hacker News via the keyless Algolia API; Reddit via Apify "
        f"`{REDDIT_ACTOR}`; YouTube via the Data API v3 (search + comment "
        f"threads) — retrieved {retrieved_on}; the stored quote rows in "
        f"`{EVIDENCE_REL.as_posix()}` are exactly the set every table "
        "above is computed from (texts truncated for storage, markers "
        "matched on full text before truncation)."
    )
    return "\n".join(lines).strip() + "\n"


# ── orchestration ──────────────────────────────────────────────────────────

@dataclass
class RunInputs:
    queries: list[str]
    query_sources: dict[str, str]
    product_context: list[str]


def collect_youtube(client: OsClient, query: str, published_after: str) -> tuple[list[dict[str, Any]], int]:
    """One search plus comment pulls for the top videos. Raises on provider
    failure; the caller decides best-effort semantics."""
    search, _ = client.yt_call(
        "search",
        {
            "query": query,
            "max_results": YT_SEARCH_RESULTS,
            "order": "relevance",
            "published_after": published_after,
        },
    )
    videos = [v for v in (search.get("rows") or []) if isinstance(v, dict)]
    candidates: list[dict[str, Any]] = []
    retrieved = 0
    for video in videos[:YT_VIDEOS_PER_QUERY]:
        threads, _ = client.yt_call(
            "comment-threads",
            {
                "video_id": video.get("video_id"),
                "max_results": YT_COMMENTS_PER_VIDEO,
                "order": "relevance",
            },
        )
        rows = [r for r in (threads.get("rows") or []) if isinstance(r, dict)]
        retrieved += len(rows)
        candidates.extend(
            c
            for c in (normalize_youtube_comment(r, query, video) for r in rows)
            if c
        )
    return candidates, retrieved


def _call_with_context(client: OsClient, query: str, label: str, fn: Callable[[], Any]) -> Any:
    """Re-raise a provider-call failure with WHICH query/call failed and how
    much of the attempt's paid budget is already spent — the raw gateway
    envelope alone doesn't say either, so a human can't tell whether a retry
    is even possible without this."""
    try:
        return fn()
    except CommunityDemandError as exc:
        raise CommunityDemandError(
            f"{label} for `{query}` failed: {exc} — this attempt had "
            f"already started {client.actor_runs}/{client.max_actor_runs} "
            "actor run(s); see GET /me/limits?resource=apify:runs for "
            "remaining daily quota."
        ) from exc


def run_pipeline(client: OsClient, inputs: RunInputs) -> dict[str, Any]:
    if not inputs.queries:
        raise CommunityDemandError(
            "no seed queries available: pass --seed-keywords with 1-5 "
            "category or problem phrases derived from the research assignment (see the "
            "workflow doc), or complete the Keyword Economics section first"
        )

    hn_cutoff_date = date.today() - timedelta(days=HN_RECENCY_DAYS)
    hn_cutoff = hn_cutoff_date.isoformat()
    # Midnight-UTC epoch: stable within a day, so same-day replays hit the
    # cache while a fresh attempt on a later day refetches.
    hn_cutoff_epoch = int(
        datetime.combine(hn_cutoff_date, datetime.min.time(), tzinfo=timezone.utc).timestamp()
    )
    yt_published_after = (
        date.today() - timedelta(days=YT_RECENCY_DAYS)
    ).isoformat() + "T00:00:00Z"
    candidates: list[dict[str, Any]] = []
    retrieval_counts: list[dict[str, Any]] = []
    youtube_failure: str | None = None

    for query in inputs.queries:
        story_hits, _ = client.hn_search(query, "story", HN_STORY_HITS, hn_cutoff_epoch)
        comment_hits, _ = client.hn_search(query, "comment", HN_COMMENT_HITS, hn_cutoff_epoch)
        reddit_rows, _ = _call_with_context(
            client,
            query,
            "Reddit",
            lambda: client.run_actor(
                REDDIT_ACTOR,
                {
                    "searches": [query],
                    "searchPosts": True,
                    "searchComments": True,
                    "searchCommunities": False,
                    "searchUsers": False,
                    "skipUserPosts": True,
                    "includeMediaLinks": True,
                    "sort": "relevance",
                    "time": "year",
                    "maxItems": REDDIT_ITEMS_PER_QUERY,
                    "proxy": {"useApifyProxy": True},
                },
                limit=REDDIT_ITEMS_PER_QUERY,
            ),
        )

        hn_candidates = [
            c
            for c in (
                [normalize_hn_story(h, query) for h in story_hits]
                + [normalize_hn_comment(h, query) for h in comment_hits]
            )
            if c
        ]
        reddit_candidates = [
            c for c in (normalize_reddit_row(r, query) for r in reddit_rows) if c
        ]
        candidates.extend(hn_candidates)
        candidates.extend(reddit_candidates)
        retrieval_counts.append(
            {
                "query": query,
                "source": "hackernews",
                "retrieved": len(story_hits) + len(comment_hits),
                "normalized": len(hn_candidates),
            }
        )
        retrieval_counts.append(
            {
                "query": query,
                "source": "reddit",
                "retrieved": len(reddit_rows),
                "normalized": len(reddit_candidates),
            }
        )
        if youtube_failure is None:
            try:
                yt_candidates, yt_retrieved = collect_youtube(
                    client, query, yt_published_after
                )
            except CommunityDemandError as exc:
                # Best-effort: an undeployed provider or exhausted
                # fleet-shared quota degrades to a recorded exclusion, never
                # a silent gap and never a failed section.
                youtube_failure = f"unavailable during this run: {str(exc)[:200]}"
            else:
                candidates.extend(yt_candidates)
                retrieval_counts.append(
                    {
                        "query": query,
                        "source": "youtube",
                        "retrieved": yt_retrieved,
                        "normalized": len(yt_candidates),
                    }
                )

    # The same item can match several queries: first query wins, once.
    seen_ids: set[str] = set()
    quotes: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate["id"] in seen_ids:
            continue
        seen_ids.add(candidate["id"])
        quote = to_quote_row(candidate, hn_cutoff, inputs.product_context)
        if quote:
            quotes.append(quote)

    stored_quotes = select_stored_quotes(quotes)
    communities = summarize_communities(stored_quotes)

    search_summaries = [
        {
            "type": "search_summary",
            "query": count["query"],
            "source": count["source"],
            "retrieved": count["retrieved"],
            "matched": sum(
                1
                for q in quotes
                if q["query"] == count["query"] and q["source"] == count["source"]
            ),
            "stored": sum(
                1
                for q in stored_quotes
                if q["query"] == count["query"] and q["source"] == count["source"]
            ),
            "tier": "A",
        }
        for count in retrieval_counts
    ]

    totals = client.ledger_totals()
    retrieved_on = (
        totals["first_retrieved_on"]
        if totals["first_retrieved_on"] == totals["last_retrieved_on"]
        else f"{totals['first_retrieved_on']}..{totals['last_retrieved_on']}"
    )

    excluded_sources = excluded_source_rows(youtube_failure)
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "generated_by": Path(__file__).name,
        "retrieved_on": retrieved_on,
        "marker_list_version": MARKER_LIST_VERSION,
        "inputs": {
            "queries": inputs.queries,
            "query_sources": inputs.query_sources,
            "product_context": inputs.product_context,
        },
        "rows": (
            search_summaries
            + communities
            + stored_quotes
            + excluded_sources
        ),
        "totals": {
            "actor_runs": totals["actor_runs"],
            "provider_calls": totals["provider_calls"],
            "hn_calls": totals["hn_calls"],
            "youtube_calls": totals["youtube_calls"],
        },
    }

    section_markdown = render_section(
        queries=inputs.queries,
        query_sources=inputs.query_sources,
        product_context=inputs.product_context,
        search_summaries=search_summaries,
        communities=communities,
        stored_quotes=stored_quotes,
        excluded_sources=excluded_sources,
        totals=totals,
        retrieved_on=retrieved_on,
    )
    return {
        "evidence": evidence,
        "section_markdown": section_markdown,
        "totals": totals,
        "attempt": {
            "actor_runs": client.actor_runs,
            "hn_calls": client.hn_calls,
            "yt_calls": client.yt_calls,
            "cache_hits": client.cache_hits,
        },
    }


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _canonicalize_legacy_headings(upsert: ModuleType, report_path: Path) -> None:
    """Fold pre-rename legacy H2s of this section into the canonical heading.

    A report materialized by an older bundle keeps `## Community demand`; the
    PRD extractor and this runner's upsert address the canonical H2 only, so a
    stale legacy heading would either fail extraction or make the section
    coexist under two names after a rerun. Rename the legacy H2 in place, or
    drop the stale legacy section when a canonical one already exists.
    """
    if not report_path.is_file():
        return
    text = report_path.read_text(encoding="utf-8")
    changed = False
    for legacy in LEGACY_SECTION_HEADINGS:
        while True:
            offsets = upsert._h2_offsets(text)
            match = next(
                (
                    (index, offset)
                    for index, (name, offset) in enumerate(offsets)
                    if name == legacy
                ),
                None,
            )
            if match is None:
                break
            canonical_present = any(
                name == SECTION_HEADING for name, _ in offsets
            )
            index, start = match
            if canonical_present:
                end = (
                    offsets[index + 1][1]
                    if index + 1 < len(offsets)
                    else len(text)
                )
                text = text[:start] + text[end:]
            else:
                line_end = text.find("\n", start)
                if line_end == -1:
                    line_end = len(text)
                text = text[:start] + f"## {SECTION_HEADING}" + text[line_end:]
            changed = True
    if changed:
        _write_atomic(report_path, text)


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
        raise CommunityDemandError("OS_API_KEY is required")
    os_url = (os.environ.get("OS_URL") or DEFAULT_OS_URL).strip() or DEFAULT_OS_URL

    explicit = parse_terms(args.seed_keywords or "", MAX_QUERIES)
    discovered = queries_from_keyword_evidence(workspace, MAX_QUERIES)
    queries, query_sources = select_queries(explicit, discovered, args.max_queries)
    # One actor run and two HN calls per query: never admit more queries
    # than the required budgets can finish in one attempt (YouTube is
    # best-effort and merely stops when its own budget runs out).
    queries = queries[: max(1, min(args.max_actor_runs, args.max_hn_calls // 2))]
    query_sources = {q: query_sources[q] for q in queries}

    inputs = RunInputs(
        queries=queries,
        query_sources=query_sources,
        product_context=parse_context_tokens(args.product_context or ""),
    )
    client = OsClient(
        os_url=os_url,
        api_key=api_key,
        cache_dir=cache_dir,
        max_actor_runs=args.max_actor_runs,
        max_hn_calls=args.max_hn_calls,
        max_yt_calls=args.max_yt_calls,
    )

    outcome = run_pipeline(client, inputs)

    evidence_path = workspace / EVIDENCE_REL
    evidence_json = json.dumps(outcome["evidence"], indent=1, ensure_ascii=False)
    _write_atomic(evidence_path, evidence_json)

    section_file = runtime / "result.md"
    _write_atomic(section_file, outcome["section_markdown"])

    upsert = _load_script("upsert-markdown-section.py", "pmr_upsert_markdown_section")
    report_path = workspace / REPORT_REL
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _canonicalize_legacy_headings(upsert, report_path)
    upsert.upsert_markdown_section(report_path, SECTION_HEADING, outcome["section_markdown"])

    persist = _load_script("persist-research-report.py", "pmr_persist_research_report")
    persistence = persist.persist_research_report(
        workspace,
        commit_message=f"research: update {SECTION_HEADING.lower()} section",
        extra_paths=(Path(_artifact_path("egbe-docs/research/market/evidence/community-demand.json")),),
    )

    state = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "status": "completed",
        "queries": inputs.queries,
        "query_sources": inputs.query_sources,
        "product_context": inputs.product_context,
        "evidence_path": EVIDENCE_REL.as_posix(),
        "evidence_sha256": hashlib.sha256(evidence_json.encode("utf-8")).hexdigest(),
        "result_path": (RUNTIME_REL / "result.md").as_posix(),
        "result_sha256": hashlib.sha256(outcome["section_markdown"].encode("utf-8")).hexdigest(),
        "provider_calls": outcome["totals"]["provider_calls"],
        "actor_runs": outcome["totals"]["actor_runs"],
        "hn_calls": outcome["totals"]["hn_calls"],
        "youtube_calls": outcome["totals"]["youtube_calls"],
        "actor_starts_recorded": outcome["totals"].get("actor_starts_recorded", 0),
        "attempt_actor_runs": outcome["attempt"]["actor_runs"],
        "attempt_hn_calls": outcome["attempt"]["hn_calls"],
        "attempt_yt_calls": outcome["attempt"]["yt_calls"],
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
        help="Comma-separated category AND problem phrases derived from "
        "the research assignment; merged ahead of the top keywords discovered by Keyword "
        "Economics.",
    )
    parser.add_argument(
        "--product-context",
        default="",
        help="Comma-separated mechanism tokens from the research assignment (e.g. 'ai, "
        "agent'); quotes mentioning them are flagged as speaking to THIS "
        "product's mechanism rather than the bare category.",
    )
    parser.add_argument("--max-queries", type=int, default=MAX_QUERIES)
    parser.add_argument("--max-actor-runs", type=int, default=MAX_ACTOR_RUNS_PER_ATTEMPT)
    parser.add_argument("--max-hn-calls", type=int, default=MAX_HN_CALLS_PER_ATTEMPT)
    parser.add_argument("--max-yt-calls", type=int, default=MAX_YT_CALLS_PER_ATTEMPT)
    args = parser.parse_args()

    try:
        state = run(args.workspace, args)
    except (CommunityDemandError, ValueError) as exc:
        print(f"{DISPLAY_NAME}: {exc}", file=sys.stderr)
        return 1
    print(
        f"{DISPLAY_NAME}: completed — {state['actor_runs']} actor run(s), "
        f"{state['hn_calls']} HN call(s), {state['youtube_calls']} YouTube "
        f"call(s), evidence at {state['evidence_path']}, report commit "
        f"{state['report_commit_sha'][:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
