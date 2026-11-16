"""Receipt-backed research inputs and bounded, provider-safe projections."""
from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import hashlib
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RUNTIME = Path(_artifact_path("egbe-docs/research/market/work"))
EVIDENCE = Path(_artifact_path("egbe-docs/research/market/evidence"))
MEASURED = {
    "keyword_economics": "keyword-economics.json", "competitor_set": "competitors.json",
    "channel_footprint": "channel-footprint.json", "creative_patterns": "creative-patterns.json",
    "funnel_teardown": "funnel-teardown.json",
    "lifecycle_capture": "lifecycle-capture.json", "competitor_ads": "competitor-ads.json",
    "review_mining": "review-mining.json", "community_demand": "community-demand.json",
    "fleet_prior": "fleet-prior.json",
}
INPUTS = {
    "market_size_dynamics": ("keyword_economics", "community_demand"),
    "target_audience": ("review_mining", "community_demand"),
    "competitive_landscape": ("keyword_economics", "competitor_set", "competitor_ads", "review_mining"),
    "value_proposition": ("review_mining", "community_demand", "competitor_ads", "funnel_teardown"),
    "pricing_monetization": ("competitor_ads", "review_mining", "lifecycle_capture"),
    "acquisition_channels": ("keyword_economics", "competitor_set", "channel_footprint", "creative_patterns", "funnel_teardown", "lifecycle_capture", "competitor_ads", "community_demand"),
    "demand_validation": ("keyword_economics", "competitor_ads", "review_mining", "community_demand"),
    "unit_economics": ("keyword_economics",),
}
# Only public measured facts. Fleet cases/private product context never pass here.
PUBLIC_FIELDS = frozenset({
    "type", "keyword", "locale_key", "locale", "domain", "kind", "url", "source", "sources", "platform",
    "search_volume", "cpc", "cpc_low", "cpc_high", "competition", "intent_signal", "free_edu_intent",
    "paid_by", "title", "description", "text", "quote", "query", "stars", "rating", "price",
    "pricing_mentions", "billing_pricing_complaint", "switched_reason", "reason", "tier", "found_via",
    "excerpt", "date", "served_days", "status", "is_active", "presence_span_days",
    "love_theme", "hate_theme", "switched_from", "verified", "reviewer_country", "company_segment_code",
    "categories", "product_context", "has_dollar_amount", "created", "sample_url",
    "serp_paid_appearances", "serp_organic_appearances", "score", "paid_results", "organic_results",
    "paid_advertisers", "organic_top", "ads_count", "se_results_count", "response_status",
    "observed_on", "retrieved_on", "published_at", "first_seen", "last_seen", "active_days",
    "bid", "match", "average_cpc", "monthly_clicks_at_bid", "monthly_cost_at_bid",
    "test_budget_usd", "est_clicks_within_test_budget", "simulated_keywords", "budget_covers_full_month",
    # Competitor set rows: tiering outcome and discovery provenance.
    "rank", "name", "competitor_tier", "icp_match", "jtbd_match", "decided_by", "source_count",
    "serp_paid_hits", "serp_organic_hits", "search_hits", "overlap_intersections", "listed_for",
    "retrieved", "candidates", "listicles", "spyfu_ppc_hits", "spyfu_common_keywords",
    # Competitor set rows: the offer-led profile, composition and ad check.
    "round", "query_kind", "provenance", "provenance_detail", "found_in", "brand_hits", "keyword_ads_hits",
    "listicle_pages", "relationship_hits", "offer_url", "offer_class", "offer_match", "price_text", "price_usd",
    "price_band", "duration", "buyer", "job", "operating", "marketplace", "evidence_urls", "comparable",
    "ad_activity", "ad_evidence", "selection_group", "selection", "override_reason", "reviewed", "reason_code",
    "profiled",
    # Channel footprint rows: library presence, tags, traffic split, partner signals, history, ranking.
    "channel", "label", "market_scope", "matched_ads", "active_ads", "oldest_days", "latest_seen", "formats",
    "present", "verified_by", "note", "fetch_status", "http_status", "via", "gtm_containers", "tags_detected",
    "channels_detected", "tools_reported", "paid_channel", "share_pct", "visits_monthly", "hits", "urls",
    "unavailable", "first_archived", "months_with_snapshots_24m", "window_months", "detail",
    "competitors_present", "competitors_total", "present_domains", "evidence_kinds", "active_ads_total",
    "max_oldest_days", "avg_share_pct", "why", "formats_recent", "tag_managers", "linkedin_company",
    "archived_host", "distinct_versions_24m", "months_archived_24m", "versions_capped",
    "target_country", "countries", "relevance", "relevance_reason", "current_presence", "native_duration_available",
    "duration_scope", "consideration_status", "needs_campaign_data", "observed_domains_by_role", "active_domains", "active_competitors", "days_since_last_delivery",
    "sampling", "stopped_ads", "unknown_ads", "policy_sha256",
    # Channel footprint SpyFu rows: modeled Google Ads spend per competitor.
    "country", "found", "months_checked", "months_with_spend", "spending_now", "latest_month",
    "latest_monthly_budget_usd", "latest_monthly_paid_clicks", "latest_paid_keywords",
    "avg_monthly_budget_usd", "max_monthly_budget_usd", "est_monthly_budget_usd",
    # Creative patterns rows, compact: patterns, labels and short excerpts, never full ad copy.
    "creative_id", "headline", "cta_intent", "landing_host", "format_kind", "running_at_capture",
    "longevity_status", "variants", "labels", "texts", "offer", "pattern_level", "pattern_key", "pattern_status",
    "convergence", "recurring", "competitors", "dated_competitors", "running_competitors", "creatives",
    "max_served_days", "examples", "creative_type", "format_detail", "message_family", "angles",
    "members", "source_members", "semantic_context_sha256", "category_dictionary_sha256", "language", "language_status", "language_allowed",
    # Funnel teardown rows: landing page facts, walked screens and funnel patterns (full page text never).
    "campaign_id", "campaign_ids", "funnel_id", "funnel_ids", "walk_id", "walk_ref", "walk_refs", "path_id", "role",
    "observation_status", "advertising_observation_status", "research_comparable", "research_comparable_campaign_ids", "running_refs", "dated_refs", "destination_refs", "observed_outcome", "partial", "unknown", "stop_reason", "features", "positions",
    "email_review", "email_events", "funnel_types", "creative_links", "dated_convergence", "observed_convergence", "selected_campaigns_total", "known_campaigns_total", "campaigns_with", "unknown_campaigns", "share",
    "cluster_id", "address", "host", "path", "origin", "discovered_as", "platforms", "running_creatives", "proven_creatives",
    "creative_ids", "weight", "final_host", "final_path", "redirected", "redirected_off_site", "page_type", "rendered_client_side",
    "headline_words", "meta_description", "primary_cta", "cta_labels", "forms", "form_fields", "asks_email", "asks_password",
    "asks_phone", "amounts_mentioned", "free_mentions", "trust_signals", "viewport_meta", "word_count", "message_match",
    "matched_terms", "walk_candidate", "walked_on", "viewport", "answers_used", "ends_in", "stopped_at", "screens", "screens_count",
    "question_screens", "proof_screens", "loader_screens", "contact_request_at", "result_at", "result_before_contact",
    "automatic_advance_share", "progress_indicator", "skip_control", "pattern", "walks_with", "walks_total",
    # Lifecycle capture rows: subscriptions and harvested sequences; the alias and message ids stay private.
    "entry_url", "entry_host", "subscribed_on", "confirmed", "unsubscribed_on", "harvested_on", "days_covered", "messages",
    "messages_per_week", "first_message_day", "first_welcome_day", "is_welcome", "last_message_day", "median_gap_days", "confirmations", "offers", "first_offer_day",
    "max_discount_percent", "deadlines", "nudges", "prices", "sender_domains", "unsubscribe_present", "subjects", "received_at",
    "day_offset", "hour_utc", "sender_domain", "subject", "is_confirmation", "is_offer", "discount_percent", "listing_truncated",
    "free_mention", "deadline", "unsubscribe_link", "links", "competitors_with",
})


