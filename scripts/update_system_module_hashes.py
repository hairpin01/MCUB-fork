#!/usr/bin/env python3
"""Update SHA-256 hashes in core/system_modules.json.

The loader verifies system modules by hashing the decoded source text and then
encoding it as UTF-8.  Keep this script in sync with
core.lib.loader.protection.SystemModuleProtection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "core" / "system_modules.json"


def module_sha256(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict) or not isinstance(data.get("modules"), dict):
        raise ValueError(f"Invalid system module manifest: {path}")
    return data


def update_hashes(manifest_path: Path, *, check: bool = False) -> int:
    manifest_path = manifest_path.resolve(strict=False)
    project_root = (
        manifest_path.parent.parent
        if manifest_path.parent.name == "core"
        else manifest_path.parent
    )
    data = load_manifest(manifest_path)
    modules = data["modules"]

    changed: list[tuple[str, str, str]] = []
    missing: list[tuple[str, Path]] = []

    for name, entry in modules.items():
        if not isinstance(entry, dict):
            raise ValueError(f"Invalid manifest entry for {name!r}")
        rel_path = entry.get("path")
        if not isinstance(rel_path, str) or not rel_path:
            raise ValueError(f"Manifest entry {name!r} has no path")

        module_path = (project_root / rel_path).resolve(strict=False)
        if not module_path.exists():
            missing.append((name, module_path))
            continue

        old_hash = str(entry.get("sha256", ""))
        new_hash = module_sha256(module_path)
        if old_hash.lower() != new_hash.lower():
            changed.append((name, old_hash, new_hash))
            if not check:
                entry["sha256"] = new_hash

    if missing:
        for name, path in missing:
            print(f"missing: {name}: {path}", file=sys.stderr)
        return 2

    if check:
        if changed:
            for name, old_hash, new_hash in changed:
                print(f"stale: {name}: {old_hash} -> {new_hash}")
            return 1
        print("All system module hashes are up to date.")
        return 0

    if changed:
        manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        for name, old_hash, new_hash in changed:
            print(f"updated: {name}: {old_hash} -> {new_hash}")
    else:
        print("All system module hashes are already up to date.")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update sha256 values in core/system_modules.json."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to system_modules.json (default: core/system_modules.json).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only verify hashes; exit 1 if any entry is stale.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return update_hashes(args.manifest, check=args.check)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
