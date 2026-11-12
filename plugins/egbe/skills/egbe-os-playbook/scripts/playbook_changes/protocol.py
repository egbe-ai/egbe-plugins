"""Wire representation and path/content checks, without transport or persistence."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from uuid import UUID

MAX_FILES = 16
MAX_TEXT = 256 * 1024
MAX_PACKET = 2 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def change_id(value):
    try:
        normalized = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid change ID") from None
    if normalized != value:
        raise ValueError("Use the canonical change ID returned by capture")
    return normalized


def valid_path(value):
    parts = value.split("/")
    if (len(parts) < 3 or parts[:2] != ["egbe-docs", "playbooks"]
            or any(part in {"", ".", ".."} or part.startswith(".") for part in parts)
            or any(char in value for char in "\\%?#:\x00")
            or any(ord(char) < 32 or ord(char) == 127 for char in value) or len(value) > 512
            or PurePosixPath(value).suffix != ".md"):
        raise ValueError("Choose relative Markdown files under egbe-docs/playbooks")
    return value


def method_paths(root, paths):
    if not 1 <= len(paths) <= MAX_FILES:
        raise ValueError("Choose between 1 and 16 method files")
    seen_names, seen_files = set(), set()
    result = []
    for name in paths:
        valid_path(name)
        target = root / name
        current = root
        for part in Path(name).parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("Method files and their parent directories must not be symlinks")
        if target.exists() and not target.is_file():
            raise ValueError("A selected method path is not a regular file")
        resolved = target.resolve()
        if not resolved.is_relative_to(root / "egbe-docs/playbooks") or resolved in seen_names:
            raise ValueError("Duplicate or escaping method path")
        seen_names.add(resolved)
        if target.exists():
            stat = target.stat()
            inode = (stat.st_dev, stat.st_ino)
            if inode in seen_files or stat.st_nlink != 1:
                raise ValueError("Method aliases and hard links are not supported")
            seen_files.add(inode)
        result.append((name, target))
    return result


def open_method(root, name):
    """Walk from an opened workspace directory, rejecting symlink swaps too."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    directory = os.open(root, flags | getattr(os, "O_DIRECTORY", 0))
    try:
        parts = Path(name).parts
        for part in parts[:-1]:
            child = os.open(part, flags | getattr(os, "O_DIRECTORY", 0), dir_fd=directory)
            os.close(directory)
            directory = child
        return os.open(parts[-1], flags | getattr(os, "O_NONBLOCK", 0), dir_fd=directory)
    finally:
        os.close(directory)


def snapshot(root, name, *, before=False, unknown=False):
    if unknown:
        return {"state": "unknown", "text": None, "captured_at": now()}
    try:
        descriptor = open_method(root, name)
    except FileNotFoundError:
        return {"state": "absent" if before else "deleted", "text": None, "captured_at": now()}
    # Decode bytes explicitly: text-mode reads would normalize CRLF.
    with os.fdopen(descriptor, "rb") as stream:
        initial = os.fstat(stream.fileno())
        if not stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1:
            raise ValueError("Method snapshots require regular files without hard links")
        raw = stream.read(MAX_TEXT + 1)
        final = os.fstat(stream.fileno())
        if (initial.st_size, initial.st_mtime_ns) != (final.st_size, final.st_mtime_ns):
            raise ValueError("Method file changed during capture; retry after editing stops")
    if len(raw) > MAX_TEXT:
        raise ValueError("A method snapshot exceeds 256 KiB")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Method files must be UTF-8") from None
    if "\x00" in text:
        raise ValueError("Method files must not contain NUL")
    return {"state": "captured", "text": text, "captured_at": now()}


def metadata(value, field, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{field} must contain 1–{maximum} characters without NUL")
    return value


def receipt(value, expected_hash):
    if not isinstance(value, dict) or value.get("content_hash") != expected_hash:
        raise ValueError("Delivery returned an unverified receipt")
    change_id(value.get("id"))
    stamp = datetime.fromisoformat(value.get("received_at", "").replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Receipt time must include timezone")
    return {key: value[key] for key in ("id", "content_hash", "received_at")}
