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


def plan(target: Path, *, base=False, auth_db=False, accounts=False, subscriptions=False, skills=None):
    skills = skills or Path(__file__).resolve().parents[2]
    if target.is_symlink():
        raise Conflict(f"Symlink destination: {target}")
    root = target.resolve()
    if root.exists() and not root.is_dir():
        raise Conflict(f"Expected a product directory: {root}")
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
    package_path = root / "package.json"
    check_path(root, package_path)
    package_bytes = package_path.read_bytes() if package_path.exists() else files.get(Path("package.json"))
    if package_bytes is None:
        raise Conflict("A product package.json is required; use --nextjs only for a new app")
    package = json.loads(package_bytes)
    if not isinstance(package, dict):
        raise Conflict("package.json must contain an object")
    agents_path = root / "AGENTS.md"
    check_path(root, agents_path)
    agents = agents_path.read_text() if agents_path.exists() else ""
    if base:
        starter_guidance = files[Path("AGENTS.md")].decode()
        agents = append_marked(agents, "EGBE:APPLICATION-SCAFFOLD", starter_guidance)
        ignore_path = root / ".gitignore"
        check_path(root, ignore_path)
        existing_ignores = ignore_path.read_text() if ignore_path.exists() else ""
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
    if base and package_path.exists():
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
    edits = []
    for relative, after in sorted(files.items()):
        destination = root / relative
        check_path(root, destination)
        before = destination.read_bytes() if destination.exists() else None
        if before == after:
            continue
        if before is not None and relative not in {Path("package.json"), Path("AGENTS.md"), Path(".gitignore")}:
            raise Conflict(f"Existing file differs: {relative}; no files were written")
        edits.append(Edit(destination, before, after))
    return root, edits


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
            print("Next: refresh dependencies/lockfile with your package manager, implement accepted behavior, configure real bindings and verify before publishing.", file=sys.stderr)
    except (Conflict, OSError, ValueError) as exc:
        parser.exit(1, f"Scaffold installation stopped: {exc}\n")


if __name__ == "__main__":
    main()
