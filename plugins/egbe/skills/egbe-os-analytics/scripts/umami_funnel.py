#!/usr/bin/env python3
"""Collect Umami evidence and report per-session stage observations, not conversions.

Stdlib-only. Auth: project-local .env.local (OS_URL / OS_API_KEY), or environment.
Run from the project root, with the complete Egbe catalog installed.

  python3 umami_funnel.py [--site <name-domain-or-id>] [--since 2026-07-01]
      [--until 2026-08-01]
      [--act-path /color] [--act-start-event generation_started]
      [--act-event activated]
      [--events-json evidence/events.json] [--json analysis/funnel.json]
  python3 umami_funnel.py --from-events evidence/events.json --json analysis/replay.json

Output: totals (included vs excluded), traffic mix, depth/bounce, top paths,
custom events, stage counts, per-source sessions/arrivals, and compact,
filtered journeys for sessions with activity or exposure events. Raise
`--max-journey-events` when a longer timeline is needed. Repeated completion
events and a small allowlist of non-PII event properties are preserved by
joining Umami's paged event-data endpoint to event rows. Paths and canonical
visitor/visit IDs are anonymized before output. Exclude confirmed internal
activity and disclose suspects; completion is a technical proxy, never proof
of usable value. Filtering is described in references/data-recipes.md.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import runpy
import sys
import time
import urllib.parse
import urllib.error
import urllib.request

PAGE_SIZE, MAX_EVENT_PAGES = 500, 200
SIGNUP_PATHS = ("/signup", "/register", "/ru/signup", "/#/join")
POST_AUTH_PATHS = ("/dashboard", "/#/dashboard", "/#/app", "/account", "/admin")
CHECKOUT_PATHS = ("/checkout",)
PRICING_PATHS = ("/pricing", "/#pricing", "/#plans")
ENGAGE_EVENTS = {"campaign-visit", "engagement-scroll", "engagement-time", "engagement-click"}
EXPOSURE_EVENTS = {"section_view", "scroll_depth"}
SIGNUP_START_EVENTS = {"signup_started"}
SIGNUP_DONE_EVENTS = {"signup_completed"}
CHECKOUT_EVENTS = {"checkout_started"}
PAYWALL_EVENTS = {"paywall_view"}
TECHNICAL_START_EVENTS = {
    "main_action_submit", "quiz_start", "request_form_start", "activation_started",
}
TECHNICAL_DONE_EVENTS = {
    "activated", "main_action_success", "quiz_complete", "activation_completed",
}
SAFE_EVENT_FIELDS = {
    "button", "cta", "action", "plan", "surface", "status", "hq",
    "activation_type", "style", "room_type", "op", "count", "product_slug",
    "cta_id", "cta_role", "button_id", "button_role", "input_type",
    "result_type", "duration_ms", "checkout_type", "currency", "amount_cents",
    "price_cents", "plan_name", "section", "percent", "thresholdSeconds", "position",
}
NUMERIC_EVENT_FIELDS = {
    "count", "duration_ms", "amount_cents", "price_cents",
    "percent", "thresholdSeconds", "position",
}
BOOLEAN_EVENT_FIELDS = {"hq"}
IDENTITY_EVENT_FIELDS = {"visitor_id", "visit_id"}
ASSET_PATH_PREFIXES = ("/_next", "/favicon", "/assets", "/static/")
SENSITIVE_PATH_PARENTS = {
    "u", "user", "users", "r", "share", "invite", "reset", "verify",
    "magic", "token", "session", "sessions",
}
EMAIL_ANY_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
JWT_RE = re.compile(r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
URL_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S+|\bwww\.\S+", re.IGNORECASE)
LONG_HEX_RE = re.compile(r"^[0-9a-f]{20,}$", re.IGNORECASE)
BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]{24,}$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
LONG_NUMBER_RE = re.compile(r"(?<!\d)\+?\d[\d .()-]{6,}\d(?!\d)")
SNAPSHOT_FORMAT = "egbe-umami-events.v1"
SAFE_UTM_FIELDS = ("utm_source", "utm_medium", "utm_campaign", "utm_content")
ANALYSIS_OPTIONS = (
    "act_event", "act_start_event", "act_path", "internal_sources",
    "internal_country", "dc_country", "max_journey_events",
)


def os_connection():
    root = Path(__file__).resolve().parents[1]
    quickstart = "egbe-os-quickstart" if root.name.startswith("egbe-os-") else "quickstart"
    helper_path = root.parent / quickstart / "scripts/egbe-curl.py"
    if not helper_path.is_file():
        sys.exit("Install the complete Egbe catalog through quickstart before collecting analytics")
    helper = runpy.run_path(str(helper_path))
    settings = Path.cwd() / ".env.local"
    try:
        env = helper["project_environment"](str(settings) if settings.exists() else None)
        base, key = env.get("OS_URL", "").rstrip("/"), env.get("OS_API_KEY", "")
        parsed = urllib.parse.urlsplit(base)
        if not key or not parsed.hostname or parsed.scheme not in {"http", "https"} or parsed.query or parsed.fragment or parsed.username:
            raise ValueError("OS_URL and OS_API_KEY are required")
        args = helper["command"]([base + "/analytics"], env)
        headers = dict(args[i + 1].split(": ", 1) for i, arg in enumerate(args) if arg == "-H")
        headers["Authorization"] = "Bearer " + key
        return base, headers
    except (ValueError, OSError):
        sys.exit("Check OS_URL / OS_API_KEY in .env.local and this agent's quickstart connection identity")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward project credentials to a redirected host.


def call(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"OS analytics returned HTTP {error.code}; check access, app registration and OS release") from None
    if not isinstance(result, dict) or result.get("code") != 200 or "data" not in result:
        raise ValueError("Invalid OS analytics response envelope")
    return result["data"]


def event_property_value(prop):
    for key in ("stringValue", "numberValue", "dateValue"):
        if prop.get(key) is not None:
            return prop[key]
    return None


def ephemeral_ref(kind, value, salt):
    if not isinstance(value, (str, int, float)) or not str(value):
        return None
    digest = hashlib.sha256(
        salt + b"\0" + kind.encode("utf-8") + b"\0" + str(value).encode("utf-8")
    ).hexdigest()
    return digest[:12]


def looks_opaque_token(value):
    """Distinguish likely secrets/IDs from ordinary long semantic slugs."""
    if not isinstance(value, str):
        return False
    if LONG_HEX_RE.fullmatch(value) or JWT_RE.fullmatch(value):
        return True
    if not BASE64URL_RE.fullmatch(value):
        return False
    chunks = re.split(r"[-_]", value)
    mixed_chunks = [
        chunk for chunk in chunks
        if any(char.isalpha() for char in chunk)
        and any(char.isdigit() for char in chunk)
    ]
    secret_prefix = (
        len(chunks) >= 2
        and ((chunks[0] in {"sk", "pk", "rk"} and chunks[1] in {"live", "test", "prod"})
             or chunks[:2] in (["api", "key"], ["access", "token"]))
    )
    if (secret_prefix
            or any(len(chunk) >= 12 for chunk in mixed_chunks)
            or (len(mixed_chunks) >= 2 and sum(map(len, mixed_chunks)) >= 12)):
        return True
    if len(chunks) > 1 and all(
            re.fullmatch(r"[a-z0-9]{1,16}", chunk) for chunk in chunks):
        # Preserve readable kebab/snake-case route and event labels.
        return False
    compact = value.replace("-", "").replace("_", "")
    classes = sum((
        any(char.islower() for char in compact),
        any(char.isupper() for char in compact),
        any(char.isdigit() for char in compact),
    ))
    return (classes >= 2 and len(set(compact)) >= 8) or len(set(compact)) >= 16


def safe_event_value(key, value):
    """Return a short scalar only when its value has no obvious PII/secret."""
    if isinstance(value, bool):
        return value if key in BOOLEAN_EVENT_FIELDS else None
    if isinstance(value, (int, float)):
        return value if key in NUMERIC_EVENT_FIELDS and (
            isinstance(value, int) or math.isfinite(value)
        ) else None
    if not isinstance(value, str):
        return None
    if len(value) > 120 or CONTROL_RE.search(value):
        return None
    inspected = urllib.parse.unquote_plus(value)
    if key in NUMERIC_EVENT_FIELDS:
        return value if re.fullmatch(r"-?\d+(?:\.\d+)?", inspected) else None
    if key in BOOLEAN_EVENT_FIELDS:
        return value if inspected.lower() in {"true", "false"} else None
    if (EMAIL_ANY_RE.search(inspected) or URL_RE.search(inspected)
            or UUID_RE.search(inspected) or JWT_RE.search(inspected)
            or LONG_NUMBER_RE.search(inspected)):
        return None
    for candidate in re.findall(r"[A-Za-z0-9_-]{20,}", inspected):
        if looks_opaque_token(candidate):
            return None
    return value


def parse_event_properties(properties, identity_salt):
    """Extract a strict safe allowlist and ephemeral identity references."""
    safe, identity_refs = {}, {}
    for prop in properties if isinstance(properties, list) else []:
        if not isinstance(prop, dict):
            continue
        key = prop.get("dataKey")
        value = event_property_value(prop)
        if key in SAFE_EVENT_FIELDS:
            safe_value = safe_event_value(key, value)
            if safe_value is not None:
                safe[key] = safe_value
        elif key in IDENTITY_EVENT_FIELDS:
            ref = ephemeral_ref(key, value, identity_salt)
            if ref:
                identity_refs[key] = ref
    return safe, identity_refs


def fetch_event_data(base, app_slug, headers, start, end):
    """Fetch bulk Umami event data, retaining only safe fields and hashed IDs."""
    safe_by_event, identity_by_event, seen = {}, {}, set()
    identity_salt = os.urandom(16)
    page, expected_count, status, error_type = 1, 0, "available", None
    while page <= MAX_EVENT_PAGES:
        query = urllib.parse.urlencode({
            "startAt": start, "endAt": end, "page": page, "pageSize": PAGE_SIZE,
        })
        try:
            response = call(
                f"{base}/analytics/{app_slug}/event-data?{query}", headers,
            )
        except Exception as error:  # Keep base funnel usable when enrichment fails.
            status = "partial" if seen else "unavailable"
            error_type = type(error).__name__
            break
        if not isinstance(response, dict):
            status, error_type = "partial" if seen else "unavailable", "invalid_response"
            break
        entries = response.get("data", [])
        if not isinstance(entries, list):
            status, error_type = "partial" if seen else "unavailable", "invalid_data"
            break
        try:
            expected_count = int(response.get("count", expected_count or 0) or 0)
        except (TypeError, ValueError):
            status, error_type = "partial" if seen else "unavailable", "invalid_count"
            break
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("eventId"):
                continue
            event_id = str(entry["eventId"])
            safe, identity_refs = parse_event_properties(
                entry.get("eventProperties", []), identity_salt,
            )
            safe_by_event[event_id] = safe
            identity_by_event[event_id] = identity_refs
            seen.add(event_id)
        if not entries:
            if len(seen) < expected_count:
                status = "partial" if seen else "unavailable"
                error_type = "empty_page"
            break
        if len(seen) >= expected_count:
            break
        if len(entries) < PAGE_SIZE:
            status = "partial" if seen else "unavailable"
            error_type = "short_page"
            break
        page += 1
    if page > MAX_EVENT_PAGES and len(seen) < expected_count:
        status, error_type = "partial", "page_limit"
    return safe_by_event, identity_by_event, {
        "status": status,
        "reported_events": expected_count,
        "fetched_events": len(seen),
        "error_type": error_type,
    }


def attach_event_data(rows, base, app_slug, headers, start, end, skip=False):
    marked = sum(bool(row.get("hasData")) for row in rows)
    if skip:
        return {
            "status": "skipped", "reported_events": None, "fetched_events": 0,
            "marked_rows": marked, "matched_rows": 0, "error_type": None,
        }
    safe_by_event, identity_by_event, status = fetch_event_data(
        base, app_slug, headers, start, end,
    )
    matched = 0
    for row in rows:
        event_id = str(row.get("id") or "")
        if event_id in safe_by_event:
            row["eventData"] = safe_by_event[event_id]
            row["eventIdentityRefs"] = identity_by_event.get(event_id, {})
            row["_eventDataLoaded"] = True
            matched += 1
        elif row.get("hasData"):
            row["_eventDataLoaded"] = False
    return {**status, "marked_rows": marked, "matched_rows": matched}


def fetch_events(args):
    args.window = getattr(args, "window", None) or resolve_window(args)
    start, end = args.window["startAt"], args.window["endAt"]
    base, headers = os_connection()
    sites = call(f"{base}/analytics", headers)
    if not isinstance(sites, list) or any(not isinstance(s, dict) for s in sites):
        sys.exit("invalid OS analytics site list")
    if args.site:
        query = args.site.casefold()
        exact = [s for s in sites if query in {
            str(s.get(key) or "").casefold() for key in ("websiteId", "appSlug", "domain", "name")
        }]
        sites = exact or [s for s in sites if any(
            query in (s.get(key) or "").casefold() for key in ("domain", "name")
        )]
    if not sites:
        sys.exit("no matching website; check --site or register the product's analytics site")
    if len(sites) != 1:
        sys.exit(f"expected one website, found {len(sites)}; use --site with an exact name/domain/id")
    slug = sites[0].get("appSlug")
    if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?", slug):
        sys.exit("analytics site has no valid appSlug; check its OS registration")
    args.website = {"id": sites[0].get("websiteId"), **{key: sites[0].get(key) for key in ("name", "domain")}}
    print(f"# website: {sites[0].get('name')} ({sites[0].get('domain')})")
    rows, page = [], 1
    while True:
        ev = call(f"{base}/analytics/{slug}/events?startAt={start}&endAt={end}&page={page}&pageSize={PAGE_SIZE}", headers)
        if not isinstance(ev, dict) or not isinstance(ev.get("data"), list):
            sys.exit("invalid event page; coverage is unknown")
        data = ev.get("data", [])
        rows.extend(data)
        count = ev.get("count")
        if type(count) is not int or count < 0:
            sys.exit("event response has no valid total count; coverage is unknown")
        if count > MAX_EVENT_PAGES * PAGE_SIZE:
            sys.exit(f"event count {count} exceeds the {MAX_EVENT_PAGES * PAGE_SIZE} event cap; narrow the date window")
        if len(rows) >= count:
            break
        if not data:
            sys.exit(f"empty event page {page}: fetched {len(rows)} of {count}; count/data mismatch, retry or inspect the source")
        if page >= MAX_EVENT_PAGES:
            sys.exit(f"incomplete event download at page cap: {len(rows)} of {count}; inspect pagination or narrow the window")
        page += 1
    event_data_status = attach_event_data(
        rows, base, slug, headers, start, end, skip=args.skip_event_data,
    )
    return rows, event_data_status


def utc_date_ms(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("expected YYYY-MM-DD")
    return int(dt.datetime.strptime(value, "%Y-%m-%d").replace(
        tzinfo=dt.timezone.utc,
    ).timestamp() * 1000)


def resolve_window(args):
    bounds = {}
    for option in ("since", "until"):
        value = getattr(args, option, None)
        try:
            bounds[option] = utc_date_ms(value) if value else None
        except ValueError as error:
            raise ValueError(f"--{option} must be a valid YYYY-MM-DD date (UTC)") from error
    start = bounds["since"] if bounds["since"] is not None else 0
    # Umami's endAt is inclusive; --until is exclusive.
    end = bounds["until"] - 1 if bounds["until"] is not None else int(time.time() * 1000)
    if end < start:
        raise ValueError("--until must be after --since" if bounds["until"] is not None
                         else "--since must not be in the future when --until is omitted")
    return {"startAt": start, "endAt": end, "timezone": "UTC",
            "start_utc": dt.datetime.fromtimestamp(start / 1000, dt.timezone.utc).isoformat(),
            "end_inclusive_utc": dt.datetime.fromtimestamp(end / 1000, dt.timezone.utc).isoformat()}


def first_touch_source(evs):
    q = urllib.parse.parse_qs(evs[0].get("urlQuery") or "")
    utm = (q.get("utm_source") or [None])[0]
    return utm or (evs[0].get("referrerDomain") or "direct")


def internal_reason(evs, src, args):
    # A smoke tag may first appear after an initial pageview; keep the whole
    # dedicated audit session out even when emulating a mobile device.
    sources = {src}
    for event in evs:
        query = urllib.parse.parse_qs(event.get("urlQuery") or "")
        sources.update(query.get("utm_source", []))
    matched = sources.intersection(args.internal_sources)
    if matched:
        return "source:" + sorted(matched)[0]
    country = evs[0].get("country")
    return f"verified_country:{country}" if country in args.internal_country else None


def is_suspected_internal(evs, src, args):
    """Heuristics are sensitivity flags, never automatic exclusions."""
    f0 = evs[0]
    if (src == "direct" and f0.get("device") in ("laptop", "desktop")
            and f0.get("country") in args.dc_country):
        return True
    for e in evs:
        p = e.get("urlPath") or ""
        if e.get("eventType") == 1 and ("/admin" in p or "/tmp/" in p or "localhost" in p):
            return True
    return False


def safe_path(path):
    """Redact common identifier/token path segments before output or storage."""
    if not isinstance(path, str):
        return path
    path = path.split("?", 1)[0].split("#", 1)[0]
    parts, redacted, redact_next = path.split("/"), [], False
    for raw in parts:
        decoded = urllib.parse.unquote(raw)
        lowered = decoded.lower()
        sensitive = (
            redact_next
            or safe_event_value("surface", decoded) is None
            or bool(UUID_RE.fullmatch(decoded))
            or bool(JWT_RE.fullmatch(decoded))
            or looks_opaque_token(decoded)
        )
        redacted.append(":redacted" if sensitive else raw)
        redact_next = lowered in SENSITIVE_PATH_PARENTS
    return "/".join(redacted)


def safe_label(value):
    """Keep categorical labels, not arbitrary URLs/free-form text."""
    if not isinstance(value, str) or not re.fullmatch(r"[\w .:/-]{1,120}", value):
        return None
    return safe_event_value("surface", value)


def safe_route_path(path):
    """Preserve hash-router/anchor semantics for stage detection after redaction."""
    before, marker, fragment = path.partition("#")
    base = safe_path(before)
    if not marker:
        return base
    safe_fragment = safe_path(fragment) if fragment.startswith("/") else safe_label(fragment)
    return base + "#" + (safe_fragment or ":redacted")


def snapshot_rows(rows):
    """Retain uncapped safe input rows; pseudonymous joins last for this snapshot."""
    salt = os.urandom(16)
    result = []
    for row in rows:
        dt.datetime.fromisoformat(row["createdAt"].replace("Z", "+00:00"))
        if type(row["eventType"]) is not int or row["eventType"] < 0:
            raise ValueError("Umami event type must be a non-negative integer")
        session_ref = ephemeral_ref("session_id", row["sessionId"], salt)
        path = row.get("urlPath") or ""
        query = urllib.parse.parse_qs(row.get("urlQuery") or "")
        attribution = {key: [safe_label(value) or "redacted" for value in query[key]]
                       for key in SAFE_UTM_FIELDS if key in query}
        # Retain distinct-page counting even when different private paths redact alike.
        page_ref = ephemeral_ref("page", path.split("#")[0].rstrip("/") or "/", salt)
        item = {
            "id": ephemeral_ref("event", row.get("id"), salt),
            "sessionId": session_ref, "_sessionRef": session_ref,
            "createdAt": row["createdAt"], "eventType": row["eventType"],
            "urlPath": safe_route_path(path), "_pageRef": page_ref,
            "urlQuery": urllib.parse.urlencode(attribution, doseq=True),
            "referrerDomain": (safe_label(row["referrerDomain"]) or "redacted") if row.get("referrerDomain") else "",
            "country": row.get("country") if re.fullmatch(r"[A-Z]{2}", row.get("country") or "") else None,
            "device": row.get("device") if row.get("device") in {"mobile", "tablet", "laptop", "desktop"} else None,
        }
        if row.get("eventName"):
            item["eventName"] = safe_label(row["eventName"]) or "redacted"
        if row.get("hasData"):
            item["hasData"] = True
        if row.get("_eventDataLoaded") or "eventData" in row:
            item["_eventDataLoaded"] = True
            item["eventData"] = safe_event_props(row)
        refs = event_identity_refs(row, salt)
        # Even pre-enriched input refs are re-keyed together for this export.
        item["eventIdentityRefs"] = {
            key: ephemeral_ref(key, value, salt) for key, value in refs.items()
        }
        result.append(item)
    return result


def make_snapshot(rows, args, event_data_status):
    return {
        "format": SNAPSHOT_FORMAT,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "website": args.website, "window": args.window,
        "analysis_options": {key: getattr(args, key) for key in ANALYSIS_OPTIONS},
        "coverage": {"base_events": "complete", "downloaded_rows": len(rows),
                     "non_funnel_event_types": dict(collections.Counter(
                         str(row["eventType"]) for row in rows if row["eventType"] not in (1, 2))),
                     "event_data": event_data_status},
        "redaction": "Safe categorical fields/properties and UTM source/medium/campaign/content only; "
                     "identities and distinct paths use per-snapshot pseudonyms. "
                     "Private path segments and unsupported properties cannot be reconstructed.",
        "rows": snapshot_rows(rows),
    }


def read_snapshot(path, args):
    with open(path, encoding="utf-8") as source:
        snapshot = json.load(source)
    if snapshot.get("format") != SNAPSHOT_FORMAT or not isinstance(snapshot.get("rows"), list):
        raise ValueError("expected an egbe-umami-events.v1 snapshot, not a summary")
    for key in ANALYSIS_OPTIONS:
        setattr(args, key, snapshot["analysis_options"][key])
    args.window, args.website = snapshot["window"], snapshot["website"]
    return snapshot["rows"], snapshot["coverage"]["event_data"]


def check_output_paths(*paths):
    selected = [Path(path) for path in paths if path]
    if len({path.resolve() for path in selected}) != len(selected):
        raise ValueError("source and summary outputs must have different paths")
    for path in selected:
        if os.path.lexists(path):
            raise ValueError(f"output already exists; preserve it and choose a new filename: {path}")
        if not path.parent.is_dir():
            raise ValueError(f"create the output directory first: {path.parent}")


def write_json(path, value):
    payload = json.dumps(value, indent=1, allow_nan=False)
    with open(path, "x", encoding="utf-8") as output:
        output.write(payload + "\n")


def safe_event_props(event):
    """Return only explicitly allowlisted, short scalar event properties."""
    value = event.get("eventData")
    if isinstance(value, str) and value.startswith("{") and len(value) <= 5000:
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = None
    if not isinstance(value, dict):
        return {}
    props = {}
    for key in SAFE_EVENT_FIELDS:
        prop_value = safe_event_value(key, value.get(key))
        if prop_value is not None:
            props[key] = prop_value
    return props


def event_identity_refs(event, salt):
    existing = event.get("eventIdentityRefs")
    if isinstance(existing, dict):
        return {key: value for key, value in existing.items()
                if key in IDENTITY_EVENT_FIELDS and isinstance(value, str)}
    payload = event.get("eventData")
    if not isinstance(payload, dict):
        return {}
    refs = {}
    for key in IDENTITY_EVENT_FIELDS:
        ref = ephemeral_ref(key, payload.get(key), salt)
        if ref:
            refs[key] = ref
    return refs


def build_timeline(evs, max_entries):
    """Build a redacted timeline, collapsing only adjacent identical pageviews."""
    display, structured = [], []
    eligible_count, last_pageview = 0, None
    for event in evs:
        if event["eventType"] == 1:
            raw_path = event.get("urlPath")
            if not raw_path or raw_path.startswith(ASSET_PATH_PREFIXES):
                continue
            token = safe_path(raw_path)
            if token == last_pageview:
                continue
            last_pageview = token
            item = {"at": event["createdAt"], "type": "pageview", "path": token}
        elif event["eventType"] == 2:
            last_pageview = None
            name = event.get("eventName")
            if not name:
                continue
            props = safe_event_props(event)
            has_data = bool(event.get("hasData") or "eventData" in event)
            data_loaded = bool(event.get("_eventDataLoaded") or "eventData" in event)
            suffix = " " + json.dumps(props, sort_keys=True) if props else ""
            if has_data and not data_loaded:
                suffix += " {event_data:unavailable}"
            token = f"[{name}]{suffix}"
            item = {"at": event["createdAt"], "type": "event", "name": name}
            if props:
                item["properties"] = props
            if has_data:
                item["has_data"] = True
                item["event_data_loaded"] = data_loaded
        else:
            continue
        eligible_count += 1
        if len(structured) >= max_entries:
            continue
        display.append(f"{event['createdAt'][11:19]} {token}")
        structured.append(item)
    return display, structured, eligible_count


def analyze(rows, args, event_data_status=None):
    rows.sort(key=lambda r: r["createdAt"])
    sessions = collections.defaultdict(list)
    for r in rows:
        sessions[r["sessionId"]].append(r)

    included, internal, suspected = {}, {}, set()
    exclusion_reasons = collections.Counter()
    for sid, evs in sessions.items():
        src = first_touch_source(evs)
        reason = internal_reason(evs, src, args)
        (internal if reason else included)[sid] = (src, evs)
        if reason:
            exclusion_reasons[reason] += 1
        if sid in included and is_suspected_internal(evs, src, args):
            suspected.add(sid)

    funnel = collections.Counter()
    suspect_funnel = collections.Counter()
    mix = collections.Counter()
    arrivals_by_source = collections.Counter()
    depth = collections.Counter()
    paths = collections.defaultdict(set)
    events = collections.defaultdict(set)
    event_occurrences = collections.Counter()
    interesting = []
    journey_rows = []
    repeat_completions = {}
    identity_salt = os.urandom(16)
    start_names = TECHNICAL_START_EVENTS | set(args.act_start_event)
    completion_names = TECHNICAL_DONE_EVENTS | set(args.act_event)
    run = {
        "window": getattr(args, "window", None), "website": getattr(args, "website", None),
        "config": {"execution_start_events": sorted(start_names),
                   "execution_completion_events": sorted(completion_names),
                   "execution_start_paths": args.act_path,
                   "internal_sources": args.internal_sources,
                   "internal_countries": args.internal_country,
                   "suspect_countries": args.dc_country,
                   "ambient_events": sorted(ENGAGE_EVENTS | EXPOSURE_EVENTS),
                   "max_journey_events": args.max_journey_events},
    }
    print("# run: " + json.dumps(run, sort_keys=True))
    if event_data_status is None:
        marked = sum(bool(row.get("hasData")) for row in rows)
        loaded = sum(bool(row.get("_eventDataLoaded") or "eventData" in row) for row in rows)
        event_data_status = {
            "status": "provided" if loaded else "not_fetched",
            "reported_events": None,
            "fetched_events": loaded,
            "marked_rows": marked,
            "matched_rows": loaded,
            "error_type": None,
        }

    for sid, (src, evs) in included.items():
        session_ref = evs[0].get("_sessionRef") or ephemeral_ref("session_id", sid, identity_salt)
        mix[src] += 1
        pv = [e for e in evs if e["eventType"] == 1 and e.get("urlPath")
              and not e["urlPath"].startswith(ASSET_PATH_PREFIXES)]
        event_names = [e.get("eventName") for e in evs
                       if e["eventType"] == 2 and e.get("eventName")]
        evn_counts = collections.Counter(event_names)
        evn = set(event_names)
        for e in pv:
            paths[safe_path(e["urlPath"])].add(sid)
        for n, count in evn_counts.items():
            events[n].add(sid)
            event_occurrences[n] += count
        npv = len(pv)
        depth_bucket = f"{npv}pv" if npv <= 1 else ("2-3pv" if npv <= 3 else "4+pv")
        depth[depth_bucket] += 1
        pset = {p["urlPath"] for p in pv}
        base_pages = {p.get("_pageRef") or p["urlPath"].split("#")[0].rstrip("/") or "/" for p in pv}
        # Activity proxy, not proven attention: exposures may fire on load.
        activity_events = evn - ENGAGE_EVENTS - EXPOSURE_EVENTS
        scroll_dwell = {"engagement-scroll", "engagement-time"} <= evn
        engaged = len(base_pages) > 1 or bool(activity_events) or scroll_dwell
        completion_count = sum(evn_counts[name] for name in completion_names)
        execution_started = bool(start_names & evn) or any(
            p.startswith(tuple(args.act_path)) for p in pset if args.act_path)
        execution_completed = completion_count > 0
        f = collections.Counter()
        if pv:
            f["arrival"] += 1
            arrivals_by_source[src] += 1
            if not engaged: f["unengaged_arrivals"] += 1
            if engaged: f["engaged"] += 1
        if "cta_click" in evn: f["cta_click"] += 1
        if "button_click" in evn: f["button_click"] += 1
        if execution_started: f["execution_started"] += 1
        if execution_completed: f["execution_completed*"] += 1
        if completion_count > 1:
            repeat_completions[session_ref] = completion_count
        if any(p.startswith(SIGNUP_PATHS) for p in pset):
            f["signup_page_seen"] += 1
        if SIGNUP_START_EVENTS & evn:
            f["signup_started"] += 1
        if SIGNUP_DONE_EVENTS & evn:
            f["signup_completed*"] += 1  # * reconcile vs ground truth
        if any(p.startswith(POST_AUTH_PATHS) for p in pset):
            f["post_auth_seen"] += 1
        if PAYWALL_EVENTS & evn or any(p.startswith(PRICING_PATHS) for p in pset):
            f["pricing_seen"] += 1
        if CHECKOUT_EVENTS & evn or any(p.startswith(CHECKOUT_PATHS) for p in pset):
            f["checkout_started"] += 1
        funnel.update(f)
        if sid in suspected:
            suspect_funnel.update(f)
        # Journey list stays focused on sessions with something to read:
        # Keep exposure timelines for reach analysis even when not engaged.
        # scroll+dwell-only sessions have no journey beyond beacons.
        beyond = (len(base_pages) > 1 or execution_started or execution_completed
                  or evn - ENGAGE_EVENTS)
        if beyond:
            tl, structured_timeline, timeline_items_total = build_timeline(
                evs, args.max_journey_events,
            )
            session_identity_refs = {"visitor": set(), "visit": set()}
            for event in evs:
                refs = event_identity_refs(event, identity_salt)
                if refs.get("visitor_id"):
                    session_identity_refs["visitor"].add(refs["visitor_id"])
                if refs.get("visit_id"):
                    session_identity_refs["visit"].add(refs["visit_id"])
            anonymized_refs = {
                key: sorted(value) for key, value in session_identity_refs.items() if value
            }
            f0 = evs[0]
            identity_suffix = f" refs={anonymized_refs}" if anonymized_refs else ""
            truncated = timeline_items_total > args.max_journey_events
            truncation_suffix = (
                f" | … {timeline_items_total - args.max_journey_events} more"
                if truncated else ""
            )
            interesting.append(
                f"{session_ref} {f0['createdAt'][:10]} {f0.get('country')}/{f0.get('device')} "
                f"src={src}{' [suspect]' if sid in suspected else ''}{identity_suffix}\n    "
                + " | ".join(tl) + truncation_suffix)
            journey_rows.append({
                "session_ref": session_ref,
                "date": f0["createdAt"][:10],
                "country": f0.get("country"),
                "device": f0.get("device"),
                "source": src,
                "suspected_internal": sid in suspected,
                "execution_completion_event_count": completion_count,
                "events_total": len(evs),
                "timeline_items_total": timeline_items_total,
                "timeline_truncated": truncated,
                "identity_refs": anonymized_refs,
                "timeline": structured_timeline,
            })

    n = max(len(included), 1)
    print(f"\n== internal filter: sources={args.internal_sources} "
          f"verified-internal-country={args.internal_country or 'NONE'} "
          f"suspect-dc-laptop-direct={args.dc_country}")
    print(f"== sessions: included={len(included)} internal={len(internal)} "
          f"suspected_included={len(suspected)} "
          f"excluded_by_reason={dict(exclusion_reasons)}")
    print("  included = not excluded by configured rules; not verified humans/customers")
    print(f"event data: {event_data_status}")
    print(f"traffic (first touch): {dict(mix.most_common(10))}")
    print(f"observed arrivals by source (suspects included): {dict(arrivals_by_source)}")
    arrivals = funnel["arrival"]
    bounce = 100 * funnel["unengaged_arrivals"] / arrivals if arrivals else None
    print(f"depth: {dict(depth)} | bounce(unengaged/arrivals)="
          + (f"{bounce:.1f}%" if bounce is not None else "unknown (no observed arrivals)"))
    without_suspects = {key: value - suspect_funnel[key] for key, value in funnel.items()}
    if suspected:
        print(f"sensitivity excluding suspects: sessions={len(included) - len(suspected)} "
              f"funnel={without_suspects}")
    print(f"top paths: { {k: len(v) for k, v in sorted(paths.items(), key=lambda kv: -len(kv[1]))[:12]} }")
    print(f"custom events (uniq sessions / raw events): "
          f"{ {k: f'{len(v)}/{event_occurrences[k]}' for k, v in sorted(events.items(), key=lambda kv: -len(kv[1]))[:15]} }")
    print("\n== stage observations (% of non-excluded sessions; not ordered conversions)")
    order = ["arrival", "engaged", "unengaged_arrivals", "cta_click", "button_click", "execution_started", "execution_completed*",
             "signup_page_seen", "signup_started", "signup_completed*", "post_auth_seen", "pricing_seen", "checkout_started"]
    for k in order:
        print(f"  {k:22s} {funnel.get(k, 0):6d}  ({funnel.get(k, 0) * 100 / n:.1f}%)")
    print("  * execution/signup completion events are technical proxies; "
          "reconcile with domain outcome and ground truth")
    print("  engaged = another distinct page, non-ambient custom event, or scroll+time "
          "beacons; activity proxy, not purchase intent")
    print(f"repeat execution-completion sessions: {repeat_completions or '{}'}")
    print("\n== activity/exposure journeys (included sessions):")
    for line in interesting:
        print("  " + line)
    if args.json:
        out = {**run, "included_sessions": len(included), "internal": len(internal), "mix": dict(mix),
               "non_funnel_event_types": dict(collections.Counter(
                   str(row["eventType"]) for row in rows if row["eventType"] not in (1, 2))),
               "exclusion_reasons": dict(exclusion_reasons),
               "arrivals_by_source": dict(arrivals_by_source),
               "suspected_internal": len(suspected),
               "funnel_excluding_suspected": without_suspects,
               "bounce_percent": bounce,
               "depth": dict(depth), "funnel": dict(funnel),
               "paths": {k: len(v) for k, v in paths.items()},
               "events": {k: {"unique_sessions": len(v),
                               "raw_events": event_occurrences[k]}
                          for k, v in events.items()},
               "event_data": event_data_status,
               "metric_notes": {
                   "execution_completed*": {
                       "kind": "technical_proxy",
                       "reconcile_with": "domain_outcome",
                   },
                   "signup_completed*": {
                       "kind": "completion_event_proxy",
                       "reconcile_with": "signup_ground_truth",
                   },
                   "signup_started": {"kind": "intent_event_requires_verified_wiring"},
                   "cta_click": {"kind": "canonical_cta_event_only"},
                   "button_click": {"kind": "secondary_interaction_requires_property_filter"},
                   "signup_page_seen": {"kind": "page_visit_not_intent"},
                   "engaged": {
                       "kind": "arrival_with_activity_requires_verified_wiring",
                       "rule": "distinct_pages>1 OR non_ambient_event OR scroll_and_time_beacons",
                       "ambient_events": sorted(ENGAGE_EVENTS | EXPOSURE_EVENTS),
                       "commercial_intent_verified": False,
                   },
                   "post_auth_seen": {"kind": "page_visit_not_signup"},
                   "arrival": {"kind": "session_with_non_asset_pageview"},
                   "bounce_percent": {"denominator": "arrival", "numerator": "unengaged_arrivals"},
                   "included_sessions": {
                       "kind": "not_excluded_by_configured_rules",
                       "suspected_internal_included": True,
                       "human_or_customer_verified": False,
                   },
                   "journeys.timeline.path": {"redacted": True},
                   "journeys.session_ref": {"ephemeral_per_run": True},
                   "journeys.identity_refs": {"ephemeral_per_run": True},
               },
               "repeat_execution_completion_sessions": repeat_completions,
               "journeys": journey_rows}
        write_json(args.json, out)
        print(f"\n(json written to {args.json})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", help="exact website name/domain/id, otherwise a unique name/domain substring")
    ap.add_argument("--since", help="inclusive YYYY-MM-DD in UTC (default: all time)")
    ap.add_argument("--until", help="exclusive YYYY-MM-DD in UTC (default: now)")
    ap.add_argument("--act-path", action="append", default=[],
                    help="path prefix that counts as execution start (repeatable)")
    ap.add_argument("--act-start-event", action="append", default=[],
                    dest="act_start_event",
                    help="event name that counts as execution start (repeatable)")
    ap.add_argument("--act-event", action="append", default=[],
                    help="event name that counts as technical execution completion (repeatable)")
    ap.add_argument("--internal-country", action="append", default=[],
                    dest="internal_country",
                    help="verified internal geography to exclude; no default. "
                         "Do not infer internal traffic from country alone")
    ap.add_argument("--dc-country", action="extend", nargs="*",
                    dest="dc_country", help="suspect countries (default DE FI); empty flag clears them")
    ap.add_argument("--internal-sources", action="extend", nargs="*",
                    dest="internal_sources", help="synthetic sources (default smoke); empty flag clears them")
    ap.add_argument("--skip-event-data", action="store_true",
                    help="skip Umami event-data enrichment and report it skipped")
    ap.add_argument("--max-journey-events", type=int, default=100,
                    help="maximum filtered timeline entries printed/stored per journey (default: 100)")
    ap.add_argument("--json", help="also write summary json here")
    ap.add_argument("--events-json", help="save uncapped sanitized input rows for offline replay")
    ap.add_argument("--from-events", help="replay a saved event snapshot/config without network access")
    args = ap.parse_args()
    args.dc_country = args.dc_country if args.dc_country is not None else ["DE", "FI"]
    args.internal_sources = args.internal_sources if args.internal_sources is not None else ["smoke"]
    if args.max_journey_events < 1:
        ap.error("--max-journey-events must be at least 1")
    try:
        check_output_paths(args.json, args.events_json)
        if args.from_events:
            live_options = {
                "--site", "--since", "--until", "--act-path", "--act-start-event",
                "--act-event", "--internal-country", "--dc-country", "--internal-sources",
                "--skip-event-data", "--max-journey-events", "--events-json",
            }
            if any(arg.split("=", 1)[0] in live_options for arg in sys.argv[1:]):
                ap.error("--from-events uses the saved config; only --json can be added")
            rows, event_data_status = read_snapshot(args.from_events, args)
            analyze(rows, args, event_data_status)
            return
        args.window = resolve_window(args)
    except (ValueError, OSError, KeyError) as error:
        ap.error(str(error))
    try:
        rows, event_data_status = fetch_events(args)
    except (ValueError, OSError, RuntimeError) as error:
        ap.error(str(error))
    print(f"# events fetched: {len(rows)}")
    # Analyze exactly the safe dataset we retain; replay reproduces its joins too.
    if args.events_json:
        snapshot = make_snapshot(rows, args, event_data_status)
        write_json(args.events_json, snapshot)
        rows = snapshot["rows"]
    analyze(rows, args, event_data_status)


if __name__ == "__main__":
    main()
