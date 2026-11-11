#!/usr/bin/env python3
"""PRØVEDATA for archive filtering and sorting (docs/archive-sort-filter.md).

Small, invented and clearly labelled: every title starts with «Prøvepost» or
«Prøveprogram», CD labels are made up and nothing describes a real program. Each
entry is one hard case for the type rule (known type, CD menu group, agreeing groups,
conflict, «Demoer» alone, no group), the CD year (issue 2 vs 10 in one year, a CD
without a year) or Norwegian sorting (Æ, Ø, Å, equal titles on different CDs).

The package is built through the real gates: one single-medium projection per CD,
build-collection.py (which projects `menu_groups` onto the index), frontend_contract
and build-release.py. Build a servable directory with:

    python tests/synthetic_archive.py NEW_DIRECTORY
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
PUBLICATION = "PRØVEDATA ARKIV"
REGISTRY = {"schema": "bootdisk-web-collections-1", "collections": [{
    "id": "provedata-arkiv", "title": "Prøvedata for arkivet", "publication_values": [PUBLICATION],
    "summary": "PRØVEDATA: oppdiktet samling for test av filtrering og sortering. Ikke produksjonsinnhold.",
    "lede": "PRØVEDATA: oppdiktet samling.", "history": [], "sources": []}]}

# (medium id, label). The last CD has no issue/year in its label on purpose.
MEDIA = [("kcd-2-2001", "K-CD 2/2001"), ("kcd-10-2001", "K-CD 10/2001"), ("kcd-5-2000", "K-CD 5/2000"),
         ("kcd-1-2013", "K-CD 1/2013"), ("prove-uten-aar", "Prøve-CD uten utgavenummer")]

# Per entry: (medium, title, menu groups or None for no observation, content_kind, distribution_kind)
ENTRIES = [
    ("kcd-2-2001", "Prøvepost: Bekreftet spill", ["Spil"], "game", "full"),
    ("kcd-2-2001", "Prøvepost: Spill fra menyen", ["Spill"], None, None),
    ("kcd-2-2001", "Prøvepost: Kurs fra Skole", ["Skole"], None, None),
    ("kcd-2-2001", "Prøvepost: Samme navn", ["KProgram"], None, None),
    ("kcd-2-2001", "Prøvepost: Bare demo", ["Demoer"], None, None),
    ("kcd-2-2001", "Prøvepost: Ærfugl", ["Spil", "Barn"], None, None),
    ("kcd-10-2001", "Prøvepost: Samme navn", ["KProgram", "Software"], None, None),
    ("kcd-10-2001", "Prøvepost: Typekonflikt", ["KProgram", "Spil"], None, None),
    ("kcd-10-2001", "Prøvepost: Kjent program mot spillmeny", ["Spil"], "application", None),
    ("kcd-10-2001", "Prøvepost: Øvingsspill", ["games"], None, None),
    ("kcd-10-2001", "Prøvepost: Barn alene", ["Barn"], None, None),
    ("kcd-10-2001", "Prøvepost: Demo av program", ["Demoer"], None, "demo"),
    ("kcd-5-2000", "Prøvepost: Åpent spill", ["Spill"], None, None),
    ("kcd-5-2000", "Prøvepost: Bekreftet kurs", [], "course", None),
    ("kcd-5-2000", "Prøvepost: Uten menygruppe", None, None, None),
    ("kcd-5-2000", "Prøvepost: Zebra", ["programs"], None, None),
    ("kcd-5-2000", "Prøvepost: Skriftpakke", ["Galleri"], "font_collection", None),
    ("kcd-1-2013", "Prøvepost: Videokurs", ["Videokurs"], None, None),
    ("kcd-1-2013", "Prøvepost: Artikkel", ["Artikler"], None, None),
    ("kcd-1-2013", "Prøvepost: Aktuelt", ["Aktuelt"], None, None),
    ("kcd-1-2013", "Prøvepost: Bonus", ["Bonus"], None, None),
    ("kcd-1-2013", "Prøvepost: Tom gruppeliste", [], None, None),
    ("prove-uten-aar", "Prøvepost: Spill uten år", ["Spil"], None, None),
    ("prove-uten-aar", "Prøvepost: Program uten år", ["KProgram"], None, None),
]


def projection(root: Path, medium_id: str, label: str) -> Path:
    data = root / medium_id
    data.mkdir()
    manifest = "sha256:" + hashlib.sha256(f"archive-sort/{medium_id}".encode()).hexdigest()
    rows = []
    for position, (medium, title, groups, kind, edition) in enumerate(e for e in ENTRIES if e[0] == medium_id):
        entry = f"K{position + 1}"
        key = {"entry": entry, "manifest": manifest}
        context = {"key": key, "description": {"source_ref": {**key, "pointer": f"/entries/{position}/raw/Global"},
                                               "value": f"PRØVEDATA: oppdiktet menyomtale for {title}."}}
        if groups is not None:
            context["menu_groups"] = {"source_ref": {**key, "pointer": f"/entries/{position}/normalized/categories"}, "value": groups}
        software = []
        if kind or edition:
            software = [{"software_id": f"software:prove-{medium_id}-{position}", "software_name": title.replace("Prøvepost", "Prøveprogram"),
                         "version": "unknown", "status": "curated", "content_kind": kind, "distribution_kind": edition, "descriptions": []}]
        document = {"entry": entry, "publication": PUBLICATION, "medium": label, "editorial_title": title, "curation_status": "identified" if software else "pending",
                    "software": software, "assets": [], "source_context": context}
        (data / f"{entry.lower()}.json").write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        first = software[0] if software else {}
        rows.append({"entry": entry, "editorial_title": title, "curation_status": document["curation_status"],
                     "software_name": first.get("software_name"), "version": first.get("version"),
                     "identification_status": first.get("status"), "content_kind": first.get("content_kind"),
                     "distribution_kind": first.get("distribution_kind"), "source_catalog_status": None, "icon": None})
    (data / "index.json").write_text(json.dumps({"publication": PUBLICATION, "medium": label, "entries": rows}, ensure_ascii=False), encoding="utf-8")
    return data


def build(output: Path) -> dict:
    """Build the PRØVEDATA release into the new directory `output`."""
    spec = importlib.util.spec_from_file_location("collection_builder", ROOT / "scripts" / "build-collection.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    with tempfile.TemporaryDirectory(prefix="bootdisk-archive-") as temporary:
        work = Path(temporary)
        config = {"media": [{"id": medium_id, "data": str(projection(work, medium_id, label)), "legacy_links": False,
                             "images_unavailable_reason": "PRØVEDATA uten bilder"} for medium_id, label in MEDIA]}
        (work / "collection.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        index = builder.build_collection(work / "collection.json", work / "data")
        (work / "publish").mkdir()
        (work / "collections.json").write_text(json.dumps(REGISTRY, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build-release.py"), str(work / "data"), str(work / "publish"),
                                 "--output", str(output), "--expected-entries", str(len(ENTRIES)),
                                 "--collections", str(work / "collections.json")], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.expanduser().absolute()
    if output.exists():
        raise SystemExit(f"Refusing to replace existing path: {output}")
    index = build(output)
    print(f"PRØVEDATA: {len(index['entries'])} invented archive entries on {len(index['media'])} invented CDs. Not the real archive.")


if __name__ == "__main__":
    main()
