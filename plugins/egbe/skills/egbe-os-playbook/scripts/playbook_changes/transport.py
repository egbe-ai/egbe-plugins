"""Origin-pinned HTTP with no redirects or provider/error-body disclosure."""
import json
import os
import re
import shlex
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_RESPONSE = 128 * 1024


class DeliveryError(Exception):
    def __init__(self, code, *, transient=False, retry_after=0):
        self.code = code
        self.transient = transient
        self.retry_after = retry_after
        super().__init__(code)


def origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in {"https", "http"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}
            or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"})):
        raise ValueError("OS_URL must be an HTTPS origin (HTTP is allowed only for loopback tests)")
    if any(ord(char) < 33 for char in value):
        raise ValueError("OS_URL contains invalid characters")
    port = parsed.port
    host = "[" + parsed.hostname + "]" if ":" in parsed.hostname else parsed.hostname
    return parsed.scheme + "://" + host + (f":{port}" if port and port != {"http": 80, "https": 443}[parsed.scheme] else "")


def connection(root):
    path = root / ".env.local"
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("Connection settings must be a regular project-local .env.local file")
    if path.exists():
        if path.stat().st_size > 1024 * 1024:
            raise ValueError("Connection settings file is unexpectedly large")
        values = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"(?:export\s+)?(OS_URL|OS_API_KEY)\s*=(.*)$", line.strip())
            if match:
                try:
                    pieces = shlex.split(match[2], comments=True)
                except ValueError:
                    raise ValueError("Invalid quoting in connection settings") from None
                if len(pieces) != 1:
                    raise ValueError("Connection settings must be literal values")
                values[match[1]] = pieces[0]
    else:
        values = {name: os.environ.get(name, "") for name in ("OS_URL", "OS_API_KEY")}
    if not values.get("OS_URL") or not values.get("OS_API_KEY"):
        raise ValueError("Set OS_URL and OS_API_KEY in this project's .env.local first")
    key = values["OS_API_KEY"]
    if len(key) > 4096 or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise ValueError("Invalid project credential format")
    return origin(values["OS_URL"]), key


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(base, key, path, *, packet=None, timeout=10):
    from .protocol import canonical
    req = Request(base + path, data=canonical(packet) if packet is not None else None,
                  headers={"Authorization": "Bearer " + key, "Accept": "application/json",
                           "Content-Type": "application/json", "User-Agent": "egbe-playbook-changes/1"},
                  method="POST" if packet is not None else "GET")
    try:
        deadline = time.monotonic() + timeout
        with build_opener(NoRedirects()).open(req, timeout=timeout) as response:
            raw = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DeliveryError("network_timeout", transient=True)
                # urllib's timeout is per socket operation. Tighten it to the
                # remaining request budget so a slow stream cannot prolong it.
                sock = getattr(getattr(response.fp, "raw", None), "_sock", None)
                if sock is not None:
                    sock.settimeout(remaining)
                chunk = response.read1(min(8192, MAX_RESPONSE + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE:
                    raise DeliveryError("unverified_response", transient=True)
            value = json.loads(raw)
    except HTTPError as error:
        retry = error.headers.get("Retry-After", "0")
        retry = min(int(retry), 86400) if retry.isdigit() else 0
        error.close()
        raise DeliveryError("http_" + str(error.code), transient=(error.code == 429 or 500 <= error.code < 600 and error.code != 507), retry_after=retry) from None
    except (URLError, TimeoutError, ConnectionError, OSError):
        raise DeliveryError("network_unavailable", transient=True) from None
    except (ValueError, UnicodeDecodeError):
        raise DeliveryError("unverified_response", transient=True) from None
    if not isinstance(value, dict) or value.get("code") != 200 or not isinstance(value.get("data"), dict):
        raise DeliveryError("unverified_response", transient=True)
    return value["data"]


def identity(base, key, *, timeout=10):
    project = request(base, key, "/me/limits", timeout=timeout).get("instance_id")
    if type(project) is not int or project <= 0:
        raise DeliveryError("unverified_project", transient=True)
    return project
