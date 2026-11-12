#!/usr/bin/env python3
"""Walk the selected funnels in a real mobile browser and assemble walks.json.

  serve  one local mobile Chrome (390x844) behind 127.0.0.1:9417, a page per
         funnel. Actions, POSTed as JSON: open {funnel_id, url},
         screen {funnel_id, screen_id, kind, slices?, fields?},
         click {funnel_id, text | selector}, fill {funnel_id, selector, value},
         dom {funnel_id}, scroll {funnel_id, y}, eval {funnel_id, js},
         finish {funnel_id, status, stop_reason, unknown, observed_market?}.
  call   send one action: walk-funnels.py call screen '{"funnel_id": "...", ...}'
  build  write egbe-docs/research/market/work/funnel_teardown/walks.json from the records.

Screens are recorded under egbe-docs/research/market/work/funnel_teardown/records/ and
their screenshots under egbe-docs/research/market/assets/funnel-teardown/, so the decision
site can publish them. The agent decides every click and writes what it saw
(headline, cta, offer, proof, amounts, lead_fields, notes) in `fields`, with
the funnel-walk.v2 screen fields that apply (branch_role, submission_required,
completion_observed; contains_private_data with a redacted display_screenshot);
a walk stops at the first form it would have to send (`form_not_submitted`).
"""
from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

RUNTIME_REL = Path(_artifact_path("egbe-docs/research/market/work/funnel_teardown"))
SHOTS_REL = Path(_artifact_path("egbe-docs/research/market/assets/funnel-teardown"))
ADDRESS = ("127.0.0.1", 9417)
VIEWPORT = {"width": 390, "height": 844}
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
# funnel-walk.v2 screen fields the agent may record; build() adds defaults only where they are absent.
SCREEN_FIELDS = ("branch_role", "advance", "options", "words_per_option", "notes", "answer", "cta", "offer", "proof", "lead_fields", "amounts",
                 "result_type", "conversion_kind", "progress_indicator", "booking_kind", "captured_before_fill", "submission_required",
                 "completion_observed", "display_screenshot")
DOM_SUMMARY = """() => {
  const visible = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && r.bottom > 0 && r.top < innerHeight * 3; };
  const label = el => ((el.labels && el.labels[0] && el.labels[0].innerText) || el.getAttribute('aria-label') || el.placeholder || el.name || el.id || '').trim().slice(0, 100);
  return { url: location.href, title: document.title, text: document.body.innerText.replace(/\\n{2,}/g, '\\n').slice(0, 5000),
    inputs: [...document.querySelectorAll('input,select,textarea')].filter(x => x.type !== 'hidden' && visible(x))
      .map(x => ({ tag: x.tagName.toLowerCase(), type: x.type, name: x.name || null, required: x.required, label: label(x) })),
    buttons: [...document.querySelectorAll('a,button,[role=button],input[type=submit]')].filter(visible)
      .map(b => (b.innerText || b.value || b.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ').slice(0, 70)).filter(Boolean).slice(0, 40) };
}"""


def record_path(workspace: Path, funnel_id: str) -> Path:
    return workspace / RUNTIME_REL / "records" / f"{funnel_id}.json"


def load_record(workspace: Path, funnel_id: str) -> dict[str, Any]:
    path = record_path(workspace, funnel_id)
    return json.loads(path.read_text()) if path.is_file() else {"funnel_id": funnel_id, "screens": [], "redirects": []}


