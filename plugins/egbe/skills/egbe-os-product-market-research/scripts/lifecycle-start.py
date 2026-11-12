"""Private, portable input and human-action contracts for Lifecycle Capture."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

KINDS = ("newsletter", "account", "trial", "waitlist", "lead_form")
ENTRY_TYPES = ("details", "materials", "webinar", "quiz", "waitlist", "account", "trial", "newsletter")


def read_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path.name} must contain valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def _url(value: Any, label: str) -> str:
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError(f"{label} needs an https URL")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{label} needs an https URL without credentials")
    return value


def validate_entry(value: Any, domain: str, normalize: Callable[[str], str]) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{domain}: selected/fallback must be an object or null")
    out = dict(value)
    for key in ("id", "comparable_offer", "reason", "stop_condition"):
        if not isinstance(out.get(key), str) or not out[key].strip():
            raise ValueError(f"{domain}: entry needs {key}")
    source = _url(out.get("source_url"), f"{domain} source_url")
    destination = _url(out.get("entry_url"), f"{domain} entry_url")
    if normalize(urlsplit(source).hostname or "") != domain:
        raise ValueError(f"{domain}: source_url must originate on the competitor's domain")
    if normalize(urlsplit(destination).hostname or "") != domain:
        if not isinstance(out.get("handoff_evidence"), str) or not out["handoff_evidence"].strip():
            raise ValueError(f"{domain}: external form needs handoff_evidence for the linked or embedded destination")
    if out.get("kind") not in KINDS or out.get("entry_type") not in ENTRY_TYPES:
        raise ValueError(f"{domain}: invalid kind or entry_type")
    for key in ("needs_phone", "needs_card"):
        if key not in out or (out[key] is not None and not isinstance(out[key], bool)):
            raise ValueError(f"{domain}: {key} must be true, false or null (unknown)")
    fields = out.get("fields")
    if not isinstance(fields, list) or any(not isinstance(f, dict) or not isinstance(f.get("name"), str)
                                          or not isinstance(f.get("required"), bool) for f in fields):
        raise ValueError(f"{domain}: fields needs named fields with boolean required")
    instructions = out.get("instructions")
    if not isinstance(instructions, list) or not instructions or any(not isinstance(i, str) or not i.strip() for i in instructions):
        raise ValueError(f"{domain}: instructions must be a nonempty list")
    evidence = out.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"{domain}: entry needs source evidence")
    for proof in evidence:
        if not isinstance(proof, dict) or not isinstance(proof.get("detail"), str) or not proof["detail"].strip():
            raise ValueError(f"{domain}: evidence needs a detail")
        _url(proof.get("url"), f"{domain} evidence URL")
        try:
            observed = date.fromisoformat(proof["observed_on"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{domain}: evidence needs observed_on YYYY-MM-DD") from exc
        if observed > date.today():
            raise ValueError(f"{domain}: evidence cannot be observed in the future")
    return out


def discovery(path: Path, domains: list[str], normalize: Callable[[str], str]) -> dict[str, dict[str, Any]]:
    raw = read_object(path)
    if not raw:
        return {}
    if raw.get("schema_version") != 1 or not isinstance(raw.get("competitors"), list):
        raise ValueError("entry-points.json needs schema_version 1 and competitors")
    result = {}
    for value in raw["competitors"]:
        if not isinstance(value, dict):
            raise ValueError("entry-point competitor must be an object")
        domain = normalize(str(value.get("domain") or ""))
        if domain not in domains:
            continue
        if domain in result:
            raise ValueError(f"duplicate entry-point competitor {domain}")
        selected = validate_entry(value.get("selected"), domain, normalize)
        fallback = validate_entry(value.get("fallback"), domain, normalize)
        reason = value.get("skip_reason")
        if selected is None and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError(f"{domain}: no selected entry needs a skip_reason")
        if selected and fallback and selected["id"] == fallback["id"]:
            raise ValueError(f"{domain}: selected and fallback need different ids")
        result[domain] = {"selected": selected, "fallback": fallback, "skip_reason": reason,
                          "discovery_status": "reviewed"}
    return result


def subscription_entry(item: dict[str, Any], planned: dict[str, Any]) -> dict[str, Any]:
    """Bind a real subscription to the reviewed selected/fallback entry."""
    candidates = [e for e in (planned.get("selected"), planned.get("fallback")) if e]
    if not candidates:  # Only pre-existing, already active legacy captures use this path.
        if planned.get("legacy"):
            return {}
        raise ValueError(f"{item['domain']}: subscription needs a reviewed entry point")
    matches = [e for e in candidates if e["entry_url"] == item.get("entry_url") and e["kind"] == item.get("kind")
               and (not item.get("entry_id") or item["entry_id"] == e["id"])]
    if len(matches) != 1:
        raise ValueError(f"{item['domain']}: entry_url/kind must match the selected entry or recorded fallback")
    entry = matches[0]
    if entry["needs_phone"] is True or entry["needs_card"] is True:
        raise ValueError(f"{item['domain']}: selected entry requires a phone or card")
    if (entry["needs_phone"] is None or entry["needs_card"] is None) and item.get("requirements_verified") is not True:
        raise ValueError(f"{item['domain']}: the assigned human must verify unknown phone/card requirements")
    if planned.get("fallback") and entry["id"] == planned["fallback"]["id"] and not str(item.get("fallback_reason") or "").strip():
        raise ValueError(f"{item['domain']}: fallback use needs fallback_reason")
    return {"entry_id": entry["id"], "entry_type": entry["entry_type"], "source_url": entry["source_url"],
            "fallback_reason": item.get("fallback_reason"), "requirements_verified": item.get("requirements_verified")}


def render_signups(plan: dict[str, Any]) -> str:
    lines = ["# Lifecycle Capture: human signup actions", "", "Use only the planned address. Leave optional phone fields empty; stop before a required phone, a card, payment or CAPTCHA bypass.",
             "Only the assigned human with verified access to the planned aliases and mailbox may register, confirm double opt-in and unsubscribe; report each result and its actual date in the chat. If nobody has that access, leave actions pending. Never reply to sales representatives.",
             "", "This private list contains mailbox aliases. Keep it outside published research and decision packs.", ""]
    for c in plan["competitors"]:
        lines += [f"## {c['domain']}", "", f"Address: `{c['alias']}`", ""]
        if c.get("discovery_status") != "reviewed" and not c.get("legacy"):
            lines += ["Entry discovery is pending; there is no verified sign-up recommendation yet.", ""]
            continue
        if not c.get("selected"):
            lines += ["Skip: " + str(c.get("skip_reason") or "no reviewed entry"), ""]
        for label, entry in (("Selected", c.get("selected")), ("Fallback", c.get("fallback"))):
            if not entry:
                continue
            phone = "unknown — verify before submitting" if entry["needs_phone"] is None else "required — unavailable" if entry["needs_phone"] else "not required"
            card = "unknown — verify before submitting" if entry["needs_card"] is None else "required — unavailable" if entry["needs_card"] else "not required"
            lines += [f"**{label}: {entry['entry_type']} ({entry['id']})**", "", f"Source: {entry['source_url']}",
                      f"Form: {entry['entry_url']}", f"Phone: {phone}. Card: {card}.",
                      "Fields: " + ", ".join(f["name"] + (" (required)" if f["required"] else " (optional)") for f in entry["fields"]),
                      "Reason: " + entry["reason"], "", *[f"- {step}" for step in entry["instructions"]],
                      "", "Stop condition: " + entry["stop_condition"], ""]
    return "\n".join(lines)


def operator_actions(plan: dict[str, Any], subscriptions: list[dict[str, Any]], skipped: list[dict[str, Any]],
                     harvested_on: str | None, previous: dict[str, Any], harvested_domains: list[str] | None = None) -> dict[str, Any]:
    if previous.get("capture_id") != plan["capture_id"]:
        previous = {}
    old = {a["id"]: a for a in previous.get("actions", []) if isinstance(a, dict) and "id" in a}
    old_harvests = {a["id"]: a for a in previous.get("harvests", []) if isinstance(a, dict) and "id" in a}
    by_domain = {s["domain"]: s for s in subscriptions}
    skipped_domains = {s["domain"] for s in skipped}
    actions, harvests = [], []
    for c in plan["competitors"]:
        d, s = c["domain"], by_domain.get(c["domain"])
        if not s and c.get("discovery_status") != "reviewed" and not c.get("legacy"):
            continue
        discovery_skip = c.get("discovery_status") == "reviewed" and not c.get("selected") and bool(c.get("skip_reason"))
        signup_id = d + ":signup"
        actions.append({"id": signup_id, "domain": d, "kind": "signup",
                        "status": "completed" if s else "skipped" if d in skipped_domains or discovery_skip else "pending",
                        "due_on": old.get(signup_id, {}).get("due_on") or (date.today() + timedelta(days=1)).isoformat()})
        if not s:
            continue
        subscribed = date.fromisoformat(s["subscribed_on"])
        full_due = (subscribed + timedelta(days=14)).isoformat()
        if s.get("confirmed") is not None:
            actions.append({"id": d + ":confirm", "domain": d, "kind": "confirm",
                            "status": "completed" if s["confirmed"] else "skipped" if s.get("unsubscribed_on") else "pending",
                            "due_on": old.get(d + ":confirm", {}).get("due_on") or date.today().isoformat()})
        actions.append({"id": d + ":unsubscribe", "domain": d, "kind": "unsubscribe",
                        "status": "completed" if s.get("unsubscribed_on") else "pending", "due_on": full_due,
                        "blocked_by": d + ":full"})
        for kind, days in (("early", 3), ("full", 14)):
            due = (subscribed + timedelta(days=days)).isoformat()
            old_harvest = old_harvests.get(d + ":" + kind, {})
            ended_early = s.get("unsubscribed_on") and s["unsubscribed_on"] < due
            completed = (old_harvest.get("due_on") == due and old_harvest.get("status") == "completed") or (
                harvested_on and harvested_on >= due and d in (harvested_domains or []))
            status = "skipped" if ended_early else "completed" if completed else "pending"
            harvests.append({"id": d + ":" + kind, "domain": d, "kind": kind, "due_on": due, "status": status})
    return {"schema_version": 1, "section_id": "lifecycle_capture", "capture_id": plan["capture_id"],
            "product_domain": plan.get("product_domain", ""), "actions": actions, "harvests": harvests}
