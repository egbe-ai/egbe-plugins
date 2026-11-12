"""Small filesystem boundary shared by research publishers (stdlib only).

    python3 research-artifact-io.py --compact WS

compresses the provider caches of the sections whose readers accept it and
hard-links byte-identical content-addressed images; replays read both forms.
"""
from __future__ import annotations

import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
_artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parent))
from egbe_artifacts import artifact_path as _artifact_path

import argparse
import fcntl
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zlib
from contextlib import contextmanager
from pathlib import Path


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as handle:
            name = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        name = None
    finally:
        if name:
            Path(name).unlink(missing_ok=True)


def write_json(path: Path, value: dict) -> None:
    write_atomic(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context_path(section_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9_]+", section_id):
        raise ValueError("Invalid research section id")
    return Path(_artifact_path("egbe-docs/research/market/work")) / section_id / "input-context.json"


def resolve_context(workspace: Path, *, context_file=None, context=None) -> dict:
    """Read only explicitly supplied context. Measurements may need none."""
    if context_file is not None and context is not None:
        raise ValueError("Supply context text or a context file, not both")
    sources = {}
    text = "" if context is None else str(context).strip()
    if context_file is not None:
        path = Path(context_file)
        path = path if path.is_absolute() else workspace / path
        raw = path.read_bytes()
        text = raw.decode("utf-8").strip()
        if not text:
            raise ValueError("The supplied research context is empty")
        resolved = path.resolve()
        source = resolved.relative_to(workspace.resolve()).as_posix() if resolved.is_relative_to(workspace.resolve()) else str(resolved)
        sources[source] = hashlib.sha256(raw).hexdigest()
    return {"schema_version": 1, "text": text, "sources": sources}


def bind_context(workspace: Path, section_id: str, *, context_file=None, context=None) -> dict:
    """Freeze selected context before collection; never discover product files."""
    with file_lock((workspace / context_path(section_id)).with_name(".context.lock"), timeout=1):
        return _bind_context(workspace, section_id, context_file=context_file, context=context)


def _bind_context(workspace: Path, section_id: str, *, context_file=None, context=None) -> dict:
    path = workspace / context_path(section_id)
    previous = json.loads(path.read_text()) if path.exists() else None
    receipt_path = path.with_name("request.json")
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        binding = receipt.get("research_context")
        provenance_path = path.with_name("input-provenance.json")
        if binding is None and provenance_path.exists():
            binding = json.loads(provenance_path.read_text()).get("research_context")
        if previous is None or binding != context_binding(workspace, section_id):
            raise ValueError("Saved research input binding is missing or damaged; preserve evidence and inspect before resuming")
    if previous is not None and context_file is None and context is None:
        value = previous  # continuation/clone uses the recorded input, not a fresh search
    else:
        value = resolve_context(workspace, context_file=context_file, context=context)
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("text"), str) or not isinstance(value.get("sources"), dict):
        raise ValueError("Invalid saved research context; retain it and inspect before continuing")
    if previous is not None and previous != value:
        raise ValueError("Research context changed; retain this study and use a new research ID for new work")
    if previous is None:
        write_json(path, value)
    return value


def context_binding(workspace: Path, section_id: str) -> dict:
    relative = context_path(section_id)
    return {"path": relative.as_posix(), "sha256": sha256(workspace / relative)}


def context_text(workspace: Path, section_id: str) -> str:
    value = json.loads((workspace / context_path(section_id)).read_text())
    if value.get("schema_version") != 1 or not isinstance(value.get("text"), str):
        raise ValueError("Invalid research context snapshot")
    return value["text"]


def verify_context(workspace: Path, section_id: str, binding) -> dict:
    if binding != context_binding(workspace, section_id):
        raise ValueError("Research input snapshot does not match its receipt")
    value = json.loads((workspace / context_path(section_id)).read_text())
    if value.get("schema_version") != 1 or not isinstance(value.get("text"), str) or not isinstance(value.get("sources"), dict):
        raise ValueError("Invalid research context snapshot")
    for source, digest in value["sources"].items():
        path = Path(source)
        path = path if path.is_absolute() else workspace / path
        if path.is_file() and sha256(path) != digest:
            raise ValueError("Declared research input changed; saved evidence remains intact, review its applicability")
    return value


