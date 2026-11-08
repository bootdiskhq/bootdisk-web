#!/usr/bin/env python3
"""PRØVEDATA in catalogue size for the public retro catalogue pages.

A deterministic, clearly labelled stand-in for the real local preview Birk builds
(1705 source entries on 29 CDs on 2026-11-08). Nothing here is real: every title
starts with "Prøvepost", every description says it is invented, the CD labels and
per-CD counts are made up, and the release ids say "test". It exists so the pages
can be checked at the real archive's size and with the hard cases the data contract
allows, without access to Birk's machine:

* long Norwegian titles with æøå and a very long unbroken word, HTML-looking titles;
* identified, provisional ("interpreted"), source-documented and pending entries;
* version unknown, missing icon, missing screenshot, missing description;
* original RTF text: identical to the menu text, long, unreadable (null), two files;
* source issues and a completed source investigation note;
* a two-release update history (bootdisk-public-updates-v4) with new and changed entries.

The package is built with the real gates (build-collection layout, frontend_contract,
build-release.py and public_updates.py), so it is a valid release *shape*, never a
release. Build a servable directory with:

    python tests/synthetic_catalog.py NEW_DIRECTORY [--entries 1705] [--media 29]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import public_updates  # noqa: E402
import synthetic_collection as synthetic  # noqa: E402

PUBLICATION = synthetic.PUBLICATION
BASELINE, RELEASE = "test-catalog-r1", "test-catalog-r2"
RELEASE_TIME = "2026-11-08T12:00:00Z"
KINDS = ["application", "game", "course", "image_collection", "font_collection", "reference", None]
EDITIONS = ["full", "demo", "trial", "update", "unknown", None]
WORDS = ["Tekstbehandler", "Bildeviser", "Skrivetrener", "Regneark", "Flysimulator", "Diskettverktøy",
         "Musikkspiller", "Kryssordløser", "Fargelegger", "Sjakkspill", "Adressebok", "Økonomistyring",
         "Ordbok", "Værvarsel", "Skjermsparer", "Tegneprogram", "Fotballmanager", "Fjordspill"]
LONG_TITLE = ("Prøvepost: Et usedvanlig langt programnavn med æøå som må brytes pent i kolonnene – "
              "Norsk utgave for Windows 95/98 og NT med Ekstramateriale")
LONG_WORD = "Prøvepost: " + "Programvarebevaringsdokumentasjonsverktøy" * 2
HTML_TITLE = 'Prøvepost <b>fet</b> <img src=x onerror="window.__catalogXss=1"> & «sitat»'
LONG_RTF = ("PRØVEDATA – lang originaltekst\n\n" + "\n\n".join(
    f"Avsnitt {n}: Denne teksten er oppdiktet. Den står her for å vise at lange originaltekster "
    "med æ, ø og å, «anførselstegn» og <b>HTML-lignende</b> tegn vises bokstavelig og uendret." for n in range(1, 9)) + "\n")


def media_plan(media: int, entries: int) -> list[tuple[str, str, int]]:
    """(id, label, entry count): 29 issues over 1998-2002 by default, uneven counts summing to `entries`."""
    issues = []
    year, issue = 2002, 12
    while len(issues) < media:
        issues.append((year, issue))
        issue -= 2 if (len(issues) % 3) else 1
        if issue < 1:
            year, issue = year - 1, 15 if year % 2 else 13
    weights = [20 + int(hashlib.sha256(f"w{n}".encode()).hexdigest()[:2], 16) % 70 for n in range(media)]
    counts = [max(1, entries * w // sum(weights)) for w in weights]
    counts[0] += entries - sum(counts)
    return [(f"kcd-{i}-{y}", f"K-CD {i}/{y}", c) for (y, i), c in zip(issues, counts)]


_PNG: dict[tuple, bytes] = {}


def image(store_root: Path, entry: str, kind: str, size: tuple[int, int], variant: int) -> dict:
    # 40 distinct pictures per kind are plenty; generating 3 400 PNGs in Python is slow.
    seed = (kind, size, variant % 40)
    if seed not in _PNG:
        _PNG[seed] = synthetic.png(*size, f"catalog/{kind}/{variant % 40}")
    original = synthetic.store_image(store_root, _PNG[seed])
    return {"entry": entry, "kind": kind, "source_path": f"PRØVEDATA/{kind}.png", "original": original, "derivatives": []}


def rtf(store_root: Path, key: dict, path: str, text: str | None) -> dict:
    content = ("{\\rtf1\\ansi PRØVEDATA " + path + "\\par}").encode("cp1252", "replace")
    digest = hashlib.sha256(content).hexdigest()
    public_path = f"store/documents/sha256/{digest[:2]}/{digest}.rtf"
    target = store_root / public_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return {"key": dict(key), "path": path, "sha256": digest, "size": len(content), "text": text, "warning": None,
            "original": {"sha256": digest, "size": len(content), "public_path": public_path, "media_type": "application/rtf"}}


def make_entry(store_root: Path, medium: dict, legacy: bool, position: int, number: int, order: int) -> tuple[dict, dict]:
    source_entry = f"K{position + 1}"
    entry = source_entry if legacy else f"{medium['id']}--{source_entry}"
    key = {"entry": source_entry, "manifest": medium["source_manifest"]}
    ref = lambda pointer: {**key, "pointer": f"/entries/{position}/{pointer}"}  # noqa: E731
    word = WORDS[number % len(WORDS)]
    title = f"Prøvepost {number + 1}: {word}"
    if number % 97 == 5:
        title = LONG_TITLE
    elif number % 211 == 7:
        title = LONG_WORD
    elif number == 13:
        title = HTML_TITLE
    status, software, source_catalog = "pending", [], None
    kind, edition = KINDS[number % len(KINDS)], EDITIONS[number % len(EDITIONS)]
    version = ["1.0", "2.76", "unknown", "98", "unknown"][number % 5]
    if number % 7 in (0, 1):
        name = f"Prøveprogram {word} {number + 1}"
        software = [{"software_id": f"software:prove-{number}", "software_name": name, "version": version,
                     "status": "interpreted" if number % 7 == 1 else "curated",
                     "content_kind": kind, "distribution_kind": edition, "descriptions": []}]
        status = "identified"
    elif number % 7 in (2, 3, 4):
        source_catalog = {"rule": "source-catalog-readiness-4", "status": "documented", "key": dict(key),
                          "title": {"value": title, "source_ref": ref("raw/Title")}}
        if number % 31 == 2:
            source_catalog["file_association"] = {"explanation": {
                "pattern": "documented_source_defect", **key,
                "explanation": "PRØVEDATA: CD-menyen peker til en fil som mangler. Undersøkt og merket som kildefeil."}}
    description = None if number % 11 == 3 else (
        f"PRØVEDATA: oppdiktet menyomtale for {title} på {medium['medium']}. Dette er ikke en original CD-omtale.")
    context = {"key": dict(key), "menu_groups": {"source_ref": ref("normalized/categories"), "value": [word]},
               "issues": {"source_ref": ref("issues"), "value": ["missing_file_reference"] if number % 19 == 4 else []}}
    if description is not None:
        context["description"] = {"source_ref": ref("raw/Global"), "value": description}
    assets = []
    if number % 9 != 4:
        assets.append(image(store_root, entry, "icon", (32, 32), number))
    if number % 5 != 2:
        assets.append(image(store_root, entry, "screenshot", (320, 240), number))
    documents = []
    if number % 6 == 0 and description:
        documents.append(rtf(store_root, key, f"{word}/No.rtf", description + "\n"))
    if number % 17 == 1:
        documents.append(rtf(store_root, key, f"{word}/Lang.rtf", LONG_RTF))
    if number % 23 == 2:
        documents.append(rtf(store_root, key, f"{word}/Uleselig.rtf", None))
    if number % 29 == 3:
        documents += [rtf(store_root, key, f"{word}/Les.rtf", "PRØVEDATA første fil."),
                      rtf(store_root, key, f"{word}/Installasjon.rtf", "PRØVEDATA andre fil.\nLinje to.")]
    metadata = {"entry": entry, "medium_id": medium["id"], "medium": medium["medium"], "publication": PUBLICATION,
                "source_entry": source_entry, "source_manifest": medium["source_manifest"], "source_order": order}
    document = {**metadata, "editorial_title": title, "curation_status": status, "software": software,
                "assets": assets, "source_context": context}
    if documents:
        document["source_documents"] = documents
    if source_catalog:
        document["source_catalog"] = source_catalog
    icon = next((asset for asset in assets if asset["kind"] == "icon"), None) or next(iter(assets), None)
    summary = {**metadata, "curation_status": status, "editorial_title": title,
               "software_name": software[0]["software_name"] if software else None,
               "version": software[0]["version"] if software else None,
               "identification_status": software[0]["status"] if software else None,
               "content_kind": software[0]["content_kind"] if software else None,
               "distribution_kind": software[0]["distribution_kind"] if software else None,
               "source_catalog_status": source_catalog["status"] if source_catalog else None,
               "icon": copy.deepcopy(icon)}
    return summary, document


def write_projection(output: Path, plan: list[tuple[str, str, int]], store_root: Path, changed: bool, skip: set = frozenset()) -> Path:
    """`skip` leaves out media by position in the plan; every other entry keeps its content."""
    media, summaries, documents = [], [], {}
    number = 0
    for slot, (medium_id, label, count) in enumerate(plan):
        if slot in skip:
            number += count
            continue
        manifest = "sha256:" + hashlib.sha256(f"catalog/{medium_id}".encode()).hexdigest()
        medium = {"id": medium_id, "publication": PUBLICATION, "medium": label, "legacy_links": slot == 0,
                  "source_manifest": manifest}
        media.append(medium)
        for position in range(count):
            summary, document = make_entry(store_root, medium, slot == 0, position, number, len(summaries))
            number += 1
            if changed and number % 41 == 0:
                # A visible change in the second release: a new original description.
                document["source_context"].setdefault("description", {"source_ref": {**document["source_context"]["key"], "pointer": "/x"}})
                document["source_context"]["description"]["value"] = "PRØVEDATA: omtalen er endret i test-catalog-r2."
            summaries.append(summary)
            documents[summary["entry"].lower()] = document
    index = {"schema": "bootdisk-web-collection-1", "publication": "Bootdisk", "medium": f"{len(media)} CD-er",
             "media": media, "entries": summaries}
    output.mkdir(parents=True)
    for name, document in {**documents, "index": index}.items():
        (output / f"{name}.json").write_text(json.dumps(document, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return output


def build(output: Path, entries: int = 1705, media: int = 29) -> dict:
    """Package the preview into the new directory `output`; return a short report."""
    plan = media_plan(media, entries)
    with tempfile.TemporaryDirectory(prefix="bootdisk-catalog-") as temporary:
        work = Path(temporary)
        store_root = work / "publish"
        store_root.mkdir()
        # Release r1 lacks three of the newest CDs; r2 adds them and changes some descriptions.
        previous = write_projection(work / "r1", plan, store_root, changed=False, skip={1, 2, 3})
        current = write_projection(work / "r2", plan, store_root, changed=True)
        p1, p2 = public_updates.load_projection(previous), public_updates.load_projection(current)
        register = public_updates.record_release(public_updates.init_register(p1, BASELINE), p1, p2, RELEASE, RELEASE_TIME)
        updates = work / "updates.json"
        updates.write_text(public_updates.dumps(register), encoding="utf-8")
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build-release.py"), str(current), str(store_root),
                                 "--output", str(output), "--expected-entries", str(sum(c for _, _, c in plan)),
                                 "--updates", str(updates)], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
    return {"media": len(plan), "entries": sum(c for _, _, c in plan), "events": len(register["events"]),
            "plan": plan}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path, help="New directory for the PRØVEDATA package")
    parser.add_argument("--entries", type=int, default=1705)
    parser.add_argument("--media", type=int, default=29)
    args = parser.parse_args()
    output = args.output.expanduser().absolute()
    if output.exists():
        raise SystemExit(f"Refusing to replace existing path: {output}")
    report = build(output, args.entries, args.media)
    print(f"PRØVEDATA: {report['entries']} invented source entries on {report['media']} invented CDs, "
          f"{report['events']} update events. Not the real archive.")


if __name__ == "__main__":
    main()
