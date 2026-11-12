#!/usr/bin/env python3
"""Run the deterministic Competitor Ads section against ad-transparency data.

Collect scoped ad-library observations, identity, native dates and coverage.
Advertising duration does not establish spend, conversion or profitability.

Providers (all reached through the OS gateway with the claw's own key):
  - Google Ads Transparency via the Apify actor
    `scrapesage/google-ads-transparency-scraper` (domain-keyed: the
    actor's `domains` input returns the creatives whose destination is the
    competitor's site, with firstShown/lastShown/numServedDays);
  - Meta Ads Library via the Apify actor
    `curious_coder/facebook-ads-library-scraper` (US coverage, ad start/end
    timestamps, creative texts);
  - the official Meta Ad Library endpoint (`/tools/meta-ad-library/search`)
    for EU delivery data and reach.

Competitor domains come from explicit `--domains`, then the completed
Competitor Set, then the Keyword Economics evidence file (the
`competitor_domain` rows discovered on the demand surface). Identity is
destination-first: Google rows are collected by destination domain (the
actor's `domains` input); Meta rows are kept when their landing destination
resolves to the competitor's domain or, when the ad carries no destination,
when the page name is an exact brand match (`verified_by: exact_name`);
contains-only namesakes and foreign destinations are excluded and reported
separately.

Caching and spend provenance mirror the Keyword Economics runner: every
provider response is cached under the runtime directory keyed by request
hash, re-runs replay for free, and durable totals come from the cache ledger
so retries stay byte-stable.
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
from datetime import date, datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable
from urllib.parse import quote

SCHEMA_VERSION = 1
SECTION_ID = "competitor_ads"
SECTION_HEADING = "Competitor ads"
DISPLAY_NAME = "Competitor Ads"

DEFAULT_OS_URL = "https://os.hz.egbe.dev"
RUNTIME_REL = Path(_artifact_path("egbe-docs/research/market/work")) / SECTION_ID
EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/competitor-ads.json"))
REPORT_REL = Path(_artifact_path("egbe-docs/research/market/full-report.md"))

# Google collection is DOMAIN-keyed: the actor's `domains` input returns every
# advertiser account whose ads point at the target domain (validated live:
# clickup.com -> "Mango Technologies, Inc.", ClickUp's legal entity, with zero
# same-name lookalikes — name search returned only "CLICKUP LEGALTECH
# SERVICES SL"). Identity comes from ad destination, never advertiser names.
GOOGLE_ACTOR = "scrapesage/google-ads-transparency-scraper"
META_ACTOR = "curious_coder/facebook-ads-library-scraper"

# Every Apify actor run places a wallet hold on the claw, so the per-attempt
# budget is deliberately tight; cache hits are free.
MAX_ACTOR_RUNS_PER_ATTEMPT = 6
MAX_META_SEARCHES_PER_ATTEMPT = 8
# Each competitor costs two actor runs (Google + Meta), so the default
# competitor count is sized to the actor budget; run() trims further if the
# caller lowers --max-actor-runs.
MAX_COMPETITORS = 3
GOOGLE_ADS_PER_COMPETITOR = 60
META_ADS_PER_COMPETITOR = 25
STORED_ADS_PER_DOMAIN = 15

# Synchronous actor runs occasionally die with a transient 5xx at the edge
# while the upstream run itself is fine. One bounded retry, carrying a
# deterministic Idempotency-Key derived from the request hash, lets the
# gateway reuse the same upstream run instead of paying for a duplicate.
ACTOR_RETRY_DELAY_SECONDS = 20.0

_PRICE_RE = re.compile(
    r"(\$\s?\d+(?:[.,]\d{1,2})?|\d+\s?%\s?off|per\s+month|/mo\b|a\s+month)",
    re.IGNORECASE,
)


class CompetitorAdsError(RuntimeError):
    """Terminal runner failure; runtime state is preserved for resume."""


def _load_script(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise CompetitorAdsError(f"cannot load bundled script {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


POLICY = _load_script("research-policy.py", "pmr_policy_for_competitor_ads")
LONG_RUNNING_DAYS = None  # Retained call parameter; no duration-to-success classification.


# ── OS client: generic POST with cache ledger and per-kind budgets ─────────

@dataclass
class OsClient:
    os_url: str
    api_key: str
    cache_dir: Path
    max_actor_runs: int = MAX_ACTOR_RUNS_PER_ATTEMPT
    max_meta_searches: int = MAX_META_SEARCHES_PER_ATTEMPT
    actor_runs: int = 0
    meta_searches: int = 0
    cache_hits: int = 0
    touched: set[str] = None  # type: ignore[assignment]  # set in __post_init__
    request: Callable[..., dict[str, Any]] | None = None
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
            raise CompetitorAdsError(f"OS {path} failed: HTTP {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise CompetitorAdsError(f"OS {path} unreachable: {exc.reason}") from exc
        data = envelope.get("data")
        if envelope.get("code") not in (None, 200) or not isinstance(data, dict):
            raise CompetitorAdsError(
                f"OS {path} returned no data: {str(envelope)[:300]}"
            )
        return data

    def _cached(self, kind: str, path: str, payload: dict[str, Any], timeout: float, budget_check: Callable[[], None], count: Callable[[], None], retry_transient: bool = False) -> tuple[dict[str, Any], str]:
        """Return (response, retrieved_on). Paid starts are counted BEFORE the
        transport call (fail closed): an ambiguous sync failure may still have
        started a billable upstream run, so a retry consumes budget exactly
        like a first attempt."""
        key_raw = json.dumps({"kind": kind, "path": path, "payload": payload}, sort_keys=True)
        digest = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        self.touched.add(digest)
        if cache_file.is_file():
            try:
                entry = json.loads(cache_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                # A torn write must not poison replay: discard and refetch.
                cache_file.unlink(missing_ok=True)
                entry = None
            if entry is not None:
                self.cache_hits += 1
                return entry["response"], entry.get("retrieved_on") or date.today().isoformat()
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
            budget_check()
            count()
            self._journal_start(kind, digest)
            try:
                response = transport(path, payload, timeout, idempotency_key=wire_key)
                break
            except CompetitorAdsError as exc:
                if (
                    not retry_transient
                    or attempts >= 1
                    or not re.search(r"HTTP 5\d\d", str(exc))
                ):
                    raise
                attempts += 1
                (self.sleep or time.sleep)(ACTOR_RETRY_DELAY_SECONDS)
        retrieved_on = date.today().isoformat()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = cache_file.with_suffix(".json.tmp")
        tmp_file.write_text(
            json.dumps(
                {
                    "kind": kind,
                    "path": path,
                    "payload": payload,
                    "response": response,
                    "retrieved_on": retrieved_on,
                }
            ),
            encoding="utf-8",
        )
        tmp_file.replace(cache_file)
        return response, retrieved_on

    def _journal_start(self, kind: str, digest: str) -> None:
        """Append-only durable record of every PAID start, successful or not
        — the cache holds only successes, but a failed sync start may still
        have billed upstream."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with (self.cache_dir / "starts.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{date.today().isoformat()} {kind} {digest}\n")

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

    def run_actor(self, actor: str, actor_input: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        def check() -> None:
            if self.actor_runs >= self.max_actor_runs:
                raise CompetitorAdsError(
                    f"actor-run budget exhausted ({self.max_actor_runs} per attempt); "
                    "narrow the competitor list or re-run to continue from cache"
                )

        def count() -> None:
            self.actor_runs += 1

        response, retrieved_on = self._cached(
            "actor",
            "/scrape/apify/run",
            {"actor": actor, "input": actor_input, "sync": True, "limit": limit},
            timeout=330.0,
            budget_check=check,
            count=count,
            retry_transient=True,
        )
        rows = response.get("rows")
        return (rows if isinstance(rows, list) else []), retrieved_on

    def meta_library_search(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        def check() -> None:
            if self.meta_searches >= self.max_meta_searches:
                raise CompetitorAdsError(
                    f"meta-ad-library budget exhausted ({self.max_meta_searches} per attempt)"
                )

        def count() -> None:
            self.meta_searches += 1

        response, retrieved_on = self._cached(
            "meta-ad-library",
            "/tools/meta-ad-library/search",
            payload,
            timeout=90.0,
            budget_check=check,
            count=count,
        )
        rows = response.get("data")
        return (rows if isinstance(rows, list) else []), retrieved_on

    def ledger_totals(self) -> dict[str, Any]:
        """Durable provenance over the entries THIS execution touched (fresh
        or replayed): one entry = one successful provider call, whichever
        attempt made it. Entries from unrelated earlier runs against other
        inputs in the same workspace are excluded."""
        actor_runs = 0
        meta_searches = 0
        dates: list[str] = []
        if self.cache_dir.is_dir():
            for digest in sorted(self.touched):
                entry_path = self.cache_dir / f"{digest}.json"
                try:
                    entry = json.loads(entry_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if entry.get("kind") == "actor":
                    actor_runs += 1
                elif entry.get("kind") == "meta-ad-library":
                    meta_searches += 1
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
            "actor_runs": actor_runs,
            "meta_searches": meta_searches,
            "provider_calls": actor_runs + meta_searches,
            "provider_starts_recorded": starts_recorded,
            "first_retrieved_on": min(dates) if dates else today,
            "last_retrieved_on": max(dates) if dates else today,
        }


# ── deterministic helpers ──────────────────────────────────────────────────

_KEYWORD_ECONOMICS: ModuleType | None = None


def registrable_domain(value: str) -> str:
    """The shared normalization of the Keyword Economics runner: two-level
    public suffixes, sellers' subdomains on course and creator hosts."""
    global _KEYWORD_ECONOMICS
    if _KEYWORD_ECONOMICS is None:
        _KEYWORD_ECONOMICS = _load_script("run-keyword-economics.py", "pmr_keyword_economics_for_competitor_ads")
    return _KEYWORD_ECONOMICS.registrable_domain(value)


def brand_token(domain: str) -> str:
    """clickup.com -> clickup; the search key for name-matched ad libraries."""
    stem = registrable_domain(domain).split(".")[0]
    return re.sub(r"[^a-z0-9]", "", stem)


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def name_matches_brand(name: str, brand: str) -> bool:
    """Ad-library keyword search matches advertiser NAMES; keep only entities
    whose normalized name contains the brand token (validated live: a search
    for 'clickup' also returned 'CLICKUP LEGALTECH SERVICES SL')."""
    if not brand:
        return False
    return brand in _normalize_name(name)


def verify_ad_identity(
    ads: list[dict[str, Any]], target_domain: str, brand: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split candidate ads into (verified, excluded_namesakes).

    Identity policy, strongest evidence first:
    1. destination — the ad's landing destination resolves to the target
       domain (Meta snapshot link_url/caption, official
       ad_creative_link_captions);
    2. exact_name — no destination data, but the advertiser/page name
       normalizes exactly to the brand token;
    3. anything else (contains-only namesakes, foreign destinations) is
       EXCLUDED from all verdicts and reported separately — a lookalike's ads
       must never prove a competitor's channel."""
    target = registrable_domain(target_domain)
    verified: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for ad in ads:
        destination = ad.pop("_destination", None)
        if destination:
            if registrable_domain(destination) == target:
                verified.append({**ad, "verified_by": "destination"})
            else:
                excluded.append(
                    {
                        "type": "excluded_namesake",
                        "domain": target_domain,
                        "platform": ad.get("platform"),
                        "advertiser": ad.get("advertiser"),
                        "ad_id": ad.get("ad_id"),
                        "destination": destination,
                        "reason": "destination_mismatch",
                        "tier": "B",
                    }
                )
            continue
        if _normalize_name(ad.get("advertiser") or "") == brand:
            verified.append({**ad, "verified_by": "exact_name"})
            continue
        excluded.append(
            {
                "type": "excluded_namesake",
                "domain": target_domain,
                "platform": ad.get("platform"),
                "advertiser": ad.get("advertiser"),
                "ad_id": ad.get("ad_id"),
                "destination": None,
                "reason": "name_contains_only",
                "tier": "B",
            }
        )
    return verified, excluded


def dedupe_meta_ads(
    actor_ads: list[dict[str, Any]], official_ads: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The US actor and the EU official API can return the SAME ad archive
    id; counting it twice would double every longevity statistic. Merge by ad
    identity, preferring the official row's EU fields and the larger measured
    age."""
    merged: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for ad in actor_ads + official_ads:
        key = str(ad.get("ad_id") or "") or f"__anon_{len(ordered)}"
        existing = merged.get(key)
        if existing is None:
            row = dict(ad)
            merged[key] = row
            ordered.append(row)
            continue
        for field_name in ("eu_total_reach", "publisher_platforms", "link", "text"):
            if existing.get(field_name) in (None, "") and ad.get(field_name) not in (None, ""):
                existing[field_name] = ad[field_name]
        for day_field in ("served_days",):
            a, b = existing.get(day_field), ad.get(day_field)
            if isinstance(b, int) and (not isinstance(a, int) or b > a):
                existing[day_field] = b
        existing["platform"] = "meta"
    return ordered


def parse_terms(raw: str, cap: int) -> list[str]:
    seen: dict[str, None] = {}
    for part in re.split(r"[,;\n]", raw or ""):
        term = part.strip().lower()
        if term and term not in seen:
            seen[term] = None
    return list(seen)[:cap]



def domains_from_keyword_evidence(workspace: Path, cap: int, exclude=frozenset()) -> list[str]:
    evidence = _load_script("research-evidence.py", "pmr_evidence")
    return evidence.keyword_inputs(workspace, consumer=SECTION_ID, row_type="competitor_domain", field="domain", cap=cap, exclude=exclude)


def domains_from_competitor_set(workspace: Path, cap: int) -> list[str]:
    """Tiered competitors from a completed Competitor Set section, in rank order."""
    evidence = _load_script("research-evidence.py", "pmr_evidence")
    return evidence.competitor_set_inputs(workspace, consumer=SECTION_ID, cap=cap)


def domains_excluded_by_competitor_set(workspace: Path) -> set[str]:
    """Domains the completed Competitor Set rejected; never refilled automatically."""
    evidence = _load_script("research-evidence.py", "pmr_evidence")
    return evidence.competitor_set_excluded_domains(workspace)


def _days_between(start_iso: str, end_iso: str) -> int | None:
    try:
        start = date.fromisoformat(start_iso[:10])
        end = date.fromisoformat(end_iso[:10])
    except (ValueError, TypeError):
        return None
    return max(0, (end - start).days)


def _epoch_to_iso(value: Any) -> str | None:
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return datetime.fromtimestamp(float(value), tz=timezone.utc).date().isoformat()


def normalize_google_ad(row: dict[str, Any], domain: str) -> dict[str, Any] | None:
    """Domain-mode rows are destination-verified by construction; still check
    the echoed destination domain and drop anything foreign."""
    destination = registrable_domain(str(row.get("domain") or ""))
    if destination != registrable_domain(domain):
        return None
    first = str(row.get("firstShown") or "")[:10] or None
    last = str(row.get("lastShown") or "")[:10] or None
    served = row.get("shownForDays")
    if not isinstance(served, int) and first and last:
        served = _days_between(first, last)
    return {
        "type": "ad_observation",
        "domain": domain,
        "platform": "google",
        "advertiser": str(row.get("advertiserName") or ""),
        "advertiser_id": row.get("advertiserId"),
        "ad_id": row.get("creativeId"),
        "format": row.get("format"),
        "first_seen": first,
        "last_seen": last,
        "served_days": served,
        "verified_by": "destination",
        "text": None,
        "link": row.get("adUrl") or row.get("previewUrl"),
        "tier": "A",
    }


def normalize_meta_actor_ad(row: dict[str, Any], domain: str, today_iso: str) -> dict[str, Any] | None:
    page = str(row.get("page_name") or row.get("pageName") or "")
    snapshot_peek = row.get("snapshot") or {}
    peek_destination = str(
        snapshot_peek.get("link_url") or snapshot_peek.get("caption") or ""
    )
    # Admit a candidate when the page name resembles the brand OR the ad's
    # destination points at the target domain (a page named after the product
    # line, not the brand, still counts); verify_ad_identity decides.
    if not name_matches_brand(page, brand_token(domain)) and registrable_domain(
        peek_destination
    ) != registrable_domain(domain):
        return None
    snapshot = row.get("snapshot") or {}
    body = snapshot.get("body") or {}
    text = body.get("text") if isinstance(body, dict) else None
    destination = (
        str(snapshot.get("link_url") or "").strip()
        or str(snapshot.get("caption") or "").strip()
        or None
    )
    first = _epoch_to_iso(row.get("start_date") or row.get("startDate"))
    last = _epoch_to_iso(row.get("end_date") or row.get("endDate"))
    is_active = row.get("is_active")
    effective_last = today_iso if is_active or not last else last
    served = _days_between(first, effective_last) if first else None
    ad_id = row.get("ad_archive_id") or row.get("adArchiveID") or row.get("ad_id")
    return {
        "type": "ad_observation",
        "domain": domain,
        "platform": "meta",
        "advertiser": page,
        "page_id": row.get("page_id"),
        "ad_id": ad_id,
        "format": None,
        "first_seen": first,
        "last_seen": last,
        "is_active": bool(is_active) if is_active is not None else None,
        "served_days": served,
        "_destination": destination,
        "text": (text or "")[:280] or None,
        "link": f"https://www.facebook.com/ads/library/?id={ad_id}" if ad_id else None,
        "tier": "A",
    }


def normalize_meta_official_ad(row: dict[str, Any], domain: str, today_iso: str) -> dict[str, Any] | None:
    page = str(row.get("page_name") or "")
    captions_peek = row.get("ad_creative_link_captions") or []
    peek_destination = str(captions_peek[0]) if captions_peek else ""
    if not name_matches_brand(page, brand_token(domain)) and registrable_domain(
        peek_destination
    ) != registrable_domain(domain):
        return None
    first = str(row.get("ad_delivery_start_time") or "")[:10] or None
    last = str(row.get("ad_delivery_stop_time") or "")[:10] or None
    served = _days_between(first, last or today_iso) if first else None
    bodies = row.get("ad_creative_bodies") or []
    text = bodies[0] if bodies and isinstance(bodies[0], str) else None
    captions = row.get("ad_creative_link_captions") or []
    destination = (
        str(captions[0]).strip() if captions and str(captions[0]).strip() else None
    )
    return {
        "type": "ad_observation",
        "domain": domain,
        "platform": "meta_eu",
        "_destination": destination,
        "advertiser": page,
        "page_id": row.get("page_id"),
        "ad_id": row.get("id"),
        "format": None,
        "first_seen": first,
        "last_seen": last,
        "served_days": served,
        "eu_total_reach": row.get("eu_total_reach"),
        "publisher_platforms": row.get("publisher_platforms"),
        "text": (text or "")[:280] or None,
        "link": row.get("ad_snapshot_url"),
        "tier": "A",
    }


def summarize_platform(
    domain: str,
    platform: str,
    ads: list[dict[str, Any]],
    threshold_days: int = LONG_RUNNING_DAYS,
) -> dict[str, Any]:
    served = [a.get("served_days") for a in ads if isinstance(a.get("served_days"), int)]
    # Advertiser presence SPAN survives creative rotation: a business swapping
    # creatives weekly still shows a long earliest-first-seen -> latest-last-
    # seen window, while any single creative's age resets on every edit.
    firsts = [a.get("first_seen") for a in ads if a.get("first_seen")]
    lasts = [a.get("last_seen") for a in ads if a.get("last_seen")]
    span_days = _days_between(min(firsts), max(lasts)) if firsts and lasts else None
    return {
        "type": "platform_presence",
        "domain": domain,
        "platform": platform,
        "ads_observed": len(ads),
        "max_served_days": max(served) if served else None,
        "median_served_days": sorted(served)[len(served) // 2] if served else None,
        "presence_span_days": span_days,
        "presence_first_seen": min(firsts) if firsts else None,
        "presence_last_seen": max(lasts) if lasts else None,
        "verified_by_destination": sum(1 for a in ads if a.get("verified_by") == "destination"),
        "verified_by_exact_name": sum(1 for a in ads if a.get("verified_by") == "exact_name"),
        "status": "observed" if ads else "no_matches_in_sample",
        "tier": "A",
    }


def extract_price_mentions(ads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ad in ads:
        text = ad.get("text") or ""
        for match in _PRICE_RE.finditer(text):
            start = max(0, match.start() - 40)
            excerpt = text[start : match.end() + 40].strip()
            key = f"{ad['domain']}|{excerpt.lower()}"
            if key in seen:
                continue
            seen.add(key)
            mentions.append(
                {
                    "type": "price_mention",
                    "domain": ad["domain"],
                    "platform": ad["platform"],
                    "excerpt": excerpt,
                    "ad_id": ad.get("ad_id"),
                    "tier": "B",
                }
            )
    return mentions


def meta_search_url(brand: str, country: str) -> str:
    return (
        "https://www.facebook.com/ads/library/?active_status=all&ad_type=all"
        f"&country={quote(country)}&q=%22{quote(brand)}%22&search_type=keyword_unordered&media_type=all"
    )


# ── rendering ──────────────────────────────────────────────────────────────

def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def render_section(
    *,
    domains: list[str],
    domain_sources: dict[str, str],
    presences: list[dict[str, Any]],
    ads: list[dict[str, Any]],
    price_mentions: list[dict[str, Any]],
    excluded_namesakes: list[dict[str, Any]],
    totals: dict[str, Any],
    retrieved_on: str,
    eu_country: str,
    threshold_days: int = LONG_RUNNING_DAYS,
) -> str:
    lines: list[str] = []
    add = lines.append

    add(
        f"Ad-transparency data retrieved {retrieved_on} from Google Ads "
        f"Transparency and the Meta Ads Library (US coverage via scraper, EU "
        f"delivery data via the official API, country `{eu_country}`). "
        "Observed ad duration and advertiser span do not establish spend, "
        "continuous delivery, conversion or profitability. "
        "Identity is destination-verified: Google ads are collected by the "
        "domain their ads point to (advertiser legal names like ClickUp's "
        "'Mango Technologies, Inc.' are found automatically), and Meta ads "
        "count only when their landing destination resolves to the target "
        "domain or the page name is an exact brand match; same-name "
        "lookalikes are excluded and listed below."
    )
    add("")
    add(
        "Domains examined: "
        + ", ".join(f"`{d}` ({domain_sources.get(d, 'explicit')})" for d in domains)
        + "."
    )
    add("")

    add("### Platform presence and ad longevity")
    add("")
    add("| Domain | Platform | Ads observed | Oldest creative (days) | Advertiser span (days) | Coverage |")
    add("| --- | --- | ---: | ---: | ---: | --- |")
    for row in presences:
        add(
            f"| {row['domain']} | {row['platform']} | {_fmt(row['ads_observed'])} | "
            f"{_fmt(row['max_served_days'])} | {_fmt(row.get('presence_span_days'))} | "
            f"{row['status']} |"
        )
    add("")
    add("No matches means no matching ads in this bounded sample, not absent advertising or absent demand.")
    add("")
    if excluded_namesakes:
        by_name: dict[str, int] = {}
        for row in excluded_namesakes:
            key = f"{row.get('advertiser')} ({row.get('platform')}, {row.get('reason')})"
            by_name[key] = by_name.get(key, 0) + 1
        add(
            "Excluded same-name lookalikes (not attributed to the scoped competitors): "
            + "; ".join(f"{name} × {count}" for name, count in sorted(by_name.items()))
            + "."
        )
        add("")

    long_ads = sorted(
        (a for a in ads if isinstance(a.get("served_days"), int)),
        key=lambda a: a["served_days"],
        reverse=True,
    )
    if long_ads:
        add("### Longest-running creatives")
        add("")
        add("| Domain | Platform | Days served | First seen | Last seen | Creative |")
        add("| --- | --- | ---: | --- | --- | --- |")
        per_domain: dict[str, int] = {}
        for ad in long_ads:
            if per_domain.get(ad["domain"], 0) >= 3:
                continue
            per_domain[ad["domain"]] = per_domain.get(ad["domain"], 0) + 1
            creative = (ad.get("text") or ad.get("format") or "—").replace("|", "/")
            creative = " ".join(str(creative).split())[:110]
            link = ad.get("link")
            creative_cell = f"[{creative}]({link})" if link else creative
            add(
                f"| {ad['domain']} | {ad['platform']} | {ad['served_days']} | "
                f"{_fmt(ad.get('first_seen'))} | {_fmt(ad.get('last_seen'))} | {creative_cell} |"
            )
        add("")

    if price_mentions:
        add("### Price anchors found in ad copy")
        add("")
        for mention in price_mentions[:10]:
            add(f"- `{mention['domain']}` ({mention['platform']}): “{mention['excerpt']}”")
        add("")

    add("### Method and coverage")
    add("")
    add(
        f"- Provider calls recorded: {totals['actor_runs']} Apify actor run(s) "
        f"+ {totals['meta_searches']} official Meta Ad Library search(es), "
        "accumulated across attempts; cached replays add no new spend."
    )
    add(
        f"- Caps: {MAX_COMPETITORS} competitors, {GOOGLE_ADS_PER_COMPETITOR} "
        f"Google creatives and {META_ADS_PER_COMPETITOR} Meta ads per "
        f"competitor, {MAX_ACTOR_RUNS_PER_ATTEMPT} actor runs per attempt."
    )
    add(
        "- Longevity from Google's own served-days and Meta delivery windows; "
        "the advertiser span may include gaps and creative rotation. Not covered: LinkedIn/TikTok libraries, targeting details, "
        "spend amounts (Meta discloses neither for commercial ads outside "
        "the EU), and any judgement of which combo to pursue."
    )
    add("")
    add("### Sources")
    add("")
    add(
        f"- Google Ads Transparency via Apify `{GOOGLE_ACTOR}` "
        f"(domain-keyed collection); Meta Ads Library via Apify "
        f"`{META_ACTOR}` (US) and the official `ads_archive` API (EU, "
        f"`{eu_country}`) — retrieved {retrieved_on}; evidence rows in "
        f"`{EVIDENCE_REL.as_posix()}`."
    )
    return "\n".join(lines).strip() + "\n"


# ── orchestration ──────────────────────────────────────────────────────────

@dataclass
class RunInputs:
    domains: list[str]
    domain_sources: dict[str, str]
    eu_country: str
    long_running_days: int = LONG_RUNNING_DAYS


def _call_with_context(client: OsClient, domain: str, label: str, fn: Callable[[], Any]) -> Any:
    """Re-raise a provider-call failure with WHICH competitor/call failed and
    how much of the attempt's paid budget is already spent — the raw gateway
    envelope alone doesn't say either, so a human can't tell whether a retry
    is even possible without this."""
    try:
        return fn()
    except CompetitorAdsError as exc:
        raise CompetitorAdsError(
            f"{label} for `{domain}` failed: {exc} — this attempt had "
            f"already started {client.actor_runs}/{client.max_actor_runs} "
            f"actor run(s) and {client.meta_searches}/{client.max_meta_searches} "
            "meta search(es); see GET /me/limits?resource=apify:runs for "
            "remaining daily quota."
        ) from exc


def run_pipeline(client: OsClient, inputs: RunInputs) -> dict[str, Any]:
    if not inputs.domains:
        raise CompetitorAdsError(
            "no competitor domains available: run the Keyword Economics "
            "section first (its evidence feeds this section) or pass "
            "--domains explicitly"
        )
    ads: list[dict[str, Any]] = []
    presences: list[dict[str, Any]] = []
    excluded_namesakes: list[dict[str, Any]] = []
    for domain in inputs.domains:
        brand = brand_token(domain)

        google_rows, _ = _call_with_context(
            client,
            domain,
            "Google Ads Transparency",
            lambda: client.run_actor(
                GOOGLE_ACTOR,
                {
                    "domains": [registrable_domain(domain)],
                    "resultType": "ads",
                    "region": "ANYWHERE",
                    "maxAdsPerSearch": GOOGLE_ADS_PER_COMPETITOR,
                },
                limit=GOOGLE_ADS_PER_COMPETITOR,
            ),
        )
        google_ads = [
            ad for ad in (normalize_google_ad(r, domain) for r in google_rows) if ad
        ]

        # Active ads age up to the date their snapshot was RETRIEVED, never
        # the current wall clock: a cache replay must not fabricate extra
        # longevity for an ad that may have stopped the day after capture.
        meta_rows, meta_as_of = _call_with_context(
            client,
            domain,
            "Meta Ads Library (US actor)",
            lambda: client.run_actor(
                META_ACTOR,
                {
                    "urls": [{"url": meta_search_url(brand, "US")}],
                    "count": META_ADS_PER_COMPETITOR,
                },
                limit=META_ADS_PER_COMPETITOR,
            ),
        )
        meta_candidates = [
            ad
            for ad in (normalize_meta_actor_ad(r, domain, meta_as_of) for r in meta_rows)
            if ad
        ]
        meta_ads, meta_excluded = verify_ad_identity(meta_candidates, domain, brand)
        excluded_namesakes.extend(meta_excluded)

        official_rows, official_as_of = _call_with_context(
            client,
            domain,
            "Meta Ads Library (official EU API)",
            lambda: client.meta_library_search(
                {
                    "query": brand,
                    "countries": [inputs.eu_country],
                    "activeStatus": "ALL",
                    "limit": META_ADS_PER_COMPETITOR,
                }
            ),
        )
        official_candidates = [
            ad
            for ad in (
                normalize_meta_official_ad(r, domain, official_as_of)
                for r in official_rows
            )
            if ad
        ]
        meta_eu_ads, official_excluded = verify_ad_identity(
            official_candidates, domain, brand
        )
        excluded_namesakes.extend(official_excluded)

        merged_meta = dedupe_meta_ads(meta_ads, meta_eu_ads)
        ads.extend(google_ads + merged_meta)
        presences.append(
            summarize_platform(domain, "google", google_ads, inputs.long_running_days)
        )
        presences.append(
            summarize_platform(domain, "meta", merged_meta, inputs.long_running_days)
        )

    price_mentions = extract_price_mentions(ads)

    # Keep the evidence lean: per (domain, platform), store the longest-served
    # ads — per-platform so a long-lived Google history cannot crowd Meta's
    # creatives (and their price-bearing texts) out of the evidence file.
    stored_ads: list[dict[str, Any]] = []
    for domain in inputs.domains:
        for platform in ("google", "meta"):
            platform_ads = sorted(
                (
                    a
                    for a in ads
                    if a["domain"] == domain and a["platform"] == platform
                ),
                key=lambda a: a.get("served_days") or -1,
                reverse=True,
            )
            stored_ads.extend(platform_ads[:STORED_ADS_PER_DOMAIN])

    totals = client.ledger_totals()
    retrieved_on = (
        totals["first_retrieved_on"]
        if totals["first_retrieved_on"] == totals["last_retrieved_on"]
        else f"{totals['first_retrieved_on']}..{totals['last_retrieved_on']}"
    )

    domain_rows = [
        {
            "type": "competitor_domain",
            "domain": domain,
            "source": inputs.domain_sources.get(domain, "explicit"),
            "tier": "A",
        }
        for domain in inputs.domains
    ]

    evidence = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "generated_by": Path(__file__).name,
        "retrieved_on": retrieved_on,
        "inputs": {
            "domains": inputs.domains,
            "domain_sources": inputs.domain_sources,
            "eu_country": inputs.eu_country,
        },
        "rows": domain_rows + presences + stored_ads + price_mentions + excluded_namesakes,
        "totals": {
            "actor_runs": totals["actor_runs"],
            "meta_searches": totals["meta_searches"],
            "provider_calls": totals["provider_calls"],
        },
    }

    section_markdown = render_section(
        domains=inputs.domains,
        domain_sources=inputs.domain_sources,
        presences=presences,
        ads=stored_ads,
        price_mentions=price_mentions,
        excluded_namesakes=excluded_namesakes,
        totals=totals,
        retrieved_on=retrieved_on,
        eu_country=inputs.eu_country,
        threshold_days=inputs.long_running_days,
    )
    return {
        "evidence": evidence,
        "section_markdown": section_markdown,
        "totals": totals,
        "attempt": {
            "actor_runs": client.actor_runs,
            "meta_searches": client.meta_searches,
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
        raise CompetitorAdsError("OS_API_KEY is required")
    os_url = (os.environ.get("OS_URL") or DEFAULT_OS_URL).strip() or DEFAULT_OS_URL
    effective_policy, policy_sha256 = POLICY.load_policy()
    explicit = parse_terms(args.domains or "", MAX_COMPETITORS)
    explicit = [registrable_domain(d) for d in explicit if registrable_domain(d)]
    # Explicit domains first, then the tiered Competitor Set, then the
    # Keyword Economics demand surface; each source is optional.
    tiered = domains_from_competitor_set(workspace, MAX_COMPETITORS)
    # The tiering decisions constrain automatic fallbacks: a domain the
    # Competitor Set rejected is not pulled back from the demand surface.
    # Explicit --domains remain the founder's override.
    rejected = domains_excluded_by_competitor_set(workspace) - set(explicit)
    discovered = domains_from_keyword_evidence(workspace, MAX_COMPETITORS, exclude=rejected)

    domains: list[str] = []
    domain_sources: dict[str, str] = {}
    for domain in explicit:
        if domain not in domains:
            domains.append(domain)
            domain_sources[domain] = "explicit"
    for source, candidates in (("competitor_set", tiered), ("keyword_economics", discovered)):
        for domain in candidates:
            if len(domains) >= args.max_competitors:
                break
            if domain not in domains:
                domains.append(domain)
                domain_sources[domain] = source
    domains = domains[: args.max_competitors]
    # Two actor runs per competitor: never admit more domains than the
    # actor budget can finish in one attempt (cache makes retries free, but a
    # first attempt must be able to complete).
    domains = domains[: max(1, args.max_actor_runs // 2)]

    inputs = RunInputs(
        domains=domains,
        domain_sources=domain_sources,
        eu_country=args.eu_country.strip().upper() or "DE",
        long_running_days=None,
    )
    client = OsClient(
        os_url=os_url,
        api_key=api_key,
        cache_dir=cache_dir,
        max_actor_runs=args.max_actor_runs,
    )

    outcome = run_pipeline(client, inputs)
    outcome["evidence"]["inputs"].update(effective_policy=effective_policy, policy_sha256=policy_sha256)

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
        extra_paths=(Path(_artifact_path("egbe-docs/research/market/evidence/competitor-ads.json")),),
    )

    state = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "status": "completed",
        "domains": inputs.domains,
        "domain_sources": inputs.domain_sources,
        "eu_country": inputs.eu_country,
        "evidence_path": EVIDENCE_REL.as_posix(),
        "evidence_sha256": hashlib.sha256(evidence_json.encode("utf-8")).hexdigest(),
        "result_path": (RUNTIME_REL / "result.md").as_posix(),
        "result_sha256": hashlib.sha256(outcome["section_markdown"].encode("utf-8")).hexdigest(),
        "provider_calls": outcome["totals"]["provider_calls"],
        "actor_runs": outcome["totals"]["actor_runs"],
        "meta_searches": outcome["totals"]["meta_searches"],
        "attempt_actor_runs": outcome["attempt"]["actor_runs"],
        "attempt_meta_searches": outcome["attempt"]["meta_searches"],
        "attempt_cache_hits": outcome["attempt"]["cache_hits"],
        "report_commit_sha": persistence.commit_sha,
        "publication_mode": persistence.publication_mode,
        "research_context": _load_script("research-artifact-io.py", "pmr_input_io").context_binding(workspace, SECTION_ID),
        "effective_policy": effective_policy,
        "policy_sha256": policy_sha256,
        "error": None,
    }
    _write_atomic(runtime / "request.json", json.dumps(state, indent=1))
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-file", type=Path, help="Explicit context for this study; no project files are discovered implicitly.")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--domains",
        default="",
        help="Comma-separated competitor domains; merged ahead of the "
        "domains discovered by Keyword Economics.",
    )
    parser.add_argument("--max-competitors", type=int, default=MAX_COMPETITORS)
    parser.add_argument("--eu-country", default="DE")
    parser.add_argument("--max-actor-runs", type=int, default=MAX_ACTOR_RUNS_PER_ATTEMPT)
    args = parser.parse_args()

    try:
        state = run(args.workspace, args)
    except (CompetitorAdsError, ValueError) as exc:
        print(f"{DISPLAY_NAME}: {exc}", file=sys.stderr)
        return 1
    print(
        f"{DISPLAY_NAME}: completed — {state['actor_runs']} actor run(s) + "
        f"{state['meta_searches']} Meta library search(es), evidence at "
        f"{state['evidence_path']}, report commit {state['report_commit_sha'][:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
