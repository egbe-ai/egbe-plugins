"""Validate one homogeneous forecast scenario; never choose live campaign bids."""
from __future__ import annotations

import hashlib
import json
import math

MAX_KEYWORDS = 1000


def keywords(values: list) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValueError("forecast keywords must be a nonempty list of strings")
    result = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError("forecast accepts keyword strings, not mixed match/bid assets")
        term = " ".join(value.lower().split())
        if not term or len(term) > 80 or len(term.split()) > 10:
            raise ValueError("forecast keywords must be 1–80 characters and at most 10 words")
        if term not in result:
            result.append(term)
    return result


def validate_scenario(value: dict, locale: dict) -> dict:
    required = {"keywords", "location_code", "language_code", "match", "bid", "rationale", "source"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"scenario must contain exactly: {', '.join(sorted(required))}")
    if any(value[k] != v for k, v in locale.items()):
        raise ValueError("scenario location/language must match this run")
    terms = keywords(value["keywords"])
    if len(terms) > MAX_KEYWORDS:
        raise ValueError("explicit scenario exceeds the 1000-keyword provider cap; choose a bounded scenario")
    if value["match"] not in {"exact", "phrase", "broad"}:
        raise ValueError("scenario requires one match type: exact, phrase or broad")
    bid = value["bid"]
    if type(bid) not in (int, float) or not math.isfinite(bid) or not 0 < bid <= 500:
        raise ValueError("scenario bid must be finite, positive and at most 500")
    for key in ("rationale", "source"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError(f"scenario {key} is required")
    return {**value, "keywords": terms}


def coverage(*, requested: list[str], submitted: list[str], excluded: list[dict],
             locale: dict, bid: float, match: str, scenario: dict | None) -> dict:
    assumptions = scenario or {"rationale": "Exploratory historical CPC assumption, not a starting bid",
                               "source": "candidate keyword auction observations"}
    return {
        "kind": "explicit_scenario" if scenario else "exploratory_candidate_set",
        "locale": locale, "match": match, "bid": bid, "forecast_period": "next_month",
        "requested_count": len(requested), "submitted_count": len(submitted),
        "submitted_keywords": submitted, "omitted_keywords": requested[len(submitted):],
        "excluded": excluded, "rationale": assumptions["rationale"], "source": assumptions["source"],
        "scenario_sha256": hashlib.sha256(json.dumps(scenario or {}, sort_keys=True).encode()).hexdigest(),
        "limitations": "One homogeneous keyword set; not total market reach or an approved campaign. "
                        "Test-budget clicks are conditional linear arithmetic, not a daily-budget forecast.",
    }
