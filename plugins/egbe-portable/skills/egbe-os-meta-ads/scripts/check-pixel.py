#!/usr/bin/env python3
"""Focused Meta source diagnostic; live event delivery still requires browser verification."""
from __future__ import annotations
import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

def read_text(path: Path, limit: int = 300_000) -> str:
    return path.read_text(encoding="utf-8", errors="replace")[:limit]

META_PIXEL_LITERAL_PATTERNS = (
    re.compile(r'''(?is)\b(?:NEXT_PUBLIC_)?META_PIXEL_ID\b[^\n;]{0,120}?["']\d{10,20}["']'''),
    re.compile(r'''(?is)\bfbq\s*\(\s*["']init["']\s*,\s*["']\d{10,20}["']'''),
    re.compile(r'''(?is)(?:facebook\.com/tr/\?id=|[?&]id=)["']?\d{10,20}\b'''),
)

# A direct `fbq('track'|'trackCustom', <name>, ...)` call.  Do not widen this
# to arbitrary functions accepting `track`: generic analytics clients use the
# same calling convention and must not satisfy the Meta delivery contract.
META_PIXEL_DIRECT_CALL_PATTERN = re.compile(
    r'''(?is)\b(?:window\s*\.\s*)?fbq\s*\(\s*["'](track|trackCustom)["']\s*,\s*([A-Za-z0-9_$."']+)'''
)
# Products may route calls through a retry/dedupe helper.  A helper only counts
# when its body forwards its first two parameters to `fbq(method, event, ...)`.
# Function declarations cover the normal exported helper shape; arrow helpers
# are included because many product frontends use them instead.
META_PIXEL_FUNCTION_DECL_PATTERN = re.compile(
    r'''(?im)\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(([^)]*)\)\s*\{'''
)
META_PIXEL_ARROW_DECL_PATTERN = re.compile(
    r'''(?im)\b(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>\s*\{'''
)
META_PIXEL_FORWARD_CALL_PATTERN = re.compile(
    r'''(?is)\b(?:window\s*\.\s*)?fbq\s*\(\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*,\s*([A-Za-z_$][A-Za-z0-9_$]*)'''
)
# `const NAME = "value"` so a constant used as an event name can be resolved.
META_PIXEL_CONST_PATTERN = re.compile(
    r'''(?m)^\s*(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*(?::[^=\n]+)?=\s*["']([^"'\n]+)["']'''
)
# `from "x"`, `import "x"`, `require("x")` — used to follow a delivery module
# into the helper that builds its payload.
META_PIXEL_IMPORT_PATTERN = re.compile(
    r'''(?is)\b(?:from|import|require\s*\()\s*["']([^"'\n]+)["']'''
)
# A product has a signup funnel / takes money — used to decide whether the
# matching Meta event is required, since not every product has either.
# Matched against whole path segments, not substrings: "register" as a
# substring also hits `register-service-worker.ts`, and demanding a Lead event
# from a product with no signup at all would block a correct deploy.
SIGNUP_PATH_SEGMENTS = frozenset({"signup", "sign-up", "signups", "register"})
PAYMENT_PATH_SEGMENTS = frozenset({"checkout", "billing", "payment", "payments"})
PAYMENT_ENV_HINTS = ("PAYMENTS_API_KEY", "STRIPE_SECRET_KEY", "PAYMENT_WEBHOOK_SECRET")

