#!/usr/bin/env python3
"""Pure, scoped normalization and decisions for Channel Footprint v2.

Dates describe delivery only when the provider supplies native delivery
scope. Listing observations never supply delivery duration.
"""
from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path
import hashlib
import json
from datetime import date, timedelta
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def countries(values: Any) -> list[str]:
    if isinstance(values, str):
        values = values.replace(";", ",").split(",")
    result = []
    aliases = {"UK": "GB", "UNITED KINGDOM": "GB", "UNITED STATES": "US", "GERMANY": "DE", "FRANCE": "FR", "CANADA": "CA", "AUSTRALIA": "AU"}
    iso = set("AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split())
    for value in values or []:
        code = aliases.get(str(value).strip().upper(), str(value).strip().upper())
        if code in {"EU", "EUROPE", "EEA"}:
            raise ValueError("EU/EEA requires an explicit country list in intake; no proxy country is chosen")
        if code not in iso:
            raise ValueError(f"country must be an ISO alpha-2 code: {value}")
        if code not in result:
            result.append(code)
    return result


def days(start, end):
    try:
        return max(0, (date.fromisoformat(str(end)[:10]) - date.fromisoformat(str(start)[:10])).days)
    except (ValueError, TypeError):
        return None


def valid_date(value):
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (ValueError, TypeError):
        return None


def text_value(value):
    if isinstance(value, dict):
        return str(value.get("text") or value.get("value") or "")
    if isinstance(value, list):
        return "\n".join(text_value(x) for x in value if x)
    return str(value or "")


def ad_fields(raw):
    snapshot = raw.get("snapshot") if isinstance(raw.get("snapshot"), dict) else {}
    cards = snapshot.get("cards") or []
    card = cards[0] if cards and isinstance(cards[0], dict) else {}
    images = snapshot.get("images") or []
    videos = snapshot.get("videos") or []
    image = images[0] if images and isinstance(images[0], dict) else {}
    video = videos[0] if videos and isinstance(videos[0], dict) else {}
    return {
        "native_ad_id": str(raw.get("ad_archive_id") or raw.get("creativeId") or raw.get("adId") or raw.get("ad_id") or raw.get("id") or ""),
        "advertiser": text_value(raw.get("advertiserName") or raw.get("advertiser_name") or raw.get("page_name") or raw.get("pageName")),
        "landing_url": text_value(raw.get("destinationUrl") or raw.get("destination_url") or raw.get("landingUrl") or raw.get("landing_url") or raw.get("destination") or raw.get("clickUrl") or snapshot.get("link_url") or card.get("link_url") or raw.get("ad_creative_link_captions")),
        "source_url": text_value(raw.get("adUrl") or raw.get("ad_url") or raw.get("url") or raw.get("ad_snapshot_url")),
        "ad_text": text_value(raw.get("adText") or raw.get("text") or raw.get("ad_text") or raw.get("creativeText") or raw.get("ad_creative_bodies") or snapshot.get("body") or card.get("body") or snapshot.get("title") or raw.get("title")),
        "image_url": text_value(raw.get("imageUrl") or raw.get("image_url") or image.get("original_image_url") or image.get("resized_image_url") or video.get("video_preview_image_url") or card.get("original_image_url") or card.get("resized_image_url")),
        "video_url": text_value(raw.get("videoUrl") or raw.get("video_url") or video.get("video_hd_url") or video.get("video_sd_url")),
        "cta": text_value(raw.get("cta") or snapshot.get("cta_text") or card.get("cta_text") or snapshot.get("cta_type")),
    }


def observation(ad, source, country, market_scope, today, policy, date_scope="global", activity_scope="global"):
    # Only an explicit native delivery scope can narrow global provider dates.
    raw = ad.get("raw") or {}
    native_scope = raw.get("native_date_scope") or raw.get("date_scope")
    native_country = raw.get("delivery_country") or raw.get("date_country")
    if native_scope == "country" and native_country:
        date_scope, date_country = "country", str(native_country).upper().replace("UK", "GB")
    else:
        date_country = country if date_scope == "country" else None
    first, last = valid_date(ad.get("first_seen")), valid_date(ad.get("last_seen"))
    explicit = ad.get("is_active")
    listing = source in {"linkedin_library_actor", "reddit_inspiration_actor"}
    if listing:
        first_shown = last_shown = None
        status = "unknown"
    else:
        first_shown, last_shown = first, last
        stop_value = raw.get("end_date") or raw.get("endDate") or raw.get("ad_delivery_stop_time")
        stop = valid_date(stop_value) or last if stop_value else None
        # The Meta page-search actor reports the capture day as the end date of
        # an ad that is still active; only an end before capture is a stop.
        # That day is Pacific time, so an explicitly active ad may carry the
        # day before a capture made east of it.
        grace = timedelta(days=1) if explicit is True else timedelta(0)
        ended = bool(stop and date.fromisoformat(stop) < today - grace)
        if explicit is False or ended:
            status = "stopped"
        elif explicit is True:
            status = "active"
        else:
            status = "unknown"
    activity_scope = raw.get("native_activity_scope") or activity_scope
    activity_country = str(raw.get("activity_country") or country or "").upper().replace("UK", "GB") or None
    endpoint = last_shown if last_shown and date.fromisoformat(last_shown) <= today else None
    # A native last-delivery date wins even if an ad is globally active.
    # Extending country duration to capture requires that same country's
    # native active delivery; a global flag cannot extend a country span.
    same_delivery_scope = (date_scope == "global" and activity_scope == "global") or (date_scope == "country" and activity_scope == "country" and date_country == activity_country)
    if endpoint is None and status == "active" and same_delivery_scope:
        endpoint = today.isoformat()
    placement = str(raw.get("placement") or raw.get("platform") or "").lower() or None
    return {
        "source": source, "country": country, "market_scope": market_scope, "observed_on": today.isoformat(), "placement": placement,
        "date_scope": date_scope if not listing else "unknown", "date_country": date_country if not listing else None,
        "activity_scope": activity_scope,
        "activity_country": activity_country,
        "first_shown": first_shown, "last_shown": last_shown, "status": status,
        "first_observed": first if listing and source == "linkedin_library_actor" else today.isoformat(),
        "last_observed": last if listing and source == "linkedin_library_actor" else today.isoformat(),
        "served_days": days(first_shown, endpoint),
        "days_since_last_delivery": days(last_shown, today.isoformat()) if last_shown and last_shown <= today.isoformat() else None,
    }


def build_corpus(presences, context_hash, policy):
    corpus = {}
    for presence_index, presence in enumerate(presences):
        refs = []
        for ad_index, ad in enumerate(presence.get("ads") or []):
            fields = ad_fields(ad.get("raw") or {})
            family = "meta" if presence["platform"] == "meta_ads" else presence["platform"]
            native = fields["native_ad_id"]
            # No native id: scope the fingerprint to this observation. Equal
            # copy is not proof that two listings are a single continuous ad.
            identity = (family, presence["domain"], native) if native else (family, presence["domain"], fields, presence["source"], presence.get("country"), ad.get("first_seen"))
            ad_id = family + ":" + digest(identity)[:24]
            refs.append(ad_id)
            obs = observation(ad, presence["source"], presence.get("country"), presence["market_scope"], date.fromisoformat(presence["observed_on"]), policy, presence.get("native_date_scope", "global"), presence.get("native_activity_scope", "global"))
            item = corpus.setdefault(ad_id, {"type": "channel_ad", "ad_id": ad_id, "domain": presence["domain"], "platform": presence["platform"], "format": str(ad.get("format") or "unknown").lower(), **fields, "identity_method": "native_id" if native else "observation_fingerprint", "observations": [], "provider_observation_refs": [], "relevance": "unknown", "relevance_reason": "awaiting a context-bound relevance decision", "product_context_sha256": context_hash})
            item["provider_observation_refs"].append(_artifact_path(f"egbe-docs/research/market/work/channel_footprint/collected.json#/raw/presences/{presence_index}/ads/{ad_index}"))
            for key, value in fields.items():
                if value and not item.get(key):
                    item[key] = value
            if obs not in item["observations"]:
                item["observations"].append(obs)
            # Placements belong to each native observation, not the ad's
            # identity across all countries and provider results.
            placements = {o["placement"] for o in item["observations"] if o.get("placement")}
            item["placements"] = sorted(placements)
            item["placement"] = next(iter(placements)) if len(placements) == 1 else None
        presence["ad_ids"] = sorted(set(refs))
    for item in corpus.values():
        item["candidate_sha256"] = digest({k: item[k] for k in ("ad_id", "domain", "platform", "format", "advertiser", "landing_url", "source_url", "ad_text", "image_url", "cta", "product_context_sha256")})
    return sorted(corpus.values(), key=lambda x: x["ad_id"])


def apply_decisions(corpus, decisions, context_hash, stale="raise"):
    # A sample expansion can fill empty fields of an ad decided earlier, so
    # one ad has two candidate hashes within a collect. `stale` sets what a
    # decision for the other version does: "raise" (finalize), "accept" by
    # ad_id (pre-expansion gate) or "pending" (the ad goes back to review).
    if stale not in {"raise", "accept", "pending"}:
        raise ValueError(f"unknown stale decision mode: {stale}")
    if decisions and decisions.get("product_context_sha256") != context_hash:
        raise ValueError("relevance decisions belong to a different product/intake context")
    entries = decisions.get("decisions", []) if decisions else []
    if not isinstance(entries, list):
        raise ValueError("relevance decisions must be an array")
    by_id = {}
    for decision in entries:
        ad_id = decision.get("ad_id")
        if ad_id in by_id:
            raise ValueError(f"duplicate relevance decision: {ad_id}")
        by_id[ad_id] = decision
    pending = []
    for ad in corpus:
        decision = by_id.get(ad["ad_id"])
        if decision is None:
            pending.append(ad["ad_id"])
            continue
        if decision.get("candidate_sha256") != ad["candidate_sha256"]:
            if stale == "raise":
                raise ValueError(f"stale relevance decision for {ad['ad_id']}")
            if stale == "pending":
                ad["relevance_reason"] = "the ad changed after its relevance decision; review this version again"
                pending.append(ad["ad_id"])
                continue
        value = decision.get("relevance")
        reason = str(decision.get("reason") or "").strip()
        refs = decision.get("evidence_refs")
        if value not in {"relevant", "irrelevant", "unknown"} or not reason or not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs) or (value != "unknown" and not refs):
            raise ValueError(f"invalid relevance decision for {ad['ad_id']}: require relevance, reason and evidence_refs")
        ad.update(relevance=value, relevance_reason=reason, relevance_evidence_refs=refs, relevance_decision_sha256=digest(decision))
    return pending


