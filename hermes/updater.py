"""Automatic updates of the Egbe plugin for Hermes.

Hermes's own unattended update (`plugins.auto_apply`) never applies a Git update
whose install scan says "caution", which this plugin's bundled skill scripts
always do, and it is off by default. So the plugin updates itself the way
Egbe's OpenClaw plugin does, through Hermes's own installer:

1. At most every six hours, on a background thread started by a new session
   (or now with `hermes egbe update`), read `hermes-release.json` from
   egbe-ai/egbe-plugins: the version, the commit that publishes it, the SHA-256
   of each plugin file and the declared tools and hooks.
2. Skip it unless it is newer than the installed version, not a version that
   failed before, and this install came from egbe-ai/egbe-plugins. A release
   that declares other tools or hooks waits for the founder's
   `hermes plugins update egbe`.
3. Before installing, download that commit's archive and check that the
   plugin's files are exactly the release's (the version included).
4. Install exactly that commit with `hermes plugins install <source> --ref
   <commit> --force --enable`, so Hermes's provenance, update lock and scan
   apply; then check the installed files against the release again.
5. If the install or the check fails, reinstall the previous commit the same
   way and remember the version as bad.

The `auto_update` setting turns it off. Nothing runs at import time, no turn
waits for it, and only this plugin's own install is touched.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Optional

REPOSITORY = "egbe-ai/egbe-plugins"
SUBDIR = "hermes"
RELEASE_FILE = "hermes-release.json"
RELEASE_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/main/{RELEASE_FILE}"
ARCHIVE_URL = f"https://codeload.github.com/{REPOSITORY}/tar.gz/{{commit}}"
# The source Hermes records for `hermes plugins install egbe-ai/egbe-plugins/hermes`.
OFFICIAL_SOURCE = f"https://github.com/{REPOSITORY}.git#{SUBDIR}"
CHECK_INTERVAL = 6 * 60 * 60
MAX_RELEASE_BYTES = 1024 * 1024
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
INSTALL_TIMEOUT = 15 * 60
LOCK_STALE = 30 * 60
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IGNORED = "__pycache__"


def version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def declared(manifest: str) -> dict[str, list[str]]:
    """The tools and hooks a plugin.yaml declares, in order."""
    found: dict[str, list[str]] = {"tools": [], "hooks": []}
    section = None
    for line in manifest.splitlines():
        if line.startswith("provides_tools:"):
            section = "tools"
        elif line.startswith("provides_hooks:"):
            section = "hooks"
        elif section and line.startswith("  - "):
            found[section].append(line[4:].strip())
        elif line and not line.startswith(" "):
            section = None
    return found


def manifest_version(manifest: str) -> Optional[str]:
    match = re.search(r"^version: (\S+)$", manifest, re.M)
    return match[1] if match else None


def valid_release(release: Any) -> bool:
    if not isinstance(release, dict):
        return False
    files, capabilities = release.get("files"), release.get("capabilities")
    return (isinstance(release.get("version"), str) and bool(SEMVER.match(release["version"]))
            and isinstance(release.get("commit"), str) and bool(COMMIT.match(release["commit"]))
            and isinstance(files, dict) and "plugin.yaml" in files and "__init__.py" in files
            and all(isinstance(name, str) and _safe_path(name) and isinstance(digest, str) and SHA256.match(digest)
                    for name, digest in files.items())
            and isinstance(capabilities, dict)
            and all(isinstance(capabilities.get(key), list) for key in ("tools", "hooks")))


def _safe_path(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and IGNORED not in path.parts


def tree_hashes(root: Path) -> dict[str, str]:
    """SHA-256 of every file under `root`, without Python's bytecode caches."""
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file() and IGNORED not in path.relative_to(root).parts}


def archive_hashes(data: bytes) -> dict[str, str]:
    """SHA-256 of each file under `hermes/` in a GitHub commit archive (`<repo>-<commit>/hermes/...`)."""
    hashes = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive:
            parts = PurePosixPath(member.name).parts
            if len(parts) < 3 or parts[1] != SUBDIR or not member.isfile():
                continue
            handle = archive.extractfile(member)
            hashes["/".join(parts[2:])] = hashlib.sha256(handle.read()).hexdigest()
    return hashes


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch(url: str, limit: int, timeout: float = 30) -> bytes:
    """GET `url` over HTTPS without following redirects, at most `limit` bytes."""
    if not url.startswith("https://"):
        raise ValueError("updates are fetched over HTTPS only")
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(urllib.request.Request(url, headers={"Accept": "*/*"}), timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}")
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("response too large")
    return data


