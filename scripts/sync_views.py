#!/usr/bin/env python3
"""Keeps ``views/`` and ``pages/`` byte-identical.

AstrBot 4.24.2 - 4.28 scan only ``pages/``; AstrBot 4.29+ scan ``views/`` first
and keep ``pages/`` as an alias. Both directories must therefore ship the same
files. ``views/`` is the source of truth; this script mirrors it into ``pages/``.

Run after editing anything under ``views/``:

    python scripts/sync_views.py          # copy views -> pages
    python scripts/sync_views.py --check  # exit 1 when out of sync
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "views"
MIRROR = ROOT / "pages"
IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc")


def _iter_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def check() -> int:
    if not SOURCE.is_dir():
        print(f"missing source directory: {SOURCE}", file=sys.stderr)
        return 1
    if not MIRROR.is_dir():
        print(f"missing mirror directory: {MIRROR} (run without --check)", file=sys.stderr)
        return 1

    source_files = {path.relative_to(SOURCE) for path in _iter_files(SOURCE)}
    mirror_files = {path.relative_to(MIRROR) for path in _iter_files(MIRROR)}

    stale = sorted(source_files - mirror_files)
    orphaned = sorted(mirror_files - source_files)
    differing = sorted(
        rel
        for rel in source_files & mirror_files
        if not filecmp.cmp(SOURCE / rel, MIRROR / rel, shallow=False)
    )

    for label, items in (("missing in pages/", stale), ("extra in pages/", orphaned), ("differs", differing)):
        for rel in items:
            print(f"{label}: {rel}", file=sys.stderr)

    if stale or orphaned or differing:
        print("views/ and pages/ are out of sync; run python scripts/sync_views.py", file=sys.stderr)
        return 1

    print(f"views/ and pages/ are in sync ({len(source_files)} files)")
    return 0


def sync() -> int:
    if not SOURCE.is_dir():
        print(f"missing source directory: {SOURCE}", file=sys.stderr)
        return 1
    if MIRROR.exists():
        shutil.rmtree(MIRROR)
    shutil.copytree(SOURCE, MIRROR, ignore=IGNORED)
    copied = len(_iter_files(MIRROR))
    print(f"mirrored views/ -> pages/ ({copied} files)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args()
    return check() if args.check else sync()


if __name__ == "__main__":
    raise SystemExit(main())