def save_record(workspace: Path, record: dict[str, Any]) -> None:
    path = record_path(workspace, record["funnel_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1, ensure_ascii=False))


def note_navigation(workspace: Path, funnel_id: str, url: str) -> None:
    """A main-frame navigation, saved at once: screen and finish reload the record from disk."""
    record = load_record(workspace, funnel_id)
    record["redirects"].append(url)
    save_record(workspace, record)


def record_screen(workspace: Path, funnel_id: str, screen_id: str, kind: str, shots: list[Path], summary: dict[str, Any],
                  fields: dict[str, Any]) -> dict[str, Any]:
    """One observed screen: its screenshots, what the page shows and what the agent read on it."""
    record = load_record(workspace, funnel_id)
    entry = {"screen_id": screen_id, "kind": kind, "url": summary.get("url"), "captured_at": datetime.now(timezone.utc).isoformat(),
             "shots": [{"path": shot.relative_to(workspace).as_posix(), "sha256": hashlib.sha256(shot.read_bytes()).hexdigest()} for shot in shots],
             "title": summary.get("title"), "text": summary.get("text"), "inputs": summary.get("inputs"), "buttons": summary.get("buttons"), **fields}
    record["screens"] = [s for s in record["screens"] if s["screen_id"] != screen_id] + [entry]
    save_record(workspace, record)
    return entry


def build(workspace: Path) -> dict[str, Any]:
    runtime = workspace / RUNTIME_REL
    candidates = json.loads((runtime / "candidates.json").read_text())
    context = runtime / "research-context.json"
    persona = (json.loads(context.read_text()).get("persona") or {}).get("id", "buyer") if context.is_file() else "buyer"
    by_id = {c["funnel_id"]: c for c in candidates["candidates"]}
    walks = []
    for path in sorted((runtime / "records").glob("*.json")):
        record = json.loads(path.read_text())
        candidate, walk = by_id[record["funnel_id"]], record.get("walk") or {}
        screens = []
        for n, s in enumerate(record["screens"], 1):
            # The agent declares private pixels; the validator then publishes its redacted `display_screenshot`.
            shots = [{**shot, "contains_private_data": s.get("contains_private_data") is True} for shot in s["shots"]]
            screen = {"screen_id": s["screen_id"], "attempt_id": record["attempt_id"], "url": s["url"], "kind": s["kind"], "branch_role": "main",
                      "advance": "none" if n == len(record["screens"]) else "button", "headline": s.get("headline") or s.get("title") or "",
                      "options": "none", "notes": "", "lead_fields": [], "amounts": [], "screenshot": shots[0], "screenshots": shots[1:],
                      "observed_at": s["captured_at"], "source": "browser", **({"submission_required": True} if s["kind"] == "contact request" else {}),
                      **{key: s[key] for key in SCREEN_FIELDS if key in s}}
            screen["headline_words"] = len(re.findall(r"\w+", screen["headline"]))
            screens.append(screen)
        item = {"funnel_id": record["funnel_id"], "campaign_ids": candidate["campaign_ids"], "path_id": "buyer", "address": candidate["address"],
                "role": candidate["role"], "persona_id": persona, "walked_on": record["walked_on"], "viewport": "390x844",
                "observed_market": walk.get("observed_market") or {"language": None, "country": None, "currency": None},
                "status": walk.get("status", "boundary"), "stop_reason": walk.get("stop_reason", "form_not_submitted"),
                "observed_outcome": walk.get("observed_outcome", "not_observed"), "unknown": walk.get("unknown", []), "screens": screens, "branch_points": []}
        hops = [hop for hop in record.get("redirects") or [] if hop != candidate["address"]]
        if screens and screens[0]["url"] != candidate["address"] and hops:
            chain, previous = [], candidate["address"]
            for hop in hops:
                chain.append({"from": previous, "to": hop, "source_ref": f"browser:{screens[0]['screen_id']}"})
                previous = hop
            item["redirect_chain"] = chain
        walks.append(item)
    document = {"schema_version": 2, "contract": "funnel-walk.v2", "inputs_sha256": candidates["inputs_sha256"], "walks": walks}
    (runtime / "walks.json").write_text(json.dumps(document, indent=1, ensure_ascii=False))
    return document


def serve(workspace: Path) -> None:  # pragma: no cover - drives a real browser
    from playwright.sync_api import sync_playwright

    pages: dict[str, Any] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)

        def settle(page) -> None:
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                pass
            page.wait_for_timeout(1500)

        def summary(page) -> dict[str, Any]:
            return page.evaluate(DOM_SUMMARY)

        def page_of(funnel_id: str):
            return pages[funnel_id]["page"]

        def open_(funnel_id: str, url: str) -> dict[str, Any]:
            if funnel_id in pages:
                pages[funnel_id]["context"].close()
            context = browser.new_context(viewport=VIEWPORT, is_mobile=True, has_touch=True, device_scale_factor=2, user_agent=IPHONE, locale="en-US")
            page = context.new_page()
            record = load_record(workspace, funnel_id)
            record.update(address=url, walked_on=date.today().isoformat(), attempt_id=f"{funnel_id}-a1", redirects=[])
            save_record(workspace, record)
            page.on("framenavigated", lambda frame: frame == page.main_frame and note_navigation(workspace, funnel_id, frame.url))
            pages[funnel_id] = {"context": context, "page": page}
            response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
            settle(page)
            return {"status": response.status if response else None, **summary(page)}

        def screen(funnel_id: str, screen_id: str, kind: str, slices: int = 0, fields: dict | None = None) -> dict[str, Any]:
            page, directory = page_of(funnel_id), workspace / SHOTS_REL / funnel_id
            directory.mkdir(parents=True, exist_ok=True)
            shots = [directory / f"{screen_id}.png"]
            page.screenshot(path=str(shots[0]))
            top = page.evaluate("scrollY")
            for n in range(1, slices + 1):
                page.evaluate(f"scrollTo(0, {top + n * VIEWPORT['height']})")
                page.wait_for_timeout(500)
                shots.append(directory / f"{screen_id}-lower-{n:02d}.png")
                page.screenshot(path=str(shots[-1]))
            page.evaluate(f"scrollTo(0, {top})")
            return record_screen(workspace, funnel_id, screen_id, kind, shots, summary(page), fields or {})

        def click(funnel_id: str, text: str | None = None, selector: str | None = None) -> dict[str, Any]:
            page = page_of(funnel_id)
            target = page.locator(selector).first if selector else page.get_by_text(text).first
            target.click(timeout=8000, force=True)
            settle(page)
            return summary(page)

        def finish(funnel_id: str, **walk: Any) -> dict[str, Any]:
            record = load_record(workspace, funnel_id)
            record["walk"] = walk
            save_record(workspace, record)
            return {"finished": funnel_id, "screens": len(record["screens"])}

        actions = {
            "open": open_, "screen": screen, "click": click, "finish": finish,
            "fill": lambda funnel_id, selector, value: page_of(funnel_id).locator(selector).first.fill(value, timeout=8000) or {"filled": selector},
            "dom": lambda funnel_id: summary(page_of(funnel_id)),
            "scroll": lambda funnel_id, y: page_of(funnel_id).evaluate(f"scrollTo(0, {int(y)})") or summary(page_of(funnel_id)),
            "eval": lambda funnel_id, js: {"result": page_of(funnel_id).evaluate(js)},
            "close": lambda funnel_id: pages.pop(funnel_id)["context"].close() or {"closed": funnel_id},
        }

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                try:
                    body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                    out = actions[self.path.strip("/")](**body)
                except Exception as exc:  # the agent reads the error and decides
                    out = {"error": str(exc)[:600]}
                data = json.dumps(out, ensure_ascii=False, default=str).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:
                pass

        print(f"walk driver ready on http://{ADDRESS[0]}:{ADDRESS[1]}", flush=True)
        HTTPServer(ADDRESS, Handler).serve_forever()


def call(action: str, payload: str) -> dict[str, Any]:
    request = urllib.request.Request(f"http://{ADDRESS[0]}:{ADDRESS[1]}/{action}", data=payload.encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("serve", "call", "build"))
    parser.add_argument("action", nargs="?")
    parser.add_argument("payload", nargs="?", default="{}")
    parser.add_argument("--workspace", type=Path, default=Path("."))
    args = parser.parse_args()
    if args.command == "serve":
        serve(args.workspace.resolve())
    elif args.command == "call":
        print(json.dumps(call(args.action, args.payload), ensure_ascii=False)[:4000])
    else:
        document = build(args.workspace.resolve())
        print(f"{len(document['walks'])} walks, {sum(len(w['screens']) for w in document['walks'])} screens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
