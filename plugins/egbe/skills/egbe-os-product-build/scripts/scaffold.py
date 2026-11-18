#!/usr/bin/env python3
"""Preview or install shipped product foundations without network operations."""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys


class Conflict(ValueError):
    pass


@dataclass
class Edit:
    path: Path
    before: bytes | None
    after: bytes


def skill(root: Path, name: str) -> Path:
    """Work in both a source checkout and the complete installed catalog."""
    for candidate in (root / ("egbe-os-" + name), root / name):
        if (candidate / "SKILL.md").is_file():
            return candidate
    raise Conflict(f"Missing skill bundle: egbe-os-{name}; refresh the complete catalog")


def check_path(root: Path, path: Path):
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise Conflict(f"Symlink destination: {candidate}")
        if candidate == root:
            break
    if path.exists() and not path.is_file():
        raise Conflict(f"Expected a regular file: {path}")
    for parent in path.parents:
        if parent == root.parent:
            break
        if parent.exists() and not parent.is_dir():
            raise Conflict(f"Expected a directory: {parent}")


def tree(source: Path):
    if not source.is_dir():
        raise Conflict(f"Missing shipped foundation: {source}")
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in {"node_modules", ".next", "__pycache__"} for part in relative.parts):
            continue
        if path.is_symlink():
            raise Conflict(f"Symlink in foundation: {path}")
        if path.is_file() and path.name not in {"package.fragment.json", "AGENTS.append.md"}:
            yield relative, path.read_bytes()


def append_marked(existing: str, marker: str, text: str, *, ignore_file=False) -> str:
    start, end = (f"# {marker}", f"# /{marker}") if ignore_file else (f"<!-- {marker} -->", f"<!-- /{marker} -->")
    block = start + "\n" + text.rstrip() + "\n" + end
    if start in existing or end in existing:
        if existing.count(start) != 1 or existing.count(end) != 1 or block not in existing:
            raise Conflict(f"Existing foundation guidance differs: {marker}; review it manually")
        return existing
    return existing.rstrip() + ("\n\n" if existing.strip() else "") + block + "\n"


# The command-line options by name, for callers that select foundations without flags.
FOUNDATIONS = {"nextjs": "base", "auth-db": "auth_db", "accounts": "accounts", "subscriptions": "subscriptions"}
MERGED = {Path("package.json"), Path("AGENTS.md"), Path(".gitignore")}


LOCKFILE = Path("package-lock.json")
LOCKED_SECTIONS = ("dependencies", "devDependencies")


def shipped_lockfiles(skills):
    """The starter's lockfile and the prebuilt ones for its foundation combinations."""
    assets = skill(skills, "design-landing-page") / "assets"
    paths = [assets / "scaffold/package-lock.json", *sorted((assets / "lockfiles").glob("*/package-lock.json"))]
    return [path.read_bytes() for path in paths if path.is_file()]


def lock_lists(lock: bytes, package: dict) -> bool:
    """Whether a lockfile's root lists exactly the package's dependencies, as `npm ci` requires."""
    try:
        root = json.loads(lock).get("packages", {}).get("", {})
    except (ValueError, AttributeError):
        return False
    return all((package.get(section) or {}) == (root.get(section) or {}) for section in LOCKED_SECTIONS)


def _lock_shape(lock: bytes):
    """A lockfile without the root package's own name and version."""
    try:
        data = json.loads(lock)
        root = dict(data.get("packages", {}).get("", {}))
    except (ValueError, AttributeError):
        return None
    for field in ("name", "version"):
        data.pop(field, None)
        root.pop(field, None)
    return {**data, "packages": {**data.get("packages", {}), "": root}}


def is_shipped_lockfile(lock: bytes, skills) -> bool:
    """An unedited shipped lockfile, whatever the root package's name and version."""
    return _lock_shape(lock) in [_lock_shape(shipped) for shipped in shipped_lockfiles(skills)]


def prebuilt_lockfile(package: dict, skills):
    """The shipped lockfile listing the package's dependencies, carrying its name and version."""
    shipped = shipped_lockfiles(skills)
    for lock in shipped:
        if lock_lists(lock, package):
            data = json.loads(lock)
            if all(data.get(field) == package.get(field) for field in ("name", "version")):
                return lock
            for record in (data, data["packages"][""]):
                for field in ("name", "version"):
                    if field in package:
                        record[field] = package[field]
                    else:
                        record.pop(field, None)
            return (json.dumps(data, indent=2) + "\n").encode()
    return None


