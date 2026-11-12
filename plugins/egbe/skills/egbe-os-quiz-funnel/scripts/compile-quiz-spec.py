#!/usr/bin/env python3
"""Validate a quiz funnel specification and render its derived artifacts.

Reads `egbe-docs/product/quizzes/<quiz-slug>/quiz.json` below the workspace
root, checks its executable contract, and writes `QUIZ.md`,
`quiz.public.json`, and `validation.json` next to them.

The compiler checks structure and consistency. It cannot check that a claim is
true; that remains the author's responsibility.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit


SPEC_CONTRACT = "quiz-funnel-spec-v1"
PUBLIC_CONTRACT = "quiz-funnel-public-v1"
REPORT_CONTRACT = "quiz-funnel-validation-v1"
PAGE_FILES = ("QUIZ.md", "quiz.public.json")

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
PARAM_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")
ROUTE_PATTERN = re.compile(r"^/[a-z0-9_-]+(?:/[a-z0-9_-]+)*$")
TOKEN_PATTERN = re.compile(r"\{\{(.*?)\}\}")
ANSWER_TOKEN_PATTERN = re.compile(r"^answer:([a-z][a-z0-9_-]{0,39})$")

# First path segments that belong to other surfaces of a product.
RESERVED_SEGMENTS = {
    "account",
    "admin",
    "api",
    "auth",
    "checkout",
    "dashboard",
    "login",
    "logout",
    "pricing",
    "privacy",
    "register",
    "signup",
    "terms",
}
# Geographies where tracking beyond what is strictly necessary needs consent:
# the European Economic Area, the United Kingdom, and Switzerland.
CONSENT_GEOGRAPHIES = frozenset(
    "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE "
    "IS LI NO GB CH".split()
)
PERSONAL_PARAMS = {"email", "mail", "name", "phone", "tel"}
DESTINATION_KINDS = ("booking_url", "lead_form", "signup", "checkout")
GOAL_DESTINATIONS = {
    "call": {"booking_url", "lead_form"},
    "signup": {"signup"},
    "payment": {"checkout"},
}
LEAD_FIELDS = ("name", "email", "phone", "company")
PROOF_KINDS = {"count", "fact", "logo", "statistic", "testimonial"}
QUESTION_PURPOSES = {"build_case", "personalize", "qualify"}
INTERSTITIAL_KINDS = {"encouragement", "proof", "teach"}
RESULT_FITS = {"fit", "partial", "not_fit"}

MAX_RULE_COMBINATIONS = 200_000


class SpecError(ValueError):
    """The executable specification violates the contract."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_choice(value: Any, choices: Any) -> bool:
    return isinstance(value, str) and value in choices