def load_script(name: str):
    spec = importlib.util.spec_from_file_location("pmr_" + name.replace("-", "_"), Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Not a JSON object: {path.name}")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def catalog() -> dict[str, dict]:
    data = read_json(Path(__file__).parent.parent / "references/catalog.v1.json")
    return {s["id"]: s for s in data["sections"]}


def report_body(workspace: Path, heading: str) -> str:
    text = (workspace / _artifact_path("egbe-docs/research/market/full-report.md")).read_text()
    offsets = load_script("upsert-markdown-section")._h2_offsets(text)
    found = [(i, offset) for i, (name, offset) in enumerate(offsets) if name == heading]
    if len(found) != 1:
        raise ValueError("Missing or duplicate materialized report section")
    index, start = found[0]
    end = offsets[index + 1][1] if index + 1 < len(offsets) else len(text)
    return text[start:end].split("\n", 1)[1].strip()


def _publication(state: dict) -> None:
    if state.get("publication_mode") != "local":
        raise ValueError("Missing local publication proof; finish publication, not recollection")


def _bound_file(workspace: Path, state: dict, path: Path, name: str) -> Path:
    if state.get(name + "_path") != path.as_posix() or state.get(name + "_sha256") != sha(workspace / path):
        raise ValueError(f"{name} path/hash mismatch; rerun the owning workflow")
    return workspace / path


def _ai(workspace: Path, section: str, state: dict) -> tuple[str, dict]:
    root = workspace / RUNTIME / section
    if state.get("schema_version") != 3 or not state.get("job_id"):
        raise ValueError("Unsupported AI receipt")
    for field, filename in (("query", "query.md"), ("system_prompt", "system-prompt.md"), ("result", "result.md")):
        if state.get(field + "_sha256") != sha(root / filename):
            raise ValueError(f"AI {field} hash mismatch")
    if state.get("result_path") != (RUNTIME / section / "result.md").as_posix():
        raise ValueError("AI result path mismatch")
    review = read_json(root / "completion-review.json")
    if (review.get("schema_version") != 1 or review.get("section_id") != section
        or any(review.get(k) != state.get(k) for k in ("job_id", "query_sha256", "system_prompt_sha256", "result_sha256"))
        or review.get("classification") not in {"complete", "uncertain"}
        or type(review.get("retry_count")) is not int or review["retry_count"] not in (0, 1)
        or review.get("retry_exhausted") is not False):
        raise ValueError("AI completion review is missing or no longer matches")
    if state.get("input_provenance_sha256") != sha(root / "input-provenance.json"):
        raise ValueError("AI input provenance does not match its receipt")
    provenance = read_json(root / "input-provenance.json")
    load_script("research-artifact-io").verify_context(workspace, section, provenance.get("research_context"))
    if provenance.get("query_sha256") != state["query_sha256"]:
        raise ValueError("AI input provenance is stale; rerun explicitly if new research is authorized")
    for source, proof in provenance.get("measured_inputs", {}).items():
        if proof.get("evidence_sha256") and (source not in MEASURED or sha(workspace / EVIDENCE / MEASURED[source]) != proof["evidence_sha256"]):
            raise ValueError("Measured input changed since this AI result; review before explicitly rerunning")
        if proof.get("status") == "completed" and inspect_section(workspace, source)["status"] != "completed":
            raise ValueError("Measured input is no longer current/published; review before explicitly rerunning")
    publication = read_json(root / "publication.json")
    if publication.get("result_sha256") != state["result_sha256"]:
        raise ValueError("AI result has not been published")
    _publication(publication)
    body = (root / "result.md").read_text().strip()
    if not body or body.lower().startswith("unverified hypothesis:") or not re.search(r"https?://[^\s)>]+", body):
        raise ValueError("AI result is not a sourced completed section")
    return body, {"result_sha256": state["result_sha256"], "inputs": provenance}


def inspect_section(workspace: Path, section: str, *, require_materialized: bool = True) -> dict:
    """Absence is pending, not zero evidence. Invalid receipts never prove completion."""
    specs = catalog()
    if section not in specs:
        raise ValueError(f"Unknown research section: {section}")
    root = workspace / RUNTIME / section
    filename = "integration-receipt.json" if section == "organic_trend_watch" else "request.json"
    if not (root / filename).exists():
        return {"status": "pending", "reason": "No published receipt yet"}
    try:
        state = read_json(root / filename)
        if state.get("status") in {"pending", "running", "submitted", "processing", "awaiting_relevance", "awaiting_collection", "awaiting_finalize", "needs_approval", "needs_email", "budget_exhausted", "submission_outcome_unknown"}:
            return {"status": "pending", "reason": "Collection/publication still pending"}
        valid_statuses = {"completed", "partial", "no_data"} if section == "organic_trend_watch" else {"completed"}
        if state.get("status") not in valid_statuses or state.get("error") not in (None, ""):
            raise ValueError("Workflow failed, incomplete or not published")
        if section in MEASURED:
            if state.get("schema_version") != 1 or state.get("section_id") != section:
                raise ValueError("Wrong measured section receipt")
            load_script("research-artifact-io").verify_context(workspace, section, state.get("research_context"))
            _publication(state)
            path = EVIDENCE / MEASURED[section]
            data = read_json(_bound_file(workspace, state, path, "evidence"))
            accepted_versions = (1, 2) if section in ("channel_footprint", "creative_patterns", "funnel_teardown") else (2,) if section == "keyword_economics" else (1,)
            if data.get("section_id") != section or data.get("schema_version") not in accepted_versions:
                raise ValueError("Unsupported evidence version; refresh the bundle and rerun this section")
            if section == "competitor_set":
                _bound_file(workspace, state, RUNTIME / section / "inputs.json", "inputs")
                intake_name = state.get("intake_path")
                if intake_name:
                    intake_path = workspace / intake_name
                    if intake_path.is_file() and sha(intake_path) != state.get("intake_sha256"):
                        raise ValueError("Declared competitor intake changed; review prior evidence applicability")
            if section == "channel_footprint" and data.get("schema_version") == 2:
                inputs = data.get("inputs") or {}
                policy = inputs.get("effective_policy")
                policy_loader = load_script("research-policy")
                if not isinstance(policy, dict) or policy_loader.canonical_hash(policy) != inputs.get("policy_sha256"):
                    raise ValueError("Channel Footprint policy hash mismatch")
                if state.get("policy_sha256") != inputs.get("policy_sha256"):
                    raise ValueError("Channel Footprint receipt policy mismatch")
                intake_path = workspace / _artifact_path("egbe-docs/research/market/intake.json")
                intake_sha256 = sha(intake_path) if intake_path.is_file() else None
                if state.get("intake_sha256") != intake_sha256:
                    raise ValueError("Channel Footprint intake changed; collect/finalize the current countries and context")
                competitor_sha256 = state.get("competitor_set_sha256")
                if competitor_sha256 and competitor_sha256 != sha(workspace / EVIDENCE / MEASURED["competitor_set"]):
                    raise ValueError("Channel Footprint competitor decisions changed; refresh its context")
                context_sha256 = policy_loader.canonical_hash({
                    "context_sha256": state["research_context"]["sha256"], "intake_sha256": intake_sha256,
                    "competitor_context": inputs.get("competitor_context") or {},
                    "product_domain": inputs.get("product_domain") or "", "target_countries": inputs.get("target_countries") or [],
                })
                if state.get("input_context_sha256") != context_sha256 or inputs.get("product_context_sha256") != context_sha256:
                    raise ValueError("Channel Footprint input context hash mismatch")
            if section == "creative_patterns" and (data.get("inputs") or {}).get("collection_mode") == "channel_footprint_reuse":
                footprint_path = workspace / EVIDENCE / MEASURED["channel_footprint"]
                if state.get("channel_footprint_sha256") != sha(footprint_path):
                    raise ValueError("Creative Patterns source footprint changed; rerun with current relevance and market scope")
                footprint = inspect_section(workspace, "channel_footprint")
                if footprint["status"] != "completed":
                    raise ValueError("Creative Patterns source footprint is pending, stale or unverified")
                policy_loader = load_script("research-policy")
                if (data["inputs"].get("footprint_document_sha256") != policy_loader.canonical_hash(footprint["data"])
                        or data["inputs"].get("policy_sha256") != footprint["data"]["inputs"].get("policy_sha256")
                        or state.get("policy_sha256") != data["inputs"].get("policy_sha256")):
                    raise ValueError("Creative Patterns footprint/policy snapshot mismatch")
            if section == "creative_patterns" and data.get("schema_version") == 2:
                inputs = data.get("inputs") or {}
                policy_loader = load_script("research-policy")
                policy = inputs.get("effective_policy")
                if not isinstance(policy, dict) or policy_loader.canonical_hash(policy) != inputs.get("policy_sha256") or state.get("policy_sha256") != inputs.get("policy_sha256"):
                    raise ValueError("Creative Patterns policy/receipt hash mismatch")
                intake = workspace / _artifact_path("egbe-docs/research/market/intake.json")
                if state.get("intake_sha256") != (sha(intake) if intake.is_file() else None):
                    raise ValueError("Creative Patterns intake changed; rebuild dependent labels and coverage")
                taxonomy = Path(__file__).resolve().parent.parent / "references/config/creative-taxonomy.v1.json"
                if inputs.get("taxonomy_sha256") != sha(taxonomy):
                    raise ValueError("Creative Patterns taxonomy changed; refresh derived evidence")
                dictionary = data.get("angle_dictionary") or {}
                dictionary_body = {k: v for k, v in dictionary.items() if k != "dictionary_sha256"}
                if dictionary.get("context_sha256") != inputs.get("semantic_context_sha256") or policy_loader.canonical_hash(dictionary_body) != dictionary.get("dictionary_sha256"):
                    raise ValueError("Creative Patterns semantic dictionary hash mismatch")
                if inputs.get("creative_selection_path"):
                    selection = load_script("creative-selection").read_selection(workspace, data)
                    if state.get("creative_selection_sha256") != inputs.get("creative_selection_sha256") or selection != data.get("selection"):
                        raise ValueError("Creative Patterns selected creative manifest/receipt mismatch")
                if inputs.get("footprint_document_sha256") and inputs.get("collection_mode") != "channel_footprint_reuse":
                    footprint = read_json(workspace / EVIDENCE / MEASURED["channel_footprint"])
                    if policy_loader.canonical_hash(footprint) != inputs["footprint_document_sha256"] or inspect_section(workspace, "channel_footprint")["status"] != "completed":
                        raise ValueError("Creative Patterns Channel Footprint input changed or is no longer completed")
            if section == "funnel_teardown" and data.get("schema_version") == 2:
                load_script("research_integrity").validate_funnel_receipt(workspace, data, state)
                for source in ("channel_footprint", "creative_patterns"):
                    if inspect_section(workspace, source)["status"] != "completed":
                        raise ValueError("Funnel upstream " + source + " is pending, stale or unverified")
            if section == "lifecycle_capture":
                load_script("research_integrity").validate_lifecycle_inputs(workspace, state)
            if not isinstance(data.get("rows"), list) or any(not isinstance(row, dict) for row in data["rows"]):
                raise ValueError("Evidence rows must be an array (empty is permitted)")
            if section == "keyword_economics":
                if not isinstance(data.get("locales"), list) or not data["locales"] or any(not isinstance(x, dict) or x.get("status") != "completed" for x in data["locales"]):
                    raise ValueError("Not every requested keyword locale completed")
                for locale in data["locales"]:
                    key = locale["key"]
                    if not re.fullmatch(r"[0-9]+-[a-z]{2,3}(?:-[a-z]{2})?", key):
                        raise ValueError("Invalid locale key")
                    canonical = EVIDENCE / "keyword-economics" / f"{key}.json"
                    if locale.get("evidence_path") != canonical.as_posix() or sha(workspace / canonical) != locale.get("evidence_sha256"):
                        raise ValueError("Locale evidence hash mismatch")
                    attempt = read_json(root / "locales" / key / "request.json")
                    if attempt.get("status") != "completed" or attempt.get("research_context") != state["research_context"]:
                        raise ValueError("Locale refresh pending/failed/stale")
            result = _bound_file(workspace, state, RUNTIME / section / "result.md", "result")
            body = result.read_text().strip()
        elif section == "organic_trend_watch":
            if state.get("schema_version") != 1 or state.get("section_id") != section:
                raise ValueError("Wrong Organic Trend integration receipt")
            if state.get("context_sha256") != sha(root / "context.json"):
                raise ValueError("Organic Trend input context changed")
            source = read_json(root / "context.json").get("sources", {}).get("context")
            if source:
                source_path = workspace / source["path"]
                if source_path.is_file() and sha(source_path) != source["source_sha256"]:
                    raise ValueError("Declared Organic context changed; review prior evidence applicability")
            _publication(state)
            for field, filename in (("skill_receipt", "receipt.json"), ("result", "result.md")):
                ref = state[field]
                if ref.get("path") != filename or ref.get("sha256") != sha(root / filename):
                    raise ValueError("Organic Trend integration hash mismatch")
            skill_receipt = read_json(root / "receipt.json")
            expected_coverage = {"completed": "complete", "partial": "partial", "no_data": "no_data"}
            coverage = state.get("coverage")
            if (not isinstance(coverage, dict)
                or coverage.get("status") != expected_coverage[state["status"]]
                or skill_receipt.get("status") != state["status"]
                or skill_receipt.get("coverage") != coverage):
                raise ValueError("Organic Trend coverage differs from its sealed receipt")
            body = (root / "result.md").read_text().strip()
            if hashlib.sha256(body.encode()).hexdigest() != state["report_section_sha256"]:
                raise ValueError("Organic Trend section hash mismatch")
            data = {"result_sha256": state["result"]["sha256"], "coverage": coverage}
        elif section == "geography_comparison":
            body, data = load_script("geography-comparison").inspect(workspace, state)
        else:
            body, data = _ai(workspace, section, state)
        if require_materialized and report_body(workspace, specs[section]["heading"]) != body:
            raise ValueError("Report section differs from its published result")
        status = state["status"] if section == "organic_trend_watch" else "completed"
        outcome = {"status": status, "data": data, "body": body, "receipt_sha256": sha(root / ("integration-receipt.json" if section == "organic_trend_watch" else filename))}
        if status != "completed":
            outcome["reason"] = "Organic research coverage is " + status + "; see source gaps"
        return outcome
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"status": "could_not_complete", "reason": str(exc)}


