#!/usr/bin/env python3
"""Build or dry-run the original CD menus for many media and report per medium.

    python3 scripts/cd-menu-matrix.py --config MATRIX.json --index DATA/index.json \\
        --site BUILD_DIR --report-dir REPORT_DIR [--dry-run] [--approve ID,ID | --preview-all]

MATRIX.json (relative paths are read from the config file's folder)::

    {"schema": "bootdisk-cd-menu-matrix-1",
     "media": [{"id": "kcd-18-2013", "manifest": ".../manifest.json", "source": ".../menu-source/kcd-18-2013"}]}

``source`` is the extracted menu selection (scripts/extract-cd-menu-source.py). When it
is missing, only the entry pages embedded in the manifest are checked.

One medium's problem never stops the others, and a blocked medium keeps the menu that
is already in BUILD_DIR. ``cd-meny/menus.json`` (the file the archive reads) lists only
the media named with ``--approve``; ``--preview-all`` lists every built medium for a
local preview. Nothing is uploaded.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cd_menu  # noqa: E402

STATUS_TEXT = {"ready": "klar til gjennomgang", "review": "bygget med avvik", "blocked": "sperret",
               "dry_run": "tørrkjørt (uten kildeutvalg)", "error": "feil i byggeren"}


def resolve(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path)


def markdown(rows: list[dict], args) -> str:
    lines = ["# Originalmenyer fra K-CD: matrise", "",
             f"Modus: {'tørrkjøring' if args.dry_run else 'bygging'}. Indeks: `{args.index.name}`. Ingen opplasting.", "",
             "| Medium | Status | Kilder | Ruter | Ankre | Delte sider | Sider | Bilder | Manglende ressurser | Deaktivert | Merknad |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for row in rows:
        counts = row.get("counts") or {}
        missing = counts.get("missing_images", 0) + counts.get("pages_unavailable", 0) + counts.get("images_unavailable", 0)
        notes = list(row.get("problems") or [])
        unchecked = row.get("unchecked")
        if unchecked:
            missing = counts.get("missing_images", 0)
            notes.append(f"ikke kontrollert uten kildeutvalg: {unchecked['pages']} sider/stilark, {unchecked['images']} bilder"
                         + (", menymalen" if unchecked["template"] else ""))
        note = row.get("blocked") or row.get("error") or "; ".join(notes) or "–"
        lines.append(f"| {row['medium_id']} | {STATUS_TEXT.get(row['status'], row['status'])} | {counts.get('source_entries', '–')} | "
                     f"{counts.get('routes', '–')} | {counts.get('anchored_routes', '–')} | {counts.get('shared_pages', '–')} | "
                     f"{counts.get('pages_built', '–')} | {counts.get('images', '–')} | {missing if counts else '–'} | "
                     f"{counts.get('disabled', '–')} | {note} |")
    lines += ["", "«Klar til gjennomgang» betyr at alle kildeposter fikk en verifisert rute og at alle filer stemte med manifestet. "
              "Det er ikke en godkjenning; Stian og Birk avgjør hvilke utgaver som vises.", ""]
    for row in rows:
        unbound = row.get("unbound") or []
        missing = [item for item in row.get("missing_images") or [] if not item["page"].endswith(".css")]
        if unbound or missing or row.get("broken_pages"):
            lines.append(f"## {row['medium_id']}")
            for item in unbound:
                lines.append(f"- Uten rute: {item['entry']}: {item['reason']}")
            for page, reason in (row.get("broken_pages") or {}).items():
                lines.append(f"- Ødelagt side: {page}: {reason}")
            for item in missing:
                lines.append(f"- Bilde: {item['page']} → {item['url']}: {item['reason']}")
            lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--site", type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", help="comma-separated media to run")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--approve", default="", help="comma-separated media to list in cd-meny/menus.json")
    group.add_argument("--preview-all", action="store_true", help="list every built medium (local preview only)")
    args = parser.parse_args(argv)
    if not args.dry_run and args.site is None:
        parser.error("--site is required unless --dry-run")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config.get("schema") != "bootdisk-cd-menu-matrix-1":
        parser.error("unknown matrix schema")
    index = json.loads(args.index.read_text(encoding="utf-8"))
    base = args.config.resolve().parent
    only = {item for item in (args.only or "").split(",") if item}
    rows = []
    for medium in config["media"]:
        if only and medium["id"] not in only:
            continue
        manifest = resolve(base, medium.get("manifest"))
        source = resolve(base, medium.get("source"))
        if manifest is None or not manifest.is_file():
            rows.append({"medium_id": medium["id"], "status": "blocked", "blocked": ("manifestet finnes ikke: " + str(medium["manifest"])) if medium.get("manifest")
                         else "manifestet som kildepostene er bygget fra, er ikke funnet"})
        else:
            if source is not None and not source.is_dir():
                source = None
            try:
                rows.append(cd_menu.build_medium(medium["id"], manifest, source, index, args.site, args.dry_run))
            except Exception as error:  # one medium must not stop the matrix
                rows.append({"medium_id": medium["id"], "status": "error", "error": f"{type(error).__name__}: {error}",
                             "trace": traceback.format_exc(limit=3)})
        print(json.dumps({key: rows[-1].get(key) for key in ("medium_id", "status", "blocked", "error", "problems")}, ensure_ascii=False), flush=True)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    (args.report_dir / "report.json").write_text(json.dumps({"schema": "bootdisk-cd-menu-matrix-report-1", "dry_run": args.dry_run, "media": rows},
                                                            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.report_dir / "RAPPORT.md").write_text(markdown(rows, args), encoding="utf-8")
    if args.site is not None and not args.dry_run:
        wanted = {item for item in args.approve.split(",") if item}
        listed = []
        for folder in sorted((args.site / cd_menu.MENU_DIR).glob("*/menu-index.json")):
            report = json.loads(folder.read_text(encoding="utf-8"))
            if report.get("status") in ("ready", "review") and (args.preview_all or report["medium_id"] in wanted):
                listed.append(report)
        cd_menu.register(args.site, listed)
        print(f"menus.json: {len(listed)} medier", flush=True)
    return 0 if all(row["status"] != "error" for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
