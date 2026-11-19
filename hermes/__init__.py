"""Egbe's native plugin for Hermes Agent.

It registers Egbe's skills (`egbe:egbe`, `egbe:egbe-setup` and the
`egbe:egbe-os-*` capabilities), records consented sessions to Egbe's telemetry
gateway (see session_log.py), and adds `hermes egbe status|connect` and the
`egbe_status` tool, and updates itself from Egbe's releases (see updater.py).
Egbe's MCP server is not declared here: a native Hermes
plugin cannot provide one, so `hermes egbe connect` adds it to the profile's
`mcp_servers` with Hermes's own OAuth sign-in (`hermes mcp add ... --auth oauth`).
"""
from __future__ import annotations

import json
import os
import time
import subprocess
import sys
from pathlib import Path

from . import session_log, updater as update

PLUGIN = "egbe"
SERVER = "egbe"
MCP_URL = f"{session_log.OS_URL}/mcp"
ROOT = Path(__file__).resolve().parent
STATE = "session_logging"
UPDATER_STATE = "updater"


def _version() -> str:
    for line in (ROOT / "plugin.yaml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return "unknown"


VERSION = _version()


def _cwd():
    try:
        from agent.runtime_cwd import resolve_agent_cwd
        return resolve_agent_cwd()
    except Exception:
        return Path(os.getcwd())


def _hermes_home():
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        return None


def _mcp_server() -> dict | None:
    """This profile's `mcp_servers.egbe` entry, without its headers."""
    try:
        from hermes_cli.config import load_config
        entry = (load_config().get("mcp_servers") or {}).get(SERVER)
    except Exception:
        return None
    if not isinstance(entry, dict):
        return None
    return {key: entry[key] for key in ("url", "auth", "enabled") if key in entry}


def _installed_version() -> str:
    """The version on disk, which an update changes before this process reloads the plugin."""
    try:
        return update.manifest_version((ROOT / "plugin.yaml").read_text(encoding="utf-8")) or VERSION
    except OSError:
        return VERSION


def status(ctx) -> dict:
    return {"version": _installed_version(), "loaded_version": VERSION, "mcp_server": _mcp_server(),
            "session_logging": ctx.state.get(STATE, default=None) or "no turn yet",
            "updates": ctx.state.get(UPDATER_STATE, default=None) or "not checked yet"}


def _hermes(*args: str) -> list[str]:
    """The argv that runs this Hermes install: its launcher, else this interpreter with Hermes's CLI."""
    try:
        from hermes_cli.chat_launch import hermes_command
        command = hermes_command(list(args))
        if Path(command[0]).is_file():
            return command
    except Exception:
        pass
    return [sys.executable, "-m", "hermes_cli.main", *args]


def connect_command(server: dict | None) -> list[str]:
    """The Hermes command that connects Egbe's MCP server with OAuth in this profile."""
    if server and server.get("url") == MCP_URL and server.get("auth") == "oauth":
        return _hermes("mcp", "login", SERVER)
    return _hermes("mcp", "add", SERVER, "--url", MCP_URL, "--auth", "oauth")


def _lock_dir() -> Path:
    try:
        from plugins.plugin_storage import plugin_data_dir
        return Path(plugin_data_dir(PLUGIN))
    except Exception:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home()) / "plugin-data" / PLUGIN


def make_updater(ctx) -> update.Updater:
    return update.Updater(
        root=ROOT,
        state_get=lambda: ctx.state.get(UPDATER_STATE, default=None),
        state_set=lambda value: ctx.state.set(UPDATER_STATE, value),
        enabled=lambda: ctx.get_config("auto_update", default=True),
        hermes=_hermes,
        lock_dir=_lock_dir,
    )


def _describe_updates(state) -> str:
    if not isinstance(state, dict):
        return str(state)
    line = state.get("result") or "-"
    if state.get("error") and state.get("error") not in line:
        line += f" ({state['error']})"
    if state.get("latest_version"):
        line += f"; latest release {state['latest_version']}"
    if state.get("last_check_at"):
        line += time.strftime("; checked %Y-%m-%dT%H:%M:%SZ", time.gmtime(state["last_check_at"]))
    return line


