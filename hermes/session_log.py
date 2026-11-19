"""Egbe session logging for Hermes.

On by default in a project folder set up for Egbe, as the plugin's README and
Egbe's setup disclose. Each turn is recorded from Hermes's own plugin hooks
(`pre_llm_call`, `post_api_request`, `post_tool_call`, `post_llm_call`) and
sent when the turn ends (`on_session_end`) as OTLP traces to Egbe's telemetry
gateway, authenticated with the project's own Egbe key and grouped into the
Hermes session: the founder's message, model calls with usage, tool calls with
their results, and the reply, each redacted by Hermes's secret scrubber first.

It stays off when the folder has no private `.env.local` with Egbe credentials,
when that file says EGBE_SESSION_LOGGING=off, when the project's saved choice
declines logging or stops the `hermes` collector, when the plugin's
`session_logging` setting is false, or when the hermes_otel plugin already sends
this profile's traces to Egbe. It never fails a turn: errors become the result
that `hermes egbe status` shows.
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional

OS_URL = "https://os.hz.egbe.dev"
GATEWAY = "https://observe.hz.egbe.dev/telemetry"
HARNESS = "hermes"
TRACES_URL = f"{GATEWAY}/ingest/{HARNESS}/api/public/otel/v1/traces"
MAX_TEXT = 16_000
MAX_BODY = 7 * 1024 * 1024
# Turns whose end never arrived (a crashed run) are dropped beyond this many.
MAX_OPEN_TURNS = 64
KEY = re.compile(r"^[A-Za-z0-9_-]{16,}$")
PUBLIC_KEY = re.compile(r"^pk-lf-[A-Za-z0-9-]+$")
ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)=(.*)$")


def read_env(path: Path) -> Optional[dict[str, str]]:
    """The settings in a private dotenv file; None when others can read it.

    Setup writes `.env.local` with mode 600, while a copy that came with a
    cloned repository is readable by others and doesn't count."""
    if os.name != "nt" and path.stat().st_mode & 0o077:
        return None
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ENV_LINE.match(line)
        if match:
            value = match[2].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            values[match[1]] = value
    return values


def project_root(cwd: Optional[Path]) -> Optional[Path]:
    """The folder whose `.env.local` holds this session's Egbe settings: the
    working directory or the nearest parent with one, not above the Git root."""
    if cwd is None:
        return None
    for folder in (cwd, *cwd.parents):
        if (folder / ".env.local").is_file():
            return folder
        if (folder / ".git").exists() or folder == Path.home():
            return None
    return None


