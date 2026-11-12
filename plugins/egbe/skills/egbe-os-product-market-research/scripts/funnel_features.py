"""Portable browser-observation projection shared by producers and consumers.

Ship byte-identical copies inside each skill. Missing optional observations
remain unknown even on a complete path; explicit absence is a different fact.
No network, repository imports or independent proof policy are used here.
"""
from __future__ import annotations


class FunnelFeaturesError(ValueError):
    pass


def observation_features(walk: dict) -> dict:
    screens = [s for s in walk.get("screens", []) if s.get("branch_role") == "main"]
    if not screens:
        raise FunnelFeaturesError("funnel proof needs at least one observed main-path screen")
    partial = walk.get("partial")
    if type(partial) is not bool:
        raise FunnelFeaturesError("funnel path must explicitly declare partial")
    kinds = [str(s.get("kind", "")).split(":", 1)[0] for s in screens]
    positions = {
        "contact_at": next((i + 1 for i, k in enumerate(kinds) if k == "contact request"), None),
        "teaser_at": next((i + 1 for i, s in enumerate(screens) if s.get("result_type") == "teaser"), None),
        "result_at": next((i + 1 for i, s in enumerate(screens) if s.get("result_type") == "final"), None),
        "price_at": next((i + 1 for i, s in enumerate(screens) if any(a.get("kind") == "price" for a in s.get("amounts", []))), None),
        "offer_at": next((i + 1 for i, s in enumerate(screens) if s.get("offer")), None),
    }
    result, contact = positions["result_at"], positions["contact_at"]
    relation = result < contact if result is not None and contact is not None else None
    present = lambda condition: True if condition else None if partial else False
    types = {"quiz": "question" in kinds,
             "landing_with_form": "landing" in kinds and "contact request" in kinds,
             "webinar_registration": any(s.get("conversion_kind") == "webinar_registration" for s in screens),
             "trial": any(s.get("conversion_kind") == "trial" for s in screens),
             "call_booking": "booking" in kinds, "checkout": "payment gate" in kinds}
    proof_seen = any(s.get("proof") or kind == "proof" for s, kind in zip(screens, kinds))
    progress_seen = any(s.get("progress_indicator") is True for s in screens)
    features = {
        "question_flow": present("question" in kinds),
        "proof_blocks": True if proof_seen else False if not partial and all("proof" in s for s in screens) else None,
        "progress_indicator": True if progress_seen else False if not partial and all("progress_indicator" in s for s in screens) else None,
        "result_before_contact": relation,
        "contact_before_result": not relation if relation is not None else None,
        "short_flow": len(screens) <= 5 if not partial else None,
        "long_flow": len(screens) >= 10 if not partial else None,
        "automatic_advance": sum(s.get("advance") == "automatic" for s in screens) / len(screens) >= .5 if not partial else None,
    }
    features.update({"type:" + name: present(value) for name, value in types.items()})
    return {"positions": positions, "features": features, "funnel_types": [name for name, value in types.items() if value]}
