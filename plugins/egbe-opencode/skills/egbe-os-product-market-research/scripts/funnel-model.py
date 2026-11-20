"""Browser evidence, approval journals and scoped funnel projections (stdlib only).

This module never opens a page, submits a form, invents a screen or grants
approval. Private contact data live in runtime; public rows contain references.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote, quote_plus, unquote, unquote_plus, urlencode, urlsplit, urlunsplit

_features_spec = importlib.util.spec_from_file_location(__name__ + "_features", Path(__file__).with_name("funnel_features.py"))
FEATURES = importlib.util.module_from_spec(_features_spec)
_features_spec.loader.exec_module(FEATURES)

MECHANICS = json.loads((Path(__file__).resolve().parent.parent /
                       "references/contracts/walk-mechanics.v2.json").read_text())
SCHEMA_VERSION = 2
CONTRACT = MECHANICS["contract"]
SCREEN_KINDS = tuple(MECHANICS["screen_kinds"])
ADVANCE_KINDS = tuple(MECHANICS["advance_types"])
STATUSES = tuple(MECHANICS["research_statuses"])
STOP_REASONS = tuple(MECHANICS["stop_reasons"])
VIEWPORT = "390x844"
MAX_SCREENS_PER_ATTEMPT = MECHANICS["max_screens_per_attempt"]
PENDING_STATUSES = {"queued", "in_progress", "needs_approval", "needs_email"}
PERMITTED_SUBMISSIONS = set(MECHANICS["submission_kinds"])
TRACKING_NAMES = {"fbclid", "gclid", "gclsrc", "gbraid", "wbraid", "dclid", "msclkid", "ttclid", "li_fat_id"}


class FunnelError(ValueError):
    pass


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def identity(prefix: str, value) -> str:
    return prefix + "_" + canonical_hash(value)[:20]


def url_identity(address: str, confirmed_tracking=()) -> str:
    """Preserve meaningful query/fragment/order. Even UTM removal is opt-in.

    Tracking may change an offer. Equivalence needs browser observations, not
    just a familiar parameter name. Userinfo and non-web destinations fail.
    """
    if not isinstance(address, str):
        raise FunnelError("destination must be a public HTTP(S) URL")
    parts = urlsplit(address.strip())
    scheme = parts.scheme.lower()
    if scheme not in {"https", "http"} or not parts.hostname or parts.username or parts.password or re.search(r"[\x00-\x20]", address.strip()):
        raise FunnelError("destination must be a public HTTP(S) URL without credentials")
    try:
        port = parts.port
    except ValueError as exc:
        raise FunnelError("invalid destination port") from exc
    host = parts.hostname.lower()
    host = "[" + host + "]" if ":" in host else host
    netloc = host + (f":{port}" if port and port != (443 if scheme == "https" else 80) else "")
    remove = set(confirmed_tracking)
    if any(not (name.lower().startswith("utm_") or name.lower() in TRACKING_NAMES) for name in remove):
        raise FunnelError("only confirmed tracking parameters can be removed")
    query = parts.query
    if remove:
        query = urlencode([(k, v) for k, v in parse_qsl(query, keep_blank_values=True) if k not in remove])
    return urlunsplit((scheme, netloc, parts.path or "/", query, parts.fragment))


def duration_proven(row: dict, policy: dict) -> bool:
    return (type(row.get("served_days")) is int and row["served_days"] >= 0
            and row.get("age_basis") == "platform_dates" and row.get("duration_scope") in ("country", "global")
            and bool(row.get("country")))


def campaign_proof(members: list[dict], policy: dict) -> dict:
    """Preserve dated and current observations for this exact campaign.

    Native intervals and activity remain separate; neither establishes success.
    """
    proving = [copy.deepcopy(m) for m in members if duration_proven(m, policy)]
    def country_current(member):
        if not member.get("country"):
            return False
        if member.get("current_in_country") is not None:
            return member["current_in_country"] is True
        if member.get("running_at_capture") is not True:
            return False
        observations = member.get("source_observations") or []
        if observations:
            return native_current(observations, member["country"], policy)
        if member.get("activity_scope") in ("country", "global") and member.get("activity_country") == member["country"]:
            return True
        # Compatibility with native-dated 04 records; a root consumer also
        # verifies the pinned 03 activity observations before replication.
        return member.get("duration_scope") in ("country", "global") and member.get("age_basis") == "platform_dates"
    running = [copy.deepcopy(m) for m in members if country_current(m)]
    status = "active" if running else "stopped" if any(
        m.get("running_at_capture") is False for m in members) else "unknown"
    return {"observation_status": status, "dated_refs": proving,
            "running_refs": running, "source_members": copy.deepcopy(members),
            "policy_sha256": canonical_hash(policy)}


def native_current(observations: list[dict], country: str, policy: dict) -> bool:
    matched = [o for o in observations if o.get("country") == country]
    statuses = {o.get("activity_status", o.get("status")) for o in matched}
    if statuses & {"stopped", "inactive", "ended", "archived"} and statuses & {"active", "recent"}:
        return False
    for observation in matched:
        # Activity seen in this country's query (global provider flag) or native
        # country activity both count as current use in the market.
        if observation.get("activity_scope") not in ("country", "global") or observation.get("activity_country") != country:
            continue
        status = observation.get("activity_status", observation.get("status"))
        if status == "active":
            return True
    return False


def bind_activity_provenance(campaigns: list[dict], footprint: dict, policy: dict) -> None:
    """Current activity in the campaign's country is independent of date availability."""
    ads = {r.get("ad_id"): r for r in footprint.get("rows", []) if r.get("type") == "channel_ad"}
    if not ads:
        return
    for campaign in campaigns:
        for member in campaign["source_members"]:
            ad = ads.get(member.get("footprint_ad_id"))
            observations = []
            if ad and ad.get("domain") == campaign["domain"]:
                for observation in ad.get("observations", []):
                    placement = observation.get("placement")
                    channel = ad.get("channel") or ad.get("platform")
                    if placement in {"youtube", "youtube_ads"}:
                        channel = "youtube_ads"
                    elif placement in {"display", "display_ads", "display_native"}:
                        channel = "display_native"
                    if channel == campaign["channel"] and observation.get("country") == campaign.get("country"):
                        observations.append(copy.deepcopy(observation))
            member["source_observations"] = observations
            member["current_in_country"] = native_current(observations, campaign.get("country"), policy)
        campaign.update(campaign_proof(campaign["source_members"], policy))