class Updater:
    def __init__(self, *, root: Path, state_get: Callable[[], dict], state_set: Callable[[dict], None],
                 enabled: Callable[[], Any], hermes: Callable[..., list[str]], lock_dir: Callable[[], Path],
                 fetch_release: Optional[Callable[[], bytes]] = None,
                 fetch_archive: Optional[Callable[[str], bytes]] = None,
                 run: Optional[Callable[[list[str]], int]] = None,
                 allowed_sources: tuple[str, ...] = (OFFICIAL_SOURCE,), clock: Callable[[], float] = time.time,
                 background: bool = True):
        self.root = root
        self.state_get = state_get
        self.state_set = state_set
        self.enabled = enabled
        self.hermes = hermes
        self.lock_dir = lock_dir
        self.fetch_release = fetch_release or (lambda: fetch(RELEASE_URL, MAX_RELEASE_BYTES))
        self.fetch_archive = fetch_archive or (lambda commit: fetch(ARCHIVE_URL.format(commit=commit),
                                                                    MAX_ARCHIVE_BYTES, timeout=120))
        self.run = run or self._run
        self.allowed_sources = allowed_sources
        self.clock = clock
        self.background = background
        self._started = threading.Lock()

    # -- state ----------------------------------------------------------------------------------
    def state(self) -> dict:
        try:
            value = self.state_get()
        except Exception:
            value = None
        return value if isinstance(value, dict) else {}

    def _save(self, **changes) -> dict:
        state = {**self.state(), **changes}
        try:
            self.state_set(state)
        except Exception:
            pass
        return state

    def installed(self) -> tuple[Optional[str], Optional[dict]]:
        """The installed version on disk and this plugin's Hermes install record."""
        version = manifest_version((self.root / "plugin.yaml").read_text(encoding="utf-8"))
        try:
            rows = json.loads((self.root.parent / ".install-metadata.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rows = {}
        row = rows.get(self.root.name) if isinstance(rows, dict) else None
        return version, row if isinstance(row, dict) else None

    # -- triggers -------------------------------------------------------------------------------
    def maybe_check(self, **_kwargs) -> None:
        """The `on_session_start` hook: start a due check in the background, never wait for it."""
        if self.enabled() is False:
            return
        if self.clock() - float(self.state().get("last_check_at") or 0) < CHECK_INTERVAL:
            return
        if not self._started.acquire(blocking=False):
            return
        def work():
            try:
                self.check()
            finally:
                self._started.release()
        if self.background:
            threading.Thread(target=work, name="egbe-updater", daemon=True).start()
        else:
            work()

    def check(self, force: bool = False) -> dict:
        """Check for a release and apply it; returns the updater's state."""
        if self.enabled() is False and not force:
            return self._save(result="off: the auto_update setting is false")
        lock = self._lock()
        if lock is None:
            return self._save(result="busy: another Hermes process is updating the plugin")
        try:
            self._save(last_check_at=self.clock())
            return self._check()
        except Exception as error:  # an update problem never reaches a turn
            return self._save(result="error", error=f"{type(error).__name__}: {error}"[:300])
        finally:
            self._unlock(lock)

    # -- the update -----------------------------------------------------------------------------
    def _check(self) -> dict:
        version, row = self.installed()
        release = json.loads(self.fetch_release())
        if not valid_release(release):
            return self._save(result="error", error="the release file is malformed")
        self._save(latest_version=release["version"])
        if version is None or version_tuple(release["version"]) <= version_tuple(version):
            return self._save(result="up to date", error=None)
        if release["version"] in self.state().get("bad_versions", []):
            return self._save(result=f"skipped {release['version']}: it failed before")
        source = (row or {}).get("source")
        if source not in self.allowed_sources or not isinstance((row or {}).get("revision"), str):
            return self._save(result="manual: this install is not from egbe-ai/egbe-plugins; "
                                     "update it with `hermes plugins update egbe`")
        current = declared((self.root / "plugin.yaml").read_text(encoding="utf-8"))
        if {key: release["capabilities"][key] for key in ("tools", "hooks")} != current:
            return self._save(result=f"needs consent: {release['version']} declares other tools or hooks; "
                                     "run `hermes plugins update egbe`")
        # Verify the commit's files before Hermes installs anything from it.
        published = archive_hashes(self.fetch_archive(release["commit"]))
        if published != release["files"]:
            return self._bad(release, "the commit's files differ from the release")
        if self.run(self._install(source, release["commit"])) != 0:
            return self._rollback(release, row, "Hermes could not install the release")
        installed_version, installed_row = self.installed()
        if (tree_hashes(self.root) != release["files"] or installed_version != release["version"]
                or (installed_row or {}).get("revision") != release["commit"]):
            return self._rollback(release, row, "the installed files differ from the release")
        return self._save(result=f"updated {version} -> {release['version']}; loads in new sessions",
                          error=None, updated_at=self.clock(), previous_commit=row["revision"])

    def _install(self, source: str, commit: str) -> list[str]:
        return self.hermes("plugins", "install", source, "--ref", commit, "--force", "--enable")

    def _bad(self, release: dict, why: str) -> dict:
        bad = [*self.state().get("bad_versions", []), release["version"]][-10:]
        return self._save(result=f"rejected {release['version']}: {why}", error=why, bad_versions=bad)

    def _rollback(self, release: dict, row: dict, why: str) -> dict:
        self._bad(release, why)
        previous = row["revision"]
        version, now = self.installed()
        if (now or {}).get("revision") == previous and version != release["version"]:
            return self._save(result=f"rejected {release['version']}: {why}; the installed version is unchanged")
        code = self.run(self._install(row["source"], previous))
        _, after = self.installed()
        if code != 0 or (after or {}).get("revision") != previous:
            return self._save(result=f"rollback failed after {why}; reinstall with "
                                     f"`hermes plugins install {row['source']} --ref {previous} --force`",
                              error=why)
        return self._save(result=f"rolled back {release['version']}: {why}")

    def _run(self, command: list[str]) -> int:
        try:
            return subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, timeout=INSTALL_TIMEOUT).returncode
        except (OSError, subprocess.TimeoutExpired):
            return 1

    # -- one updater per profile ----------------------------------------------------------------
    def _lock(self) -> Optional[Path]:
        folder = self.lock_dir()
        folder.mkdir(parents=True, exist_ok=True)
        lock = folder / "update.lock"
        for _ in range(2):
            try:
                handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.write(handle, str(os.getpid()).encode())
                os.close(handle)
                return lock
            except FileExistsError:
                try:
                    if time.time() - lock.stat().st_mtime < LOCK_STALE:
                        return None
                    lock.unlink()
                except OSError:
                    return None
        return None

    @staticmethod
    def _unlock(lock: Path) -> None:
        try:
            lock.unlink()
        except OSError:
            pass
