"""Grounded, category-specific meaning alongside the generic creative taxonomy.

The classifier proposes meanings; this module preserves evidence, allocates
stable dictionary IDs, and never infers meaning by matching headline strings.
It is intentionally independent of a product category and an LLM provider.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SEMANTIC_CONTRACT = "creative-semantics.v1"
ANGLE_AXES = ("buyer_context", "job", "mechanism", "outcome", "proof", "price_terms", "action")
_LANGUAGE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")
_SPACE = re.compile(r"\s+")


def _normalized(value: str) -> str:
    return _SPACE.sub(" ", value).strip().casefold()


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _source_records(creative: dict[str, Any]) -> list[dict]:
    sources = []
    for field in ("headline", "body", "cta_label", "transcript"):
        value = creative.get(field)
        if isinstance(value, str) and value.strip():
            sources.append({"text": value, "excerpt_source": "transcript" if field == "transcript" else "native_ad_copy", "frame_refs": []})
    origins = creative.get("extra_text_sources") or []
    for index, value in enumerate(creative.get("extra_texts") or []):
        origin = origins[index] if index < len(origins) and isinstance(origins[index], dict) else {}
        kind = origin.get("kind", "ad_text")
        source = "frame_extraction" if kind == "video_frame_ocr" else "video_metadata" if kind.startswith("video_metadata_") else "native_ad_copy"
        if isinstance(value, str) and value.strip():
            sources.append({"text": value, "excerpt_source": source,
                            "frame_refs": [origin["ref"]] if source == "frame_extraction" and origin.get("ref") else []})
    metadata = creative.get("video_metadata") or {}
    if isinstance(metadata, dict):
        for key in ("title", "description"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                sources.append({"text": value, "excerpt_source": "video_metadata", "frame_refs": []})
    analysis = creative.get("media_analysis") or creative.get("video_analysis") or {}
    if isinstance(analysis, dict):
        analysis = analysis.get("analysis") or analysis
        for frame in analysis.get("frames") or []:
            if isinstance(frame, dict):
                for value in frame.get("visible_text") or []:
                    if isinstance(value, str) and value.strip():
                        ref = frame.get("ref") or frame.get("frame_ref")
                        sources.append({"text": value, "excerpt_source": "frame_extraction", "frame_refs": [ref] if ref else []})
    # A classifier may preserve a headline and body as adjacent lines. Their
    # combined native span remains independently bound to these source fields.
    grouped = []
    for source in sources:
        if grouped and all(grouped[-1][key] == source[key] for key in ("excerpt_source", "frame_refs")):
            grouped[-1]["text"] += "\n" + source["text"]
        else:
            grouped.append(dict(source))
    return [*sources, *grouped]


def _excerpt_record(raw: Any, sources: list[dict], *, promises: bool = False) -> dict | None:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 1200:
        return None
    value = _SPACE.sub(" ", raw).strip()
    for source in sources:
        if promises and source["excerpt_source"] == "video_metadata":
            continue
        if _normalized(value) in _normalized(source["text"]):
            return {"excerpt": value, "excerpt_source": source["excerpt_source"], "frame_refs": source["frame_refs"]}
    return None


def build_semantic_context(product_context: str, languages: list[str], known_dictionary: dict | None = None) -> dict:
    """Full offer context and explicit accepted languages; no country defaults.

    Prior frozen definitions are anchors for canonical meanings across batches.
    Their support records stay in the dictionary and are not repeated in prompts.
    Changes to the offer, languages or anchors invalidate semantic label caches.
    """
    if not isinstance(product_context, str) or len(product_context) > 24000:
        raise ValueError("product_context must be a string of at most 24000 characters")
    allowed = sorted(set(str(language).strip().casefold() for language in languages))
    if len(allowed) > 40 or any(not _LANGUAGE.fullmatch(language) for language in allowed):
        raise ValueError("accepted languages must be explicit ISO/BCP-47 language codes")
    dictionary = known_dictionary or {}
    if dictionary and dictionary.get("semantic_contract") != SEMANTIC_CONTRACT:
        raise ValueError("known dictionary has a different semantic contract")
    angles = [{k: angle[k] for k in ("axis", "key", "label")}
              for angle in dictionary.get("angles", []) if isinstance(angle, dict)
              and angle.get("axis") in ANGLE_AXES and all(isinstance(angle.get(k), str) for k in ("key", "label"))]
    families = [{k: family[k] for k in ("key", "label", "meaning")}
                for family in dictionary.get("message_families", []) if isinstance(family, dict)
                and all(isinstance(family.get(k), str) for k in ("key", "label", "meaning"))]
    # Exceeding a prompt budget is visible; definitions are never silently lost.
    if len(angles) > 320 or len(families) > 320:
        raise ValueError("known semantic dictionary exceeds 320 angles or message families")
    context = {"semantic_contract": SEMANTIC_CONTRACT, "product_context": product_context,
               "allowed_languages": allowed, "axes": list(ANGLE_AXES),
               "known_angles": sorted(angles, key=lambda a: (a["axis"], a["key"])),
               "known_message_families": sorted(families, key=lambda f: f["key"])}
    context["context_sha256"] = _hash(context)
    return context


def _valid_excerpt(raw: Any, sources: list[str]) -> str | None:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 1200:
        return None
    excerpt = _SPACE.sub(" ", raw).strip()
    return excerpt if any(_normalized(excerpt) in _normalized(source) for source in sources) else None


def _safe_label(raw: Any, maximum: int = 240) -> str | None:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > maximum:
        return None
    return _SPACE.sub(" ", raw).strip()


def language_matches(detected: str, allowedcodes: list[str]) -> bool:
    """A bare language and its regional form match in either direction.

    Two explicitly different regions remain distinct restrictions. Inputs are
    normalized here so every consumer applies the same case-insensitive rule.
    """
    if not isinstance(detected, str):
        return False
    detected = detected.strip().casefold()
    if not _LANGUAGE.fullmatch(detected):
        return False
    for allowed in allowedcodes:
        if not isinstance(allowed, str):
            continue
        allowed = allowed.strip().casefold()
        if not _LANGUAGE.fullmatch(allowed):
            continue
        if detected == allowed or (detected.split("-", 1)[0] == allowed.split("-", 1)[0]
                                   and ("-" not in detected or "-" not in allowed)):
            return True
    return False


def apply_semantics(creatives: list[dict], classifications: list[dict], semantic_context: dict) -> dict:
    """Attach evidence-backed meaning to both row types, return a frozen dictionary.

    Footprint relevance is retained when the new classifier has no grounded
    decision. Explicit grounded disagreement is recorded rather than erased.
    Missing semantic output leaves unknown states and cannot create patterns.
    Dictionary members are ad IDs; several images/ads never become one creative.
    """
    if semantic_context.get("semantic_contract") != SEMANTIC_CONTRACT:
        raise ValueError("unsupported semantic context")
    by_id = {creative["creative_id"]: creative for creative in creatives}
    angles: dict[tuple[str, str], dict] = {}
    families: dict[str, dict] = {}
    allowed_languages = semantic_context.get("allowed_languages") or []
    for classification in classifications:
        creative = by_id.get(classification.get("creative_id"))
        if creative is None:
            continue
        cid = creative["creative_id"]
        semantics = classification.get("semantics") or {}
        if not isinstance(semantics, dict):
            semantics = {}
        source_records = _source_records(creative)
        observed = classification.get("observed_text")
        extraction = classification.get("observed_text_source")
        has_visual = bool(classification.get("with_image") or classification.get("with_video_frames"))
        derived = _normalized(str(creative.get("video_observations") or ""))
        observed_sources = []
        proposed_sources = classification.get("observed_text_sources")
        if isinstance(proposed_sources, list) and proposed_sources:
            candidates = proposed_sources
        else:
            candidates = [{"text": line, "excerpt_source": "frame_extraction" if extraction in ("frame_extraction", "mixed") else "native_ad_copy",
                           "frame_refs": classification.get("observed_text_frame_refs") or []}
                          for line in observed.splitlines() if line.strip()] if isinstance(observed, str) else []
        for candidate in candidates:
            if not isinstance(candidate, dict) or not isinstance(candidate.get("text"), str):
                continue
            value = candidate["text"]
            # Full OCR lines can exceed excerpt limits; native containment is
            # still checked against an independent input source.
            native_source = next((source for source in source_records
                                  if _normalized(value) in _normalized(source["text"])), None)
            if native_source is not None:
                attributed = {"text": value, "excerpt_source": native_source["excerpt_source"], "frame_refs": native_source["frame_refs"]}
            elif has_visual and candidate.get("excerpt_source") == "frame_extraction" and value.strip() and _normalized(value) not in derived:
                refs = candidate.get("frame_refs") or []
                refs = refs if isinstance(refs, list) else []
                attributed = {"text": value, "excerpt_source": "frame_extraction", "frame_refs": [ref for ref in refs if isinstance(ref, str)]}
            else:
                continue
            observed_sources.append(attributed)
            source_records.append(attributed)
        if observed_sources:
            grouped_sources = []
            for source in observed_sources:
                if grouped_sources and all(grouped_sources[-1][key] == source[key] for key in ("excerpt_source", "frame_refs")):
                    grouped_sources[-1]["text"] += "\n" + source["text"]
                else:
                    grouped_sources.append(dict(source))
            observed_sources = grouped_sources
            source_records.extend(observed_sources)
            creative["observed_text"] = "\n".join(source["text"] for source in observed_sources)
            creative["observed_text_source"] = extraction or "native_text"
            creative["observed_text_sources"] = observed_sources
            creative["observed_text_frame_refs"] = sorted({ref for source in observed_sources for ref in source["frame_refs"]})
            classification["observed_text_sources"] = observed_sources
        # Taxonomy excerpts can consume literal evidence, never create it.
        # Their modality is retained even when the model extracts text from an image.
        text_origins = {}
        for field, value in (classification.get("texts") or {}).items():
            support = _excerpt_record(value, source_records, promises=True)
            if support:
                text_origins[field] = {key: support[key] for key in ("excerpt_source", "frame_refs")}
        classification["texts_sources"] = text_origins
        sources = [source["text"] for source in source_records]
        for field in ("relevance", "language", "message_family"):
            value = semantics.get(field)
            if isinstance(value, dict):
                support = _excerpt_record(value.get("excerpt"), source_records)
                if support:
                    value.update(support)
        for value in semantics.get("angles") or []:
            if isinstance(value, dict):
                support = _excerpt_record(value.get("excerpt"), source_records)
                if support:
                    value.update(support)
        # Old receipts without provenance receive the same validation. Metadata
        # and derived descriptions never become literal advertised promises.
        promises = []
        for value in semantics.get("promises") or []:
            if isinstance(value, dict):
                support = _excerpt_record(value.get("excerpt"), source_records, promises=True)
                if support:
                    promises.append({**value, **support})
        if "promises" in semantics:
            semantics["promises"] = promises
        relevance = semantics.get("relevance") or {}
        status = relevance.get("status") if isinstance(relevance, dict) else None
        excerpt = _valid_excerpt(relevance.get("excerpt"), sources) if isinstance(relevance, dict) else None
        reason = _safe_label(relevance.get("reason"), 1200) if isinstance(relevance, dict) else None
        prior = creative.get("relevance")
        if isinstance(prior, dict):
            prior = prior.get("status")
        if status in ("relevant", "irrelevant") and excerpt and reason:
            if prior in ("relevant", "irrelevant") and prior != status:
                creative["relevance_conflict"] = {"footprint": prior, "creative_analysis": status,
                                                   "excerpt": excerpt, "reason": reason}
            creative.update(relevance=status, relevance_reason=reason, relevance_excerpt=excerpt,
                            relevance_source=SEMANTIC_CONTRACT,
                            relevance_excerpt_source=relevance.get("excerpt_source"),
                            relevance_frame_refs=relevance.get("frame_refs") or [])
        elif prior not in ("relevant", "irrelevant"):
            creative.update(relevance="unknown", relevance_reason=reason or "No grounded comparable-offer decision.")
        language = semantics.get("language") or {}
        code = _safe_label(language.get("code"), 40) if isinstance(language, dict) else None
        language_excerpt = _valid_excerpt(language.get("excerpt"), sources) if isinstance(language, dict) else None
        code = code.casefold() if code else None
        ad_languages = creative.get("allowed_languages")
        ad_languages = ad_languages if isinstance(ad_languages, list) else allowed_languages
        if code and _LANGUAGE.fullmatch(code) and language_excerpt:
            creative.update(language=code, language_excerpt=language_excerpt,
                            language_excerpt_source=language.get("excerpt_source"),
                            language_frame_refs=language.get("frame_refs") or [],
                            language_status=("allowed" if language_matches(code, ad_languages) else "excluded")
                            if ad_languages else "unknown")
        elif creative.get("language") and creative.get("language_status") in ("allowed", "excluded"):
            # Keep the observed language, but apply the current market policy.
            prior_code = str(creative["language"]).casefold()
            creative["language_status"] = ("allowed" if language_matches(prior_code, ad_languages) else "excluded") if ad_languages else "unknown"
        else:
            creative.update(language=None, language_status="unknown")
        creative["language_allowed"] = creative.get("language_status") == "allowed"
        meaning_allowed = creative.get("relevance") == "relevant" and creative["language_allowed"]
        angle_ids = []
        for angle in (semantics.get("angles") or []) if meaning_allowed else []:
            if not isinstance(angle, dict) or angle.get("axis") not in ANGLE_AXES:
                continue
            key, label = _safe_label(angle.get("key")), _safe_label(angle.get("label"), 160)
            excerpt = _valid_excerpt(angle.get("excerpt"), sources)
            if not key or not label or not excerpt:
                continue
            identity = (angle["axis"], _normalized(key))
            aid = "angle:" + _hash(identity)[:20]
            definition = angles.setdefault(identity, {"angle_id": aid, "axis": angle["axis"], "key": identity[1],
                                                       "label": label, "members": [], "support": []})
            # Label variation does not affect identity. Pick deterministically.
            definition["label"] = min(definition["label"], label)
            if cid not in definition["members"]:
                definition["members"].append(cid)
            support = {"creative_id": cid, "excerpt": excerpt, "country": creative.get("country"),
                       "relevance": creative.get("relevance"), "language_status": creative.get("language_status"),
                       **(_excerpt_record(excerpt, source_records) or {})}
            if support not in definition["support"]:
                definition["support"].append(support)
            if aid not in angle_ids:
                angle_ids.append(aid)
        family = (semantics.get("message_family") or {}) if meaning_allowed else {}
        family_id = None
        if isinstance(family, dict):
            key = _safe_label(family.get("key"), 320)
            label = _safe_label(family.get("label"), 160)
            meaning = _safe_label(family.get("meaning"), 1200)
            excerpt = _valid_excerpt(family.get("excerpt"), sources)
            # A generic taxonomy label is not a selling-message family. The
            # canonical key describes a proposition, not a verbatim headline.
            weak = key and _normalized(key).replace(" ", "_") in {
                "unknown", "none", "other", "desired_outcome", "identity_callout", "value_framing",
                "social_proof", "professional", "job_seeker", "direct_offer", "pain_problem"}
            if key and label and meaning and excerpt and not weak:
                identity = _normalized(key)
                family_id = "family:" + _hash(identity)[:20]
                definition = families.setdefault(identity, {"message_family_id": family_id, "key": identity,
                                                             "label": label, "meaning": meaning, "members": [], "support": []})
                definition["label"] = min(definition["label"], label)
                definition["meaning"] = min(definition["meaning"], meaning)
                if cid not in definition["members"]:
                    definition["members"].append(cid)
                support = {"creative_id": cid, "excerpt": excerpt, "country": creative.get("country"),
                           "relevance": creative.get("relevance"), "language_status": creative.get("language_status"),
                           **(_excerpt_record(excerpt, source_records) or {})}
                if support not in definition["support"]:
                    definition["support"].append(support)
        for row in (creative, classification):
            row.update(semantic_contract=SEMANTIC_CONTRACT, semantic_context_sha256=semantic_context.get("context_sha256"),
                       category_angle_ids=sorted(angle_ids), message_family_id=family_id,
                       message_family_status="classified" if family_id else "unknown")
        for field in ("relevance", "relevance_reason", "relevance_excerpt", "relevance_source", "relevance_conflict",
                      "relevance_excerpt_source", "relevance_frame_refs", "language", "language_status", "language_allowed", "language_excerpt",
                      "language_excerpt_source", "language_frame_refs", "observed_text", "observed_text_source",
                      "observed_text_sources", "observed_text_frame_refs"):
            if field in creative:
                classification[field] = creative[field]
    classified_ids = {row.get("creative_id") for row in classifications}
    for creative in creatives:
        if creative["creative_id"] not in classified_ids:
            # A failed enriched classification cannot keep memberships learned
            # from an earlier preview pass. Its grounded preflight relevance,
            # language and source observations remain usable independently.
            creative.update(semantic_contract=SEMANTIC_CONTRACT,
                            semantic_context_sha256=semantic_context.get("context_sha256"),
                            category_angle_ids=[], message_family_id=None,
                            message_family_status="unknown")
    for definitions in (angles.values(), families.values()):
        for definition in definitions:
            definition["members"].sort()
            definition["support"].sort(key=lambda x: (x["creative_id"], x["excerpt"]))
    dictionary = {"schema_version": 1, "semantic_contract": SEMANTIC_CONTRACT,
                  "context_sha256": semantic_context.get("context_sha256"),
                  "coverage_basis": "classified observations within the collected sample",
                  "unclassified_creative_ids": sorted(set(by_id) - classified_ids),
                  "angles": sorted(angles.values(), key=lambda x: x["angle_id"]),
                  "message_families": sorted(families.values(), key=lambda x: x["message_family_id"])}
    dictionary["dictionary_sha256"] = _hash(dictionary)
    for row in [*creatives, *classifications]:
        if row.get("semantic_contract") == SEMANTIC_CONTRACT:
            row["category_dictionary_sha256"] = dictionary["dictionary_sha256"]
    return dictionary