def _plain(value: str) -> str:
    """A text without case and accents, for finding a phrase in another text."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )


def _has_control_characters(value: str) -> bool:
    return any(character.isspace() or ord(character) < 32 for character in value)


def _named(path: str, item: Any) -> str:
    """`screens[1]` becomes `screens[1] (behind)` when the item has a usable id."""
    identifier = item.get("id") if isinstance(item, dict) else None
    if isinstance(identifier, str) and ID_PATTERN.fullmatch(identifier):
        return f"{path} ({identifier})"
    return path


class Tokens:
    """Which `{{answer:...}}` tokens one visitor-facing text may contain."""

    def __init__(
        self, questions: dict[str, dict[str, Any]], *, sentence: bool, place: str
    ) -> None:
        self.questions = questions
        self.sentence = sentence
        self.place = place

    def as_points(self) -> "Tokens":
        return Tokens(self.questions, sentence=False, place=self.place)


class Validation:
    """Collect executable contract errors and nonblocking diagnostics."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[dict[str, str]] = []
        self.reachability = "not_checked"
        # Questions whose answer a rule or a token uses.
        self.referenced: set[str] = set()
        # Every text the visitor reads.
        self.read: list[tuple[str, str]] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, rule: str, target: str, message: str) -> None:
        self.warnings.append({"rule": rule, "target": target, "message": message})

    def text(self, value: Any, path: str) -> bool:
        """An internal text: any non-empty string."""
        if _is_text(value):
            return True
        self.error(f"{path} must be a non-empty string")
        return False

    def copy(
        self,
        value: Any,
        path: str,
        *,
        tokens: Tokens | None = None,
    ) -> bool:
        """A text the visitor reads: one plain line, with safe answer tokens."""
        if not self.text(value, path):
            return False
        if value != value.strip() or "\n" in value or "\r" in value:
            self.error(
                f"{path} must be one line of plain text without line breaks or "
                "surrounding spaces"
            )
        self._check_tokens(value, path, tokens)
        self.read.append((path, value))
        return True

    def _check_tokens(
        self, value: str, path: str, tokens: Tokens | None
    ) -> None:
        if tokens is None:
            if "{{" in value or "}}" in value:
                self.error(
                    f"{path} must not contain a token; tokens work only in the "
                    "headline, body, and points of interstitial screens and results"
                )
            return
        leftover = TOKEN_PATTERN.sub("", value)
        if "{{" in leftover or "}}" in leftover:
            self.error(f"{path} contains an unfinished token")
        for raw in TOKEN_PATTERN.findall(value):
            match = ANSWER_TOKEN_PATTERN.fullmatch(raw.strip())
            if match is None:
                self.error(
                    f"{path} contains the unknown token '{{{{{raw}}}}}'; only "
                    "{{answer:<question id>}} is supported"
                )
                continue
            question_id = match.group(1)
            question = tokens.questions.get(question_id)
            if question is None:
                self.error(
                    f"{path} token names '{question_id}', which is not a question "
                    f"the visitor has answered before {tokens.place}"
                )
                continue
            self.referenced.add(question_id)
            if question["sensitive"]:
                self.error(
                    f"{path} token names the sensitive question '{question_id}'; "
                    "answer text must not appear on unmasked screens or results"
                )
                continue
            if not tokens.sentence:
                continue
            if question["select"] != "single":
                self.error(
                    f"{path} token names '{question_id}', which is not a "
                    "single-select question; quote it in `points` instead"
                )
            if question["has_escape"]:
                self.error(
                    f"{path} token names '{question_id}', which has an escape "
                    "option; a declined answer cannot be quoted in a sentence, "
                    "quote it in `points` instead"
                )

    def text_list(self, value: Any, path: str, *, nonempty: bool) -> list[str]:
        if not isinstance(value, list):
            self.error(f"{path} must be an array")
            return []
        if nonempty and not value:
            self.error(f"{path} must not be empty")
        items = []
        for index, item in enumerate(value):
            if self.text(item, f"{path}[{index}]"):
                items.append(item)
        return items

    def mapping(
        self,
        value: Any,
        path: str,
        *,
        required: tuple[str, ...],
        optional: tuple[str, ...] = (),
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            self.error(f"{path} must be an object")
            return None
        for key in required:
            if key not in value:
                self.error(f"{path}.{key} is required")
        allowed = set(required) | set(optional)
        for key in sorted(str(key) for key in value if key not in allowed):
            self.error(f"{path}.{key} is not part of the contract")
        return value

    def identifier(self, value: Any, path: str) -> bool:
        if isinstance(value, str) and ID_PATTERN.fullmatch(value):
            return True
        self.error(
            f"{path} must start with a lowercase letter and contain only "
            "lowercase letters, digits, '-' or '_' (40 characters at most)"
        )
        return False

    def flag(self, value: Any, path: str) -> bool:
        if isinstance(value, bool):
            return value
        self.error(f"{path} must be true or false")
        return False


def _is_same_origin_path(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("/")
        and not value.startswith("//")
        and "\\" not in value
        and "#" not in value
        and not _has_control_characters(value)
    )


def _query_keys(query: str) -> set[str]:
    return {key.lower() for key, _ in parse_qsl(query, keep_blank_values=True)}


def _validate_https_url(check: Validation, value: Any, path: str) -> bool:
    message = f"{path} must be an absolute https URL"
    if not _is_text(value) or _has_control_characters(value):
        check.error(message)
        return False
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        credentials = parts.username or parts.password
        _ = parts.port  # Reading the port validates it.
    except ValueError:
        check.error(message)
        return False
    if parts.scheme != "https" or not hostname or "." not in hostname:
        check.error(message)
        return False
    valid = True
    if credentials:
        check.error(f"{path} must not contain credentials")
        valid = False
    if parts.fragment:
        check.error(f"{path} must not contain a fragment")
        valid = False
    personal = sorted(_query_keys(parts.query) & PERSONAL_PARAMS)
    if personal:
        check.error(
            f"{path} must not carry personal data in its query ({', '.join(personal)})"
        )
        valid = False
    return valid


def _location(value: str) -> str:
    """The part of an address that identifies the page, without its query."""
    if value.startswith("/"):
        return value.split("?", 1)[0].rstrip("/") or "/"
    parts = urlsplit(value)
    return f"https://{(parts.hostname or '').lower()}{parts.path.rstrip('/')}"


def _validate_path(check: Validation, value: Any, path: str) -> str | None:
    if not _is_same_origin_path(value):
        check.error(
            f"{path} must be a same-origin path that starts with '/' and has no "
            "fragment or spaces"
        )
        return None
    personal = sorted(_query_keys(urlsplit(value).query) & PERSONAL_PARAMS)
    if personal:
        check.error(
            f"{path} must not carry personal data in its query ({', '.join(personal)})"
        )
        return None
    return _location(value)


def _validate_inputs(check: Validation, inputs: Any) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "not_for": [],
        "geographies": [],
        "claims": [],
    }
    inputs = check.mapping(
        inputs,
        "inputs",
        required=("product", "application", "segment", "offer", "traffic", "sources"),
    )
    if inputs is None:
        return facts
    check.text(inputs.get("product"), "inputs.product")

    application = check.mapping(
        inputs.get("application"), "inputs.application", required=("repository", "url")
    )
    if application is not None:
        check.text(application.get("repository"), "inputs.application.repository")
        _validate_https_url(check, application.get("url"), "inputs.application.url")

    segment = check.mapping(
        inputs.get("segment"),
        "inputs.segment",
        required=("name", "situation", "problem"),
    )
    if segment is not None:
        for key in ("name", "situation", "problem"):
            check.text(segment.get(key), f"inputs.segment.{key}")

    offer = check.mapping(
        inputs.get("offer"),
        "inputs.offer",
        required=("promise", "mechanism", "terms", "claims_to_avoid", "not_for"),
    )
    if offer is not None:
        for key in ("promise", "mechanism", "terms"):
            check.text(offer.get(key), f"inputs.offer.{key}")
        facts["claims"] = check.text_list(
            offer.get("claims_to_avoid"), "inputs.offer.claims_to_avoid", nonempty=False
        )
        facts["not_for"] = check.text_list(
            offer.get("not_for"), "inputs.offer.not_for", nonempty=False
        )

    traffic = check.mapping(
        inputs.get("traffic"),
        "inputs.traffic",
        required=("channels", "geographies"),
        optional=("promise",),
    )
    if traffic is not None:
        check.text_list(traffic.get("channels"), "inputs.traffic.channels", nonempty=True)
        geographies = check.text_list(
            traffic.get("geographies"), "inputs.traffic.geographies", nonempty=True
        )
        for index, code in enumerate(geographies):
            if not COUNTRY_PATTERN.fullmatch(code):
                check.error(
                    f"inputs.traffic.geographies[{index}] must be a two-letter "
                    "country code such as US, GB, or ES"
                )
        facts["geographies"] = geographies
        if "promise" in traffic:
            check.text(traffic["promise"], "inputs.traffic.promise")

    sources = inputs.get("sources")
    if not isinstance(sources, list) or not sources:
        check.error("inputs.sources must be a non-empty array")
        return facts
    for index, source in enumerate(sources):
        source = check.mapping(
            source, f"inputs.sources[{index}]", required=("label", "ref")
        )
        if source is not None:
            check.text(source.get("label"), f"inputs.sources[{index}].label")
            check.text(source.get("ref"), f"inputs.sources[{index}].ref")
    return facts


def _validate_link(check: Validation, link: Any, path: str) -> str | None:
    """A `link` destination carries exactly one of a same-origin path or a URL."""
    if not isinstance(link, dict):
        check.error(f"{path} must be an object")
        return None
    for key in sorted(str(key) for key in link if key not in {"kind", "path", "url"}):
        check.error(f"{path}.{key} is not part of the contract")
    if link.get("kind") != "link":
        check.error(f"{path}.kind must be 'link'")
    has_path, has_url = "path" in link, "url" in link
    if has_path == has_url:
        check.error(f"{path} must contain exactly one of 'path' or 'url'")
        return None
    if has_path:
        return _validate_path(check, link["path"], f"{path}.path")
    if _validate_https_url(check, link["url"], f"{path}.url"):
        return _location(link["url"])
    return None


def _validate_booking(check: Validation, destination: dict[str, Any]) -> str | None:
    check.mapping(
        destination,
        "goal.destination",
        required=("kind", "url"),
        optional=("fallback_params", "result_param"),
    )
    valid_url = _validate_https_url(check, destination.get("url"), "goal.destination.url")
    carried = _query_keys(urlsplit(destination["url"]).query) if valid_url else set()

    params = destination.get("fallback_params", {})
    if not isinstance(params, dict):
        check.error("goal.destination.fallback_params must be an object")
    else:
        for key, value in params.items():
            if not isinstance(key, str) or not PARAM_PATTERN.fullmatch(key):
                check.error(
                    f"goal.destination.fallback_params.{key} is not a valid "
                    "query parameter name"
                )
            elif key in PERSONAL_PARAMS:
                check.error(
                    f"goal.destination.fallback_params.{key} would carry personal data"
                )
            check.text(value, f"goal.destination.fallback_params.{key}")
    if "result_param" in destination:
        result_param = destination["result_param"]
        if not isinstance(result_param, str) or not PARAM_PATTERN.fullmatch(result_param):
            check.error(
                "goal.destination.result_param is not a valid query parameter name"
            )
        elif result_param in PERSONAL_PARAMS:
            check.error("goal.destination.result_param would carry personal data")
        elif result_param in carried:
            check.error(
                f"goal.destination.url already carries '{result_param}', so the "
                "result could never be added; remove it from the address or "
                "choose another result_param"
            )
    return _location(destination["url"]) if valid_url else None


