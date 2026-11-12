#!/usr/bin/env python3
"""Run the deterministic Channel Footprint section: where competitors buy traffic.

Ad libraries say whether a competitor advertises on a platform; nothing in the
other measured sections says WHERE its traffic comes from or which platforms
it pays. This runner answers that per competitor from five kinds of
observation, each cheap and reproducible:

  - tracking tags on the competitor's own pages (home page plus its Google
    Tag Manager containers): ad-platform pixels, native-ad networks, review
    marketplace trackers and affiliate platforms reveal where conversions are
    bought, including platforms without any public ad library;
  - ad-library presence and age on Google, Meta (US page search plus the
    official EU delivery data), LinkedIn, TikTok (EU library) and Reddit,
    through OS scrape actors and the official Meta endpoint;
  - the public traffic-source split and monthly visit estimate (a Similarweb
    actor, or the SimilarWeb tools provider once it is configured);
  - partner signals from web search: affiliate program pages, coupon and
    promo-code listings, sponsorship mentions;
  - page history from the Wayback Machine: domain age and how often the home
    page changed over the last two years.

The staged runner preserves a normalized ad corpus, validates context-bound
agent relevance decisions, and reports scoped activity, duration, coverage and
comparison roles without selecting a business priority. No LLM runs
inside the runner. Cache replays add no spend; durable cumulative provider
starts and per-attempt budgets bound collection and sample expansion.
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
import base64
import hashlib
import html as html_lib
import http.client
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

SCHEMA_VERSION = 2
SECTION_ID = "channel_footprint"
SECTION_HEADING = "Channel footprint"
DISPLAY_NAME = "Channel Footprint"

DEFAULT_OS_URL = "https://os.hz.egbe.dev"
RUNTIME_REL = Path(_artifact_path("egbe-docs/research/market/work")) / SECTION_ID
EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/channel-footprint.json"))
REPORT_REL = Path(_artifact_path("egbe-docs/research/market/full-report.md"))
SOURCES_CONFIG_REL = Path("references/config/channel-footprint-sources.v1.json")
WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"

MAX_COMPETITORS = 10
MAX_EXPLICIT_DOMAINS = 10
MAX_ACTOR_RUNS_PER_ATTEMPT = 12
MAX_META_SEARCHES_PER_ATTEMPT = 10
MAX_SEARCH_CALLS_PER_ATTEMPT = 30
MAX_FETCHES_PER_ATTEMPT = 40
MAX_CDX_CALLS_PER_ATTEMPT = 25
# One SpyFu domain-stats lookup per competitor (12 months = 12 rows, ~$0.006).
MAX_SPYFU_CALLS_PER_ATTEMPT = 12
SPYFU_MONTHS = 12
FETCH_MAX_BYTES = 2_000_000
FETCH_TIMEOUT_SECONDS = 25.0
CDX_TIMEOUT_SECONDS = 60.0
CDX_PAUSE_SECONDS = 1.0
CDX_ROW_LIMIT = 500
GTM_CONTAINERS_PER_SITE = 3
HISTORY_MONTHS = 24
BRAVE_COUNT = 10
PARTNER_URLS_PER_KIND = 3
ACTOR_RETRY_DELAY_SECONDS = 20.0
# The OS host refuses connections for about 40 s while a gateway on it
# redeploys (observed live 2026-10-02); one retry after this delay covers it.
OS_UNREACHABLE_RETRY_DELAY_SECONDS = 45.0
FREE_RETRY_DELAY_SECONDS = 5.0
DEFAULT_COUNTRY = "US"
DEFAULT_EU_COUNTRY = "DE"
# Product relevance by the creative classifier's semantic verdict: small
# batches keep each answer bounded; a decided sample may expand once more
# per round, so a few rounds settle a collect.
MAX_IMAGE_FETCHES_PER_ATTEMPT = 500
MAX_IMAGE_BYTES = 4 * 1024 * 1024
IMAGE_TIMEOUT_SECONDS = 30.0
RELEVANCE_PATH = "/v1/media/classify-creative"
RELEVANCE_BATCH = 4
MAX_RELEVANCE_CALLS_PER_ATTEMPT = 40
RELEVANCE_TIMEOUT_SECONDS = 330.0
MODEL_RELEVANCE_ROUNDS = 3
PRESENT_SHARE_PCT = 0.0  # Any positive modeled share is an observation, not a success threshold.

ALL_SOURCES = ("pixels", "history", "traffic", "google", "spyfu", "meta", "linkedin", "partners", "tiktok", "reddit")
CHANNELS = (
    "google_ads", "youtube_ads", "meta_ads", "linkedin_ads", "tiktok_ads", "reddit_ads", "microsoft_ads", "x_ads",
    "pinterest_ads", "snap_ads", "quora_ads", "display_native", "review_marketplace", "affiliate", "paid_search", "paid_social",
)
CHANNEL_LABELS = {
    "google_ads": "Google Ads", "youtube_ads": "YouTube (video)", "meta_ads": "Meta", "linkedin_ads": "LinkedIn",
    "tiktok_ads": "TikTok", "reddit_ads": "Reddit", "microsoft_ads": "Microsoft Ads", "x_ads": "X",
    "pinterest_ads": "Pinterest", "snap_ads": "Snapchat", "quora_ads": "Quora", "display_native": "Display / native",
    "review_marketplace": "Review marketplaces", "affiliate": "Affiliate / partners", "paid_search": "Paid search (category)", "paid_social": "Paid social (category)",
}
TAG_MANAGER_SIGNATURES: tuple[tuple[str, str], ...] = (
    ("google_tag_manager", r"googletagmanager\.com/gtm\.js|\bGTM-[A-Z0-9]{4,10}\b"),
    ("segment", r"cdn\.segment\.com/analytics\.js|\banalytics\.load\s*\("),
    ("tealium", r"tags\.tiqcdn\.com"),
    ("adobe_launch", r"assets\.adobedtm\.com"),
)
LINKEDIN_COMPANY_RE = re.compile(r"linkedin\.com/(?:company|school|showcase)/([A-Za-z0-9._%-]+)", re.IGNORECASE)
AFFILIATE_NETWORK_DOMAINS = {
    "impact.com", "partnerstack.com", "shareasale.com", "cj.com", "awin.com", "rakutenadvertising.com",
    "rewardful.com", "firstpromoter.com", "tapfiliate.com", "refersion.com", "getrewardful.com",
    "affiliateprogramdb.com", "lasso.net", "affpaying.com", "offervault.com",
}
COUPON_DOMAINS = {
    "retailmenot.com", "joinhoney.com", "coupons.com", "dealspotr.com", "couponfollow.com", "slickdeals.net",
    "wethrift.com", "knoji.com", "couponbirds.com", "coupert.com", "simplycodes.com", "capitaloneshopping.com",
    "rakuten.com", "groupon.com", "couponcabin.com", "offers.com", "promocodes.com", "hotdeals.com",
}
TRAFFIC_CHANNEL_MAP = {
    "paid_search": "paid_search", "search_paid": "paid_search", "paid_social": "paid_social", "social_paid": "paid_social",
    "display": "display_native", "display_ads": "display_native", "displayads": "display_native",
    "paid_referrals": "display_native", "affiliates": "affiliate", "affiliate": "affiliate",
}

# (tag id, channel, regex over page HTML and tag-manager container JS)
TAG_SIGNATURES: tuple[tuple[str, str, str], ...] = (
    ("meta_pixel", "meta_ads", r"connect\.facebook\.net/[^\"']*/fbevents\.js|\bfbq\s*\("),
    ("google_ads_tag", "google_ads", r"googleads\.g\.doubleclick\.net|googleadservices\.com/pagead/conversion|\bAW-\d{6,}"),
    ("reddit_pixel", "reddit_ads", r"redditstatic\.com/ads/pixel\.js|\brdt\s*\(\s*['\"]init"),
    ("linkedin_insight", "linkedin_ads", r"snap\.licdn\.com/li\.lms-analytics/insight\.min\.js|_linkedin_partner_id"),
    ("tiktok_pixel", "tiktok_ads", r"analytics\.tiktok\.com/i18n/pixel/events\.js|\bttq\.load\s*\("),
    ("microsoft_uet", "microsoft_ads", r"bat\.bing\.com/bat\.js|\buetq\b"),
    ("x_pixel", "x_ads", r"static\.ads-twitter\.com/uwt\.js|\btwq\s*\(\s*['\"](?:config|init)"),
    ("pinterest_tag", "pinterest_ads", r"s\.pinimg\.com/ct/core\.js|\bpintrk\s*\("),
    ("snap_pixel", "snap_ads", r"sc-static\.net/scevent\.min\.js|\bsnaptr\s*\("),
    ("quora_pixel", "quora_ads", r"a\.quora\.com/qevents\.js|\bqp\s*\(\s*['\"]init"),
    ("taboola", "display_native", r"cdn\.taboola\.com/libtrc|\b_tfa\b"),
    ("outbrain", "display_native", r"amplify\.outbrain\.com/cp/obtp\.js|\bobApi\s*\("),
    ("criteo", "display_native", r"static\.criteo\.net/js/ld/ld\.js"),
    ("capterra_tracker", "review_marketplace", r"ct\.capterra\.com/capterra_tracker"),
    ("g2_tracker", "review_marketplace", r"tracking\.g2crowd\.com|g2crowd\.com/attribution"),
    ("partnerstack", "affiliate", r"js\.partnerstack\.com|\bgrsm\.io\b|growsumo"),
    ("impact", "affiliate", r"utt\.impactcdn\.com|impactradius"),
    ("rewardful", "affiliate", r"r\.wdfl\.co|\brewardful\b"),
    ("firstpromoter", "affiliate", r"cdn\.firstpromoter\.com|\bfpr\s*\(\s*['\"]init"),
    ("tapfiliate", "affiliate", r"script\.tapfiliate\.com"),
    ("refersion", "affiliate", r"refersion\.com/tracker"),
    ("shareasale", "affiliate", r"shareasale\.com/sale\.cfm|static\.shareasale\.com/json/shareasale\.js"),
)
GTM_ID_RE = re.compile(r"\bGTM-[A-Z0-9]{4,10}\b")
PARTNER_KINDS: tuple[tuple[str, str], ...] = (
    # (kind, query template); precision rules live in `_partner_hit`.
    ("affiliate_program", '"{brand}" affiliate program'),
    ("coupon_listing", '"{brand}" promo code coupon'),
    ("sponsorship", '"sponsored by {brand}" OR "{brand} sponsored"'),
)
_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,251}\.[a-z]{2,24}$")


class ChannelFootprintError(RuntimeError):
    """Terminal runner failure; runtime state is preserved for resume."""


class SourceUnavailable(ChannelFootprintError):
    """A provider rejected the request itself (invalid input, unsupported
    actor): a fact about the source, cached so reruns never re-spend."""


class BudgetExhausted(ChannelFootprintError):
    """The per-attempt budget of one metered or free call type is spent;
    always propagates so a rerun resumes from the cache."""


class OsUnreachable(ChannelFootprintError):
    """The request never reached the OS gateway (connection refused, DNS,
    TLS, a connect timeout), so nothing was started or billed. Retried once;
    then it fails the attempt instead of becoming a coverage gap, because it
    says nothing about the source and a rerun resumes from the cache."""


# Consecutive failures of one supplementary source within an attempt after
# which its remaining domains are skipped instead of started (a provider that
# is down must not burn the paid actor budget one domain at a time).
SOURCE_BREAKER_FAILURES = 2
# Hosts that are not a competitor's destination but the platform itself or a
# store/link hub: the advertiser name decides for those rows.
NEUTRAL_DESTINATION_HOSTS = {
    # the platforms themselves and their messaging / short hosts
    "facebook.com", "instagram.com", "fb.me", "fb.com", "fb.watch", "fb.gg", "m.me", "ig.me", "messenger.com",
    "whatsapp.com", "wa.me", "t.me", "reddit.com", "redd.it", "linkedin.com", "lnkd.in", "tiktok.com", "vm.tiktok.com",
    "youtu.be", "youtube.com", "t.co", "x.com", "twitter.com",
    # stores and link hubs
    "apps.apple.com", "itunes.apple.com", "play.google.com", "linktr.ee", "lnk.to", "lnk.bio",
    # shorteners and attribution/deep-link hosts (the real destination is hidden)
    "bit.ly", "tinyurl.com", "ow.ly", "buff.ly", "hubs.ly", "hubs.la", "amzn.to", "rebrand.ly", "cutt.ly",
    "onelink.me", "app.link", "adjust.com", "adj.st", "go.link", "smart.link", "page.link",
}
# Click-tracking wrappers whose `u` query parameter carries the real address.
REDIRECT_WRAPPER_HOSTS = {"l.facebook.com", "lm.facebook.com", "l.instagram.com", "l.messenger.com", "google.com", "www.google.com"}


def _load_script(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ChannelFootprintError(f"cannot load bundled script {filename}")
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
IO = _load_script("research-artifact-io.py", "pmr_channel_footprint_io")
_KEYWORD_ECONOMICS: ModuleType | None = None


def _keyword_economics() -> ModuleType:
    global _KEYWORD_ECONOMICS
    if _KEYWORD_ECONOMICS is None:
        _KEYWORD_ECONOMICS = _load_script("run-keyword-economics.py", "pmr_keyword_economics_for_channel_footprint")
    return _KEYWORD_ECONOMICS


def registrable_domain(value: str) -> str:
    return _keyword_economics().registrable_domain(value)


def brand_token(domain: str) -> str:
    return _keyword_economics().brand_token(domain)


def load_sources_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or (Path(__file__).resolve().parent.parent / SOURCES_CONFIG_REL)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChannelFootprintError(f"cannot read the sources config {config_path.name}: {exc}") from exc
    if raw.get("schema_version") != 1 or not isinstance(raw.get("actors"), dict):
        raise ChannelFootprintError("sources config must have schema_version 1 and an actors object")
    for key, spec in raw["actors"].items():
        if not isinstance(spec, dict) or not str(spec.get("actor") or "").strip():
            raise ChannelFootprintError(f"sources config actor `{key}` has no actor id")
    registry = raw.get("channels") or {}
    if not isinstance(registry, dict):
        raise ChannelFootprintError("sources config channels must be an object of channel labels")
    global CHANNELS
    for channel, label in registry.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]+", channel) or not isinstance(label, str) or not label:
            raise ChannelFootprintError("invalid channel registry entry")
        CHANNEL_LABELS[channel] = label
    CHANNELS = tuple(dict.fromkeys((*CHANNELS, *registry)))
    return raw


# ── OS client: metered actors, Meta library, web search; free fetches ──────

@dataclass
class OsClient:
    os_url: str
    api_key: str
    cache_dir: Path
    max_actor_runs: int = MAX_ACTOR_RUNS_PER_ATTEMPT
    max_meta_searches: int = MAX_META_SEARCHES_PER_ATTEMPT
    max_search_calls: int = MAX_SEARCH_CALLS_PER_ATTEMPT
    max_fetches: int = MAX_FETCHES_PER_ATTEMPT
    max_cdx_calls: int = MAX_CDX_CALLS_PER_ATTEMPT
    max_spyfu_calls: int = MAX_SPYFU_CALLS_PER_ATTEMPT
    actor_runs: int = 0
    meta_searches: int = 0
    search_calls: int = 0
    fetches: int = 0
    cdx_calls: int = 0
    spyfu_calls: int = 0
    cache_hits: int = 0
    cache_writes: int = 0
    touched: set[str] = field(default_factory=set)
    # Consecutive live non-budget failures per supplementary source in this attempt.
    source_failures: dict[str, int] = field(default_factory=dict)
    request: Callable[..., dict[str, Any]] | None = None
    fetch: Callable[[str], tuple[int, str]] | None = None
    max_image_fetches: int = MAX_IMAGE_FETCHES_PER_ATTEMPT
    image_fetches: int = 0
    max_relevance_calls: int = MAX_RELEVANCE_CALLS_PER_ATTEMPT
    relevance_calls: int = 0
    fetch_bytes: Callable[[str], tuple[int, bytes]] | None = None
    # The cutoff this client collects for: spend is reported per cutoff, and
    # answers reused from an earlier cutoff are counted apart.
    cutoff: str = ""
    sleep: Callable[[float], None] | None = None
    # Prefix of the wire Idempotency-Key. Sections that send byte-identical
    # payloads (Creative Patterns reuses these actor inputs, and at every new
    # cutoff) set their own scope so the gateway never merges their starts.
    key_scope: str = ""
    max_total_paid_starts: int | None = None
    cumulative_budget_path: Path | None = None

    def _http(self, path: str, payload: dict[str, Any], timeout: float, *, idempotency_key: str | None = None) -> dict[str, Any]:
        url = f"{self.os_url.rstrip('/')}{path}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "application/json"}
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
            raise ChannelFootprintError(f"OS {path} failed: HTTP {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise OsUnreachable(f"OS {path} unreachable: {exc.reason}") from exc
        except (OSError, http.client.HTTPException, ValueError) as exc:
            # A read timeout or a dropped connection after the request was
            # sent surfaces outside URLError; it is a provider failure too.
            raise ChannelFootprintError(f"OS {path} failed in transit: {type(exc).__name__}: {str(exc)[:200]}") from exc
        data = envelope.get("data")
        if envelope.get("code") not in (None, 200) or not isinstance(data, dict):
            raise ChannelFootprintError(f"OS {path} returned no data: {str(envelope)[:300]}")
        return data

    def _fetch_url(self, url: str) -> tuple[int, str]:
        """Plain GET of a public page; the status and a bounded body."""
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        timeout = CDX_TIMEOUT_SECONDS if url.startswith(WAYBACK_CDX_URL) else FETCH_TIMEOUT_SECONDS
        try:
            for _name, _value in _connection_headers(req.full_url).items():
                req.add_unredirected_header(_name, _value)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(FETCH_MAX_BYTES + 1)
                status = int(getattr(resp, "status", 200) or 200)
        except urllib.error.HTTPError as exc:
            return exc.code, ""
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ChannelFootprintError(f"fetch of {url} failed: {getattr(exc, 'reason', exc)}") from exc
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
        self.cache_writes += 1

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

    def _reserve_paid_start(self, kind: str, digest: str) -> None:
        """A durable total cap survives every retry, failed call and restart."""
        if self.max_total_paid_starts is None:
            return
        path = self.cumulative_budget_path or self.cache_dir.parent / "budget.json"
        try:
            budget = json.loads(path.read_text())
        except FileNotFoundError:
            try:
                legacy = [line for line in (self.cache_dir / "starts.log").read_text().splitlines() if line]
            except OSError:
                legacy = []
            budget = {"schema_version": 1, "limit": self.max_total_paid_starts, "paid_starts": [{"kind": "legacy_actor", "digest": line.split()[-1], "started_on": line.split()[0]} for line in legacy]}
            _write_atomic(path, json.dumps(budget, indent=1))
        except (OSError, json.JSONDecodeError) as exc:
            raise ChannelFootprintError(f"invalid cumulative budget ledger: {exc}") from exc
        if budget.get("schema_version") != 1 or type(budget.get("limit")) is not int or budget["limit"] < 0 or not isinstance(budget.get("paid_starts"), list):
            raise ChannelFootprintError("invalid cumulative budget ledger shape")
        # A new invocation cannot silently raise the previously accepted cap.
        maximum = min(int(budget["limit"]), self.max_total_paid_starts)
        starts = budget.get("paid_starts", [])
        if len(starts) >= maximum:
            raise BudgetExhausted(f"cumulative paid-start budget exhausted ({maximum}); remaining checks are budget_deferred")
        starts.append({"kind": kind, "digest": digest, "started_on": date.today().isoformat()})
        budget.update(limit=maximum, paid_starts=starts, spent_starts=len(starts), money_estimate=None)
        _write_atomic(path, json.dumps(budget, indent=1))

    def _metered(self, kind: str, path: str, payload: dict[str, Any], timeout: float, *, budget_attr: str, budget_max: int, label: str, paid: bool, retry_delay: float,
                 cache_payload: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
        cache_payload = payload if cache_payload is None else cache_payload
        key_raw = json.dumps({"kind": kind, "path": path, "payload": cache_payload}, sort_keys=True)
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
        wire_key = None
        while True:
            if getattr(self, budget_attr) >= budget_max:
                progress = (
                    f"{self.cache_writes} new answer(s) cached in this attempt; rerun to continue from the cache"
                    if self.cache_writes
                    else "nothing new was cached in this attempt: a failing per-domain source costs up to "
                    f"{2 * SOURCE_BREAKER_FAILURES} starts before it is skipped, so raise the budget or narrow --sources"
                )
                raise BudgetExhausted(f"{label} budget exhausted ({budget_max} per attempt); {progress}")
            self._reserve_paid_start(kind, digest)
            setattr(self, budget_attr, getattr(self, budget_attr) + 1)
            if paid:
                # Paid starts count BEFORE the transport call (fail closed)
                # and are journaled durably: a failed start may still bill.
                # Every start gets its own key, including an in-attempt retry:
                # the gateway released the failed start's wallet hold, and a
                # reused key would run the actor without being able to settle.
                wire_key = f"{self.key_scope}{digest}-{self._prior_start_count(digest)}"
                self._journal_start(digest)
            try:
                response = transport(path, payload, timeout, idempotency_key=wire_key)
                break
            except ChannelFootprintError as exc:
                if (kind == "actor" and re.search(r"HTTP 400\b", str(exc))) or (
                    kind == "spyfu" and re.search(r"HTTP 4(?:00|22)\b", str(exc))
                ):
                    # The provider rejected this input (observed live: an
                    # actor URL list without schemes; SpyFu answers 400 for an
                    # unsupported market); cache the rejection so replays stay
                    # byte-stable and never pay for the same refusal again.
                    response = {"unavailable": str(exc)[:400]}
                    break
                unreachable = isinstance(exc, OsUnreachable)
                if attempts >= 1 or not (unreachable or re.search(r"HTTP 5\d\d", str(exc))):
                    raise
                attempts += 1
                (self.sleep or time.sleep)(max(retry_delay, OS_UNREACHABLE_RETRY_DELAY_SECONDS) if unreachable else retry_delay)
        retrieved_on = date.today().isoformat()
        self._cache_write(cache_file, {"kind": kind, "path": path, "payload": cache_payload, "response": response, "retrieved_on": retrieved_on})
        return (response if isinstance(response, dict) else {}), retrieved_on

    def _shared(self) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir

    def _download(self, url: str) -> tuple[int, bytes]:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.8"})
        try:
            with urllib.request.urlopen(req, timeout=IMAGE_TIMEOUT_SECONDS) as resp:
                return int(getattr(resp, "status", 200) or 200), resp.read(MAX_IMAGE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            return exc.code, b""
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ChannelFootprintError(f"image download failed: {getattr(exc, 'reason', exc)}") from exc

    def fetch_image(self, url: str) -> dict[str, Any] | None:
        """Free, cached download of one ad image. Bytes are kept under the
        shared cache by content hash, so a rerun can classify again after the
        platform's signed URL has expired. Returns the image, None when the
        image is definitively unusable (not a JPEG, PNG or WebP, too large,
        HTTP 4xx; cached as such), or {"transient": ...} for a rate limit,
        server error or network failure (not cached; retried next attempt)."""
        digest = hashlib.sha256(json.dumps({"kind": "image", "url": url}, sort_keys=True).encode("utf-8")).hexdigest()
        cache_file = self._shared() / f"{digest}.json"
        self.touched.add(digest)
        entry = self._cache_read(cache_file)
        if entry is not None:
            response = entry.get("response") if isinstance(entry.get("response"), dict) else {}
            blob = self._shared() / "images" / str(response.get("file") or "")
            if not response.get("sha256") or blob.is_file():
                self.cache_hits += 1
                return response if response.get("sha256") else None
        if self.image_fetches >= self.max_image_fetches:
            raise BudgetExhausted(f"image download budget exhausted ({self.max_image_fetches} per attempt); rerun to continue from the cache")
        self.image_fetches += 1
        try:
            status, content = (self.fetch_bytes or self._download)(url)
        except ChannelFootprintError as exc:
            return {"transient": str(exc)[:200]}
        if _transient_status(status):
            return {"transient": f"HTTP {status}"}
        media_type = sniff_image(content) if status == 200 and 0 < len(content) <= MAX_IMAGE_BYTES else None
        response: dict[str, Any] = {"status": status}
        if media_type:
            sha = hashlib.sha256(content).hexdigest()
            ext = media_type.split("/", 1)[1]
            (self._shared() / "images").mkdir(parents=True, exist_ok=True)
            # Atomic: the same bytes may be hard-linked into published assets.
            tmp = self._shared() / "images" / f".{sha}.{ext}.tmp"
            tmp.write_bytes(content)
            tmp.replace(self._shared() / "images" / f"{sha}.{ext}")
            response.update(sha256=sha, media_type=media_type, file=f"{sha}.{ext}", bytes=len(content))
        else:
            response["unusable"] = "not a JPEG, PNG or WebP image under 4 MB" if status == 200 else f"HTTP {status}"
        self._cache_write(cache_file, {"kind": "image", "url": url, "response": response, "cutoff": self.cutoff,
                                       "retrieved_on": date.today().isoformat()})
        return response if media_type else None

    def image_bytes(self, image: dict[str, Any]) -> bytes:
        return (self._shared() / "images" / image["file"]).read_bytes()

    def classify_relevance(self, payload: dict[str, Any]) -> dict[str, Any]:
        """One cached classifier call (an AI upstream call), reserved in the
        durable budget like a provider start. The cache key covers frame
        hashes, never the image bytes."""
        key = {**payload, "frames": [{k: v for k, v in frame.items() if k != "content_base64"} for frame in payload.get("frames", [])]}
        response, _ = self._metered("relevance", RELEVANCE_PATH, payload, RELEVANCE_TIMEOUT_SECONDS, budget_attr="relevance_calls",
                                    budget_max=self.max_relevance_calls, label="relevance classification", paid=False,
                                    retry_delay=FREE_RETRY_DELAY_SECONDS, cache_payload=key)
        return response

    def run_actor(self, actor: str, actor_input: dict[str, Any], limit: int) -> tuple[list[dict[str, Any]], str]:
        payload = {"actor": actor, "input": actor_input, "sync": True, "limit": limit}
        response, retrieved_on = self._metered(
            "actor", "/scrape/apify/run", payload, 330.0,
            budget_attr="actor_runs", budget_max=self.max_actor_runs, label="actor-run", paid=True, retry_delay=ACTOR_RETRY_DELAY_SECONDS,
        )
        if response.get("unavailable"):
            raise SourceUnavailable(f"actor {actor} rejected the request: {response['unavailable']}")
        rows = response.get("rows")
        return ([r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []), retrieved_on

    def meta_library_search(self, payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        response, retrieved_on = self._metered(
            "meta-ad-library", "/tools/meta-ad-library/search", payload, 90.0,
            budget_attr="meta_searches", budget_max=self.max_meta_searches, label="meta-ad-library", paid=False, retry_delay=FREE_RETRY_DELAY_SECONDS,
        )
        rows = response.get("data")
        return ([r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []), retrieved_on

    def spyfu_domain_stats(self, domain: str, country: str, months: int) -> tuple[dict[str, Any], str]:
        """SpyFu's modeled Google Ads budget, paid clicks and paid keywords per
        month. Billed per returned row (one per month) to the shared account;
        the gateway's daily `spyfu:rows` limit bounds it per claw."""
        response, retrieved_on = self._metered(
            "spyfu", "/tools/spyfu/domain-stats", {"domain": domain, "country_code": country, "months": months}, 90.0,
            budget_attr="spyfu_calls", budget_max=self.max_spyfu_calls, label="SpyFu lookup", paid=False, retry_delay=FREE_RETRY_DELAY_SECONDS,
        )
        if response.get("unavailable"):
            raise SourceUnavailable(f"SpyFu rejected the request: {response['unavailable']}")
        return response, retrieved_on

    def brave(self, query: str, count: int, country: str) -> tuple[dict[str, Any], str]:
        return self._metered(
            "search", "/search/web/brave", {"query": query, "count": count, "country": country}, 60.0,
            budget_attr="search_calls", budget_max=self.max_search_calls, label="web search", paid=False, retry_delay=FREE_RETRY_DELAY_SECONDS,
        )

    def fetch_page(self, url: str, *, budget_attr: str = "fetches", budget_max: int | None = None, label: str = "page fetch") -> tuple[dict[str, Any], str]:
        """Free, cached GET of a public page or API; failures are cached as a
        status so a blocked site does not get hammered on every rerun."""
        kind = "cdx" if budget_attr == "cdx_calls" else "fetch"
        key_raw = json.dumps({"kind": kind, "url": url}, sort_keys=True)
        digest = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        self.touched.add(digest)
        entry = self._cache_read(cache_file)
        if entry is not None:
            cached = entry.get("response") if isinstance(entry.get("response"), dict) else {}
            if _transient_status(cached.get("status")):
                # An older runner cached rate limits and server errors; such
                # an entry is a miss, never a replayable answer.
                IO.drop_cache_entry(cache_file)
            else:
                self.cache_hits += 1
                return cached, entry.get("retrieved_on") or date.today().isoformat()
        maximum = self.max_fetches if budget_max is None else budget_max
        if getattr(self, budget_attr) >= maximum:
            raise BudgetExhausted(f"{label} budget exhausted ({maximum} per attempt); {self.cache_writes} new answer(s) cached in this attempt; rerun to continue from the cache")
        setattr(self, budget_attr, getattr(self, budget_attr) + 1)
        transport = self.fetch or self._fetch_url
        retrieved_on = date.today().isoformat()
        try:
            status, body = transport(url)
            response: dict[str, Any] = {"status": status, "body": body}
        except ChannelFootprintError as exc:
            # A timeout or connection error is transient: report it for this
            # attempt but do not cache it, so a rerun tries again (bounded by
            # the per-attempt budget).
            return {"status": None, "body": "", "error": str(exc)[:200]}, retrieved_on
        if _transient_status(status):
            # Rate limits and server errors are transient as well: not cached,
            # not an observation.
            return {**response, "error": f"HTTP {status}"}, retrieved_on
        self._cache_write(cache_file, {"kind": kind, "url": url, "response": response, "retrieved_on": retrieved_on})
        return response, retrieved_on

    def ledger_totals(self) -> dict[str, Any]:
        """Durable provenance over entries THIS execution touched. A cached
        actor rejection is a journaled start, not a successful observation."""
        counts = {"actor": 0, "meta-ad-library": 0, "search": 0, "spyfu": 0, "fetch": 0, "cdx": 0, "relevance": 0}
        rejected = 0
        rejected_spyfu = 0
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
                    if kind == "spyfu":
                        rejected_spyfu += 1
                    else:
                        rejected += 1
                elif kind in ("fetch", "cdx") and _transient_status(response.get("status")):
                    continue  # an older cache entry of a rate limit or server error is not an observation
                elif kind in counts:
                    counts[kind] += 1
                if isinstance(entry.get("retrieved_on"), str):
                    dates.append(entry["retrieved_on"])
        today = date.today().isoformat()
        try:
            starts_recorded = sum(1 for line in (self.cache_dir / "starts.log").read_text(encoding="utf-8").splitlines() if line)
        except OSError:
            starts_recorded = 0
        return {
            "actor_runs": counts["actor"],
            "meta_searches": counts["meta-ad-library"],
            "search_calls": counts["search"],
            "fetches": counts["fetch"],
            "cdx_calls": counts["cdx"],
            "spyfu_calls": counts["spyfu"],
            "relevance_calls": counts["relevance"],
            "provider_calls": counts["actor"] + counts["meta-ad-library"] + counts["search"] + counts["spyfu"],
            "rejected_actor_runs": rejected,
            "rejected_spyfu_calls": rejected_spyfu,
            # Every successful observation, metered or free: the completion
            # proof for selections that use only free sources.
            "observations": counts["actor"] + counts["meta-ad-library"] + counts["search"] + counts["spyfu"] + counts["fetch"] + counts["cdx"],
            "actor_starts_recorded": starts_recorded,
            "first_retrieved_on": min(dates) if dates else today,
            "last_retrieved_on": max(dates) if dates else today,
        }