@contextmanager
def file_lock(path: Path, timeout: float = 60):
    """A bounded process lock; callers must not nest the same lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Research publication busy: {path}; retry without recollecting data")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def publication_lock(report: Path):
    return file_lock(report.parent / ".local" / "publication.lock")


@contextmanager
def section_attempt(workspace: Path, section_id: str, *, context_file=None):
    """Invalidate old completion before work; the runner owns successful publication."""
    root = workspace / _artifact_path("egbe-docs/research/market/work") / section_id
    # A competing invocation must not invalidate the active runner's receipt.
    with file_lock(root / ".run.lock", timeout=1):
        bind_context(workspace, section_id, context_file=context_file)
        state = {"schema_version": 1, "section_id": section_id, "status": "pending", "error": None,
                 "research_context": context_binding(workspace, section_id)}
        write_json(root / "request.json", state)
        try:
            yield
        except Exception:
            # Keep cached responses/results for recovery. Never persist upstream
            # exception text, which may contain request details or credentials.
            write_json(root / "request.json", {
                **state, "status": "failed",
                "error": "Current attempt failed; retained files do not prove completion. Retry using the cache.",
            })
            raise


# Provider caches: an entry is addressed by its logical `<digest>.json` path
# and stored as `<digest>.json.gz` (an older plain file is read as well).
COMPRESSED_CACHE_SECTIONS = ("channel_footprint", "creative_patterns", "competitor_set")
_DIGEST_JSON = re.compile(r"[0-9a-f]{64}\.json")


def cache_entry_path(path: Path) -> Path | None:
    packed = path.with_name(path.name + ".gz")
    return path if path.is_file() else packed if packed.is_file() else None


def read_cache_entry(path: Path):
    """The entry, or None when absent; corrupt bytes raise (OSError/ValueError/EOFError)."""
    actual = cache_entry_path(path)
    if actual is None:
        return None
    data = actual.read_bytes()
    try:
        return json.loads(gzip.decompress(data) if actual != path else data)
    except zlib.error as exc:
        raise gzip.BadGzipFile("Invalid compressed cache entry") from exc


def write_cache_entry(path: Path, entry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    packed = path.with_name(path.name + ".gz")
    tmp = packed.with_name(packed.name + ".tmp")
    tmp.write_bytes(gzip.compress(json.dumps(entry).encode("utf-8"), mtime=0))
    tmp.replace(packed)
    path.unlink(missing_ok=True)


def drop_cache_entry(path: Path) -> None:
    path.unlink(missing_ok=True)
    path.with_name(path.name + ".gz").unlink(missing_ok=True)


def cache_entries(directory: Path) -> list[Path]:
    """Logical entry paths under `directory`, in their former sorted order."""
    found = {p for p in directory.rglob("*.json")} | {p.with_name(p.name[:-3]) for p in directory.rglob("*.json.gz")}
    return sorted(found)


def link_or_copy(source: Path, target: Path) -> None:
    """Exact bytes stored once: a hard link on the same filesystem, a copy
    otherwise; the target is replaced atomically."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and os.path.samefile(source, target):
        return
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    os.close(fd)
    os.unlink(tmp)
    try:
        try:
            os.link(source, tmp)
        except OSError:
            shutil.copyfile(source, tmp)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def compact(workspace: Path) -> dict:
    """Compress cache entries in place (same JSON, gzip) and link identical
    images named by their SHA-256; nothing is re-fetched or re-classified."""
    runtime, report = workspace / _artifact_path("egbe-docs/research/market/work"), {"entries": 0, "json_bytes_saved": 0, "linked_images": 0, "image_bytes_saved": 0}
    for section in COMPRESSED_CACHE_SECTIONS:
        for path in sorted((runtime / section / "cache").rglob("*.json")):
            if not _DIGEST_JSON.fullmatch(path.name) or "video" in path.relative_to(runtime).parts:
                continue
            before = path.stat().st_size
            write_cache_entry(path, json.loads(path.read_bytes()))
            report["entries"] += 1
            report["json_bytes_saved"] += before - path.with_name(path.name + ".gz").stat().st_size
    first: dict[str, Path] = {}
    roots = [runtime / section / "cache" for section in COMPRESSED_CACHE_SECTIONS] + [workspace / _artifact_path("egbe-docs/research/market/assets")]
    for root in roots:
        for path in sorted(root.rglob("*")) if root.is_dir() else []:
            stem = path.name.split(".", 1)[0]
            if not path.is_file() or path.is_symlink() or not re.fullmatch(r"[0-9a-f]{64}", stem) or path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() != stem:
                continue
            original = first.setdefault(stem, path)
            if original != path and not os.path.samefile(original, path):
                report["linked_images"] += 1
                report["image_bytes_saved"] += path.stat().st_size
                link_or_copy(original, path)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--compact", type=Path, metavar="WS", required=True, help="Research workspace to compact")
    args = parser.parse_args()
    print(json.dumps(compact(args.compact.resolve()), indent=2))
    sys.exit(0)