def _validate_lead_form(check: Validation, destination: dict[str, Any]) -> str | None:
    check.mapping(
        destination,
        "goal.destination",
        required=(
            "kind",
            "action",
            "fields",
            "field_labels",
            "submit_label",
            "error",
            "success",
        ),
        optional=("consent_note",),
    )
    fields = check.text_list(
        destination.get("fields"), "goal.destination.fields", nonempty=True
    )
    for field in fields:
        if field not in LEAD_FIELDS:
            check.error(
                f"goal.destination.fields contains '{field}'; allowed fields are "
                f"{', '.join(LEAD_FIELDS)}"
            )
    if len(set(fields)) != len(fields):
        check.error("goal.destination.fields must not repeat a field")
    if fields and not {"email", "phone"} & set(fields):
        check.error("goal.destination.fields must include email or phone")
    labels = destination.get("field_labels")
    if not isinstance(labels, dict):
        check.error("goal.destination.field_labels must be an object")
    else:
        for field in fields:
            check.copy(labels.get(field), f"goal.destination.field_labels.{field}")
        for key in sorted(str(key) for key in labels if key not in fields):
            check.error(f"goal.destination.field_labels.{key} has no matching field")
    check.copy(
        destination.get("submit_label"),
        "goal.destination.submit_label",
    )
    check.copy(destination.get("error"), "goal.destination.error")
    if "consent_note" in destination:
        check.copy(
            destination["consent_note"],
            "goal.destination.consent_note",
        )
    success = check.mapping(
        destination.get("success"),
        "goal.destination.success",
        required=("headline", "body"),
    )
    if success is not None:
        for key in ("headline", "body"):
            check.copy(
                success.get(key),
                f"goal.destination.success.{key}",
            )
    return _validate_path(check, destination.get("action"), "goal.destination.action")


def _validate_checkout(check: Validation, destination: dict[str, Any]) -> str | None:
    check.mapping(
        destination,
        "goal.destination",
        required=("kind", "path", "plan_key", "price"),
        optional=("plan_param",),
    )
    check.text(destination.get("plan_key"), "goal.destination.plan_key")
    if "price" in destination:
        check.copy(destination["price"], "goal.destination.price")
    location = _validate_path(check, destination.get("path"), "goal.destination.path")
    plan_param = destination.get("plan_param", "plan")
    if (
        not isinstance(plan_param, str)
        or not PARAM_PATTERN.fullmatch(plan_param)
        or plan_param in PERSONAL_PARAMS
    ):
        check.error("goal.destination.plan_param is not a valid query parameter name")
    elif location is not None and plan_param in _query_keys(
        urlsplit(destination["path"]).query
    ):
        check.error(
            f"goal.destination.path must not already carry '{plan_param}'; "
            "the selected plan is appended from plan_key"
        )
    return location


def _validate_goal(check: Validation, goal: Any) -> dict[str, Any]:
    """Validate the goal; return where it leads and the price it must show."""
    facts: dict[str, Any] = {"location": None, "price": None}
    goal = check.mapping(
        goal, "goal", required=("type", "destination"), optional=("statement",)
    )
    if goal is None:
        return facts
    goal_type = goal.get("type")
    if not _is_choice(goal_type, GOAL_DESTINATIONS):
        check.error("goal.type must be one of call, signup, payment")
        goal_type = None
    if "statement" in goal:
        check.text(goal["statement"], "goal.statement")

    destination = goal.get("destination")
    if not isinstance(destination, dict):
        check.error("goal.destination must be an object")
        return facts
    kind = destination.get("kind")
    if not _is_choice(kind, DESTINATION_KINDS):
        check.error(
            f"goal.destination.kind must be one of {', '.join(DESTINATION_KINDS)}"
        )
        return facts
    if goal_type is not None and kind not in GOAL_DESTINATIONS[goal_type]:
        check.error(
            f"goal.destination.kind '{kind}' does not serve goal '{goal_type}'; "
            f"use one of {', '.join(sorted(GOAL_DESTINATIONS[goal_type]))}"
        )
    if kind == "booking_url":
        facts["location"] = _validate_booking(check, destination)
    elif kind == "lead_form":
        facts["location"] = _validate_lead_form(check, destination)
    elif kind == "checkout":
        facts["location"] = _validate_checkout(check, destination)
        if _is_text(destination.get("price")):
            facts["price"] = destination["price"].strip()
    else:
        check.mapping(destination, "goal.destination", required=("kind", "path"))
        facts["location"] = _validate_path(
            check, destination.get("path"), "goal.destination.path"
        )
    return facts


def _validate_proof(check: Validation, proof: Any) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    if not isinstance(proof, list):
        check.error("proof must be an array (it may be empty)")
        return entries
    for index, item in enumerate(proof):
        path = _named(f"proof[{index}]", item)
        item = check.mapping(
            item,
            path,
            required=("id", "kind", "text", "source"),
            optional=("author", "citation"),
        )
        if item is None:
            continue
        if check.identifier(item.get("id"), f"{path}.id"):
            if item["id"] in entries:
                check.error(f"{path}.id is already used")
            entries[item["id"]] = item
        kind = item.get("kind")
        if not _is_choice(kind, PROOF_KINDS):
            check.error(f"{path}.kind must be one of {', '.join(sorted(PROOF_KINDS))}")
        check.copy(item.get("text"), f"{path}.text")
        if not _is_text(item.get("source")):
            check.error(
                f"{path}.source is required: record where this proof can be "
                "checked, or remove the proof"
            )
        if kind == "testimonial" and "author" not in item:
            check.error(f"{path}.author is required for a testimonial")
        if kind == "statistic" and "citation" not in item:
            check.error(
                f"{path}.citation is required for a third-party statistic; it is "
                "shown to the visitor next to the number"
            )
        for key in ("author", "citation"):
            if key in item:
                check.copy(item[key], f"{path}.{key}")
    return entries


def _validate_proof_refs(
    check: Validation,
    value: Any,
    path: str,
    proof: dict[str, dict[str, Any]],
    used: set[str],
) -> tuple[str, ...]:
    refs = check.text_list(value, path, nonempty=False)
    for ref in refs:
        if ref not in proof:
            check.error(f"{path} references unknown proof '{ref}'")
        else:
            used.add(ref)
    if len(set(refs)) != len(refs):
        check.error(f"{path} must not repeat a proof id")
    return tuple(ref for ref in refs if ref in proof)


def _validate_media(check: Validation, media: Any, path: str) -> None:
    media = check.mapping(media, path, required=("src", "alt", "source"))
    if media is None:
        return
    src = media.get("src")
    if isinstance(src, str) and src.startswith("/"):
        _validate_path(check, src, f"{path}.src")
    else:
        _validate_https_url(check, src, f"{path}.src")
    check.copy(media.get("alt"), f"{path}.alt")
    if not _is_text(media.get("source")):
        check.error(
            f"{path}.source is required: record what the image shows and where "
            "it comes from"
        )


def _validate_texts(
    check: Validation,
    item: dict[str, Any],
    path: str,
    tokens: Tokens,
) -> None:
    """The headline, body, and points of an interstitial screen, variant, or result."""
    options = {
        "tokens": tokens,
    }
    if "headline" in item:
        check.copy(item["headline"], f"{path}.headline", **options)
    if "body" in item:
        check.copy(item["body"], f"{path}.body", **options)
    if "media" in item:
        _validate_media(check, item["media"], f"{path}.media")
    if "points" not in item:
        return
    points = item["points"]
    if not isinstance(points, list) or not points:
        check.error(f"{path}.points must be a non-empty array when present")
        return
    options["tokens"] = tokens.as_points()
    for index, point in enumerate(points):
        check.copy(point, f"{path}.points[{index}]", **options)