def summarize_presences(presences, corpus, competitor_context, policy, context_hash, placement_filter=None):
    by_id = {a["ad_id"]: a for a in corpus}
    # Merge provider observations into one competitor/channel/country row.
    grouped = {}
    for raw in presences:
        key = (raw["domain"], raw["platform"], raw.get("country"))
        row = grouped.setdefault(key, {**{k: v for k, v in raw.items() if k != "ads"}, "ad_ids": [], "sources": [], "sampling": []})
        row["ad_ids"] = sorted(set(row["ad_ids"] + raw.get("ad_ids", [])))
        if raw["source"] not in row["sources"]:
            row["sources"].append(raw["source"])
        row["sampling"].append(raw.get("sampling") or {})
    result = []
    for row in grouped.values():
        country = row.get("country")
        selected = [by_id[x] for x in row["ad_ids"] if x in by_id and by_id[x]["relevance"] == "relevant" and (not placement_filter or any(o.get("country") == country and o.get("placement") == placement_filter for o in by_id[x]["observations"]))]
        current, historical, statuses = set(), set(), []
        max_duration, country_duration, formats, relevant_observed, scopes = None, None, {}, [], set()
        active, activity_scopes = set(), set()
        for ad in selected:
            matching = [o for o in ad["observations"] if o.get("country") == country and (not placement_filter or o.get("placement") == placement_filter)]
            local_current, local_historical = [], []
            for obs in matching:
                statuses.append(obs["status"])
                activity_scopes.add(obs["activity_scope"])
                if obs["status"] == "active":
                    active.add(ad["ad_id"])
                    # Current use is activity observed in this country's query
                    # (or native country delivery); global ad-level dates are accepted.
                    if country and obs.get("activity_country") == country and (obs["status"] == "active" or obs["date_scope"] == "global" or (obs["date_scope"] == "country" and obs["date_country"] == country)):
                        local_current.append(obs)
                duration = obs.get("served_days")
                if duration is not None:
                    max_duration = duration if max_duration is None else max(max_duration, duration)
                    scopes.add(obs["date_scope"])
                    if obs["date_scope"] == "country" and obs["date_country"] == country:
                        country_duration = duration if country_duration is None else max(country_duration, duration)
                # A native delivery span counts with global or this country's dates;
                # listing history (date scope unknown) never supplies a duration.
                if country and (obs["date_scope"] == "global" or (obs["date_scope"] == "country" and obs["date_country"] == country)) and duration is not None:
                    local_historical.append(obs)
            # Conflicting current statuses for the same market fail closed.
            if any(o["status"] == "stopped" for o in matching) and any(o["status"] in {"active", "recent"} for o in matching):
                local_current = []
            if local_current:
                current.add(ad["ad_id"])
            if local_historical:
                historical.add(ad["ad_id"])
            if any(o["status"] != "stopped" for o in matching):
                relevant_observed.append(ad["ad_id"])
            formats[ad["format"]] = formats.get(ad["format"], 0) + 1
        tier = (competitor_context.get(row["domain"]) or {}).get("competitor_tier", "unknown")
        row.update(competitor_tier=tier, product_context_sha256=context_hash, policy=policy, policy_sha256=digest(policy),
                   matched_ads=len(row["ad_ids"]), relevant_ads=len(selected), active_ads=len(active), formats=formats,
                   oldest_days=max_duration, max_observed_duration_days=max_duration, max_country_duration_days=country_duration,
                   activity_scopes=sorted(activity_scopes), placement=placement_filter,
                   current_ad_ids=sorted(current), historical_ad_ids=sorted(historical), relevant_ad_ids=[a["ad_id"] for a in selected],
                   observed_ad_ids=sorted(relevant_observed), current_presence=bool(current), native_duration_available=bool(historical),
                   present=bool(relevant_observed), relevance="relevant" if selected else "unknown",
                   relevance_reason="context-bound ad decisions" if selected else "no comparable ads confirmed in the available sample",
                   duration_scope=next(iter(scopes)) if len(scopes) == 1 else ("mixed" if scopes else "unknown"), target_country=country,
                   status="observed" if selected else "not_verifiable",
                   evidence_refs=sorted(a["ad_id"] for a in selected),
                   unknown_relevance_ads=sum(by_id[x]["relevance"] == "unknown" for x in row["ad_ids"] if x in by_id),
                   stopped_ads=sum(any(o["status"] == "stopped" for o in a["observations"] if o.get("country") == country) for a in selected),
                   unknown_activity_ads=sum(all(o["status"] == "unknown" for o in a["observations"] if o.get("country") == country) for a in selected),
                   activity_known=bool(active) or bool(statuses and all(s == "stopped" for s in statuses)))
        result.append(row)
    return result


def country_rows(presences, scans, target_countries, competitor_context, policy, channels):
    """Summarize scoped observations without eligibility or channel selection."""
    result = []
    for channel in channels:
        for country in target_countries:
            matched = [r for r in presences if r["platform"] == channel and r.get("country") == country]
            roles = {role: sorted({r["domain"] for r in matched if r["competitor_tier"] == role and r["relevant_ads"]})
                     for role in ("direct", "indirect", "substitute", "unknown")}
            signals = sorted({s["domain"] for s in scans if channel in s.get("channels_detected", [])})
            result.append({"type": "channel_country", "platform": channel, "channel": channel, "country": country,
                           "observed_domains_by_role": roles,
                           "active_domains": sorted({r["domain"] for r in matched if r["current_presence"]}),
                           "evidence_refs": sorted({ref for r in matched for ref in r["evidence_refs"]}),
                           "status": "observed" if any(roles.values()) else "not_verifiable",
                           "signal_domains": signals, "signal_scope": "domain_global_or_unknown",
                           "policy": policy, "policy_sha256": digest(policy)})
    return result