def destination_enrichments(document: dict, creatives: dict[str, dict]) -> dict[str, str]:
    """A candidate URL is not a verified destination until tied to the ad."""
    if not document:
        return {}
    if document.get("schema_version") != 1:
        raise FunnelError("destination enrichment requires schema_version 1")
    result = {}
    for item in document.get("destinations", []):
        cid = item.get("creative_id")
        if cid not in creatives:
            raise FunnelError("destination enrichment names an unselected creative")
        if item.get("status") != "verified":
            continue
        if not item.get("source_ref") or not item.get("verified_on") or item.get("relation") not in {
            "native_ad_destination", "observed_ad_cta", "provider_ad_history"}:
            raise FunnelError("verified destination needs an explicit ad link and source")
        try:
            verified_on = date.fromisoformat(item["verified_on"])
        except (TypeError, ValueError) as exc:
            raise FunnelError("destination verified_on must be an observation date") from exc
        if verified_on > date.today():
            raise FunnelError("destination verification cannot be in the future")
        result[cid] = item.get("url")
    return result


def prepare_campaigns(selection: dict, creative_document: dict, policy: dict,
                      campaign_as_of: str, enrichment: dict | None = None) -> tuple[list[dict], list[dict]]:
    if selection.get("artifact") != "creative_selection.v1" or selection.get("schema_version") != 1:
        raise FunnelError("05 requires the canonical creative_selection.v1 manifest from 04")
    if creative_document.get("schema_version") != 2:
        raise FunnelError("legacy Creative Patterns requires a refresh; no automatic funnel proof migration")
    creatives = {r["creative_id"]: r for r in creative_document.get("rows", []) if r.get("type") == "creative"}
    selected = selection.get("selected_creatives")
    if not isinstance(selected, list):
        raise FunnelError("selection.selected_creatives must be an array")
    chosen_ids = {r.get("creative_id") for r in selected}
    enriched = destination_enrichments(enrichment or {}, {k: v for k, v in creatives.items() if k in chosen_ids})
    groups: dict[tuple, dict] = {}
    gaps = []
    normalized_urls = {}

    def normalized_destination(creative, address):
        cid = creative["creative_id"]
        if cid not in normalized_urls:
            try:
                normalized_urls[cid] = (url_identity(address), None)
            except (FunnelError, ValueError) as exc:
                normalized_urls[cid] = (None, str(exc))
        return normalized_urls[cid]

    for rank, ref in enumerate(selected, 1):
        cid = ref.get("creative_id")
        creative = creatives.get(cid)
        if not creative:
            raise FunnelError(f"selected creative {cid!r} is absent from the pinned 04 corpus")
        for field in ("domain", "country", "channel"):
            if ref.get(field) != creative.get(field):
                raise FunnelError(f"selection scope differs from corpus for {cid}: {field}")
        if creative.get("relevance") != "relevant" or creative.get("language_status") != "allowed" or creative.get("language_allowed") is not True:
            raise FunnelError(f"selected creative {cid} is not an eligible decided 04 creative")
        address = enriched.get(cid) or creative.get("landing_url") or ref.get("landing_url")
        if not address:
            attempted = next((r for r in (enrichment or {}).get("destinations", []) if r.get("creative_id") == cid), {})
            gaps.append({"type": "coverage", "status": "destination_unknown", "detail": "Selected creative has no verified ad destination",
                         "creative_ids": [cid], "domain": ref["domain"], "country": ref.get("country"),
                         "channel": ref["channel"], "source": "creative_selection", "tier": "C"})
            if attempted:
                gaps[-1].update(detail=attempted.get("detail") or attempted.get("reason") or gaps[-1]["detail"],
                                lookup_status=attempted.get("status"), source_ref=attempted.get("source_ref"))
            continue
        normalized, error = normalized_destination(creative, address)
        if error:
            gaps.append({"type": "coverage", "status": "destination_unknown", "detail": "Selected creative destination is invalid: " + error,
                         "creative_ids": [cid], "domain": ref["domain"], "country": ref.get("country"), "channel": ref["channel"],
                         "source": "creative_selection", "lookup_status": "invalid_destination", "tier": "C"})
            continue
        key = (ref["domain"], ref.get("country"), ref["channel"], normalized)
        if key not in groups:
            campaign_id = identity("campaign", key)
            # Conservative default: a cross-channel walk is separate until
            # equivalence is explicitly established in browser observations.
            groups[key] = {"type": "campaign", "campaign_id": campaign_id,
                           "funnel_id": identity("funnel", key), "rank": rank,
                           "domain": ref["domain"], "competitor_tier": ref.get("competitor_tier", "unknown"),
                           "role": "competitor", "country": ref.get("country"), "channel": ref["channel"],
                           "address": normalized, "original_urls": [], "creative_ids": [], "creatives": [],
                           "campaign_as_of": campaign_as_of, "members": []}
        group = groups[key]
        if cid in group["creative_ids"]:
            continue
        group["creative_ids"].append(cid)
        group["original_urls"].append(address)
        group["creatives"].append(copy.deepcopy(creative))
    campaigns = list(groups.values())
    # Include non-top ads only when they have the same verified campaign
    # destination/scope. They may support longevity, never reorder selection.
    for group in campaigns:
        scope = (group["domain"], group.get("country"), group["channel"])
        members = []
        for creative in creatives.values():
            if (creative.get("domain"), creative.get("country"), creative.get("channel")) != scope:
                continue
            if creative.get("relevance") != "relevant" or creative.get("language_status") != "allowed" or creative.get("language_allowed") is not True:
                continue
            address = enriched.get(creative["creative_id"]) or creative.get("landing_url")
            if not address:
                continue
            normalized, error = normalized_destination(creative, address)
            if error or normalized != group["address"]:
                continue
            members.append({k: copy.deepcopy(creative.get(k)) for k in (
                "creative_id", "native_ad_id", "footprint_ad_id", "source_members", "domain", "country", "countries",
                "channel", "competitor_tier", "relevance", "language_status", "language_allowed", "duration_scope", "age_basis", "served_days",
                "running_at_capture", "first_seen", "last_seen", "landing_url", "source", "verified_by",
                "activity_scope", "activity_country", "source_observations", "current_in_country")})
        group.pop("members")
        group.update(campaign_proof(members, policy))
        group["destination_refs"] = []
        for creative in group["creatives"]:
            cid = creative["creative_id"]
            ref = next((r for r in (enrichment or {}).get("destinations", []) if r.get("creative_id") == cid and r.get("status") == "verified"), None)
            group["destination_refs"].append(copy.deepcopy(ref) if ref else {
                "creative_id": cid, "url": creative.get("landing_url"), "status": "verified",
                "relation": "corpus_destination", "source_ref": creative.get("source") or "creative_patterns"})
    for cell in selection.get("cells", []):
        if cell.get("selected_count", len(cell.get("creative_ids", []))) == 0:
            gaps.append({"type": "coverage", "status": "no_selected_campaign", "detail": "04 has no eligible selected creative in this cell",
                         "domain": cell.get("domain"), "channel": cell.get("channel"), "country": cell.get("country"),
                         "creative_ids": [], "source": "creative_selection", "tier": "C"})
    # Preserve missing-source/channel coverage rather than implying that an
    # omitted selection cell means this channel has no advertising.
    selected_scopes = {(r.get("domain"), r.get("country"), r.get("channel")) for r in selected}
    for coverage in creative_document.get("rows", []):
        scope = (coverage.get("domain"), coverage.get("country"), coverage.get("channel"))
        if coverage.get("type") == "coverage" and scope not in selected_scopes and coverage.get("channel"):
            gaps.append({"type": "coverage", "status": "no_available_campaign", "domain": scope[0], "country": scope[1],
                         "channel": scope[2], "detail": coverage.get("detail") or coverage.get("status") or "04 source unavailable",
                         "upstream_status": coverage.get("status"), "source": "creative_patterns_coverage", "tier": "C"})
    return campaigns, gaps