def compose(read, *, base=False, auth_db=False, accounts=False, subscriptions=False, skills=None):
    """Plan the selected foundations against any destination.

    `read(relative)` returns the destination's bytes at a relative path, or None
    when absent, and raises Conflict for a path that cannot hold a file. Returns
    `(relative, before, after)` for every file the installation changes.
    """
    skills = skills or Path(__file__).resolve().parents[2]
    if not (base or auth_db or accounts or subscriptions):
        raise Conflict("Select --nextjs, --auth-db, --accounts or --subscriptions explicitly")
    files = {}

    def add(source, prefix=Path()):
        for relative, content in tree(source):
            relative = prefix / relative
            if relative in files and files[relative] != content:
                raise Conflict(f"Overlapping foundation files: {relative}")
            files[relative] = content

    if base:
        add(skill(skills, "design-landing-page") / "assets/scaffold")
    existing_package = read(Path("package.json"))
    package_bytes = existing_package if existing_package is not None else files.get(Path("package.json"))
    if package_bytes is None:
        raise Conflict("A product package.json is required; use --nextjs only for a new app")
    package = json.loads(package_bytes)
    if not isinstance(package, dict):
        raise Conflict("package.json must contain an object")
    agents = (read(Path("AGENTS.md")) or b"").decode()
    if base:
        starter_guidance = files[Path("AGENTS.md")].decode()
        agents = append_marked(agents, "EGBE:APPLICATION-SCAFFOLD", starter_guidance)
        existing_ignores = (read(Path(".gitignore")) or b"").decode()
        files[Path(".gitignore")] = append_marked(
            existing_ignores, "EGBE:APPLICATION-SCAFFOLD", files[Path(".gitignore")].decode(), ignore_file=True,
        ).encode()

    foundations = []
    if auth_db or accounts or subscriptions:
        auth = skill(skills, "product-auth")
        add(auth / "assets/db", Path("db"))
        foundations.append(auth / "assets/scaffolds/product-auth-database")
        if accounts or subscriptions:
            foundations.append(auth / "assets/scaffolds/product-nextjs-postgres")
    if subscriptions:
        foundations.append(skill(skills, "payments") / "assets/scaffolds/billing-nextjs-subscription")
    original_package = json.loads(package_bytes)
    for foundation in foundations:
        fragment = json.loads((foundation / "package.fragment.json").read_text())
        scripts = package.setdefault("scripts", {})
        if not isinstance(scripts, dict):
            raise Conflict("package.json scripts must contain an object")
        for name, expected in fragment.get("expectedScripts", {}).items():
            if scripts.get(name) not in (expected, fragment.get("scripts", {}).get(name, expected)):
                raise Conflict(f"Incompatible script: {name}; expected {expected!r}")
        for section in ("dependencies", "devDependencies", "scripts"):
            current = package.setdefault(section, {})
            if not isinstance(current, dict):
                raise Conflict(f"package.json {section} must contain an object")
            for name, value in fragment.get(section, {}).items():
                if name in current and current[name] != value:
                    expected = fragment.get("expectedScripts", {}).get(name)
                    if section != "scripts" or current[name] != expected:
                        raise Conflict(f"Conflicting {section} entry: {name}")
                current[name] = value
        add(foundation)
        agents = append_marked(agents, fragment["agentsMarker"], (foundation / "AGENTS.append.md").read_text())
    if base and existing_package is not None:
        # Do not transplant a starter package into an existing application.
        # Repeated installation is allowed only when its merged package agrees.
        starter = json.loads(files[Path("package.json")])
        if any(package.get(key) != value for key, value in starter.items() if key not in {"scripts", "dependencies", "devDependencies"}):
            raise Conflict("Existing app package differs; omit --nextjs and integrate only the selected foundation")
        for section in ("scripts", "dependencies", "devDependencies"):
            for name, value in starter.get(section, {}).items():
                allowed = {value}
                for foundation in foundations:
                    fragment = json.loads((foundation / "package.fragment.json").read_text())
                    if name in fragment.get(section, {}):
                        allowed.add(fragment[section][name])
                if package.get(section, {}).get(name) not in allowed:
                    raise Conflict(f"Existing app differs from starter: {section}.{name}")
    if package == original_package:
        files[Path("package.json")] = package_bytes
    else:
        files[Path("package.json")] = (json.dumps(package, indent=2) + "\n").encode()
    if base or foundations:
        files[Path("AGENTS.md")] = agents.encode()
    # Keep `npm ci` working: an unedited shipped lockfile that no longer lists the
    # package's dependencies is replaced by the prebuilt one for this combination.
    replaceable = set(MERGED)
    lock = files.get(LOCKFILE)
    lock = lock if lock is not None else read(LOCKFILE)
    final_package = json.loads(files[Path("package.json")])
    if lock is not None and not lock_lists(lock, final_package):
        existing_lock = read(LOCKFILE)
        prebuilt = prebuilt_lockfile(final_package, skills) if is_shipped_lockfile(lock, skills) else None
        if prebuilt is not None and (existing_lock is None or is_shipped_lockfile(existing_lock, skills)):
            files[LOCKFILE] = prebuilt
            replaceable.add(LOCKFILE)
    changes = []
    for relative, after in sorted(files.items()):
        before = read(relative)
        if before == after:
            continue
        if before is not None and relative not in replaceable:
            raise Conflict(f"Existing file differs: {relative}; no files were written")
        changes.append((relative, before, after))
    return changes