# ── inputs ──────────────────────────────────────────────────────────────────

def parse_domains(raw: str, cap: int) -> list[str]:
    domains: list[str] = []
    for term in (raw or "").split(","):
        domain = registrable_domain(term)
        if domain and _DOMAIN_RE.match(domain) and domain not in domains:
            domains.append(domain)
    return domains[:cap]


DOMAIN_SOURCES = frozenset({"pixels", "history", "traffic", "linkedin", "reddit"})  # one check per domain, not per country
EXPANDABLE_SOURCES = frozenset({"google", "meta", "tiktok", "linkedin"})  # a direct sample may be expanded once


def check_starts(source: str, country: str | None, pixel_actor_fallback: bool = False) -> dict[str, int]:
    """Paid provider starts of one check, by provider kind."""
    if source == "partners":
        return {"search": 3}
    if source == "spyfu":
        return {"spyfu": 1}
    if source == "meta":
        return {"actor": 1, "meta-ad-library": 1} if country in EU_COUNTRIES else {"actor": 1}
    if source == "tiktok":
        return {"actor": 1} if country in EU_COUNTRIES else {}
    if source == "pixels":
        return {"actor": 1} if pixel_actor_fallback else {}
    return {"actor": 1} if source in {"traffic", "google", "linkedin", "reddit"} else {}


