#!/usr/bin/env python3
"""Prepare every selected 04 funnel, validate mobile-browser research, publish v2.

The runner makes no network requests or form submissions. The executing agent
walks real browser screens using explicit human approval and an intent journal.
Resume preserves aliases, observations and already attempted submissions.
"""
from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path
import argparse
import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA_VERSION = 2
SECTION_ID = "funnel_teardown"
SECTION_HEADING = "Funnel teardown"
DISPLAY_NAME = "Funnel Teardown"
RUNTIME_REL = Path(_artifact_path("egbe-docs/research/market/work/funnel_teardown"))
EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/funnel-teardown.json"))
CREATIVE_PATTERNS_EVIDENCE_REL = Path(_artifact_path("egbe-docs/research/market/evidence/creative-patterns.json"))
REPORT_REL = Path(_artifact_path("egbe-docs/research/market/full-report.md"))
WALKS_FILENAME = "walks.json"
CANDIDATES_FILENAME = "candidates.json"


def _load_script(filename, name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = _load_script("funnel-model.py", "pmr_funnel_model")
IO = _load_script("research-artifact-io.py", "pmr_funnel_io")
POLICY = _load_script("research-policy.py", "pmr_funnel_policy")
INTEGRITY = _load_script("research_integrity.py", "pmr_funnel_integrity")
EMAIL = _load_script("funnel-email-review.py", "pmr_funnel_email")
FunnelTeardownError = MODEL.FunnelError
WALK_VIEWPORT = MODEL.VIEWPORT
SCREEN_KINDS = MODEL.SCREEN_KINDS
ADVANCE_KINDS = MODEL.ADVANCE_KINDS


class UpstreamPending(FunnelTeardownError):
    pass


def _arg(args, key, default=None):
    value = getattr(args, key, None)
    return default if value is None else value


def _read(path, default=None):
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise FunnelTeardownError(f"invalid JSON artifact: {path.name}") from exc
    if not isinstance(data, dict):
        raise FunnelTeardownError(f"{path.name} must contain a JSON object")
    return data


def _path(workspace, value, default):
    path = Path(value or default)
    return path if path.is_absolute() else workspace / path


def load_upstream(workspace):
    reader = _load_script("research-evidence.py", "pmr_funnel_upstream")
    inspected = reader.inspect_section(workspace, "creative_patterns")
    if inspected.get("status") != "completed":
        raise UpstreamPending("04 is pending, stale or unverified: " + str(inspected.get("reason") or "refresh publication"))
    document = inspected.get("data") or _read(workspace / CREATIVE_PATTERNS_EVIDENCE_REL)
    selector = _load_script("creative-selection.py", "pmr_funnel_selection")
    selection = selector.read_selection(workspace, document)
    policy, digest = POLICY.load_policy()
    inputs = document.get("inputs") or {}
    if document.get("schema_version") != 2 or inputs.get("policy_sha256") != digest or inputs.get("effective_policy") != policy:
        raise FunnelTeardownError("04 policy or contract changed; refresh 04 before funnel research")
    return document, selection, policy


def build_candidates(campaigns, context):
    candidates = []
    by_funnel = {}
    for c in campaigns:
        if c["funnel_id"] in by_funnel:
            existing = by_funnel[c["funnel_id"]]
            existing["campaign_ids"].append(c["campaign_id"])
            existing["creative_ids"].extend(c["creative_ids"])
            existing["original_urls"].extend(c["original_urls"])
            continue
        row = {k: c.get(k) for k in ("funnel_id", "domain", "address", "country", "channel", "competitor_tier", "role", "original_urls", "rank")}
        row.update(campaign_ids=[c["campaign_id"]], creative_ids=c["creative_ids"], observation_status=c["observation_status"], primary_path_id="buyer")
        row["original_urls"] = list(row["original_urls"])
        row["creative_ids"] = list(row["creative_ids"])
        if c.get("equivalence_ref"):
            row["equivalence_ref"] = c["equivalence_ref"]
        candidates.append(row)
        by_funnel[c["funnel_id"]] = row
    seen = set()
    for entry in context.get("own_destinations", []):
        if isinstance(entry, str):
            entry = {"url": entry, "country": context.get("target_market")}
        address = MODEL.url_identity(entry.get("url"))
        key = (address, entry.get("country"))
        if key in seen:
            continue
        seen.add(key)
        candidates.append({"funnel_id": MODEL.identity("own", key), "domain": urlsplit(address).hostname,
                           "address": address, "country": entry.get("country"), "channel": "own", "role": "own",
                           "competitor_tier": "own", "campaign_ids": [], "creative_ids": [], "observation_status": "not_applicable",
                           "original_urls": [entry["url"]], "primary_path_id": "buyer", "rank": len(candidates) + 1})
    return candidates


def landing_rows(walks):
    rows = []
    for walk in walks:
        for screen in walk["screens"]:
            row = {k: walk.get(k) for k in ("funnel_id", "path_id", "walk_id", "domain", "role", "country", "channel", "campaign_ids", "creative_ids")}
            row.update(type="landing_page", page_id=MODEL.identity("page", [walk["walk_id"], screen["screen_id"]]),
                       screen_id=screen["screen_id"], address=screen["url"], page_type=screen.get("page_type", "unknown"),
                       headline=screen["headline"], primary_cta=screen.get("cta"), offer=screen.get("offer"),
                       proof=screen.get("proof", []), amounts=screen.get("amounts", []), lead_fields=screen.get("lead_fields", []),
                       screenshot=screen["screenshot"], screenshots=screen.get("screenshots", []),
                       retrieved_on=walk["walked_on"], source="browser", tier="A")
            rows.append(row)
    return rows


def _cell(value):
    return str(value if value is not None else "not observed").replace("|", "\\|").replace("\n", " ")


def private_contact_values(context, registry, mailbox, plans):
    """Collect identities, not contact preferences such as 'Email'."""
    private = [r.get("alias", "") for r in registry.get("identities", [])] + [mailbox or ""]
    private += [p.get("name") or "" for p in [context.get("persona", {}), *context.get("additional_personas", [])]]
    names = {"name", "first_name", "last_name", "full_name", "given_name", "family_name", "contact_name"}
    for form in plans.get("forms", []):
        for key, value in form.get("fields", {}).items():
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower().replace("-", "_").replace(" ", "_")
            identifier = normalized in {"email", "email_address", "phone", "phone_number", "telephone", "mobile", "mobile_number"} or normalized.endswith(("_email", "_email_address", "_phone", "_phone_number", "_telephone", "_mobile"))
            if normalized in names or identifier:
                private.append(str(value))
    return list(dict.fromkeys(value for value in private if value))


def render_section(*, campaigns, walks, patterns, coverage, as_of):
    lines = [f"Selected creative → funnel combinations; campaign cutoff {as_of}. Browser dates are separate.", "", "### A. Selected campaigns and funnel screens", ""]
    by_campaign = {c["campaign_id"]: c for c in campaigns}
    for walk in walks:
        lines += [f"#### {walk['country'] or 'unknown market'} · {walk['channel']} · {walk['domain']} · {walk['path_id']}", "",
                  f"Status: {walk['status']}; observed outcome: {walk.get('observed_outcome') or 'not observed'}; stop: {walk['stop_reason']}.",
                  f"Observed main screens: {walk['observed_screens_count']}; full length: {walk['full_screens_count'] or 'unknown'}; advertising observation: {walk['observation_status']}.",
                  f"Unknown: {', '.join(walk['unknown']) or 'none recorded'}.", ""]
        for cid in walk["campaign_ids"]:
            for creative in by_campaign[cid]["creatives"]:
                lines.append(f"Creative {creative['creative_id']}: {_cell(creative.get('headline'))} — {_cell(creative.get('body'))}")
                for asset in creative.get("media_assets", []):
                    if asset.get("path"):
                        lines.append(f"![Creative preview]({asset['path']})")
        lines += ["", "| # | Screen | Headline | Advance | Answer | Offer / price / result | Screenshot |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for screen in walk["screens"]:
            detail = {k: screen.get(k) for k in ("offer", "amounts", "result_type") if screen.get(k)}
            lines.append(f"| {screen['n']} | {_cell(screen['kind'])} ({screen['branch_role']}) | {_cell(screen['headline'])} | {screen['advance']} | {_cell(screen.get('answer'))} | {_cell(detail)} | [screen]({screen['screenshot']['path']}) |")
        lines.append("")
        for screen in walk["screens"]:
            lines += [f"![{walk['domain']} {screen['screen_id']}]({screen['screenshot']['path']})", ""]
    lines += ["### B. Patterns by channel and market", "", "| Market | Channel | Pattern | Campaigns / known | Unknown | Observed / dated convergence | Activity |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for p in patterns:
        lines.append(f"| {p.get('country') or 'unknown'} | {p['channel']} | {_cell(p['pattern'])} | {p['campaigns_with']} / {p['known_campaigns_total']} | {p['unknown_campaigns']} | {p['observed_convergence']} / {p['dated_convergence']} | {p['observation_status']} |")
    lines += ["", "### Coverage and continuation", ""]
    for gap in coverage:
        lines.append(f"- {gap.get('country') or 'unknown'} / {gap.get('channel') or 'own'} / {gap.get('domain') or 'all'}: {gap['status']} — {_cell(gap['detail'])}")
    lines += ["", "Proof is the shared advertising-duration proxy, not measured conversion. Replicate observed structure; never copy competitor claims or figures.", ""]
    return "\n".join(lines)


def lifecycle_handoff(intents, outcomes, existing, candidates, walks=()):
    by_funnel = {c["funnel_id"]: c for c in candidates}
    handoff = {"schema_version": 1, "subscriptions": [], "events": (existing or {}).get("events", [])}
    subscriptions = {}
    for eid, intent in intents.items():
        if outcomes.get(eid, {}).get("outcome") != "submitted":
            continue
        f = intent["form"]
        observed_path = next((w for w in walks if w["funnel_id"] == f["funnel_id"] and w["path_id"] == f["path_id"]), {})
        expectations = observed_path.get("email_expectations", {"confirmation": None, "result": None, "source_ref": None})
        if not isinstance(expectations, dict) or any(type(expectations.get(key)) not in (bool, type(None)) for key in ("confirmation", "result")):
            raise FunnelTeardownError("email expectations must be explicit booleans or unknown")
        if any(expectations.get(key) is not None for key in ("confirmation", "result")):
            source = expectations.get("source_ref")
            screen_ids = {s["screen_id"] for s in observed_path.get("screens", [])}
            if not isinstance(source, str) or not source.startswith("browser:") or source[8:] not in screen_ids:
                raise FunnelTeardownError("known email expectations require the actual browser screen reference")
        if expectations.get("wait_until") is not None:
            deadline = EMAIL.timestamp(expectations["wait_until"])
            if deadline is None or deadline < EMAIL.timestamp(intent["occurred_at"]) or not any(expectations.get(key) is True for key in ("confirmation", "result")):
                raise FunnelTeardownError("expected email wait_until must be an observed future timestamp")
        entry = {"domain": by_funnel[f["funnel_id"]]["domain"], "alias": f["alias"], "funnel_id": f["funnel_id"],
            "campaign_refs": f["campaign_ids"], "path_refs": [f["path_id"]], "entry_url": f["url"], "kind": f["purpose"],
            "subscribed_on": intent["occurred_at"][:10], "confirmed": outcomes[eid].get("confirmed") is True,
            "submission_ref": eid, "submission_refs": [eid], "approval_ref": intent["approval_id"],
            "submission_checks": [{"submission_ref": eid, "submitted_at": intent["occurred_at"],
                "path_id": f["path_id"], "campaign_refs": f["campaign_ids"],
                "confirmed": outcomes[eid].get("confirmed") is True, "email_expectations": dict(expectations)}],
            "email_expectations": dict(expectations)}
        prior = subscriptions.get(f["funnel_id"])
        if prior:
            if prior["alias"] != entry["alias"]:
                raise FunnelTeardownError("one physical funnel cannot use different research aliases")
            prior["campaign_refs"] = list(dict.fromkeys(prior["campaign_refs"] + entry["campaign_refs"]))
            prior["path_refs"] = list(dict.fromkeys(prior["path_refs"] + entry["path_refs"]))
            prior["submission_refs"].append(eid)
            prior["submission_checks"].extend(entry["submission_checks"])
            prior["confirmed"] = prior["confirmed"] or entry["confirmed"]
            for key in ("confirmation", "result"):
                values = (prior["email_expectations"].get(key), expectations.get(key))
                prior["email_expectations"][key] = True if True in values else False if all(value is False for value in values) else None
            if expectations.get("wait_until") and EMAIL.timestamp(expectations["wait_until"]) > (EMAIL.timestamp(prior["email_expectations"].get("wait_until")) or EMAIL.timestamp(intent["occurred_at"])):
                prior["email_expectations"]["wait_until"] = expectations["wait_until"]
        else:
            subscriptions[f["funnel_id"]] = entry
    handoff["subscriptions"] = list(subscriptions.values())
    return handoff


def _source_files(workspace, paths):
    result = {}
    for path in paths:
        path = Path(path)
        path = path if path.is_absolute() else workspace / path
        try:
            relative = path.resolve().relative_to(workspace.resolve()).as_posix()
        except ValueError as exc:
            raise FunnelTeardownError("research inputs must be inside the workspace") from exc
        result[relative] = IO.sha256(path) if path.is_file() else None
    return result


def _run(workspace, args):
    runtime = workspace / RUNTIME_REL
    runtime.mkdir(parents=True, exist_ok=True)
    context_path = _path(workspace, _arg(args, "context"), RUNTIME_REL / "research-context.json")
    context = _read(context_path, {})
    if _arg(args, "own_destinations", ""):
        context["own_destinations"] = [url.strip() for url in args.own_destinations.split(",") if url.strip()]
    if _arg(args, "mailbox"):
        context["mailbox"] = args.mailbox
    if _arg(args, "own_destinations", "") or _arg(args, "mailbox"):
        IO.write_json(context_path, context)
    creative_doc, selection, policy = load_upstream(workspace)
    creative_inputs = creative_doc.get("inputs") or {}
    as_of = _arg(args, "as_of", "") or creative_inputs.get("as_of") or creative_doc.get("as_of")
    try:
        date.fromisoformat(as_of)
    except (TypeError, ValueError) as exc:
        raise FunnelTeardownError("04 must publish its campaign cutoff date") from exc
    if _arg(args, "as_of", "") and args.as_of != (creative_inputs.get("as_of") or creative_doc.get("as_of")):
        raise FunnelTeardownError("05 cannot move the pinned 04 campaign cutoff")
    enrichment_path = runtime / "destinations.json"
    enrichment = _read(enrichment_path, {})
    campaigns, gaps = MODEL.prepare_campaigns(selection, creative_doc, policy, as_of, enrichment)
    footprint = _read(workspace / _artifact_path("egbe-docs/research/market/evidence/channel-footprint.json"), {})
    MODEL.bind_activity_provenance(campaigns, footprint, policy)
    MODEL.apply_copy_policy(campaigns, footprint)
    selected_scopes = {(r.get("country"), r.get("channel")) for r in selection.get("selected_creatives", [])}
    countries = (footprint.get("inputs") or {}).get("target_countries", [])
    for observation in footprint.get("rows", []):
        if observation.get("type") != "channel_observation":
            continue
        for country in countries:
            scope = (country, observation.get("channel"))
            if scope not in selected_scopes and not any(g.get("country") == country and g.get("channel") == observation.get("channel") for g in gaps):
                gaps.append({"type": "coverage", "country": country, "channel": observation.get("channel"), "status": "no_selected_campaign",
                    "detail": "Observed 03 channel has no selected 04 creative in this market; campaign/destination not extracted",
                    "source": "channel_footprint_observation", "tier": "C"})
    equivalence_path = runtime / "equivalences.json"
    equivalence_assets = MODEL.apply_equivalences(campaigns, _read(equivalence_path, {}), workspace)
    candidates = build_candidates(campaigns, context)
    registry_path = workspace / _artifact_path("egbe-docs/research/market/work/identity-registry.json")
    registry = _read(registry_path, {})
    identity_binding = None
    mailbox = context.get("mailbox") or registry.get("mailbox")
    if mailbox:
        with IO.file_lock(registry_path.with_name(registry_path.name + ".lock")):
            registry = MODEL.allocate_identities(_read(registry_path), mailbox, campaigns)
            IO.write_json(registry_path, registry)
        aliases = {r["funnel_id"]: r["alias"] for r in registry["identities"] if r.get("funnel_id")}
        for campaign in campaigns:
            if not any(row.get("funnel_id") == campaign["funnel_id"] and row.get("domain") == campaign["domain"] for row in registry["identities"]):
                raise FunnelTeardownError("stable funnel identity conflicts with its competitor domain")
        identity_binding = INTEGRITY.identity_binding(registry, funnel_ids=[c["funnel_id"] for c in campaigns])
        for c in candidates:
            if c["role"] != "own":
                c["planned_alias"] = aliases[c["funnel_id"]]
    source_paths = [CREATIVE_PATTERNS_EVIDENCE_REL, creative_inputs.get("creative_selection_path") or _artifact_path("egbe-docs/research/market/evidence/creative-selection.v1.json"),
        _artifact_path("egbe-docs/research/market/evidence/channel-footprint.json"), _artifact_path("egbe-docs/research/market/evidence/competitors.json"),
        _artifact_path("egbe-docs/research/market/work/creative_patterns/request.json"), _artifact_path("egbe-docs/research/market/work/channel_footprint/request.json"),
        _artifact_path("egbe-docs/research/market/work/competitor_set/request.json"), IO.context_path(SECTION_ID), context_path, enrichment_path, equivalence_path]
    resume_inputs = {"source_files": _source_files(workspace, source_paths), "research_context_sha256": MODEL.canonical_hash(context),
        "creative_patterns_sha256": IO.sha256(workspace / CREATIVE_PATTERNS_EVIDENCE_REL),
        "creative_selection_sha256": creative_inputs.get("creative_selection_sha256"), "effective_policy": policy,
        "policy_sha256": MODEL.canonical_hash(policy), "campaign_as_of": as_of, "walk_contract": MODEL.CONTRACT,
        "angle_dictionary_sha256": (creative_doc.get("angle_dictionary") or {}).get("dictionary_sha256")}
    if identity_binding is not None:
        resume_inputs["identity_registry_binding"] = identity_binding
    inputs_sha = MODEL.canonical_hash(resume_inputs)
    inputs = {k: v for k, v in resume_inputs.items() if k != "source_files"}
    inputs.update(resume_inputs=resume_inputs, inputs_sha256=inputs_sha, research_context=IO.context_binding(workspace, SECTION_ID),
                  creative_selection_path=creative_inputs.get("creative_selection_path"), research_context_sha256=MODEL.canonical_hash(context), viewport=WALK_VIEWPORT)
    walks_path = _path(workspace, _arg(args, "walks"), RUNTIME_REL / WALKS_FILENAME)
    IO.write_json(runtime / CANDIDATES_FILENAME, {"schema_version": 2, "section_id": SECTION_ID, "contract": MODEL.CONTRACT,
        "inputs_sha256": inputs_sha, "campaign_as_of": as_of, "walks_path": walks_path.as_posix(), "viewport": WALK_VIEWPORT,
        "candidates": candidates, "campaigns": campaigns, "coverage": gaps,
        "rules": ["Walk every selected distinct funnel; preserve unfinished work for resume.",
            "Real mobile screenshots and hashes per screen. Main route and auxiliary popups are separate.",
            "Review pixels for contacts and private verification URLs; keep raw captures private and declare real privacy-redacted display derivatives where needed. Hashes do not sanitize pixels.",
            "Exact forms/data require human chat confirmation; supplements for new fields. Journal intent before sending.",
            "No account creation, payment/card entry, CAPTCHA bypass or live sales call booking. Own funnels never submit.",
            "Stable aliases; same-day email capture; explicit pending and unknown downstream."]})
    defaults = {"approval-plan.json": {"schema_version": 2, "forms": []}, "approvals.json": {"schema_version": 2, "approvals": []}, "submissions.json": {"schema_version": 2, "events": []}}
    for name, value in defaults.items():
        if not (runtime / name).exists():
            IO.write_json(runtime / name, value)
    state = {"schema_version": 1, "section_id": SECTION_ID, "status": "pending", "error": None, "as_of": as_of,
        "inputs_sha256": inputs_sha, "policy_sha256": inputs["policy_sha256"], "research_context": inputs["research_context"],
        "candidates_path": (RUNTIME_REL / CANDIDATES_FILENAME).as_posix(), "walks_path": walks_path.as_posix(),
        "unwalked": [c["funnel_id"] for c in candidates], "provider_calls": 0, "documents": 0,
        "domains": list(dict.fromkeys(c["domain"] for c in campaigns))}
    if identity_binding is not None:
        state["identity_registry_binding"] = identity_binding
    missing = []
    if not context.get("persona", {}).get("id") or not context.get("persona", {}).get("name"):
        missing.append("explicit buyer persona from offer card")
    if not context.get("own_destinations"):
        missing.append("own destination URLs from intake/product context")
    walks_doc = _read(walks_path)
    if missing or walks_doc is None or _arg(args, "phase", "auto") == "prepare":
        state["reason"] = "Missing " + ", ".join(missing) if missing else "Browser observations required; read candidates and the v2 walk contract"
        IO.write_json(runtime / "request.json", state)
        return state
    if walks_doc.get("schema_version") != 2:
        state.update(reason="Legacy walks: preserve raw evidence, collect fresh screenshots and deep paths", legacy=True)
        IO.write_json(runtime / "request.json", state)
        return state
    plans, approvals, journal = (_read(runtime / name) for name in defaults)
    checkpoint_path = runtime / "journal-checkpoint.json"
    checkpoint = MODEL.validate_append_only(_read(checkpoint_path, {}), plans, approvals, journal)
    intents, outcomes = MODEL.validate_journals(plans, approvals, journal, candidates, registry)
    IO.write_json(checkpoint_path, checkpoint)
    walks = MODEL.attach_campaigns(MODEL.validate_walks(walks_doc, candidates, workspace, inputs_sha, intents, outcomes), campaigns)
    allowed_personas = {context["persona"]["id"], *(p.get("id") for p in context.get("additional_personas", []))}
    for walk in walks:
        if walk["path_id"] == "buyer" and walk["persona_id"] != context["persona"]["id"]:
            raise FunnelTeardownError("primary path persona must match the agreed buyer context")
        if walk["persona_id"] not in allowed_personas:
            raise FunnelTeardownError("additional persona must be explicitly declared in research context")
    email_path = workspace / _artifact_path("egbe-docs/research/market/work/lifecycle_capture/funnel-events.json")
    email_doc = _read(email_path, {"events": [], "pending": []})
    for w in walks:
        w["email_events"] = [e for e in email_doc.get("events", []) if e.get("funnel_id") == w["funnel_id"] and e.get("path_id") in (None, w["path_id"])]
    handoff = lifecycle_handoff(intents, outcomes, _read(runtime / "lifecycle-handoff.json"), candidates, walks)
    IO.write_json(runtime / "lifecycle-handoff.json", handoff)
    email_coverage = []
    for subscription in handoff["subscriptions"]:
        review = EMAIL.review(subscription, email_doc)
        for w in walks:
            if w["funnel_id"] == subscription["funnel_id"]:
                w["email_review"] = review
        if review["pending"] or review["gaps"]:
            email_coverage.append({"type": "coverage", "funnel_id": subscription["funnel_id"],
                "campaign_ids": subscription["campaign_refs"], "status": "needs_email" if review["pending"] else "email_coverage_gap",
                "detail": review["detail"], "gaps": review["gaps"], "unknown": review["unknown"],
                "terminal": not review["pending"], "source": "same_day_lifecycle_handoff", "tier": "C"})
    by_funnel = {}
    for w in walks:
        by_funnel.setdefault(w["funnel_id"], []).append(w)
    pending, coverage = [item["funnel_id"] for item in email_coverage if not item["terminal"]], list(gaps) + email_coverage
    for c in candidates:
        paths = by_funnel.get(c["funnel_id"], [])
        main = next((w for w in paths if w["path_id"] == c["primary_path_id"]), None)
        if not main:
            pending.append(c["funnel_id"])
            status, detail = "queued", "Selected primary buyer path has not been observed"
        elif any((w["status"] in MODEL.PENDING_STATUSES and
                  (w["status"] != "needs_email" or w.get("email_review", {}).get("pending", True)))
                 or w["stop_reason"] == "budget" for w in paths):
            pending.append(c["funnel_id"])
            status, detail = main["status"], "; ".join(main["unknown"]) or main["stop_reason"]
        else:
            status, detail = main["status"], main["stop_reason"]
        missing_paths = [point.get("alternate_path_id") for w in paths for point in w.get("branch_points", [])
                         if point.get("meaningful_change") is True and not any(other["path_id"] == point.get("alternate_path_id") for other in paths)]
        if missing_paths:
            pending.append(c["funnel_id"])
            status, detail = "queued", "Additional relevant offer/result/conversion branches need observation: " + ", ".join(str(x) for x in missing_paths)
        coverage.append({"type": "coverage", "funnel_id": c["funnel_id"], "campaign_ids": c["campaign_ids"], "creative_ids": c["creative_ids"],
            "domain": c["domain"], "role": c["role"], "country": c.get("country"), "channel": c["channel"], "source": "browser_walk",
            "status": status, "detail": detail, "tier": "C" if status != "completed" else "A"})
    uncertain = [eid for eid in intents if outcomes.get(eid, {}).get("outcome") in (None, "unknown")]
    if uncertain:
        pending += [intents[eid]["form"]["funnel_id"] for eid in uncertain]
        coverage.append({"type": "coverage", "status": "submission_outcome_unknown", "detail": "Inspect already attempted submission before retry",
                         "submission_refs": uncertain, "source": "submission_journal", "tier": "C"})
    patterns, pages = MODEL.aggregate_patterns(campaigns, walks), landing_rows(walks)
    assets = equivalence_assets + [asset for w in walks for s in w["screens"] for asset in [s["screenshot"], *s.get("screenshots", [])]]
    source_files = _source_files(workspace, source_paths + [walks_path, email_path, runtime / "lifecycle-handoff.json",
        checkpoint_path, *(runtime / name for name in defaults), *(a["path"] for a in assets),
        *(s["source_screenshot"]["path"] for w in walks for s in w["screens"] if s.get("source_screenshot"))])
    inputs.update(source_files=source_files, assets=assets)
    inputs["resume_inputs"] = resume_inputs
    private = private_contact_values(context, registry, mailbox, plans)
    if any(MODEL.private_identifier_in_reference(path, private) for path in inputs["source_files"]):
        raise FunnelTeardownError("private contact identifier in a pinned source filename; use a safely named capture before publication")
    rows = MODEL.redact(campaigns + pages + walks + patterns + coverage, private)
    document = {"schema_version": 2, "section_id": SECTION_ID, "generated_by": "run-funnel-teardown.py", "retrieved_on": date.today().isoformat(),
        "inputs": inputs, "rows": rows, "totals": {"campaigns": len(campaigns), "selected_funnels": len(candidates), "landing_pages": len(pages),
        "walks": len(walks), "patterns": len(patterns), "pending": len(set(pending)), "observations": sum(len(w["screens"]) for w in walks), "documents": 0, "provider_calls": 0}}
    IO.write_json(workspace / EVIDENCE_REL, document)
    section = render_section(campaigns=[r for r in rows if r["type"] == "campaign"], walks=[r for r in rows if r["type"] == "funnel_walk"],
        patterns=[r for r in rows if r["type"] == "funnel_pattern"], coverage=[r for r in rows if r["type"] == "coverage"], as_of=as_of)
    IO.write_atomic(runtime / "result.md", section)
    report = workspace / REPORT_REL
    report.parent.mkdir(parents=True, exist_ok=True)
    _load_script("upsert-markdown-section.py", "pmr_funnel_upsert").upsert_markdown_section(report, SECTION_HEADING, section)
    state.update(unwalked=sorted(set(pending)), walks=len(walks), patterns=len(patterns), landing_pages=len(pages), pages_read=len(pages),
        observations=document["totals"]["observations"], source_files=source_files, assets=assets,
        evidence_path=EVIDENCE_REL.as_posix(), evidence_sha256=IO.sha256(workspace / EVIDENCE_REL), result_path=(RUNTIME_REL / "result.md").as_posix(),
        result_sha256=IO.sha256(runtime / "result.md"), walks_sha256=IO.sha256(walks_path))
    if pending:
        state["reason"] = "Selected paths need continuation, approval, email or submission-outcome verification"
    else:
        persistence = _load_script("persist-research-report.py", "pmr_funnel_persist").persist_research_report(workspace,
            commit_message="research: update funnel teardown section", extra_paths=(Path(_artifact_path("egbe-docs/research/market/evidence/funnel-teardown.json")),))
        state.update(status="completed", reason=None, publication_mode=persistence.publication_mode, report_commit_sha=persistence.commit_sha)
        IO.write_json(runtime / "as-of.json", {"as_of": as_of, "completed": True})
    IO.write_json(runtime / "request.json", state)
    return state


def run(workspace, args):
    workspace = Path(workspace).resolve()
    with IO.section_attempt(workspace, SECTION_ID, context_file=getattr(args, "context_file", None)):
        try:
            return _run(workspace, args)
        except UpstreamPending as exc:
            state = {"schema_version": 1, "section_id": SECTION_ID, "status": "pending", "error": None,
                     "research_context": IO.context_binding(workspace, SECTION_ID),
                     "reason": str(exc), "unwalked": [], "provider_calls": 0}
            IO.write_json(workspace / RUNTIME_REL / "request.json", state)
            return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--context-file", type=Path, help="Explicit additional research context; optional for this operation.")
    parser.add_argument("--phase", choices=("auto", "prepare", "finalize"), default="auto")
    parser.add_argument("--context", default="", help="Private context with persona and own destinations")
    parser.add_argument("--own-destinations", default="", help="Explicit comma-separated own HTTP(S) URLs")
    parser.add_argument("--mailbox", default="", help="Base research mailbox, otherwise use identity registry")
    parser.add_argument("--walks", default="")
    parser.add_argument("--as-of", default="", help="Must equal the pinned 04 cutoff")
    parser.add_argument("--product-domain", default="", help="Invocation compatibility; own destinations must be explicit")
    args = parser.parse_args()
    try:
        state = run(args.workspace, args)
    except (FunnelTeardownError, ValueError, OSError) as exc:
        print(f"{DISPLAY_NAME}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: state.get(k) for k in ("status", "reason", "unwalked", "walks", "patterns")}, indent=2))
    return 2 if state["status"] == "pending" else 0


if __name__ == "__main__":
    raise SystemExit(main())