def plan(target: Path, *, base=False, auth_db=False, accounts=False, subscriptions=False, skills=None):
    if target.is_symlink():
        raise Conflict(f"Symlink destination: {target}")
    root = target.resolve()
    if root.exists() and not root.is_dir():
        raise Conflict(f"Expected a product directory: {root}")

    def read(relative):
        path = root / relative
        check_path(root, path)
        return path.read_bytes() if path.exists() else None

    changes = compose(read, base=base, auth_db=auth_db, accounts=accounts, subscriptions=subscriptions,
                      skills=skills)
    return root, [Edit(root / relative, before, after) for relative, before, after in changes]


def apply(root, edits):
    # Recheck every planned write before changing anything.
    for edit in edits:
        check_path(root, edit.path)
        before = edit.path.read_bytes() if edit.path.exists() else None
        if before != edit.before:
            raise Conflict(f"Destination changed since planning: {edit.path}")
    # Ownership guidance describes code already copied, so write it last.
    for edit in sorted(edits, key=lambda item: item.path.name == "AGENTS.md"):
        edit.path.parent.mkdir(parents=True, exist_ok=True)
        edit.path.write_bytes(edit.after)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "plan", "apply"))
    parser.add_argument("--target", type=Path, default=Path.cwd())
    parser.add_argument("--nextjs", action="store_true", help="Copy the blank Next.js starter; for new applications only")
    parser.add_argument("--auth-db", action="store_true", help="Add shared Node/Postgres auth database assets without Next.js server helpers")
    parser.add_argument("--accounts", action="store_true", help="Add the Postgres account/session foundation")
    parser.add_argument("--subscriptions", action="store_true", help="Add subscription billing and its required account foundation; not one-time purchases")
    args = parser.parse_args()
    if args.command == "list":
        print("--nextjs: blank Next.js application; use only when this stack fits")
        print("--auth-db: shared Node/Postgres auth schema, migrations and private validation-session helper; preserves framework/start command")
        print("--accounts: Postgres users, identities, sessions and migrations; account-entry UI still needs implementation")
        print("--subscriptions: subscription lifecycle, checkout, billing UI and account foundation; not a one-time purchase engine")
        return
    try:
        root, edits = plan(args.target, base=args.nextjs, auth_db=args.auth_db, accounts=args.accounts, subscriptions=args.subscriptions)
        if args.command == "apply":
            apply(root, edits)
        print(json.dumps({"target": str(root), "applied": args.command == "apply", "changes": [str(e.path.relative_to(root)) for e in edits]}, indent=2))
        if edits:
            print("Next: install dependencies with your package manager (refresh the lockfile only if it was edited or npm ci fails), implement accepted behavior, configure real bindings and verify before publishing.", file=sys.stderr)
    except (Conflict, OSError, ValueError) as exc:
        parser.exit(1, f"Scaffold installation stopped: {exc}\n")


if __name__ == "__main__":
    main()