def fair_rows(rows: list[dict], limit: int) -> list[dict]:
    """Round-robin per locale/type, including exclusions and contrary observations."""
    groups = defaultdict(list)
    for position, row in enumerate(rows):
        groups[(row.get("locale_key", ""), row.get("type", ""))].append((position, row))
    selected = []
    while groups and len(selected) < limit:
        for key in sorted(list(groups)):
            position, row = groups[key].pop(0)
            selected.append({**row, "evidence_row": position})
            if not groups[key]:
                del groups[key]
            if len(selected) == limit:
                break
    return selected


def keyword_inputs(workspace: Path, *, consumer: str, row_type: str, field: str, cap: int, exclude=frozenset()) -> list[str]:
    """Keyword Economics rows as optional inputs. `exclude` (domains the
    completed Competitor Set rejected) is applied BEFORE the cap so a
    rejected domain neither fills a slot nor appears in the provenance as
    an input; the exclusions themselves are recorded there."""
    outcome = inspect_section(workspace, "keyword_economics")
    provenance_path = workspace / RUNTIME / consumer / "keyword-inputs.json"
    io = load_script("research-artifact-io")
    if outcome["status"] != "completed":
        # This source only supplements explicit inputs; invalid data must not
        # be reused or turn an independent workflow into a failed dependency.
        io.write_json(provenance_path, {"schema_version": 1, "status": outcome["status"],
                                      "reason": outcome["reason"], "source_sha256": None, "inputs": []})
        print("Optional Keyword Economics inputs not used: " + outcome["reason"], file=sys.stderr)
        return []
    rows = [r for r in outcome["data"]["rows"] if r.get("type") == row_type and r.get(field)]
    if row_type == "keyword":
        rows = [r for r in rows if not r.get("free_edu_intent") and type(r.get("search_volume")) is int]
    else:
        rows = [r for r in rows if r.get("kind") == "candidate"]
    excluded = {_normalized_domain(x) for x in exclude}
    rejected = sorted({r[field] for r in rows if _normalized_domain(r[field]) in excluded}) if excluded else []
    rows = [r for r in rows if _normalized_domain(r[field]) not in excluded]
    metric = "search_volume" if row_type == "keyword" else "score"
    rows.sort(key=lambda r: (-(r.get(metric) or 0), r[field]))
    ordered = fair_rows(rows, len(rows))
    chosen = list(dict.fromkeys(r[field] for r in ordered))[:cap]
    provenance = {"schema_version": 1, "status": "completed",
                  "source_sha256": sha(workspace / EVIDENCE / MEASURED["keyword_economics"]),
                  "inputs": [{field: r[field], "locale_key": r["locale_key"], metric: r.get(metric)}
                             for r in rows if r[field] in chosen],
                  "excluded_by_competitor_set": rejected}
    io.write_json(provenance_path, provenance)
    return chosen