def allocate_identities(registry: dict | None, mailbox: str, campaigns: list[dict]) -> dict:
    registry = copy.deepcopy(registry or {"schema_version": 1, "mailbox": mailbox, "identities": []})
    if registry.get("schema_version") != 1 or registry.get("mailbox") != mailbox:
        raise FunnelError("identity registry mailbox changed; preserve existing aliases before resuming")
    if not re.fullmatch(r"[^\s@+]+@[^\s@]+", mailbox):
        raise FunnelError("research mailbox must be a base email address without an alias")
    identities = registry.get("identities")
    if not isinstance(identities, list):
        raise FunnelError("identity registry identities must be an array")
    local, host = mailbox.split("@", 1)
    reserved = {row.get("alias") for row in identities}
    by_funnel = {row.get("funnel_id"): row for row in identities if row.get("funnel_id")}
    for campaign in campaigns:
        fid = campaign["funnel_id"]
        if fid in by_funnel:
            continue
        n = 1
        while f"{local}+{n:02d}@{host}" in reserved:
            n += 1
        alias = f"{local}+{n:02d}@{host}"
        row = {"identity_id": identity("identity", fid), "domain": campaign["domain"], "funnel_id": fid,
               "alias": alias, "kind": "funnel"}
        identities.append(row)
        reserved.add(alias)
        by_funnel[fid] = row
    return registry


def apply_copy_policy(campaigns: list[dict], footprint: dict) -> None:
    """Describe selected research evidence, not permission to copy or launch."""
    for campaign in campaigns:
        campaign["research_comparable"] = bool(campaign.get("source_members"))


def apply_equivalences(campaigns: list[dict], document: dict, workspace: Path) -> list[dict]:
    """Optional reuse only after actual same-scope browser equivalence captures.

    Campaign IDs/URLs/proof remain separate. The first stable physical ID is
    reused, so prior alias reservations remain reserved. Cross-channel/market
    evidence is kept separate rather than projected by an equivalence flag.
    """
    if not document:
        return []
    if document.get("schema_version") != 1:
        raise FunnelError("equivalences requires schema_version 1")
    by_id = {c["campaign_id"]: c for c in campaigns}
    used, assets = set(), []
    for equivalence in document.get("equivalences", []):
        ids = equivalence.get("campaign_ids", [])
        if not equivalence.get("equivalence_id") or len(ids) < 2 or len(set(ids)) != len(ids) or any(cid not in by_id or cid in used for cid in ids):
            raise FunnelError("equivalence requires unique selected campaign IDs, used only once")
        group = [by_id[cid] for cid in ids]
        if len({(c["domain"], c.get("country"), c["channel"]) for c in group}) != 1:
            raise FunnelError("equivalence cannot merge different competitors, countries or channels")
        if set(equivalence.get("addresses", [])) != {c["address"] for c in group}:
            raise FunnelError("equivalence addresses must match the concrete campaign destinations")
        verification = equivalence.get("verification", {})
        if any(verification.get(key) is not True for key in ("country", "content", "route")) or not equivalence.get("source_ref") or not equivalence.get("verified_on"):
            raise FunnelError("equivalence needs observed country/content/route verification and source")
        shots = [resolve_asset(workspace, a) for a in equivalence.get("screenshots", [])]
        if len(shots) < len(group):
            raise FunnelError("equivalence requires browser captures for each original destination")
        if any(shot.get("contains_private_data") is True for shot in shots):
            raise FunnelError("equivalence captures must be safe public browser observations without private contact pixels")
        assets.extend(shots)
        primary = min(group, key=lambda c: c["rank"])
        ref = {"equivalence_id": equivalence["equivalence_id"], "campaign_ids": ids,
               "addresses": equivalence["addresses"], "source_ref": equivalence["source_ref"],
               "verified_on": equivalence["verified_on"], "screenshots": shots}
        for c in group:
            c["funnel_id"] = primary["funnel_id"]
            c["equivalence_ref"] = ref
        used.update(ids)
    return assets


