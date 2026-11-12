#!/usr/bin/env python3
"""Collect individual competitor ads and derive scoped creative patterns.

Reuse completed Channel Footprint inputs, restore native text and available
media, and classify comparable offers through OS. Generic taxonomy dimensions
and category-specific message meanings remain distinct. Confirmed serving
history and current examples support patterns within market/channel/type/format;
listing spans never establish delivery duration or conversion performance.
Cached provider responses, labels and video analysis survive compatible retries,
with a durable cumulative resource ceiling and explicit partial coverage.
"""
from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import argparse
import base64
import copy
import hashlib
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
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

SCHEMA_VERSION = 1
EVIDENCE_SCHEMA_VERSION = 2
SECTION_ID = "creative_patterns"
SECTION_HEADING = "Creative patterns"
DEFAULT_OS_URL = "https://os.hz.egbe.dev"
RUNTIME_REL = Path(_artifact_path("egbe-docs/research/market/work")) / SECTION_ID
EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/creative-patterns.json"))
REPORT_REL = Path(_artifact_path("egbe-docs/research/market/full-report.md"))
TAXONOMY_REL = Path("references/config/creative-taxonomy.v1.json")
CHANNEL_FOOTPRINT_EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/channel-footprint.json"))

MAX_COMPETITORS = 10
MAX_EXPLICIT_DOMAINS = 10
# Ten competitors with every source need 32 runs (two Google batches, then
# Meta, LinkedIn and Reddit per competitor): one attempt covers a default run.
MAX_ACTOR_RUNS_PER_ATTEMPT = 36
MAX_META_SEARCHES_PER_ATTEMPT = 12
MAX_SPYFU_CALLS_PER_ATTEMPT = 24
MAX_CLASSIFY_CALLS_PER_ATTEMPT = 40
GOOGLE_ADS_PER_DOMAIN = 40
# A non-brand advertiser is the competitor's legal entity only when it clearly
# dominates the domain's rows. Live 2026-10-02: freecodecamp.org runs no
# Google ads; four unrelated advertisers pointed at it and the largest, with
# 2 of the 4 rows, was taken for the competitor.
GOOGLE_DOMINANT_MIN_ROWS = 3
GOOGLE_DOMINANT_MIN_SHARE = 0.75
META_ADS_PER_BRAND = 30
META_EU_ADS_PER_BRAND = 30
# The LinkedIn library actor works through only the first company page of a
# multi-page input (observed live), so each competitor gets its own run.
LINKEDIN_ADS_PER_COMPANY = 30
REDDIT_ADS_PER_BRAND = 30
SPYFU_ROWS_PER_WINDOW = 100
SPYFU_EARLIER_WINDOW = (105, 365)
TEXT_BATCH = 10
IMAGE_BATCH = 8
CLASSIFY_TIMEOUT_SECONDS = 330.0
# Classification errors that are about the caller, not the batch.
STOP_CLASSIFYING_RE = re.compile(r"HTTP (?:401|402|403|429)\b|budget_exceeded|Budget has been exceeded|ExceededBudget")
PRODUCT_CONTEXT_CHARS = 24000
ALL_SOURCES = ("google_transparency", "meta", "google_search", "linkedin", "reddit")
# Libraries that keep stopped ads listed (LinkedIn keeps them a year after the
# last impression): being listed at a cutoff proves neither age nor delivery.
LISTS_STOPPED_ADS = {"linkedin_library_actor", "reddit_library_actor"}
# Rows kept per competitor and platform for ads that stopped since an earlier
# cutoff; they never take the places of ads seen at this cutoff.
# Which creative `source` values each selectable source produces.
SOURCE_ROW_SOURCES = {
    "google_transparency": {"google_transparency"},
    "meta": {"meta_library_actor", "meta_library_official_eu"},
    "google_search": {"spyfu_ad_history"},
    "linkedin": {"linkedin_library_actor"},
    "reddit": {"reddit_library_actor"},
}
PLATFORM_CHANNELS = {"google": "google_ads", "youtube": "youtube_ads", "meta": "meta_ads", "linkedin": "linkedin_ads", "reddit": "reddit_ads"}
# A price needs an amount: a currency sign or code next to a number, or a
# percent discount. Period words alone ("in a month") are not prices.
_WS_RE = re.compile(r"\s+")
_TEMPLATE_RE = re.compile(r"\{\{[^}]+\}\}")
# SpyFu renders sitelinks and callouts as Markdown links to "#".
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(#?\)")
_SITELINK_SEP_RE = re.compile(r"\s*(?:·|\\n|\n)\s*")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _load_script(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load bundled script {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


# The Channel Footprint runner owns the OS client (cache, journaled starts,
# per-attempt budgets, the per-source breaker) and the identity rules
# (destination first, strict advertiser names); this runner reuses them.
CF = _load_script("run-channel-footprint.py", "pmr_channel_footprint_for_creative_patterns")
POLICY = _load_script("research-policy.py", "pmr_policy_for_creative_patterns")
MODEL = _load_script("creative-model.py", "pmr_creative_model")
SEMANTICS = _load_script("creative-semantics.py", "pmr_creative_semantics")
VIDEO = _load_script("creative-video.py", "pmr_creative_video")
SPYFU_RECENT_WINDOW_DAYS = 30  # Bounded provider query window; never an activity or success threshold.
CreativePatternsError = CF.ChannelFootprintError
BudgetExhausted = CF.BudgetExhausted
SourceUnavailable = CF.SourceUnavailable
registrable_domain = CF.registrable_domain
brand_token = CF.brand_token
usable_destination = CF.usable_destination


def load_taxonomy(path: Path | None = None) -> tuple[dict[str, Any], str]:
    taxonomy_path = path or (Path(__file__).resolve().parent.parent / TAXONOMY_REL)
    raw = taxonomy_path.read_bytes()
    taxonomy = json.loads(raw)
    if taxonomy.get("schema_version") != 1 or not isinstance(taxonomy.get("dimensions"), dict):
        raise CreativePatternsError("the creative taxonomy file has an unexpected shape")
    return taxonomy, hashlib.sha256(raw).hexdigest()


# ── OS client: the Channel Footprint client plus SpyFu ad history and
#    creative classification

@dataclass
class OsClient(CF.OsClient):
    max_classify_calls: int = MAX_CLASSIFY_CALLS_PER_ATTEMPT
    classify_calls: int = 0
    # Classifications and images depend only on the creative, so they live in
    # one cache shared by every cutoff (a refresh never pays for them twice).
    shared_dir: Path | None = None
    semantic_context: dict[str, Any] | None = None
    media_calls: int = 0
    max_media_calls: int = 100
    budget_gaps: list[dict] = field(default_factory=list)
    # Deployment and shared AI-account failures are scoped to this attempt.
    # Successful content caches stay available; a later client can recover.
    media_endpoint_blocked: dict[str, str] = field(default_factory=dict)
    paid_ai_blocked_reason: str = ""

    def media_call(self, path: str, payload: dict[str, Any], *, kind: str, timeout: float = 330.0) -> dict[str, Any]:
        key_payload = {"kind": kind, "path": path, "payload": payload}
        digest = hashlib.sha256(json.dumps(key_payload, sort_keys=True).encode()).hexdigest()
        cache = self._shared() / f"{digest}.json"
        entry = self._cache_read(cache)
        self.touched.add(digest)
        if entry is not None:
            self.cache_hits += 1
            return entry.get("response") or {}
        if path.startswith("/v1/media/") and self.paid_ai_blocked_reason:
            raise CreativePatternsError(self.paid_ai_blocked_reason)
        if path in self.media_endpoint_blocked:
            raise SourceUnavailable(self.media_endpoint_blocked[path])
        if self.media_calls >= self.max_media_calls:
            raise BudgetExhausted("media call budget exhausted for this attempt; remaining videos are budget_deferred")
        self._reserve_paid_start(kind, digest)
        self.media_calls += 1
        try:
            response = (self.request or self._http)(path, payload, timeout, idempotency_key=None)
        except Exception as exc:
            reason = str(exc)[:500]
            if path.startswith("/v1/media/") and STOP_CLASSIFYING_RE.search(reason):
                self.paid_ai_blocked_reason = reason
                raise CreativePatternsError(reason) from exc
            if re.search(r"HTTP (?:404|405|503)\b", reason):
                self.media_endpoint_blocked[path] = reason
                raise SourceUnavailable(reason) from exc
            raise
        self._cache_write(cache, {"kind": kind, "response": response, "cutoff": self.cutoff, "retrieved_on": date.today().isoformat()})
        return response


    def _shared(self) -> Path:
        base = self.shared_dir or self.cache_dir
        base.mkdir(parents=True, exist_ok=True)
        return base

    def spyfu_ad_history(self, domain: str, country: str, since: str, until: str, max_rows: int) -> tuple[dict[str, Any], str]:
        payload = {"domain": domain, "country_code": country, "max_rows": max_rows, "since": since, "until": until}
        response, retrieved_on = self._metered(
            "spyfu", "/tools/spyfu/ad-history", payload, 90.0,
            budget_attr="spyfu_calls", budget_max=self.max_spyfu_calls, label="SpyFu lookup", paid=False,
            retry_delay=CF.FREE_RETRY_DELAY_SECONDS,
        )
        if response.get("unavailable"):
            raise SourceUnavailable(f"SpyFu rejected the request: {response['unavailable']}")
        if response.get("limited_by_quota"):
            # The gateway cut the page to the claw's remaining daily rows: not
            # the window's answer. Drop it from the cache and retry later.
            digest = hashlib.sha256(json.dumps({"kind": "spyfu", "path": "/tools/spyfu/ad-history", "payload": payload}, sort_keys=True).encode("utf-8")).hexdigest()
            CF.IO.drop_cache_entry(self.cache_dir / f"{digest}.json")
            raise CreativePatternsError("SpyFu answer was cut by the daily spyfu:rows limit; rerun after the limit resets")
        return response, retrieved_on

    def classify(self, request: dict[str, Any], images: dict[str, dict[str, Any]], taxonomy_sha256: str) -> tuple[dict[str, Any], str, str]:
        """One POST /v1/media/classify-creative call. The cache key covers the
        request with frame hashes (never the image bytes) and the local
        taxonomy file's hash, so an edited taxonomy is never served old answers."""
        key_payload = {**request, "taxonomy_sha256": taxonomy_sha256, "classification_contract": 4,
                       "frames": [{"ref": ref, "sha256": images[ref]["sha256"], "media_type": images[ref]["media_type"]} for ref in sorted(images)]}
        digest = hashlib.sha256(json.dumps({"kind": "classify", "path": "/v1/media/classify-creative", "payload": key_payload}, sort_keys=True).encode("utf-8")).hexdigest()
        cache_file = self._shared() / f"{digest}.json"
        self.touched.add(digest)
        entry = self._cache_read(cache_file)
        if entry is not None:
            self.cache_hits += 1
            response = entry.get("response")
            if isinstance(response, dict) and response.get("unavailable"):
                error = SourceUnavailable(f"classification batch was rejected: {response['unavailable']}")
                error.batch_digest = digest
                raise error
            return (response if isinstance(response, dict) else {}), entry.get("retrieved_on") or date.today().isoformat(), digest
        wire = {**{k: v for k, v in request.items()}, "frames": [
            {"ref": ref, "timestamp_seconds": 0, "media_type": images[ref]["media_type"], "sha256": images[ref]["sha256"],
             "content_base64": base64.b64encode(self.image_bytes(images[ref])).decode("ascii")}
            for ref in sorted(images)
        ]}
        if self.paid_ai_blocked_reason:
            raise CreativePatternsError(self.paid_ai_blocked_reason)
        transport = self.request or self._http
        attempts = 0
        while True:
            if self.classify_calls >= self.max_classify_calls:
                raise BudgetExhausted(f"classification budget exhausted ({self.max_classify_calls} calls per attempt); {self.cache_writes} new answer(s) cached in this attempt; rerun to continue from the cache")
            self._reserve_paid_start("classify", digest)
            self.classify_calls += 1
            try:
                response = transport("/v1/media/classify-creative", wire, CLASSIFY_TIMEOUT_SECONDS, idempotency_key=None)
                break
            except CreativePatternsError as exc:
                if re.search(r"HTTP 422\b", str(exc)):
                    # A rejected request is a fact about this batch: cache it
                    # so reruns never send (or pay for) it again.
                    self._cache_write(cache_file, {"kind": "classify", "path": "/v1/media/classify-creative", "payload": key_payload,
                                                   "response": {"unavailable": str(exc)[:300]}, "cutoff": self.cutoff,
                                                   "retrieved_on": date.today().isoformat()})
                    error = SourceUnavailable(f"classification batch was rejected: {str(exc)[:300]}")
                    error.batch_digest = digest
                    raise error from exc
                # A server error (502 included: the model's answer may fail
                # validation once) or an unreachable OS gets one retry.
                unreachable = isinstance(exc, CF.OsUnreachable)
                if attempts >= 1 or not (unreachable or re.search(r"HTTP 5(?:00|02|03|04)\b", str(exc))):
                    raise
                attempts += 1
                (self.sleep or time.sleep)(CF.OS_UNREACHABLE_RETRY_DELAY_SECONDS if unreachable else CF.FREE_RETRY_DELAY_SECONDS)
        retrieved_on = date.today().isoformat()
        self._cache_write(cache_file, {"kind": "classify", "path": "/v1/media/classify-creative", "payload": key_payload, "response": response,
                                       "cutoff": self.cutoff, "retrieved_on": retrieved_on})
        return response, retrieved_on, digest

    def ledger_totals(self) -> dict[str, Any]:
        kinds = ("actor", "meta-ad-library", "spyfu", "classify", "image", "video_metadata", "video_transcription", "video_analysis")
        counts = dict.fromkeys(kinds, 0)
        reused = dict.fromkeys(kinds, 0)
        rejected = 0
        usage = {"classify_prompt_tokens": 0, "classify_completion_tokens": 0,
                 "media_prompt_tokens": 0, "media_completion_tokens": 0}
        dates = []
        for digest in sorted(self.touched):
            path = self.cache_dir / f"{digest}.json"
            if CF.IO.cache_entry_path(path) is None and self.shared_dir is not None:
                path = self.shared_dir / f"{digest}.json"
            entry = self._cache_read(path)
            if not entry:
                continue
            kind, response = entry.get("kind"), entry.get("response") or {}
            if response.get("unavailable"):
                rejected += 1
            elif kind in kinds:
                if kind in ("classify", "image", "video_metadata", "video_transcription", "video_analysis") and self.cutoff and entry.get("cutoff") not in (None, self.cutoff):
                    reused[kind] += 1
                else:
                    counts[kind] += 1
                    token_usage = response.get("usage") or {}
                    prefix = "classify" if kind == "classify" else "media"
                    if kind != "image":
                        for field in ("prompt_tokens", "completion_tokens"):
                            key = prefix + "_" + field
                            value = token_usage.get(field)
                            if key in usage and type(value) is int:
                                usage[key] += value
            if isinstance(entry.get("retrieved_on"), str):
                dates.append(entry["retrieved_on"])
        media_calls = sum(counts[k] for k in ("video_metadata", "video_transcription", "video_analysis"))
        provider = sum(counts[k] for k in kinds if k != "image")
        budget = self._cache_read(self.cumulative_budget_path) if self.cumulative_budget_path else None
        return {"actor_runs": counts["actor"], "meta_searches": counts["meta-ad-library"], "spyfu_calls": counts["spyfu"],
                "classify_calls": counts["classify"], "reused_classify_calls": reused["classify"], "image_fetches": counts["image"],
                "media_calls": media_calls, "video_metadata_calls": counts["video_metadata"],
                "video_transcription_calls": counts["video_transcription"], "video_analysis_calls": counts["video_analysis"],
                "reused_media_calls": sum(reused[k] for k in ("video_metadata", "video_transcription", "video_analysis")),
                "provider_calls": provider, "rejected_calls": rejected, "observations": provider + counts["image"], **usage,
                "cumulative_paid_starts": len((budget or {}).get("paid_starts", [])),
                "cumulative_paid_start_limit": (budget or {}).get("limit", self.max_total_paid_starts),
                "first_retrieved_on": min(dates) if dates else date.today().isoformat(),
                "last_retrieved_on": max(dates) if dates else date.today().isoformat()}


# ── normalization helpers ───────────────────────────────────────────────────

def _clean_text(value: Any, cap: int | None = 600) -> str | None:
    if not isinstance(value, str):
        return None
    if "](#" in value or "]()" in value:
        value = _MD_LINK_RE.sub(lambda m: "; " + m.group(1).strip() if m.group(1).strip() else "", value)
        value = _SITELINK_SEP_RE.sub(" ", value).replace(" ;", ";").strip(" ;")
    text = _WS_RE.sub(" ", value).strip()
    if not text or _TEMPLATE_RE.fullmatch(text) or text.startswith("{{"):
        return None
    return text[:cap]


def _norm(value: str | None) -> str:
    return _WS_RE.sub(" ", (value or "").casefold()).strip()


def fingerprint(headline: str | None, body: str | None, media: str | None = None, ad_key: str | None = None) -> str:
    """Similarity key for copy/visual variants; never an ad identity or age proof."""
    if _norm(headline) or _norm(body):
        text = "copy:" + _norm(headline) + " | " + _norm(body)
    elif media:
        text = "media:" + media
    else:
        text = "ad:" + (ad_key or "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def destination_url(values: list[Any]) -> str | None:
    """The first full landing URL whose host is usable (redirect wrappers
    unwrapped, platform and link-hub hosts skipped); the host alone is what
    identity checks use, the URL is what the classifier and funnels need."""
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        url = value.strip()
        parsed = urllib.parse.urlsplit(url if "//" in url else "https://" + url)
        host = (parsed.hostname or "").lower()
        if host in CF.REDIRECT_WRAPPER_HOSTS:
            wrapped = urllib.parse.parse_qs(parsed.query).get("u") or urllib.parse.parse_qs(parsed.query).get("q")
            if not wrapped:
                continue
            parsed = urllib.parse.urlsplit(urllib.parse.unquote(wrapped[0]))
        if parsed.scheme not in ("http", "https") or not usable_destination(urllib.parse.urlunsplit(parsed)):
            continue
        return urllib.parse.urlunsplit(parsed)[:2000]
    return None


def _days(first: str | None, last: str | None) -> int | None:
    return CF._days_between(first, last)


def _alias(taxonomy: dict[str, Any], dimension: str, platform: str, raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw:
        return None
    return (taxonomy.get("aliases", {}).get(dimension) or {}).get(f"{platform}:{raw}")


def _creative(*, domain: str, platform: str, source: str, ad_id: str, advertiser: str | None, headline: str | None,
              body: str | None, extra_texts: list[str] | None = None, cta_label: str | None = None, cta_code: str | None = None,
              landing_url: str | None = None, format_raw: str | None = None, image_url: str | None = None,
              first_seen: str | None, last_seen: str | None, served_days: int | None, running: bool | None,
              age_basis: str, market_scope: str, verified_by: str, link: str | None, extra: dict[str, Any] | None = None,
              taxonomy: dict[str, Any]) -> dict[str, Any]:
    extra_texts = [t for t in (extra_texts or []) if t]
    row = {
        "type": "creative",
        "creative_id": f"{platform}:{ad_id}",
        "domain": domain,
        "platform": platform,
        "channel": PLATFORM_CHANNELS.get(platform, platform),
        "source": source,
        "ad_id": ad_id,
        "competitor_tier": "unknown", "relevance": "unknown", "country": None, "countries": [],
        "duration_scope": "global" if age_basis == "platform_dates" else "unknown",
        "advertiser": advertiser,
        "headline": headline,
        "body": body,
        "extra_texts": extra_texts,
        "cta_label": cta_label,
        "cta_code": cta_code,
        "cta_intent": _alias(taxonomy, "cta_intent", platform, cta_code),
        "landing_url": landing_url,
        "landing_host": registrable_domain(landing_url) if landing_url else None,
        "format_raw": format_raw,
        "format_kind": _alias(taxonomy, "format_kind", platform, format_raw),
        "image_url": image_url,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "served_days": served_days,
        "running_at_capture": running,
        "age_basis": age_basis,
        "market_scope": market_scope,
        "verified_by": verified_by,
        "link": link,
        "fingerprint": fingerprint(headline, body, image_url, f"{platform}:{ad_id}"),
        "tier": "A",
    }
    row.update(extra or {})
    return row


# ── collectors ──────────────────────────────────────────────────────────────

def _google_identity(rows: list[dict[str, Any]], domain: str) -> tuple[set[str], str]:
    """Which advertisers of a domain's Transparency rows are the competitor.
    Names that are (or contain) the brand win; when none does, the verified
    advertiser behind at least three rows and three quarters of the domain's
    rows is the competitor (its legal entity, e.g. Ryzac, Inc. for
    codecademy.com); otherwise none is. The rest are third parties."""
    brand = brand_token(domain)
    by_advertiser: dict[str, list[str]] = {}
    for ad in rows:
        key = str(ad.get("advertiserId") or ad.get("advertiserName") or "").strip()
        by_advertiser.setdefault(key, []).append(str(ad.get("advertiserName") or "").strip())
    named = {key for key, names in by_advertiser.items() if any(CF._name_matches(n, brand) or CF._mentions(n, brand) for n in names if n)}
    if named:
        return named, "destination_and_advertiser"
    if not by_advertiser:
        return set(), "destination_and_advertiser"
    dominant, ads = sorted(by_advertiser.items(), key=lambda kv: (-len(kv[1]), kv[0]))[0]
    total = sum(len(names) for names in by_advertiser.values())
    if len(ads) < GOOGLE_DOMINANT_MIN_ROWS or len(ads) < GOOGLE_DOMINANT_MIN_SHARE * total:
        return set(), "destination_and_advertiser"
    return {dominant}, "destination_dominant_advertiser"


def collect_google_transparency(client: OsClient, spec: dict[str, Any], domains: list[str], as_of: date, taxonomy: dict[str, Any], excluded: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ads Transparency Center by destination domain: format, first and last
    shown, and the rendered image for text and image ads. Destination keying
    does not prove the advertiser, so third-party advertisers are excluded."""
    rows: list[dict[str, Any]] = []
    batch = max(1, int(spec.get("batch_domains") or 5))
    for start in range(0, len(domains), batch):
        chunk = domains[start:start + batch]
        result, retrieved_on = CF._call_with_context(client, ", ".join(chunk), "Google Ads Transparency", lambda chunk=chunk: client.run_actor(
            spec["actor"], {"domains": chunk, "resultType": "ads", "region": "ANYWHERE", "maxAdsPerSearch": GOOGLE_ADS_PER_DOMAIN},
            GOOGLE_ADS_PER_DOMAIN * len(chunk),
        ))
        by_domain: dict[str, list[dict[str, Any]]] = {}
        seen: set[str] = set()
        for ad in result:
            domain = registrable_domain(str(ad.get("domain") or ""))
            creative_id = str(ad.get("creativeId") or "")
            if domain in chunk and creative_id and creative_id not in seen:
                seen.add(creative_id)
                by_domain.setdefault(domain, []).append(ad)
        for domain in chunk:
            ads = by_domain.get(domain) or []
            own, verified_by = _google_identity(ads, domain)
            third_party = sorted({str(ad.get("advertiserName") or "")[:80] for ad in ads
                                  if str(ad.get("advertiserId") or ad.get("advertiserName") or "").strip() not in own})
            for ad in ads:
                if str(ad.get("advertiserId") or ad.get("advertiserName") or "").strip() not in own:
                    continue
                creative_id = str(ad["creativeId"])
                first = str(ad.get("firstShown") or "")[:10] or None
                last = str(ad.get("lastShown") or "")[:10] or None
                served = ad.get("shownForDays") if isinstance(ad.get("shownForDays"), int) else _days(first, last)
                fmt = str(ad.get("format") or "").upper() or None
                platform = "youtube" if fmt == "VIDEO" else "google"
                image = ad.get("imageUrl") if fmt in ("TEXT", "IMAGE") and isinstance(ad.get("imageUrl"), str) else None
                gap = _days(last, as_of.isoformat()) if last else None
                rows.append(_creative(
                    domain=domain, platform=platform, source="google_transparency", ad_id=creative_id,
                    advertiser=str(ad.get("advertiserName") or "").strip() or None, headline=None, body=None, format_raw=fmt, image_url=image,
                    first_seen=first, last_seen=last, served_days=served, running=None,
                    age_basis="platform_dates", market_scope="global", verified_by=verified_by,
                    link=ad.get("adUrl") or None, taxonomy=_google_taxonomy(taxonomy, platform), extra={"retrieved_on": retrieved_on},
                ))
            if third_party:
                excluded.append({"type": "coverage", "domain": domain, "source": "google_transparency", "status": "excluded",
                                 "detail": f"{len(third_party)} third-party advertiser(s) pointing at the domain: {', '.join(third_party[:4])}", "tier": "C"})
    return rows


def _google_taxonomy(taxonomy: dict[str, Any], platform: str) -> dict[str, Any]:
    # YouTube creatives come from the Google library and use its format codes.
    if platform != "youtube":
        return taxonomy
    aliases = dict(taxonomy.get("aliases") or {})
    aliases["format_kind"] = {**(aliases.get("format_kind") or {}), "youtube:VIDEO": "video"}
    return {**taxonomy, "aliases": aliases}


def collect_google_search(client: OsClient, domain: str, country: str, as_of: date, taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    """Preserve native SpyFu ads; capture spans describe sightings, not delivery."""
    recent_days = SPYFU_RECENT_WINDOW_DAYS
    windows = (((as_of - timedelta(days=recent_days)).isoformat(), as_of.isoformat()),
               ((as_of - timedelta(days=SPYFU_EARLIER_WINDOW[1])).isoformat(),
                (as_of - timedelta(days=SPYFU_EARLIER_WINDOW[0])).isoformat()))
    groups: dict[str, dict[str, Any]] = {}
    for since, until in windows:
        response, retrieved_on = client.spyfu_ad_history(domain, country, since, until, SPYFU_ROWS_PER_WINDOW)
        for row in response.get("rows") or []:
            if not isinstance(row, dict) or registrable_domain(str(row.get("display_domain") or row.get("url") or "")) != domain:
                continue
            headline, body = _clean_text(row.get("title"), None), _clean_text(row.get("body"), None)
            seen_on = row.get("seen_on")
            if not (headline or body) or not isinstance(seen_on, str) or not _DATE_RE.match(seen_on):
                continue
            native = str(row["ad_id"]) if row.get("ad_id") is not None else None
            # Without a native ID, preserve each distinct source observation.
            key = native or "observation-" + POLICY.canonical_hash(row)[:20]
            group = groups.setdefault(key, {"headline": headline, "body": body, "dates": [],
                "observations": [], "native": native, "retrieved_on": retrieved_on})
            if row not in group["observations"]:
                group["observations"].append(dict(row))
                group["dates"].append(seen_on)
    creatives = []
    recent_start = (as_of - timedelta(days=recent_days)).isoformat()
    for key, group in groups.items():
        first, last = min(group["dates"]), max(group["dates"])
        landing = destination_url([row.get("url") for row in group["observations"]])
        creatives.append(_creative(
            domain=domain, platform="google", source="spyfu_ad_history", ad_id=f"search-{domain}-{key}", advertiser=domain,
            headline=group["headline"], body=group["body"], landing_url=landing, format_raw="TEXT",
            first_seen=first, last_seen=last, served_days=None, running=None,
            age_basis="capture_dates", market_scope="target", verified_by="display_domain", link=landing, taxonomy=taxonomy,
            extra={"keywords": list(dict.fromkeys(row["keyword"] for row in group["observations"] if row.get("keyword"))),
                   "captures": len(group["dates"]), "spyfu_ad_ids": [group["native"]] if group["native"] else [],
                   "native_ad_id": group["native"] or key, "country": country, "countries": [country],
                   "duration_scope": "unknown", "source_observations": group["observations"], "retrieved_on": group["retrieved_on"]},
        ))
    return creatives


def _meta_identity(domain: str, brand: str, page_name: str, destinations: list[str]) -> str | None:
    """Destination first: a usable address decides; the advertiser name
    decides only when the ad carries no usable destination."""
    hosts = {registrable_domain(d) for d in (usable_destination(x) for x in destinations) if d}
    if hosts:
        return "destination" if domain in hosts else None
    return "exact_name" if CF._name_matches(page_name, brand) else None


def _meta_actor_creative(ad: dict[str, Any], domain: str, brand: str, as_of: date, retrieved_on: str, taxonomy: dict[str, Any]) -> dict[str, Any] | None:
    snapshot = ad.get("snapshot") if isinstance(ad.get("snapshot"), dict) else {}
    cards = [c for c in (snapshot.get("cards") or []) if isinstance(c, dict)]
    page_name = str(ad.get("page_name") or snapshot.get("page_name") or "")
    destinations = [snapshot.get("link_url"), snapshot.get("caption")] + [c.get("link_url") for c in cards]
    verified = _meta_identity(domain, brand, page_name, [d for d in destinations if isinstance(d, str)])
    ad_id = str(ad.get("ad_archive_id") or ad.get("adArchiveID") or "")
    if not verified or not ad_id:
        return None
    headline = _clean_text(snapshot.get("title"), 300) or next((_clean_text(c.get("title"), 300) for c in cards if _clean_text(c.get("title"), 300)), None)
    body = _clean_text((snapshot.get("body") or {}).get("text") if isinstance(snapshot.get("body"), dict) else snapshot.get("body"), None) \
        or next((_clean_text(c.get("body"), 1200) for c in cards if _clean_text(c.get("body"), 1200)), None)
    extra_texts: list[str] = []
    for value in [snapshot.get("link_description")] + [x for c in cards for x in (c.get("title"), c.get("body"), c.get("link_description"))]:
        text = _clean_text(value, None)
        if text and text not in (headline, body) and text not in extra_texts:
            extra_texts.append(text)
    images = snapshot.get("images") if isinstance(snapshot.get("images"), list) else []
    videos = snapshot.get("videos") if isinstance(snapshot.get("videos"), list) else []
    image = next((i.get("original_image_url") or i.get("resized_image_url") for i in images if isinstance(i, dict) and (i.get("original_image_url") or i.get("resized_image_url"))), None) \
        or next((v.get("video_preview_image_url") for v in videos if isinstance(v, dict) and v.get("video_preview_image_url")), None) \
        or next((c.get("original_image_url") or c.get("resized_image_url") or c.get("video_preview_image_url") for c in cards if c.get("original_image_url") or c.get("resized_image_url") or c.get("video_preview_image_url")), None)
    landing = destination_url(destinations)
    first = CF._iso_from_epoch(ad.get("start_date"))
    active = bool(ad.get("is_active"))
    # A resumed attempt must not accrue evidence after its immutable cutoff.
    last = min(retrieved_on, as_of.isoformat()) if active else CF._iso_from_epoch(ad.get("end_date"))
    fmt = str(snapshot.get("display_format") or "").upper() or None
    cta_code = snapshot.get("cta_type") or next((c.get("cta_type") for c in cards if c.get("cta_type")), None)
    return _creative(
        domain=domain, platform="meta", source="meta_library_actor", ad_id=ad_id, advertiser=page_name or None,
        headline=headline, body=body, extra_texts=extra_texts, cta_label=_clean_text(snapshot.get("cta_text"), 60),
        cta_code=cta_code if isinstance(cta_code, str) else None, landing_url=landing, format_raw=fmt, image_url=image,
        first_seen=first, last_seen=last, served_days=_days(first, last), running=active, age_basis="platform_dates",
        market_scope="target", verified_by=verified, link=f"https://www.facebook.com/ads/library/?id={ad_id}", taxonomy=taxonomy,
        extra={"collation_count": ad.get("collation_count") if isinstance(ad.get("collation_count"), int) else None,
               "publisher_platforms": [p for p in (ad.get("publisher_platform") or []) if isinstance(p, str)][:6],
               "retrieved_on": retrieved_on,
               "video_url": next((v.get("video_hd_url") or v.get("video_sd_url") or v.get("video_url") for v in videos + cards if isinstance(v, dict) and (v.get("video_hd_url") or v.get("video_sd_url") or v.get("video_url"))), None),
               "media_urls": list(dict.fromkeys(u for v in images + videos + cards if isinstance(v, dict) for u in [v.get("original_image_url") or v.get("resized_image_url") or v.get("video_preview_image_url")] if u)),
               "media_cards": [{k: c.get(k) for k in ("title","body","link_description","original_image_url","resized_image_url","video_preview_image_url","video_hd_url","video_sd_url","link_url")} for c in cards]},
    )


def _eu_demographics(row: dict[str, Any]) -> dict[str, Any] | None:
    breakdown = row.get("age_country_gender_reach_breakdown")
    if not isinstance(breakdown, list):
        return None
    by_age: dict[str, int] = {}
    by_gender = {"male": 0, "female": 0, "unknown": 0}
    for country in breakdown:
        for item in (country.get("age_gender_breakdowns") or []) if isinstance(country, dict) else []:
            if not isinstance(item, dict):
                continue
            total = sum(int(item.get(g) or 0) for g in by_gender)
            by_age[str(item.get("age_range"))] = by_age.get(str(item.get("age_range")), 0) + total
            for g in by_gender:
                by_gender[g] += int(item.get(g) or 0)
    total = sum(by_gender.values())
    if not total:
        return None
    top_ages = sorted(by_age.items(), key=lambda kv: -kv[1])[:2]
    return {"top_age_ranges": [age for age, _ in top_ages], "female_share": round(by_gender["female"] / total, 2),
            "reach_counted": total, "target_ages": row.get("target_ages") if isinstance(row.get("target_ages"), list) else None,
            "target_gender": row.get("target_gender") if isinstance(row.get("target_gender"), str) else None}


def _meta_official_creative(row: dict[str, Any], domain: str, brand: str, as_of: date, retrieved_on: str, taxonomy: dict[str, Any]) -> dict[str, Any] | None:
    def first_text(key: str, cap: int) -> str | None:
        values = row.get(key)
        values = [values] if isinstance(values, str) else (values if isinstance(values, list) else [])
        return next((_clean_text(v, cap) for v in values if _clean_text(v, cap)), None)

    captions = row.get("ad_creative_link_captions")
    captions = [captions] if isinstance(captions, str) else [c for c in (captions or []) if isinstance(c, str)]
    verified = _meta_identity(domain, brand, str(row.get("page_name") or ""), captions)
    ad_id = str(row.get("id") or "")
    if not verified or not ad_id.isdigit():
        return None
    first = str(row.get("ad_delivery_start_time") or "")[:10] or None
    stop = str(row.get("ad_delivery_stop_time") or "")[:10] or None
    last = stop or min(retrieved_on, as_of.isoformat())
    return _creative(
        domain=domain, platform="meta", source="meta_library_official_eu", ad_id=ad_id, advertiser=row.get("page_name"),
        headline=first_text("ad_creative_link_titles", 300), body=first_text("ad_creative_bodies", None),
        extra_texts=[t for key in ("ad_creative_bodies", "ad_creative_link_titles", "ad_creative_link_descriptions") for d in (row.get(key) if isinstance(row.get(key), list) else [row.get(key)]) if (t := _clean_text(d, None))], landing_url=None, format_raw=None,
        first_seen=first, last_seen=last, served_days=_days(first, last), running=stop is None, age_basis="platform_dates",
        market_scope="eu_proxy", verified_by=verified,
        # The public permalink; the Graph render URL carries an access token.
        link=f"https://www.facebook.com/ads/library/?id={ad_id}", taxonomy=taxonomy,
        extra={"eu_total_reach": row.get("eu_total_reach") if isinstance(row.get("eu_total_reach"), int) else None,
               "eu_demographics": _eu_demographics(row),
               "publisher_platforms": [p for p in (row.get("publisher_platforms") or []) if isinstance(p, str)][:6],
               "retrieved_on": retrieved_on},
    )


META_EU_FIELDS = ",".join((
    "id", "page_id", "page_name", "ad_delivery_start_time", "ad_delivery_stop_time", "ad_creative_bodies",
    "ad_creative_link_titles", "ad_creative_link_descriptions", "ad_creative_link_captions", "publisher_platforms",
    "languages", "eu_total_reach", "age_country_gender_reach_breakdown", "target_ages", "target_gender",
    "target_locations", "beneficiary_payers",
))


def collect_meta(client: OsClient, spec: dict[str, Any], domain: str, as_of: date, eu_country: str, taxonomy: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """The creatives plus the number of US page-search rows: fewer rows than
    requested means the listing was complete, the only case in which an ad
    missing at a later cutoff can be read as stopped."""
    brand = brand_token(domain)
    # Running ads only: an all-status sample of 30 is mostly stopped ads of
    # global brands; stopped ones come from the EU data and earlier snapshots.
    search_url = CF.meta_search_url(brand, "US", active_status="active")
    result, retrieved_on = CF._call_with_context(client, domain, "Meta Ad Library page search", lambda: client.run_actor(
        spec["actor"], {"urls": [{"url": search_url}], "count": META_ADS_PER_BRAND}, META_ADS_PER_BRAND,
    ))
    rows = []
    seen = set()
    for ad in result:
        creative = _meta_actor_creative(ad, domain, brand, as_of, retrieved_on, taxonomy)
        if creative and creative["ad_id"] not in seen:
            seen.add(creative["ad_id"])
            creative.update(country="US", countries=["US"], duration_scope="global")
            rows.append(creative)
    try:
        official, eu_retrieved = CF._call_with_context(client, domain, "Meta Ad Library EU", lambda: client.meta_library_search(
            {"query": brand, "countries": [eu_country], "activeStatus": "ALL", "limit": META_EU_ADS_PER_BRAND, "fields": META_EU_FIELDS},
        ))
    except BudgetExhausted as exc:
        if "cumulative" not in str(exc):
            raise
        client.budget_gaps.append({"type": "coverage", "domain": domain, "country": eu_country, "channel": "meta_ads", "source": "meta_library_official_eu", "status": "budget_deferred", "detail": str(exc), "tier": "C"})
        return rows, len(result)
    seen = set()
    for row in official:
        creative = _meta_official_creative(row, domain, brand, as_of, eu_retrieved, taxonomy)
        if creative and creative["ad_id"] not in seen:
            seen.add(creative["ad_id"])
            creative.update(country=eu_country, countries=[eu_country], duration_scope="global")
            rows.append(creative)
    # Same ID in different markets stays separate. Global delivery dates and
    # EU aggregate reach must not strengthen the US observation.
    return rows, len(result)


def collect_linkedin(client: OsClient, spec: dict[str, Any], domain: str, slug: str | None, taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    query = f"https://www.linkedin.com/company/{slug or brand_token(domain)}"
    result, retrieved_on = CF._call_with_context(client, domain, "LinkedIn Ad Library", lambda: client.run_actor(
        spec["actor"], {"queries": [query], "maxResults": LINKEDIN_ADS_PER_COMPANY, "enrich": True}, LINKEDIN_ADS_PER_COMPANY,
    ))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ad in result:
        ad_id = str(ad.get("ad_id") or "")
        if not ad_id or ad_id in seen or str(ad.get("query") or "").rstrip("/") != query \
                or not CF._name_matches(str(ad.get("advertiser_name") or ""), brand_token(domain)):
            continue
        seen.add(ad_id)
        images = [u for u in (ad.get("image_urls") or []) if isinstance(u, str)]
        rows.append(_creative(
            domain=domain, platform="linkedin", source="linkedin_library_actor", ad_id=ad_id, advertiser=ad.get("advertiser_name"),
            headline=_clean_text(ad.get("headline"), 300), body=_clean_text(ad.get("ad_copy"), 1200), format_raw=str(ad.get("creative_format") or "") or None,
            image_url=images[0] if images else None, first_seen=None, last_seen=None, served_days=None, running=None,
            age_basis="none", market_scope="global", verified_by="company_page_query", link=ad.get("detail_url"), taxonomy=taxonomy,
            extra={"retrieved_on": retrieved_on},
        ))
    return rows


def collect_reddit(client: OsClient, spec: dict[str, Any], domain: str, taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    brand = brand_token(domain)
    result, retrieved_on = CF._call_with_context(client, domain, "Reddit ad library", lambda: client.run_actor(
        spec["actor"], {"query": brand, "maxItems": REDDIT_ADS_PER_BRAND}, REDDIT_ADS_PER_BRAND,
    ))
    rows: list[dict[str, Any]] = []
    for ad in result:
        ad_id = str(ad.get("id") or ad.get("creativeId") or "")
        advertiser = str(ad.get("advertiserName") or "")
        verified = _meta_identity(domain, brand, advertiser.removeprefix("u_"), [ad.get("destinationUrl") or ""])
        if not verified or not ad_id:
            continue
        created = str(ad.get("createdAt") or "")[:10] or None
        rows.append(_creative(
            domain=domain, platform="reddit", source="reddit_library_actor", ad_id=ad_id, advertiser=advertiser or None,
            headline=_clean_text(ad.get("headline"), 300), body=_clean_text(ad.get("body"), 1200),
            cta_label=_clean_text(ad.get("callToAction"), 60), landing_url=destination_url([ad.get("destinationUrl")]),
            format_raw=str(ad.get("creativeType") or "") or None, image_url=ad.get("mediaUrl") or ad.get("thumbnailUrl"),
            first_seen=created, last_seen=created, served_days=None, running=None, age_basis="creation_only", market_scope="global",
            verified_by=verified, link=ad.get("postUrl"), taxonomy=taxonomy,
            extra={"objective": ad.get("objective"), "budget_category": ad.get("budgetCategory"),
                   "placements": [p for p in (ad.get("placements") or []) if isinstance(p, str)][:4], "retrieved_on": retrieved_on},
        ))
    return rows


# ── longevity and selection ─────────────────────────────────────────────────

def cap_at_cutoff(creatives: list[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    """No evidence after the cutoff, whatever the source: an ad first seen
    after it did not exist yet, and one last seen after it was still running
    at the cutoff, aged up to the cutoff only. Matters for an explicit
    past --as-of and for calls made when a cutoff resumes on a later day."""
    cutoff = as_of.isoformat()
    kept: list[dict[str, Any]] = []
    for creative in creatives:
        first, last = creative.get("first_seen"), creative.get("last_seen")
        if first and first > cutoff:
            continue
        if last and last > cutoff:
            span = _days(first, cutoff) if first else None
            served = creative.get("served_days")
            if isinstance(served, int) and isinstance(span, int):
                served = min(served, span)
            elif isinstance(span, int):
                served = span
            creative = {**creative, "last_seen": cutoff, "served_days": served, "running_at_capture": True}
        kept.append(creative)
    return kept


def longevity_status(creative: dict[str, Any], long_running_days: int) -> str:
    return MODEL.status(creative, long_running_days)


def deduplicate(creatives: list[dict[str, Any]], long_running_days: int) -> list[dict[str, Any]]:
    return MODEL.individual_ads(creatives, long_running_days)


def load_snapshots(runtime: Path, as_of: date) -> list[tuple[date, dict[str, Any]]]:
    """Snapshots stored at earlier cutoffs (`--refresh` runs), oldest first."""
    history = []
    for path in sorted((runtime / "snapshots").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cutoff = date.fromisoformat(data["as_of"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
        if cutoff < as_of and isinstance(data.get("creatives"), list):
            data["creatives"] = [c for c in data["creatives"] if isinstance(c, dict) and c.get("fingerprint") and c.get("creative_id")]
            history.append((cutoff, data))
    return history


def _complete_listing(listings: dict[str, Any], domain: str) -> bool:
    rows = (listings.get(domain) or {}).get("meta_us_rows")
    return isinstance(rows, int) and not isinstance(rows, bool) and 0 <= rows < META_ADS_PER_BRAND


def merge_snapshots(creatives: list[dict[str, Any]], history: list[tuple[date, dict[str, Any]]], as_of: date,
                    long_running_days: int, domains: list[str], listings: dict[str, Any]) -> list[dict[str, Any]]:
    """Fold earlier cutoffs into this one, claiming only what the samples prove.

    - Libraries that keep stopped ads listed (LinkedIn, Reddit) get a listing
      history (`first_listed`, `snapshot_sightings`), never an age or a
      running status.
    - A US Meta ad that was running at an earlier cutoff and is missing now
      has stopped (the US library lists active ads only), but only when this
      cutoff queried that competitor's Meta listing and both listings were
      complete (fewer rows than requested); a missing ad in a truncated sample
      may simply be outside it. It comes back once, as `vanished_after` the
      last cutoff that saw it.
    """
    if not history:
        return creatives
    seen_at: dict[tuple, list[date]] = {}
    for cutoff, snapshot in history:
        for record in snapshot["creatives"]:
            key = (record["domain"], record["platform"], record.get("native_ad_id") or record["creative_id"], record.get("country"))
            if cutoff not in seen_at.setdefault(key, []):
                seen_at[key].append(cutoff)
    current_ids = {c["creative_id"] for c in creatives}
    current_keys = set()
    for c in creatives:
        key = (c["domain"], c["platform"], c.get("native_ad_id") or c["creative_id"], c.get("country"))
        current_keys.add(key)
        dates = seen_at.get(key)
        if not dates:
            continue
        c["snapshot_sightings"] = len(dates) + 1
        c["first_listed"] = min(dates).isoformat()
        if c.get("source") in LISTS_STOPPED_ADS:
            continue  # listed is not delivered: no age, no running status
    vanished: dict[str, dict[str, Any]] = {}
    for cutoff, snapshot in history:
        for record in snapshot["creatives"]:
            domain = record["domain"]
            key = (domain, record["platform"], record.get("native_ad_id") or record["creative_id"], record.get("country"))
            if (record.get("source") != "meta_library_actor" or record.get("running_at_capture") is not True
                    or key in current_keys or record["creative_id"] in current_ids or domain not in domains
                    or not _complete_listing(listings, domain) or not _complete_listing(snapshot.get("listings") or {}, domain)):
                continue
            row = dict(record)
            last = max(seen_at[key]).isoformat()
            row.update(running_at_capture=False, vanished_after=last, snapshot_sightings=len(seen_at[key]),
                       last_observed=last)
            # Listing sightings never extend native delivery dates or duration.
            row["longevity_status"] = longevity_status(row, long_running_days)
            vanished[record["creative_id"]] = row  # the latest cutoff's record wins
    return creatives + [vanished[k] for k in sorted(vanished)]


def write_snapshot(runtime: Path, as_of: date, creatives: list[dict[str, Any]], listings: dict[str, Any], domains: list[str],
                   sources: list[str]) -> None:
    _write_atomic(runtime / "snapshots" / f"{as_of.isoformat()}.json",
                  json.dumps({"as_of": as_of.isoformat(), "domains": domains, "sources": sources, "listings": listings,
                              "creatives": creatives}, ensure_ascii=False))


def select_for_classification(creatives: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple, list] = {}
    for c in creatives:
        if c.get("relevance") == "irrelevant" or c.get("language_status") == "excluded":
            continue
        if c.get("headline") or c.get("body") or c.get("extra_texts") or c.get("image_url") or c.get("transcript") or c.get("media_analysis") or c.get("video_metadata"):
            groups.setdefault((c.get("country") or "", c.get("channel") or c.get("platform") or "unknown", c.get("creative_type")), []).append(c)
    for rows in groups.values():
        rows.sort(key=MODEL.strength_key)
    selected = []
    while groups:
        for key in sorted(list(groups), key=lambda k: (MODEL.strength_key(groups[k][0])[0], groups[k][0].get("channel_priority", 999), str(k))):
            selected.append(groups[key].pop(0))
            if not groups[key]:
                del groups[key]
    return selected


# ── classification ──────────────────────────────────────────────────────────

def classification_extra_texts(creative: dict) -> list[tuple[str, dict]]:
    origins = creative.get("extra_text_sources") or []
    extra = [(text, dict(origins[index]) if index < len(origins) and isinstance(origins[index], dict)
              else {"kind": "ad_text", "ref": creative["creative_id"]})
             for index, text in enumerate(creative.get("extra_texts") or []) if isinstance(text, str)]
    metadata = creative.get("video_metadata") or {}
    video_ref = f"youtube:{creative.get('youtube_video_id') or metadata.get('video_id') or creative['creative_id']}"
    for field in ("title", "description"):
        if isinstance(metadata.get(field), str) and metadata[field].strip():
            extra.append((metadata[field], {"kind": f"video_metadata_{field}", "ref": video_ref}))
    for frame in (creative.get("media_analysis") or {}).get("frames") or []:
        extra.extend((text, {"kind": "video_frame_ocr", "ref": frame.get("ref") or creative["creative_id"]})
                     for text in frame.get("visible_text") or [] if isinstance(text, str))
    return extra


def _classify_input(creative: dict[str, Any], frame_ref: str | None) -> dict[str, Any]:
    item: dict[str, Any] = {"ad_ref": creative["creative_id"], "platform": "google" if creative["platform"] == "youtube" else creative["platform"]}
    for key, cap in (("advertiser", 200), ("headline", 600), ("body", 4000), ("cta_label", 100), ("landing_url", 2000)):
        value = creative.get(key)
        if isinstance(value, str) and value.strip():
            item[key] = value[:cap]
    if isinstance(creative.get("transcript"), str) and creative["transcript"].strip():
        item["transcript"] = creative["transcript"][:8000]
    if isinstance(creative.get("video_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", creative["video_sha256"]):
        item["video_sha256"] = creative["video_sha256"]
    analysis = creative.get("media_analysis")
    if isinstance(analysis, dict) and analysis:
        derived = {
            "schema_version": 1, "derived": True, "truncated": False,
            "source": "media/analyze", "source_input_sha256": (creative.get("video_analysis_receipt") or {}).get("input_sha256"),
            "video_analysis_status": creative.get("video_analysis_status"),
            "frames": [{"ref": frame.get("ref"), "observations": frame.get("observations") or []}
                       for frame in analysis.get("frames") or [] if isinstance(frame, dict)],
            "sequence_summary": analysis.get("sequence_summary"),
            "visual_claims": [claim for claim in analysis.get("claims") or []
                              if isinstance(claim, dict) and claim.get("modality") == "visual"],
            "gaps": analysis.get("gaps") or [],
        }
        encoded = json.dumps(derived, ensure_ascii=False, sort_keys=True)
        if len(encoded) > 12000:
            # Keep the wire payload valid JSON; never silently slice a JSON
            # object or present derived descriptions as original ad words.
            wrapped = {"schema_version": 1, "derived": True, "truncated": True,
                       "source": "media/analyze", "original_chars": len(encoded),
                       "original_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
                       "observations_excerpt": encoded[:11000]}
            shortened = json.dumps(wrapped, ensure_ascii=False, sort_keys=True)
            while len(shortened) > 12000:
                wrapped["observations_excerpt"] = wrapped["observations_excerpt"][:max(0, len(wrapped["observations_excerpt"]) - (len(shortened) - 12000) - 1)]
                shortened = json.dumps(wrapped, ensure_ascii=False, sort_keys=True)
            encoded = shortened
        item["video_observations"] = encoded
    extra = classification_extra_texts(creative)
    if extra:
        item["extra_texts"] = [text[:4000] for text, _ in extra[:16]]
        item["extra_text_sources"] = [source for _, source in extra[:16]]
    item["country"] = creative.get("country")
    item["allowed_languages"] = creative.get("allowed_languages")
    if creative.get("format_kind"):
        item["format_hint"] = creative["format_kind"]
    if creative.get("cta_intent"):
        item["cta_hint"] = creative["cta_intent"]
    if frame_ref:
        item["frame_refs"] = [frame_ref]
    return item


def _label_key(item: dict[str, Any], image: dict[str, Any] | None, taxonomy_sha256: str, product_context: str, semantic_context: dict | None = None, source_content_sha256: str | None = None) -> str:
    """Per-creative cache key: the classification depends only on the ad's
    content, its image, the taxonomy and the product context."""
    content = {k: v for k, v in item.items() if k not in ("ad_ref", "frame_refs")}
    value = {"kind": "creative_label", "classification_contract": 4, "taxonomy_sha256": taxonomy_sha256, "context_sha256": hashlib.sha256(product_context.encode("utf-8")).hexdigest(),
             "semantic_context": semantic_context, "source_content_sha256": source_content_sha256,
             "content": content, "image_sha256": image["sha256"] if image else None}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def classification_source_hash(creative: dict) -> str:
    return POLICY.canonical_hash({name: creative.get(name) for name in (
        "headline", "body", "extra_texts", "extra_text_sources", "transcript", "video_metadata", "media_analysis", "video_sha256")})


def classify_corpus(client: OsClient, creatives: list[dict[str, Any]], taxonomy: dict[str, Any], taxonomy_sha256: str,
                    product_context: str, coverage: list[dict[str, Any]], cached_only: list[dict[str, Any]] = ()) -> list[dict[str, Any]]:
    """Labels for `creatives` (cached per creative, new ones in batches) and,
    from the cache only, for `cached_only` (ads that stopped since an earlier
    cutoff were classified then)."""
    images: dict[str, dict[str, Any]] = {}
    deferred: dict[str, set[str]] = {}
    for creative in [*creatives, *cached_only]:
        url = creative.get("image_url")
        if isinstance(url, str) and url.startswith("https://"):
            image = client.fetch_image(url)
            if image and image.get("transient"):
                # Classifying it text-only now would cache a weaker label; it waits for the image.
                deferred.setdefault(creative["domain"], set()).add(creative["creative_id"])
            elif image:
                images[creative["creative_id"]] = image
    for domain, ids in sorted(deferred.items()):
        CF._coverage_gap(coverage, "classify", [domain], f"{len(ids)} image(s) could not be downloaded now; those creatives are classified on the next attempt")

    def frame_ref(creative: dict[str, Any]) -> str:
        return f"frames/{creative['creative_id'].replace(':', '-')}.img"

    labels: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    pending: list[tuple[dict[str, Any], str]] = []
    allowed_new = {c["creative_id"] for c in creatives}
    for creative in [*creatives, *cached_only]:
        cid = creative["creative_id"]
        if cid in labels or any(cid in ids for ids in deferred.values()):
            continue
        has_image = cid in images
        analyzed_frame_text = any(frame.get("visible_text") for frame in (creative.get("media_analysis") or {}).get("frames") or [])
        if not has_image and not (creative.get("headline") or creative.get("body") or creative.get("extra_texts")
                                  or creative.get("transcript") or analyzed_frame_text
                                  or (creative.get("video_metadata") or {}).get("title")
                                  or (creative.get("video_metadata") or {}).get("description")):
            continue
        item = _classify_input(creative, frame_ref(creative) if has_image else None)
        source_sha = classification_source_hash(creative)
        creative["classification_source_sha256"] = source_sha
        limits = []
        for name, maximum in (("headline", 600), ("body", 4000), ("transcript", 8000)):
            if len(creative.get(name) or "") > maximum:
                limits.append(f"{name}: first {maximum} characters supplied to classification")
        extra = classification_extra_texts(creative)
        if len(extra) > 16 or any(len(text) > 4000 for text, _ in extra):
            limits.append("extra texts (native copy, video metadata and OCR): at most 16 sources, 4000 characters each supplied to classification")
        if item.get("video_observations") and json.loads(item["video_observations"]).get("truncated"):
            limits.append("derived video observations: bounded JSON excerpt supplied to classification")
        if limits:
            creative["classification_input_limits"] = limits
            coverage.append({"type": "coverage", "creative_id": cid, "domain": creative["domain"], "country": creative.get("country"), "channel": creative["channel"], "source": "classify", "status": "truncated_input", "detail": "; ".join(limits) + "; full source content retained in evidence", "tier": "C"})
        key = _label_key(item, images.get(cid), taxonomy_sha256, product_context, client.semantic_context, source_sha)
        cached = client._cache_read(client._shared() / f"{key}.json")
        if cached is not None and isinstance(cached.get("response"), dict):
            client.cache_hits += 1
            # The answer came from one batch call: the ledger counts that call
            # (and its tokens) on every replay, so receipts stay byte-stable.
            if isinstance(cached.get("batch"), str):
                client.touched.add(cached["batch"])
            if cached["response"].get("unavailable"):
                coverage.append({"type": "coverage", "creative_id": cid, "domain": creative["domain"], "channel": creative["channel"], "country": creative.get("country"), "source": "classify", "status": "rejected", "detail": cached["response"]["unavailable"], "tier": "C"})
                continue
            labels[cid] = (cached["response"], cached.get("meta") or {})
        elif cid in allowed_new and not any(cid == c["creative_id"] for c, _ in pending):
            pending.append((creative, key))

    text_only = [(c, k) for c, k in pending if c["creative_id"] not in images]
    with_frames = [(c, k) for c, k in pending if c["creative_id"] in images]
    def content_batches(entries, maximum):
        batch, text_chars = [], 0
        # Rich semantics and complete OCR require more response room than the
        # legacy labels. Long speech/text ads are classified individually.
        maximum = min(maximum, 4) if client.semantic_context is not None else maximum
        for creative, key in entries:
            item = _classify_input(creative, None)
            cost = sum(len(item.get(name) or "") for name in ("headline", "body", "transcript")) + sum(len(t) for t in item.get("extra_texts") or [])
            if batch and (len(batch) >= maximum or text_chars + cost > 12000):
                yield batch
                batch, text_chars = [], 0
            batch.append((creative, key))
            text_chars += cost
        if batch:
            yield batch
    batches = list(content_batches(text_only, TEXT_BATCH)) + list(content_batches(with_frames, IMAGE_BATCH))
    failures = 0
    for batch_position, batch in enumerate(batches):
        frames = {frame_ref(c): images[c["creative_id"]] for c, _ in batch if c["creative_id"] in images}
        request = {"schema_version": 1, "taxonomy_version": taxonomy["taxonomy_version"], "product_context": product_context or None,
                   "creatives": [_classify_input(c, frame_ref(c) if c["creative_id"] in images else None) for c, _ in batch]}
        if client.semantic_context is not None:
            # Existing paid labels anchor canonical meanings for later batches.
            # The stable per-ad key binds the offer/language policy; each batch
            # receipt also binds the actual (possibly expanded) anchor context.
            prior_rows = [{**item, "ad_ref": cid} for cid, (item, _) in labels.items()]
            prior_by_id = {row["creative_id"]: row for row in [*creatives, *cached_only]}
            prior_labels = [copy.deepcopy({**row, "creative_id": row["ad_ref"], "with_image": row["ad_ref"] in images}) for row in prior_rows if row.get("ad_ref") in prior_by_id]
            prior_creatives = [copy.deepcopy(prior_by_id[row["creative_id"]]) for row in prior_labels]
            dictionary = SEMANTICS.apply_semantics(prior_creatives, prior_labels, client.semantic_context)
            original_counts = {field: len(dictionary[field]) for field in ("angles", "message_families")}
            for field in original_counts:
                dictionary[field] = sorted(dictionary[field], key=lambda row: (-len(row.get("members") or []), row["key"]))[:320]
            # Full observations remain in the final dictionary. Request anchors
            # obey the bounded public inference context, with visible coverage.
            while len(json.dumps(dictionary, ensure_ascii=False)) > 220000 and any(dictionary[field] for field in original_counts):
                field = max(original_counts, key=lambda name: len(json.dumps(dictionary[name], ensure_ascii=False)))
                dictionary[field].pop()
            if any(len(dictionary[field]) < original_counts[field] for field in original_counts):
                coverage.append({"type": "coverage", "source": "semantic_context", "status": "bounded_anchors", "detail": f"Request canonical anchors bounded from {original_counts}; full observations remain in output dictionary", "tier": "C"})
            request["semantic_context"] = SEMANTICS.build_semantic_context(product_context, client.semantic_context["allowed_languages"], dictionary)
        try:
            response, retrieved_on, batch_digest = client.classify(request, frames, taxonomy_sha256)
        except BudgetExhausted as exc:
            if "cumulative" not in str(exc):
                raise
            for creative, _ in [entry for remaining in batches[batch_position:] for entry in remaining]:
                coverage.append({"type": "coverage", "creative_id": creative["creative_id"], "domain": creative["domain"], "channel": creative["channel"],
                                 "country": creative.get("country"), "source": "classify", "status": "budget_deferred",
                                 "detail": str(exc), "tier": "C"})
            break
        except CreativePatternsError as exc:
            if not isinstance(exc, SourceUnavailable) and re.search(r"HTTP (?:404|405|409|503)\b", str(exc)):
                # The endpoint is not deployed, not configured or on another taxonomy: no batch can succeed.
                raise CreativePatternsError(f"creative classification is unavailable: {CF._provider_detail(exc)}") from exc
            if isinstance(exc, CF.OsUnreachable) or (not isinstance(exc, SourceUnavailable) and STOP_CLASSIFYING_RE.search(str(exc))):
                # Not about this batch: the OS is unreachable, the key is
                # refused, rate-limited or out of LLM budget, so later batches
                # would fail the same way. Recording gaps would complete the
                # section with creatives unlabelled; failing the attempt lets
                # a rerun continue from the cached answers.
                raise type(exc)(f"creative classification stopped: {CF._provider_detail(exc)}; rerun later to continue "
                                f"({len(labels)} label(s) so far are cached)") from exc
            failures += 1
            if isinstance(exc, SourceUnavailable) and getattr(exc, "batch_digest", None):
                for creative, key in batch:
                    client._cache_write(client._shared() / f"{key}.json", {"kind": "creative_label", "response": {"unavailable": str(exc)}, "batch": exc.batch_digest})
            CF._coverage_gap(coverage, "classify", sorted({c["domain"] for c, _ in batch}), f"a classification batch failed: {CF._provider_detail(exc)}")
            continue
        meta = {"taxonomy_version": response.get("taxonomy_version"), "taxonomy_sha256": response.get("taxonomy_sha256") or taxonomy_sha256,
                "model_role": response.get("model_role"), "effective_model": response.get("effective_model"), "classified_on": retrieved_on,
                "classification_request_context_sha256": (request.get("semantic_context") or {}).get("context_sha256")}
        by_ref = {c["creative_id"]: (c, k) for c, k in batch}
        for item in response.get("classifications") or []:
            if not isinstance(item, dict) or item.get("ad_ref") not in by_ref:
                continue
            creative, key = by_ref[item["ad_ref"]]
            labels[creative["creative_id"]] = (item, meta)
            client._cache_write(client._shared() / f"{key}.json", {"kind": "creative_label", "response": item, "meta": meta,
                                                                   "batch": batch_digest, "retrieved_on": retrieved_on})
    if batches and failures == len(batches) and not labels:
        raise CreativePatternsError("every creative classification batch failed; rerun later (no spend is lost: answers are cached)")
    if deferred and not labels:
        raise CreativePatternsError("transient image failures left no usable creative classifications; rerun later to continue from the cache")

    rows: list[dict[str, Any]] = []
    for creative in [*creatives, *cached_only]:
        if creative["creative_id"] not in labels or any(r["creative_id"] == creative["creative_id"] for r in rows):
            continue
        item, meta = labels[creative["creative_id"]]
        rows.append({
            "type": "creative_classification",
            "creative_id": creative["creative_id"],
            "domain": creative["domain"],
            "platform": creative["platform"],
            "channel": creative["channel"],
            "fingerprint": creative["fingerprint"],
            "semantics": item.get("semantics") or {},
            "classification_request_context_sha256": meta.get("classification_request_context_sha256"),
            "classification_source_sha256": creative.get("classification_source_sha256"),
            "classification_input_limits": creative.get("classification_input_limits") or [],
            "observed_text": item.get("observed_text"),
            "observed_text_source": item.get("observed_text_source"),
            "observed_text_sources": item.get("observed_text_sources") or [],
            "texts_sources": item.get("texts_sources") or {},
            "observed_text_frame_refs": item.get("observed_text_frame_refs") or [],
            "country": creative.get("country"),
            "creative_type": creative.get("creative_type"),
            "format_kind": creative.get("format_kind"),
            "labels": item.get("labels") or {},
            "texts": item.get("texts") or {},
            "offer": item.get("offer") or {},
            "confidence": item.get("confidence"),
            "coerced": item.get("coerced") or [],
            "with_image": creative["creative_id"] in images,
            "with_video_frames": False,
            "with_analyzed_video_frames": bool(creative.get("video_frames")),
            "video_analysis_ref": (creative.get("video_analysis_receipt") or {}).get("input_sha256"),
            "input_text_sources": _classify_input(creative, None).get("extra_text_sources") or [],
            "taxonomy_version": meta.get("taxonomy_version"),
            "taxonomy_sha256": meta.get("taxonomy_sha256") or taxonomy_sha256,
            "model_role": meta.get("model_role"),
            "effective_model": meta.get("effective_model"),
            "classified_on": meta.get("classified_on"),
            "market_scope": creative["market_scope"],
            "tier": "C",
        })
    return rows


# ── patterns ────────────────────────────────────────────────────────────────

def score_patterns(creatives: list[dict[str, Any]], classifications: list[dict[str, Any]], taxonomy: dict[str, Any], long_running_days: int, dictionary: dict | None = None) -> list[dict[str, Any]]:
    return MODEL.patterns(creatives, classifications, taxonomy, long_running_days, dictionary)


def price_anchors(creatives: list[dict[str, Any]], classifications: list[dict] | None = None) -> list[dict[str, Any]]:
    return MODEL.promises(creatives, classifications)


def _cell(value: Any, cap: int = 110) -> str:
    return CF._cell(value, cap)


def _label(value: Any) -> str:
    return str(value).replace("_", " ") if value not in (None, "") else "—"


def render_section(*, domains: list[str], creatives: list[dict[str, Any]], classifications: list[dict[str, Any]],
                   patterns: list[dict[str, Any]], anchors: list[dict[str, Any]], coverage: list[dict[str, Any]],
                   totals: dict[str, Any], as_of: str, retrieved_on: str, long_running_days: int, taxonomy_version: str, selection: dict | None = None) -> str:
    body = MODEL.section(creatives, patterns, anchors, coverage, long_running_days, selection)
    spend = (f"\nClassified {len(classifications)} of {len(creatives)} individual ads; "
             f"{totals['classify_calls']} classification calls and {totals['classify_prompt_tokens']} prompt tokens; "
             f"{totals.get('media_calls', 0)} media calls and {totals.get('media_prompt_tokens', 0)} media prompt tokens. "
             f"Cumulative paid starts: {totals.get('cumulative_paid_starts', 0)}/{totals.get('cumulative_paid_start_limit')}; "
             f"these are resource counts, not a currency estimate. "
             f"Cutoff {as_of}; sources retrieved {retrieved_on}; taxonomy {taxonomy_version}.\n")
    return body + spend


# ── orchestration ───────────────────────────────────────────────────────────

def frozen_semantic_context(client: OsClient, inputs: RunInputs) -> dict:
    # Freeze anchors across compatible cutoffs. A dictionary learned during a
    # run must not change the key of already-paid labels on the next refresh.
    base = SEMANTICS.build_semantic_context(inputs.product_context, inputs.languages)
    base_sha = POLICY.canonical_hash({"context": base, "market_languages": inputs.market_languages})
    shared = client._shared() / "semantic-context.json"
    snapshot = client.cache_dir / "semantic-context.json"
    for path in (snapshot, shared):
        previous = client._cache_read(path)
        if previous and previous.get("base_sha256") == base_sha:
            _write_atomic(snapshot, json.dumps(previous, ensure_ascii=False))
            return previous["context"]
    record = {"base_sha256": base_sha, "context": base}
    _write_atomic(shared, json.dumps(record, ensure_ascii=False))
    _write_atomic(snapshot, json.dumps(record, ensure_ascii=False))
    return base


def language_inputs(workspace: Path, args: argparse.Namespace, countries: list[str] | None = None) -> tuple[list[str], dict]:
    intake = CF.typed_intake(workspace)
    raw = str(_arg(args, "languages", "") or "")
    market = str(_arg(args, "market_languages", "") or "")
    languages = ([code.strip().lower() for code in raw.split(",") if code.strip()]
                 if raw else list(intake.get("languages") or []))
    by_market = {} if raw or market else dict(intake.get("market_languages") or {})
    for entry in market.split(";"):
        if not entry.strip():
            continue
        if ":" not in entry:
            raise CreativePatternsError("market languages must use COUNTRY:language,language entries")
        country, codes = entry.split(":", 1)
        country = country.strip().upper().replace("UK", "GB")
        if not re.fullmatch(r"[A-Z]{2}", country):
            raise CreativePatternsError("market language country must be an ISO code")
        by_market[country] = [code.strip().lower() for code in codes.split(",") if code.strip()]
        if not by_market[country]:
            raise CreativePatternsError("market languages cannot be empty")
    if by_market:
        for country in countries or []:
            if country not in by_market:
                if not languages:
                    raise CreativePatternsError(f"accepted languages are missing for market {country}; set a global list or that market explicitly")
                by_market[country] = list(languages)
    languages = sorted(set(languages + [c for values in by_market.values() for c in values]))
    SEMANTICS.build_semantic_context("", languages)
    return languages, by_market


def full_product_context(workspace: Path) -> str:
    text = CF.IO.context_text(workspace, SECTION_ID)
    intake = CF.typed_intake(workspace)
    offer = {key: value for key, value in (intake.get("offer") or {}).items()
             if value not in (None, "", [])}
    if offer:
        text += "\n\nOffer card:\n" + json.dumps(offer, ensure_ascii=False)
    if len(text) > PRODUCT_CONTEXT_CHARS:
        raise CreativePatternsError("offer context exceeds 24000 characters; provide a bounded offer card rather than silently truncating it")
    return text


def hydrate_footprint_media(creatives: list[dict], inputs: RunInputs, taxonomy: dict) -> None:
    if inputs.runtime is None:
        return
    by_native = {}
    for c in creatives:
        by_native.setdefault(c["native_ad_id"], []).append(c)
    for path in CF.IO.cache_entries(inputs.runtime.parent / "channel_footprint/cache"):
        try:
            entry = CF.IO.read_cache_entry(path)
        except (ValueError, OSError, EOFError):
            continue
        if not isinstance(entry, dict):
            continue
        captured = entry.get("cutoff") or entry.get("retrieved_on")
        if isinstance(captured, str) and captured[:10] > inputs.as_of.isoformat():
            continue  # Future media must not enrich a historical cutoff.
        response = entry.get("response") or {}
        rows = response.get("rows") or response.get("data") or []
        if not isinstance(rows, list):
            continue
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            native = str(raw.get("ad_archive_id") or raw.get("creativeId") or raw.get("adId") or raw.get("id") or "")
            for c in by_native.get(native, []):
                if c["platform"] == "meta" and raw.get("snapshot"):
                    recovered = _meta_actor_creative(raw, c["domain"], CF.brand_token(c["domain"]), inputs.as_of,
                                                    entry.get("retrieved_on") or inputs.as_of.isoformat(), taxonomy)
                    if recovered:
                        for field in ("headline", "body", "extra_texts", "image_url", "video_url", "media_urls", "media_cards", "format_raw", "format_kind"):
                            if recovered.get(field):
                                c[field] = recovered[field]
                        c["creative_type"] = MODEL.creative_type(c)
                elif c["platform"] in ("google", "youtube"):
                    for field, native_field in (("image_url", "imageUrl"), ("video_url", "videoUrl"), ("link", "adUrl")):
                        if raw.get(native_field):
                            c[field] = raw[native_field]


def footprint_coverage(inputs: RunInputs, creatives: list[dict]) -> list[dict]:
    document = inputs.footprint or {}
    countries = document.get("inputs", {}).get("target_countries") or [None]
    rows = []
    for rank in document.get("rows", []):
        if rank.get("type") != "channel_observation":
            continue
        channel = rank.get("channel") or rank.get("platform")
        if not channel:
            continue
        for country in [rank["country"]] if rank.get("country") else countries:
            if inputs.deepened_cells is not None and (country, channel) not in inputs.deepened_cells:
                rows.extend({"type": "coverage", "domain": domain, "country": country, "channel": channel, "source": "channel_footprint",
                             "status": "not_deepened", "detail": f"Bounded scope inspects the first {inputs.max_channels} observed channel(s) in stable name order "
                             "per market; use --max-channels 0 for every cell.", "rank": rank.get("rank"), "tier": "C"}
                            for domain in inputs.domains)
                continue
            for domain in inputs.domains:
                items = [c for c in creatives if c["channel"] == channel and c["domain"] == domain and c.get("country") == country]
                gaps = [g for g in document.get("rows", []) if g.get("type") == "coverage" and g.get("domain") == domain
                        and (g.get("channel") or g.get("platform")) == channel and g.get("country") in (country, None)]
                rows.append({"type": "coverage", "domain": domain, "country": country, "channel": channel,
                             "source": "channel_footprint", "status": "extracted" if items else "not_extracted",
                             "detail": f"{len(items)} native ads in available sample; not a census" if items else
                             "; ".join(str(g.get("detail") or g.get("reason") or g.get("status")) for g in gaps) or "No extractable ads in completed Footprint; channel presence retained",
                             "rank": rank.get("rank"), "tier": "C"})
    return rows


def prepare_media(client: OsClient, creatives: list[dict], inputs: RunInputs, config: dict, coverage: list[dict], *, analyze_videos: bool = True) -> None:
    selected_videos: dict[tuple, dict[str, str]] = {}
    for c in sorted(creatives, key=MODEL.strength_key):
        c["allowed_languages"] = inputs.market_languages.get(c.get("country"), inputs.languages)
        urls = [c.get("image_url")] + list(c.get("media_urls") or [])
        for url in dict.fromkeys(urls):
            if not isinstance(url, str) or not url.startswith("https://"):
                continue
            image = client.fetch_image(url)
            if image and image.get("file") and inputs.runtime:
                workspace = VIDEO._workspace(inputs.runtime)
                path = client._shared() / "images" / image["file"]
                if path.is_relative_to(workspace):
                    asset = {"path": path.relative_to(workspace).as_posix(), "kind": "preview" if c["creative_type"] == "video" else "image", "sha256": image["sha256"]}
                    if asset not in c.setdefault("media_assets", []):
                        c["media_assets"].append(asset)
        if c["creative_type"] != "video" or inputs.runtime is None or not analyze_videos:
            continue
        key = (c["domain"], c["channel"], c.get("country"))
        # A market observation or second native ad is not a new video. Prefer
        # actual bytes, then exact provider video ID, before native-ad fallback.
        content_id = c.get("video_sha256") or c.get("youtube_video_id") or VIDEO.youtube_id(c.get("video_id")) \
            or VIDEO.youtube_id(c.get("video_url")) or VIDEO.youtube_id(c.get("link")) \
            or c.get("video_url") or c.get("native_ad_id") or c["creative_id"]
        content_id = str(content_id)
        selected = selected_videos.setdefault(key, {})
        excluded = c.get("relevance") == "irrelevant" or c.get("language_status") == "excluded"
        if excluded or (content_id not in selected and len(set(selected.values())) >= inputs.top_videos):
            c["video_analysis_status"] = "not_selected"
            c.setdefault("video_gaps", []).append("Irrelevant or excluded-language video" if excluded else "Beyond configured top-N unique videos")
        else:
            selected.setdefault(content_id, content_id)
            try:
                c.update(VIDEO.preserve_video_media(c, inputs.runtime, config, client=client))
                c.update(VIDEO.analyze_video(client, c, inputs.runtime, config))
                # Resolved IDs/hashes let subsequent ads reuse this video's
                # shared paid receipts, including after the cell reached N.
                if c.get("video_sha256") or c.get("youtube_video_id"):
                    resolved_id = str(c.get("video_sha256") or c["youtube_video_id"])
                    previous_id = selected[content_id]
                    for alias in list(selected):
                        if selected[alias] == previous_id:
                            selected[alias] = resolved_id
                    selected[resolved_id] = resolved_id
            except BudgetExhausted as exc:
                c["video_analysis_status"] = "budget_deferred"
                c.setdefault("video_gaps", []).append(str(exc))
        if c.get("video_gaps"):
            coverage.append({"type": "coverage", "domain": c["domain"], "channel": c["channel"], "country": c.get("country"),
                             "source": "video_analysis", "status": c.get("video_analysis_status") or "unavailable", "detail": "; ".join(c["video_gaps"]), "tier": "C"})


def footprint_input(workspace: Path, policy: dict[str, Any], policy_sha256: str) -> dict[str, Any] | None:
    """A v2 footprint is an owned input, never an unverified optional hint."""
    path = workspace / CHANNEL_FOOTPRINT_EVIDENCE_REL
    if not path.is_file():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 2:
        raise CreativePatternsError("Channel Footprint must be refreshed to its scoped v2 contract before Creative Patterns")
    reader = _load_script("research-evidence.py", "pmr_cf_inputs_for_creative_patterns")
    result = reader.inspect_section(workspace, "channel_footprint")
    if result.get("status") != "completed":
        raise CreativePatternsError("Channel Footprint input is pending, stale or unverified: " + str(result.get("reason") or result.get("status")))
    inputs = document.get("inputs") or {}
    if inputs.get("effective_policy") != policy or inputs.get("policy_sha256") != policy_sha256:
        raise CreativePatternsError("Channel Footprint evidence policy changed; finalize it with the current shared taxonomy before Creative Patterns")
    return document


def footprint_creatives(document: dict[str, Any], as_of: date, taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    """Reuse decided ads with per-market lineage, without re-admitting unrelated ads."""
    context = (document.get("inputs") or {}).get("competitor_context") or {}
    policy, _ = POLICY.policy_from_taxonomy(taxonomy)
    selected_countries = set((document.get("inputs") or {}).get("target_countries") or [])
    result = []
    platforms = {"google_ads": "google", "youtube_ads": "youtube", "meta_ads": "meta", "linkedin_ads": "linkedin", "reddit_ads": "reddit", "tiktok_ads": "tiktok", "display_native": "google"}
    for ad in document.get("rows") or []:
        if ad.get("type") != "channel_ad":
            continue
        base_channel = ad.get("channel") or ad.get("platform")
        if base_channel not in platforms:
            continue
        domain_context = context.get(ad.get("domain"), {}) if isinstance(context, dict) else {}
        role = ad.get("competitor_tier") or (domain_context.get("competitor_tier") if isinstance(domain_context, dict) else None) or "unknown"
        for observation in ad.get("observations") or []:
            channel = base_channel
            if channel == "google_ads":
                placement = str(observation.get("placement") or "").lower()
                if placement in {"youtube", "youtube_ads"}:
                    channel = "youtube_ads"
                elif placement in {"display", "display_ads", "display_native"}:
                    channel = "display_native"
            platform = platforms.get(channel, str(channel).removesuffix("_ads"))
            country = observation.get("country")
            if country and country not in selected_countries:
                continue
            native_date_scope = observation.get("date_scope") or "unknown"
            date_country = observation.get("date_country")
            date_scope = native_date_scope
            if date_scope == "country" and (not country or date_country != country):
                date_scope = "unknown"
            first = observation.get("first_shown")
            last = observation.get("last_shown")
            activity = observation.get("activity_status", observation.get("status"))
            activity_scope = observation.get("activity_scope") or "unknown"
            activity_country = observation.get("activity_country")
            # Activity observed in this country's query (global provider flag) or
            # native country activity both establish current use in the market.
            same_activity_country = bool(country and activity_scope in ("country", "global") and activity_country == country)
            capture = observation.get("observed_on") or observation.get("last_observed") or document.get("retrieved_on") or as_of.isoformat()
            capture = str(capture).split("..")[-1][:10]
            running = (True if activity == "active" else
                       False if activity in ("stopped", "inactive", "ended", "archived") else None) if same_activity_country else None
            same_delivery_scope = ((date_scope == "global" and activity_scope == "global")
                                   or (date_scope == "country" and activity_scope == "country" and same_activity_country))
            counted_last = last
            if activity == "active" and same_activity_country and same_delivery_scope and first and (not last or str(last)[:10] > capture):
                # Counted through the footprint capture, as Channel Footprint
                # does: a later section cannot extend delivery because time
                # elapsed, and a scheduled future end adds no days.
                counted_last = capture
                last = last or capture
            # Listing observations deliberately have no delivery age or flag.
            served = _days(first, counted_last) if first and counted_last and date_scope in ("country", "global") else None
            if date_scope in ("country", "global") and counted_last and str(counted_last)[:10] > capture:
                served = None  # Future delivery is not historical proof at source capture.
            native_id = str(ad.get("native_ad_id") or ad.get("ad_id"))
            scope_key = country or "global"
            identity = f"{native_id}:{channel}:{scope_key}:{date_scope}"
            creative = _creative(
                domain=ad["domain"], platform=platform, source=str(observation.get("source") or ad.get("source") or "channel_footprint"),
                ad_id=identity, advertiser=ad.get("advertiser"), headline=ad.get("headline"), body=ad.get("ad_text"),
                landing_url=ad.get("landing_url"), format_raw=str(ad.get("format") or "unknown").upper(), image_url=ad.get("image_url"),
                first_seen=first, last_seen=last, served_days=served, running=running,
                age_basis="platform_dates" if served is not None else "none", market_scope=observation.get("market_scope") or "global",
                verified_by=ad.get("verified_by") or "channel_footprint_identity", link=ad.get("source_url"), taxonomy=_google_taxonomy(taxonomy, platform),
                extra={"country": country, "countries": [country] if country else [], "competitor_tier": role,
                       "relevance": ad.get("relevance") or "unknown", "relevance_reason": ad.get("relevance_reason"), "duration_scope": date_scope,
                       "video_url": ad.get("video_url"), "media_urls": ad.get("media_urls") or [],
                       "media_cards": ad.get("media_cards") or [], "format_kind": _alias(_google_taxonomy(taxonomy, platform), "format_kind", platform, str(ad.get("format") or "unknown").upper()),
                       "footprint_ad_id": ad.get("ad_id"), "native_ad_id": native_id, "channel": channel,
                       "first_observed": observation.get("first_observed"), "last_observed": observation.get("last_observed"),
                       "retrieved_on": capture,
                       "date_scope": native_date_scope, "date_country": date_country,
                       "activity_scope": activity_scope, "activity_country": activity_country,
                       "native_activity_status": activity, "placement": observation.get("placement")},
            )
            creative["source_members"] = [{k: creative.get(k) for k in (
                "creative_id", "domain", "country", "countries", "channel", "competitor_tier", "relevance", "duration_scope",
                "footprint_ad_id", "native_ad_id", "served_days", "running_at_capture", "first_seen", "last_seen",
                "date_scope", "date_country", "activity_scope", "activity_country", "native_activity_status", "placement") }]
            result.append(creative)
    return result


@dataclass
class RunInputs:
    domains: list[str]
    domain_sources: dict[str, str]
    product_domain: str
    sources: list[str]
    country: str
    eu_country: str
    as_of: date
    long_running_days: int
    product_context: str
    linkedin_slugs: dict[str, str] = field(default_factory=dict)
    runtime: Path | None = None
    footprint: dict[str, Any] | None = None
    effective_policy: dict[str, Any] = field(default_factory=dict)
    policy_sha256: str = ""
    restrict_sources: bool = False
    languages: list[str] = field(default_factory=list)
    market_languages: dict[str, list[str]] = field(default_factory=dict)
    top_videos: int = 5
    max_channels: int = 0  # express scope: deepen this many candidate channels per market; 0 keeps every cell
    deepened_cells: set[tuple[str | None, str]] | None = None


def candidate_cells(footprint: dict[str, Any], max_channels: int) -> set[tuple[str | None, str]] | None:
    """Bound an inspection sample by stable channel name, not business merit.
    None means every observed comparable cell is deepened."""
    if not max_channels:
        return None
    rows = footprint.get("rows") or []
    channel = lambda row: row.get("channel") or row.get("platform")  # Footprint presence rows name it `platform`
    current = {(r.get("country"), channel(r)) for r in rows if r.get("type") == "library_presence"
               and r.get("relevance") == "relevant" and channel(r)}
    ranks = {(r.get("country"), channel(r)): r.get("rank", 999) for r in rows if r.get("type") == "channel_observation"}
    cells: set[tuple[str | None, str]] = set()
    for country in {country for country, _ in current}:
        channels = sorted((name for market, name in current if market == country), key=str)
        cells.update((country, channel) for channel in channels[:max_channels])
    return cells


def run_pipeline(client: OsClient, inputs: RunInputs, config: dict[str, Any], taxonomy: dict[str, Any], taxonomy_sha256: str) -> dict[str, Any]:
    actors = config["actors"]
    coverage: list[dict[str, Any]] = []
    raw: list[dict[str, Any]] = []
    listings: dict[str, Any] = {}
    def partial_source(source, domains, fn):
        try:
            return CF._attempt(client, coverage, source, domains, fn)
        except BudgetExhausted as exc:
            if "cumulative" not in str(exc):
                raise
            for domain in domains:
                coverage.append({"type": "coverage", "domain": domain, "source": source, "status": "budget_deferred", "detail": str(exc), "tier": "C"})
            return None
    if inputs.footprint is not None:
        raw = [c for c in footprint_creatives(inputs.footprint, inputs.as_of, taxonomy) if c["domain"] in inputs.domains]
        inputs.deepened_cells = candidate_cells(inputs.footprint, inputs.max_channels)
        if inputs.deepened_cells is not None:
            raw = [c for c in raw if (c.get("country"), c["channel"]) in inputs.deepened_cells]
        if inputs.restrict_sources:
            families = {"google_ads": "google_transparency", "youtube_ads": "google_transparency", "display_native": "google_transparency",
                        "meta_ads": "meta", "linkedin_ads": "linkedin", "reddit_ads": "reddit"}
            raw = [c for c in raw if families.get(c["channel"]) in inputs.sources]
        hydrate_footprint_media(raw, inputs, taxonomy)
    else:
        if "google_transparency" in inputs.sources:
            for domain in inputs.domains:
                found = partial_source("google_transparency", [domain], lambda d=domain: collect_google_transparency(client, actors["google_ads"], [d], inputs.as_of, taxonomy, coverage))
                raw.extend(found or [])
        for domain in inputs.domains:
            if "meta" in inputs.sources:
                found = partial_source("meta", [domain], lambda d=domain: collect_meta(client, actors["meta_ads"], d, inputs.as_of, inputs.eu_country, taxonomy))
                if found:
                    meta_rows, us_rows = found
                    raw.extend(meta_rows)
                    listings[domain] = {"meta_us_rows": us_rows}
            if "google_search" in inputs.sources:
                found = partial_source("google_search", [domain], lambda d=domain: collect_google_search(client, d, inputs.country, inputs.as_of, taxonomy))
                raw.extend(found or [])
            if "linkedin" in inputs.sources:
                found = partial_source("linkedin", [domain], lambda d=domain: collect_linkedin(client, actors["linkedin_ads"], d, inputs.linkedin_slugs.get(d), taxonomy))
                raw.extend(found or [])
            if "reddit" in inputs.sources:
                found = partial_source("reddit", [domain], lambda d=domain: collect_reddit(client, actors["reddit_ads"], d, taxonomy))
                raw.extend(found or [])
            # Meta (and Reddit) media URLs are signed and expire within days:
            # download this competitor's images now, not after every collector.
            for creative in raw:
                if creative["domain"] != domain:
                    continue
                if isinstance(creative.get("image_url"), str) and creative["image_url"].startswith("https://"):
                    client.fetch_image(creative["image_url"])

    coverage.extend(client.budget_gaps)

    raw = cap_at_cutoff(raw, inputs.as_of)
    creatives = deduplicate(raw, inputs.long_running_days)
    # Native identity and scope were reconciled above; copy never defines identity.
    by_id: dict[str, dict[str, Any]] = {}
    for c in sorted(creatives, key=MODEL.strength_key):
        by_id.setdefault(c["creative_id"], c)
    creatives = list(by_id.values())
    if inputs.runtime is not None and inputs.footprint is None:
        # Earlier cutoffs only; the corpus of this cutoff is written below.
        creatives = merge_snapshots(creatives, load_snapshots(inputs.runtime, inputs.as_of), inputs.as_of, inputs.long_running_days,
                                    inputs.domains, listings)
    creatives.sort(key=lambda c: (c["domain"], c["platform"], c["creative_id"]))
    stored = creatives
    if inputs.footprint is not None:
        coverage.extend(footprint_coverage(inputs, stored))
    else:
        for domain in inputs.domains:
            for source in inputs.sources:
                if not any(c["domain"] == domain and c["source"] in SOURCE_ROW_SOURCES[source] for c in raw):
                    coverage.append({"type": "coverage", "domain": domain, "source": source, "status": "no_data", "detail": "no verified creative", "tier": "C"})
    # Copy/preview classification establishes exclusions before large downloads.
    prepare_media(client, stored, inputs, config, coverage, analyze_videos=False)
    client.semantic_context = frozen_semantic_context(client, inputs)
    selected = select_for_classification([c for c in stored if not c.get("vanished_after")])
    stopped_rows = [c for c in stored if c.get("vanished_after")]
    classifications = classify_corpus(client, selected, taxonomy, taxonomy_sha256, inputs.product_context, coverage,
                                      cached_only=stopped_rows) if (selected or stopped_rows) else []
    SEMANTICS.apply_semantics(stored, classifications, client.semantic_context)
    before_media = {c["creative_id"]: classification_source_hash(c) for c in stored}
    prepare_media(client, stored, inputs, config, coverage)
    enriched = [c for c in stored if not c.get("vanished_after")
                and classification_source_hash(c) != before_media[c["creative_id"]]]
    if enriched:
        changed_ids = {c["creative_id"] for c in enriched}
        # A preview classification cannot claim it observed subsequently added
        # speech/frames. Only a successful enriched classification replaces it.
        classifications = [cl for cl in classifications if cl["creative_id"] not in changed_ids]
        classifications += classify_corpus(client, select_for_classification(enriched), taxonomy, taxonomy_sha256,
                                           inputs.product_context, coverage)
    dictionary = SEMANTICS.apply_semantics(stored, classifications, client.semantic_context)
    if inputs.runtime is not None:
        write_snapshot(inputs.runtime, inputs.as_of, [c for c in stored if not c.get("vanished_after")], listings, inputs.domains, inputs.sources)
    for c in stored:
        for member in c.get("source_members") or []:
            member["language_allowed"] = c.get("language_allowed")
            member["language_status"] = c.get("language_status")
    by_creative = {c["creative_id"]: c for c in stored}
    for cl in classifications:
        c = by_creative[cl["creative_id"]]
        labels = cl.get("labels") or {}
        detail = labels.get("message_shape") if c.get("creative_type") == "text" else "+".join(sorted(labels.get("visual_treatment") or []))
        c["format_detail"] = detail or "unspecified"
        for name in ("language_allowed", "language_status", "country", "creative_type", "format_kind", "format_detail", "competitor_tier", "relevance", "duration_scope", "source_members"):
            cl[name] = by_creative[cl["creative_id"]].get(name)
    classified_ids = {c["creative_id"] for c in classifications}
    for c in stored:
        if c.get("relevance") != "irrelevant" and c.get("language_status") != "excluded" and c["creative_id"] not in classified_ids:
            coverage.append({"type": "coverage", "domain": c["domain"], "country": c.get("country"), "channel": c["channel"], "source": "classify", "status": "unclassified", "detail": "No usable classification; see media and budget gaps", "tier": "C"})
    patterns = score_patterns(stored, classifications, taxonomy, inputs.long_running_days, dictionary)
    anchors = price_anchors(stored, classifications)
    totals = client.ledger_totals()
    retrieved_on = totals["first_retrieved_on"] if totals["first_retrieved_on"] == totals["last_retrieved_on"] else f"{totals['first_retrieved_on']}..{totals['last_retrieved_on']}"
    if inputs.footprint is not None:
        retrieved_on = inputs.footprint.get("retrieved_on") or inputs.as_of.isoformat()
    evidence = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "coverage_status": "partial" if any(r.get("status") in ("budget_deferred", "unclassified", "not_extracted", "unavailable", "media_gap", "truncated_input") for r in coverage) else "sample_completed",
        "angle_dictionary": dictionary,
        "generated_by": Path(__file__).name,
        "retrieved_on": retrieved_on,
        "inputs": {"domains": inputs.domains, "domain_sources": inputs.domain_sources, "product_domain": inputs.product_domain,
                   "sources": inputs.sources, "country": inputs.country, "eu_country": inputs.eu_country, "as_of": inputs.as_of.isoformat(),
                   "effective_policy": inputs.effective_policy,
                   "policy_sha256": inputs.policy_sha256, "target_countries": (inputs.footprint or {}).get("inputs", {}).get("target_countries", sorted({inputs.country, inputs.eu_country})),
                   "collection_mode": "channel_footprint_reuse" if inputs.footprint is not None else "standalone",
                   "accepted_languages": inputs.languages, "market_languages": inputs.market_languages,
                   "top_videos_per_competitor_channel_market": inputs.top_videos,
                   "deepened_cells": None if inputs.deepened_cells is None else sorted([country, channel] for country, channel in inputs.deepened_cells),
                   "semantic_context_sha256": client.semantic_context["context_sha256"],
                   "footprint_document_sha256": POLICY.canonical_hash(inputs.footprint) if inputs.footprint is not None else None,
                   "taxonomy_version": taxonomy["taxonomy_version"],
                   "taxonomy_sha256": taxonomy_sha256},
        # Patterns first by score, then every other type interleaved by
        # competitor: any sample of the file (the AI projection keeps the
        # first rows of each type) covers the competitors, not the first one.
        "rows": patterns + _interleave_by_domain(stored) + _interleave_by_domain(classifications)
                + _interleave_by_domain(anchors) + _interleave_by_domain(coverage),
        "totals": {k: v for k, v in totals.items() if k not in ("first_retrieved_on", "last_retrieved_on")},
    }
    section = render_section(domains=inputs.domains, creatives=stored, classifications=classifications, patterns=patterns, anchors=anchors,
                             coverage=coverage, totals=totals, as_of=inputs.as_of.isoformat(), retrieved_on=retrieved_on,
                             long_running_days=inputs.long_running_days, taxonomy_version=taxonomy["taxonomy_version"], selection=MODEL.SELECTION.build_selection(evidence))
    return {"evidence": evidence, "section_markdown": section, "totals": totals,
            "attempt": {"actor_runs": client.actor_runs, "meta_searches": client.meta_searches, "spyfu_calls": client.spyfu_calls,
                        "classify_calls": client.classify_calls, "media_calls": client.media_calls, "image_fetches": client.image_fetches, "cache_hits": client.cache_hits}}


def publish_previews(rows: list[dict], workspace: Path, selection: dict | None = None, countries: list[str] | None = None) -> tuple[Path, ...]:
    """Make previews portable in the research artifact folder, hash-verified: the
    top selection plus every row a campaign pack may cite as its original."""
    selection = selection or MODEL.SELECTION.build_selection({"rows": rows})
    selected = {(ref["country"], ref["channel"], ref["creative_type"], ref["domain"], ref["creative_id"]) for ref in selection["selected_creatives"]}
    publishable = [row for row in rows if row.get("type") == "creative"
        and (not countries or row.get("country") in countries) and (
        (row.get("country"), row.get("channel"), row.get("creative_type", "unknown"), row.get("domain"), row.get("creative_id")) in selected
        or MODEL.SELECTION.citable(row, countries))]
    published = set()
    for row in publishable:
        assets = row.get("media_assets") or []
        previews = [a for a in assets if a.get("kind") in ("image", "preview")]
        if not previews:
            previews = [a for a in assets if a.get("kind") == "frame"][:1]
        for asset in previews:
            try:
                ref = Path(str(asset["path"]))
                source = (workspace / ref).resolve()
                if ref.is_absolute() or ".." in ref.parts or not source.is_relative_to(workspace):
                    raise ValueError("preview path escapes workspace")
                if source.stat().st_size > VIDEO.MAX_FRAME_BYTES:
                    raise ValueError("preview exceeds the bounded image size")
                content = source.read_bytes()
                digest = hashlib.sha256(content).hexdigest()
                if asset.get("sha256") and asset["sha256"] != digest:
                    raise ValueError("preview hash mismatch")
                mime = CF.sniff_image(content)
                if mime is None:
                    raise ValueError("preview is not a supported image")
                extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[mime]
                dest = workspace / _artifact_path("egbe-docs/research/market/assets/creative-patterns") / f"{digest}.{extension}"
                if not dest.resolve().is_relative_to(workspace):
                    raise ValueError("published preview path escapes workspace")
                # The cached bytes themselves, hard-linked when on one filesystem.
                CF.IO.link_or_copy(source, dest)
                if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
                    raise ValueError("published preview changed while it was linked")
                asset.setdefault("source_path", asset["path"])
                asset.update(path=dest.relative_to(workspace).as_posix(), sha256=digest)
                published.add(dest.relative_to(workspace))
            except (OSError, ValueError, KeyError) as exc:
                asset["publication_status"] = "unavailable"
                rows.append({"type": "coverage", "source": "preview_publication", "domain": row["domain"], "country": row.get("country"), "channel": row["channel"], "creative_id": row.get("creative_id"), "status": "media_gap", "detail": str(exc), "tier": "C"})
    return tuple(sorted(published))


def _interleave_by_domain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get("domain") or ""), []).append(row)
    out: list[dict[str, Any]] = []
    while groups:
        for domain in sorted(list(groups)):
            out.append(groups[domain].pop(0))
            if not groups[domain]:
                del groups[domain]
    return out


def _arg(args: argparse.Namespace, name: str, default: Any) -> Any:
    value = getattr(args, name, None)
    return default if value is None else value


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def resolve_as_of(runtime: Path, override: str, refresh: bool) -> date:
    """The cutoff is fixed at the first attempt so that every rerun asks the
    providers the same questions and replays from the cache. --as-of picks a
    cutoff; --refresh starts today's cutoff, but only once the current one has
    completed: a refresh that stopped on a budget resumes, it never buys the
    same calls again under a new date."""
    marker = runtime / "as-of.json"
    try:
        state = json.loads(marker.read_text(encoding="utf-8"))
        current = date.fromisoformat(state["as_of"])
        completed = bool(state.get("completed"))
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        current, completed = None, False
    if override:
        if not _DATE_RE.match(override):
            raise CreativePatternsError("--as-of must be YYYY-MM-DD")
        chosen = date.fromisoformat(override)
    elif current is None:
        chosen = date.today()
    elif refresh and completed:
        chosen = date.today()
    else:
        if refresh and current != date.today():
            print(f"Creative Patterns: cutoff {current.isoformat()} has not completed yet; resuming it instead of starting a new one.", file=sys.stderr)
        chosen = current
    if chosen != current:
        completed = False
    _write_atomic(marker, json.dumps({"as_of": chosen.isoformat(), "completed": completed}))
    return chosen


def mark_cutoff_completed(runtime: Path, as_of: date) -> None:
    _write_atomic(runtime / "as-of.json", json.dumps({"as_of": as_of.isoformat(), "completed": True}))


def linkedin_slugs(workspace: Path) -> dict[str, str]:
    """Company page slugs that Channel Footprint read from competitor sites."""
    path = workspace / CHANNEL_FOOTPRINT_EVIDENCE_REL
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("rows") or []
    except (OSError, json.JSONDecodeError, AttributeError):
        return {}
    return {r["domain"]: r["linkedin_company"] for r in rows if isinstance(r, dict) and r.get("type") == "pixel_scan" and r.get("linkedin_company")}


def run(workspace: Path, args: argparse.Namespace) -> dict[str, Any]:
    workspace = workspace.resolve()
    io = _load_script("research-artifact-io.py", "pmr_artifact_io")
    with io.section_attempt(workspace, SECTION_ID, context_file=getattr(args, "context_file", None)):
        return _run(workspace, args)


def _run(workspace: Path, args: argparse.Namespace) -> dict[str, Any]:
    runtime = workspace / RUNTIME_REL
    runtime.mkdir(parents=True, exist_ok=True)
    api_key = (os.environ.get("OS_API_KEY") or "").strip()
    if not api_key:
        raise CreativePatternsError("OS_API_KEY is required")
    os_url = (os.environ.get("OS_URL") or DEFAULT_OS_URL).strip() or DEFAULT_OS_URL
    config = CF.load_sources_config(Path(_arg(args, "sources_config", "")) if _arg(args, "sources_config", "") else None)
    taxonomy, taxonomy_sha256 = load_taxonomy()
    effective_policy, policy_sha256 = POLICY.policy_from_taxonomy(taxonomy)
    footprint = footprint_input(workspace, effective_policy, policy_sha256)
    raw_sources = str(_arg(args, "sources", "") or "")
    chosen = [s.strip().lower() for s in raw_sources.split(",") if s.strip()] if raw_sources.strip() else list(ALL_SOURCES)
    unknown = [s for s in chosen if s not in ALL_SOURCES]
    if unknown:
        raise CreativePatternsError(f"unknown sources: {', '.join(unknown)} (known: {', '.join(ALL_SOURCES)})")
    sources = [s for s in ALL_SOURCES if s in chosen]

    max_competitors = max(1, int(_arg(args, "max_competitors", MAX_COMPETITORS)))
    product_domain = registrable_domain(str(_arg(args, "product_domain", "") or ""))
    explicit = [d for d in CF.parse_domains(_arg(args, "domains", ""), MAX_EXPLICIT_DOMAINS) if d != product_domain]
    evidence_mod = _load_script("research-evidence.py", "pmr_evidence_for_creative_patterns")
    tiered = evidence_mod.competitor_set_inputs(workspace, consumer=SECTION_ID, cap=MAX_COMPETITORS)
    rejected = evidence_mod.competitor_set_excluded_domains(workspace) - set(explicit)
    discovered = evidence_mod.keyword_inputs(workspace, consumer=SECTION_ID, row_type="competitor_domain", field="domain", cap=MAX_COMPETITORS, exclude=rejected)
    domains: list[str] = []
    domain_sources: dict[str, str] = {}
    for source, candidates in (("explicit", explicit), ("competitor_set", tiered), ("keyword_economics", discovered)):
        for domain in candidates:
            domain = registrable_domain(domain)
            if len(domains) < max_competitors and domain and domain != product_domain and domain not in domains:
                domains.append(domain)
                domain_sources[domain] = source
    if footprint is not None:
        footprint_domains = footprint["inputs"]["domains"]
        if any(d not in footprint_domains for d in explicit):
            raise CreativePatternsError("explicit competitor is outside the completed Channel Footprint; collect and finalize it there first")
        domains = list(dict.fromkeys(explicit + footprint_domains))[:max_competitors]
        domain_sources = {d: "channel_footprint" for d in domains}
    if not domains:
        raise CreativePatternsError("no competitor domains available: pass --domains, or complete the Competitor Set (or Keyword Economics) section first")
    target_markets = (footprint or {}).get("inputs", {}).get("target_countries") or [str(_arg(args, "country", "US") or "US").upper(), str(_arg(args, "eu_country", "DE") or "DE").upper()]
    languages, market_languages = language_inputs(workspace, args, target_markets)
    if not languages:
        raise CreativePatternsError("accepted languages must be explicitly supplied in intake or --languages before paid calls")
    for name in ("top_videos", "max_channels", "max_media_calls", "max_total_paid_starts", "max_actor_runs", "max_meta_searches", "max_spyfu_calls", "max_classify_calls", "max_image_fetches"):
        value = _arg(args, name, None)
        if value is not None and int(value) < 0:
            raise CreativePatternsError(f"--{name.replace('_', '-')} cannot be negative")
    inputs = RunInputs(
        domains=domains, domain_sources=domain_sources, product_domain=product_domain, sources=sources,
        country=str(_arg(args, "country", "US") or "US").upper(), eu_country=str(_arg(args, "eu_country", "DE") or "DE").upper(),
        as_of=resolve_as_of(runtime, str(_arg(args, "as_of", "") or ""), bool(_arg(args, "refresh", False))),
        long_running_days=None,
        footprint=footprint, effective_policy=effective_policy, policy_sha256=policy_sha256,
        restrict_sources=bool(str(_arg(args, "sources", "") or "").strip()),
        product_context=full_product_context(workspace),
        languages=languages, market_languages=market_languages, top_videos=int(_arg(args, "top_videos", 5)),
        max_channels=int(_arg(args, "max_channels", 0) or 0),
        linkedin_slugs=linkedin_slugs(workspace),
        runtime=runtime,
    )
    client = OsClient(
        # One cache namespace per cutoff: a new cutoff asks every provider again.
        os_url=os_url, api_key=api_key, cache_dir=runtime / "cache" / inputs.as_of.isoformat(), shared_dir=runtime / "cache" / "shared",
        cutoff=inputs.as_of.isoformat(), key_scope=f"{SECTION_ID}:{inputs.as_of.isoformat()}:",
        max_actor_runs=int(_arg(args, "max_actor_runs", MAX_ACTOR_RUNS_PER_ATTEMPT)),
        max_meta_searches=int(_arg(args, "max_meta_searches", MAX_META_SEARCHES_PER_ATTEMPT)),
        max_spyfu_calls=int(_arg(args, "max_spyfu_calls", MAX_SPYFU_CALLS_PER_ATTEMPT)),
        max_total_paid_starts=int(_arg(args, "max_total_paid_starts", 240)),
        cumulative_budget_path=runtime / "budget.json",
        max_media_calls=int(_arg(args, "max_media_calls", 100)),
        max_classify_calls=int(_arg(args, "max_classify_calls", MAX_CLASSIFY_CALLS_PER_ATTEMPT)),
        max_image_fetches=int(_arg(args, "max_image_fetches", CF.MAX_IMAGE_FETCHES_PER_ATTEMPT)),
    )
    existing_budget = client._cache_read(client.cumulative_budget_path)
    if existing_budget is None and client.cumulative_budget_path.is_file():
        raise CreativePatternsError("invalid cumulative budget ledger; do not reset its accepted limit")
    budget = existing_budget or {"schema_version": 1, "limit": client.max_total_paid_starts, "paid_starts": []}
    budget["limit"] = min(int(budget["limit"]), client.max_total_paid_starts)
    budget["spent_starts"] = len(budget["paid_starts"])
    _write_atomic(client.cumulative_budget_path, json.dumps(budget, indent=1))
    outcome = run_pipeline(client, inputs, config, taxonomy, taxonomy_sha256)
    selection = MODEL.SELECTION.build_selection(outcome["evidence"], workspace)
    published_previews = publish_previews(outcome["evidence"]["rows"], workspace, selection, outcome["evidence"]["inputs"]["target_countries"])
    if any(r.get("status") == "media_gap" for r in outcome["evidence"]["rows"]):
        outcome["evidence"]["coverage_status"] = "partial"
    # Regenerate the markdown with portable preview refs after materialization.
    rows = outcome["evidence"]["rows"]
    outcome["section_markdown"] = render_section(domains=inputs.domains, creatives=[r for r in rows if r["type"] == "creative"],
        classifications=[r for r in rows if r["type"] == "creative_classification"], patterns=[r for r in rows if r["type"] == "pattern_score"],
        anchors=[r for r in rows if r["type"] == "price_anchor"], coverage=[r for r in rows if r["type"] == "coverage"], totals=outcome["totals"],
        as_of=inputs.as_of.isoformat(), retrieved_on=outcome["evidence"]["retrieved_on"], long_running_days=inputs.long_running_days, taxonomy_version=taxonomy["taxonomy_version"], selection=selection)
    if outcome["totals"]["provider_calls"] == 0 and inputs.footprint is None and not any(r.get("status") == "budget_deferred" for r in outcome["evidence"]["rows"]):
        raise CreativePatternsError("no provider answered for any competitor; the section cannot complete without one successful call")

    selection = MODEL.SELECTION.build_selection(outcome["evidence"], workspace)
    selection_json = json.dumps(selection, indent=1, ensure_ascii=False)
    selection_sha256 = hashlib.sha256(selection_json.encode("utf-8")).hexdigest()
    _write_atomic(workspace / MODEL.SELECTION.SELECTION_REL, selection_json)
    outcome["evidence"]["selection"] = selection
    outcome["evidence"]["inputs"].update(creative_selection_path=MODEL.SELECTION.SELECTION_REL.as_posix(), creative_selection_sha256=selection_sha256)
    evidence_json = json.dumps(outcome["evidence"], indent=1, ensure_ascii=False)
    _write_atomic(workspace / EVIDENCE_REL, evidence_json)
    _write_atomic(runtime / "result.md", outcome["section_markdown"])
    upsert = _load_script("upsert-markdown-section.py", "pmr_upsert_markdown_section")
    report_path = workspace / REPORT_REL
    report_path.parent.mkdir(parents=True, exist_ok=True)
    upsert.upsert_markdown_section(report_path, SECTION_HEADING, outcome["section_markdown"])
    persist = _load_script("persist-research-report.py", "pmr_persist_research_report")
    persistence = persist.persist_research_report(
        workspace, commit_message=f"research: update {SECTION_HEADING.lower()} section",
        extra_paths=(Path(_artifact_path("egbe-docs/research/market/evidence/creative-patterns.json")), Path(_artifact_path("egbe-docs/research/market/evidence/creative-selection.v1.json")), *published_previews),
    )
    totals, attempt = outcome["totals"], outcome["attempt"]
    state = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "status": "completed",
        "coverage_status": outcome["evidence"]["coverage_status"],
        "creative_selection_path": MODEL.SELECTION.SELECTION_REL.as_posix(),
        "creative_selection_sha256": selection_sha256,
        "intake_sha256": hashlib.sha256((workspace / _artifact_path("egbe-docs/research/market/intake.json")).read_bytes()).hexdigest() if (workspace / _artifact_path("egbe-docs/research/market/intake.json")).is_file() else None,
        "media_calls": totals["media_calls"], "reused_media_calls": totals["reused_media_calls"],
        "media_prompt_tokens": totals["media_prompt_tokens"], "media_completion_tokens": totals["media_completion_tokens"],
        "cumulative_paid_starts": totals["cumulative_paid_starts"], "cumulative_paid_start_limit": totals["cumulative_paid_start_limit"],
        "domains": inputs.domains,
        "domain_sources": inputs.domain_sources,
        "sources": inputs.sources,
        "country": inputs.country,
        "eu_country": inputs.eu_country,
        "as_of": inputs.as_of.isoformat(),
        "taxonomy_version": taxonomy["taxonomy_version"],
        "effective_policy": effective_policy, "policy_sha256": policy_sha256,
        "channel_footprint_sha256": hashlib.sha256((workspace / CHANNEL_FOOTPRINT_EVIDENCE_REL).read_bytes()).hexdigest() if footprint is not None else None,
        "taxonomy_sha256": taxonomy_sha256,
        "evidence_path": EVIDENCE_REL.as_posix(),
        "evidence_sha256": hashlib.sha256(evidence_json.encode("utf-8")).hexdigest(),
        "result_path": (RUNTIME_REL / "result.md").as_posix(),
        "result_sha256": hashlib.sha256(outcome["section_markdown"].encode("utf-8")).hexdigest(),
        "provider_calls": totals["provider_calls"],
        "actor_runs": totals["actor_runs"],
        "meta_searches": totals["meta_searches"],
        "spyfu_calls": totals["spyfu_calls"],
        "classify_calls": totals["classify_calls"],
        "reused_classify_calls": totals["reused_classify_calls"],
        "image_fetches": totals["image_fetches"],
        "rejected_calls": totals["rejected_calls"],
        "observations": totals["observations"],
        "classify_prompt_tokens": totals["classify_prompt_tokens"],
        "classify_completion_tokens": totals["classify_completion_tokens"],
        "creatives": sum(1 for r in outcome["evidence"]["rows"] if r["type"] == "creative"),
        "classifications": sum(1 for r in outcome["evidence"]["rows"] if r["type"] == "creative_classification"),
        "patterns": sum(1 for r in outcome["evidence"]["rows"] if r["type"] == "pattern_score"),
        "attempt_actor_runs": attempt["actor_runs"],
        "attempt_meta_searches": attempt["meta_searches"],
        "attempt_spyfu_calls": attempt["spyfu_calls"],
        "attempt_classify_calls": attempt["classify_calls"],
        "attempt_image_fetches": attempt["image_fetches"],
        "attempt_cache_hits": attempt["cache_hits"],
        "report_commit_sha": persistence.commit_sha,
        "publication_mode": persistence.publication_mode,
        "research_context": _load_script("research-artifact-io.py", "pmr_input_io").context_binding(workspace, SECTION_ID),
        "error": None,
    }
    _write_atomic(runtime / "request.json", json.dumps(state, indent=1))
    _write_atomic(runtime / "semantic-dictionary.json", json.dumps({**outcome["evidence"]["angle_dictionary"],
                  "as_of": inputs.as_of.isoformat(), "product_sha256": hashlib.sha256(inputs.product_context.encode()).hexdigest(),
                  "languages": inputs.languages}, ensure_ascii=False))
    mark_cutoff_completed(runtime, inputs.as_of)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-file", type=Path, help="Explicit context for this study; no project files are discovered implicitly.")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--domains", default="", help="Comma-separated competitor domains; merged ahead of the Competitor Set and Keyword Economics domains.")
    parser.add_argument("--product-domain", default="", help="The product's own domain; never collected as a competitor.")
    parser.add_argument("--sources", default="", help=f"Comma-separated subset of {', '.join(ALL_SOURCES)} (default: all).")
    parser.add_argument("--sources-config", default="", help="Path to an alternative actor config (default: the Channel Footprint sources config).")
    parser.add_argument("--max-competitors", type=int, default=MAX_COMPETITORS)
    parser.add_argument("--country", default="US", help="Market for SpyFu Google search ads (default US).")
    parser.add_argument("--eu-country", default="DE", help="EU country for official Meta delivery data (default DE).")
    parser.add_argument("--as-of", default="", help="Cutoff date YYYY-MM-DD (default: the first attempt's date, kept across reruns).")
    parser.add_argument("--refresh", action="store_true", help="Start a new cutoff at today's date (new provider calls).")
    parser.add_argument("--max-actor-runs", type=int, default=MAX_ACTOR_RUNS_PER_ATTEMPT)
    parser.add_argument("--max-meta-searches", type=int, default=MAX_META_SEARCHES_PER_ATTEMPT)
    parser.add_argument("--max-spyfu-calls", type=int, default=MAX_SPYFU_CALLS_PER_ATTEMPT, help="SpyFu ad-history lookups per attempt (two per competitor).")
    parser.add_argument("--max-classify-calls", type=int, default=MAX_CLASSIFY_CALLS_PER_ATTEMPT, help="Classification calls per attempt (up to ten creatives each).")
    parser.add_argument("--max-image-fetches", type=int, default=CF.MAX_IMAGE_FETCHES_PER_ATTEMPT)
    parser.add_argument("--languages", default="", help="Explicit accepted language codes, e.g. en,es")
    parser.add_argument("--market-languages", default="", help="Per-market language codes: US:en,es;GB:en")
    parser.add_argument("--top-videos", type=int, default=5)
    parser.add_argument("--max-channels", type=int, default=0, help="Express scope: deepen only this many candidate channels per market (0: every cell).")
    parser.add_argument("--max-media-calls", type=int, default=100)
    parser.add_argument("--max-total-paid-starts", type=int, default=240, help="Durable section-wide cap; reruns do not reset it")
    args = parser.parse_args()
    try:
        state = run(args.workspace, args)
    except CreativePatternsError as exc:
        print(f"Creative Patterns could not complete: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Creative Patterns could not complete: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: state[k] for k in ("status", "domains", "creatives", "classifications", "patterns", "provider_calls")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
