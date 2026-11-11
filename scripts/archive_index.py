#!/usr/bin/env python3
"""Archive index extension: the CD's own menu groups on each index row.

The archive (archive.js) groups entries by type for filtering and sorting. Catalog's
`content_kind` is known for few entries, so the archive may also use the CD's menu
groups, which every built entry document already carries as the source observation
`source_context.menu_groups.value`. This module copies that list, unchanged, onto the
entry's row in `index.json` as `menu_groups`. Nothing is read from ISOs, titles, file
names or descriptions, and no entry document is changed.

Run on an already built frontend data directory (also older releases) to write a new,
complete directory, then print the type distribution before and after:

    python scripts/archive_index.py DATA --output NEW_DATA

`ARCHIVE_MENU_GROUP_KINDS` and `archive_kind` mirror archive.js exactly
(tests/test_archive_sort_filter.py checks that both give the same answer).
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import tempfile

CONTENT_KINDS = ("application", "game", "course", "image_collection", "font_collection", "reference")
KIND_LABELS = {"application": "Program", "game": "Spill", "course": "Kurs / veiledning", "image_collection": "Bildesamling",
               "font_collection": "Skriftpakke", "reference": "Oppslagsverk", "article": "Artikkel", "unknown": "Ikke oppgitt"}
ARCHIVE_MENU_GROUP_KINDS = {
    "Spill": "game", "Spil": "game", "games": "game",
    "Skole": "course", "Videokurs": "course",
    "KProgram": "application", "programs": "application", "Software": "application",
    "Artikler": "article",
}


def menu_groups(document: dict) -> list[str] | None:
    """The entry's own menu-group observation, or None when the source has none."""
    observation = (document.get("source_context") or {}).get("menu_groups")
    if observation is None:
        return None
    value = observation.get("value")
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{document.get('entry')}: menu_groups must be a list of text")
    return list(value)


def project_menu_groups(summary: dict, document: dict) -> dict:
    """Set or remove `menu_groups` on an index row from its own entry document."""
    groups = menu_groups(document)
    if groups is None:
        summary.pop("menu_groups", None)
    else:
        summary["menu_groups"] = groups
    return summary


def archive_kind(summary: dict) -> tuple[str, str]:
    """(kind, basis) exactly as archive.js archiveKind: catalog, menu, conflict or none."""
    known = summary.get("content_kind")
    if known in CONTENT_KINDS:
        return known, "catalog"
    kinds = {ARCHIVE_MENU_GROUP_KINDS[group.strip()] for group in summary.get("menu_groups") or []
             if isinstance(group, str) and group.strip() in ARCHIVE_MENU_GROUP_KINDS}
    if len(kinds) == 1:
        return kinds.pop(), "menu"
    return "unknown", "conflict" if kinds else "none"


def distribution(entries: list[dict]) -> dict:
    kinds = Counter(archive_kind(entry)[0] for entry in entries)
    bases = Counter(archive_kind(entry)[1] for entry in entries)
    groups = Counter(group for entry in entries for group in entry.get("menu_groups") or [])
    return {"entries": len(entries), "kinds": dict(kinds), "bases": dict(bases), "groups": dict(groups),
            "with_menu_groups": sum("menu_groups" in entry for entry in entries)}


def extend(data: Path, output: Path) -> tuple[dict, dict]:
    """Write `output` as a copy of `data` whose index rows carry their menu groups.

    Entry documents and any other files are copied byte for byte; only index.json is
    rewritten, and it is validated with the frontend contract before it is moved in.
    """
    from frontend_contract import require, validate_frontend_data

    data, output = Path(data).resolve(), Path(output).absolute()
    require(not output.exists() and not output.is_symlink(), "output must be a new directory")
    before = validate_frontend_data(data)
    index = deepcopy(before)
    for summary in index["entries"]:
        document = json.loads((data / f"{summary['entry'].lower()}.json").read_text(encoding="utf-8"))
        project_menu_groups(summary, document)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".archive-index-", dir=output.parent))
    try:
        for path in data.iterdir():
            if path.name != "index.json" and path.is_file():
                shutil.copy2(path, stage / path.name)
        (stage / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        validate_frontend_data(stage, len(before["entries"]))
        os.rename(stage, output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return before, index


def report(label: str, index: dict) -> str:
    counts = distribution(index["entries"])
    lines = [f"{label}: {counts['entries']} entries, {counts['with_menu_groups']} with menu_groups in the index"]
    for kind in [*KIND_LABELS]:
        if counts["kinds"].get(kind):
            lines.append(f"  {KIND_LABELS[kind]:<20} {counts['kinds'][kind]:>6}")
    lines.append("  basis: " + ", ".join(f"{name} {counts['bases'].get(name, 0)}" for name in ("catalog", "menu", "conflict", "none")))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data", type=Path, help="Built frontend data directory (index.json + entry documents)")
    parser.add_argument("--output", type=Path, help="New directory for the extended data; omit to only report")
    parser.add_argument("--groups", action="store_true", help="Also list every menu-group value and how often it occurs")
    args = parser.parse_args()
    if args.output:
        before, after = extend(args.data, args.output)
    else:
        from frontend_contract import validate_frontend_data
        before = validate_frontend_data(args.data.resolve())
        after = deepcopy(before)
        for summary in after["entries"]:
            project_menu_groups(summary, json.loads((args.data / f"{summary['entry'].lower()}.json").read_text(encoding="utf-8")))
    print(report("before (index as given)", before))
    print(report("after (menu groups from entry documents)", after))
    if args.groups:
        for group, count in sorted(distribution(after["entries"])["groups"].items(), key=lambda item: (-item[1], item[0])):
            mapped = ARCHIVE_MENU_GROUP_KINDS.get(group.strip())
            print(f"  {count:>6}  {group!r}" + (f" -> {KIND_LABELS[mapped]}" if mapped else ""))
    if args.output:
        print(f"extended data: {args.output}")


if __name__ == "__main__":
    main()
