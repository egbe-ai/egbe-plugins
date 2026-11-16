"""Private, locked, atomic local records; never persist credentials."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .protocol import canonical, change_id

MAX_ACTIVE = 100
MAX_STORAGE = 64 * 1024 * 1024
MAX_RECORD = 5 * 1024 * 1024
ACTIVE = {"captured", "pending", "held"}


def regular(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("Transport and exclusion files must be regular files")


def atomic_write(path, value):
    regular(path)
    raw = canonical(value)
    descriptor, temp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.path = self.root / "egbe-docs/.local/playbook-changes"

    def require_inspectable_checkout(self):
        markers = (folder / ".git" for folder in (self.root, *self.root.parents))
        if any(path.exists() or path.is_symlink() for path in markers) or os.environ.get("GIT_DIR") or os.environ.get("GIT_WORK_TREE"):
            raise ValueError("Existing Git checkout cannot be inspected; resolve Git access before recording")

    def prepare(self):
        for name, rule in ((".gitignore", "/egbe-docs/.local/"),
                           (".dockerignore", "/egbe-docs/")):
            path = self.root / name
            regular(path)
            text = path.read_text(encoding="utf-8") if path.exists() else ""
            # Last match wins; append after any existing negations.
            if not text.splitlines() or text.splitlines()[-1] != rule:
                with path.open("a", encoding="utf-8") as stream:
                    stream.write(("\n" if text and not text.endswith("\n") else "") + rule + "\n")
        # An ignore rule cannot make an already tracked file private.
        try:
            tracked = subprocess.run(
                ["git", "-C", str(self.root), "ls-files", "--", "egbe-docs/.local"],
                capture_output=True, timeout=5, check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.require_inspectable_checkout()
            tracked = None
        if tracked and tracked.returncode != 0:
            self.require_inspectable_checkout()
        if tracked and tracked.returncode == 0 and tracked.stdout.strip():
            raise ValueError("Private egbe-docs/.local files are tracked by Git; resolve before capture")
        current = self.root
        for part in self.path.relative_to(self.root).parts:
            current /= part
            if current.is_symlink() or (current.exists() and not current.is_dir()):
                raise ValueError("Transport directories must not be symlinks or files")
            current.mkdir(mode=0o700, exist_ok=True)
        # A deeper egbe-docs/.gitignore can negate the root exclusion. Keep the
        # transport's own rule closest to its files, and verify each real write.
        exclusion = self.path / ".gitignore"
        regular(exclusion)
        text = exclusion.read_text(encoding="utf-8") if exclusion.exists() else ""
        if not text.splitlines() or text.splitlines()[-1] != "*":
            with exclusion.open("a", encoding="utf-8") as stream:
                stream.write(("\n" if text and not text.endswith("\n") else "") + "*\n")

    def verify_ignored(self, path):
        try:
            repository = subprocess.run(["git", "-C", str(self.root), "rev-parse", "--is-inside-work-tree"],
                                        capture_output=True, timeout=5, check=False)
            if repository.returncode != 0:
                self.require_inspectable_checkout()
                return  # No repository yet; the local ignore rule applies after init.
            ignored = subprocess.run(["git", "-C", str(self.root), "check-ignore", "--quiet", "--",
                                      str(path.relative_to(self.root))],
                                     capture_output=True, timeout=5, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.require_inspectable_checkout()
            return
        if ignored.returncode != 0:
            raise ValueError("Private transport path is not Git-ignored; resolve exclusions before recording")

    @contextmanager
    def locked(self):
        self.prepare()
        lock = self.path / ".lock"
        regular(lock)
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "r+b") as stream:
            if os.name == "nt":
                import msvcrt
                stream.write(b"0")
                stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield self
            finally:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def load(self, identity):
        path = self.path / (change_id(identity) + ".json")
        regular(path)
        if path.stat().st_size > MAX_RECORD:
            raise ValueError("A local transport record exceeds its size limit")
        try:
            value = json.loads(path.read_bytes())
        except (ValueError, UnicodeDecodeError):
            raise ValueError("A local transport record is invalid; preserve it for inspection") from None
        if (not isinstance(value, dict) or value.get("version") != 1 or value.get("change_id") != identity
                or value.get("status") not in ACTIVE | {"delivered", "no_change"}
                or type(value.get("expected_project_id")) is not int or value["expected_project_id"] <= 0
                or not isinstance(value.get("origin"), str) or not isinstance(value.get("created_at"), str)
                or type(value.get("attempts")) is not int or value["attempts"] < 0
                or not isinstance(value.get("next_retry_at"), (int, float))):
            raise ValueError("A local transport record has an unknown format or identity")
        if value["status"] == "captured" and not isinstance(value.get("files"), list):
            raise ValueError("Local capture contents are invalid; preserve the file for inspection")
        if value["status"] in {"pending", "held"} and (not isinstance(value.get("packet"), dict)
                                                      or not isinstance(value.get("content_hash"), str)):
            raise ValueError("Local packet contents are invalid; preserve the file for inspection")
        return value

    def records(self):
        return [self.load(path.stem) for path in sorted(self.path.glob("*.json"))]

    def save(self, value, *, new=False):
        path = self.path / (change_id(value["change_id"]) + ".json")
        self.verify_ignored(path)
        if new and path.exists():
            raise ValueError("Refusing to overwrite an existing capture")
        raw = canonical(value)
        if len(raw) > MAX_RECORD:
            raise ValueError("Local capture exceeds its size limit; existing data was preserved")
        size = 0
        for item in self.path.iterdir():
            regular(item)
            size += item.stat().st_size
        if size - (path.stat().st_size if path.exists() else 0) + len(raw) > MAX_STORAGE:
            raise ValueError("Local journal is full; preserve pending records and inspect storage")
        if new and sum(record["status"] in ACTIVE for record in self.records()) >= MAX_ACTIVE:
            raise ValueError("100 unfinished records already exist; resolve delivery before new capture")
        atomic_write(path, value)

    def discard(self, identity):
        value = self.load(identity)
        if value["status"] != "captured":
            raise ValueError("Only an unfinished, unfinalized capture can be explicitly discarded")
        (self.path / (identity + ".json")).unlink()
