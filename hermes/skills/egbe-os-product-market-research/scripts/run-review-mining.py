#!/usr/bin/env python3
"""Run the deterministic Competitor Reviews section against review platforms.

Reviews of paid competitor products are offer material: a 1-3 star review
is a reviewer of a paid product reporting an unmet need (an offer wedge),
and a 5-star review is the exact language of value its users speak. No
payment signal exists per reviewer, so the section never claims reviewers
themselves paid. This runner collects both sides for
the market's competitors:

  - G2 via the Apify actor `automation-lab/g2-scraper` (B2B reviews with
    company-segment/industry codes, love/hate themes, switched-from fields);
  - Trustpilot via `memo23/trustpilot-scraper-ppe` (consumer/prosumer
    reviews, DOMAIN-keyed — identity by construction; billing and
    cancellation complaints live here).

Two pulls per competitor per platform: lowest-rated (wedges) and top-rated
(value language). G2 is slug-keyed, so its product identity is verified
against the brand and unverified slugs are EXCLUDED from analysis rather
than silently mixed in (the Competitor Ads namesake lesson).

No LLM anywhere: platform-provided theme fields (hateTheme/loveTheme,
switchedReason) and deterministic extraction carry the analysis; synthesis
into hypotheses is a downstream concern. Caching, spend provenance, budgets
and retries mirror the Competitor Ads runner.
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
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any, Callable
from urllib.parse import urlparse

SCHEMA_VERSION = 1
SECTION_ID = "review_mining"
SECTION_HEADING = "Competitor reviews"
DISPLAY_NAME = "Competitor Reviews"

DEFAULT_OS_URL = "https://os.hz.egbe.dev"
RUNTIME_REL = Path(_artifact_path("egbe-docs/research/market/work")) / SECTION_ID
EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/review-mining.json"))
REPORT_REL = Path(_artifact_path("egbe-docs/research/market/full-report.md"))

G2_ACTOR = "automation-lab/g2-scraper"
TRUSTPILOT_ACTOR = "memo23/trustpilot-scraper-ppe"

# Two platforms x two pulls (low stars, top stars) per competitor.
MAX_ACTOR_RUNS_PER_ATTEMPT = 12
MAX_COMPETITORS = 3
LOW_REVIEWS_CAP = 60
HIGH_REVIEWS_CAP = 40
STORED_LOW_PER_PLATFORM = 30
STORED_HIGH_PER_PLATFORM = 15
TEXT_TRUNCATE = 300
LOW_STARS = {1, 2, 3}

ACTOR_RETRY_DELAY_SECONDS = 20.0

# Billing/pricing pain markers inside low-star texts — recurring anti-
# positioning material for offers ("no credit card tricks", "cancel anytime").
_BILLING_RE = re.compile(
    r"\b(refund(?:s|ed)?|cancel(?:led|ed|ling|ing)?|billing|billed|"
    r"charge[ds]?|subscription[s]?|price[sd]?|pricing|expensive|cost[s]?|"
    r"renewal[s]?|auto-?renew(?:al|s)?|trial[s]?)\b",
    re.IGNORECASE,
)


class ReviewMiningError(RuntimeError):
    """Terminal runner failure; runtime state is preserved for resume."""


def _load_script(filename: str, module_name: str) -> ModuleType:
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ReviewMiningError(f"cannot load bundled script {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


# ── OS client (same contract as the Competitor Ads runner) ─────────────────

@dataclass
class OsClient:
    os_url: str
    api_key: str
    cache_dir: Path
    max_actor_runs: int = MAX_ACTOR_RUNS_PER_ATTEMPT
    actor_runs: int = 0
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
            raise ReviewMiningError(f"OS {path} failed: HTTP {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise ReviewMiningError(f"OS {path} unreachable: {exc.reason}") from exc
        data = envelope.get("data")
        if envelope.get("code") not in (None, 200) or not isinstance(data, dict):
            raise ReviewMiningError(f"OS {path} returned no data: {str(envelope)[:300]}")
        return data

    def run_actor(self, actor: str, actor_input: dict[str, Any], limit: int) -> tuple[list[dict[str, Any]], str]:
        payload = {"actor": actor, "input": actor_input, "sync": True, "limit": limit}
        key_raw = json.dumps({"kind": "actor", "payload": payload}, sort_keys=True)
        digest = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        self.touched.add(digest)
        if cache_file.is_file():
            try:
                entry = json.loads(cache_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                # A torn write must not poison replay forever: discard the
                # corrupt entry and refetch (charged as a new paid start).
                cache_file.unlink(missing_ok=True)
                entry = None
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
                raise ReviewMiningError(
                    f"actor-run budget exhausted ({self.max_actor_runs} per "
                    "attempt); narrow the competitor list or re-run to "
                    "continue from cache"
                )
            self.actor_runs += 1
            self._journal_start(digest)
            try:
                response = transport(
                    "/scrape/apify/run", payload, 330.0, idempotency_key=wire_key
                )
                break
            except ReviewMiningError as exc:
                if attempts >= 1 or not re.search(r"HTTP 5\d\d", str(exc)):
                    raise
                attempts += 1
                (self.sleep or time.sleep)(ACTOR_RETRY_DELAY_SECONDS)
        retrieved_on = date.today().isoformat()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = cache_file.with_suffix(".json.tmp")
        tmp_file.write_text(
            json.dumps(
                {
                    "kind": "actor",
                    "payload": payload,
                    "response": response,
                    "retrieved_on": retrieved_on,
                }
            ),
            encoding="utf-8",
        )
        tmp_file.replace(cache_file)
        rows = response.get("rows")
        return (rows if isinstance(rows, list) else []), retrieved_on

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
        actor_runs = 0
        dates: list[str] = []
        if self.cache_dir.is_dir():
            for digest in sorted(self.touched):
                entry_path = self.cache_dir / f"{digest}.json"
                try:
                    entry = json.loads(entry_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                actor_runs += 1
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
            "provider_calls": actor_runs,
            "actor_starts_recorded": starts_recorded,
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
        _KEYWORD_ECONOMICS = _load_script("run-keyword-economics.py", "pmr_keyword_economics_for_review_mining")
    return _KEYWORD_ECONOMICS.registrable_domain(value)


def brand_token(domain: str) -> str:
    stem = registrable_domain(domain).split(".")[0]
    return re.sub(r"[^a-z0-9]", "", stem)


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _clean(value: Any) -> Any:
    """The G2 actor serializes empty fields as the literal string 'None' and
    numbers as strings ('starRating': '1') — validated on a live probe."""
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


def _switched_from(value: Any) -> Any:
    """G2's switchedFromOtherProduct is a QUESTIONNAIRE answer observed live
    as 'yes'/'no'/'unknown' (occasionally an actual product name). Only a
    real product name is a switching source; 'yes' means the story lives in
    switchedReason."""
    value = _clean(value)
    if value is None:
        return None
    lowered = str(value).strip().lower()
    if lowered in ("no", "unknown", "none", "n/a", "na"):
        return None
    if lowered == "yes":
        return "yes"
    return str(value).strip()


def _to_bool(value: Any) -> bool | None:
    """Actors serialize booleans as strings ('False') — bool('False') is
    True in Python, so parse explicitly (validated on a live probe)."""
    value = _clean(value)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


def _trustpilot_reviewed_domain(business_url: str, business_name: str) -> str:
    """businessUrl is the TRUSTPILOT page (trustpilot.com/review/<domain>),
    not the company site — extract the reviewed domain from the path."""
    path = urlparse(str(business_url or "")).path
    if "/review/" in path:
        return registrable_domain(path.rsplit("/review/", 1)[-1])
    return registrable_domain(business_name or "")


def parse_terms(raw: str, cap: int) -> list[str]:
    seen: dict[str, None] = {}
    for part in re.split(r"[,;\n]", raw or ""):
        term = part.strip().lower()
        if term and term not in seen:
            seen[term] = None
    return list(seen)[:cap]


def parse_slug_overrides(raw: str) -> dict[str, str]:
    """Parse --g2-slugs 'domain=slug,other.com=other-slug' overrides."""
    overrides: dict[str, str] = {}
    for part in re.split(r"[,;\n]", raw or ""):
        if "=" not in part:
            continue
        domain, slug = part.split("=", 1)
        domain = registrable_domain(domain.strip())
        slug = slug.strip().lower()
        if domain and slug:
            overrides[domain] = slug
    return overrides



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


def normalize_g2_review(row: dict[str, Any], domain: str, slug: str) -> dict[str, Any] | None:
    stars = _to_int(row.get("starRating"))
    text = " ".join(str(_clean(row.get("reviewText")) or "").split())
    if stars is None or not text:
        return None
    billing_flag = bool(_BILLING_RE.search(text))  # classify BEFORE truncation
    switched_reason = " ".join(str(_clean(row.get("switchedReason")) or "").split())
    return {
        "type": "review",
        "platform": "g2",
        "domain": domain,
        "product_slug": _clean(row.get("productSlug")) or slug,
        "product_name": _clean(row.get("productName")),
        "stars": stars,
        "nps": _to_int(row.get("nps")),
        "title": (str(_clean(row.get("title")) or "").strip() or None),
        "text": text[:TEXT_TRUNCATE],
        "date": str(_clean(row.get("publishedAt")) or "")[:10] or None,
        "company_segment_code": _clean(row.get("companySegment")),
        "industry_code": _clean(row.get("industry")),
        "love_theme": _clean(row.get("loveTheme")),
        "hate_theme": _clean(row.get("hateTheme")),
        "switched_from": _switched_from(row.get("switchedFromOtherProduct")),
        "switched_reason": switched_reason[:TEXT_TRUNCATE] or None,
        "billing_pricing_complaint": billing_flag,
        "helpful_votes": _to_int(row.get("helpfulVotes")),
        "url": _clean(row.get("url")),
        "tier": "A",
    }


def normalize_trustpilot_review(row: dict[str, Any], domain: str) -> dict[str, Any] | None:
    stars = _to_int(row.get("rating"))
    text = " ".join(str(_clean(row.get("text")) or "").split())
    if stars is None or not text:
        return None
    billing_flag = bool(_BILLING_RE.search(text))  # classify BEFORE truncation
    business = _trustpilot_reviewed_domain(
        str(row.get("businessUrl") or ""), str(row.get("businessName") or "")
    )
    if business and business != registrable_domain(domain):
        return None  # regional sibling or wrong company — identity is by domain
    return {
        "type": "review",
        "platform": "trustpilot",
        "domain": domain,
        "stars": stars,
        "title": (str(row.get("title") or "").strip() or None),
        "text": text[:TEXT_TRUNCATE],
        "date": str(row.get("publishedDate") or "")[:10] or None,
        "verified": _to_bool(row.get("isVerified")),
        "reviewer_country": row.get("reviewerCountry"),
        "has_company_reply": bool((row.get("reply") or {}).get("text")) if isinstance(row.get("reply"), dict) else False,
        "billing_pricing_complaint": billing_flag,
        "url": row.get("url"),
        "tier": "A",
    }


def g2_expected_names(domain: str, slug: str) -> set[str]:
    """Accepted normalized product names for a competitor: the brand token,
    brand+domain ('mondaycom' for monday.com), and the RESOLVED slug — so a
    legitimate --g2-slugs override ('usemotion.com=motion' with productName
    'Motion') validates instead of being rejected."""
    return {
        brand_token(domain),
        _normalize_name(registrable_domain(domain)),
        _normalize_name(slug),
    } - {""}


def g2_row_identity_ok(review: dict[str, Any], expected: set[str], slug: str) -> bool:
    """Per-ROW identity (one matching name must not admit a mixed batch):
    the row's product name matches an expected form (or a '(formerly X)'
    rename of one), or the row carries no name but echoes the requested
    slug. Rows with neither are rejected individually."""
    name = review.get("product_name")
    if name:
        normalized = _normalize_name(str(name))
        if normalized in expected:
            return True
        if "formerly" in str(name).lower() and any(
            normalized.startswith(candidate) for candidate in expected
        ):
            return True
        return False
    return _normalize_name(str(review.get("product_slug") or "")) == _normalize_name(slug)


def summarize_reviews(
    domain: str, platform: str, low: list[dict[str, Any]], high: list[dict[str, Any]]
) -> dict[str, Any]:
    hate = Counter(r["hate_theme"] for r in low if r.get("hate_theme"))
    love = Counter(r["love_theme"] for r in high if r.get("love_theme"))
    switched = [
        {"from": r["switched_from"], "reason": r.get("switched_reason")}
        for r in low + high
        if r.get("switched_from")
        and (r["switched_from"] != "yes" or r.get("switched_reason"))
    ]
    billing_complaints = sum(1 for r in low if r.get("billing_pricing_complaint"))
    segments = Counter(
        r["company_segment_code"] for r in low + high if r.get("company_segment_code")
    )
    return {
        "type": "review_summary",
        "domain": domain,
        "platform": platform,
        "low_star_reviews": len(low),
        "high_star_reviews": len(high),
        "billing_pricing_complaints": billing_complaints,
        "hate_themes": dict(hate.most_common(8)),
        "love_themes": dict(love.most_common(8)),
        "switched_from": switched[:10],
        "company_segment_codes": dict(segments.most_common(6)),
        "tier": "A",
    }


# ── rendering ──────────────────────────────────────────────────────────────

def _excerpt_row(review: dict[str, Any]) -> str:
    text = (review.get("text") or "").replace("|", "/")
    cell = f"{text[:140]}"
    if review.get("url"):
        cell = f"[{cell}]({review['url']})"
    date_str = review.get("date") or "—"
    extra = review.get("hate_theme") or review.get("love_theme") or "—"
    return f"| {review['domain']} | {review['platform']} | {review['stars']}★ | {date_str} | {extra} | {cell} |"


def render_section(
    *,
    domains: list[str],
    domain_sources: dict[str, str],
    summaries: list[dict[str, Any]],
    low_reviews: list[dict[str, Any]],
    high_reviews: list[dict[str, Any]],
    excluded_platforms: list[dict[str, Any]],
    totals: dict[str, Any],
    retrieved_on: str,
) -> str:
    lines: list[str] = []
    add = lines.append

    add(
        f"Customer reviews of paid competitor products retrieved {retrieved_on} "
        "from G2 (B2B reviews with company-segment and switching data; "
        "slug-keyed, per-row identity-checked against the brand) and "
        "Trustpilot (consumer/prosumer reviews; DOMAIN-keyed). Two pulls per "
        "competitor and platform: lowest-rated reviews come from reviewers "
        "of a paid product reporting unmet needs (offer wedges), top-rated "
        "reviews carry the exact language of value its users speak. No "
        "per-reviewer payment signal exists — Trustpilot rows carry a "
        "verified flag, G2 rows do not — so no claim is made that reviewers "
        "themselves paid. Analysis uses only platform-recorded fields over "
        "exactly the rows persisted in the evidence file; hypothesis "
        "synthesis happens downstream."
    )
    add("")
    add(
        "Competitors examined: "
        + ", ".join(f"`{d}` ({domain_sources.get(d, 'explicit')})" for d in domains)
        + "."
    )
    add("")

    add("### Review coverage")
    add("")
    add("| Domain | Platform | 1–3★ collected | 5★ collected | Billing/pricing complaints (1–3★) |")
    add("| --- | --- | ---: | ---: | ---: |")
    for summary in summaries:
        add(
            f"| {summary['domain']} | {summary['platform']} | "
            f"{summary['low_star_reviews']} | {summary['high_star_reviews']} | "
            f"{summary['billing_pricing_complaints']} |"
        )
    add("")
    if excluded_platforms:
        add(
            "Excluded from analysis (identity not verified): "
            + "; ".join(
                f"{row['domain']} on {row['platform']} ({row['reason']})"
                for row in excluded_platforms
            )
            + "."
        )
        add("")

    themed = [s for s in summaries if s["hate_themes"] or s["switched_from"]]
    if themed:
        add("### Complaint themes and switching (as recorded by the platform)")
        add("")
        for summary in themed:
            if summary["hate_themes"]:
                themes = ", ".join(
                    f"{theme} × {count}" for theme, count in summary["hate_themes"].items()
                )
                add(f"- `{summary['domain']}` ({summary['platform']}) hate themes: {themes}.")
            for switch in summary["switched_from"][:5]:
                reason = f" — “{switch['reason']}”" if switch.get("reason") else ""
                source = (
                    "another tool"
                    if switch["from"] == "yes"
                    else switch["from"]
                )
                add(
                    f"- `{summary['domain']}`: reviewer switched from "
                    f"{source}{reason}."
                )
        add("")

    if low_reviews:
        add("### Lowest-rated excerpts (unmet needs)")
        add("")
        add("| Domain | Platform | Stars | Date | Platform theme | Excerpt |")
        add("| --- | --- | --- | --- | --- | --- |")
        shown: dict[str, int] = {}
        for review in low_reviews:
            key = f"{review['domain']}|{review['platform']}"
            if shown.get(key, 0) >= 4:
                continue
            shown[key] = shown.get(key, 0) + 1
            add(_excerpt_row(review))
        add("")

    if high_reviews:
        add("### Value language (top-rated excerpts)")
        add("")
        add("| Domain | Platform | Stars | Date | Platform theme | Excerpt |")
        add("| --- | --- | --- | --- | --- | --- |")
        shown = {}
        for review in high_reviews:
            key = f"{review['domain']}|{review['platform']}"
            if shown.get(key, 0) >= 3:
                continue
            shown[key] = shown.get(key, 0) + 1
            add(_excerpt_row(review))
        add("")

    add("### Method and coverage")
    add("")
    add(
        f"- Provider calls recorded: {totals['actor_runs']} review-platform "
        "actor run(s), accumulated across attempts; cached replays add no "
        "new spend."
    )
    add(
        f"- Caps: {MAX_COMPETITORS} competitors, {LOW_REVIEWS_CAP} lowest-rated "
        f"and {HIGH_REVIEWS_CAP} top-rated reviews per competitor-platform, "
        f"{MAX_ACTOR_RUNS_PER_ATTEMPT} actor runs per attempt."
    )
    add(
        "- G2 company-segment and industry values are G2's integer codes "
        "(kept raw in evidence). Review volumes reflect what the platforms "
        "serve, are biased toward products that solicit reviews, and an "
        "empty platform is weak evidence for small competitors. Not covered: "
        "Capterra/GetApp, app stores, Shopify/Chrome/WordPress directories."
    )
    add("")
    add("### Sources")
    add("")
    add(
        f"- G2 via Apify `{G2_ACTOR}`; Trustpilot via Apify "
        f"`{TRUSTPILOT_ACTOR}` — retrieved {retrieved_on}; the stored review "
        f"rows in `{EVIDENCE_REL.as_posix()}` are exactly the set the "
        "aggregates above are computed from (top rows per competitor-"
        "platform by helpfulness/recency; texts truncated for storage, "
        "billing flags classified on full text before truncation)."
    )
    return "\n".join(lines).strip() + "\n"


# ── orchestration ──────────────────────────────────────────────────────────

@dataclass
class RunInputs:
    domains: list[str]
    domain_sources: dict[str, str]
    g2_slugs: dict[str, str]


def _call_with_context(client: OsClient, domain: str, label: str, fn: Callable[[], Any]) -> Any:
    """Re-raise a provider-call failure with WHICH competitor/call failed and
    how much of the attempt's paid budget is already spent — the raw gateway
    envelope alone doesn't say either, so a human can't tell whether a retry
    is even possible without this."""
    try:
        return fn()
    except ReviewMiningError as exc:
        raise ReviewMiningError(
            f"{label} for `{domain}` failed: {exc} — this attempt had "
            f"already started {client.actor_runs}/{client.max_actor_runs} "
            "actor run(s); see GET /me/limits?resource=apify:runs for "
            "remaining daily quota."
        ) from exc


def run_pipeline(client: OsClient, inputs: RunInputs) -> dict[str, Any]:
    if not inputs.domains:
        raise ReviewMiningError(
            "no competitor domains available: run the Keyword Economics "
            "section first (its evidence feeds this section) or pass "
            "--domains explicitly"
        )

    summaries: list[dict[str, Any]] = []
    stored_low: list[dict[str, Any]] = []
    stored_high: list[dict[str, Any]] = []
    excluded_platforms: list[dict[str, Any]] = []

    for domain in inputs.domains:
        brand = brand_token(domain)
        slug = inputs.g2_slugs.get(registrable_domain(domain), brand)

        g2_low_rows, _ = _call_with_context(
            client,
            domain,
            "G2 (lowest-rated)",
            lambda: client.run_actor(
                G2_ACTOR,
                {
                    "mode": "product_reviews",
                    "productUrls": [slug],
                    "maxReviews": LOW_REVIEWS_CAP,
                    "sortReviews": "rating_low",
                },
                limit=LOW_REVIEWS_CAP,
            ),
        )
        g2_high_rows, _ = _call_with_context(
            client,
            domain,
            "G2 (top-rated)",
            lambda: client.run_actor(
                G2_ACTOR,
                {
                    "mode": "product_reviews",
                    "productUrls": [slug],
                    "maxReviews": HIGH_REVIEWS_CAP,
                    "sortReviews": "rating_high",
                },
                limit=HIGH_REVIEWS_CAP,
            ),
        )
        g2_low_all = [
            r for r in (normalize_g2_review(x, domain, slug) for x in g2_low_rows) if r
        ]
        g2_high_all = [
            r for r in (normalize_g2_review(x, domain, slug) for x in g2_high_rows) if r
        ]
        expected_names = g2_expected_names(domain, slug)
        g2_low = [r for r in g2_low_all if g2_row_identity_ok(r, expected_names, slug)]
        g2_high = [r for r in g2_high_all if g2_row_identity_ok(r, expected_names, slug)]
        g2_identity_rejected = (len(g2_low_all) - len(g2_low)) + (
            len(g2_high_all) - len(g2_high)
        )
        if (g2_low_all or g2_high_all) and not (g2_low or g2_high):
            excluded_platforms.append(
                {
                    "type": "excluded_platform",
                    "domain": domain,
                    "platform": "g2",
                    "slug": slug,
                    "reason": "slug_resolves_to_different_product",
                    "tier": "B",
                }
            )
        # Sort filters are best-effort: keep only genuinely low rows and
        # EXACTLY five-star rows (the report labels the column 5-star).
        g2_low = [r for r in g2_low if r["stars"] in LOW_STARS]
        g2_high = [r for r in g2_high if r["stars"] == 5]

        tp_low_rows, _ = _call_with_context(
            client,
            domain,
            "Trustpilot (lowest-rated)",
            lambda: client.run_actor(
                TRUSTPILOT_ACTOR,
                {
                    "startUrls": [registrable_domain(domain)],
                    "filterStars": ["1", "2", "3"],
                    "maxItems": LOW_REVIEWS_CAP,
                    "sortBy": "recent",
                    "filterLanguages": ["en"],
                },
                limit=LOW_REVIEWS_CAP,
            ),
        )
        tp_high_rows, _ = _call_with_context(
            client,
            domain,
            "Trustpilot (top-rated)",
            lambda: client.run_actor(
                TRUSTPILOT_ACTOR,
                {
                    "startUrls": [registrable_domain(domain)],
                    "filterStars": ["5"],
                    "maxItems": HIGH_REVIEWS_CAP,
                    "sortBy": "recent",
                    "filterLanguages": ["en"],
                },
                limit=HIGH_REVIEWS_CAP,
            ),
        )
        tp_low = [
            r
            for r in (normalize_trustpilot_review(x, domain) for x in tp_low_rows)
            if r and r["stars"] in LOW_STARS
        ]
        tp_high = [
            r
            for r in (normalize_trustpilot_review(x, domain) for x in tp_high_rows)
            if r and r["stars"] == 5
        ]

        def _stored(reviews: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
            ranked = sorted(
                reviews,
                key=lambda r: (r.get("helpful_votes") or 0, r.get("date") or ""),
                reverse=True,
            )
            return ranked[:cap]

        # Aggregates are computed over EXACTLY the rows persisted in the
        # evidence file, so the published numbers are reproducible from it.
        g2_low_stored = _stored(g2_low, STORED_LOW_PER_PLATFORM)
        g2_high_stored = _stored(g2_high, STORED_HIGH_PER_PLATFORM)
        tp_low_stored = _stored(tp_low, STORED_LOW_PER_PLATFORM)
        tp_high_stored = _stored(tp_high, STORED_HIGH_PER_PLATFORM)

        g2_summary = summarize_reviews(domain, "g2", g2_low_stored, g2_high_stored)
        g2_summary["identity_rejected_rows"] = g2_identity_rejected
        summaries.append(g2_summary)
        summaries.append(
            summarize_reviews(domain, "trustpilot", tp_low_stored, tp_high_stored)
        )

        stored_low.extend(g2_low_stored)
        stored_low.extend(tp_low_stored)
        stored_high.extend(g2_high_stored)
        stored_high.extend(tp_high_stored)

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
            "g2_slugs": inputs.g2_slugs,
        },
        "rows": (
            domain_rows
            + summaries
            + stored_low
            + stored_high
            + excluded_platforms
        ),
        "totals": {
            "actor_runs": totals["actor_runs"],
            "provider_calls": totals["provider_calls"],
        },
    }

    section_markdown = render_section(
        domains=inputs.domains,
        domain_sources=inputs.domain_sources,
        summaries=summaries,
        low_reviews=stored_low,
        high_reviews=stored_high,
        excluded_platforms=excluded_platforms,
        totals=totals,
        retrieved_on=retrieved_on,
    )
    return {
        "evidence": evidence,
        "section_markdown": section_markdown,
        "totals": totals,
        "attempt": {
            "actor_runs": client.actor_runs,
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
        raise ReviewMiningError("OS_API_KEY is required")
    os_url = (os.environ.get("OS_URL") or DEFAULT_OS_URL).strip() or DEFAULT_OS_URL

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
    # Four actor runs per competitor: never admit more domains than the
    # budget can finish in one attempt.
    domains = domains[: max(1, args.max_actor_runs // 4)]

    inputs = RunInputs(
        domains=domains,
        domain_sources=domain_sources,
        g2_slugs=parse_slug_overrides(args.g2_slugs or ""),
    )
    client = OsClient(
        os_url=os_url,
        api_key=api_key,
        cache_dir=cache_dir,
        max_actor_runs=args.max_actor_runs,
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
    upsert.upsert_markdown_section(report_path, SECTION_HEADING, outcome["section_markdown"])

    persist = _load_script("persist-research-report.py", "pmr_persist_research_report")
    persistence = persist.persist_research_report(
        workspace,
        commit_message=f"research: update {SECTION_HEADING.lower()} section",
        extra_paths=(Path(_artifact_path("egbe-docs/research/market/evidence/review-mining.json")),),
    )

    state = {
        "schema_version": SCHEMA_VERSION,
        "section_id": SECTION_ID,
        "status": "completed",
        "domains": inputs.domains,
        "domain_sources": inputs.domain_sources,
        "evidence_path": EVIDENCE_REL.as_posix(),
        "evidence_sha256": hashlib.sha256(evidence_json.encode("utf-8")).hexdigest(),
        "result_path": (RUNTIME_REL / "result.md").as_posix(),
        "result_sha256": hashlib.sha256(outcome["section_markdown"].encode("utf-8")).hexdigest(),
        "provider_calls": outcome["totals"]["provider_calls"],
        "actor_runs": outcome["totals"]["actor_runs"],
        "actor_starts_recorded": outcome["totals"].get("actor_starts_recorded", 0),
        "attempt_actor_runs": outcome["attempt"]["actor_runs"],
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
        "--domains",
        default="",
        help="Comma-separated competitor domains; merged ahead of the "
        "domains discovered by Keyword Economics.",
    )
    parser.add_argument(
        "--g2-slugs",
        default="",
        help="Optional G2 slug overrides as 'domain=slug,other.com=slug2' "
        "when a competitor's G2 slug differs from its brand token.",
    )
    parser.add_argument("--max-competitors", type=int, default=MAX_COMPETITORS)
    parser.add_argument("--max-actor-runs", type=int, default=MAX_ACTOR_RUNS_PER_ATTEMPT)
    args = parser.parse_args()

    try:
        state = run(args.workspace, args)
    except (ReviewMiningError, ValueError) as exc:
        print(f"{DISPLAY_NAME}: {exc}", file=sys.stderr)
        return 1
    print(
        f"{DISPLAY_NAME}: completed — {state['actor_runs']} actor run(s), "
        f"evidence at {state['evidence_path']}, report commit "
        f"{state['report_commit_sha'][:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
