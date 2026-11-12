#!/usr/bin/env python3
"""Lifecycle Capture runner (internal section of the competitor-led process).

What the competitors send after someone signs up: the welcome sequence, its
cadence, offers, discounts and deadlines. The claw's own mailbox is the
secret shopper: one ordinary plus-addressed alias per competitor, plus stable
per-funnel aliases imported from section 05
(`<local>+NN@<domain>`, NN from 10–99), so every message is attributed by the
address it was sent to.

Two phases, one command:

- Start: the runner plans one alias per competitor and names the entry
  points from an agent's reviewed discovery; the assigned human subscribes (newsletter, free account, trial
  or waitlist that needs no payment) in the browser and the agent records each
  subscription in `subscriptions.json`. The runner validates the file and
  publishes the subscriptions. Until every competitor is subscribed or
  skipped with a reason, the receipt stays `pending`.
- Harvest: the runner reads the inbox by alias through OS (`GET /mail/inbox`
  with `to` and `since`), reads new messages once each, extracts cadence,
  offers, discounts and deadlines, and republishes the section. Run it
  again as mail accumulates; a later harvest replaces the earlier one.

Policy, approved for this section only: research sign-ups on competitor
sites with the claw's plus-addressed mailbox alias; no payments and no card
details; no agent-created accounts or required phone; no CAPTCHA bypass;
no real third-party identities; unsubscribe when
the capture ends. Message bodies stay in the runtime cache; the evidence
carries subjects and extracted facts, never bodies or excerpts.

Usage:
  python3 run-lifecycle-capture.py --workspace . --product-domain product.com            # start, or harvest once subscribed
  python3 run-lifecycle-capture.py --workspace . --product-domain product.com --harvest  # harvest explicitly
  python3 run-lifecycle-capture.py --workspace . --funnel-mail --refresh                # same-day 05 mail
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
import fcntl
import hashlib
import html
import importlib.util
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = 1
SECTION_ID = "lifecycle_capture"
SECTION_HEADING = "Lifecycle capture"
DISPLAY_NAME = "Lifecycle Capture"
DEFAULT_OS_URL = "https://os.hz.egbe.dev"
RUNTIME_REL = Path(_artifact_path("egbe-docs/research/market/work")) / SECTION_ID
EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/lifecycle-capture.json"))
REPORT_REL = Path(_artifact_path("egbe-docs/research/market/full-report.md"))
FUNNEL_TEARDOWN_EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/funnel-teardown.json"))
SUBSCRIPTIONS_FILENAME = "subscriptions.json"
PLAN_FILENAME = "plan.json"
ENTRY_POINTS_FILENAME = "entry-points.json"
OPERATOR_ACTIONS_FILENAME = "operator-actions.json"
IDENTITY_REL = Path(_artifact_path("egbe-docs/research/market/work/identity-registry.json"))
FUNNEL_HANDOFF_REL = Path(_artifact_path("egbe-docs/research/market/work/funnel_teardown/lifecycle-handoff.json"))
FUNNEL_EVENTS_FILENAME = "funnel-events.json"
FUNNEL_KINDS = ("lead_form", "quiz", "webinar_registration")
ALIAS_PREFIX = "lc-"

MAX_COMPETITORS = 10
MAX_INBOX_CALLS_PER_ATTEMPT = 30     # one per subscription per harvest; each is one IMAP login at the mail server
MAX_MESSAGE_READS_PER_ATTEMPT = 60   # bodies are read once and cached for good
INBOX_PAGE = 50
HARVEST_AFTER_DAYS = 14              # the sequence worth reading has had time to arrive
EARLY_HARVEST_AFTER_DAYS = 3
EXCERPT_CHARS = 160
SUBSCRIPTION_KINDS = ("newsletter", "account", "trial", "waitlist", "lead_form")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_URL_RE = re.compile(r"^https?://[^\s<>\"']+$", re.IGNORECASE)
_CONFIRM_RE = re.compile(r"\b(?:confirm|verify|verification|activate|validate)\b", re.IGNORECASE)
_DEADLINE_RE = re.compile(r"\b(?:ends? (?:today|tonight|tomorrow|soon|in \d+ (?:hours?|days?))|expires?(?: in \d+ (?:hours?|days?))?|last (?:chance|day|call)|"
                          r"today only|\d+ hours? left|final hours|limited time|don't miss|hurry|offer ends|sale ends|closing soon)\b", re.IGNORECASE)
_DISCOUNT_RE = re.compile(r"(?<!\d)(\d{1,2})\s?%\s?(?:off|discount|savings?)|(?:save|discount of)\s*(?:up to\s*)?(\d{1,2})\s?%", re.IGNORECASE)
_AMOUNT = r"\d{1,3}(?:[.,  ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_PRICE_RE = re.compile(rf"(?:[$€£]\s?(?:{_AMOUNT})(?!\d)(?:\s*(?:/\s?(?:mo|month|yr|year)\b|per\s+(?:month|year)|a\s+(?:month|year)))?"
                       rf"|(?<!\d)(?:{_AMOUNT})\s?(?:USD|EUR|GBP|€|£)(?![a-z]))", re.IGNORECASE)
_FREE_RE = re.compile(r"\b(?:free trial|for free|100% free|try (?:it )?free|free (?:plan|month|week|course|lesson)|no credit card)\b", re.IGNORECASE)
_UNSUB_RE = re.compile(r"unsubscribe|manage (?:your )?(?:email )?preferences|opt[- ]out", re.IGNORECASE)
_PROGRESS_RE = re.compile(r"\b(?:your progress|pick up where|continue (?:your|learning|the course)|you(?:'| a)re almost|streak|keep going|don't stop|still waiting)\b", re.IGNORECASE)
_LINK_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)


def _load_script(filename: str, module_name: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


CF = _load_script("run-channel-footprint.py", "pmr_channel_footprint_for_lifecycle_capture")
LifecycleCaptureError = CF.ChannelFootprintError
BudgetExhausted = CF.BudgetExhausted
registrable_domain = CF.registrable_domain
brand_token = CF.brand_token
START = _load_script("lifecycle-start.py", "pmr_lifecycle_start")
FUNNEL = _load_script("funnel-model.py", "pmr_funnel_model_for_lifecycle_mail")

# Mail-specific access material, not a general personal-data filter. Ordinary
# bodies, addresses, offer codes and campaign URLs remain portable evidence.
_MAIL_LINK_RE = re.compile(r"(?:https?://|https?%3a%2f%2f)[^\s<>\"')\]]+", re.IGNORECASE)
_MAIL_SECRET_FIELDS = frozenset({"password", "access_token", "refresh_token", "id_token", "auth_token",
                                "token", "otp", "verification_code", "confirmation_code", "recovery_code"})
_MAIL_CREDENTIAL_LABEL = (r"(?:(?:one[- ]time|verification|confirmation|security|login|sign[- ]in|access|authentication)\s+(?:code|password)"
                          r"|(?:temporary\s+)?password|(?:access|refresh|auth)[-_ ]token|OTP)")
_MAIL_GAP = r"(?:\s|<[^>]*>)*"
_MAIL_CREDENTIAL_RE = re.compile(
    rf"(\b{_MAIL_CREDENTIAL_LABEL}{_MAIL_GAP}(?:(?:is\b|[:=]){_MAIL_GAP})?[\"']?)"
    r"([A-Za-z0-9][A-Za-z0-9._~+/=-]{2,})", re.IGNORECASE)
_MAIL_CREDENTIAL_BEFORE_LABEL_RE = re.compile(
    rf"\b([A-Za-z0-9][A-Za-z0-9._~+/=-]{{2,}})(\s+is\s+(?:(?:your|the)\s+)?{_MAIL_CREDENTIAL_LABEL}\b)", re.IGNORECASE)
_MAIL_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_MAIL_SIGNIN_SUBJECT_RE = re.compile(r"\b(?:sign[- ]?in|log[- ]?in)\b", re.IGNORECASE)
_MAIL_ACCESS_RE = re.compile(r"\b(?:magic[- ]link|password reset|reset (?:your )?password|"
                             r"one[- ]time (?:code|password)|(?:verification|confirmation|security|access|authentication|login|sign[- ]in) code|OTP|"
                             r"code (?:to|for) (?:sign[- ]?in|log[- ]?in)|"
                             r"(?:confirm|verify|activate) (?:your )?(?:email|account))\b", re.IGNORECASE)
# Access messages often separate the label and value (including in their HTML
# alternative). Apply these only to message content, never IDs, dates or addresses.
_MAIL_NUMERIC_CODE_RE = re.compile(r"(?<![\w$€£./:-])(?:\d{3}[ \t\u00a0-]\d{3}|\d{4,10})(?![\w/-])")
_MAIL_CODE_LINE_RE = re.compile(r"(^|>)([ \t]*)([A-Z0-9]{4,16})([ \t]*)(?=$|<)", re.MULTILINE | re.IGNORECASE)
_MAIL_CONTENT_FIELDS = frozenset({"subject", "text", "html"})


def portable_mail_response(value: Any, *, _access_message: bool = False, _content: bool = False) -> Any:
    """Remove usable access material before it reaches any versionable file."""
    if isinstance(value, dict):
        subject = str(value.get("subject") or "")
        content = str(value.get("text") or "")[:600] + "\n" + re.sub(
            r"<[^>]*>", " ", html.unescape(str(value.get("html") or "")))[:600]
        _access_message = bool(_access_message or _CONFIRM_RE.search(subject)
                               or _MAIL_SIGNIN_SUBJECT_RE.search(subject)
                               or _MAIL_ACCESS_RE.search(subject + "\n" + content))
        return {key: "[credential]" if key.lower().replace("-", "_") in _MAIL_SECRET_FIELDS and item
                else portable_mail_response(item, _access_message=_access_message,
                                            _content=key.lower() in _MAIL_CONTENT_FIELDS) for key, item in value.items()}
    if isinstance(value, list):
        return [portable_mail_response(item, _access_message=_access_message, _content=_content) for item in value]
    if not isinstance(value, str):
        return value

    def link(match: re.Match[str]) -> str:
        raw = match.group(0)
        decoded = raw
        for _ in range(3):
            decoded = urllib.parse.unquote(html.unescape(decoded))
        try:
            parts = urllib.parse.urlsplit(decoded)
            fragment_keys = {key.lower() for key, _ in urllib.parse.parse_qsl(parts.fragment)}
            # Access mail can wrap its credential link in an opaque click URL.
            # Preserve the body, but keep all its usable links in the local original.
            sensitive = (_access_message or FUNNEL._private_mail_url(decoded, [], True) or parts.username or parts.password
                         or fragment_keys & (_MAIL_SECRET_FIELDS | {"code", "key", "auth", "signature"})
                         or re.search(r"/(?:login|sign-?in|reset-password|password-reset|recover|recovery|unsubscribe)(?:/|$)", parts.path, re.I))
        except ValueError:
            sensitive = True
        return "[access-link]" if sensitive else raw

    decoded = html.unescape(value) if _content else value
    cleaned = _MAIL_LINK_RE.sub(link, decoded)
    if _access_message and _content:
        cleaned = _MAIL_NUMERIC_CODE_RE.sub("[credential]", cleaned)
        cleaned = _MAIL_CODE_LINE_RE.sub(
            lambda match: match.group(1) + match.group(2) + "[credential]" + match.group(4)
            if any(c.isdigit() for c in match.group(3)) else match.group(0), cleaned)
    cleaned = _MAIL_CREDENTIAL_BEFORE_LABEL_RE.sub(lambda match: "[credential]" + match.group(2), cleaned)
    cleaned = _MAIL_BEARER_RE.sub("Bearer [credential]", _MAIL_CREDENTIAL_RE.sub(
        lambda match: match.group(1) + "[credential]", cleaned))
    return value if cleaned == decoded else cleaned


# ── client ──────────────────────────────────────────────────────────────────

@dataclass
class OsClient(CF.OsClient):
    """The Channel Footprint client plus GET calls to the OS mail routes. The
    mailbox address is cached for the runtime; inbox listings are cached per
    harvest day; message bodies are cached once for good."""

    max_inbox_calls: int = MAX_INBOX_CALLS_PER_ATTEMPT
    max_message_reads: int = MAX_MESSAGE_READS_PER_ATTEMPT
    inbox_calls: int = 0
    message_reads: int = 0
    shared_dir: Path | None = None
    secret_dir: Path | None = None
    get: Callable[..., dict[str, Any]] | None = None
    inbox_checks: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_get_at: str | None = None

    def _isolate_mail_credentials(self, entry: dict[str, Any]) -> dict[str, Any]:
        original = entry["response"]
        portable = portable_mail_response(original)
        if portable == original:
            return entry
        if isinstance(original, dict) and isinstance(original.get("text"), str):
            portable["mail_content_metrics"] = {"links": len(_LINK_RE.findall(original["text"])),
                                               "word_count": len(original["text"].split()),
                                               "unsubscribe_link": bool(_UNSUB_RE.search(original["text"])),
                                               "confirmation_in_prefix": bool(_CONFIRM_RE.search(original["text"][:600]))}
        # Store the original only inside the existing ignored .local boundary,
        # before even a temporary versionable cache file can contain credentials.
        secret_dir = self.secret_dir or self._shared() / ".local" / "mail-cache"
        if ".local" not in secret_dir.parts:
            raise LifecycleCaptureError("credential-bearing mail requires a .local cache directory")
        for parent in (secret_dir, *secret_dir.parents):
            if parent.is_symlink():
                raise LifecycleCaptureError("credential-bearing mail cache must not use symlinks")
            if parent.name == ".local":
                break
        secret_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        encoded = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=secret_dir, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            try:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
                os.replace(temporary, secret_dir / f"{digest}.json")
            finally:
                temporary.unlink(missing_ok=True)
        return {**entry, "response": portable, "credentials_isolated": True}

    def _shared(self) -> Path:
        path = self.shared_dir or self.cache_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _http_get(self, path: str, params: dict[str, Any] | None = None, timeout: float = 60.0) -> dict[str, Any]:
        query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})
        url = f"{self.os_url.rstrip('/')}{path}" + (f"?{query}" if query else "")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}, method="GET")
        try:
            for _name, _value in _connection_headers(req.full_url).items():
                req.add_unredirected_header(_name, _value)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                envelope = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Upstream bodies may echo mail access material; status is enough
            # for retry/coverage decisions and is safe for caller output.
            raise LifecycleCaptureError(f"OS {path} failed: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise CF.OsUnreachable(f"OS {path} unreachable: {exc.reason}") from exc
        except (OSError, ValueError) as exc:
            raise LifecycleCaptureError(f"OS {path} failed in transit: {type(exc).__name__}: {str(exc)[:200]}") from exc
        data = envelope.get("data")
        if envelope.get("code") not in (None, 200) or not isinstance(data, dict):
            raise LifecycleCaptureError(f"OS {path} returned no valid mail data")
        return data

    def _cached_get(self, kind: str, path: str, params: dict[str, Any], *, cache_dir: Path, budget_attr: str, budget_max: int, label: str,
                    timeout: float) -> tuple[dict[str, Any], str]:
        digest = hashlib.sha256(json.dumps({"kind": kind, "path": path, "params": params}, sort_keys=True).encode("utf-8")).hexdigest()
        cache_file = cache_dir / f"{digest}.json"
        self.touched.add(digest)
        entry = self._cache_read(cache_file)
        if entry is not None:
            self.cache_hits += 1
            self.last_get_at = entry.get("retrieved_at")
            response = entry.get("response")
            if portable_mail_response(response) != response:
                raise LifecycleCaptureError("saved mail cache contains access material; secure the local original and sanitize the cache before resuming")
            return (response if isinstance(response, dict) else {}), entry.get("retrieved_on") or date.today().isoformat()
        if getattr(self, budget_attr) >= budget_max:
            raise BudgetExhausted(f"{label} budget exhausted ({budget_max} per attempt); {self.cache_writes} new answer(s) cached in this attempt; rerun to continue from the cache")
        setattr(self, budget_attr, getattr(self, budget_attr) + 1)
        transport = self.get or self._http_get
        attempts = 0
        while True:
            try:
                response = transport(path, params, timeout)
                break
            except LifecycleCaptureError as exc:
                unreachable = isinstance(exc, CF.OsUnreachable)
                if attempts >= 1 or not (unreachable or re.search(r"HTTP 5\d\d", str(exc))):
                    raise
                attempts += 1
                (self.sleep or __import__("time").sleep)(CF.OS_UNREACHABLE_RETRY_DELAY_SECONDS if unreachable else CF.FREE_RETRY_DELAY_SECONDS)
        retrieved_on = date.today().isoformat()
        self.last_get_at = datetime.now().astimezone().isoformat()
        entry = self._isolate_mail_credentials({"kind": kind, "path": path, "params": params, "response": response,
                                               "retrieved_on": retrieved_on, "retrieved_at": self.last_get_at})
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cache_file.with_name(cache_file.name + ".tmp")
        tmp.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, cache_file)
        self.cache_writes += 1
        return entry["response"], retrieved_on

    def mail_account(self) -> str:
        response, _ = self._cached_get("mail_account", "/mail/account", {}, cache_dir=self._shared(), budget_attr="inbox_calls",
                                       budget_max=self.max_inbox_calls, label="mail account", timeout=30.0)
        email = str(response.get("email") or "").strip().lower()
        if "@" not in email:
            raise LifecycleCaptureError("the claw has no mailbox: GET /mail/account returned no address")
        return email

    def reserve_aliases(self, capture_id: str, domains: list[str], mailbox: str) -> dict[str, str]:
        """The OS registry atomically reserves neutral aliases across workspaces.
        A retry uses the same durable capture id, including after a lost response."""
        payload = {"capture_id": capture_id, "domains": domains}
        data = self._http_post("/mail/lifecycle-aliases/reserve", payload)
        aliases = data.get("aliases")
        if str(data.get("mailbox") or "").lower() != mailbox or not isinstance(aliases, dict):
            raise LifecycleCaptureError("alias reservation returned a different mailbox or no mapping")
        local, _, host = mailbox.partition("@")
        for domain in domains:
            alias = str(aliases.get(domain) or "").lower()
            if not re.fullmatch(re.escape(local) + r"\+[1-9][0-9]@" + re.escape(host), alias):
                raise LifecycleCaptureError("alias reservation returned an invalid neutral alias")
        if len({aliases[d] for d in domains}) != len(domains):
            raise LifecycleCaptureError("alias reservation reused a number for different competitors")
        return {d: str(aliases[d]).lower() for d in domains}

    def _http_post(self, path: str, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        req = urllib.request.Request(f"{self.os_url.rstrip('/')}{path}", data=json.dumps(payload).encode(),
                                     headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, method="POST")
        try:
            for _name, _value in _connection_headers(req.full_url).items():
                req.add_unredirected_header(_name, _value)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                envelope = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raise LifecycleCaptureError(f"alias reservation failed: HTTP {exc.code}; the neutral number pool may be exhausted or unavailable") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise LifecycleCaptureError(f"alias reservation unavailable: {type(exc).__name__}; rerun with the same capture") from exc
        if envelope.get("code") != 200 or not isinstance(envelope.get("data"), dict):
            raise LifecycleCaptureError("alias reservation returned no mapping; rerun with the same capture")
        return envelope["data"]

    def inbox(self, alias: str, since: str) -> tuple[list[dict[str, Any]], str]:
        response, retrieved_on = self._cached_get("inbox", "/mail/inbox", {"to": alias, "since": since, "limit": INBOX_PAGE}, cache_dir=self.cache_dir,
                                                  budget_attr="inbox_calls", budget_max=self.max_inbox_calls, label="inbox listing", timeout=90.0)
        messages = response.get("messages")
        if not isinstance(messages, list):
            raise LifecycleCaptureError("OS inbox response has no messages list")
        self.inbox_checks[alias] = {"checked_at": self.last_get_at, "inbox_since": since, "query_succeeded": True}
        return [m for m in messages if isinstance(m, dict) and m.get("uid")], retrieved_on

    def read_message(self, uid: str) -> dict[str, Any]:
        response, _ = self._cached_get("message", f"/mail/message/{urllib.parse.quote(str(uid))}", {}, cache_dir=self._shared() / "messages",
                                       budget_attr="message_reads", budget_max=self.max_message_reads, label="message read", timeout=90.0)
        return response

    def ledger_totals(self) -> dict[str, Any]:
        counts = {"mail_account": 0, "inbox": 0, "message": 0}
        dates: list[str] = []
        for base in (self.cache_dir, self._shared(), self._shared() / "messages"):
            if not base.is_dir():
                continue
            for digest in sorted(self.touched):
                path = base / f"{digest}.json"
                if not path.is_file():
                    continue
                try:
                    entry = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                kind = entry.get("kind")
                if kind in counts:
                    counts[kind] += 1
                    if entry.get("retrieved_on"):
                        dates.append(str(entry["retrieved_on"]))
        total = sum(counts.values())
        return {**counts, "provider_calls": total, "observations": total,
                "first_retrieved_on": min(dates) if dates else date.today().isoformat(),
                "last_retrieved_on": max(dates) if dates else date.today().isoformat()}


# ── plan and subscriptions ──────────────────────────────────────────────────

def alias_for(mailbox: str, domain: str) -> str:
    """One alias per registrable domain: `lc-coursera-org`, `lc-mural-co`.
    The suffix keeps two competitors with the same brand stem apart."""
    local, _, host = mailbox.partition("@")
    tag = ALIAS_PREFIX + re.sub(r"[^a-z0-9-]", "", registrable_domain(domain).replace(".", "-"))[:48]
    return f"{local}+{tag}@{host}"


def funnel_lineage(item: dict[str, Any]) -> dict[str, Any]:
    """Public attribution; mailbox addresses and submission receipts stay private."""
    return {key: item[key] for key in ("funnel_id", "campaign_refs", "path_refs") if key in item}


def identity_registry(workspace: Path, mailbox: str, aliases: dict[str, str]) -> dict[str, Any]:
    """Reserve ordinary 02 aliases without replacing the stable identities from 05."""
    path = workspace / IDENTITY_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.is_file():
            try:
                registry = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise LifecycleCaptureError("identity registry is not valid JSON") from exc
            if not isinstance(registry, dict) or registry.get("schema_version") != 1 or registry.get("mailbox") != mailbox or not isinstance(registry.get("identities"), list):
                raise LifecycleCaptureError("identity registry needs schema_version 1 and the current research mailbox")
        else:
            registry = {"schema_version": 1, "mailbox": mailbox, "identities": []}
        identities = registry["identities"]
        if any(not isinstance(item, dict) for item in identities):
            raise LifecycleCaptureError("identity registry identities must be objects")
        if len({item.get("alias") for item in identities}) != len(identities):
            raise LifecycleCaptureError("identity registry aliases must be unique")
        for domain, alias in aliases.items():
            matches = [item for item in identities if item.get("alias") == alias]
            if any(item.get("domain") != domain or item.get("funnel_id") is not None
                   or item.get("kind") not in {"lifecycle", "lifecycle_reserved"} for item in matches):
                raise LifecycleCaptureError("ordinary lifecycle alias collides with another research identity")
            # A restored, actually recorded legacy subscription can replace an
            # unused neutral plan alias. Preserve that address's reservation,
            # but keep one current mapping for the domain-scoped receipt hash.
            # Changing a used mapping still invalidates its previous receipt.
            for item in identities:
                if item.get("kind") == "lifecycle" and item.get("domain") == domain and item.get("alias") != alias:
                    item.update(kind="lifecycle_reserved", identity_id="lifecycle-reservation:" + domain + ":" +
                                hashlib.sha256(item["alias"].encode()).hexdigest()[:20])
            if matches:
                matches[0].update(kind="lifecycle", identity_id=f"lifecycle:{domain}")
            else:
                identities.append({"identity_id": f"lifecycle:{domain}", "domain": domain, "funnel_id": None, "alias": alias, "kind": "lifecycle"})
        _write_atomic(path, json.dumps(registry, indent=2, ensure_ascii=False) + "\n")
        return registry


def load_funnel_handoff(workspace: Path, mailbox: str, registry: dict[str, Any]) -> dict[str, Any]:
    """Import only journalled, approved registrations with reserved per-funnel aliases.

    This accepts several funnels for one competitor. It neither creates accounts
    nor relaxes the form/phone rules of ordinary Lifecycle Capture subscriptions.
    """
    path = workspace / FUNNEL_HANDOFF_REL
    if not path.is_file():
        return {"subscriptions": [], "events": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LifecycleCaptureError("funnel lifecycle handoff is not valid JSON") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or not isinstance(raw.get("subscriptions"), list) or not isinstance(raw.get("events", []), list):
        raise LifecycleCaptureError("funnel lifecycle handoff needs schema_version 1, subscriptions and events lists")
    subscriptions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw["subscriptions"]:
        if not isinstance(item, dict):
            raise LifecycleCaptureError("funnel subscription must be an object")
        funnel_id = str(item.get("funnel_id") or "")
        domain = registrable_domain(str(item.get("domain") or ""))
        alias = str(item.get("alias") or "").strip().lower()
        if not funnel_id or not domain or funnel_id in seen:
            raise LifecycleCaptureError("funnel handoff needs one subscription per distinct funnel_id")
        seen.add(funnel_id)
        local, _, host = mailbox.partition("@")
        if not re.fullmatch(re.escape(local) + r"\+\d{2,}@" + re.escape(host), alias):
            raise LifecycleCaptureError("funnel handoff alias must be a numeric plus alias of the research mailbox")
        if not any(identity.get("funnel_id") == funnel_id and identity.get("domain") == domain and identity.get("alias") == alias for identity in registry["identities"]):
            raise LifecycleCaptureError("funnel handoff alias is not reserved for this funnel in the identity registry")
        if not item.get("approval_ref") or not item.get("submission_ref"):
            raise LifecycleCaptureError("funnel handoff requires approval_ref and submission_ref")
        if item.get("kind") not in FUNNEL_KINDS:
            raise LifecycleCaptureError("funnel handoff accepts lead_form, quiz or webinar_registration only")
        try:
            subscribed = date.fromisoformat(str(item.get("subscribed_on") or ""))
        except ValueError as exc:
            raise LifecycleCaptureError("funnel handoff needs a valid subscribed_on date") from exc
        if subscribed > date.today():
            raise LifecycleCaptureError("funnel handoff subscription is in the future")
        entry_url = str(item.get("entry_url") or "")
        if not _URL_RE.fullmatch(entry_url):
            raise LifecycleCaptureError("funnel handoff entry_url needs its approved HTTP(S) form URL")
        for key in ("campaign_refs", "path_refs"):
            if not isinstance(item.get(key), list) or not item[key] or any(not isinstance(ref, str) or not ref for ref in item[key]):
                raise LifecycleCaptureError(f"funnel handoff needs nonempty {key}")
        if item.get("confirmed") is not None and not isinstance(item["confirmed"], bool):
            raise LifecycleCaptureError("funnel handoff confirmed must be boolean or null")
        expectations = item.get("email_expectations", {})
        if not isinstance(expectations, dict) or any(expectations.get(key) is not None and type(expectations[key]) is not bool for key in ("confirmation", "result")):
            raise LifecycleCaptureError("funnel handoff email expectations must be boolean or null")
        if any(expectations.get(key) is not None for key in ("confirmation", "result")) and not str(expectations.get("source_ref") or "").startswith("browser:"):
            raise LifecycleCaptureError("funnel handoff email expectations need a browser observation reference")
        email = _load_script("funnel-email-review.py", "pmr_lifecycle_handoff_email")
        if expectations.get("wait_until") is not None and (email.timestamp(expectations["wait_until"]) is None or
                not any(expectations.get(key) is True for key in ("confirmation", "result")) or
                not str(expectations.get("source_ref") or "").startswith("browser:")):
            raise LifecycleCaptureError("expected email deadline needs an observed timestamp and browser reference")
        if "submission_checks" in item:
            checks = item["submission_checks"]
            if not isinstance(checks, list) or not checks:
                raise LifecycleCaptureError("funnel handoff submission_checks must describe each submitted path")
            for check in checks:
                if not isinstance(check, dict) or not check.get("submission_ref") or email.timestamp(check.get("submitted_at")) is None or check.get("path_id") not in item["path_refs"] or not isinstance(check.get("campaign_refs"), list) or not check["campaign_refs"] or not set(check["campaign_refs"]).issubset(item["campaign_refs"]):
                    raise LifecycleCaptureError("funnel handoff submission check is not attributable to its subscription")
                per_submission = check.get("email_expectations", expectations)
                if not isinstance(per_submission, dict) or any(type(per_submission.get(key)) not in (bool, type(None)) for key in ("confirmation", "result")) or (check.get("confirmed") is not None and type(check["confirmed"]) is not bool):
                    raise LifecycleCaptureError("funnel handoff submission expectations/confirmation must be observed booleans or unknown")
                if any(per_submission.get(key) is not None for key in ("confirmation", "result")) and not str(per_submission.get("source_ref") or "").startswith("browser:"):
                    raise LifecycleCaptureError("funnel handoff submission expectations need their browser source")
                if per_submission.get("wait_until") is not None and (email.timestamp(per_submission["wait_until"]) is None or email.timestamp(per_submission["wait_until"]) < email.timestamp(check["submitted_at"]) or not any(per_submission.get(key) is True for key in ("confirmation", "result"))):
                    raise LifecycleCaptureError("funnel handoff submission email deadline is invalid")
        if item.get("unsubscribed_on") is not None:
            try:
                unsubscribed = date.fromisoformat(item["unsubscribed_on"])
            except (ValueError, TypeError) as exc:
                raise LifecycleCaptureError("funnel handoff has an invalid unsubscribed_on") from exc
            if not subscribed <= unsubscribed <= date.today():
                raise LifecycleCaptureError("funnel handoff has an invalid unsubscribed_on")
        subscriptions.append({**item, "domain": domain, "alias": alias, "confirmed": item.get("confirmed"), "unsubscribed_on": item.get("unsubscribed_on"), "notes": item.get("notes")})
    events: list[dict[str, Any]] = []
    for event in raw.get("events", []):
        if not isinstance(event, dict) or not event.get("event_id") or not event.get("occurred_at") or not event.get("source_ref"):
            raise LifecycleCaptureError("funnel handoff events need event_id, occurred_at and source_ref")
        subscription = next((item for item in subscriptions if item["funnel_id"] == event.get("funnel_id")), None)
        if subscription is None or event.get("alias") != subscription["alias"] or event.get("type") not in ("email_confirmation", "email_result"):
            raise LifecycleCaptureError("funnel handoff event is not attributed to a reserved subscription")
        if not isinstance(event.get("campaign_refs"), list) or not set(event["campaign_refs"]).issubset(subscription["campaign_refs"]):
            raise LifecycleCaptureError("funnel handoff event campaign refs do not match its subscription")
        if event.get("path_id") is not None and event["path_id"] not in subscription["path_refs"]:
            raise LifecycleCaptureError("funnel handoff event path does not match its subscription")
        if event["type"] == "email_confirmation" and event.get("verification_status") == "confirmed":
            subscription["confirmed"] = True
        events.append(event)
    return {"subscriptions": subscriptions, "events": events}


_RESULT_RE = re.compile(r"\b(?:your (?:quiz |assessment |audit |test )?results?|your (?:personalized|personalised) (?:plan|report)|assessment complete|quiz complete)\b", re.IGNORECASE)


def capture_funnel_events(client: OsClient, workspace: Path, handoff: dict[str, Any], *, refresh: bool = False) -> dict[str, Any]:
    """Read same-day confirmation/results without completing section 02.

    --refresh uses a new listing snapshot, even on the same day; message bodies
    remain cached once. Receiving a confirmation is never treated as clicking it.
    """
    runtime = workspace / RUNTIME_REL
    path = runtime / FUNNEL_EVENTS_FILENAME
    previous = json.loads(path.read_text()) if path.is_file() else {"events": []}
    events = {str(event["event_id"]): event for event in previous.get("events", [])}
    events.update({str(event["event_id"]): event for event in handoff["events"]})
    day = date.today().isoformat()
    snapshot_path = runtime / "funnel-mail-snapshot.json"
    snapshot_state = json.loads(snapshot_path.read_text()) if snapshot_path.is_file() else {}
    if snapshot_state.get("day") == day and (not snapshot_state.get("completed") or not refresh):
        snapshot = snapshot_state["snapshot"]
    else:
        snapshot = datetime.now(timezone.utc).strftime("%H%M%S%f") if refresh else "initial"
    _write_atomic(snapshot_path, json.dumps({"day": day, "snapshot": snapshot, "completed": False}))
    client.cache_dir = runtime / "cache" / "funnel-mail" / day / snapshot
    coverage: list[dict[str, Any]] = []
    messages, _ = harvest(client, handoff["subscriptions"], date.today(), coverage)
    for message in messages:
        subscription = next(item for item in handoff["subscriptions"] if item["alias"] == message["alias"])
        body = client.read_message(message["uid"])
        kind = "email_confirmation" if message["is_confirmation"] else "email_result" if _RESULT_RE.search(message["subject"] + "\n" + str(body.get("text") or "")[:1000]) else None
        if kind is None:
            continue
        if not message["received_at"]:
            CF._coverage_gap(coverage, "message", [subscription["domain"]], "confirmation/result arrival time was not observed")
            continue
        digest = hashlib.sha256(f"{subscription['funnel_id']}:{message['uid']}:{kind}".encode()).hexdigest()[:20]
        event_id = f"mail-{digest}"
        if event_id in events and events[event_id].get("verification_status") == "confirmed":
            continue
        events[event_id] = {"event_id": event_id, "type": kind, "funnel_id": subscription["funnel_id"],
                            "path_id": subscription["path_refs"][0] if len(subscription["path_refs"]) == 1 else None,
                            "campaign_refs": subscription["campaign_refs"], "alias": subscription["alias"],
                            "occurred_at": message["received_at"], "source_ref": f"mail:{message['uid']}", "message_ref": message["uid"],
                            "verification_status": "received", "result": {"subject": message["subject"], "excerpt": _excerpt(str(body.get("text") or ""))} if kind == "email_result" else None}
    pending, checks = [], list(previous.get("checks", []))
    email = _load_script("funnel-email-review.py", "pmr_lifecycle_email_review")
    for subscription in handoff["subscriptions"]:
        query = client.inbox_checks.get(subscription["alias"], {})
        check = {"funnel_id": subscription["funnel_id"], "path_refs": subscription["path_refs"],
                       "campaign_refs": subscription["campaign_refs"], "alias": subscription["alias"],
                       "checked_at": query.get("checked_at"), "inbox_since": query.get("inbox_since") or
                           (date.fromisoformat(subscription["subscribed_on"]) - timedelta(days=1)).isoformat(),
                       "query_succeeded": query.get("query_succeeded") is True,
                       "source_ref": f"inbox_snapshot:{day}:{snapshot}"}
        if check not in checks:
            checks.append(check)
        review = email.review(subscription, {"checks": checks, "events": list(events.values())}, harvest_after_days=HARVEST_AFTER_DAYS)
        if review["pending"]:
            reason = ("mailbox_check_failed" if query.get("query_succeeded") is not True else
                      "mailbox_check_time_unknown" if not query.get("checked_at") else review["detail"])
            pending.append({"funnel_id": subscription["funnel_id"], "path_refs": subscription["path_refs"], "alias": subscription["alias"], "reason": reason})
        if review["gaps"]:
            coverage.append({"type": "coverage", **funnel_lineage(subscription), "status": "email_coverage_gap",
                "detail": review["detail"], "gaps": review["gaps"], "unknown": review["unknown"], "terminal": not review["pending"], "tier": "C"})
    result = {"schema_version": 1, "events": sorted(events.values(), key=lambda event: str(event.get("occurred_at") or "")),
              "checks": checks, "pending": pending, "coverage": coverage, "checked_at": datetime.now(timezone.utc).isoformat()}
    _write_atomic(path, json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    _write_atomic(snapshot_path, json.dumps({"day": day, "snapshot": snapshot, "completed": True}))
    return result


def entry_points(workspace: Path, domains: list[str]) -> dict[str, list[str]]:
    """Sign-up, lead-form, pricing and home addresses per competitor from a
    completed Funnel Teardown; the home page otherwise."""
    points: dict[str, list[str]] = {d: [f"https://{d}/"] for d in domains}
    evidence = _load_script("research-evidence.py", "pmr_research_evidence_for_lifecycle_entry_points")
    try:
        outcome = evidence.inspect_section(workspace, "funnel_teardown", require_materialized=False)
    except ValueError:
        return points
    if outcome.get("status") != "completed":
        return points
    try:
        document = json.loads((workspace / FUNNEL_TEARDOWN_EVIDENCE_REL).read_text(encoding="utf-8"))
        rows = document.get("rows") or []
    except (OSError, json.JSONDecodeError, AttributeError):
        return points
    preferred = ("signup_page", "lead_form", "dedicated_landing", "pricing_page", "homepage")
    browser_contract = document.get("schema_version", 1) >= 2
    for domain in domains:
        entries = {r.get("address") for r in rows if isinstance(r, dict) and r.get("type") == "funnel_walk"
                   and r.get("domain") == domain and r.get("role") != "own"}
        pages = []
        for row in rows:
            if not isinstance(row, dict) or row.get("type") != "landing_page" or row.get("domain") != domain or row.get("role") == "own":
                continue
            address = str(row.get("address") or "")
            if not _URL_RE.fullmatch(address) or registrable_domain(urllib.parse.urlsplit(address).hostname or "") != domain:
                continue
            if browser_contract:
                # V2 publishes browser screens without the legacy fetch_status.
                # A personalized result/confirmation is not a sign-up entry.
                if row.get("source") != "browser" or not (row.get("page_type") in preferred or row.get("lead_fields") or address in entries):
                    continue
            elif row.get("fetch_status") != "ok":
                continue
            pages.append(row)
        pages.sort(key=lambda r: (preferred.index(r.get("page_type")) if r.get("page_type") in preferred else len(preferred),
                                  0 if browser_contract else -(r.get("weight") or 0)))
        chosen = [r["address"] for r in pages[:4]]
        if chosen:
            points[domain] = list(dict.fromkeys(chosen + points[domain]))[:5]
    return points


def load_subscriptions(path: Path, domains: list[str], aliases: dict[str, str], planned: dict[str, dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """The agent's subscriptions file, strictly validated. Missing means no
    subscriptions yet. Every alias must be the planned alias of its
    competitor: the capture never uses another address."""
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleCaptureError(f"{path.name} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or not isinstance(raw.get("subscriptions"), list):
        raise LifecycleCaptureError(f"{path.name} must be an object with schema_version 1 and a subscriptions list")
    subscriptions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw["subscriptions"], 1):
        label = f"subscription #{index}"
        if not isinstance(item, dict):
            raise LifecycleCaptureError(f"{label} must be an object")
        domain = registrable_domain(str(item.get("domain") or ""))
        if domain not in domains:
            continue  # recorded for a competitor outside this run; kept in the file, not published here
        if domain in seen:
            raise LifecycleCaptureError(f"{label} subscribes `{domain}` twice")
        seen.add(domain)
        alias = str(item.get("alias") or "").strip().lower()
        if alias != aliases[domain]:
            raise LifecycleCaptureError(f"{label} must use the planned alias {aliases[domain]} (got {item.get('alias')!r})")
        subscribed_on = str(item.get("subscribed_on") or "")
        if not _DATE_RE.match(subscribed_on):
            raise LifecycleCaptureError(f"{label} needs subscribed_on as YYYY-MM-DD")
        try:
            subscribed = date.fromisoformat(subscribed_on)
        except ValueError as exc:
            raise LifecycleCaptureError(f"{label} has an invalid subscribed_on date") from exc
        if subscribed > date.today():
            raise LifecycleCaptureError(f"{label} is subscribed in the future")
        entry_url = str(item.get("entry_url") or "").strip()
        has_reviewed_entry = planned is not None and any(planned[domain].get(key) for key in ("selected", "fallback"))
        if not _URL_RE.match(entry_url) or (not has_reviewed_entry and registrable_domain(urllib.parse.urlsplit(entry_url).hostname or "") != domain):
            raise LifecycleCaptureError(f"{label} needs entry_url as an https address on {domain}")
        kind = str(item.get("kind") or "").strip().lower()
        if kind not in SUBSCRIPTION_KINDS:
            raise LifecycleCaptureError(f"{label} needs kind in {', '.join(SUBSCRIPTION_KINDS)}")
        confirmed = item.get("confirmed", None)
        if confirmed is not None and not isinstance(confirmed, bool):
            raise LifecycleCaptureError(f"{label} has a non-boolean confirmed")
        unsubscribed_on = item.get("unsubscribed_on")
        if unsubscribed_on is not None:
            if not isinstance(unsubscribed_on, str) or not _DATE_RE.match(unsubscribed_on) or not (subscribed <= date.fromisoformat(unsubscribed_on) <= date.today()):
                raise LifecycleCaptureError(f"{label} has an invalid unsubscribed_on date")
        bound_entry = START.subscription_entry({**item, "domain": domain}, planned[domain]) if planned is not None else {}
        subscriptions.append({"domain": domain, "alias": alias, "subscribed_on": subscribed_on, "entry_url": entry_url, "kind": kind, **bound_entry,
                              "confirmed": confirmed, "unsubscribed_on": unsubscribed_on,
                              "notes": " ".join(str(item.get("notes") or "").split())[:240] or None})
    if len({s["alias"] for s in subscriptions}) != len(subscriptions):
        raise LifecycleCaptureError("two subscriptions share one alias; every competitor gets its own")
    skipped: list[dict[str, str]] = []
    for index, item in enumerate(raw.get("skipped") or [], 1):
        if not isinstance(item, dict):
            raise LifecycleCaptureError(f"skipped entry #{index} must be an object")
        domain = registrable_domain(str(item.get("domain") or ""))
        reason = " ".join(str(item.get("reason") or "").split())
        if not domain or not reason:
            raise LifecycleCaptureError(f"skipped entry #{index} needs a domain and a reason")
        if domain not in domains:
            continue
        if domain in seen:
            raise LifecycleCaptureError(f"skipped entry #{index} names `{domain}`, which is also subscribed")
        skipped.append({"domain": domain, "reason": reason[:240]})
    return {"subscriptions": subscriptions, "skipped": skipped}


# ── harvest ─────────────────────────────────────────────────────────────────

def _parse_received(message: dict[str, Any]) -> datetime | None:
    for key in ("received_at", "date"):
        value = message.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            if key == "received_at":
                return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
            return parsedate_to_datetime(value).astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def _excerpt(text: str) -> str:
    """The opening words without any link: confirmation and tracking links
    carry per-recipient tokens and never leave the runtime cache."""
    plain = " ".join(_LINK_RE.sub("[link]", text or "").split())
    return plain[:EXCERPT_CHARS] + ("…" if len(plain) > EXCERPT_CHARS else "")


_ADDRESS_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


PRIVATE_ROW_FIELDS = ("alias", "uid", "message_ref", "source_ref", "approval_ref", "submission_ref")
_MESSAGE_REF_RE = re.compile(r"/mail/message/[^\s\"')\]]+|\buid\s+[A-Za-z0-9_-]+", re.IGNORECASE)
_WELCOME_RE = re.compile(r"\bwelcome\b", re.IGNORECASE)


def private_strings(aliases: Any, mailbox: str) -> tuple[str, ...]:
    """Every spelling of an address that must not be published: the planned
    aliases and the mailbox, plain and percent-encoded (an alias echoed in a
    confirmation link or a server error comes back encoded)."""
    out: list[str] = []
    for value in [*aliases, mailbox]:
        value = str(value or "").strip()
        if not value:
            continue
        out += [value, urllib.parse.quote(value, safe=""), value.replace("+", "%2B").replace("@", "%40"),
                value.replace("@", "%40"), value.replace("+", "%2B")]  # half-encoded spellings a server may echo
    return tuple(dict.fromkeys(out))


def public_text(value: Any, private: tuple[str, ...]) -> Any:
    """Published text never carries an address or a message reference."""
    if isinstance(value, str):
        return _MESSAGE_REF_RE.sub("a message", _scrub(value, private))
    if isinstance(value, list):
        return [public_text(v, private) for v in value]
    if isinstance(value, dict):
        return {k: public_text(v, private) for k, v in value.items()}
    return value


def public_row(row: dict[str, Any], private: tuple[str, ...] = ()) -> dict[str, Any]:
    """The evidence copy of a row: the mailbox alias and the message id stay
    in the runtime folder (plan.json, subscriptions.json, the cache), and
    every published string is scrubbed of addresses and message references."""
    return {k: public_text(v, private) for k, v in row.items() if k not in PRIVATE_ROW_FIELDS}


def public_entry_url(url: str) -> str:
    """The entry point without its query and fragment (a confirmation link
    can carry the address)."""
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _scrub(value: str, aliases: tuple[str, ...]) -> str:
    """No mailbox address in published text: the alias, the mailbox or any
    other address a sender echoes back becomes `[address]`."""
    out = value
    for alias in aliases:
        if alias:
            out = re.sub(re.escape(alias), "[address]", out, flags=re.IGNORECASE)
    return _ADDRESS_RE.sub("[address]", out)


def recipient_addresses(item: dict[str, Any]) -> set[str]:
    """Every address the listing names as a recipient (To and Delivered-To),
    parsed and normalised, so attribution compares whole addresses."""
    found: set[str] = set()
    for field in ("to", "delivered_to"):
        raw = item.get(field)
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            if not isinstance(value, str) or not value.strip():
                continue
            for _, address in getaddresses([value]):
                address = address.strip().lower()
                if "@" in address:
                    found.add(address)
    return found


def message_row(listing: dict[str, Any], body: dict[str, Any], subscription: dict[str, Any], index: int) -> dict[str, Any]:
    text = str(body.get("text") or "")
    aliases = (subscription["alias"], subscription["alias"].partition("+")[0] + "@" + subscription["alias"].partition("@")[2])
    subject = _scrub(" ".join(str(listing.get("subject") or body.get("subject") or "").split()), aliases)
    sender_name, sender_address = parseaddr(str(listing.get("from") or body.get("from") or ""))
    received = _parse_received(listing) or _parse_received(body)
    subscribed = date.fromisoformat(subscription["subscribed_on"])
    # The inbox is asked from the day before the subscription (server days are
    # UTC, the recorded date is local); a message from that margin is day 0.
    day_offset = max(0, (received.date() - subscribed).days) if received else None
    haystack = f"{subject}\n{text}"
    discounts = [int(a or b) for a, b in _DISCOUNT_RE.findall(haystack) if (a or b)]
    prices = list(dict.fromkeys(m.group(0).strip() for m in _PRICE_RE.finditer(haystack)))[:4]
    deadline = _DEADLINE_RE.search(haystack)
    is_confirmation = bool(_CONFIRM_RE.search(subject)) or (index == 1 and
        body.get("mail_content_metrics", {}).get("confirmation_in_prefix", bool(_CONFIRM_RE.search(text[:600]))))
    is_offer = bool(discounts or prices or _FREE_RE.search(haystack))
    kind = "confirmation" if is_confirmation else "offer" if is_offer else "nudge" if _PROGRESS_RE.search(haystack) else "welcome" if index <= 2 else "content"
    is_welcome = kind == "welcome" or (not is_confirmation and bool(_WELCOME_RE.search(subject)))
    return {
        **funnel_lineage(subscription),
        "type": "lifecycle_message", "domain": subscription["domain"], "alias": subscription["alias"], "uid": str(listing.get("uid")),
        "received_at": received.isoformat().replace("+00:00", "Z") if received else None, "day_offset": day_offset,
        "hour_utc": received.hour if received else None, "sender_domain": registrable_domain(sender_address.partition("@")[2]) if "@" in sender_address else None,
        "subject": subject[:200], "kind": kind, "is_confirmation": is_confirmation, "is_offer": is_offer, "is_welcome": is_welcome,
        "discount_percent": max(discounts) if discounts else None, "prices": prices, "free_mention": bool(_FREE_RE.search(haystack)),
        "deadline": deadline.group(0).lower() if deadline else None,
        "unsubscribe_link": body.get("mail_content_metrics", {}).get("unsubscribe_link", bool(_UNSUB_RE.search(text))),
        "links": body.get("mail_content_metrics", {}).get("links", len(_LINK_RE.findall(text))),
        "word_count": body.get("mail_content_metrics", {}).get("word_count", len(text.split())), "tier": "A",
    }


def sequence_end(subscription: dict[str, Any], harvested_on: date) -> date:
    """The last day a sequence is observed: the harvest cutoff, or the
    unsubscribe date when it came first."""
    if subscription.get("unsubscribed_on"):
        return min(harvested_on, date.fromisoformat(subscription["unsubscribed_on"]))
    return harvested_on


def sequence_row(subscription: dict[str, Any], messages: list[dict[str, Any]], harvested_on: date, truncated: bool = False) -> dict[str, Any]:
    subscribed = date.fromisoformat(subscription["subscribed_on"])
    end = sequence_end(subscription, harvested_on)
    days_covered = max(0, (end - subscribed).days)
    offsets = sorted(m["day_offset"] for m in messages if isinstance(m.get("day_offset"), int))
    offers = [m for m in messages if m["is_offer"]]
    gaps = [b - a for a, b in zip(offsets, offsets[1:])]
    kinds = Counter(m["kind"] for m in messages)
    return {
        **funnel_lineage(subscription),
        "type": "lifecycle_sequence", "domain": subscription["domain"], "alias": subscription["alias"], "kind": subscription["kind"],
        "subscribed_on": subscription["subscribed_on"], "harvested_on": harvested_on.isoformat(), "days_covered": days_covered,
        "observation_status": "full" if days_covered >= HARVEST_AFTER_DAYS else "partial", "target_days": HARVEST_AFTER_DAYS,
        "observed_from": subscribed.isoformat(), "observed_through": end.isoformat(),
        "early_harvest_due_on": (subscribed + timedelta(days=EARLY_HARVEST_AFTER_DAYS)).isoformat(),
        "full_harvest_due_on": (subscribed + timedelta(days=HARVEST_AFTER_DAYS)).isoformat(),
        "coverage_complete": not truncated and subscription.get("confirmed") is not False,
        "listing_succeeded": True,
        "messages": len(messages), "messages_per_week": round(len(messages) * 7 / days_covered, 2) if days_covered >= 7 else None,
        "first_message_day": offsets[0] if offsets else None, "last_message_day": offsets[-1] if offsets else None,
        "first_welcome_day": min((m["day_offset"] for m in messages if m.get("is_welcome") and isinstance(m.get("day_offset"), int)), default=None),
        "median_gap_days": sorted(gaps)[len(gaps) // 2] if gaps else None, "confirmations": kinds.get("confirmation", 0),
        "offers": len(offers), "first_offer_day": min((m["day_offset"] for m in offers if isinstance(m.get("day_offset"), int)), default=None),
        "max_discount_percent": max((m["discount_percent"] for m in messages if m["discount_percent"]), default=None),
        "deadlines": sum(1 for m in messages if m["deadline"]), "nudges": kinds.get("nudge", 0),
        "prices": list(dict.fromkeys(p for m in messages for p in m["prices"]))[:6],
        "sender_domains": list(dict.fromkeys(m["sender_domain"] for m in messages if m["sender_domain"]))[:4],
        "unsubscribe_present": any(m["unsubscribe_link"] for m in messages), "subjects": [m["subject"] for m in messages[:8]],
        "listing_truncated": truncated, "tier": "A" if messages else "C",
    }


_PATTERN_LABELS = {
    "double_opt_in": "A confirmation step before the sequence starts",
    "welcome_same_day": "A welcome message within a day",
    "offer_in_first_week": "A paid offer within the first seven days",
    "discount_offered": "A percentage discount is offered",
    "deadline_used": "A deadline or scarcity line is used",
    "nudges_sent": "Progress or come-back nudges are sent",
    "daily_or_more": "Five or more messages a week",
    "weekly_or_less": "At most one message a week",
    "prices_named": "Prices are named inside the emails",
}


def lifecycle_patterns(sequences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active = [s for s in sequences if s["messages"]]
    if not active:
        return []
    hits: dict[str, list[str]] = {k: [] for k in _PATTERN_LABELS}
    for s in active:
        d = s["domain"]
        if s["confirmations"]:
            hits["double_opt_in"].append(d)
        if s.get("first_welcome_day") is not None and s["first_welcome_day"] <= 1:
            hits["welcome_same_day"].append(d)
        if s["first_offer_day"] is not None and s["first_offer_day"] <= 7:
            hits["offer_in_first_week"].append(d)
        if s["max_discount_percent"]:
            hits["discount_offered"].append(d)
        if s["deadlines"]:
            hits["deadline_used"].append(d)
        if s["nudges"]:
            hits["nudges_sent"].append(d)
        if s["days_covered"] >= 7 and (s["messages_per_week"] or 0) >= 5:
            hits["daily_or_more"].append(d)
        elif s["days_covered"] >= 7 and (s["messages_per_week"] or 0) <= 1:
            hits["weekly_or_less"].append(d)
        if s["prices"]:
            hits["prices_named"].append(d)
    rows = []
    for pattern, domains in hits.items():
        if not domains:
            continue
        supporting = [s for s in active if s["domain"] in domains]
        windows = [s for s in supporting if s.get("observed_from") and s.get("observed_through")]
        rows.append({"type": "lifecycle_pattern", "pattern": pattern, "label": _PATTERN_LABELS[pattern], "competitors": sorted(set(domains)),
                     "competitors_with": len(set(domains)), "competitors_total": len({s["domain"] for s in active}), "share": round(len(set(domains)) / len({s["domain"] for s in active}), 2),
                     "recurring": len(set(domains)) >= 2, "eligible": True,
                     "observation_status": "full" if all(s["days_covered"] >= HARVEST_AFTER_DAYS for s in supporting) else "partial",
                     "target_days": HARVEST_AFTER_DAYS, "days_covered": min(s["days_covered"] for s in supporting),
                     "observed_from": min((s["observed_from"] for s in windows), default=None),
                     "observed_through": max((s["observed_through"] for s in windows), default=None),
                     "coverage_complete": all(s.get("coverage_complete", True) for s in supporting),
                     "tier": "B" if len(set(domains)) >= 2 else "C"})
    rows.sort(key=lambda r: (-r["competitors_with"], r["pattern"]))
    return rows


def harvest(client: OsClient, subscriptions: list[dict[str, Any]], harvested_on: date, coverage: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every recorded subscription is harvested, unsubscribed ones included:
    their mail is still in the mailbox and the sequence they produced is the
    evidence. Messages after the harvest day or after the unsubscribe date are
    left out."""
    messages_out: list[dict[str, Any]] = []
    sequences: list[dict[str, Any]] = []
    for subscription in subscriptions:
        if date.fromisoformat(subscription["subscribed_on"]) > harvested_on:
            coverage.append({"type": "coverage", "domain": subscription["domain"], "source": "inbox", "status": "pending",
                             "detail": "subscription had not started at this historical cutoff", "tier": "C"})
            continue
        since = (date.fromisoformat(subscription["subscribed_on"]) - timedelta(days=1)).isoformat()
        try:
            listing, _ = client.inbox(subscription["alias"], since)
        except BudgetExhausted:
            raise
        except LifecycleCaptureError as exc:
            if isinstance(exc, CF.OsUnreachable) or re.search(r"HTTP (?:401|402|403|429)\b", str(exc)):
                raise  # the key, the mailbox or the quota is refused: not a fact about this competitor
            CF._coverage_gap(coverage, "inbox", [subscription["domain"]], CF._provider_detail(exc))
            failed_sequence = sequence_row(subscription, [], harvested_on)
            failed_sequence["coverage_complete"] = False
            failed_sequence["listing_succeeded"] = False
            sequences.append(failed_sequence)
            continue
        alias = subscription["alias"].lower()
        end = sequence_end(subscription, harvested_on)
        kept = []
        for item in listing:
            if alias not in recipient_addresses(item):
                continue  # the server filter is a substring match; keep exact alias hits only
            received = _parse_received(item)
            if received is not None and received.date() > end:
                continue
            kept.append(item)
        truncated = len(listing) >= INBOX_PAGE
        if truncated:
            CF._coverage_gap(coverage, "inbox", [subscription["domain"]],
                             f"the inbox listing returned the newest {INBOX_PAGE} messages since {since}; earlier messages of this sequence may be missing")
        rows: list[dict[str, Any]] = []
        ordered = sorted(kept, key=lambda m: (str(m.get("received_at") or ""), str(m.get("uid"))))
        for index, item in enumerate(ordered, 1):
            try:
                body = client.read_message(str(item["uid"]))
            except BudgetExhausted:
                raise
            except LifecycleCaptureError as exc:
                if not re.search(r"HTTP (?:404|410)\b", str(exc)):
                    raise  # only a message that vanished between the listing and the read is a fact about this sequence
                status_match = re.search(r"HTTP (\d{3})", str(exc))
                CF._coverage_gap(coverage, "message", [subscription["domain"]], f"a message of this sequence could not be read: HTTP {status_match.group(1) if status_match else 'error'}")
                continue
            rows.append(message_row(item, body, subscription, index))
        messages_out.extend(rows)
        sequence = sequence_row(subscription, rows, harvested_on, truncated)
        if any(g.get("domain") == subscription["domain"] and g.get("status") != "ok" for g in coverage):
            sequence["coverage_complete"] = False
        sequences.append(sequence)
    return messages_out, sequences


