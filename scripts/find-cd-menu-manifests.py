#!/usr/bin/env python3
"""Write a matrix config by finding the exact manifest each published medium was built from.

    python3 scripts/find-cd-menu-manifests.py --index DATA/index.json --root RESULTS_DIR \\
        [--root ...] [--sources MENU_SOURCE_DIR] --out MATRIX.json

Every ``manifest.json`` under the roots is hashed. A medium is listed only when one of
its files hashes to the ``source_manifest`` that the published source posts carry and
its format is an HTML menu (``kcd-html-menu-1``). Two runs of the same disc often have
manifests of the same size with different bytes, so names and sizes are never used.
Folders whose names start with a dot (unfinished ``.partial`` runs) are skipped.

With ``--sources``, ``SOURCES/<medium>`` is used as the extracted menu selection when
that folder exists. Media whose manifest is not found are reported, not guessed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

HTML_FORMAT = "kcd-html-menu-1"


def file_ref(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def manifests(roots: list[Path]):
    for root in roots:
        for folder, dirs, files in os.walk(root):
            dirs[:] = sorted(name for name in dirs if not name.startswith("."))
            if "manifest.json" in files:
                yield Path(folder) / "manifest.json"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path, action="append")
    parser.add_argument("--sources", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    index = json.loads(args.index.read_text(encoding="utf-8"))
    wanted: dict[str, set[str]] = {}
    for entry in index.get("entries", []):
        if entry.get("medium_id") and entry.get("source_manifest"):
            wanted.setdefault(entry["source_manifest"], set()).add(entry["medium_id"])
    found: dict[str, Path] = {}
    for path in manifests(args.root):
        ref = file_ref(path)
        if ref not in wanted:
            continue
        try:
            fmt = (json.loads(path.read_text(encoding="utf-8")).get("source") or {}).get("format")
        except (OSError, ValueError):
            continue
        if fmt != HTML_FORMAT:
            continue
        for medium in wanted[ref]:
            found.setdefault(medium, path.resolve())
    order = [medium.get("id") for medium in index.get("media", [])] or sorted(found)
    media = []
    for medium in order:
        if medium in found:
            row = {"id": medium, "manifest": str(found[medium])}
            if args.sources and (args.sources / medium).is_dir():
                row["source"] = str((args.sources / medium).resolve())
            media.append(row)
    args.out.write_text(json.dumps({"schema": "bootdisk-cd-menu-matrix-1", "media": media}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Media with an HTML menu are only known once their manifest is found; list the
    # rest so a missing HTML disc is visible rather than silently absent.
    missing = sorted({medium for ref, ids in wanted.items() for medium in ids} - set(found))
    print(json.dumps({"media": len(media), "with_source": sum("source" in row for row in media),
                      "not_found_or_not_html": missing}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