def _validate_when(
    check: Validation,
    when: Any,
    path: str,
    questions: dict[str, dict[str, Any]],
    place: str,
    *,
    in_results: bool,
) -> bool:
    if not isinstance(when, dict) or len(when) != 1 or not set(when) <= {"all", "any"}:
        check.error(f"{path} must contain exactly one of 'all' or 'any'")
        return False
    mode = next(iter(when))
    conditions = when[mode]
    if not isinstance(conditions, list) or not conditions:
        check.error(f"{path}.{mode} must be a non-empty array")
        return False
    valid = True
    for index, condition in enumerate(conditions):
        condition_path = f"{path}.{mode}[{index}]"
        if not isinstance(condition, dict):
            check.error(f"{condition_path} must be an object")
            valid = False
            continue
        for key in sorted(
            str(key) for key in condition if key not in {"screen", "any_of", "none_of"}
        ):
            check.error(f"{condition_path}.{key} is not part of the contract")
            valid = False
        operators = [key for key in ("any_of", "none_of") if key in condition]
        if len(operators) != 1:
            check.error(
                f"{condition_path} must contain exactly one of 'any_of' or 'none_of'"
            )
            valid = False
            continue
        screen_id = condition.get("screen")
        question = questions.get(screen_id) if isinstance(screen_id, str) else None
        if question is None:
            check.error(
                f"{condition_path}.screen must name a question the visitor has "
                f"answered before {place}"
            )
            valid = False
        else:
            check.referenced.add(screen_id)
            if in_results:
                if question["sensitive"]:
                    check.error(
                        f"{condition_path}.screen names the sensitive question "
                        f"'{screen_id}'; the answer to a sensitive question must "
                        "not choose the result, because the result is reported"
                    )
                    valid = False
        values = condition[operators[0]]
        if (
            not isinstance(values, list)
            or not values
            or not all(isinstance(value, str) for value in values)
        ):
            check.error(
                f"{condition_path}.{operators[0]} must be a non-empty array of option ids"
            )
            valid = False
            continue
        if len(set(values)) != len(values):
            check.error(f"{condition_path}.{operators[0]} must not repeat an option")
            valid = False
        if question is not None:
            for value in values:
                if value not in question["options"]:
                    check.error(
                        f"{condition_path}.{operators[0]} names unknown option "
                        f"'{value}' of screen '{screen_id}'"
                    )
                    valid = False
    return valid


def _validate_question(
    check: Validation, screen: dict[str, Any], path: str, index: int
) -> dict[str, Any] | None:
    select = screen.get("select")
    required = ["id", "type", "select", "headline", "options"]
    if select == "multi":
        required.append("button")
    # `button` and `lead` get their own, more helpful messages below.
    check.mapping(
        screen,
        path,
        required=tuple(required),
        optional=("button", "hint", "lead", "sensitive", "purpose"),
    )
    target = screen["id"] if isinstance(screen.get("id"), str) else f"#{index + 1}"

    if select not in ("single", "multi"):
        check.error(f"{path}.select must be 'single' or 'multi'")
    if select == "single" and "button" in screen:
        check.error(
            f"{path}.button is not allowed: a single-select question advances "
            "as soon as an option is chosen"
        )
    if select == "multi" and "button" in screen:
        check.copy(screen["button"], f"{path}.button")
    if "lead" in screen:
        check.copy(screen["lead"], f"{path}.lead")
    if "hint" in screen:
        check.copy(screen["hint"], f"{path}.hint")
    check.copy(
        screen.get("headline"),
        f"{path}.headline",
    )
    purpose = screen.get("purpose")
    if purpose is not None and not _is_choice(purpose, QUESTION_PURPOSES):
        check.error(
            f"{path}.purpose must be one of {', '.join(sorted(QUESTION_PURPOSES))}"
        )
    sensitive = "sensitive" in screen and check.flag(
        screen["sensitive"], f"{path}.sensitive"
    )

    options = screen.get("options")
    if not isinstance(options, list):
        check.error(f"{path}.options must be an array")
        return None
    if not options:
        check.error(f"{path}.options must not be empty")

    known: dict[str, dict[str, Any]] = {}
    escapes = 0
    for option_index, option in enumerate(options):
        option_path = _named(f"{path}.options[{option_index}]", option)
        option = check.mapping(
            option,
            option_path,
            required=("id", "label"),
            optional=("escape", "phrase"),
        )
        if option is None:
            continue
        if check.identifier(option.get("id"), f"{option_path}.id"):
            if option["id"] in known:
                check.error(f"{option_path}.id is already used on this screen")
            known[option["id"]] = option
        check.copy(option.get("label"), f"{option_path}.label")
        if "phrase" in option:
            check.copy(option["phrase"], f"{option_path}.phrase")
        if "escape" in option and check.flag(option["escape"], f"{option_path}.escape"):
            escapes += 1
    if escapes > 1:
        check.error(f"{path}.options must not contain more than one escape option")
    if options and escapes == len(options):
        check.error(f"{path}.options must offer an answer besides the escape option")
    if sensitive and escapes == 0:
        check.error(
            f"{path} is sensitive and needs an escape option such as "
            "'Prefer not to say' (set escape to true on it)"
        )
    if select == "multi" and escapes == 0:
        check.warn(
            "multi_select_escape",
            target,
            f"{path} is a multi-select question without an escape option; a "
            "visitor to whom no option applies cannot continue",
        )
    return {
        "select": select if select in ("single", "multi") else "single",
        "purpose": purpose,
        "options": known,
        "has_escape": escapes > 0,
        "sensitive": sensitive,
    }


def _validate_interstitial(
    check: Validation,
    screen: dict[str, Any],
    path: str,
    index: int,
    questions: dict[str, dict[str, Any]],
    proof: dict[str, dict[str, Any]],
    used_proof: set[str],
) -> list[Any]:
    """Validate one interstitial screen and return its variant conditions."""
    check.mapping(
        screen,
        path,
        required=("id", "type", "kind", "headline", "button"),
        optional=("body", "media", "points", "proof_ids", "variants"),
    )
    target = screen["id"] if isinstance(screen.get("id"), str) else f"#{index + 1}"
    place = f"screen '{target}'"
    tokens = Tokens(questions, sentence=True, place=place)
    kind = screen.get("kind")
    if not _is_choice(kind, INTERSTITIAL_KINDS):
        check.error(f"{path}.kind must be one of {', '.join(sorted(INTERSTITIAL_KINDS))}")
    refs = _validate_proof_refs(
        check, screen.get("proof_ids", []), f"{path}.proof_ids", proof, used_proof
    )
    if kind == "proof" and not refs:
        check.error(f"{path} is a proof screen and must reference at least one proof")
    _validate_texts(check, screen, path, tokens)
    check.copy(screen.get("button"), f"{path}.button")

    conditions: list[Any] = []
    if "variants" not in screen:
        return conditions
    variants = screen["variants"]
    if not isinstance(variants, list) or not variants:
        check.error(f"{path}.variants must be a non-empty array when present")
        return conditions
    for variant_index, variant in enumerate(variants):
        variant_path = f"{path}.variants[{variant_index}]"
        variant = check.mapping(
            variant,
            variant_path,
            required=("when",),
            optional=("headline", "body", "media", "points", "proof_ids"),
        )
        if variant is None:
            conditions.append(None)
            continue
        if not set(variant) & {"headline", "body", "media", "points", "proof_ids"}:
            check.error(
                f"{variant_path} must change at least one text, the image, or the proof"
            )
        valid = _validate_when(
            check,
            variant.get("when"),
            f"{variant_path}.when",
            questions,
            place,
            in_results=False,
        )
        conditions.append(variant.get("when") if valid else None)
        variant_refs = refs
        if "proof_ids" in variant:
            variant_refs = _validate_proof_refs(
                check,
                variant["proof_ids"],
                f"{variant_path}.proof_ids",
                proof,
                used_proof,
            )
            if kind == "proof" and not variant_refs:
                check.error(
                    f"{variant_path} belongs to a proof screen and must reference "
                    "at least one proof"
                )
        _validate_texts(check, variant, variant_path, tokens)
    return conditions


