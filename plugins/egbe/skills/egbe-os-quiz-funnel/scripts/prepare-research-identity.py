#!/usr/bin/env python3
"""Reserve a stable private research alias without another skill installation."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
from pathlib import Path


def reserve(registry_path: Path, mailbox: str, domain: str, funnel_id: str) -> dict:
    mailbox, domain = mailbox.strip().lower(), domain.strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]+@[a-z0-9.-]+\.[a-z]{2,}", mailbox):
        raise ValueError("Use the confirmed research mailbox without a plus suffix")
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain) or not funnel_id.strip():
        raise ValueError("A competitor domain and stable funnel_id are required")
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.with_name(registry_path.name + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        registry = json.loads(registry_path.read_text()) if registry_path.is_file() else {"schema_version": 1, "mailbox": mailbox, "identities": []}
        if not isinstance(registry, dict) or registry.get("schema_version") != 1 or registry.get("mailbox") != mailbox or not isinstance(registry.get("identities"), list):
            raise ValueError("Existing identity registry must use schema 1 and the same research mailbox")
        identities = registry["identities"]
        if any(not isinstance(item, dict) for item in identities) or len({item.get("alias") for item in identities}) != len(identities):
            raise ValueError("Identity registry needs unique alias objects")
        existing = [item for item in identities if item.get("funnel_id") == funnel_id]
        if existing:
            local, host = mailbox.split("@")
            if len(existing) != 1 or existing[0].get("domain") != domain or not re.fullmatch(re.escape(local) + r"\+\d{2,}@" + re.escape(host), str(existing[0].get("alias") or "")):
                raise ValueError("Stable funnel identity conflicts with its competitor domain")
            return existing[0]
        local, host = mailbox.split("@")
        used = {item.get("alias") for item in identities}
        number = 1
        while f"{local}+{number:02d}@{host}" in used:
            number += 1
        identity = {"identity_id": f"funnel:{funnel_id}", "domain": domain, "funnel_id": funnel_id,
                    "alias": f"{local}+{number:02d}@{host}", "kind": "funnel"}
        identities.append(identity)
        temporary = registry_path.with_name(registry_path.name + ".tmp")
        temporary.write_text(json.dumps(registry, indent=2) + "\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, registry_path)
        return identity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path, help="Private runtime registry; use the shared registry inside competitor-led GTM")
    parser.add_argument("--mailbox", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--funnel-id", required=True)
    args = parser.parse_args()
    try:
        identity = reserve(args.registry, args.mailbox, args.domain, args.funnel_id)
    except (ValueError, OSError) as exc:
        print(str(exc))
        return 1
    print(json.dumps(identity))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