def collection_plan(competitors: list[tuple[str, str]], sources: list[str], target_countries: list[str], *,
                    pixel_actor_fallback: bool = False) -> list[dict[str, Any]]:
    """Every (domain, tier) x source x country check with its upper bound of
    paid provider starts. Every scoped domain is collected regardless of role."""
    plan = []
    for domain, role in competitors:
        for source in sources:
            for country in ([None] if source in DOMAIN_SOURCES else target_countries):
                starts = check_starts(source, country, pixel_actor_fallback)
                plan.append({"domain": domain, "competitor_tier": role, "source": source, "country": country,
                             "max_expansion_factor": 2 if source in EXPANDABLE_SOURCES else 1,
                             "provider_starts": starts, "provider_starts_upper_bound": sum(starts.values())})
    return plan


def sniff_image(content: bytes) -> str | None:
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def typed_intake(workspace: Path) -> dict[str, Any]:
    """Use the existing typed-input validator; no prose or project discovery."""
    loader = _load_script("run-competitor-set.py", "pmr_typed_intake_for_channels")
    try:
        return loader.load_intake(workspace / _artifact_path("egbe-docs/research/market/intake.json")) or {}
    except loader.CompetitorSetError as exc:
        raise ValueError(str(exc)) from exc


def relevance_context(workspace: Path, args: argparse.Namespace) -> tuple[str, list[str]]:
    """The offer the classifier judges ads against, and the audience languages."""
    parts = [IO.context_text(workspace, SECTION_ID)]
    intake = typed_intake(workspace)
    offer = {key: value for key, value in (intake.get("offer") or {}).items()
             if value not in (None, "", [])}
    if offer:
        parts.append("Offer card: " + json.dumps(offer, ensure_ascii=False))
    text = "\n\n".join(part for part in parts if part)
    if len(text) > 24000:
        raise ChannelFootprintError("relevance context exceeds 24000 characters; supply bounded context")
    explicit = str(_arg(args, "languages", "") or "")
    languages = ([code.strip().lower() for code in explicit.split(",") if code.strip()]
                 if explicit else list(intake.get("languages") or []))
    _load_script("creative-semantics.py", "pmr_relevance_context_validator").build_semantic_context(text, languages)
    return text, languages


def model_relevance(client: "OsClient", corpus: list[dict[str, Any]], pending: list[str], decisions: dict[str, Any], context_hash: str,
                    product_context: str, languages: list[str]) -> dict[str, Any] | None:
    """Decide pending ads by the classifier's relevance verdict from their text
    or their downloaded image; an ad with neither stays pending for review.
    None: nothing new was decided (nothing to judge, or the budget stopped)."""
    platforms = set(_taxonomy()["platforms"])
    judged = []
    for ad in (ad for ad in corpus if ad["ad_id"] in pending and str(ad["platform"]).removesuffix("_ads") in platforms):
        text = (ad.get("ad_text") or "").strip()  # a CTA label alone is no copy: the offer is in the picture
        image = client.fetch_image(ad["image_url"]) if not text and ad.get("image_url") else None
        if text or (image and image.get("sha256")):
            judged.append((ad, image if image and image.get("sha256") else None))
    if not judged:
        return None
    semantic = _load_script("creative-semantics.py", "pmr_semantics_for_footprint").build_semantic_context(product_context, languages)
    new: list[dict[str, Any]] = []
    for start in range(0, len(judged), RELEVANCE_BATCH):
        batch = {ad["ad_id"]: ad for ad, _ in judged[start:start + RELEVANCE_BATCH]}
        frames = [{"ref": f"{ad['ad_id']}/image", "timestamp_seconds": 0, "media_type": image["media_type"], "sha256": image["sha256"],
                   "content_base64": base64.b64encode(client.image_bytes(image)).decode("ascii")} for ad, image in judged[start:start + RELEVANCE_BATCH] if image]
        creatives = [{"ad_ref": ad_id, "platform": str(ad["platform"]).removesuffix("_ads"), "advertiser": str(ad.get("advertiser") or ad["domain"])[:200],
                      "body": (ad.get("ad_text") or None) and str(ad["ad_text"])[:4000], "cta_label": (ad.get("cta") or None) and str(ad["cta"])[:100],
                      "landing_url": (ad.get("landing_url") or None) and str(ad["landing_url"])[:2000],
                      "frame_refs": [frame["ref"] for frame in frames if frame["ref"] == f"{ad_id}/image"]} for ad_id, ad in batch.items()]
        try:
            data = client.classify_relevance({"schema_version": 1, "taxonomy_version": _taxonomy()["taxonomy_version"], "semantic_context": semantic,
                                              "creatives": creatives, "frames": frames})
        except BudgetExhausted:
            break  # the rest stays pending; a rerun continues from the cache
        for item in data.get("classifications") or []:
            ad = batch.get(item.get("ad_ref"))
            if ad is None:
                continue
            verdict = (item.get("semantics") or {}).get("relevance") or {}
            status = verdict.get("status") if verdict.get("status") in {"relevant", "irrelevant"} else "unknown"
            excerpt = f' Excerpt: "{verdict["excerpt"]}".' if verdict.get("excerpt") else ""
            source = "ad_text" if (ad.get("ad_text") or "").strip() else "image"
            new.append({"ad_id": ad["ad_id"], "candidate_sha256": ad["candidate_sha256"], "relevance": status,
                        "reason": f"{verdict.get('reason') or 'The classifier gave no reason.'}{excerpt} (classifier role {data.get('model_role')})",
                        "evidence_refs": [f"{ad['ad_id']}:{source}", *([ad["landing_url"]] if ad.get("landing_url") else [])], "decided_by": "model"})
    if not new:
        return None
    decided = {d["ad_id"] for d in new}
    return {"schema_version": 1, "product_context_sha256": context_hash,
            "decisions": [d for d in decisions.get("decisions", []) if d.get("ad_id") not in decided] + new}


def _taxonomy() -> dict[str, Any]:
    return json.loads((Path(__file__).resolve().parent.parent / "references/config/creative-taxonomy.v1.json").read_text(encoding="utf-8"))