def _cli(ctx, updater):
    def handler(args):
        action = getattr(args, "egbe_command", None)
        if action == "update":
            state = updater.check(force=True)
            print(f"Updates: {_describe_updates(state)}")
            return 1 if str(state.get("result", "")).startswith(("error", "rollback failed")) else 0
        if action == "connect":
            server = _mcp_server()
            if server and server.get("url") not in (None, MCP_URL):
                print(f"mcp_servers.{SERVER} already points elsewhere; remove it with `hermes mcp remove {SERVER}` first.")
                return 1
            print("Connecting Egbe: sign in to Egbe in your browser and approve the connection.")
            code = subprocess.call(connect_command(server))
            if code == 0:
                print("Egbe is connected. In an open chat, send /reload-mcp or start a new session, "
                      "then ask Hermes to set up Egbe.")
            return code
        report = status(ctx)
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2))
            return 0
        server = report["mcp_server"]
        loaded = "" if report["loaded_version"] == report["version"] else f" (this process runs {report['loaded_version']})"
        print(f"Egbe plugin {report['version']}{loaded}")
        print(f"Egbe MCP server: {'configured (' + str(server.get('url')) + ')' if server else 'not configured: run `hermes egbe connect`'}")
        logged = report["session_logging"]
        print(f"Session logging: {logged['result'] + ' (' + logged['at'] + ', ' + (logged['workspace'] or '-') + ')' if isinstance(logged, dict) else logged}")
        print(f"Updates: {_describe_updates(report['updates'])}")
        return 0

    def setup(parser):
        subs = parser.add_subparsers(dest="egbe_command")
        show = subs.add_parser("status", help="Show the plugin version, Egbe's MCP server and the last session log")
        show.add_argument("--json", action="store_true", help="print JSON")
        subs.add_parser("connect", help="Add Egbe's MCP server to this profile and sign in to Egbe")
        subs.add_parser("update", help="Check for an Egbe plugin release now and install it")
        parser.set_defaults(func=handler)

    return setup, handler


STATUS_SCHEMA = {
    "name": "egbe_status",
    "description": "Report the Egbe plugin's version, whether Egbe's MCP server is configured in this Hermes "
                   "profile, the result of the last session logging run (sent, off and why, or failed) and "
                   "the plugin's last update check.",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}


def register(ctx):
    skills = ROOT / "skills"
    for folder in sorted(skills.iterdir()):
        if folder.is_dir() and (folder / "SKILL.md").is_file():
            ctx.register_skill(folder.name, folder / "SKILL.md")

    ctx.register_tool(name="egbe_status", toolset=PLUGIN, schema=STATUS_SCHEMA,
                      handler=lambda args, **kwargs: json.dumps(status(ctx)),
                      description=STATUS_SCHEMA["description"])
    updater = make_updater(ctx)
    ctx.register_hook("on_session_start", updater.maybe_check)
    setup, handler = _cli(ctx, updater)
    ctx.register_cli_command(name=PLUGIN, help="Egbe plugin status and connection", setup_fn=setup,
                             handler_fn=handler)

    logger = session_log.SessionLogger(
        version=VERSION,
        redact=lambda text: ctx.redact_text(text, force=True),
        cwd=_cwd,
        enabled=lambda: ctx.get_config("session_logging", default=True),
        hermes_home=_hermes_home,
        record=lambda result: ctx.state.set(STATE, result),
    )
    for hook in ("pre_llm_call", "post_api_request", "post_tool_call", "post_llm_call", "on_session_end"):
        ctx.register_hook(hook, getattr(logger, hook))
    return logger


if __name__ == "__main__":  # pragma: no cover - the plugin is imported by Hermes
    sys.exit("Install this folder as a Hermes plugin: hermes plugins install egbe-ai/egbe-plugins/hermes")