def resolve_asset(workspace: Path, screenshot: dict) -> dict:
    if not isinstance(screenshot, dict) or not screenshot.get("path"):
        raise FunnelError("every observed screen requires a screenshot object with path and sha256")
    path = Path(screenshot["path"])
    path = path if path.is_absolute() else workspace / path
    try:
        path = path.resolve(strict=True)
        relative = path.relative_to(workspace.resolve())
    except (OSError, ValueError) as exc:
        raise FunnelError("screenshot must be an existing file inside the research workspace") from exc
    data = path.read_bytes()
    if not (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")
            or data.startswith((b"GIF87a", b"GIF89a")) or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")):
        raise FunnelError("screenshot is not a supported raster image")
    digest = hashlib.sha256(data).hexdigest()
    if screenshot.get("sha256") != digest:
        raise FunnelError("screenshot hash mismatch; refresh the observation")
    return {**screenshot, "path": relative.as_posix(), "sha256": digest}


def form_fingerprint(form: dict) -> str:
    return canonical_hash({k: form.get(k) for k in (
        "form_id", "revision", "funnel_id", "path_id", "campaign_ids", "screen_id", "url", "purpose", "fields", "alias")})


def validate_append_only(previous: dict, plans: dict, approvals: dict, journal: dict) -> dict:
    current = {"schema_version": 2, "forms": plans.get("forms", []),
               "approvals": approvals.get("approvals", []), "events": journal.get("events", [])}
    for key in ("forms", "approvals", "events"):
        prior = previous.get(key, [])
        if current[key][:len(prior)] != prior:
            raise FunnelError("approval/submission history is append-only; preserve revisions and resolve outcomes, never erase attempts")
    return current


def _timestamp(value, name: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise FunnelError(f"{name} must be an ISO timestamp with timezone") from exc
    if parsed.tzinfo is None or parsed > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise FunnelError(f"{name} must have a timezone and cannot be in the future")
    return str(value)


def validate_journals(plans: dict, approvals: dict, journal: dict, candidates: list[dict], registry: dict | None) -> tuple[dict, dict]:
    """Validate exact form revisions and intent-before-outcome event sequences."""
    for label, doc in (("approval-plan", plans), ("approvals", approvals), ("submissions", journal)):
        if doc.get("schema_version") != 2:
            raise FunnelError(f"{label} requires schema_version 2")
    by_funnel = {c["funnel_id"]: c for c in candidates}
    alias_by_funnel = {r.get("funnel_id"): r.get("alias") for r in (registry or {}).get("identities", [])}
    forms = {}
    for form in plans.get("forms", []):
        key = (form.get("form_id"), form.get("revision"))
        if not key[0] or type(key[1]) is not int or key[1] < 1 or key in forms:
            raise FunnelError("form_id/revision must be unique and revision a positive integer")
        candidate = by_funnel.get(form.get("funnel_id"))
        if not candidate or candidate.get("role") == "own":
            raise FunnelError("planned submission must belong to a selected competitor funnel")
        if form.get("purpose") not in PERMITTED_SUBMISSIONS or not isinstance(form.get("fields"), dict) or not form["fields"]:
            raise FunnelError("only exact lead_form/quiz/webinar_registration fields can be approved")
        if not form.get("path_id") or not form.get("screen_id") or not form.get("campaign_ids"):
            raise FunnelError("planned form requires path, screen and campaign references")
        if not set(form["campaign_ids"]) <= set(candidate.get("campaign_ids", [])):
            raise FunnelError("planned form campaign scope mismatch")
        url_identity(form.get("url"))
        alias = form.get("alias")
        if not alias or alias != alias_by_funnel.get(form["funnel_id"]):
            raise FunnelError("planned form must use the funnel's stable research alias")
        for field, value in form["fields"].items():
            normalized = field.casefold()
            if any(word in normalized for word in ("password", "card_number", "credit_card", "cvv", "payment", "captcha", "sms_code")):
                raise FunnelError("account and card/payment fields cannot be approved")
            if "email" in normalized and value != alias:
                raise FunnelError("email must match the stable funnel alias")
            if "phone" in normalized or "mobile" in normalized or normalized in {"tel", "telephone"}:
                digits = re.sub(r"\D", "", str(value))
                if not (len(digits) in (10, 11) and (len(digits) != 11 or digits.startswith("1"))
                        and re.fullmatch(r"55501\d\d", digits[-7:])):
                    raise FunnelError("phone must be a full US number in fiction range 555-0100..0199")
        if form.get("form_sha256") not in (None, form_fingerprint(form)):
            raise FunnelError("planned form fingerprint mismatch")
        forms[key] = {**form, "form_sha256": form_fingerprint(form)}
    approved = {}
    for approval in approvals.get("approvals", []):
        aid = approval.get("approval_id")
        if not aid or aid in approved or approval.get("confirmed_by") != "human_operator" or not str(approval.get("source_ref") or "").startswith("chat:"):
            raise FunnelError("approval needs a unique ID and explicit human chat confirmation reference")
        _timestamp(approval.get("approved_at"), "approved_at")
        matches = set()
        for ref in approval.get("forms", []):
            key = (ref.get("form_id"), ref.get("revision"))
            if key not in forms or ref.get("form_sha256") != forms[key]["form_sha256"]:
                raise FunnelError("approval does not match the exact form revision/data")
            matches.add(key)
        if not matches:
            raise FunnelError("approval has no exact forms")
        approved[aid] = {"forms": matches, "approved_at": approval["approved_at"]}
    intents = {}
    results = {}
    fingerprints = {}
    events = set()
    for event in journal.get("events", []):
        eid = event.get("event_id")
        if not eid or eid in events:
            raise FunnelError("submission event IDs must be unique")
        events.add(eid)
        timestamp = _timestamp(event.get("occurred_at"), "submission occurred_at")
        kind = event.get("type")
        if kind == "intent":
            key = (event.get("form_id"), event.get("revision"))
            aid = event.get("approval_id")
            if key not in forms or aid not in approved or key not in approved[aid]["forms"]:
                raise FunnelError("submission intent has no exact human approval")
            form = forms[key]
            if event.get("form_sha256") != form["form_sha256"] or event.get("fields") != form["fields"]:
                raise FunnelError("submission data differ from the approved revision")
            if datetime.fromisoformat(timestamp.replace("Z", "+00:00")) < datetime.fromisoformat(approved[aid]["approved_at"].replace("Z", "+00:00")):
                raise FunnelError("submission intent predates human approval")
            fingerprint = form["form_sha256"]
            previous = fingerprints.get(fingerprint)
            if previous and results.get(previous, {}).get("outcome") != "not_submitted":
                raise FunnelError("duplicate or uncertain submission: inspect outcome before retrying")
            if previous and event.get("retry_authorization_ref") != aid:
                raise FunnelError("retry after confirmed non-submission requires explicit approval reference")
            if previous and aid == intents[previous]["approval_id"]:
                raise FunnelError("retry requires a new human approval, not the original form list confirmation")
            fingerprints[fingerprint] = eid
            intents[eid] = {**event, "form": form}
        elif kind in {"outcome", "resolution"}:
            ref = event.get("submission_ref")
            if ref not in intents or not event.get("source_ref") or event.get("outcome") not in {"submitted", "not_submitted", "unknown"}:
                raise FunnelError("submission outcome needs an earlier intent and observed source")
            if ref in results and kind != "resolution":
                raise FunnelError("duplicate outcome; use an explicit resolution event")
            if datetime.fromisoformat(timestamp.replace("Z", "+00:00")) < datetime.fromisoformat(intents[ref]["occurred_at"].replace("Z", "+00:00")):
                raise FunnelError("submission outcome predates its intent")
            results[ref] = event
        else:
            raise FunnelError("submission event type must be intent, outcome or resolution")
    return intents, results


def validate_walks(document: dict, candidates: list[dict], workspace: Path, inputs_sha256: str,
                   intents: dict | None = None, outcomes: dict | None = None) -> list[dict]:
    if document.get("schema_version") != 2 or document.get("contract") != CONTRACT:
        raise FunnelError("legacy walks require fresh browser evidence; expected funnel-walk.v2")
    if document.get("inputs_sha256") != inputs_sha256:
        raise FunnelError("walk inputs changed; inspect and rebind observations without repeating submissions")
    by_funnel = {c["funnel_id"]: c for c in candidates}
    seen = set()
    valid = []
    intents, outcomes = intents or {}, outcomes or {}
    for source in document.get("walks", []):
        walk = copy.deepcopy(source)
        fid, pid = walk.get("funnel_id"), walk.get("path_id")
        if fid not in by_funnel or not pid or (fid, pid) in seen:
            raise FunnelError("every path needs a unique selected funnel_id/path_id")
        seen.add((fid, pid))
        candidate = by_funnel[fid]
        if set(walk.get("campaign_ids", [])) != set(candidate.get("campaign_ids", [])):
            raise FunnelError("walk campaign references differ from its selected funnel")
        if walk.get("role", candidate["role"]) != candidate["role"]:
            raise FunnelError("own/competitor walk role mismatch")
        walk["role"] = candidate["role"]
        walk["domain"] = candidate["domain"]
        walk["country"] = candidate.get("country")
        walk["channel"] = candidate.get("channel")
        if candidate.get("equivalence_ref"):
            walk["equivalence_ref"] = copy.deepcopy(candidate["equivalence_ref"])
        if url_identity(walk.get("address")) != url_identity(candidate["address"]):
            raise FunnelError("walk entry URL differs from the chosen campaign destination")
        if walk.get("viewport") != VIEWPORT or walk.get("status") not in STATUSES:
            raise FunnelError("walk requires the mobile viewport and a closed research status")
        if walk.get("stop_reason") not in STOP_REASONS:
            raise FunnelError("walk requires an explicit permitted stop reason")
        if walk["status"] == "completed" and walk["stop_reason"] != "completed":
            raise FunnelError("completed path needs a reached outcome, not a blocked boundary")
        if walk["status"] in PENDING_STATUSES and walk["stop_reason"] == "completed":
            raise FunnelError("pending path cannot claim completion")
        if walk.get("observed_outcome") not in {"lead_submitted", "webinar_registered", "quiz_completed", "result_observed", "public_content_end", "not_observed"}:
            raise FunnelError("observed_outcome must be a permitted reached outcome or not_observed")
        if walk["status"] == "completed" and walk["observed_outcome"] == "not_observed":
            raise FunnelError("completed path needs a actually reached observable outcome")
        if not walk.get("persona_id") or not isinstance(walk.get("observed_market"), dict):
            raise FunnelError("walk requires persona_id and observed_market (unknown values permitted)")
        walked_on = walk.get("walked_on")
        try:
            observed_date = date.fromisoformat(walked_on)
        except (TypeError, ValueError) as exc:
            raise FunnelError("walked_on must be an observation date") from exc
        if observed_date > date.today():
            raise FunnelError("browser observation cannot be in the future")
        if not isinstance(walk.get("unknown"), list):
            raise FunnelError("walk requires an explicit unknown list")
        screens = walk.get("screens")
        if not isinstance(screens, list) or not screens:
            raise FunnelError("an observed walk needs at least one real screen")
        attempts = Counter()
        screen_ids = set()
        for n, screen in enumerate(screens, 1):
            sid = screen.get("screen_id")
            if not sid or sid in screen_ids:
                raise FunnelError("screen_id must be unique within the path")
            screen_ids.add(sid)
            screen["n"] = n
            kind = str(screen.get("kind") or "").split(":", 1)[0].strip()
            if kind not in SCREEN_KINDS or screen.get("advance") not in ADVANCE_KINDS:
                raise FunnelError("screen kind/advance must follow funnel-walk.v2")
            if screen.get("branch_role") not in MECHANICS["branch_roles"] or not screen.get("attempt_id"):
                raise FunnelError("screen requires main/auxiliary branch_role and attempt_id")
            attempts[screen["attempt_id"]] += 1
            if attempts[screen["attempt_id"]] > MAX_SCREENS_PER_ATTEMPT:
                raise FunnelError("40 screens per attempt; save a budget stop and resume in a new attempt")
            screen["screenshot"] = resolve_asset(workspace, screen.get("screenshot"))
            if screen.get("display_screenshot"):
                display = resolve_asset(workspace, screen["display_screenshot"])
                if display.get("source_sha256") != screen["screenshot"]["sha256"] or display.get("derivation") != "privacy_redaction":
                    raise FunnelError("display screenshot must explicitly reference the raw observation and privacy redaction")
                screen["source_screenshot"] = screen["screenshot"]
                screen["screenshot"] = display
            elif screen["screenshot"].get("contains_private_data") is True:
                raise FunnelError("private contact pixels need a separately declared privacy-redacted display asset")
            if "screenshots" in screen:
                screen["screenshots"] = [resolve_asset(workspace, asset) for asset in screen["screenshots"]]
                if any(asset.get("contains_private_data") is True for asset in screen["screenshots"]):
                    raise FunnelError("additional public screenshots cannot contain private contact pixels")
            url_identity(screen.get("url"))
            if type(screen.get("headline_words")) is not int or screen["headline_words"] < 0:
                raise FunnelError("headline_words must be a nonnegative integer")
            if not isinstance(screen.get("headline"), str) or not isinstance(screen.get("notes", ""), str):
                raise FunnelError("screen content must preserve observed text")
            if type(screen.get("options")) is not int and screen.get("options") != "none":
                raise FunnelError("options must be an integer or none")
            if type(screen.get("options")) is int and screen["options"] < 0:
                raise FunnelError("options cannot be negative")
            if screen.get("result_type") not in {None, "teaser", "final", "not_observed", "absent", "not_applicable"}:
                raise FunnelError("result_type distinguishes teaser and final result")
            if kind == "teaser" and screen.get("result_type") != "teaser":
                raise FunnelError("teaser must not be encoded as a final result")
            if kind == "result" and screen.get("result_type") != "final":
                raise FunnelError("result screen needs a visually observed final result")
            if screen.get("source", "browser") != "browser":
                raise FunnelError("website screen must be a browser observation; page config/email is a separate source")
            for number in screen.get("amounts", []):
                if number.get("kind") not in {"price", "discount", "financing", "salary_claim", "other"} or not number.get("context"):
                    raise FunnelError("observed amounts need a semantic kind and context")
                if not number.get("text"):
                    raise FunnelError("amounts preserve the actual displayed browser text")
            action = screen.get("action")
            if action is None:
                action = {}
            if not isinstance(action, dict):
                raise FunnelError("screen action must be an object or null")
            if action.get("type") is not None and not isinstance(action["type"], str):
                raise FunnelError("screen action type must be a string")
            screen["action"] = action
            if action.get("type") in {"pay", "enter_card", "create_account", "book_live_call"}:
                raise FunnelError("forbidden browser action")
            if action.get("type") == "submit":
                ref = action.get("submission_ref")
                if ref not in intents:
                    raise FunnelError("submitted screen must reference an approved journal intent")
                form = intents[ref]["form"]
                if (form["funnel_id"], form["path_id"], form["screen_id"]) != (fid, pid, sid):
                    raise FunnelError("screen submission reference belongs to another path/form")
                if candidate["role"] == "own":
                    raise FunnelError("own funnel cannot submit forms")
                if screen.get("captured_before_fill") is not True:
                    raise FunnelError("submitted form screenshot must be captured before contact data were filled")
            if kind == "contact request" and screen.get("submission_required") is True and any(
                following.get("branch_role") == "main" for following in screens[n:]):
                ref = action.get("submission_ref")
                if action.get("type") != "submit" or outcomes.get(ref, {}).get("outcome") != "submitted":
                    raise FunnelError("post-contact continuation requires an approved observed submission")
            if kind == "account gate" and any(s.get("branch_role") == "main" for s in screens[n:]) and not str(screen.get("operator_access_ref") or "").startswith("chat:"):
                raise FunnelError("account-gated continuation requires access provided by an authorized account holder")
            if kind in {"payment gate", "booking"} and any(s.get("branch_role") == "main" for s in screens[n:]):
                if kind == "payment gate" or screen.get("booking_kind") == "live_sales_call":
                    raise FunnelError("payment or live sales booking ends the path before submission")
        if not any(s["branch_role"] == "main" for s in screens):
            raise FunnelError("auxiliary popup cannot replace the main funnel path")
        opened = next(s["url"] for s in screens if s["branch_role"] == "main")
        if url_identity(opened) != url_identity(walk["address"]):
            redirects = walk.get("redirect_chain", [])
            previous = url_identity(walk["address"])
            for redirect in redirects:
                if url_identity(redirect.get("from")) != previous or not redirect.get("source_ref"):
                    raise FunnelError("observed redirect chain must preserve the original ad entry URL")
                previous = url_identity(redirect.get("to"))
            if not redirects or previous != url_identity(opened):
                raise FunnelError("different opened URL needs the actual observed redirect chain")
        walk["opened_address"] = opened
        partial = walk["status"] != "completed"
        if partial and not walk["unknown"]:
            raise FunnelError("partial path must identify its unseen downstream")
        if candidate["role"] == "own" and walk["stop_reason"] not in {"own_no_submit", "form_not_submitted", "technical", "captcha", "completed", "budget"}:
            raise FunnelError("own funnel uses an explicit no-submit boundary")
        if walk["observed_outcome"] in {"lead_submitted", "webinar_registered"} and not any(
                outcomes.get(s.get("action", {}).get("submission_ref"), {}).get("outcome") == "submitted" for s in screens):
            raise FunnelError("claimed registration outcome requires an observed approved submission")
        main_screens = [s for s in screens if s["branch_role"] == "main"]
        last = main_screens[-1]
        last_kind = last["kind"].split(":", 1)[0]
        if walk["status"] == "completed":
            if last_kind in {"account gate", "payment gate", "booking", "verification", "loader", "contact request"}:
                raise FunnelError("a terminal gate or request cannot masquerade as a completed full path")
            final_result = any(s.get("result_type") == "final" for s in main_screens)
            final_submission = any(outcomes.get(s.get("action", {}).get("submission_ref"), {}).get("outcome") == "submitted" for s in main_screens)
            if walk["observed_outcome"] in {"quiz_completed", "result_observed"} and not final_result:
                if not (walk["observed_outcome"] == "quiz_completed" and final_submission and last_kind == "confirmation" and last.get("completion_observed") is True):
                    raise FunnelError("quiz completion needs an actual final result or observed approved completion response")
            if walk["observed_outcome"] in {"lead_submitted", "webinar_registered"} and last_kind not in {"confirmation", "result"}:
                raise FunnelError("registration completion needs an observed confirmation screen")
            if walk["observed_outcome"] == "public_content_end" and last.get("completion_observed") is not True:
                raise FunnelError("public content end needs an explicitly observed end, not a shallow landing stop")
        walk["partial"] = partial
        walk["observed_screens_count"] = len([s for s in screens if s["branch_role"] == "main"])
        walk["screens_count"] = walk["observed_screens_count"]
        walk["full_screens_count"] = None if partial else walk["observed_screens_count"]
        walk["last_observed_screen"] = screens[-1]["screen_id"]
        market = walk["observed_market"]
        walk["market_mismatch"] = bool(market.get("country") and candidate.get("country") and market["country"] != candidate["country"])
        walk["target_market"] = candidate.get("country") or "unknown"
        walk["type"] = "funnel_walk"
        valid.append(walk)
    return valid


def observation_features(walk: dict) -> dict:
    try:
        return FEATURES.observation_features(walk)
    except FEATURES.FunnelFeaturesError as exc:
        raise FunnelError(str(exc)) from exc


def attach_campaigns(walks: list[dict], campaigns: list[dict]) -> list[dict]:
    by_id = {c["campaign_id"]: c for c in campaigns}
    for walk in walks:
        linked = [by_id[cid] for cid in walk["campaign_ids"]]
        walk.update(observation_features(walk))
        walk["creative_ids"] = list(dict.fromkeys(cid for c in linked for cid in c["creative_ids"]))
        walk["dated_refs"] = [r for c in linked if c.get("research_comparable") for r in c["dated_refs"]]
        walk["running_refs"] = [r for c in linked if c.get("research_comparable") for r in c["running_refs"]]
        walk["source_members"] = [r for c in linked for r in c["source_members"]]
        walk["advertising_observation_status"] = "active" if any(c["observation_status"] == "active" for c in linked) else "observed" if linked else "unknown"
        walk["observation_status"] = walk["advertising_observation_status"]
        if walk.get("market_mismatch"):
            walk["observation_status"] = "unknown"
            walk["dated_refs"] = []
            walk["running_refs"] = []
        walk["policy_sha256"] = linked[0]["policy_sha256"] if linked else None
        walk["competitor_tier"] = linked[0]["competitor_tier"] if linked else "own"
        walk["research_comparable"] = any(c.get("research_comparable") for c in linked)
        walk["walk_id"] = identity("walk", [walk["funnel_id"], walk["path_id"]])
        walk["walk_ref"] = walk["walk_id"]
        walk["creative_links"] = []
        main = [s for s in walk["screens"] if s["branch_role"] == "main"]
        for campaign in linked:
            for creative in campaign["creatives"]:
                walk["creative_links"].append({
                    "creative_id": creative["creative_id"], "campaign_id": campaign["campaign_id"],
                    "category_angle_ids": creative.get("category_angle_ids", []),
                    "message_family_id": creative.get("message_family_id"),
                    "ad_hook": creative.get("headline"), "ad_promise": creative.get("body"),
                    "ad_offer": creative.get("offer_kind"),
                    "landing_headline": main[0].get("headline"),
                    "landing_offer": next((s["offer"] for s in main if s.get("offer")), None),
                    "observed_ending": walk.get("observed_outcome"),
                    "ending_unknown": walk["partial"], "funnel_types": walk["funnel_types"],
                    "source": "04 angle dictionary + observed browser content",
                })
        walk["tier"] = "A"
    return walks


def aggregate_patterns(campaigns: list[dict], walks: list[dict]) -> list[dict]:
    """One vote per campaign; unknown excluded from denominator but shown.

    Extra persona paths are additional observations, not votes/competitors.
    A feature is known true if any relevant path shows it; false only if a
    completed path determines absence. Unobserved downstream stays unknown.
    """
    groups = defaultdict(list)
    by_campaign = defaultdict(list)
    for walk in walks:
        if walk["role"] == "own" or walk.get("market_mismatch"):
            continue
        for cid in walk["campaign_ids"]:
            by_campaign[cid].append(walk)
    for campaign in campaigns:
        groups[(campaign.get("country"), campaign["channel"])].append(campaign)
    out = []
    for (country, channel), members in groups.items():
        names = sorted({name for c in members for w in by_campaign[c["campaign_id"]] for name in w["features"]})
        for name in names:
            yes, known = [], []
            for c in members:
                values = [w["features"].get(name) for w in by_campaign[c["campaign_id"]]]
                value = True if True in values else False if False in values else None
                if value is not None:
                    known.append(c)
                if value is True:
                    yes.append(c)
            if not yes:
                continue
            domains = sorted({c["domain"] for c in yes})
            dated = [c for c in yes if bool(c.get("dated_refs")) and c.get("research_comparable")]
            dated_domains = sorted({c["domain"] for c in dated})
            supporting = [w for c in yes for w in by_campaign[c["campaign_id"]] if w["features"].get(name) is True]
            row = {"type": "funnel_pattern", "pattern_id": identity("pattern", [country, channel, name]),
                   "pattern": name, "pattern_group": "funnel_type" if name.startswith("type:") else "structure",
                   "country": country, "channel": channel, "role": "competitor", "selected_campaigns_total": len(members),
                   "campaigns_with": len(yes), "known_campaigns_total": len(known), "unknown_campaigns": len(members) - len(known),
                   "share": round(len(yes) / len(known), 4) if known else None,
                   "competitors": domains, "convergence": len(domains), "observed_convergence": len(domains),
                   "dated_convergence": len(dated_domains), "dated_competitors": dated_domains,
                   "direct_convergence": len({c["domain"] for c in dated if c["competitor_tier"] == "direct"}),
                   "indirect_convergence": len({c["domain"] for c in dated if c["competitor_tier"] == "indirect"}),
                   "observation_status": "active" if any(c["observation_status"] == "active" for c in yes) else "observed",
                   "dated_refs": [r for c in dated for r in c["dated_refs"]],
                   "running_refs": [r for c in yes if c.get("research_comparable") for r in c["running_refs"]],
                   "source_members": [r for c in yes for r in c["source_members"]],
                   "campaign_ids": [c["campaign_id"] for c in yes], "creative_ids": list(dict.fromkeys(cid for c in yes for cid in c["creative_ids"])),
                   "funnel_ids": sorted({c["funnel_id"] for c in yes}), "walk_refs": sorted({w["walk_ref"] for w in supporting}),
                   "policy_sha256": members[0]["policy_sha256"], "recurring": len(domains) >= 2,
                   "relevance": "relevant", "tier": "B"}
            row["research_comparable_campaign_ids"] = [c["campaign_id"] for c in yes if c.get("research_comparable")]
            row["research_comparable"] = bool(row["research_comparable_campaign_ids"])
            out.append(row)
    # Angles are paired with observed types, rather than measured by lexical
    # overlap. One campaign gets one vote regardless of its ad/path count.
    for (country, channel), members in groups.items():
        link_keys = set()
        known_members = []
        campaign_links = {}
        for c in members:
            links = [link for w in by_campaign[c["campaign_id"]] for link in w.get("creative_links", [])]
            keys = {(angle, link.get("message_family_id"), kind)
                    for link in links for angle in link.get("category_angle_ids", []) for kind in link.get("funnel_types", [])}
            campaign_links[c["campaign_id"]] = keys
            link_keys.update(keys)
            if any(link.get("category_angle_ids") and link.get("funnel_types") for link in links):
                known_members.append(c)
        for key in sorted(link_keys, key=str):
            yes = [c for c in known_members if key in campaign_links[c["campaign_id"]]]
            dated = [c for c in yes if bool(c.get("dated_refs")) and c.get("research_comparable")]
            domains, dated_domains = sorted({c["domain"] for c in yes}), sorted({c["domain"] for c in dated})
            out.append({"type": "funnel_pattern", "pattern_id": identity("link", [country, channel, key]),
                "pattern": "creative_link:" + key[0] + "→" + key[2], "pattern_group": "creative_link",
                "country": country, "channel": channel, "role": "competitor", "category_angle_ids": [key[0]],
                "message_family_id": key[1], "funnel_type": key[2], "selected_campaigns_total": len(members),
                "campaigns_with": len(yes), "known_campaigns_total": len(known_members),
                "unknown_campaigns": len(members) - len(known_members), "share": round(len(yes) / len(known_members), 4),
                "competitors": domains, "convergence": len(domains), "observed_convergence": len(domains),
                "dated_convergence": len(dated_domains), "dated_competitors": dated_domains,
                "direct_convergence": len({c["domain"] for c in dated if c["competitor_tier"] == "direct"}),
                "indirect_convergence": len({c["domain"] for c in dated if c["competitor_tier"] == "indirect"}),
                "observation_status": "active" if any(c["observation_status"] == "active" for c in yes) else "observed",
                "dated_refs": [r for c in dated for r in c["dated_refs"]],
                "running_refs": [r for c in yes if c.get("research_comparable") for r in c["running_refs"]],
                "source_members": [r for c in yes for r in c["source_members"]], "campaign_ids": [c["campaign_id"] for c in yes],
                "creative_ids": list(dict.fromkeys(cid for c in yes for cid in c["creative_ids"])),
                "funnel_ids": sorted({c["funnel_id"] for c in yes}),
                "walk_refs": sorted({w["walk_id"] for c in yes for w in by_campaign[c["campaign_id"]]
                    if any(key[0] in link.get("category_angle_ids", []) and link.get("message_family_id") == key[1]
                           and key[2] in link.get("funnel_types", []) for link in w.get("creative_links", []))}),
                "policy_sha256": members[0]["policy_sha256"], "recurring": len(domains) >= 2,
                "relevance": "relevant", "research_comparable_campaign_ids": [c["campaign_id"] for c in yes if c.get("research_comparable")],
                "research_comparable": any(c.get("research_comparable") for c in yes), "tier": "B"})
    return out


_PUBLIC_REFERENCE_FIELDS = {
    "address", "opened_address", "landing_url", "entry_url", "original_urls",
    "destination_refs", "source_members", "dated_refs", "running_refs", "assets",
    "screenshot", "screenshots", "display_screenshot", "media_assets", "path", "sha256",
}
_PUBLIC_URL_FIELDS = {"url", "address", "opened_address", "landing_url", "entry_url", "original_urls", "from", "to"}
_PRIVATE_ROW_FIELDS = {"fields", "alias", "mailbox", "message_ref", "raw_body", "source_screenshot"}
_PUBLIC_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.I)
_PUBLIC_METADATA_FIELDS = {
    "id", "ids", "ref", "refs", "type", "kind", "source", "source_ref", "status",
    "verification_status", "pattern", "advance", "role", "country", "channel",
    "result_type", "observed_outcome", "stop_reason", "currency", "language",
    "schema_version", "domain", "format", "tier", "competitor_tier", "ad_offer",
    "relevance", "age_basis", "duration_scope", "viewport",
}
_PUBLIC_METADATA_SUFFIXES = (
    "_id", "_ids", "_ref", "_refs", "_sha256", "_type", "_types", "_kind", "_kinds",
    "_status", "_statuses", "_at", "_on", "_role", "_roles", "_group",
)


def _contact_pattern(private):
    return r"(?<!\w)" + re.escape(private) + r"(?!\w)"


def _phone_contact_pattern(private):
    digits = re.sub(r"\D", "", str(private))
    if re.fullmatch(r"1?\d{3}55501\d\d", digits):
        return r"(?<!\d)(?:\+?1[\s().-]*)?" + r"[\s().-]*".join(re.escape(d) for d in digits[-10:]) + r"(?!\d)"
    return None


def private_identifier_in_reference(value, private_values):
    decoded_forms = {unquote(unquote(value)), unquote_plus(value), unquote_plus(unquote(value))}
    for decoded in decoded_forms:
        for private in private_values:
            if not private:
                continue
            if "@" in str(private) and re.search(_contact_pattern(str(private)), decoded, re.I):
                return True
            phone = _phone_contact_pattern(private)
            if phone and re.search(phone, decoded):
                return True
    return False


def _private_mail_url(url, private_values, mail_context):
    """Names in a hostname or business URL are not contact echoes."""
    # Exact known email/phone identifiers must not appear in a public URL.
    if private_identifier_in_reference(url, private_values):
        return True
    if not mail_context:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        # Malformed links inside private email are not safe public references.
        return True
    private_keys = {"token", "verification", "auth", "signature", "magic_link", "access_token", "email", "code", "uid", "key"}
    return (any(k.lower() in private_keys for k, _ in parse_qsl(parts.query))
            or bool(re.search(r"/(?:verify|confirm|activate|magic-link)(?:/|$)", parts.path, re.I)))


def _redact_text(text, private_values, mail_context):
    variants = {variant for private in private_values if private
                for variant in (str(private), quote(str(private), safe=""), quote_plus(str(private), safe=""))}

    def scrub(fragment):
        for private in sorted(variants, key=len, reverse=True):
            fragment = re.sub(_contact_pattern(private), "[research contact]", fragment, flags=re.I)
        for private in private_values:
            phone = _phone_contact_pattern(private)
            if phone:
                fragment = re.sub(phone, "[research contact]", fragment)
        return fragment

    pieces, start = [], 0
    for match in _PUBLIC_URL_PATTERN.finditer(text):
        pieces.append(scrub(text[start:match.start()]))
        url = match.group(0)
        pieces.append("[private email URL]" if _private_mail_url(url, private_values, mail_context) else url)
        start = match.end()
    pieces.append(scrub(text[start:]))
    return "".join(pieces)


def redact(value, private_values: list[str], mail_context: bool = False, *, _text=False, _field=None, _reference=False):
    """Scrub public prose while preserving identity and pinned graph references.

    Tokenized email links may be hidden in mail events and free text. A private
    contact URL used as a bound destination/asset is rejected instead of silently
    publishing a different reference that no longer matches the source hashes.
    """
    if isinstance(value, str):
        if _reference and private_identifier_in_reference(value, private_values):
            raise FunnelError("private contact identifier in a pinned public reference; use a public destination or safely named display asset")
        if _field in _PUBLIC_URL_FIELDS and _private_mail_url(value, private_values, mail_context):
            if _reference:
                raise FunnelError("private contact URL in a pinned public reference; provide a public destination or display asset")
            return "[private email URL]"
        return _redact_text(value, private_values, mail_context) if _text or _field is None else value
    if isinstance(value, dict):
        mail_context = mail_context or value.get("type") in {"email_confirmation", "email_result"} or str(value.get("source_ref") or "").lower().startswith("mail:")
        public = {}
        for key, item in value.items():
            if key in _PRIVATE_ROW_FIELDS:
                continue
            if key == "source_ref" and isinstance(item, str) and item.lower().startswith("mail:"):
                public[key] = "[private mail source]"
                continue
            reference = _reference or key in _PUBLIC_REFERENCE_FIELDS or key in {"id", "ids", "ref", "refs", "source_ref"} or key.endswith(("_id", "_ids", "_ref", "_refs", "_sha256"))
            structural = reference or key in _PUBLIC_URL_FIELDS or key in _PUBLIC_METADATA_FIELDS or key.endswith(_PUBLIC_METADATA_SUFFIXES)
            public[key] = redact(item, private_values, mail_context,
                _text=not structural, _field=key, _reference=reference)
        return public
    if isinstance(value, list):
        return [redact(v, private_values, mail_context, _text=_text, _field=_field, _reference=_reference) for v in value]
    if _text and type(value) is int and any(
            pattern and re.fullmatch(pattern, str(value))
            for pattern in (_phone_contact_pattern(private) for private in private_values)):
        return "[research contact]"
    return value