def _validate_screens(
    check: Validation,
    screens: Any,
    proof: dict[str, dict[str, Any]],
    used_proof: set[str],
) -> tuple[dict[str, dict[str, Any]], list[tuple[str, list[Any]]], set[str]]:
    questions: dict[str, dict[str, Any]] = {}
    rule_sets: list[tuple[str, list[Any]]] = []
    seen: set[str] = set()
    if not isinstance(screens, list) or not screens:
        check.error("screens must be a non-empty array")
        return questions, rule_sets, seen

    for index, screen in enumerate(screens):
        path = _named(f"screens[{index}]", screen)
        if not isinstance(screen, dict):
            check.error(f"{path} must be an object")
            continue
        screen_id = screen.get("id")
        if check.identifier(screen_id, f"{path}.id"):
            if screen_id in seen:
                check.error(f"{path}.id is already used")
            seen.add(screen_id)
        else:
            screen_id = None
        kind = screen.get("type")
        if kind == "question":
            question = _validate_question(check, screen, path, index)
            if question is not None and screen_id is not None:
                questions[screen_id] = question
        elif kind == "interstitial":
            conditions = _validate_interstitial(
                check, screen, path, index, dict(questions), proof, used_proof
            )
            if conditions:
                rule_sets.append((path, [*conditions, None]))
        else:
            check.error(f"{path}.type must be 'question' or 'interstitial'")

    return questions, rule_sets, seen


def _can_be_left_out(point: str, questions: dict[str, dict[str, Any]]) -> bool:
    """True when the page leaves the point out for some visitors.

    A point is left out when the visitor chose the escape option of a question
    that the point quotes.
    """
    for raw in TOKEN_PATTERN.findall(point):
        match = ANSWER_TOKEN_PATTERN.fullmatch(raw.strip())
        question = questions.get(match.group(1)) if match else None
        if question is None or question["has_escape"]:
            return True
    return False


def _validate_price_is_shown(
    check: Validation,
    result: dict[str, Any],
    cta: dict[str, Any],
    path: str,
    price: str,
    questions: dict[str, dict[str, Any]],
) -> None:
    """Every visitor of a result that leads to the checkout reads the price."""
    always = [result.get("headline"), result.get("body"), cta.get("label"), cta.get("note")]
    sometimes = []
    points = result.get("points")
    for point in points if isinstance(points, list) else []:
        if isinstance(point, str):
            (sometimes if _can_be_left_out(point, questions) else always).append(point)
    if any(isinstance(text, str) and price in text for text in always):
        return
    if any(price in point for point in sometimes):
        check.error(
            f"{path} shows the price '{price}' only in a point that is left out "
            "when the visitor declines a question it quotes; state the price in "
            "a text that every visitor of this result reads"
        )
    else:
        check.error(
            f"{path} leads to the checkout and must show the price "
            f"'{price}' exactly as goal.destination.price states it"
        )


def _validate_results(
    check: Validation,
    results: Any,
    questions: dict[str, dict[str, Any]],
    proof: dict[str, dict[str, Any]],
    used_proof: set[str],
    goal: dict[str, Any],
    not_for: list[str],
    screen_ids: set[str],
) -> list[Any]:
    """Validate the results and return their conditions in order."""
    conditions: list[Any] = []
    if not isinstance(results, list) or not results:
        check.error("results must be a non-empty array")
        return conditions
    place = "the result"
    tokens = Tokens(questions, sentence=True, place=place)
    seen: set[str] = set()
    converting = 0
    for index, result in enumerate(results):
        path = _named(f"results[{index}]", result)
        result = check.mapping(
            result,
            path,
            required=("id", "fit", "headline", "body", "cta"),
            optional=("when", "media", "points", "proof_ids"),
        )
        if result is None:
            conditions.append(None)
            continue
        result_id = result.get("id")
        if check.identifier(result_id, f"{path}.id"):
            if result_id in seen:
                check.error(f"{path}.id is already used")
            elif result_id in screen_ids:
                check.error(f"{path}.id is already used by a screen")
            seen.add(result_id)

        is_last = index == len(results) - 1
        if "when" in result:
            if is_last:
                check.error(
                    f"{path} is the last result and must be the default: remove 'when'"
                )
            valid = _validate_when(
                check, result["when"], f"{path}.when", questions, place, in_results=True
            )
            conditions.append(result["when"] if valid and not is_last else None)
        else:
            if not is_last:
                check.error(
                    f"{path} has no 'when'; only the last result may be the default"
                )
            conditions.append(None)

        fit = result.get("fit")
        if not _is_choice(fit, RESULT_FITS):
            check.error(f"{path}.fit must be one of fit, partial, not_fit")
            fit = None
        elif fit == "not_fit" and not not_for:
            check.error(
                f"{path} is not_fit, but inputs.offer.not_for names nobody the "
                "offer is not for; do not invent a disqualification"
            )
        refs = _validate_proof_refs(
            check, result.get("proof_ids", []), f"{path}.proof_ids", proof, used_proof
        )
        _validate_texts(check, result, path, tokens)

        if "cta" not in result:
            continue
        cta = result["cta"]
        if cta is None:
            if fit != "not_fit":
                check.error(f"{path}.cta may be null only for a not_fit result")
            continue
        cta = check.mapping(
            cta, f"{path}.cta", required=("label",), optional=("destination", "note")
        )
        if cta is None:
            continue
        if "note" in cta:
            check.copy(
                cta["note"],
                f"{path}.cta.note",
            )
        check.copy(
            cta.get("label"),
            f"{path}.cta.label",
        )
        if "destination" in cta:
            location = _validate_link(check, cta["destination"], f"{path}.cta.destination")
            if location is not None and location == goal["location"]:
                check.error(
                    f"{path}.cta.destination leads to the destination of the goal; "
                    "remove it to use the goal, or lead somewhere else"
                )
        elif fit == "not_fit":
            check.error(
                f"{path} is not_fit and must not send the visitor to the goal "
                "destination: give it its own link destination or set cta to null"
            )
        elif fit in ("fit", "partial"):
            converting += 1
            if goal["price"]:
                _validate_price_is_shown(
                    check, result, cta, path, goal["price"], questions
                )

    if converting == 0:
        check.error(
            "no fit or partial result leads to the goal destination; the quiz "
            "cannot convert"
        )
    return conditions