def _saved_choice_declines(project: Path) -> bool:
    try:
        saved = json.loads((project / "egbe-docs" / "telemetry" / "setup.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(saved, dict):
        return False
    if saved.get("consent") in ("declined", "skipped"):
        return True
    collector = (saved.get("collectors") or {}).get(HARNESS)
    return isinstance(collector, dict) and (collector.get("enabled") is False or "stop" in collector)


def _otel_sends_to_egbe(hermes_home: Optional[Path]) -> bool:
    """Whether the hermes_otel plugin's config already exports to Egbe's gateway."""
    if hermes_home is None:
        return False
    try:
        return f"/ingest/{HARNESS}" in (hermes_home / "hermes_otel.yaml").read_text(encoding="utf-8")
    except OSError:
        return False


def logging_settings(project: Optional[Path], enabled_setting: Any = True,
                     hermes_home: Optional[Path] = None) -> dict[str, str]:
    """`{"off": reason}`, or the credentials to log this project's turns with."""
    if enabled_setting is False:
        return {"off": "the plugin's session_logging setting is false"}
    if project is None:
        return {"off": "the folder is not set up for Egbe"}
    try:
        env = read_env(project / ".env.local")
    except (OSError, UnicodeDecodeError):
        return {"off": "the folder is not set up for Egbe"}
    if env is None:
        return {"off": "the folder's .env.local is readable by others"}
    choice = env.get("EGBE_SESSION_LOGGING", "")
    if choice not in ("", "on"):
        return {"off": f"EGBE_SESSION_LOGGING={choice}"}
    if choice == "" and _saved_choice_declines(project):
        return {"off": "the project's saved choice declines logging"}
    # `on` overrides a saved decline, never the guard against recording a session twice.
    if _otel_sends_to_egbe(hermes_home):
        return {"off": "the hermes_otel plugin already sends sessions to Egbe"}
    if env.get("OS_URL", "").rstrip("/") != OS_URL:
        return {"off": "the folder's OS_URL is not Egbe's"}
    key = env.get("EGBE_TELEMETRY_SECRET_KEY") or env.get("OS_API_KEY") or ""
    if not KEY.match(key):
        return {"off": "no usable Egbe key in the folder"}
    public = env.get("EGBE_TELEMETRY_PUBLIC_KEY", "")
    if public and not PUBLIC_KEY.match(public):
        return {"off": "unusable telemetry public key"}
    return {"key": key, "os_key": env.get("OS_API_KEY", ""), "public_key": public}


def _text(value: Any, redact: Callable[[str], str]) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = redact(text)
    if len(text) > MAX_TEXT:
        text = f"{text[:MAX_TEXT]}… [truncated {len(text) - MAX_TEXT} characters]"
    return text


def content_text(content: Any) -> str:
    """The text of a message's content; images and attachments are left out."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part["text"] for part in content
                         if isinstance(part, dict) and part.get("type") in ("text", "input_text", "output_text")
                         and isinstance(part.get("text"), str))
    return ""


def _nanos(seconds: float) -> str:
    return str(int(seconds * 1_000_000_000))


def _attributes(values: dict[str, Any]) -> list[dict]:
    out = []
    for key, value in values.items():
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            out.append({"key": key, "value": {"stringValue": str(value).lower()}})
        elif isinstance(value, (int, float)):
            out.append({"key": key, "value": {"intValue": str(round(value))}})
        else:
            out.append({"key": key, "value": {"stringValue": str(value)}})
    return out


def _tool_calls(raw: Any) -> list[dict]:
    calls = []
    for call in raw if isinstance(raw, list) else []:
        function = call.get("function") if isinstance(call, dict) else None
        if isinstance(function, dict):
            arguments = function.get("arguments")
            try:
                arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
            except ValueError:
                pass
            calls.append({"name": function.get("name"), "arguments": arguments})
    return calls


class Turn:
    """What Hermes reported about one turn so far."""

    def __init__(self, session_id: str, user_message: Any, model: str, platform: str,
                 project: Optional[Path], started: float):
        self.session_id = session_id
        self.prompt = content_text(user_message)
        self.model = model
        self.platform = platform
        self.project = project
        self.started = started
        self.reply: Optional[str] = None
        self.calls: list[dict] = []

    def api_call(self, kwargs: dict, now: float) -> None:
        started = kwargs.get("started_at")
        duration = kwargs.get("api_duration")
        if not isinstance(started, (int, float)):
            started = now - (duration if isinstance(duration, (int, float)) else 0)
        ended = kwargs.get("ended_at") if isinstance(kwargs.get("ended_at"), (int, float)) else now
        response = kwargs.get("response") if isinstance(kwargs.get("response"), dict) else {}
        message = response.get("assistant_message") if isinstance(response.get("assistant_message"), dict) else {}
        usage = kwargs.get("usage") if isinstance(kwargs.get("usage"), dict) else {}
        self.calls.append({"kind": "model", "start": started, "end": ended, "model": kwargs.get("model"),
                           "provider": kwargs.get("provider"), "finish_reason": kwargs.get("finish_reason"),
                           "text": content_text(message.get("content")), "tool_calls": _tool_calls(message.get("tool_calls")),
                           "usage": usage})

    def tool_call(self, kwargs: dict, now: float) -> None:
        duration = kwargs.get("duration_ms")
        started = now - (duration / 1000 if isinstance(duration, (int, float)) else 0)
        self.calls.append({"kind": "tool", "start": started, "end": now, "name": kwargs.get("tool_name") or "tool",
                           "args": kwargs.get("args"), "result": kwargs.get("result"),
                           "status": kwargs.get("status"), "error": kwargs.get("error_message")})


def turn_traces(turn: Turn, *, completed: bool, failed: bool, interrupted: bool, ended: float,
                version: str, redact: Callable[[str], str]) -> dict:
    """The OTLP JSON request body for one turn."""
    trace_id = secrets.token_hex(16)
    root = secrets.token_hex(8)
    error = failed or not completed
    spans = []
    for call in turn.calls:
        if call["kind"] == "model":
            usage = call["usage"]
            output = {key: value for key, value in (("text", call["text"]), ("tool_calls", call["tool_calls"])) if value}
            values = {
                "langfuse.observation.type": "generation",
                "gen_ai.operation.name": "chat",
                "gen_ai.system": call["provider"],
                "gen_ai.request.model": call["model"],
                "gen_ai.usage.input_tokens": usage.get("input_tokens"),
                "gen_ai.usage.output_tokens": usage.get("output_tokens"),
                "gen_ai.usage.cache_read_input_tokens": usage.get("cache_read_tokens"),
                "langfuse.observation.output": _text(output, redact) if output else None,
                "langfuse.observation.metadata.finish_reason": call["finish_reason"],
            }
            name, status = call["model"] or "model", 1
        else:
            failed_tool = call["status"] not in (None, "", "ok", "success", "completed")
            values = {
                "langfuse.observation.type": "tool",
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": call["name"],
                "langfuse.observation.input": _text(call["args"], redact),
                "langfuse.observation.output": _text(call["result"], redact),
                "langfuse.observation.level": "ERROR" if failed_tool else None,
                "langfuse.observation.status_message": _text(call["error"], redact) if call["error"] else None,
            }
            name, status = call["name"], 2 if failed_tool else 1
        spans.append({"traceId": trace_id, "spanId": secrets.token_hex(8), "parentSpanId": root, "name": name,
                      "kind": 1, "startTimeUnixNano": _nanos(call["start"]), "endTimeUnixNano": _nanos(call["end"]),
                      "attributes": _attributes(values), "status": {"code": status}})
    prompt = _text(turn.prompt, redact)
    reply = _text(turn.reply, redact) if turn.reply is not None else None
    project = turn.project.name if turn.project else None
    root_values = {
        "langfuse.observation.type": "agent",
        "langfuse.trace.name": "Hermes",
        "langfuse.session.id": turn.session_id,
        "langfuse.observation.input": prompt,
        "langfuse.observation.output": reply,
        "langfuse.trace.input": prompt,
        "langfuse.trace.output": reply,
        "langfuse.observation.level": "ERROR" if error else None,
        "langfuse.observation.status_message": ("interrupted" if interrupted else "failed" if failed
                                                else "unfinished" if not completed else None),
        "langfuse.trace.metadata.harness": HARNESS,
        "langfuse.trace.metadata.platform": turn.platform,
        "langfuse.trace.metadata.model": turn.model,
        "langfuse.trace.metadata.workspace": project,
        "langfuse.trace.metadata.plugin_version": version,
    }
    spans.insert(0, {"traceId": trace_id, "spanId": root, "name": "Hermes turn", "kind": 1,
                     "startTimeUnixNano": _nanos(turn.started), "endTimeUnixNano": _nanos(ended),
                     "attributes": _attributes(root_values), "status": {"code": 2 if error else 1}})
    return {"resourceSpans": [{
        "resource": {"attributes": _attributes({"service.name": "hermes", "egbe.plugin.version": version})},
        "scopeSpans": [{"scope": {"name": "egbe-hermes"}, "spans": spans}],
    }]}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # a credentialed request never follows a redirect
        return None


def _opener():
    return urllib.request.build_opener(_NoRedirect)


def _request(opener, url: str, *, headers: dict, data: Optional[bytes] = None, timeout: float = 30) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, b""


def send_turn(settings: dict, body: dict, public_keys: dict, *, opener=None,
              sleep: Callable[[float], None] = time.sleep) -> str:
    """Send one turn; returns a short result for `hermes egbe status`, never a secret."""
    opener = opener or _opener()
    public = settings.get("public_key") or public_keys.get(settings["key"])
    if not public:
        if not settings.get("os_key"):
            return "skipped: no telemetry public key and no Egbe key to find it"
        status, data = _request(opener, f"{OS_URL}/me/limits", timeout=15,
                                headers={"Authorization": f"Bearer {settings['os_key']}", "Accept": "application/json"})
        try:
            instance = json.loads(data)["data"]["instance_id"] if status == 200 else None
        except (ValueError, KeyError, TypeError):
            instance = None
        if not isinstance(instance, int) or isinstance(instance, bool) or instance <= 0:
            return f"skipped: the project's key lookup failed (HTTP {status})"
        public = f"pk-lf-egbe-{instance}"
        public_keys[settings["key"]] = public
    payload = json.dumps(body, ensure_ascii=False).encode()
    if len(payload) > MAX_BODY:
        return "skipped: the turn is too large"
    auth = base64.b64encode(f"{public}:{settings['key']}".encode()).decode()
    for attempt in range(3):
        status, _ = _request(opener, TRACES_URL, data=payload,
                             headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
        if 200 <= status < 300:
            return "sent"
        if status == 401 and not settings.get("public_key"):
            public_keys.pop(settings["key"], None)
        if status not in (429, 503):
            return f"failed: HTTP {status}"
        sleep(2 * (attempt + 1))
    return "failed: the gateway stayed busy"


class SessionLogger:
    """Collects each turn from Hermes's hooks and sends it when the turn ends."""

    def __init__(self, *, version: str, redact: Callable[[str], str], cwd: Callable[[], Optional[Path]],
                 enabled: Callable[[], Any], hermes_home: Callable[[], Optional[Path]],
                 record: Callable[[dict], None], send: Callable[..., str] = send_turn,
                 background: bool = True, clock: Callable[[], float] = time.time):
        self.version = version
        self.redact = redact
        self.cwd = cwd
        self.enabled = enabled
        self.hermes_home = hermes_home
        self.record = record
        self.send = send
        self.background = background
        self.clock = clock
        self.turns: dict[str, Turn] = {}
        self.public_keys: dict[str, str] = {}
        self.lock = threading.Lock()

    @staticmethod
    def _key(kwargs: dict) -> Optional[str]:
        turn = kwargs.get("turn_id") or kwargs.get("task_id")
        return str(turn) if turn else None

    def pre_llm_call(self, **kwargs) -> None:
        key = self._key(kwargs)
        if not key:
            return None
        try:
            folder = self.cwd()
        except Exception:
            folder = None
        turn = Turn(str(kwargs.get("session_id") or "unknown"), kwargs.get("user_message"),
                    str(kwargs.get("model") or ""), str(kwargs.get("platform") or ""), project_root(folder), self.clock())
        with self.lock:
            self.turns[key] = turn
            while len(self.turns) > MAX_OPEN_TURNS:
                self.turns.pop(next(iter(self.turns)))
        return None

    def _turn(self, kwargs: dict) -> Optional[Turn]:
        key = self._key(kwargs)
        return self.turns.get(key) if key else None

    def post_api_request(self, **kwargs) -> None:
        with self.lock:
            turn = self._turn(kwargs)
            if turn:
                turn.api_call(kwargs, self.clock())

    def post_tool_call(self, **kwargs) -> None:
        with self.lock:
            turn = self._turn(kwargs)
            if turn:
                turn.tool_call(kwargs, self.clock())

    def post_llm_call(self, **kwargs) -> None:
        with self.lock:
            turn = self._turn(kwargs)
            if turn:
                turn.reply = content_text(kwargs.get("assistant_response"))

    def on_session_end(self, **kwargs) -> None:
        key = self._key(kwargs)
        with self.lock:
            turn = self.turns.pop(key, None) if key else None
        if turn is None:
            return  # a CLI exit or a turn this plugin didn't see start
        ended = self.clock()
        work = lambda: self._finish(turn, ended, completed=kwargs.get("completed") is not False,
                                    failed=bool(kwargs.get("failed")), interrupted=bool(kwargs.get("interrupted")))
        if self.background:
            # A non-daemon thread: the turn's end isn't delayed, and a one-shot CLI run
            # still delivers its last turn before the process exits.
            threading.Thread(target=work, name="egbe-session-log", daemon=False).start()
        else:
            work()

    def _finish(self, turn: Turn, ended: float, **state) -> None:
        try:
            settings = logging_settings(turn.project, self.enabled(), self.hermes_home())
            if "off" in settings:
                result = f"off: {settings['off']}"
            elif not turn.prompt and not turn.calls:
                result = "skipped: no founder message in the turn"
            else:
                body = turn_traces(turn, ended=ended, version=self.version, redact=self.redact, **state)
                result = self.send(settings, body, self.public_keys)
        except Exception as error:  # logging never fails a turn
            result = f"failed: {type(error).__name__}"
        try:
            self.record({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ended)), "result": result,
                         "workspace": turn.project.name if turn.project else ""})
        except Exception:
            pass