def _normalized_domain(value) -> str:
    """Host-only, lowercase, without scheme, path, port, trailing dot or www."""
    text = str(value or "").strip().lower()
    if "//" in text:
        text = text.split("//", 1)[1]
    host = text.split("/", 1)[0].split("?", 1)[0].split("@")[-1].split(":", 1)[0].rstrip(".")
    return host.removeprefix("www.")


def competitor_set_inputs(workspace: Path, *, consumer: str, cap: int) -> list[str]:
    """Competitor domains of the completed Competitor Set, in rank order.

    Like keyword inputs, this source only supplements explicit inputs:
    pending, failed or invalid evidence is omitted with the reason recorded
    in the consumer's `competitor-set-inputs.json`."""
    outcome = inspect_section(workspace, "competitor_set")
    provenance_path = workspace / RUNTIME / consumer / "competitor-set-inputs.json"
    io = load_script("research-artifact-io")
    if outcome["status"] != "completed":
        io.write_json(provenance_path, {"schema_version": 1, "status": outcome["status"],
                                      "reason": outcome["reason"], "source_sha256": None, "inputs": []})
        print("Optional Competitor Set inputs not used: " + outcome["reason"], file=sys.stderr)
        return []
    rows = [r for r in outcome["data"]["rows"] if r.get("type") == "competitor" and r.get("domain")]
    rows.sort(key=lambda r: (r["rank"] if type(r.get("rank")) is int else 10 ** 6, r["domain"]))
    chosen = list(dict.fromkeys(r["domain"] for r in rows))[:cap]
    provenance = {"schema_version": 1, "status": "completed",
                  "source_sha256": sha(workspace / EVIDENCE / MEASURED["competitor_set"]),
                  "inputs": [{"domain": r["domain"], "rank": r.get("rank"), "competitor_tier": r.get("competitor_tier")}
                             for r in rows if r["domain"] in chosen]}
    io.write_json(provenance_path, provenance)
    return chosen