def _answer_classes(
    question: dict[str, Any], option_sets: list[frozenset[str]],
    budget: int = MAX_RULE_COMBINATIONS,
) -> set[tuple[bool, ...]] | None:
    """Distinct ways one question's answer can satisfy the option sets that rules test."""
    regular = [key for key, option in question["options"].items() if not option.get("escape")]
    escapes = [key for key, option in question["options"].items() if option.get("escape")]

    def signature(option_id: str) -> tuple[bool, ...]:
        return tuple(option_id in options for options in option_sets)

    classes = {signature(option_id) for option_id in escapes}
    singles = {signature(option_id) for option_id in regular}
    if question["select"] == "single":
        return classes | singles if len(classes | singles) <= budget else None
    # A multi-select answer is any non-empty set of regular options, or the
    # escape option alone. Its class is the union of the classes of its options.
    # Bound the work BEFORE combinations are enumerated. Large option lists are
    # valid input; a skipped exhaustive check is not proof of reachability.
    if len(singles) >= budget.bit_length() or (1 << len(singles)) - 1 + len(classes) > budget:
        return None
    for size in range(1, len(singles) + 1):
        for group in itertools.combinations(sorted(singles), size):
            classes.add(tuple(any(column) for column in zip(*group)))
    return classes


def _unreachable(
    rules: list[Any], questions: dict[str, dict[str, Any]]
) -> list[int] | None:
    """Indexes of rules no answer can select; None when the space is too large.

    `rules` holds `when` objects in order; None stands for a rule that always
    matches, such as the default result.
    """
    tested: dict[str, list[frozenset[str]]] = {}
    for when in rules:
        if when is None:
            continue
        for condition in next(iter(when.values())):
            options = frozenset(condition.get("any_of") or condition.get("none_of"))
            known = tested.setdefault(condition["screen"], [])
            if options not in known:
                known.append(options)

    names = sorted(tested)
    spaces = []
    total = 1
    for name in names:
        classes = _answer_classes(questions[name], tested[name], MAX_RULE_COMBINATIONS // total)
        if classes is None:
            return None
        space = sorted(classes)
        spaces.append(space)
        total *= max(len(space), 1)
        if total > MAX_RULE_COMBINATIONS:
            return None

    def matches(when: Any, answer: dict[str, tuple[bool, ...]]) -> bool:
        if when is None:
            return True
        mode, conditions = next(iter(when.items()))
        outcomes = []
        for condition in conditions:
            operator = "any_of" if "any_of" in condition else "none_of"
            column = tested[condition["screen"]].index(frozenset(condition[operator]))
            hit = answer[condition["screen"]][column]
            outcomes.append(hit if operator == "any_of" else not hit)
        return all(outcomes) if mode == "all" else any(outcomes)

    reached: set[int] = set()
    for combination in itertools.product(*spaces):
        answer = dict(zip(names, combination))
        for index, when in enumerate(rules):
            if matches(when, answer):
                reached.add(index)
                break
    return [index for index in range(len(rules)) if index not in reached]


def _validate_reachability(
    check: Validation,
    results: list[Any],
    rule_sets: list[tuple[str, list[Any]]],
    result_rules: list[Any],
    questions: dict[str, dict[str, Any]],
) -> None:
    check.reachability = "checked"

    def unreachable(rules: list[Any], target: str) -> list[int]:
        found = _unreachable(rules, questions)
        if found is None:
            check.reachability = "not_checked"
            check.warn(
                "reachability_not_checked", target,
                "Exhaustive reachability exceeds the bounded analysis budget; "
                "not verified. Check these paths separately before release.",
            )
            return []
        return found

    for index in unreachable(result_rules, "results"):
        check.error(
            f"{_named(f'results[{index}]', results[index])} can never be shown: "
            "its conditions cannot be met, or earlier results catch every answer "
            "that meets them"
        )
    for path, rules in rule_sets:
        for index in unreachable(rules, path):
            if index == len(rules) - 1:
                check.error(
                    f"{path} never shows its own texts because its variants catch "
                    "every answer; move the texts of one variant onto the screen"
                )
            else:
                check.error(
                    f"{path}.variants[{index}] can never be shown: its conditions "
                    "cannot be met, or earlier variants catch every answer that "
                    "meets them"
                )


def _validate_claims(
    check: Validation,
    inputs: dict[str, Any],
) -> None:
    """Check configured prohibited claims; word matching cannot prove truth."""
    claims = [(claim.strip(), _plain(claim.strip())) for claim in inputs["claims"]]
    for path, text in check.read:
        plain = _plain(text)
        for claim, plain_claim in claims:
            if plain_claim and plain_claim in plain:
                check.error(
                    f"{path} states a claim to avoid: '{claim}' "
                    "(inputs.offer.claims_to_avoid)"
                )


def validate_spec(
    spec: Any,
) -> tuple[list[str], list[dict[str, str]], dict[str, Any]]:
    """Return executable contract errors, diagnostics, and derived facts."""
    check = Validation()
    facts: dict[str, Any] = {"consent_geographies": []}
    root = check.mapping(
        spec,
        "spec",
        required=(
            "contract",
            "quiz_slug",
            "product_slug",
            "route",
            "language",
            "title",
            "ui",
            "inputs",
            "goal",
            "proof",
            "screens",
            "results",
        ),
    )
    if root is None:
        return check.errors, [], facts

    if root.get("contract") != SPEC_CONTRACT:
        check.error(f"contract must be '{SPEC_CONTRACT}'")
    for key in ("quiz_slug", "product_slug"):
        value = root.get(key)
        if not isinstance(value, str) or not SLUG_PATTERN.fullmatch(value):
            check.error(
                f"{key} must be a slug of lowercase letters, digits and '-' "
                "(63 characters at most)"
            )
    route = root.get("route")
    if not isinstance(route, str) or not ROUTE_PATTERN.fullmatch(route):
        check.error(
            "route must be a lowercase path such as /quiz/<quiz-slug> without a "
            "query, fragment, or trailing slash"
        )
    elif route.split("/")[1] in RESERVED_SEGMENTS:
        check.error(
            f"route '{route}' starts with '/{route.split('/')[1]}', which belongs "
            "to another surface of the product"
        )
    language = root.get("language")
    if not isinstance(language, str) or not LANGUAGE_PATTERN.fullmatch(language):
        check.error("language must be a language tag such as en, es, or pt-BR")
    check.copy(root.get("title"), "title")

    ui = check.mapping(root.get("ui"), "ui", required=("back", "progress"))
    if ui is not None:
        check.copy(ui.get("back"), "ui.back")
        if check.copy(ui.get("progress"), "ui.progress"):
            for placeholder in ("{current}", "{total}"):
                if placeholder not in ui["progress"]:
                    check.error(f"ui.progress must contain the placeholder {placeholder}")

    inputs = _validate_inputs(check, root.get("inputs"))
    facts["consent_geographies"] = sorted(
        {code for code in inputs["geographies"] if code in CONSENT_GEOGRAPHIES}
    )
    goal = _validate_goal(check, root.get("goal"))
    proof = _validate_proof(check, root.get("proof"))
    used_proof: set[str] = set()
    questions, rule_sets, screen_ids = _validate_screens(
        check, root.get("screens"), proof, used_proof
    )
    result_rules = _validate_results(
        check,
        root.get("results"),
        questions,
        proof,
        used_proof,
        goal,
        inputs["not_for"],
        screen_ids,
    )
    for proof_id in sorted(set(proof) - used_proof):
        check.error(f"proof '{proof_id}' is not shown on any screen or result")
    for screen_id, question in questions.items():
        if question["purpose"] in ("personalize", "qualify") and screen_id not in check.referenced:
            check.warn(
                "unused_answer",
                screen_id,
                f"question '{screen_id}' has the purpose '{question['purpose']}' "
                "but no rule or token uses its answer",
            )
    if not check.errors:
        # Rules and claims are only comparable once every reference is known to be valid.
        _validate_reachability(check, root["results"], rule_sets, result_rules, questions)
        _validate_claims(check, inputs)

    facts["reachability"] = check.reachability
    return check.errors, check.warnings, facts


def _used_proof_ids(spec: dict[str, Any]) -> list[str]:
    ordered: list[str] = []
    holders: list[dict[str, Any]] = []
    for screen in spec["screens"]:
        holders.append(screen)
        holders.extend(screen.get("variants", []))
    holders.extend(spec["results"])
    for holder in holders:
        for proof_id in holder.get("proof_ids", []):
            if proof_id not in ordered:
                ordered.append(proof_id)
    return ordered


def public_spec(spec: dict[str, Any], digest: str) -> dict[str, Any]:
    """Project the part of a valid specification that the page renders."""
    proof_by_id = {item["id"]: item for item in spec["proof"]}
    proof = {}
    for proof_id in _used_proof_ids(spec):
        item = proof_by_id[proof_id]
        proof[proof_id] = {
            key: item[key] for key in ("kind", "text", "author", "citation") if key in item
        }
    def shown(item: dict[str, Any]) -> dict[str, Any]:
        # `purpose` explains the design and the `source` of an image is a note
        # for the owner; the page needs neither. `sensitive` stays: the page
        # keeps the chosen option of such a question private.
        public_item = {key: value for key, value in item.items() if key != "purpose"}
        if "media" in item:
            public_item["media"] = {key: item["media"][key] for key in ("src", "alt")}
        if "variants" in item:
            public_item["variants"] = [shown(variant) for variant in item["variants"]]
        return public_item

    screens = [shown(screen) for screen in spec["screens"]]
    public = {
        "contract": PUBLIC_CONTRACT,
        "quiz_slug": spec["quiz_slug"],
        "product_slug": spec["product_slug"],
        "route": spec["route"],
        "language": spec["language"],
        "title": spec["title"],
        "ui": spec["ui"],
        "goal": {
            "type": spec["goal"]["type"],
            "destination": spec["goal"]["destination"],
        },
        "proof": proof,
        "screens": screens,
        "results": [shown(result) for result in spec["results"]],
    }
    # `spec_sha256` names the specification this was compiled from.
    # `public_sha256` changes only when the page itself changes; saved progress
    # of a visitor is valid for one value of it.
    return {
        "contract": PUBLIC_CONTRACT,
        "spec_sha256": digest,
        "public_sha256": _sha256(_canonical_json(public)),
        **{key: value for key, value in public.items() if key != "contract"},
    }


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _option_label(questions: dict[str, dict[str, Any]], screen_id: str, option_id: str) -> str:
    for option in questions[screen_id]["options"]:
        if option["id"] == option_id:
            return option["label"]
    return option_id


def _describe_when(
    when: dict[str, Any] | None, questions: dict[str, dict[str, Any]], default: str
) -> str:
    if when is None:
        return default
    mode = next(iter(when))
    parts = []
    for condition in when[mode]:
        operator = "any_of" if "any_of" in condition else "none_of"
        option_ids = condition[operator]
        labels = ", ".join(
            f"\"{_option_label(questions, condition['screen'], option_id)}\""
            for option_id in option_ids
        )
        if len(option_ids) == 1:
            verb = "is" if operator == "any_of" else "is not"
        else:
            verb = "is one of" if operator == "any_of" else "is none of"
        parts.append(f"`{condition['screen']}` {verb} {labels}")
    joiner = " and " if mode == "all" else " or "
    return "Shown when " + joiner.join(parts) + "."


def _describe_destination(destination: dict[str, Any]) -> str:
    kind = destination["kind"]
    if kind == "booking_url":
        return f"booking page {destination['url']}"
    if kind == "lead_form":
        fields = ", ".join(destination["fields"])
        return f"request form ({fields}) posting to `{destination['action']}`"
    if kind == "signup":
        return f"signup at `{destination['path']}`"
    if kind == "checkout":
        return (
            f"checkout at `{destination['path']}` for the plan "
            f"`{destination['plan_key']}` at {destination['price']}"
        )
    return destination.get("path") or destination.get("url", "")


def _render_texts(lines: list[str], item: dict[str, Any]) -> None:
    if "headline" in item:
        lines.extend([f"**{item['headline']}**", ""])
    if "body" in item:
        lines.extend([item["body"], ""])
    if "points" in item:
        lines.extend(f"- {point}" for point in item["points"])
        lines.append("")
    if "media" in item:
        media = item["media"]
        lines.extend(
            [f"Image: `{media['src']}` — {media['alt']} (source: {media['source']})", ""]
        )
    if item.get("proof_ids"):
        refs = ", ".join(f"`{proof_id}`" for proof_id in item["proof_ids"])
        lines.extend([f"Proof: {refs}", ""])


def render_markdown(
    spec: dict[str, Any], facts: dict[str, Any]
) -> str:
    inputs = spec["inputs"]
    goal = spec["goal"]
    offer = inputs["offer"]
    traffic = inputs["traffic"]
    questions = {
        screen["id"]: screen for screen in spec["screens"] if screen["type"] == "question"
    }
    consent = facts["consent_geographies"]
    lines = [
        f"# {spec['title']}",
        "",
        "Rendered from `quiz.json`. Edit the specification and compile it again; "
        "do not edit this file.",
        "",
        "## Summary",
        "",
        f"- **Product:** {inputs['product']}",
        f"- **Application:** {inputs['application']['url']} "
        f"(repository `{inputs['application']['repository']}`)",
        f"- **Segment:** {inputs['segment']['name']} — {inputs['segment']['situation']} "
        f"Problem: {inputs['segment']['problem']}",
        f"- **Offer:** {offer['promise']} Mechanism: {offer['mechanism']} "
        f"Terms: {offer['terms']}",
        f"- **Goal:** {goal['type']} — {_describe_destination(goal['destination'])}",
        f"- **Route:** `{spec['route']}`",
        f"- **Language:** {spec['language']}",
        f"- **Traffic:** {', '.join(traffic['channels'])} in "
        f"{', '.join(traffic['geographies'])}"
        + (f"; arriving promise: {traffic['promise']}" if "promise" in traffic else ""),
        "- **Consent:** "
        + (
            f"required in {', '.join(consent)} before tracking beyond what is "
            "strictly necessary"
            if consent
            else "no planned geography is on the consent list"
        ),
        f"- **Length:** {len(questions)} questions, "
        f"{len(spec['screens']) - len(questions)} interstitial screens, "
        f"{len(spec['results'])} results",
        "",
    ]
    for title, items in (
        ("The offer is not for:", offer["not_for"]),
        ("Claims to avoid:", offer["claims_to_avoid"]),
    ):
        if items:
            lines.extend([title, ""])
            lines.extend(f"- {item}" for item in items)
            lines.append("")

    lines.extend(["## Proof", ""])
    if spec["proof"]:
        lines.extend(["| Id | Kind | Shown text | Source |", "|---|---|---|---|"])
        for item in spec["proof"]:
            shown = item["text"]
            if "author" in item:
                shown += f" — {item['author']}"
            if "citation" in item:
                shown += f" ({item['citation']})"
            lines.append(
                f"| `{item['id']}` | {item['kind']} | {_cell(shown)} | "
                f"{_cell(item['source'])} |"
            )
    else:
        lines.append("No proof is shown.")
    lines.append("")

    lines.extend(["## Flow", ""])
    for index, screen in enumerate(spec["screens"], start=1):
        if screen["type"] == "question":
            traits = [f"{screen['select']}-select"]
            if screen.get("purpose"):
                traits.append(screen["purpose"])
            if screen.get("sensitive"):
                traits.append("sensitive")
            lines.append(f"### {index}. `{screen['id']}` — question ({', '.join(traits)})")
            lines.append("")
            if "lead" in screen:
                lines.extend([f"Lead: {screen['lead']}", ""])
            lines.extend([f"**{screen['headline']}**", ""])
            if "hint" in screen:
                lines.extend([f"Hint: {screen['hint']}", ""])
            for option in screen["options"]:
                notes = []
                if "phrase" in option:
                    notes.append(f"in a sentence: \"{option['phrase']}\"")
                if option.get("escape"):
                    notes.append("escape")
                suffix = f" _({'; '.join(notes)})_" if notes else ""
                lines.append(f"- `{option['id']}` {option['label']}{suffix}")
            lines.append("")
            if screen["select"] == "multi":
                lines.extend([f"Button: {screen['button']}", ""])
            continue
        lines.append(f"### {index}. `{screen['id']}` — interstitial ({screen['kind']})")
        lines.append("")
        _render_texts(lines, screen)
        lines.extend([f"Button: {screen['button']}", ""])
        for variant in screen.get("variants", []):
            lines.extend(
                [
                    "Variant. "
                    + _describe_when(variant["when"], questions, "")
                    + " It replaces:",
                    "",
                ]
            )
            _render_texts(lines, variant)

    lines.extend(["## Results", ""])
    for result in spec["results"]:
        lines.extend(
            [
                f"### `{result['id']}` — {result['fit']}",
                "",
                _describe_when(
                    result.get("when"),
                    questions,
                    "Default: shown when no earlier result matches.",
                ),
                "",
            ]
        )
        if result["fit"] == "not_fit":
            lines.extend(
                [
                    "Appears as soon as the answers decide it: the questions after "
                    "the deciding one are skipped.",
                    "",
                ]
            )
        _render_texts(lines, result)
        cta = result["cta"]
        if cta is None:
            lines.append("No call to action.")
        elif "destination" in cta:
            lines.append(
                f"Call to action: {cta['label']} → "
                f"{_describe_destination(cta['destination'])}"
            )
        else:
            lines.append(f"Call to action: {cta['label']} → goal destination")
        if cta and "note" in cta:
            lines.extend(["", f"Note under the button: {cta['note']}"])
        lines.append("")

    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=str(path.parent), text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        # mkstemp creates owner-only files; artifacts are ordinary documents.
        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _format_problems(errors: list[str], warnings: list[dict[str, str]]) -> str:
    lines = ["Quiz specification is not ready:"]
    lines.extend(f"- {message}" for message in errors)
    for item in warnings:
        lines.append(f"- [{item['rule']} @ {item['target']}] {item['message']}")
    return "\n".join(lines)


def _load(folder: Path) -> Any:
    spec_path = folder / "quiz.json"
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SpecError(f"specification does not exist: {spec_path}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise SpecError(f"specification is not valid JSON: {exc}") from exc
    return spec


def compile_quiz(
    workspace: Path, quiz_slug: str, today: date, *, check_only: bool = False
) -> dict[str, Any]:
    if not SLUG_PATTERN.fullmatch(quiz_slug):
        raise SpecError("--quiz-slug must be a slug of lowercase letters, digits and '-'")
    folder = workspace / 'egbe-docs/product/quizzes' / quiz_slug
    try:
        spec = _load(folder)
        try:
            errors, warnings, facts = validate_spec(spec)
        except RecursionError as exc:
            raise SpecError("specification is nested too deeply") from exc
        if isinstance(spec, dict) and spec.get("quiz_slug") not in (None, quiz_slug):
            errors.append(
                f"quiz_slug '{spec.get('quiz_slug')}' does not match its folder "
                f"'{quiz_slug}'"
            )
        if errors:
            raise SpecError(_format_problems(errors, warnings))
    except SpecError as problem:
        if not check_only and folder.is_dir():
            # What an earlier version compiled must not outlive a failed compile.
            for name in PAGE_FILES:
                (folder / name).unlink(missing_ok=True)
            receipt = {
                "contract": REPORT_CONTRACT,
                "status": "not_ready",
                "validated_on": today.isoformat(),
                "quiz_slug": quiz_slug,
                "problems": str(problem).splitlines()[1:] or [str(problem)],
            }
            _atomic_write(
                folder / "validation.json",
                json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
            )
        raise

    digest = _sha256(_canonical_json(spec))
    public = public_spec(spec, digest)
    questions = [screen for screen in spec["screens"] if screen["type"] == "question"]
    report = {
        "contract": REPORT_CONTRACT,
        "status": "ready",
        "validated_on": today.isoformat(),
        "quiz_slug": spec["quiz_slug"],
        "route": spec["route"],
        "goal": spec["goal"]["type"],
        "destination": spec["goal"]["destination"]["kind"],
        "spec_sha256": digest,
        "public_sha256": public["public_sha256"],
        "counts": {
            "screens": len(spec["screens"]),
            "questions": len(questions),
            "interstitials": len(spec["screens"]) - len(questions),
            "results": len(spec["results"]),
            "proof": len(spec["proof"]),
        },
        "consent_geographies": facts["consent_geographies"],
        "reachability": facts["reachability"],
        "warnings": warnings,
    }
    if not check_only:
        _atomic_write(folder / "QUIZ.md", render_markdown(spec, facts))
        _atomic_write(
            folder / "quiz.public.json",
            json.dumps(public, indent=2, ensure_ascii=False) + "\n",
        )
        _atomic_write(
            folder / "validation.json",
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a quiz funnel specification and render its artifacts."
    )
    parser.add_argument(
        "--workspace",
        required=True,
        type=Path,
        help="Root that contains egbe-docs/product/quizzes/<quiz-slug>/",
    )
    parser.add_argument("--quiz-slug", required=True, help="Folder name of the quiz")
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=None,
        help="Reference date for reproducible tests (default: current UTC date)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate only; write and remove nothing",
    )
    args = parser.parse_args()
    today = args.today or datetime.now(timezone.utc).date()

    try:
        report = compile_quiz(
            args.workspace, args.quiz_slug, today, check_only=args.check
        )
    except (OSError, SpecError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    counts = report["counts"]
    print(
        f"Quiz specification ready: goal={report['goal']} "
        f"questions={counts['questions']} results={counts['results']} "
        f"sha256={report['spec_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