def collection_budget(plan: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    """Persistent shared cap, including expansion and the configured retry reserve.

    Starts are not allocated to provider kinds in the ledger. Failed uncached
    requests can consume the pool across resumed attempts, so each active kind's
    conservative upper bound is the whole pool, rather than a promised share.
    """
    reserve = int(config.get("budget", {}).get("retry_reserve_factor", 1))
    if reserve < 0:
        raise ChannelFootprintError("retry reserve factor must be nonnegative")
    base, expanded = {}, {}
    for check in plan:
        for kind, starts in check["provider_starts"].items():
            base[kind] = base.get(kind, 0) + starts
            expanded[kind] = expanded.get(kind, 0) + starts * check["max_expansion_factor"]
    limit = max(1, sum(expanded.values()) * (1 + reserve))
    return {"base": base, "expanded": expanded, "upper": {kind: limit for kind in expanded},
            "retry_reserve_factor": reserve, "cumulative_limit": limit}


def paid_start_budget(plan: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, int]:
    """Aggregate runner budget projected from the shared provider calculation."""
    budget = collection_budget(plan, config)
    return {"base": sum(budget["base"].values()), "bounded": sum(budget["expanded"].values()),
            "retry_reserve_factor": budget["retry_reserve_factor"], "cumulative_limit": budget["cumulative_limit"]}


def parse_sources(raw: str) -> list[str]:
    if not (raw or "").strip():
        return list(ALL_SOURCES)
    chosen = [s.strip().lower() for s in raw.split(",") if s.strip()]
    unknown = [s for s in chosen if s not in ALL_SOURCES]
    if unknown:
        raise ChannelFootprintError(f"unknown sources: {', '.join(unknown)} (known: {', '.join(ALL_SOURCES)})")
    return [s for s in ALL_SOURCES if s in chosen]


def domains_from_competitor_set(workspace: Path, cap: int) -> list[str]:
    evidence = _load_script("research-evidence.py", "pmr_evidence_for_channel_footprint")
    return evidence.competitor_set_inputs(workspace, consumer=SECTION_ID, cap=cap)


def domains_from_keyword_evidence(workspace: Path, cap: int, exclude=frozenset()) -> list[str]:
    evidence = _load_script("research-evidence.py", "pmr_evidence_for_channel_footprint_kwe")
    return evidence.keyword_inputs(workspace, consumer=SECTION_ID, row_type="competitor_domain", field="domain", cap=cap, exclude=exclude)


def domains_excluded_by_competitor_set(workspace: Path) -> set[str]:
    """Domains the completed Competitor Set rejected; never refilled automatically."""
    evidence = _load_script("research-evidence.py", "pmr_evidence_for_channel_footprint_excl")
    return evidence.competitor_set_excluded_domains(workspace)


@dataclass
class RunInputs:
    domains: list[str]
    domain_sources: dict[str, str]
    product_domain: str
    sources: list[str]
    country: str
    eu_country: str
    pixel_actor_fallback: bool
    target_countries: list[str] = field(default_factory=list)
    competitor_context: dict[str, dict[str, Any]] = field(default_factory=dict)
    product_context_sha256: str = ""
    effective_policy: dict[str, Any] = field(default_factory=dict)
    relevance_decisions: dict[str, Any] = field(default_factory=dict)
    stage: str = "all"
    # Sample expansions recorded by the previous compatible collect.
    prior_expansions: list[dict[str, Any]] = field(default_factory=list)


# ── helpers ─────────────────────────────────────────────────────────────────

def _days_between(start_iso: str | None, end_iso: str | None) -> int | None:
    try:
        start = date.fromisoformat(str(start_iso)[:10])
        end = date.fromisoformat(str(end_iso)[:10])
    except (ValueError, TypeError):
        return None
    return max(0, (end - start).days)


def _iso_from_epoch(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        if isinstance(value, str) and value.strip():
            digits = value.strip()
            if digits.isdigit():
                value = int(digits)
            else:
                return digits[:10]
        else:
            return None
    try:
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000.0
        return datetime.fromtimestamp(seconds, tz=timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


_GENERIC_NAME_TOKENS = {
    "inc", "llc", "ltd", "co", "corp", "corporation", "gmbh", "app", "apps", "software", "hq", "official",
    "team", "teams", "io", "ai", "com", "labs", "technologies", "technology", "tech", "the", "limited", "plc", "sas", "srl",
    # product-tier pages a brand runs under its own name
    "pro", "plus", "premium", "business", "enterprise", "for", "education", "edu", "learn", "academy",
}
# Handle prefixes platforms put in front of an advertiser name.
_NAME_PREFIX_RE = re.compile(r"^\s*(?:u/|r/|@)+", re.IGNORECASE)


def _name_matches(name: Any, brand: str) -> bool:
    """Advertiser identity: the name IS the brand (plus generic corporate or
    product-tier suffixes), not merely a name that contains the brand token:
    'Mural Painting Co' is a namesake of mural.co, 'Lucid Software' and
    'Codecademy Pro' are the brands."""
    if not brand:
        return False
    tokens = [t for t in re.split(r"[^a-z0-9]+", _NAME_PREFIX_RE.sub("", str(name or "")).lower()) if t]
    if not tokens:
        return False
    joined = "".join(tokens)
    if joined == brand:
        return True
    for size in range(1, len(tokens) + 1):
        if "".join(tokens[:size]) == brand:
            return all(t in _GENERIC_NAME_TOKENS for t in tokens[size:])
        if len("".join(tokens[:size])) > len(brand):
            break
    return False


def _mentions(text: Any, brand: str) -> bool:
    """Free text (a search result title or address) that names the brand."""
    return bool(brand) and brand in re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def _chunks(items: list[str], size: int) -> list[list[str]]:
    size = max(1, int(size))
    return [items[i:i + size] for i in range(0, len(items), size)]


def _transient_status(status: Any) -> bool:
    return isinstance(status, int) and not isinstance(status, bool) and (status == 429 or status >= 500)


def _provider_detail(exc: BaseException) -> str:
    """The provider's message without the per-attempt counter that
    `_call_with_context` appends, so evidence stays byte-stable on replay.
    Only our own wrapper is unwrapped; a transport error's cause (urllib)
    would lose the gateway's message."""
    inner = exc.__cause__ if isinstance(exc.__cause__, ChannelFootprintError) else exc
    return str(inner).split(" — this attempt had already started", 1)[0][:240]


def _coverage_gap(coverage: list[dict[str, Any]], source: str, domains: list[str], detail: str, status: str = "unavailable") -> None:
    coverage.extend({"type": "coverage", "domain": d, "source": source, "status": status, "detail": detail[:240], "tier": "C"} for d in domains)


def _attempt(client: OsClient, coverage: list[dict[str, Any]], source: str, domains: list[str], fn: Callable[[], Any]) -> Any:
    """One supplementary provider call. A failure other than budget
    exhaustion becomes a coverage gap for THESE domains only; results already
    collected for other domains stay and later domains are still attempted.
    After SOURCE_BREAKER_FAILURES consecutive failures of the same source the
    remaining domains are skipped without starting more paid runs. Budget
    exhaustion and an unreachable OS always propagate so a rerun resumes from
    the cache."""
    failures = client.source_failures.get(source, 0)
    if failures >= SOURCE_BREAKER_FAILURES:
        _coverage_gap(coverage, source, domains, f"skipped after {failures} consecutive {source} failures in this attempt; rerun to retry")
        return None
    hits_before = client.cache_hits
    try:
        result = fn()
    except BudgetExhausted as exc:
        if "cumulative" not in str(exc):
            raise
        _coverage_gap(coverage, source, domains, str(exc), status="budget_deferred")
        return None
    except OsUnreachable:
        raise
    except ChannelFootprintError as exc:
        # Only a LIVE failure feeds the breaker: a rejection replayed from the
        # cache costs nothing, and counting it would skip the remaining
        # domains on every rerun forever.
        if client.cache_hits == hits_before:
            client.source_failures[source] = failures + 1
        _coverage_gap(coverage, source, domains, _provider_detail(exc))
        return None
    client.source_failures[source] = 0
    return result


def _call_with_context(client: OsClient, subject: str, label: str, fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except ChannelFootprintError as exc:
        # Keep the subclass: a cached provider rejection stays recognisable.
        raise type(exc)(
            f"{label} for `{subject}` failed: {exc} — this attempt had already started "
            f"{client.actor_runs}/{client.max_actor_runs} actor run(s); see GET /me/limits?resource=apify:runs "
            "for remaining daily quota."
        ) from exc


def _cumulative_answer(coverage: list[dict[str, Any]] | None, source: str, domains: list[str], country: str | None, fn: Callable[[], Any]) -> Any:
    """Catch total-cap exhaustion at the smallest provider request unit.

    Completed chunks stay in the collector's result. Attempt exhaustion
    still stops and resumes from the provider cache.
    """
    try:
        return fn()
    except BudgetExhausted as exc:
        if "cumulative" not in str(exc):
            raise
        if coverage is not None:
            coverage.extend({"type": "coverage", "domain": d, "source": source, "country": country, "status": "budget_deferred", "detail": str(exc), "tier": "C"} for d in domains)
        return None


def usable_destination(value: Any, _depth: int = 0) -> str:
    """The registrable domain of an ad destination when the value is really
    an address (not display text such as 'Learn more') and not the platform
    itself, a messaging or short host, a store, a link hub or a shortener;
    otherwise '' so the advertiser name decides. Click-tracking wrappers
    (l.facebook.com/l.php?u=...) are unwrapped to the address they carry."""
    text = str(value or "").strip()
    if not text or " " in text or "." not in text:
        return ""
    lowered = text.lower()
    host = lowered
    query = ""
    if "//" in lowered:
        parsed = urllib.parse.urlparse(lowered)
        host = parsed.hostname or ""
        query = parsed.query
    host = host.split("/", 1)[0].split("?", 1)[0].removeprefix("www.").rstrip(".")
    if host.split(":", 1)[0] in REDIRECT_WRAPPER_HOSTS or ("www." + host) in REDIRECT_WRAPPER_HOSTS:
        wrapped = urllib.parse.parse_qs(query).get("u") or urllib.parse.parse_qs(query).get("q") or []
        if wrapped and _depth < 2:
            return usable_destination(urllib.parse.unquote(wrapped[0]), _depth + 1)
        return ""
    domain = registrable_domain(text)
    if not domain or not _DOMAIN_RE.match(domain):
        return ""
    if domain in NEUTRAL_DESTINATION_HOSTS or host.split(":", 1)[0] in NEUTRAL_DESTINATION_HOSTS:
        return ""
    return domain


def meta_search_url(brand: str, country: str, active_status: str = "all") -> str:
    """The public Ad Library page search. `all` also lists stopped ads that
    Meta still keeps (observed 2026-10-02: 58 of 71 US results for four
    global brands were inactive), so a sample of 30 is mostly old ads;
    `active` lists running ads only."""
    if active_status not in ("all", "active"):
        raise ValueError(f"unsupported Meta active_status {active_status!r}")
    return (
        f"https://www.facebook.com/ads/library/?active_status={active_status}&ad_type=all"
        f"&country={urllib.parse.quote(country)}&q=%22{urllib.parse.quote(brand)}%22&search_type=keyword_unordered&media_type=all"
    )


# ── pixels ──────────────────────────────────────────────────────────────────

def detect_tags(blobs: list[str]) -> list[dict[str, str]]:
    """Match the versioned signature list over page HTML and container JS."""
    text = "\n".join(html_lib.unescape(b or "") for b in blobs)
    found: list[dict[str, str]] = []
    for tag, channel, pattern in TAG_SIGNATURES:
        if re.search(pattern, text, re.IGNORECASE):
            found.append({"tag": tag, "channel": channel})
    return found


def detect_tag_managers(blobs: list[str]) -> list[str]:
    text = "\n".join(html_lib.unescape(b or "") for b in blobs)
    return [name for name, pattern in TAG_MANAGER_SIGNATURES if re.search(pattern, text, re.IGNORECASE)]


def linkedin_company_slug(body: str) -> str | None:
    """The competitor's own LinkedIn page link (footer, schema markup)."""
    for match in LINKEDIN_COMPANY_RE.finditer(html_lib.unescape(body or "")):
        slug = match.group(1).strip("/").lower()
        if slug and slug not in {"company", "school", "showcase", "login", "signup"}:
            return slug
    return None


def scan_site(client: OsClient, domain: str) -> dict[str, Any]:
    """Home page plus up to three Google Tag Manager containers."""
    page, _ = client.fetch_page(f"https://{domain}/")
    status = page.get("status")
    body = str(page.get("body") or "")
    if status is None:
        fetch_status = "error"
    elif int(status) >= 400 or (int(status) < 300 and not body.strip()):
        fetch_status = "blocked" if int(status) in (401, 403, 429, 503) else "error"
    else:
        fetch_status = "ok"
    containers = list(dict.fromkeys(GTM_ID_RE.findall(body)))[:GTM_CONTAINERS_PER_SITE] if fetch_status == "ok" else []
    blobs = [body]
    for container in containers:
        gtm, _ = client.fetch_page(f"https://www.googletagmanager.com/gtm.js?id={container}")
        blobs.append(str(gtm.get("body") or ""))
    tags = detect_tags(blobs) if fetch_status == "ok" else []
    managers = detect_tag_managers(blobs) if fetch_status == "ok" else []
    return {
        "type": "pixel_scan",
        "domain": domain,
        "fetch_status": fetch_status,
        "http_status": status,
        "via": "html",
        "gtm_containers": containers,
        "tag_managers": managers,
        "tags_detected": [t["tag"] for t in tags],
        "channels_detected": sorted({t["channel"] for t in tags}),
        "linkedin_company": linkedin_company_slug(body) if fetch_status == "ok" else None,
        "tier": "A" if fetch_status == "ok" else "C",
    }


def scan_sites_with_actor(client: OsClient, actor: str, domains: list[str]) -> dict[str, dict[str, Any]]:
    """Headless fallback for sites whose HTML cannot be fetched directly."""
    rows, _ = _call_with_context(client, ", ".join(domains), "pixel detector actor", lambda: client.run_actor(
        actor, {"startUrls": [f"https://{d}/" for d in domains], "crawlPages": False, "maxPages": 1}, limit=len(domains) * 2,
    ))
    scans: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("type") not in (None, "page"):
            continue
        domain = registrable_domain(str(row.get("url") or ""))
        if domain not in domains:
            continue
        tools = [t for t in (row.get("tools") or []) if isinstance(t, dict) and t.get("detected", True)]
        names = [str(t.get("tool") or "") for t in tools]
        tags = detect_tags([" ".join(names + [json.dumps(t.get("details") or {}) for t in tools])])
        # Tool names from the detector are mapped through the same channel
        # vocabulary by keyword; unknown tools are kept as names only.
        for name in names:
            lowered = name.lower()
            for keyword, tag, channel in (
                ("facebook pixel", "meta_pixel", "meta_ads"), ("meta pixel", "meta_pixel", "meta_ads"),
                ("google ads", "google_ads_tag", "google_ads"), ("reddit", "reddit_pixel", "reddit_ads"),
                ("linkedin insight", "linkedin_insight", "linkedin_ads"), ("tiktok", "tiktok_pixel", "tiktok_ads"),
                ("bing", "microsoft_uet", "microsoft_ads"), ("microsoft", "microsoft_uet", "microsoft_ads"),
                ("twitter", "x_pixel", "x_ads"), ("pinterest", "pinterest_tag", "pinterest_ads"),
                ("snap", "snap_pixel", "snap_ads"), ("quora", "quora_pixel", "quora_ads"),
                ("taboola", "taboola", "display_native"), ("outbrain", "outbrain", "display_native"),
                ("criteo", "criteo", "display_native"), ("capterra", "capterra_tracker", "review_marketplace"),
                ("partnerstack", "partnerstack", "affiliate"), ("impact", "impact", "affiliate"),
                ("rewardful", "rewardful", "affiliate"), ("firstpromoter", "firstpromoter", "affiliate"),
            ):
                if keyword in lowered and tag not in {t["tag"] for t in tags}:
                    tags.append({"tag": tag, "channel": channel})
        scans[domain] = {
            "type": "pixel_scan",
            "domain": domain,
            "fetch_status": "ok",
            "http_status": row.get("httpStatus"),
            "via": "actor",
            "gtm_containers": [],
            "tag_managers": [n.lower().replace(" ", "_") for n in names if any(k in n.lower() for k in ("tag manager", "segment", "tealium", "adobe launch"))][:4],
            "tags_detected": [t["tag"] for t in tags],
            "channels_detected": sorted({t["channel"] for t in tags}),
            "linkedin_company": None,
            "tools_reported": names[:40],
            "tier": "A",
        }
    return scans


# ── page history (Wayback CDX) ──────────────────────────────────────────────

def _cdx_rows(response: dict[str, Any]) -> list[list[str]]:
    try:
        value = json.loads(str(response.get("body") or "[]"))
    except json.JSONDecodeError:
        return []
    return [r for r in value[1:] if isinstance(r, list)] if isinstance(value, list) and value else []


def collect_history(client: OsClient, domain: str, today: date) -> dict[str, Any]:
    """Distinct home-page versions in the window (CDX `collapse=digest`,
    so a changed page counts once and an unchanged monthly crawl does not)
    plus the first archived date. A home page that only redirects to `www`
    has no 200 rows of its own, so `www.` is tried when the bare host is empty."""
    since = (today - timedelta(days=30 * HISTORY_MONTHS)).strftime("%Y%m")

    def fetch(host: str, *, recent: bool) -> dict[str, Any]:
        target = urllib.parse.quote(host + "/", safe="")
        url = (
            f"{WAYBACK_CDX_URL}?url={target}&output=json&fl=timestamp,digest&filter=statuscode:200"
            f"&collapse=digest&from={since}&limit={CDX_ROW_LIMIT}"
            if recent
            else f"{WAYBACK_CDX_URL}?url={target}&output=json&fl=timestamp&filter=statuscode:200&limit=1"
        )
        before = client.cache_hits
        response, _ = client.fetch_page(url, budget_attr="cdx_calls", budget_max=client.max_cdx_calls, label="Wayback CDX")
        if client.cache_hits == before:
            # The archive rate-limits bursts; space out live calls.
            (client.sleep or time.sleep)(CDX_PAUSE_SECONDS)
        return response

    host = domain
    recent = fetch(host, recent=True)
    if recent.get("status") == 200 and not _cdx_rows(recent):
        host = f"www.{domain}"
        recent = fetch(host, recent=True)
    first = fetch(host, recent=False)
    rows = _cdx_rows(recent)
    versions = {str(r[1]) for r in rows if len(r) > 1}
    months = {str(r[0])[:6] for r in rows if r}
    first_rows = _cdx_rows(first)
    first_ts = str(first_rows[0][0]) if first_rows and first_rows[0] else None
    available = recent.get("status") == 200 and first.get("status") == 200
    return {
        "type": "page_history",
        "domain": domain,
        "source": "wayback",
        "status": "ok" if available else "unavailable",
        "detail": "" if available else str(recent.get("error") or first.get("error") or f"HTTP {recent.get('status')}/{first.get('status')}")[:160],
        "archived_host": host,
        "first_archived": f"{first_ts[:4]}-{first_ts[4:6]}-{first_ts[6:8]}" if first_ts and len(first_ts) >= 8 else None,
        "months_archived_24m": len(months) if available else None,
        # Dynamic pages change their digest on every crawl; at the row cap
        # the count is a floor and the page is simply "dynamic".
        "distinct_versions_24m": len(versions) if available else None,
        "versions_capped": available and len(rows) >= CDX_ROW_LIMIT,
        "window_months": HISTORY_MONTHS,
        "tier": "B" if available else "C",
    }


# ── traffic mix ─────────────────────────────────────────────────────────────

def _share_rows(domain: str, visits: Any, shares: Any, source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(shares, dict):
        return rows
    visits_value = None
    if isinstance(visits, (int, float)) and not isinstance(visits, bool):
        visits_value = int(visits)
    elif isinstance(visits, list) and visits:
        last = visits[-1]
        if isinstance(last, dict):
            last = last.get("visits") or last.get("value")
        if isinstance(last, (int, float)) and not isinstance(last, bool):
            visits_value = int(last)
    for key, value in shares.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        share = float(value) * (100.0 if float(value) <= 1.0 else 1.0)
        channel_key = re.sub(r"[^a-z]", "_", str(key).lower()).strip("_")
        rows.append({
            "type": "traffic_mix",
            "domain": domain,
            "channel": channel_key,
            "paid_channel": TRAFFIC_CHANNEL_MAP.get(channel_key),
            "share_pct": round(share, 2),
            "share_pct_raw": share,
            "visits_monthly": visits_value,
            "source": source,
            "market_scope": "global",
            "tier": "B",
        })
    return rows


def collect_traffic(client: OsClient, spec: dict[str, Any], domains: list[str], coverage: list[dict[str, Any]]) -> list[dict[str, Any]]:
    traffic: list[dict[str, Any]] = []
    for chunk in _chunks(domains, int(spec.get("batch_domains") or 10)):
        outcome = _attempt(client, coverage, "traffic", chunk, lambda: _call_with_context(client, ", ".join(chunk), "Similarweb actor", lambda: client.run_actor(
            spec["actor"], {"startUrls": [{"url": f"https://{d}"} for d in chunk]}, limit=len(chunk) * 2,
        )))
        if outcome is None:
            continue
        rows, _ = outcome
        traffic.extend(_traffic_rows(rows, chunk, coverage))
    return traffic


def _traffic_rows(rows: list[dict[str, Any]], domains: list[str], coverage: list[dict[str, Any]]) -> list[dict[str, Any]]:
    traffic: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        # Live shape (2026-10-02): {meta: {website, request_parameter},
        # traffic: {history: [{month, visits}], sources_share: {...}}};
        # flat {domain, visits, sources_share} is accepted as well.
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        traffic_block = row.get("traffic") if isinstance(row.get("traffic"), dict) else {}
        domain = registrable_domain(str(meta.get("website") or meta.get("request_parameter") or row.get("domain") or row.get("url") or row.get("site") or ""))
        if domain not in domains or domain in seen:
            continue
        seen.add(domain)
        shares = traffic_block.get("sources_share") or row.get("sources_share") or row.get("traffic_sources") or row.get("sourcesShare") or {}
        visits = traffic_block.get("history") or row.get("visits")
        traffic.extend(_share_rows(domain, visits, shares, "similarweb_actor"))
    coverage.extend(
        {"type": "coverage", "domain": d, "source": "traffic", "status": "ok" if d in seen else "no_data", "detail": "" if d in seen else "no public Similarweb estimate (small or unlisted site)", "tier": "C"}
        for d in domains
    )
    return traffic


# ── ad libraries ────────────────────────────────────────────────────────────

def _model() -> ModuleType:
    return _load_script("channel-footprint-model.py", "pmr_channel_footprint_model")


def _presence(domain: str, platform: str, source: str, ads: list[dict[str, Any]], *, market_scope: str, verified_by: str, today: date, note: str = "", country: str | None = None, request_limit: int | None = None, raw_count: int | None = None, native_date_scope: str = "global", native_activity_scope: str = "global", retrieved_on: str | None = None) -> dict[str, Any]:
    """Raw source observation; eligibility is decided after product relevance."""
    model = _model()
    policy, _ = _load_script("research-policy.py", "pmr_channel_policy").load_policy()
    observed = min(today.isoformat(), retrieved_on) if retrieved_on else today.isoformat()
    observations = [model.observation(a, source, country, market_scope, date.fromisoformat(observed), policy, native_date_scope, native_activity_scope) for a in ads]
    durations = [o["served_days"] for o in observations if o["served_days"] is not None]
    formats: dict[str, int] = {}
    formats_recent: dict[str, int] = {}
    for ad, obs in zip(ads, observations):
        fmt = str(ad.get("format") or "unknown").lower()
        formats[fmt] = formats.get(fmt, 0) + 1
        if obs["status"] in {"active", "recent"}:
            formats_recent[fmt] = formats_recent.get(fmt, 0) + 1
    received = len(ads) if raw_count is None else raw_count
    capped = bool(request_limit and received >= request_limit)
    return {"type": "library_presence", "domain": domain, "platform": platform, "source": source,
            "matched_ads": len(ads), "active_ads": sum(o["status"] in {"active", "recent"} for o in observations),
            "oldest_days": max(durations) if durations else None,
            "latest_seen": max((o["last_shown"] for o in observations if o["last_shown"]), default=None),
            "formats": formats, "formats_recent": formats_recent, "present": bool(ads), "market_scope": market_scope,
            "verified_by": verified_by, "note": note, "tier": "A" if ads else "B",
            "country": country, "countries": [country] if country else [], "native_date_scope": native_date_scope,
            "native_activity_scope": native_activity_scope, "observed_on": observed, "source_retrieved_on": retrieved_on or observed, "ads": ads,
            "status": "observed" if ads else ("not_verifiable" if source == "reddit_inspiration_actor" else "no_matches_in_sample"),
            "sampling": {"request_limit": request_limit, "raw_received": received, "identity_matched": len(ads),
                         "limit_reached": capped, "complete": False if capped else None, "pagination_complete": None,
                         "total_ads": None, "total_lower_bound": received if capped else None}}


def collect_google(client: OsClient, spec: dict[str, Any], domains: list[str], today: date, country: str | None = None, coverage: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    per_domain = int(spec.get("ads_per_domain") or 40)
    results: list[dict[str, Any]] = []
    for chunk in _chunks(domains, int(spec.get("batch_domains") or 5)):
        outcome = _cumulative_answer(coverage, "google", chunk, country, lambda: _call_with_context(client, ", ".join(chunk), "Google Ads Transparency", lambda: client.run_actor(
            spec["actor"], {"domains": chunk, "resultType": "ads", "region": country or "ANYWHERE", "maxAdsPerSearch": per_domain}, limit=per_domain * len(chunk),
        )))
        if outcome is None:
            continue
        rows, retrieved_on = outcome
        by_domain: dict[str, list[dict[str, Any]]] = {d: [] for d in chunk}
        for row in rows:
            destination = registrable_domain(str(row.get("domain") or ""))
            if destination not in by_domain:
                continue
            first = str(row.get("firstShown") or "")[:10] or None
            last = str(row.get("lastShown") or "")[:10] or None
            by_domain[destination].append({"first_seen": first, "last_seen": last, "is_active": None, "format": row.get("format"), "raw": row})
        for domain in chunk:
            results.append(_presence(domain, "google_ads", "google_transparency_actor", by_domain[domain], market_scope="target" if country else "global", verified_by="destination", today=today, country=country, request_limit=per_domain, raw_count=sum(registrable_domain(str(r.get("domain") or "")) == domain for r in rows), retrieved_on=retrieved_on))
    return results


def collect_meta(client: OsClient, spec: dict[str, Any], domains: list[str], today: date, country: str, eu_country: str, coverage: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    per_domain = int(spec.get("ads_per_domain") or 30)
    results: list[dict[str, Any]] = []
    for chunk in _chunks(domains, int(spec.get("batch_domains") or 5)):
        brands = {d: brand_token(d) for d in chunk}
        outcome = _cumulative_answer(coverage, "meta", chunk, country, lambda: _call_with_context(client, ", ".join(chunk), "Meta Ads Library (page search actor)", lambda: client.run_actor(
            spec["actor"], {"urls": [{"url": meta_search_url(brands[d], country)} for d in chunk], "count": per_domain}, limit=per_domain * len(chunk),
        )))
        if outcome is None:
            continue
        rows, retrieved_on = outcome
        by_domain: dict[str, list[dict[str, Any]]] = {d: [] for d in chunk}
        for row in rows:
            page = str(row.get("page_name") or row.get("pageName") or "")
            snapshot = row.get("snapshot") or {}
            # The display caption is the second chance when the click link is
            # a wrapper or short host that hides the destination.
            link_domain = (usable_destination(snapshot.get("link_url")) or usable_destination(snapshot.get("caption"))) if isinstance(snapshot, dict) else ""
            # Destination first: a foreign destination excludes the ad even
            # when the page name resembles the brand (namesake policy of the
            # Competitor Ads runner); without a usable destination the name
            # decides.
            if link_domain:
                target = next((d for d in chunk if link_domain == d), None)
            else:
                target = next((d for d in chunk if _name_matches(page, brands[d])), None)
            if target is None:
                continue
            first = _iso_from_epoch(row.get("start_date") or row.get("startDate"))
            last = _iso_from_epoch(row.get("end_date") or row.get("endDate"))
            is_active = row.get("is_active")
            by_domain[target].append({"first_seen": first, "last_seen": last, "is_active": bool(is_active) if is_active is not None else None, "format": None, "raw": row})
        for domain in chunk:
            results.append(_presence(domain, "meta_ads", "meta_library_actor", by_domain[domain], market_scope="target", verified_by="destination_or_page_name", today=today, note=f"page search country {country}; provider delivery dates are global unless native scope is explicit", country=country, request_limit=per_domain, raw_count=len(rows), native_activity_scope="global", retrieved_on=retrieved_on))
    if not eu_country:
        return results
    for domain in domains:
        brand = brand_token(domain)
        outcome = _cumulative_answer(coverage, "meta", [domain], eu_country, lambda: _call_with_context(client, domain, "Meta Ads Library (official EU API)", lambda: client.meta_library_search(
            {"query": brand, "countries": [eu_country], "activeStatus": "ALL", "limit": per_domain},
        )))
        if outcome is None:
            continue
        rows, retrieved_on = outcome
        ads: list[dict[str, Any]] = []
        for row in rows:
            page = str(row.get("page_name") or "")
            links = row.get("ad_creative_link_captions") or []
            if isinstance(links, str):
                links = [links]
            # Captions are display text ('Learn more', 'MURAL.CO | ...') as
            # often as addresses: only address-shaped captions count as a
            # destination. Destination first: a known foreign destination
            # excludes the ad whatever the page is called; the name decides
            # only when the row carries no usable destination.
            link_domains = {usable_destination(x) for x in links if x} - {""} if isinstance(links, list) else set()
            if link_domains:
                if domain not in link_domains:
                    continue
            elif not _name_matches(page, brand):
                continue
            first = str(row.get("ad_delivery_start_time") or "")[:10] or None
            last = str(row.get("ad_delivery_stop_time") or "")[:10] or None
            # No stop time = delivering now; a stop time only dates the ad,
            # the recency window decides whether it still counts as recent.
            ads.append({"first_seen": first, "last_seen": last, "is_active": True if (first and last is None) else (False if last else None), "format": None, "raw": row})
        results.append(_presence(domain, "meta_ads", "meta_library_official_eu", ads, market_scope="target" if eu_country == country else "eu_proxy", verified_by="destination_or_page_name", today=today, note=f"EU delivery country {eu_country}; ad-level dates have global scope unless provider supplies country dates", country=eu_country, request_limit=per_domain, raw_count=len(rows), native_activity_scope="global", retrieved_on=retrieved_on))
    return results


def collect_linkedin(client: OsClient, spec: dict[str, Any], domains: list[str], today: date, company_slugs: dict[str, str] | None, coverage: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Advertiser search by LinkedIn company page URL. A keyword query
    returns ads whose copy mentions the word (observed live: 'coddy' matched
    'Caddi'), so the query is the company page, resolved from the
    competitor's own site when the tag scan saw it and guessed from the
    brand token otherwise. Rows are attributed by the query they came from
    and checked against the paying advertiser's name."""
    per_domain = int(spec.get("ads_per_domain") or 30)
    slugs = company_slugs or {}
    results: list[dict[str, Any]] = []
    for chunk in _chunks(domains, int(spec.get("batch_domains") or 5)):
        brands = {d: brand_token(d) for d in chunk}
        queries = {d: f"https://www.linkedin.com/company/{slugs.get(d) or brands[d]}" for d in chunk}
        outcome = _attempt(client, coverage, "linkedin", chunk, lambda: _call_with_context(client, ", ".join(chunk), "LinkedIn Ad Library", lambda: client.run_actor(
            spec["actor"], {"queries": [queries[d] for d in chunk], "maxResults": per_domain * len(chunk), "enrich": True}, limit=per_domain * len(chunk),
        )))
        if outcome is None:
            continue
        rows, retrieved_on = outcome
        by_domain: dict[str, list[dict[str, Any]]] = {d: [] for d in chunk}
        for row in rows:
            advertiser = row.get("advertiser_name") or row.get("advertiserName") or ""
            query = str(row.get("query") or "").strip().lower()
            target = next((d for d in chunk if query and query == queries[d].lower()), None)
            if target is None:
                target = next((d for d in chunk if _name_matches(advertiser, brands[d])), None)
                if target is None:
                    continue
            else:
                # Query attribution still needs the paying advertiser to BE
                # the brand (or the company page read from its own site):
                # a guessed slug can land on a namesake company page.
                slug_brand = re.sub(r"[^a-z0-9]", "", slugs.get(target, "").lower())
                if not (_name_matches(advertiser, brands[target]) or (slug_brand and _name_matches(advertiser, slug_brand))):
                    continue
            first = str(row.get("_first_seen") or row.get("first_seen") or "")[:10] or None
            last = str(row.get("_last_seen") or row.get("last_seen") or "")[:10] or None
            by_domain[target].append({"first_seen": first, "last_seen": last, "is_active": None, "format": row.get("creative_format"), "raw": row})
        for domain in chunk:
            source_note = f"company page {queries[domain]}" + ("" if slugs.get(domain) else " (slug guessed from the brand token)")
            results.append(_presence(domain, "linkedin_ads", "linkedin_library_actor", by_domain[domain], market_scope="global", verified_by="company_page_query", today=today, note=f"{source_note}; LinkedIn publishes no delivery dates; sightings are listing history", request_limit=per_domain, raw_count=len(rows), native_date_scope="unknown", retrieved_on=retrieved_on))
    return results


def collect_tiktok(client: OsClient, spec: dict[str, Any], domains: list[str], today: date, eu_country: str, coverage: list[dict[str, Any]]) -> list[dict[str, Any]]:
    per_domain = int(spec.get("ads_per_domain") or 30)
    results: list[dict[str, Any]] = []
    for domain in domains:
        brand = brand_token(domain)
        outcome = _attempt(client, coverage, "tiktok", [domain], lambda: _call_with_context(client, domain, "TikTok Ad Library", lambda: client.run_actor(
            spec["actor"], {"scrapeMode": "ad_library", "searchQuery": brand, "country": eu_country, "quickSearch": True, "maxResults": per_domain}, limit=per_domain,
        )))
        if outcome is None:
            continue
        rows, retrieved_on = outcome
        ads = []
        for row in rows:
            if not _name_matches(row.get("advertiserName"), brand):
                continue
            first = str(row.get("firstShownDate") or "")[:10] or None
            last = str(row.get("lastShownDate") or "")[:10] or None
            status = str(row.get("status") or "").lower()
            ads.append({"first_seen": first, "last_seen": last, "is_active": True if status == "active" else (False if status == "inactive" else None), "format": row.get("adFormat"), "raw": row})
        results.append(_presence(domain, "tiktok_ads", "tiktok_library_actor", ads, market_scope="target", verified_by="advertiser_name", today=today, note=f"EU library country {eu_country}; native date scope remains global unless explicitly returned", country=eu_country, request_limit=per_domain, raw_count=len(rows), native_activity_scope="global", retrieved_on=retrieved_on))
    return results


def collect_reddit(client: OsClient, spec: dict[str, Any], domains: list[str], today: date, coverage: list[dict[str, Any]]) -> list[dict[str, Any]]:
    per_domain = int(spec.get("ads_per_domain") or 30)
    results: list[dict[str, Any]] = []
    for domain in domains:
        brand = brand_token(domain)
        outcome = _attempt(client, coverage, "reddit", [domain], lambda: _call_with_context(client, domain, "Reddit ads library", lambda: client.run_actor(
            spec["actor"], {"query": brand, "maxItems": per_domain}, limit=per_domain,
        )))
        if outcome is None:
            continue
        rows, retrieved_on = outcome
        ads = []
        for row in rows:
            advertiser = row.get("advertiserName") or row.get("profile_name") or ""
            # Destination first, name only when the row has no usable
            # destination (a promoted post links to reddit.com itself).
            destination = usable_destination(row.get("destinationUrl") or row.get("destination_url") or "")
            if destination:
                if destination != domain:
                    continue
            elif not _name_matches(advertiser, brand):
                continue
            created = _iso_from_epoch(row.get("createdAt") or row.get("created_at"))
            ads.append({"first_seen": created, "last_seen": created, "is_active": None, "format": str(row.get("creativeType") or row.get("type") or "unknown").lower(), "budget": row.get("budgetCategory") or row.get("budget_category"), "placements": row.get("placements"), "raw": row})
        presence = _presence(domain, "reddit_ads", "reddit_inspiration_actor", ads, market_scope="global", verified_by="destination_or_advertiser_name", today=today, note="inspiration examples; current campaigns are not verifiable; dates are creation dates, not run spans", request_limit=per_domain, raw_count=len(rows), native_date_scope="unknown", retrieved_on=retrieved_on)
        budgets = sorted({str(a.get("budget")) for a in ads if a.get("budget")})
        if budgets:
            presence["note"] += f"; budget tiers {', '.join(budgets)}"
        results.append(presence)
    return results


# ── partner signals ─────────────────────────────────────────────────────────

def _paid_search_row(domain: str, country: str, data: dict[str, Any], retrieved_on: str) -> dict[str, Any]:
    """Per competitor: SpyFu's modeled Google Ads spend over the complete
    months checked. `found: false` means SpyFu has no data for the domain,
    which is not the same as zero spend."""
    months = [m for m in (data.get("rows") or []) if isinstance(m, dict)]
    complete = [m for m in months if not m.get("partial_month")]
    spending = [m for m in complete if float(m.get("monthly_budget_usd") or 0) > 0]
    latest = complete[0] if complete else None  # the gateway returns the newest month first
    budgets = [float(m["monthly_budget_usd"]) for m in spending]

    def latest_value(key: str) -> Any:
        # SpyFu models clicks as floats (64759.99999999999); evidence keeps whole numbers.
        value = latest.get(key) if latest else None
        return int(round(float(value))) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    return {
        "type": "paid_search_stats",
        "domain": domain,
        "platform": "google_ads",
        "source": "spyfu",
        "country": country,
        "found": bool(data.get("found")),
        "months_checked": len(complete),
        "months_with_spend": len(spending),
        "spending_now": bool(latest and float(latest.get("monthly_budget_usd") or 0) > 0),
        "latest_month": f"{int(latest['year']):04d}-{int(latest['month']):02d}" if latest and latest.get("year") and latest.get("month") else None,
        "latest_monthly_budget_usd": latest_value("monthly_budget_usd"),
        "latest_monthly_paid_clicks": latest_value("monthly_paid_clicks"),
        "latest_paid_keywords": latest_value("paid_keywords"),
        "avg_monthly_budget_usd": round(sum(budgets) / len(budgets)) if budgets else None,
        "max_monthly_budget_usd": round(max(budgets)) if budgets else None,
        "retrieved_on": retrieved_on,
        "market_scope": "target",
        "tier": "B",
    }


def collect_spyfu(client: OsClient, domains: list[str], country: str, coverage: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for domain in domains:
        answer = _attempt(client, coverage, "spyfu", [domain], lambda d=domain: client.spyfu_domain_stats(d, country, SPYFU_MONTHS))
        if answer is None:
            continue
        data, retrieved_on = answer
        row = _paid_search_row(domain, country, data, retrieved_on)
        rows.append(row)
        coverage.append({"type": "coverage", "domain": domain, "source": "spyfu", "status": "ok" if row["found"] else "no_data",
                         "detail": "" if row["found"] else "SpyFu has no Google search data for this domain", "tier": "C"})
    return rows


def _partner_hit(kind: str, domain: str, brand: str, url: str, title: str) -> bool:
    """Precision over recall: a hit must be the competitor's own program
    page, a known affiliate network or coupon site, or a page whose own
    address names the brand together with the signal word. Generic
    listicles that merely mention the brand do not count."""
    host = registrable_domain(url)
    path = urllib.parse.urlparse(url).path.lower()
    own = host == domain
    if kind == "affiliate_program":
        if own:
            return bool(re.search(r"affiliate|partner|referral|ambassador", path))
        return host in AFFILIATE_NETWORK_DOMAINS and _mentions(f"{url} {title}", brand)
    if kind == "coupon_listing":
        if own:
            return False
        return (host in COUPON_DOMAINS and _mentions(f"{url} {title}", brand)) or (
            bool(re.search(r"coupon|promo|discount", path)) and _mentions(path, brand)
        )
    if kind == "sponsorship":
        if own:
            return False
        return bool(re.search(r"sponsor", f"{url} {title}", re.IGNORECASE)) and _mentions(f"{url} {title}", brand)
    return False


def collect_partners(client: OsClient, domain: str, country: str, coverage: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    brand = brand_token(domain)
    rows: list[dict[str, Any]] = []
    for kind, template in PARTNER_KINDS:
        query = template.format(brand=brand)
        try:
            response, _ = client.brave(query, BRAVE_COUNT, country.lower())
        except BudgetExhausted as exc:
            if "cumulative" not in str(exc):
                raise
            if coverage is not None:
                coverage.append({"type": "coverage", "domain": domain, "source": "partners", "country": country, "status": "budget_deferred", "detail": f"{kind}: {exc}", "tier": "C"})
            rows.append({"type": "partner_signal", "domain": domain, "country": country, "kind": kind, "query": query, "hits": None, "urls": [], "source": "brave", "status": "budget_deferred", "tier": "C"})
            continue
        except OsUnreachable:
            raise
        except ChannelFootprintError as exc:
            rows.append({"type": "partner_signal", "domain": domain, "kind": kind, "query": query, "hits": None, "urls": [], "unavailable": _provider_detail(exc)[:200], "source": "brave", "tier": "C"})
            continue
        hits = 0
        urls: list[str] = []
        for item in response.get("results") or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            title = str(item.get("title") or "")
            if _partner_hit(kind, domain, brand, url, title):
                hits += 1
                if len(urls) < PARTNER_URLS_PER_KIND:
                    urls.append(url)
        rows.append({"type": "partner_signal", "domain": domain, "kind": kind, "query": query, "hits": hits, "urls": urls, "source": "brave", "tier": "B" if hits else "C"})
    return rows


# ── aggregation ─────────────────────────────────────────────────────────────

def observed_channels(presences=(), scans=(), traffic=(), paid_search=()) -> tuple[str, ...]:
    names = set(CHANNELS)
    names.update(p.get("platform") for p in presences if p.get("platform"))
    names.update(channel for scan in scans for channel in scan.get("channels_detected", []))
    names.update(row.get("paid_channel") for row in traffic if row.get("paid_channel"))
    names.update(row.get("platform") for row in paid_search if row.get("platform"))
    return tuple(sorted(name for name in names if isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9_]+", name)))


def channel_label(channel: str) -> str:
    return CHANNEL_LABELS.get(channel, channel)


def rank_channels(domains: list[str], presences: list[dict[str, Any]], scans: list[dict[str, Any]], traffic: list[dict[str, Any]], partners: list[dict[str, Any]], paid_search: list[dict[str, Any]] = (), competitor_context: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Describe direct-competitor observations; do not rank channel merit.

    Evidence kinds are preserved because tags, listings and modeled spend are
    different observations. Counts never imply acquisition success.
    """
    context = competitor_context or {}
    direct = {d for d in domains if context.get(d, {}).get("competitor_tier") == "direct"}
    rows = []
    for channel in observed_channels(presences, scans, traffic, paid_search):
        evidence: dict[str, set[str]] = {}
        active_ids, proven_domains, durations = set(), set(), []
        for p in presences:
            if p.get("domain") not in direct or p.get("platform") != channel:
                continue
            if p.get("present") and p.get("relevance") == "relevant":
                evidence.setdefault(p["domain"], set()).add("library" if p.get("active_ads") else "listing")
            active_ids.update(p.get("current_ad_ids") or [])
            if p.get("current_presence"):
                proven_domains.add(p["domain"])
            if p.get("oldest_days") is not None:
                durations.append(p["oldest_days"])
        for scan in scans:
            if scan["domain"] in direct and channel in scan.get("channels_detected", []):
                evidence.setdefault(scan["domain"], set()).add("pixel")
        samples = [t for t in traffic if t["domain"] in direct and t.get("paid_channel") == channel and t.get("share_pct") is not None]
        for row in samples:
            if float(row.get("share_pct_raw", row["share_pct"])) > PRESENT_SHARE_PCT:
                evidence.setdefault(row["domain"], set()).add("modeled_traffic")
        if channel == "affiliate":
            for row in partners:
                if row["domain"] in direct and row.get("kind") in {"affiliate_program", "coupon_listing"} and row.get("hits", 0):
                    evidence.setdefault(row["domain"], set()).add("partner_signal")
        budgets = [r for r in paid_search if r["domain"] in direct and r.get("platform") == channel and r.get("spending_now") and r.get("latest_monthly_budget_usd") is not None]
        for row in budgets:
            evidence.setdefault(row["domain"], set()).add("modeled_spend")
        count = len(evidence)
        rows.append({"type": "channel_observation", "channel": channel, "label": channel_label(channel),
                     "competitor_tier": "direct", "competitors_present": count, "competitors_total": len(direct), "present_domains": sorted(evidence),
                     "evidence_kinds": {d: sorted(kinds) for d, kinds in sorted(evidence.items())}, "active_ads_total": len(active_ids),
                     "active_competitors": len(proven_domains), "max_oldest_days": max(durations) if durations else None,
                     "avg_share_pct": round(sum(float(r.get("share_pct_raw", r["share_pct"])) for r in samples) / len(samples), 2) if samples else None,
                     "share_sample_n": len(samples), "share_sample_domains": sorted({r["domain"] for r in samples}), "share_scope": "modeled_domain_global",
                     "est_monthly_budget_usd": sum(float(r["latest_monthly_budget_usd"]) for r in budgets) if budgets else None,
                     "why": f"{count} of {len(direct)} direct competitor(s) with a positive observation; evidence kinds remain separate", "tier": "B" if count else "C",
                     "campaign_data_status": "activity_observed" if proven_domains else "activity_unknown"})
    rows.sort(key=lambda r: r["channel"])
    return rows


# ── rendering ───────────────────────────────────────────────────────────────

def _cell(value: Any, cap: int = 120) -> str:
    text = " ".join(str(value if value is not None else "—").split()).replace("|", "\\|")
    return text if len(text) <= cap else text[: cap - 1] + "…"


# ── orchestration ───────────────────────────────────────────────────────────

EU_COUNTRIES = frozenset("AT BE BG HR CY CZ DE DK EE ES FI FR GR HU IE IT LT LU LV MT NL PL PT RO SE SI SK".split())


def _effective_policy(config: dict[str, Any]) -> tuple[dict[str, Any], str]:
    module = _load_script("research-policy.py", "pmr_channel_policy")
    taxonomy_path = Path(__file__).resolve().parent.parent / "references/config/creative-taxonomy.v1.json"
    return module.policy_from_taxonomy(json.loads(taxonomy_path.read_text()))


def _coverage_grid(inputs: RunInputs, presences: list[dict[str, Any]], coverage: list[dict[str, Any]], raw: dict[str, Any] | None = None) -> None:
    for domain in inputs.domains:
        for source in inputs.sources:
            for country in inputs.target_countries:
                existing = [r for r in coverage if r.get("domain") == domain and r.get("source") == source and r.get("country") in {country, None}]
                if existing:
                    continue
                matching = [p for p in presences if p["domain"] == domain and p["source"].startswith({"google": "google_", "meta": "meta_", "linkedin": "linkedin_", "reddit": "reddit_", "tiktok": "tiktok_"}.get(source, source)) and p.get("country") in {country, None}]
                global_only = source in {"pixels", "history", "traffic", "linkedin", "reddit"}
                unsupported = source == "tiktok" and country not in EU_COUNTRIES
                measurements = [r for r in (raw or {}).get({"history": "history", "partners": "partners", "spyfu": "paid_search", "traffic": "traffic", "pixels": "scans"}.get(source, ""), []) if r.get("domain") == domain and r.get("country") in {country, None}]
                if unsupported:
                    status = "unsupported_market"
                elif source in {"linkedin", "reddit"} and matching:
                    status = "not_verifiable"
                elif matching:
                    status = "ok" if any(p.get("ads") for p in matching) else "no_matches_in_sample"
                elif measurements:
                    if source == "partners":
                        status = "ok" if any(r.get("hits", 0) for r in measurements) else "no_matches_in_sample"
                    else:
                        status = next((r.get("status") for r in measurements if r.get("status")), "ok")
                else:
                    status = "not_checked"
                coverage.append({"type": "coverage", "domain": domain, "source": source, "country": country,
                                 "market_scope": "global" if global_only else "target", "status": status,
                                 "detail": "source cannot verify current campaigns or native delivery duration" if source in {"linkedin", "reddit"} else ("source does not support this target country" if unsupported else ""), "tier": "C"})


def finalize_pipeline(raw: dict[str, Any], inputs: RunInputs, config: dict[str, Any], today: date, stale_decisions: str = "raise") -> dict[str, Any]:
    model = _model()
    policy, policy_hash = _effective_policy(config)
    raw_presences = raw["presences"]
    corpus = model.build_corpus(raw_presences, inputs.product_context_sha256, policy)
    for ad in corpus:
        ad["competitor_tier"] = inputs.competitor_context.get(ad["domain"], {}).get("competitor_tier", "unknown")
        ad["activity_status"] = "unknown"  # use native observation status for decisions
        ad["countries"] = sorted({o["country"] for o in ad["observations"] if o.get("country")})
    try:
        pending = model.apply_decisions(corpus, inputs.relevance_decisions, inputs.product_context_sha256, stale=stale_decisions)
    except ValueError as exc:
        raise ChannelFootprintError(str(exc)) from exc
    presences = model.summarize_presences(raw_presences, corpus, inputs.competitor_context, policy, inputs.product_context_sha256)
    # A native placement creates a separately scoped observation. A video
    # format alone stays Google and never asserts YouTube delivery.
    for placement, channel in (("youtube", "youtube_ads"), ("display", "display_native")):
        sub_raw = []
        for presence in raw_presences:
            if presence["platform"] != "google_ads":
                continue
            ids = {a["ad_id"] for a in corpus if any(o.get("placement") == placement and o.get("country") == presence.get("country") for o in a["observations"])}
            selected_ids = [x for x in presence.get("ad_ids", []) if x in ids]
            if selected_ids:
                sub_raw.append({**presence, "platform": channel, "ad_ids": selected_ids})
        if sub_raw:
            presences.extend(model.summarize_presences(sub_raw, corpus, inputs.competitor_context, policy, inputs.product_context_sha256, placement_filter=placement))
    for row in raw["scans"] + raw["traffic"] + raw["paid_search"] + raw["partners"] + raw["history"]:
        row["competitor_tier"] = inputs.competitor_context.get(row["domain"], {}).get("competitor_tier", "unknown")
        row.setdefault("market_scope", "global")
    country_rows = model.country_rows(presences, raw["scans"], inputs.target_countries, inputs.competitor_context, policy, observed_channels(presences, raw["scans"], raw["traffic"], raw["paid_search"]))
    ranks = rank_channels(inputs.domains, presences, raw["scans"], raw["traffic"], raw["partners"], raw["paid_search"], inputs.competitor_context)
    coverage = [dict(row) for row in raw["coverage"]]
    _coverage_grid(inputs, raw_presences, coverage, raw)
    totals = raw["totals"]
    retrieved_on = totals["first_retrieved_on"] if totals["first_retrieved_on"] == totals["last_retrieved_on"] else f"{totals['first_retrieved_on']}..{totals['last_retrieved_on']}"
    evidence = {"schema_version": SCHEMA_VERSION, "section_id": SECTION_ID, "generated_by": Path(__file__).name, "retrieved_on": retrieved_on,
                "inputs": {"domains": inputs.domains, "domain_sources": inputs.domain_sources, "competitor_context": inputs.competitor_context,
                           "product_domain": inputs.product_domain, "product_context_sha256": inputs.product_context_sha256,
                           "sources": inputs.sources, "country": inputs.country, "eu_country": inputs.eu_country, "target_countries": inputs.target_countries,
                           "present_share_pct": PRESENT_SHARE_PCT, "effective_policy": policy, "policy_sha256": policy_hash},
                "rows": ranks + country_rows + presences + corpus + raw["paid_search"] + raw["scans"] + raw["traffic"] + raw["partners"] + raw["history"] + coverage,
                "totals": {k: totals[k] for k in ("actor_runs", "meta_searches", "search_calls", "spyfu_calls", "fetches", "cdx_calls", "provider_calls", "rejected_actor_runs", "rejected_spyfu_calls", "observations")}}
    section = render_section_v2(inputs, presences, corpus, ranks, country_rows, {**raw, "coverage": coverage}, retrieved_on)
    return {"evidence": evidence, "section_markdown": section, "totals": totals, "attempt": raw["attempt"], "raw": raw,
            "pending_relevance": pending, "corpus": corpus, "collection_complete": raw.get("collection_complete", True)}


def run_pipeline(client: OsClient, inputs: RunInputs, config: dict[str, Any], today: date) -> dict[str, Any]:
    actors = config["actors"]
    policy, _ = _effective_policy(config)
    inputs.effective_policy = policy
    inputs.target_countries = _model().countries(inputs.target_countries or [inputs.country])
    inputs.country = inputs.target_countries[0]
    raw = {"scans": [], "history": [], "traffic": [], "presences": [], "partners": [], "coverage": [], "paid_search": []}
    primary = list(inputs.domains)  # All explicitly scoped competitors; roles describe comparability, not eligibility.

    def collect(domains: list[str], deficits: set[tuple[str, str]] | None = None) -> None:
        if not domains:
            return
        def call(source: str, country: str | None, fn: Callable[[], Any], target: str):
            coverage_before = len(raw["coverage"])
            try:
                value = fn()
            except BudgetExhausted as exc:
                if "cumulative" not in str(exc):
                    raise
                raw["coverage"].extend({"type": "coverage", "domain": d, "source": source, "country": country, "status": "budget_deferred", "detail": str(exc), "tier": "C"} for d in domains)
                return
            for row in raw["coverage"][coverage_before:]:
                row.setdefault("country", country)
            if value:
                if country and target in {"paid_search", "partners"}:
                    for row in value:
                        row.setdefault("country", country)
                raw[target].extend(value)
        if "pixels" in inputs.sources:
            call("pixels", None, lambda: [scan_site(client, d) for d in domains], "scans")
            opaque = [s["domain"] for s in raw["scans"] if s["domain"] in domains and (s["fetch_status"] != "ok" or not s.get("tags_detected"))]
            if opaque and inputs.pixel_actor_fallback:
                for chunk in _chunks(opaque, int(actors["pixel_detector"].get("batch_domains") or 5)):
                    try:
                        replacements = _attempt(client, raw["coverage"], "pixels_actor", chunk, lambda: scan_sites_with_actor(client, actors["pixel_detector"]["actor"], chunk))
                    except BudgetExhausted as exc:
                        if "cumulative" not in str(exc):
                            raise
                        replacements = None
                        raw["coverage"].extend({"type": "coverage", "domain": d, "source": "pixels_actor", "status": "budget_deferred", "detail": str(exc), "tier": "C"} for d in chunk)
                    if replacements:
                        for scan in raw["scans"]:
                            replacement = replacements.get(scan["domain"])
                            if replacement is not None:
                                replacement["linkedin_company"] = scan.get("linkedin_company")
                                replacement["gtm_containers"] = scan.get("gtm_containers") or []
                        raw["scans"] = [replacements.get(s["domain"], s) for s in raw["scans"]]
            for scan in raw["scans"]:
                if scan["domain"] in domains:
                    raw["coverage"].append({"type": "coverage", "domain": scan["domain"], "source": "pixels", "market_scope": "global", "status": "ok" if scan["fetch_status"] == "ok" else scan["fetch_status"], "detail": "domain tracking signal; campaign details unavailable" if scan.get("channels_detected") else "", "tier": "C"})
        if "history" in inputs.sources:
            call("history", None, lambda: [collect_history(client, d, today) for d in domains], "history")
        if "traffic" in inputs.sources:
            call("traffic", None, lambda: collect_traffic(client, actors["traffic_mix"], domains, raw["coverage"]), "traffic")
        for country in inputs.target_countries:
            if "google" in inputs.sources and (deficits is None or ("google_ads", country) in deficits):
                call("google", country, lambda: collect_google(client, actors["google_ads"], domains, today, country, raw["coverage"]), "presences")
            if "spyfu" in inputs.sources and (deficits is None or ("google_ads", country) in deficits):
                call("spyfu", country, lambda: collect_spyfu(client, domains, country, raw["coverage"]), "paid_search")
            if "meta" in inputs.sources and (deficits is None or ("meta_ads", country) in deficits):
                call("meta", country, lambda: collect_meta(client, actors["meta_ads"], domains, today, country, country if country in EU_COUNTRIES else "", raw["coverage"]), "presences")
            if "partners" in inputs.sources and (deficits is None or ("affiliate", country) in deficits):
                call("partners", country, lambda: [r for d in domains for r in collect_partners(client, d, country, raw["coverage"])], "partners")
            if "tiktok" in inputs.sources and country in EU_COUNTRIES and (deficits is None or ("tiktok_ads", country) in deficits):
                call("tiktok", country, lambda: collect_tiktok(client, actors["tiktok_ads"], domains, today, country, raw["coverage"]), "presences")
        if "linkedin" in inputs.sources and (deficits is None or any(ch == "linkedin_ads" for ch, _ in deficits)):
            slugs = {s["domain"]: s["linkedin_company"] for s in raw["scans"] if s.get("linkedin_company")}
            call("linkedin", None, lambda: collect_linkedin(client, actors["linkedin_ads"], domains, today, slugs, raw["coverage"]), "presences")
        if "reddit" in inputs.sources and (deficits is None or any(ch == "reddit_ads" for ch, _ in deficits)):
            call("reddit", None, lambda: collect_reddit(client, actors["reddit_ads"], domains, today, raw["coverage"]), "presences")
    collect(primary)
    raw["totals"] = client.ledger_totals()
    raw["attempt"] = {"actor_runs": client.actor_runs, "meta_searches": client.meta_searches, "search_calls": client.search_calls, "spyfu_calls": client.spyfu_calls, "fetches": client.fetches, "cdx_calls": client.cdx_calls, "relevance_calls": client.relevance_calls, "cache_hits": client.cache_hits}
    # The base sample lacks fields that the expansion may fill in an ad
    # decided after it, so this gate takes decisions by ad_id; the passes on
    # the expanded corpus send such a changed ad back to review instead.
    preliminary = finalize_pipeline(raw, inputs, config, today, stale_decisions="accept")
    # A reviewed direct sample without comparable ads may be expanded once.
    # The enlarged payload is cached; repeated collect never adds another step.
    # A collected expansion is replayed whatever a later review says: an ad it
    # enriched and the founder then found relevant keeps its expanded sample.
    reviewed = not preliminary["pending_relevance"]
    expanded_before = {(e.get("domain"), e.get("source"), e.get("country")) for e in inputs.prior_expansions}
    raw["expansions"] = []
    for presence in list(raw["presences"]):
        if not presence.get("sampling", {}).get("limit_reached"):
            continue
        if (presence["domain"], presence["source"], presence.get("country")) not in expanded_before:
            if not reviewed:
                continue
            comparable = next((r for r in preliminary["evidence"]["rows"] if r["type"] == "library_presence" and r["domain"] == presence["domain"] and r["platform"] == presence["platform"] and r.get("country") == presence.get("country")), {})
            if comparable.get("relevant_ads"):
                continue
        source_key = {"google_transparency_actor": "google_ads", "meta_library_actor": "meta_ads", "linkedin_library_actor": "linkedin_ads", "tiktok_library_actor": "tiktok_ads"}.get(presence["source"])
        if not source_key:
            continue
        expanded_spec = dict(actors[source_key])
        base = int(expanded_spec.get("ads_per_domain") or 30)
        maximum = int(expanded_spec.get("max_ads_per_domain") or base * 2)
        if maximum <= base:
            continue
        expanded_spec["ads_per_domain"] = maximum
        domain, country = presence["domain"], presence.get("country")
        try:
            if source_key == "google_ads":
                added = collect_google(client, expanded_spec, [domain], today, country, raw["coverage"])
            elif source_key == "meta_ads":
                added = collect_meta(client, expanded_spec, [domain], today, country, country if country in EU_COUNTRIES else "", raw["coverage"])
            elif source_key == "linkedin_ads":
                slugs = {s["domain"]: s["linkedin_company"] for s in raw["scans"] if s.get("linkedin_company")}
                added = collect_linkedin(client, expanded_spec, [domain], today, slugs, raw["coverage"])
            else:
                added = collect_tiktok(client, expanded_spec, [domain], today, country, raw["coverage"])
            raw["presences"].extend(added)
            if added:
                raw["expansions"].append({"domain": domain, "source": presence["source"], "country": country})
        except BudgetExhausted as exc:
            if "cumulative" not in str(exc):
                raise
            raw["coverage"].append({"type": "coverage", "domain": domain, "source": source_key, "country": country, "status": "budget_deferred", "detail": str(exc), "tier": "C"})
    if reviewed or raw["expansions"]:
        preliminary = finalize_pipeline(raw, inputs, config, today, stale_decisions="pending")
    raw["collection_complete"] = True
    raw["totals"] = client.ledger_totals()
    raw["attempt"] = {"actor_runs": client.actor_runs, "meta_searches": client.meta_searches, "search_calls": client.search_calls, "spyfu_calls": client.spyfu_calls, "fetches": client.fetches, "cdx_calls": client.cdx_calls, "relevance_calls": client.relevance_calls, "cache_hits": client.cache_hits}
    return finalize_pipeline(raw, inputs, config, today, stale_decisions="pending")


def render_section_v2(inputs, presences, corpus, ranks, country_rows, raw, retrieved_on):
    lines = [f"Observed: {retrieved_on}. Target countries: {', '.join(inputs.target_countries)}.", "",
             "Counts describe the bounded source sample, not channel priority or success. Tracking tags, modeled traffic and ad-library observations remain distinct; a tag does not describe campaigns or country delivery.", ""]
    for role, label in (("direct", "Direct competitors"), ("indirect", "Indirect competitors"), ("unknown", "Unclassified domains")):
        domains = [d for d in inputs.domains if inputs.competitor_context.get(d, {}).get("competitor_tier", "unknown") == role]
        if not domains:
            continue
        lines += [f"### {label}: channel footprint matrix", "", "| Competitor | Channel | Country / scope | Observations | Campaign data |", "| --- | --- | --- | --- | --- |"]
        for domain in domains:
            for channel in (r["channel"] for r in ranks):
                pixels = any(s["domain"] == domain and channel in s.get("channels_detected", []) for s in raw["scans"])
                rows = [r for r in presences if r["domain"] == domain and r["platform"] == channel]
                if not rows and not pixels:
                    continue
                if not rows:
                    lines.append(f"| {domain} | {channel_label(channel)} | global / unknown | pixel found; campaign data unavailable | needs_campaign_data |")
                for row in rows:
                    parts = ["pixel found (global / unknown)"] if pixels else []
                    parts += [f"comparable ads {row['relevant_ads']}; active {row['active_ads']} ({', '.join(row['activity_scopes']) or 'unknown'} scope); country current {len(row['current_ad_ids'])}; stopped {row['stopped_ads']}; undated {row['unknown_activity_ads']}"]
                    if row["unknown_relevance_ads"]:
                        parts.append(f"relevance unknown {row['unknown_relevance_ads']}")
                    parts.append(row["status"])
                    lines.append(f"| {domain} | {channel_label(channel)} | {_cell(row.get('country') or row['market_scope'])} | {_cell('; '.join(parts), 300)} | {'activity_observed' if row['current_presence'] else 'activity_unknown'} |")
    lines += ["", "### Channel observations (direct competitors)", "", "| Channel | Direct positive observations | Active competitors | Activity coverage |", "| --- | --- | --- | --- |"]
    for row in ranks:
        lines.append(f"| {row['label']} | {row['competitors_present']}/{row['competitors_total']} | {row['active_competitors']} | {row['campaign_data_status']} |")
    lines += ["", "### Country observations", "", "| Channel | Country | Direct observed | Indirect observed | Active domains | Coverage |", "| --- | --- | --- | --- | --- | --- |"]
    for row in country_rows:
        lines.append(f"| {channel_label(row['channel'])} | {row['country']} | {len(row['observed_domains_by_role']['direct'])} | {len(row['observed_domains_by_role']['indirect'])} | {len(row['active_domains'])} | {row['status']} |")
    lines += ["", "### Source samples", "", "| Competitor | Source | Country / scope | Received before relevance | Comparable | Limit / completeness | Max observed delivery duration |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in presences:
        samples = row.get("sampling", [])
        cap = any(x.get("limit_reached") for x in samples)
        received = max((x.get("raw_received", 0) for x in samples), default=0)
        lines.append(f"| {row['domain']} | {_cell(', '.join(row['sources']))} | {_cell(row.get('country') or row['market_scope'])} | {'≥' if cap else ''}{received} | {row['relevant_ads']} found | {'limit reached; total unknown' if cap else 'completeness unknown'} | {_cell(row['oldest_days'])} days ({row['duration_scope']}) |")
    lines += ["", "### Coverage", "", "| Competitor | Source | Country / scope | Status | Detail |", "| --- | --- | --- | --- | --- |"]
    for row in raw["coverage"]:
        lines.append(f"| {row['domain']} | {row['source']} | {_cell(row.get('country') or row.get('market_scope') or 'global / unknown')} | {row['status']} | {_cell(row.get('detail', ''), 300)} |")
    lines += ["", "### Source measurements", "", "| Competitor | Source / type | Market | Measurement |", "| --- | --- | --- | --- |"]
    for row in raw["traffic"] + raw["paid_search"] + raw["partners"] + raw["history"]:
        measurement = {k: v for k, v in row.items() if k not in {"type", "domain", "competitor_tier", "tier", "market_scope"}}
        lines.append(f"| {row['domain']} | {_cell(row.get('source') or row['type'])} | {_cell(row.get('country') or row.get('market_scope') or 'unknown')} | {_cell(json.dumps(measurement, ensure_ascii=False), 500)} |")
    lines += ["", "Legend: pixel found; active native status; stopped; undated listing; no matches in sample; not_checked; not_verifiable; unsupported_market; budget_deferred. Repeated listing observations are presence only. Empty samples never assert channel absence.", ""]
    return "\n".join(lines)


def _collection_matches(stored: dict[str, Any], context_hash: str, policy_hash: str, sources: list[str], config: dict[str, Any]) -> bool:
    model = _model()
    return (stored.get("input_context_sha256") == context_hash and stored.get("policy_sha256") == policy_hash and stored.get("sources") == sources
            and stored.get("sources_config_sha256") == model.digest(config) and stored.get("raw_sha256") == model.digest(stored.get("raw")))


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _arg(args: argparse.Namespace, name: str, default: Any) -> Any:
    value = getattr(args, name, None)
    return default if value is None else value


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

    config = load_sources_config(Path(_arg(args, "sources_config", "")) if _arg(args, "sources_config", "") else None)
    sources = parse_sources(str(_arg(args, "sources", "") or ""))
    stage = str(_arg(args, "stage", "all"))
    if stage not in {"all", "collect", "finalize"}:
        raise ChannelFootprintError("stage must be collect, finalize or all")
    policy, policy_hash = _effective_policy(config)
    max_competitors = max(1, int(_arg(args, "max_competitors", MAX_COMPETITORS)))
    product_domain = registrable_domain(str(_arg(args, "product_domain", "") or ""))
    explicit = [d for d in parse_domains(_arg(args, "domains", ""), MAX_EXPLICIT_DOMAINS) if d != product_domain]
    tiered = domains_from_competitor_set(workspace, MAX_COMPETITORS)
    rejected = domains_excluded_by_competitor_set(workspace) - set(explicit)
    discovered = domains_from_keyword_evidence(workspace, MAX_COMPETITORS, exclude=rejected)
    domains, domain_sources = [], {}
    for source, candidates in (("explicit", explicit), ("competitor_set", tiered), ("keyword_economics", discovered)):
        for domain in candidates:
            if len(domains) >= max_competitors:
                break
            if domain and domain != product_domain and domain not in domains:
                domains.append(domain)
                domain_sources[domain] = source
    if not domains:
        raise ChannelFootprintError("no competitor domains available: pass --domains, or complete the Competitor Set (or Keyword Economics) section first")
    try:
        provenance = json.loads((runtime / "competitor-set-inputs.json").read_text())
    except (OSError, json.JSONDecodeError):
        provenance = {}
    competitor_context = {r["domain"]: {**r, "source_sha256": provenance.get("source_sha256"), "source_path": _artifact_path("egbe-docs/research/market/evidence/competitors.json")} for r in provenance.get("inputs", []) if r.get("domain") in domains}
    for domain in domains:
        competitor_context.setdefault(domain, {"domain": domain, "competitor_tier": "unknown", "reason": "no approved Competitor Set role", "source_path": None, "source_sha256": None})
    intake_path = workspace / _artifact_path("egbe-docs/research/market/intake.json")
    intake = typed_intake(workspace)
    intake_hash = IO.sha256(intake_path) if intake_path.is_file() else None
    research_context = IO.context_binding(workspace, SECTION_ID)
    context = IO.context_text(workspace, SECTION_ID)
    geography = (_arg(args, "countries", "") or _arg(args, "country", "")
                 or intake.get("markets") or [DEFAULT_COUNTRY])
    target_countries = _model().countries(geography)
    context_hash = _model().digest({"context_sha256": research_context["sha256"], "intake_sha256": intake_hash, "competitor_context": competitor_context, "product_domain": product_domain, "target_countries": target_countries})
    relevance_inputs = relevance_context(workspace, args) if _arg(args, "relevance_by_model", False) else None
    decision_path = Path(_arg(args, "relevance_decisions", "") or runtime / "relevance-decisions.json")
    try:
        decisions = json.loads(decision_path.read_text()) if decision_path.is_file() else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ChannelFootprintError(f"invalid relevance decisions: {exc}") from exc
    if decisions and decisions.get("product_context_sha256") != context_hash:
        if stage == "finalize":
            raise ChannelFootprintError("relevance decisions belong to a different product/intake context; collect the new candidates")
        decisions = {}  # retain the old input on disk; expose new context-bound candidates
    inputs = RunInputs(domains=domains, domain_sources=domain_sources, product_domain=product_domain, sources=sources,
                       country=target_countries[0], eu_country=str(_arg(args, "eu_country", "") or ""), pixel_actor_fallback=bool(_arg(args, "pixel_actor_fallback", False)),
                       target_countries=target_countries, competitor_context=competitor_context, product_context_sha256=context_hash,
                       relevance_decisions=decisions, effective_policy=policy, stage=stage)
    plan = collection_plan([(domain, competitor_context[domain]["competitor_tier"]) for domain in domains], sources, target_countries,
                           pixel_actor_fallback=inputs.pixel_actor_fallback)
    budget = paid_start_budget(plan, config)
    max_total = int(_arg(args, "max_total_paid_starts", budget["cumulative_limit"]))
    if max_total < 0:
        raise ChannelFootprintError("total paid-start budget must be nonnegative")
    plan_doc = {"schema_version": 1, "input_context_sha256": context_hash, "policy_sha256": policy_hash,
                "base_paid_starts_upper_bound": budget["base"], "bounded_paid_starts_upper_bound": budget["bounded"], "retry_reserve_factor": budget["retry_reserve_factor"], "cumulative_limit": max_total, "money_estimate": None, "checks": plan}
    _write_atomic(runtime / "collection-plan.json", json.dumps(plan_doc, indent=1))
    collected_path = runtime / "collected.json"
    if stage == "finalize":
        try:
            stored = json.loads(collected_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ChannelFootprintError(f"collect the section before finalize: {exc}") from exc
        if not _collection_matches(stored, context_hash, policy_hash, sources, config):
            raise ChannelFootprintError("collected data context or policy changed; rerun collect using compatible provider cache")
        outcome = finalize_pipeline(stored["raw"], inputs, config, date.fromisoformat(stored["captured_on"]))
    else:
        api_key = (os.environ.get("OS_API_KEY") or "").strip()
        if not api_key:
            raise ChannelFootprintError("OS_API_KEY is required for collection")
        os_url = (os.environ.get("OS_URL") or DEFAULT_OS_URL).strip() or DEFAULT_OS_URL
        client = OsClient(
            os_url=os_url,
            api_key=api_key,
            cache_dir=cache_dir,
            max_actor_runs=int(_arg(args, "max_actor_runs", MAX_ACTOR_RUNS_PER_ATTEMPT)),
            max_meta_searches=int(_arg(args, "max_meta_searches", MAX_META_SEARCHES_PER_ATTEMPT)),
            max_search_calls=int(_arg(args, "max_search_calls", MAX_SEARCH_CALLS_PER_ATTEMPT)),
            max_fetches=int(_arg(args, "max_fetches", MAX_FETCHES_PER_ATTEMPT)),
            max_cdx_calls=int(_arg(args, "max_cdx_calls", MAX_CDX_CALLS_PER_ATTEMPT)),
            max_spyfu_calls=int(_arg(args, "max_spyfu_calls", MAX_SPYFU_CALLS_PER_ATTEMPT)),
            max_total_paid_starts=max_total, cumulative_budget_path=runtime / "budget.json",
        )

        try:
            previous = json.loads(collected_path.read_text())
        except (OSError, json.JSONDecodeError):
            previous = {}
        if _collection_matches(previous, context_hash, policy_hash, sources, config):
            inputs.prior_expansions = (previous.get("raw") or {}).get("expansions") or []
        outcome = run_pipeline(client, inputs, config, date.today())
        if _arg(args, "relevance_by_model", False):
            product_context, languages = relevance_inputs
            for _ in range(MODEL_RELEVANCE_ROUNDS):
                decided = model_relevance(client, outcome["corpus"], outcome["pending_relevance"], decisions, context_hash, product_context, languages)
                if decided is None:
                    break
                decisions = inputs.relevance_decisions = decided
                _write_atomic(decision_path, json.dumps(decided, indent=1, ensure_ascii=False))
                # A collected expansion is replayed in the next pass, as on a rerun.
                inputs.prior_expansions = outcome["raw"]["expansions"] + [e for e in inputs.prior_expansions if e not in outcome["raw"]["expansions"]]
                outcome = run_pipeline(client, inputs, config, date.today())
        _write_atomic(collected_path, json.dumps({"schema_version": 2, "input_context_sha256": context_hash, "policy_sha256": policy_hash, "sources": sources, "sources_config_sha256": _model().digest(config), "captured_on": date.today().isoformat(), "raw_sha256": _model().digest(outcome["raw"]), "raw": outcome["raw"]}, indent=1))
    no_observations_budget_deferred = outcome["totals"]["observations"] == 0 and any(r.get("status") == "budget_deferred" for r in outcome["raw"]["coverage"])
    if outcome["totals"]["observations"] == 0 and not no_observations_budget_deferred:
        raise ChannelFootprintError(
            "no source answered for any competitor (every provider call was rejected or failed); the section "
            "cannot complete without at least one successful observation. Rerun later or change --sources."
        )

    candidates = {"schema_version": 1, "product_context_sha256": context_hash, "policy_sha256": policy_hash,
                  "product_context": {"context": context, "intake": intake, "product_domain": product_domain, "competitor_context": competitor_context},
                  "candidates": outcome["corpus"], "pending_ad_ids": outcome["pending_relevance"]}
    _write_atomic(runtime / "relevance-candidates.json", json.dumps(candidates, indent=1, ensure_ascii=False))
    if outcome["pending_relevance"] or not outcome["collection_complete"] or stage == "collect" or no_observations_budget_deferred:
        status = "budget_deferred" if no_observations_budget_deferred else "awaiting_relevance" if outcome["pending_relevance"] else ("awaiting_collection" if not outcome["collection_complete"] else "awaiting_finalize")
        state = {"schema_version": 1, "section_id": SECTION_ID, "status": status, "domains": domains, "target_countries": target_countries,
                 "research_context": research_context,
                 "input_context_sha256": context_hash, "policy_sha256": policy_hash, "pending_ad_ids": outcome["pending_relevance"], "coverage": outcome["raw"]["coverage"],
                 "candidates_path": (RUNTIME_REL / "relevance-candidates.json").as_posix(), "collected_path": (RUNTIME_REL / "collected.json").as_posix(), "error": None}
        _write_atomic(runtime / "request.json", json.dumps(state, indent=1))
        return state

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
        extra_paths=(Path(_artifact_path("egbe-docs/research/market/evidence/channel-footprint.json")),),
    )

    state = {
        "schema_version": 1,
        "section_id": SECTION_ID,
        "status": "completed",
        "domains": inputs.domains,
        "domain_sources": inputs.domain_sources,
        "sources": inputs.sources,
        "country": inputs.country,
        "eu_country": inputs.eu_country,
        "target_countries": inputs.target_countries,
        "input_context_sha256": context_hash,
        "intake_sha256": intake_hash,
        "competitor_set_sha256": provenance.get("source_sha256"),
        "policy_sha256": policy_hash,
        "effective_policy": policy,
        "relevance_decisions_sha256": _model().digest(decisions),
        "sources_config_sha256": _model().digest(config),
        "evidence_path": EVIDENCE_REL.as_posix(),
        "evidence_sha256": hashlib.sha256(evidence_json.encode("utf-8")).hexdigest(),
        "result_path": (RUNTIME_REL / "result.md").as_posix(),
        "result_sha256": hashlib.sha256(outcome["section_markdown"].encode("utf-8")).hexdigest(),
        "provider_calls": outcome["totals"]["provider_calls"],
        "actor_runs": outcome["totals"]["actor_runs"],
        "meta_searches": outcome["totals"]["meta_searches"],
        "search_calls": outcome["totals"]["search_calls"],
        "fetches": outcome["totals"]["fetches"],
        "cdx_calls": outcome["totals"]["cdx_calls"],
        "spyfu_calls": outcome["totals"]["spyfu_calls"],
        "relevance_calls": outcome["totals"].get("relevance_calls", 0),
        "rejected_actor_runs": outcome["totals"]["rejected_actor_runs"],
        "rejected_spyfu_calls": outcome["totals"]["rejected_spyfu_calls"],
        "observations": outcome["totals"]["observations"],
        "actor_starts_recorded": outcome["totals"]["actor_starts_recorded"],
        "attempt_actor_runs": outcome["attempt"]["actor_runs"],
        "attempt_meta_searches": outcome["attempt"]["meta_searches"],
        "attempt_search_calls": outcome["attempt"]["search_calls"],
        "attempt_fetches": outcome["attempt"]["fetches"],
        "attempt_cdx_calls": outcome["attempt"]["cdx_calls"],
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
    parser.add_argument("--domains", default="", help="Comma-separated competitor domains; merged ahead of the Competitor Set and Keyword Economics domains.")
    parser.add_argument("--product-domain", default="", help="The product's own domain; never scanned as a competitor.")
    parser.add_argument("--sources", default="", help=f"Comma-separated subset of {', '.join(ALL_SOURCES)} (default: all).")
    parser.add_argument("--sources-config", default="", help="Path to an alternative sources config JSON (actor ids and batch sizes).")
    parser.add_argument("--max-competitors", type=int, default=MAX_COMPETITORS)
    parser.add_argument("--country", default="", help="Explicit single target country; otherwise typed intake markets, then US.")
    parser.add_argument("--eu-country", default="", help="Deprecated compatibility argument; target markets come from intake/--countries.")
    parser.add_argument("--countries", "--target-countries", default="", help="Explicit ISO target countries; otherwise --country or typed intake markets.")
    parser.add_argument("--languages", default="", help="Explicit accepted language codes for relevance classification; otherwise typed intake languages.")
    parser.add_argument("--stage", choices=("all", "collect", "finalize"), default="all")
    parser.add_argument("--relevance-decisions", default="", help="Context-bound decisions JSON (default runtime/relevance-decisions.json).")
    parser.add_argument("--relevance-by-model", action="store_true", help="Decide ads with text by the creative classifier's relevance verdict; the rest stay for review.")
    parser.add_argument("--max-total-paid-starts", type=int, default=None, help="Durable section cap across every retry and rerun.")
    parser.add_argument("--pixel-actor-fallback", action="store_true", help="Use the headless tag-detector actor for sites whose HTML cannot be fetched directly (one actor run per batch).")
    parser.add_argument("--max-actor-runs", type=int, default=MAX_ACTOR_RUNS_PER_ATTEMPT)
    parser.add_argument("--max-meta-searches", type=int, default=MAX_META_SEARCHES_PER_ATTEMPT)
    parser.add_argument("--max-search-calls", type=int, default=MAX_SEARCH_CALLS_PER_ATTEMPT)
    parser.add_argument("--max-fetches", type=int, default=MAX_FETCHES_PER_ATTEMPT)
    parser.add_argument("--max-cdx-calls", type=int, default=MAX_CDX_CALLS_PER_ATTEMPT)
    parser.add_argument("--max-spyfu-calls", type=int, default=MAX_SPYFU_CALLS_PER_ATTEMPT, help="SpyFu domain-stats lookups per attempt (one per competitor).")
    args = parser.parse_args()

    try:
        state = run(args.workspace, args)
    except (ChannelFootprintError, ValueError) as exc:
        print(f"{DISPLAY_NAME}: {exc}", file=sys.stderr)
        return 1
    if state["status"] != "completed":
        print(f"{DISPLAY_NAME}: {state['status']} — {state.get('candidates_path', '')}; review decisions, then collect/finalize")
        return 2
    print(
        f"{DISPLAY_NAME}: completed — {len(state['domains'])} competitor(s), {state['actor_runs']} actor run(s), "
        f"{state['meta_searches']} Meta library search(es), {state['search_calls']} web search(es), evidence at "
        f"{state['evidence_path']}, report commit {(state['report_commit_sha'] or '')[:12] or 'n/a'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