def _closing_brace(text: str, opening_brace: int) -> int:
    """Return the matching brace for a shallow JS function body, if present."""
    depth = 0
    for index in range(opening_brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def meta_pixel_wrapper_names(text: str) -> set[str]:
    """Names of helpers demonstrably forwarding `(method, event)` to `fbq`."""
    wrappers: set[str] = set()
    for pattern in (META_PIXEL_FUNCTION_DECL_PATTERN, META_PIXEL_ARROW_DECL_PATTERN):
        for match in pattern.finditer(text):
            params = re.findall(r"[A-Za-z_$][A-Za-z0-9_$]*", match.group(2))
            if len(params) < 2:
                continue
            end = _closing_brace(text, match.end() - 1)
            if end < 0:
                continue
            body = text[match.end():end]
            if any(method == params[0] and event == params[1]
                   for method, event in META_PIXEL_FORWARD_CALL_PATTERN.findall(body)):
                wrappers.add(match.group(1))
    return wrappers


def _meta_pixel_call_pattern(function_name: str) -> re.Pattern[str]:
    return re.compile(
        rf'''(?is)\b{re.escape(function_name)}\s*\(\s*["'](track|trackCustom)["']\s*,\s*([A-Za-z0-9_$."']+)'''
    )


def meta_pixel_events_sent(text: str) -> set[str]:
    """Event names a source file actually hands to fbq.

    The name is often a constant (`fbq("trackCustom", ACTIVATION_EVENT, ...)`),
    so resolve identifiers against the string constants declared in the same
    text before giving up on a match.
    """
    constants = dict(META_PIXEL_CONST_PATTERN.findall(text))
    sent: set[str] = set()
    call_patterns = [META_PIXEL_DIRECT_CALL_PATTERN]
    call_patterns.extend(_meta_pixel_call_pattern(name) for name in meta_pixel_wrapper_names(text))
    for pattern in call_patterns:
        for _method, raw in pattern.findall(text):
            argument = raw.strip()
            if argument[:1] in {'"', "'"}:
                sent.add(argument.strip("\"'"))
            elif argument in constants:
                sent.add(constants[argument])
    return sent


def meta_pixel_delivery_scope(files: list[Path], texts: list[str], depth: int = 3) -> str:
    """Text of the modules that take part in Meta event delivery.

    Starts from the files that hand an event to the pixel and follows their
    local imports.  The contract asks products to share one payload helper, and
    that helper legitimately lives in its own module — so scoping to files that
    literally contain `fbq` would fail a compliant split, while scanning the
    whole frontend would pass on an unrelated file that merely names the field.
    """
    keys = [path.with_suffix("").as_posix().lower() for path in files]
    wrapper_names = set().union(*(meta_pixel_wrapper_names(body) for body in texts))
    selected = {
        index for index, body in enumerate(texts)
        if META_PIXEL_DIRECT_CALL_PATTERN.search(body)
        or any(_meta_pixel_call_pattern(name).search(body) for name in wrapper_names)
    }
    frontier = set(selected)
    for _ in range(depth):
        discovered: set[int] = set()
        for index in frontier:
            for specifier in META_PIXEL_IMPORT_PATTERN.findall(texts[index]):
                tail = specifier.strip().rstrip("/")
                tail = re.sub(r"\.(m|c)?[jt]sx?$", "", tail)
                tail = re.sub(r"^(?:\.{1,2}/)+", "", tail)
                tail = re.sub(r"^[@~]/", "", tail).lower()
                if not tail:
                    continue
                for other, key in enumerate(keys):
                    if other not in selected and (key == tail or key.endswith("/" + tail)):
                        discovered.add(other)
        if not discovered:
            break
        selected |= discovered
        frontier = discovered
    return "\n".join(texts[index] for index in sorted(selected))


def check_meta_pixel_wiring(files: list[Path], env_json: dict[str, Any]) -> list[str]:
    """Keep every product on the gateway-owned Meta dataset and event shape.

    This is deliberately a source contract, not proof that Meta received the
    event; the Meta skill verifies the live browser request later.  It catches
    the deploy-time failure modes that matter here: a copied literal pixel id,
    and a funnel the ad network cannot see past.

    `PageView` and `Activation` are required of every product.  `Lead` and
    `Purchase` are required only when the product actually has a signup funnel
    or takes money — demanding them everywhere would fail honest products that
    have neither.
    """
    frontend = [
        path for path in files
        if path.suffix.lower() in {".astro", ".html", ".js", ".jsx", ".ts", ".tsx"}
    ]
    texts = [read_text(path, limit=300_000) for path in frontend]
    text = "\n".join(texts)
    failures: list[str] = []
    if any(pattern.search(text) for pattern in META_PIXEL_LITERAL_PATTERNS):
        failures.append("meta_pixel:hardcoded_id:read_NEXT_PUBLIC_META_PIXEL_ID_without_fallback")

    # The gateway may intentionally be unconfigured in local/test installs. In
    # that case only prohibit literals; do not require browser tracking code.
    if not str(env_json.get("NEXT_PUBLIC_META_PIXEL_ID") or "").strip():
        return failures
    if "NEXT_PUBLIC_META_PIXEL_ID" not in text:
        failures.append("meta_pixel:missing_env_wiring:read_NEXT_PUBLIC_META_PIXEL_ID")

    sent = meta_pixel_events_sent(text)
    segments = {
        segment
        for path in files
        for segment in path.with_suffix("").as_posix().lower().split("/")
    }
    required = {
        "PageView": "meta_pixel:missing_pageview_event:fbq_track_PageView",
        "Activation": "meta_pixel:missing_activation_event:fbq_trackCustom_Activation",
    }
    if segments & SIGNUP_PATH_SEGMENTS:
        required["Lead"] = "meta_pixel:missing_lead_event:fbq_track_Lead_on_signup_completed"
    takes_money = bool(segments & PAYMENT_PATH_SEGMENTS) or any(
        hint in key.upper() for key in env_json for hint in PAYMENT_ENV_HINTS
    )
    if takes_money:
        required["Purchase"] = "meta_pixel:missing_purchase_event:fbq_track_Purchase_on_payment"
    for event, failure in required.items():
        if event not in sent:
            failures.append(failure)

    # Scope the payload check to the delivery modules and what they import,
    # so a shared payload helper in its own module still counts.
    pixel_text = meta_pixel_delivery_scope(frontend, texts)
    for parameter in ("content_name", "product_name", "egbe_product_id"):
        if parameter not in pixel_text:
            failures.append(f"meta_pixel:events_missing_{parameter}")
    return failures



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--pixel-config", type=Path, required=True, help="JSON with public NEXT_PUBLIC_META_PIXEL_ID; never a secret env file")
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error("root must be an existing product directory")
    files = []
    for current, dirs, names in os.walk(args.root):
        dirs[:] = [d for d in dirs if d not in {".git", ".next", ".agents", ".claude", "egbe-docs", "node_modules", "dist", "build", "coverage"}]
        files.extend(Path(current) / name for name in names if Path(name).suffix in {".js", ".jsx", ".ts", ".tsx", ".html", ".astro"})
    failures = check_meta_pixel_wiring(files, json.loads(args.pixel_config.read_text()))
    print(json.dumps({"findings": failures, "delivery_verified": False}, indent=2))
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