# ── rendering ───────────────────────────────────────────────────────────────

def _cell(value: Any, cap: int = 90) -> str:
    return CF._cell(value, cap)


def render_section(*, domains: list[str], mailbox_domain: str, subscriptions: list[dict[str, Any]], skipped: list[dict[str, str]],
                   sequences: list[dict[str, Any]], messages: list[dict[str, Any]], patterns: list[dict[str, Any]], coverage: list[dict[str, Any]],
                   phase: str, harvested_on: str | None, totals: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    if phase == "started":
        add(f"Research subscriptions started at {len({s['domain'] for s in subscriptions})} of {len(domains)} competitor(s) with separate plus-addressed aliases on the claw's `@{mailbox_domain}` mailbox; "
            f"the early harvest reads the inbox after {EARLY_HARVEST_AFTER_DAYS} days and the full window after {HARVEST_AFTER_DAYS} days from each actual sign-up.")
    else:
        add(f"Competitor email sequences harvested on {harvested_on}: {len(messages)} message(s) from {sum(1 for s in sequences if s['messages'])} of {len(subscriptions)} subscription(s), "
            f"attributed by the exact subscription alias and, where present, its funnel and campaign references.")
        fully_observed = sequences and len(sequences) == len(subscriptions) and all(s["observation_status"] == "full" for s in sequences)
        pending_signups = any(g.get("source") == "subscription" and g.get("status") == "pending" for g in coverage)
        add("Observation: " + ("full" if fully_observed and not pending_signups else "partial") +
            "; conclusions apply only to the stated observation windows. Full duration does not imply complete inbox coverage.")
    add("")
    add("### Subscriptions")
    add("")
    add("| Competitor | Kind | Entry point | Subscribed on | Confirmed | Status | Notes |")
    add("| --- | --- | --- | --- | --- | --- | --- |")
    for s in subscriptions:
        status = f"unsubscribed {s['unsubscribed_on']}" if s.get("unsubscribed_on") else "active"
        confirmed = "yes" if s.get("confirmed") else "no" if s.get("confirmed") is False else "not observed"
        add(f"| {s['domain']} | {s['kind'].replace('_', ' ')} | {_cell(s['entry_url'].replace('https://', ''), 60)} | {s['subscribed_on']} | {confirmed} | {status} | {_cell(s.get('notes') or '—', 80)} |")
    for s in skipped:
        add(f"| {s['domain']} | — | — | — | — | skipped | {_cell(s['reason'], 80)} |")
    add("")
    if phase == "harvested":
        add("### Sequences by competitor")
        add("")
        add("| Competitor | Observation | Window | Coverage | Days covered | Messages | Per week | First message (day) | First offer (day) | Max discount | Deadlines | Nudges | Prices named |")
        add("| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
        for s in sequences:
            add(f"| {s['domain']} | {s['observation_status']} | {s['observed_from']}..{s['observed_through']} | {'complete' if s['coverage_complete'] else 'gaps'} | {s['days_covered']} | {s['messages']} | {s['messages_per_week'] if s['messages_per_week'] is not None else '—'} | "
                f"{s['first_message_day'] if s['first_message_day'] is not None else '—'} | {s['first_offer_day'] if s['first_offer_day'] is not None else '—'} | "
                f"{str(s['max_discount_percent']) + '%' if s['max_discount_percent'] else '—'} | {s['deadlines']} | {s['nudges']} | {_cell(', '.join(s['prices']) or '—', 60)} |")
        add("")
        for s in sequences:
            rows = [m for m in messages if m["domain"] == s["domain"] and m.get("funnel_id") == s.get("funnel_id")]
            if not rows:
                continue
            add(f"#### {s['domain']}" + (f" — {s['funnel_id']}" if s.get("funnel_id") else ""))
            add("")
            add("| Day | Kind | Subject | Offer or deadline |")
            add("| ---: | --- | --- | --- |")
            for m in rows:
                offer = ", ".join(x for x in ([f"{m['discount_percent']}% off"] if m["discount_percent"] else []) + m["prices"][:2] + ([m["deadline"]] if m["deadline"] else []))
                add(f"| {m['day_offset'] if m['day_offset'] is not None else '—'} | {m['kind']} | {_cell(m['subject'] or '(no subject)', 90)} | {_cell(offer or '—', 60)} |")
            add("")
        add("### Recurring lifecycle patterns")
        add("")
        if patterns:
            add("| Pattern | Competitors | Observation | Share |")
            add("| --- | --- | --- | ---: |")
            for r in patterns:
                add(f"| {r['label']} | {', '.join(r['competitors'])} ({r['competitors_with']} of {r['competitors_total']}) | {r['observation_status']}, {r['days_covered']} days | {int(r['share'] * 100)}% |")
        else:
            add("No message has arrived yet; patterns need at least one harvested sequence.")
        add("")
    add("### Method and policy")
    add("")
    add("- One neutral plus-addressed alias per competitor per capture, reserved uniquely for the mailbox; every message is attributed by an exact To or Delivered-To address match; "
        "stable per-funnel aliases imported from section 05 retain their attribution; the inbox is read through OS by alias and start date, each message body once. Bodies stay in the runtime cache; the section carries subjects, "
        f"and extracted facts. Reads in this cutoff: {totals.get('inbox', 0)} inbox listing(s), {totals.get('message', 0)} message(s).")
    add("- Research sign-ups only: newsletters, free accounts, trials and waitlists that need no payment; no card details, no CAPTCHA bypass, no real "
        "third-party identities; no required phone. A human with verified access to the planned aliases and mailbox signs up, confirms and unsubscribes; never engage sales representatives. Replicate observed offer structure; cadence needs at least a week of observation. Never copy competitor wording or claims.")
    gaps = [g for g in coverage if g.get("status") != "ok"]
    if gaps:
        add("- Not read in this run: " + "; ".join(f"{g['domain']} ({g['detail']})" for g in gaps[:10]) + ".")
    add("")
    add("### Sources")
    add("")
    add("- The claw's mailbox through OS `GET /mail/inbox` (filters `to` and `since`) and `GET /mail/message/{uid}`; subscriptions recorded by the executing agent.")
    return "\n".join(lines).strip() + "\n"


# ── orchestration ───────────────────────────────────────────────────────────

def _arg(args: Any, name: str, default: Any) -> Any:
    value = getattr(args, name, None)
    return default if value is None else value


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def resolve_harvest_day(runtime: Path, override: str, refresh: bool, not_before: date | None = None) -> date:
    """A harvest is a day's snapshot of the inbox: reruns on the same cutoff
    replay the cache; `--refresh` reads the inbox again once the current
    harvest completed."""
    marker = runtime / "harvest-as-of.json"
    try:
        state = json.loads(marker.read_text(encoding="utf-8"))
        current = date.fromisoformat(state["as_of"])
        completed = bool(state.get("completed"))
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        current, completed = None, False
    if override:
        if not _DATE_RE.match(override):
            raise LifecycleCaptureError("--as-of must be YYYY-MM-DD")
        chosen = date.fromisoformat(override)
        if chosen > date.today():
            raise LifecycleCaptureError("--as-of cannot be in the future")
        if not_before is not None and chosen < not_before:
            raise LifecycleCaptureError(f"--as-of cannot be before the first subscription day ({not_before.isoformat()})")
    elif current is None or (completed and (refresh or current < date.today())):
        # A harvest is a day's snapshot: a completed one is replayed only on
        # its own day; the next day's run reads the inbox again.
        chosen = date.today()
    else:
        chosen = current
    if chosen != current:
        completed = False
    _write_atomic(marker, json.dumps({"as_of": chosen.isoformat(), "completed": completed}))
    return chosen


def mark_harvest_completed(runtime: Path, as_of: date) -> None:
    _write_atomic(runtime / "harvest-as-of.json", json.dumps({"as_of": as_of.isoformat(), "completed": True}))


def _plan(mailbox: str, domains: list[str], aliases: dict[str, str], points: dict[str, list[str]], subscriptions_path: Path,
          *, capture_id: str, reviewed: dict[str, dict[str, Any]], previous: dict[str, Any], product_domain: str) -> dict[str, Any]:
    old = {c["domain"]: c for c in previous.get("competitors", []) if isinstance(c, dict) and "domain" in c}
    competitors = []
    for d in domains:
        entry = reviewed.get(d) or ({k: old[d].get(k) for k in ("selected", "fallback", "skip_reason", "discovery_status", "legacy")} if d in old else {})
        urls = [v["entry_url"] for v in (entry.get("selected"), entry.get("fallback")) if v]
        competitors.append({"domain": d, "alias": aliases[d], "entry_points": urls or points.get(d) or [f"https://{d}/"],
                            "discovery_status": "pending", **entry})
    return {
        "schema_version": SCHEMA_VERSION, "section_id": SECTION_ID, "mailbox": mailbox, "subscriptions_path": subscriptions_path.as_posix(),
        "capture_id": capture_id, "product_domain": product_domain, "kinds": list(SUBSCRIPTION_KINDS),
        "early_harvest_after_days": EARLY_HARVEST_AFTER_DAYS, "harvest_after_days": HARVEST_AFTER_DAYS,
        "competitors": competitors,
        "rules": [
            "Assign signups to any authorized human with verified access to the planned aliases and mailbox, regardless of role. Use the planned alias only at the reviewed selected entry or fallback; no payment is allowed. If nobody has that access, leave actions pending.",
            "Never enter a required phone, card or payment details, never bypass a CAPTCHA or bot check, never use a real third-party identity; try a verified fallback or record a skip reason.",
            "The assigned human confirms double opt-in from the inbox and reports the result; the agent records confirmed: true. Never reply to sales representatives.",
            f"Record one entry per competitor in {subscriptions_path.name}: domain, alias, subscribed_on, entry_url, kind, confirmed, notes; competitors you could not subscribe go to `skipped` with a reason.",
            "After the full harvest the assigned human unsubscribes through the link in the emails and reports the actual date; record unsubscribed_on.",
        ],
    }


def subscription_scope(item: dict[str, Any]) -> str:
    return item["domain"] + (":funnel:" + item["funnel_id"] if item.get("funnel_id") else "")


def write_operator_actions(runtime: Path, plan: dict[str, Any], subscriptions: list[dict[str, Any]], skipped: list[dict[str, Any]], harvested_on: str | None,
                           harvested_domains: list[str] | None = None) -> None:
    path = runtime / OPERATOR_ACTIONS_FILENAME
    previous = START.read_object(path)
    actions, harvests = [], []
    for competitor in plan["competitors"]:
        domain = competitor["domain"]
        observed = [s for s in subscriptions if s["domain"] == domain]
        for subscription in observed or [None]:
            scope = subscription_scope(subscription) if subscription else domain
            old = {**previous}
            for key in ("actions", "harvests"):
                old[key] = [{**item, "id": domain + item["id"][len(scope):]}
                            for item in previous.get(key, []) if item.get("id", "").startswith(scope + ":")]
            generated = START.operator_actions({**plan, "competitors": [competitor]}, [subscription] if subscription else [], skipped,
                harvested_on, old, [domain] if scope in (harvested_domains or []) else [])
            for key, output in (("actions", actions), ("harvests", harvests)):
                for item in generated[key]:
                    item["id"] = scope + item["id"][len(domain):]
                    if item.get("blocked_by"):
                        item["blocked_by"] = scope + item["blocked_by"][len(domain):]
                    if subscription:
                        item.update(funnel_lineage(subscription))
                    output.append(item)
    _write_atomic(path, json.dumps({"schema_version": 1, "section_id": SECTION_ID, "capture_id": plan["capture_id"],
        "product_domain": plan.get("product_domain", ""), "actions": actions, "harvests": harvests}, indent=1))


PHASE_FILENAME = "phase.json"


def _previous_phase(runtime: Path) -> str | None:
    """The phase of the last completed publication (a durable marker: the
    receipt itself is reset to pending at the start of every attempt)."""
    try:
        state = json.loads((runtime / PHASE_FILENAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    if state.get("phase") in ("started", "harvested"):
        return str(state["phase"])
    if (runtime / "harvest-as-of.json").is_file():
        return "harvested"
    return None


def _pending(runtime: Path, reason: str, *, extra: dict[str, Any], client: OsClient) -> dict[str, Any]:
    state = {"schema_version": SCHEMA_VERSION, "section_id": SECTION_ID, "status": "pending", "error": None, "reason": reason, **extra,
             "research_context": {"path": (RUNTIME_REL / "input-context.json").as_posix(),
                                  "sha256": hashlib.sha256((runtime / "input-context.json").read_bytes()).hexdigest()},
             "attempt_inbox_calls": client.inbox_calls, "attempt_message_reads": client.message_reads, "attempt_cache_hits": client.cache_hits}
    _write_atomic(runtime / "request.json", json.dumps(state, indent=1))
    return state


def _run(workspace: Path, args: Any) -> dict[str, Any]:
    api_key = (os.environ.get("OS_API_KEY") or "").strip()
    if not api_key:
        raise LifecycleCaptureError("OS_API_KEY is required")
    os_url = (os.environ.get("OS_URL") or DEFAULT_OS_URL).strip() or DEFAULT_OS_URL
    runtime = workspace / RUNTIME_REL
    runtime.mkdir(parents=True, exist_ok=True)
    if bool(_arg(args, "funnel_mail", False)):
        client = OsClient(os_url=os_url, api_key=api_key, cache_dir=runtime / "cache" / "start", shared_dir=runtime / "cache" / "shared",
                          secret_dir=workspace / REPORT_REL.parent / ".local" / SECTION_ID / "mail-cache",
                          max_inbox_calls=int(_arg(args, "max_inbox_calls", MAX_INBOX_CALLS_PER_ATTEMPT)),
                          max_message_reads=int(_arg(args, "max_message_reads", MAX_MESSAGE_READS_PER_ATTEMPT)), key_scope=f"{SECTION_ID}:")
        mailbox = client.mail_account()
        registry = identity_registry(workspace, mailbox, {})
        handoff = load_funnel_handoff(workspace, mailbox, registry)
        result = capture_funnel_events(client, workspace, handoff, refresh=bool(_arg(args, "refresh", False)))
        return {"status": "pending" if result["pending"] or any(not gap.get("terminal") for gap in result["coverage"]) else "completed", "phase": "funnel-mail",
                "events_path": (RUNTIME_REL / FUNNEL_EVENTS_FILENAME).as_posix(), "events": len(result["events"]), "pending": result["pending"],
                "coverage": result["coverage"], "subscriptions": len(handoff["subscriptions"])}
    product_domain = registrable_domain(str(_arg(args, "product_domain", "") or "")) if _arg(args, "product_domain", "") else ""
    max_competitors = max(1, int(_arg(args, "max_competitors", MAX_COMPETITORS)))
    explicit = [d for d in CF.parse_domains(str(_arg(args, "domains", "") or ""), CF.MAX_EXPLICIT_DOMAINS) if d != product_domain]
    evidence = _load_script("research-evidence.py", "pmr_research_evidence_for_lifecycle_capture")
    tiered = evidence.competitor_set_inputs(workspace, consumer=SECTION_ID, cap=MAX_COMPETITORS)
    rejected = evidence.competitor_set_excluded_domains(workspace) - set(explicit)
    discovered = evidence.keyword_inputs(workspace, consumer=SECTION_ID, row_type="competitor_domain", field="domain", cap=MAX_COMPETITORS, exclude=rejected)
    domains: list[str] = []
    domain_sources: dict[str, str] = {}
    for source, candidates in (("explicit", explicit), ("competitor_set", tiered), ("keyword_economics", discovered)):
        for domain in candidates:
            domain = registrable_domain(domain)
            if len(domains) < max_competitors and domain and domain != product_domain and domain not in domains:
                domains.append(domain)
                domain_sources[domain] = source
    if not domains:
        raise LifecycleCaptureError("no competitor domains available: pass --domains, or complete the Competitor Set (or Keyword Economics) section first")

    subscriptions_path = Path(_arg(args, "subscriptions", "") or (runtime / SUBSCRIPTIONS_FILENAME))
    if not subscriptions_path.is_absolute():
        subscriptions_path = workspace / subscriptions_path
    want_harvest = bool(_arg(args, "harvest", False))
    want_start = bool(_arg(args, "start", False))
    client = OsClient(os_url=os_url, api_key=api_key, cache_dir=runtime / "cache" / "start", shared_dir=runtime / "cache" / "shared",
                      secret_dir=workspace / REPORT_REL.parent / ".local" / SECTION_ID / "mail-cache",
                      max_inbox_calls=int(_arg(args, "max_inbox_calls", MAX_INBOX_CALLS_PER_ATTEMPT)),
                      max_message_reads=int(_arg(args, "max_message_reads", MAX_MESSAGE_READS_PER_ATTEMPT)), key_scope=f"{SECTION_ID}:")
    mailbox = client.mail_account()
    previous_plan = START.read_object(runtime / PLAN_FILENAME)
    if previous_plan and previous_plan.get("mailbox") != mailbox:
        raise LifecycleCaptureError("this capture belongs to another mailbox; use a fresh research workspace")
    if previous_plan.get("product_domain") and previous_plan["product_domain"] != product_domain:
        raise LifecycleCaptureError("this capture belongs to another product; use a fresh research workspace")
    marker = START.read_object(runtime / "capture.json")
    capture_id = str(previous_plan.get("capture_id") or marker.get("capture_id") or uuid.uuid4())
    try:
        uuid.UUID(capture_id)
    except ValueError as exc:
        raise LifecycleCaptureError("capture_id must be a UUID") from exc
    # Persist before the network call so a lost reservation response is safely retryable.
    _write_atomic(runtime / "capture.json", json.dumps({"capture_id": capture_id}))
    existing_subscriptions = START.read_object(subscriptions_path)
    active_legacy = {registrable_domain(str(s.get("domain") or "")): str(s.get("alias") or "").strip().lower()
                     for s in existing_subscriptions.get("subscriptions", []) if isinstance(s, dict)}
    legacy_aliases = {c["domain"]: c["alias"] for c in previous_plan.get("competitors", [])
                      if c.get("domain") in domains and active_legacy.get(c["domain"]) == c.get("alias") == alias_for(mailbox, c["domain"])}
    for c in previous_plan.get("competitors", []):
        c["legacy"] = c.get("domain") in legacy_aliases
    reserve_domains = [d for d in domains if d not in legacy_aliases]
    aliases = {**legacy_aliases, **(client.reserve_aliases(capture_id, reserve_domains, mailbox) if reserve_domains else {})}
    if len(set(aliases.values())) != len(aliases):
        raise LifecycleCaptureError("two competitors map to one alias; name them with distinct registrable domains")
    registry = identity_registry(workspace, mailbox, aliases)
    handoff = load_funnel_handoff(workspace, mailbox, registry)
    points = entry_points(workspace, domains)
    discovery_path = Path(_arg(args, "entry_points", "") or (runtime / ENTRY_POINTS_FILENAME))
    if not discovery_path.is_absolute():
        discovery_path = workspace / discovery_path
    reviewed = START.discovery(discovery_path, domains, registrable_domain)
    plan = _plan(mailbox, domains, aliases, points, subscriptions_path, capture_id=capture_id, reviewed=reviewed,
                 previous=previous_plan, product_domain=product_domain)
    plan["imported_funnel_subscriptions"] = handoff["subscriptions"]
    imported_domains = {item["domain"] for item in handoff["subscriptions"] if item["domain"] in domains}
    _write_atomic(runtime / PLAN_FILENAME, json.dumps(plan, indent=1, ensure_ascii=False))
    signup_plan = {**plan, "competitors": [c for c in plan["competitors"] if c["domain"] not in imported_domains]}
    signup_list = START.render_signups(signup_plan)
    for item in handoff["subscriptions"]:
        if item["domain"] in imported_domains:
            signup_list += f"\n## {item['domain']} — {item['funnel_id']}\n\nAlready registered through approved section 05; do not register again.\nAddress: `{item['alias']}`\nEntry: {item['entry_url']}\n"
    _write_atomic(runtime / "lifecycle-signups.md", signup_list)
    planned = {c["domain"]: c for c in plan["competitors"]}
    recorded = load_subscriptions(subscriptions_path, domains, aliases, planned)
    if imported_domains:
        recorded = recorded or {"subscriptions": [], "skipped": []}
        recorded["subscriptions"].extend(item for item in handoff["subscriptions"] if item["domain"] in domains)
        recorded["skipped"] = [item for item in recorded["skipped"] if item["domain"] not in imported_domains]
    phase_marker = START.read_object(runtime / PHASE_FILENAME)
    previous_windows = phase_marker.get("subscription_windows") or {}
    old_scopes = phase_marker.get("harvested_scopes", phase_marker.get("harvested_domains", []))
    still_observed = [subscription_scope(s) for s in (recorded or {}).get("subscriptions", [])
                      if subscription_scope(s) in old_scopes
                      and previous_windows.get(subscription_scope(s)) == {"alias": s["alias"], "subscribed_on": s["subscribed_on"]}]
    write_operator_actions(runtime, plan, (recorded or {}).get("subscriptions", []), (recorded or {}).get("skipped", []),
                           phase_marker.get("harvested_on"), still_observed)
    accounted = {s["domain"] for s in (recorded or {}).get("subscriptions", [])} | {s["domain"] for s in (recorded or {}).get("skipped", [])}
    missing = [d for d in domains if d not in accounted]
    skipped_domains = {s["domain"] for s in (recorded or {}).get("skipped", [])}
    discovery_missing = [d for d in domains if d not in skipped_domains and d not in imported_domains and planned[d].get("discovery_status") != "reviewed" and not planned[d].get("legacy")]
    if discovery_missing and not (want_harvest and (recorded or {}).get("subscriptions")):
        return _pending(runtime, "awaiting reviewed entry-point discovery", extra={"capture_id": capture_id,
                        "plan_path": (RUNTIME_REL / PLAN_FILENAME).as_posix(), "subscriptions_path": subscriptions_path.as_posix(),
                        "entry_points_path": discovery_path.as_posix(), "missing_entry_points": discovery_missing,
                        "unsubscribed": missing, "mailbox_domain": mailbox.partition("@")[2]}, client=client)
    if recorded is None or missing:
        if want_harvest and not (recorded or {}).get("subscriptions"):
            raise LifecycleCaptureError("harvest needs at least one recorded subscription first")
        if not want_harvest:
            return _pending(runtime, "awaiting research subscriptions for the planned aliases",
                        extra={"plan_path": (RUNTIME_REL / PLAN_FILENAME).as_posix(), "subscriptions_path": subscriptions_path.as_posix(),
                               "capture_id": capture_id, "unsubscribed": missing or domains, "mailbox_domain": mailbox.partition("@")[2]}, client=client)
    subscriptions, skipped = recorded["subscriptions"], recorded["skipped"]
    coverage: list[dict[str, Any]] = []
    for d in missing:
        coverage.append({"type": "coverage", "domain": d, "source": "subscription", "status": "pending",
                         "detail": "entry-point discovery is pending; no observation window has started" if d in discovery_missing
                         else "human sign-up is pending; no observation window has started", "tier": "C"})
    # The first run with every competitor recorded publishes the subscriptions
    # (phase started); later runs harvest. Flags override that order.
    previously = _previous_phase(runtime)
    if want_harvest:
        phase = "harvested"
    elif previously == "harvested":
        phase = "harvested"  # A start refresh must never erase an already observed sequence.
    elif want_start or previously is None:
        phase = "started"
    else:
        phase = "harvested"
    if phase == "harvested" and not subscriptions:
        phase = "started"
    harvested_on: date | None = None
    messages: list[dict[str, Any]] = []
    sequences: list[dict[str, Any]] = []
    patterns: list[dict[str, Any]] = []
    if phase == "harvested":
        requested_as_of = str(_arg(args, "as_of", "") or "")
        if requested_as_of and phase_marker.get("harvested_on") and requested_as_of < phase_marker["harvested_on"]:
            raise LifecycleCaptureError("--as-of cannot replace a newer published harvest; read its private snapshot instead")
        harvested_on = resolve_harvest_day(runtime, str(_arg(args, "as_of", "") or ""), bool(_arg(args, "refresh", False)),
                                           not_before=min(date.fromisoformat(s["subscribed_on"]) for s in subscriptions))
        client.cache_dir = runtime / "cache" / "harvest" / harvested_on.isoformat()
        messages, sequences = harvest(client, subscriptions, harvested_on, coverage)
        patterns = lifecycle_patterns(sequences)
    else:
        coverage.append({"type": "coverage", "domain": "all", "source": "inbox", "status": "pending",
                         "detail": f"subscriptions started; the inbox is harvested after {EARLY_HARVEST_AFTER_DAYS} days for early evidence and {HARVEST_AFTER_DAYS} days for the full window", "tier": "C"})
    for s in skipped:
        CF._coverage_gap(coverage, "subscription", [s["domain"]], f"skipped: {s['reason']}")
    totals = client.ledger_totals()
    if totals["observations"] == 0:
        raise LifecycleCaptureError("no OS mail call succeeded; rerun later")
    if phase == "harvested" and totals["inbox"] == 0:
        raise LifecycleCaptureError("no inbox listing succeeded in this harvest; rerun later")

    private = private_strings([*aliases.values(), *(item["alias"] for item in subscriptions)], mailbox)
    subscription_rows = [public_row({**funnel_lineage(s), "type": "subscription", "domain": s["domain"], "kind": s["kind"], "entry_url": public_entry_url(s["entry_url"]),
                                     "entry_host": registrable_domain(urllib.parse.urlsplit(s["entry_url"]).hostname or ""), "subscribed_on": s["subscribed_on"],
                                     "entry_type": s.get("entry_type"), "source_url": public_entry_url(s.get("source_url") or s["entry_url"]),
                                     "early_harvest_due_on": (date.fromisoformat(s["subscribed_on"]) + timedelta(days=EARLY_HARVEST_AFTER_DAYS)).isoformat(),
                                     "full_harvest_due_on": (date.fromisoformat(s["subscribed_on"]) + timedelta(days=HARVEST_AFTER_DAYS)).isoformat(),
                                     "confirmed": s["confirmed"], "unsubscribed_on": s.get("unsubscribed_on"), "status": "unsubscribed" if s.get("unsubscribed_on") else "active",
                                     "notes": s.get("notes"), "tier": "A"}, private) for s in subscriptions]
    sequences = [public_row(r, private) for r in sequences]
    messages = [public_row(r, private) for r in messages]
    patterns = [public_row(r, private) for r in patterns]
    coverage = [public_row(r, private) for r in coverage]
    skipped = [public_text(s, private) for s in skipped]
    rows = subscription_rows + sequences + messages + patterns + coverage
    observation = {
        "observation_status": "pending" if phase == "started" else "full" if sequences and not missing and len(sequences) == len(subscriptions) and all(s["observation_status"] == "full" for s in sequences) else "partial",
        "target_days": HARVEST_AFTER_DAYS,
        "observed_from": min((s["observed_from"] for s in sequences), default=None),
        "observed_through": harvested_on.isoformat() if harvested_on else None,
        "days_covered": min((s["days_covered"] for s in sequences), default=0),
        "coverage_complete": bool(sequences) and not missing and not skipped and len(sequences) == len(subscriptions) and all(s["coverage_complete"] for s in sequences),
        "early_harvest_due_on": min((s["early_harvest_due_on"] for s in subscription_rows), default=None),
        "full_harvest_due_on": max((s["full_harvest_due_on"] for s in subscription_rows), default=None),
    }
    retrieved_on = totals["first_retrieved_on"] if totals["first_retrieved_on"] == totals["last_retrieved_on"] else f"{totals['first_retrieved_on']}..{totals['last_retrieved_on']}"
    evidence_doc = {
        "schema_version": SCHEMA_VERSION, "section_id": SECTION_ID, "generated_by": "run-lifecycle-capture.py", "retrieved_on": retrieved_on,
        "inputs": {"domains": domains, "domain_sources": domain_sources, "product_domain": product_domain, "mailbox_domain": mailbox.partition("@")[2],
                   "capture_id": capture_id, "phase": phase, "harvested_on": harvested_on.isoformat() if harvested_on else None,
                   "harvest_after_days": HARVEST_AFTER_DAYS, "early_harvest_after_days": EARLY_HARVEST_AFTER_DAYS, **observation},
        "rows": rows,
        "totals": {**totals, "subscriptions": len(subscriptions), "skipped": len(skipped), "messages": len(messages), "patterns": len(patterns)},
    }
    evidence_json = json.dumps(evidence_doc, indent=1, ensure_ascii=False)
    _write_atomic(workspace / EVIDENCE_REL, evidence_json)
    section_markdown = render_section(domains=domains, mailbox_domain=mailbox.partition("@")[2], subscriptions=subscription_rows, skipped=skipped, sequences=sequences,
                                      messages=messages, patterns=patterns, coverage=coverage, phase=phase,
                                      harvested_on=harvested_on.isoformat() if harvested_on else None, totals=totals)
    _write_atomic(runtime / "result.md", section_markdown)
    upsert = _load_script("upsert-markdown-section.py", "pmr_upsert_markdown_section_for_lifecycle_capture")
    report_path = workspace / REPORT_REL
    report_path.parent.mkdir(parents=True, exist_ok=True)
    upsert.upsert_markdown_section(report_path, SECTION_HEADING, section_markdown)
    persist = _load_script("persist-research-report.py", "pmr_persist_research_report_for_lifecycle_capture")
    persistence = persist.persist_research_report(workspace, commit_message=f"research: update {SECTION_HEADING.lower()} section",
                                                  extra_paths=(Path(_artifact_path("egbe-docs/research/market/evidence/lifecycle-capture.json")),))
    io = _load_script("research-artifact-io.py", "pmr_artifact_io_for_lifecycle_capture")
    state = {
        "schema_version": SCHEMA_VERSION, "section_id": SECTION_ID, "status": "completed", "error": None, "phase": phase,
        "capture_id": capture_id, **observation,
        "domains": domains, "domain_sources": domain_sources, "product_domain": product_domain, "mailbox_domain": mailbox.partition("@")[2],
        "harvested_on": harvested_on.isoformat() if harvested_on else None, "subscriptions": len(subscriptions), "skipped": len(skipped),
        "messages": len(messages), "patterns": len(patterns), "provider_calls": totals["provider_calls"], "observations": totals["observations"],
        "inbox_calls": totals["inbox"], "message_reads": totals["message"],
        "attempt_inbox_calls": client.inbox_calls, "attempt_message_reads": client.message_reads, "attempt_cache_hits": client.cache_hits,
        "subscriptions_sha256": hashlib.sha256(subscriptions_path.read_bytes()).hexdigest() if subscriptions_path.is_file() else None,
        "funnel_handoff_sha256": hashlib.sha256((workspace / FUNNEL_HANDOFF_REL).read_bytes()).hexdigest() if (workspace / FUNNEL_HANDOFF_REL).is_file() else None,
        "identity_registry_binding": _load_script("research_integrity.py", "pmr_lifecycle_identity_integrity").identity_binding(
            registry, lifecycle_domains=domains, funnel_ids=[s["funnel_id"] for s in subscriptions if s.get("funnel_id")]),
        "research_context": io.context_binding(workspace, SECTION_ID),
        "publication_mode": persistence.publication_mode, "report_commit_sha": persistence.commit_sha,
        "evidence_path": EVIDENCE_REL.as_posix(), "evidence_sha256": hashlib.sha256(evidence_json.encode("utf-8")).hexdigest(),
        "result_path": (RUNTIME_REL / "result.md").as_posix(), "result_sha256": hashlib.sha256(section_markdown.encode("utf-8")).hexdigest(),
    }
    _write_atomic(runtime / "request.json", json.dumps(state, indent=1))
    successful_scopes = [subscription_scope(s) for s in sequences if s["listing_succeeded"]]
    successful_domains = sorted({s["domain"] for s in sequences if s["listing_succeeded"]})
    _write_atomic(runtime / PHASE_FILENAME, json.dumps({"phase": phase, "published_on": date.today().isoformat(),
                    "harvested_on": harvested_on.isoformat() if harvested_on else phase_marker.get("harvested_on"),
                    "harvested_domains": successful_domains if harvested_on else sorted({s["domain"] for s in subscriptions if subscription_scope(s) in still_observed}),
                    "harvested_scopes": successful_scopes if harvested_on else still_observed,
                    "subscription_windows": {subscription_scope(s): {"alias": s["alias"], "subscribed_on": s["subscribed_on"]} for s in subscriptions}
                    if harvested_on else previous_windows}))
    if harvested_on is not None:
        mark_harvest_completed(runtime, harvested_on)
        write_operator_actions(runtime, plan, subscriptions, recorded["skipped"], harvested_on.isoformat(), successful_scopes)
    # Immutable private provenance for handed-over packs, even for multiple revisions on one day.
    snapshot = runtime / "snapshots" / (harvested_on or date.today()).isoformat() / state["evidence_sha256"]
    for name, contents in (("evidence.json", evidence_json), ("result.md", section_markdown), ("request.json", json.dumps(state, indent=1))):
        path = snapshot / name
        if not path.exists():
            _write_atomic(path, contents)
    return state


def run(workspace: Path, args: Any) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    io = _load_script("research-artifact-io.py", "pmr_artifact_io")
    if bool(_arg(args, "funnel_mail", False)):
        # A same-day mailbox check is a 05 continuation, not a publication or
        # a failed/completed receipt for the independent section 02 capture.
        with io.file_lock(workspace / RUNTIME_REL / ".run.lock", timeout=1):
            io.bind_context(workspace, SECTION_ID, context_file=getattr(args, "context_file", None))
            return _run(workspace, args)
    with io.section_attempt(workspace, SECTION_ID, context_file=getattr(args, "context_file", None)):
        try:
            return _run(workspace, args)
        except ValueError as exc:
            raise LifecycleCaptureError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--context-file", type=Path, help="Optional selected research context; existing snapshots are reused on resume.")
    parser.add_argument("--domains", default="", help="Comma-separated competitor domains; merged ahead of the Competitor Set and Keyword Economics domains.")
    parser.add_argument("--product-domain", default="", help="The product's own domain; never subscribed to as a competitor.")
    parser.add_argument("--max-competitors", type=int, default=MAX_COMPETITORS)
    parser.add_argument("--subscriptions", default="", help=_artifact_path(f"Path to the subscriptions file (default egbe-docs/research/market/work/{SECTION_ID}/{SUBSCRIPTIONS_FILENAME})."))
    parser.add_argument("--entry-points", default="", help="Reviewed entry discovery JSON (default: the private runtime entry-points.json).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--funnel-mail", action="store_true", help="Read confirmations/results for imported 05 aliases today; writes runtime events only, without completing 02.")
    mode.add_argument("--start", action="store_true", help="Publish recorded subscriptions before the first harvest; later refreshes preserve the harvested phase.")
    mode.add_argument("--harvest", action="store_true", help="Read the inbox by alias and publish the sequences (the default once subscriptions are recorded).")
    parser.add_argument("--as-of", default="", help="Harvest day YYYY-MM-DD (default: today for a new harvest, kept across reruns).")
    parser.add_argument("--refresh", action="store_true", help="For --funnel-mail, refresh today’s inbox listing; for ordinary harvest, advance a completed daily snapshot.")
    parser.add_argument("--max-inbox-calls", type=int, default=MAX_INBOX_CALLS_PER_ATTEMPT)
    parser.add_argument("--max-message-reads", type=int, default=MAX_MESSAGE_READS_PER_ATTEMPT)
    args = parser.parse_args()
    try:
        state = run(args.workspace, args)
    except (LifecycleCaptureError, ValueError) as exc:
        print(f"{DISPLAY_NAME}: {exc}", file=sys.stderr)
        return 1
    if state.get("phase") == "funnel-mail":
        print(json.dumps(state, indent=1))
        return 2 if state["status"] == "pending" else 0
    if state["status"] == "pending":
        print(f"{DISPLAY_NAME}: {state['reason']} — read {state['plan_path']} and the lifecycle workflow; "
              f"the assigned human's results go in {state['subscriptions_path']}. Continue other research while waiting.", file=sys.stderr)
        return 2
    print(json.dumps({k: state[k] for k in ("status", "phase", "domains", "subscriptions", "skipped", "messages", "patterns")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