def competitor_set_excluded_domains(workspace: Path) -> set[str]:
    """Domains the completed Competitor Set rejected: agent exclusions,
    directories, below-threshold candidates. Automatic fallbacks (Keyword
    Economics) must not pull them back in; explicit founder inputs may.
    Over-cap competitors are not exclusions. Empty when the section is not
    completed."""
    outcome = inspect_section(workspace, "competitor_set")
    if outcome["status"] != "completed":
        return set()
    return {
        _normalized_domain(r["domain"]) for r in outcome["data"]["rows"]
        if r.get("type") == "excluded_candidate" and r.get("domain") and r.get("decided_by") != "cap"
    }


def _bounded(value):
    if isinstance(value, str):
        return value[:600] + ("…[truncated]" if len(value) > 600 else "")
    if isinstance(value, list):
        return [_bounded(x) for x in value[:12]]
    if isinstance(value, dict):
        return {k: _bounded(v) for k, v in list(value.items())[:20]}
    return value


def measured_context(workspace: Path, section: str) -> tuple[tuple, dict]:
    context_path = workspace / RUNTIME / "preview-context.json"
    selection = read_json(context_path) if context_path.exists() else None
    outcomes = {s["id"]: s["status"] for s in selection["sections"]} if selection else {}
    projections, manifest = [], {}
    for source in INPUTS.get(section, ()):
        selected_status = outcomes.get(source)
        outcome = {"status": "not_selected"} if selected_status == "not_selected" else inspect_section(workspace, source)
        if selected_status == "could_not_complete":
            outcome = {"status": "could_not_complete", "reason": "Caller closed this selected section without completion"}
        elif (outcome["status"] == "pending" and selection and selected_status is not None
              and selection["selection_id"].startswith("local:")):
            raise ValueError(f"Selected supporting research {source} is pending; finish or explicitly skip it before {section}")
        elif outcome["status"] == "pending" and not selection:
            outcome = {"status": "unknown", "reason": "No selection scope or completed receipt; no conclusion about demand"}
        projected = {"section": source, "status": outcome["status"], "reason": outcome.get("reason")}
        if outcome["status"] == "completed":
            data = outcome["data"]
            rows = data["rows"]
            chosen = fair_rows(rows, 40)
            projected.update({"source_path": (EVIDENCE / MEASURED[source]).as_posix(),
                              "evidence_sha256": sha(workspace / EVIDENCE / MEASURED[source]),
                              "receipt_sha256": outcome["receipt_sha256"],
                              "retrieved_on": data.get("retrieved_on"),
                              "locales": [{k: x.get(k) for k in ("key", "status", "locale", "retrieved_on", "evidence_sha256")}
                                          for x in data.get("locales", [])],
                              "rows": [{k: _bounded(v) for k, v in r.items() if k in PUBLIC_FIELDS or k == "evidence_row"} for r in chosen],
                              "rows_total": len(rows), "rows_omitted": len(rows) - len(chosen),
                              "field_limits": {"text_characters": 600, "list_items": 12},
                              "forecast_coverage": [{"locale_key": x["key"], **{k: x.get("simulation", {}).get(k) for k in
                                                      ("kind", "requested_count", "submitted_count", "match", "bid", "forecast_period",
                                                       "response_status", "response_rows", "rationale", "source", "limitations")}}
                                                     for x in data.get("locales", [])],
                              "limitations": "Bounded observations, not TAM or proof of willingness to pay. "
                                              "CPC is auction cost, not product pricing. Missing/null is not zero. "
                                              "Geographies and alternative budget scenarios must not be summed."})
            while len(json.dumps(projected, ensure_ascii=False)) > 16000 and projected["rows"]:
                projected["rows"].pop()
                projected["rows_omitted"] += 1
        content = json.dumps(projected, sort_keys=True, ensure_ascii=False)
        projections.append((f"Measured {source} (untrusted observations)", content))
        manifest[source] = {"status": projected["status"], "projection_sha256": hashlib.sha256(content.encode()).hexdigest(),
                            "evidence_sha256": projected.get("evidence_sha256")}
    return tuple(projections), manifest
