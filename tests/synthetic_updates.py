#!/usr/bin/env python3
"""Labelled test data for the public update overview (bootdisk-public-updates-v2).

PRØVEDATA. Three invented releases of the synthetic seven-disc archive from
tests/synthetic_collection.py, recorded with scripts/public_updates.py:

* `test-r1`: the dateless baseline.
* `test-r2`, published 2026-03-28T23:30:00Z (00:30 on 29 March in Oslo, the night
  summer time starts): one new entry and a set of visible changes, together with
  changes that must not count (moved storage path, reformatted JSON, new manifest
  digest, renumbered source order).
* `test-r3`, published 2026-10-24T22:30:00Z (00:30 on 25 October in Oslo, the night
  summer time ends): a second change to one entry, the same program changed on two
  CDs, and an entry from r2 removed from the archive.

Program names such as "Testkatt" and "Testvakt" are invented. None of this is real
history, it is never packaged as such, and the release ids say "test".
`large_fixture` writes a 5 000-entry index and feed for search and paging checks.

    python tests/synthetic_updates.py NEW_DIRECTORY   # servable package of test-r3
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import public_updates  # noqa: E402
import synthetic_collection as synthetic  # noqa: E402

R1, R2, R3 = "test-r1", "test-r2", "test-r3"
R2_TIME = "2026-03-28T23:30:00Z"
R3_TIME = "2026-10-24T22:30:00Z"
NEW_ENTRY = "kcd-9-2000--K7"
REMOVED_IN_R3 = "kcd-1-2001--K2"

# What the r2 and r3 changes must produce. Entries not listed get no event.
EXPECTED_R2 = {
    "K3": ("updated", ["identified", "name_added", "version_added", "content_kind_added", "distribution_kind_added"]),
    "kcd-8-2001--K1": ("updated", ["identified", "name_added"]),
    "K37": ("updated", ["name_changed", "version_removed"]),
    "kcd-1-2001--K1": ("updated", ["description_changed"]),
    "kcd-1-2001--K2": ("updated", ["screenshot_changed"]),
    "kcd-8-2001--K2": ("updated", ["source_document_added"]),
    NEW_ENTRY: ("added", []),
}
EXPECTED_R3 = {
    "kcd-1-2001--K1": ("updated", ["description_changed"]),
    "K37": ("updated", ["name_changed", "version_added"]),
    "kcd-8-2001--K5": ("updated", ["version_changed"]),
}


def read(directory: Path) -> tuple[dict, dict[str, dict]]:
    index = json.loads((directory / "index.json").read_text(encoding="utf-8"))
    documents = {summary["entry"]: json.loads((directory / f"{summary['entry'].lower()}.json").read_text(encoding="utf-8"))
                 for summary in index["entries"]}
    return index, documents


def write(directory: Path, index: dict, documents: dict[str, dict], indent: int | None = 2, sort_keys: bool = True) -> Path:
    directory.mkdir(parents=True)
    for position, summary in enumerate(index["entries"]):
        summary["source_order"] = position
    for entry_id, document in documents.items():
        (directory / f"{entry_id.lower()}.json").write_text(
            json.dumps(document, ensure_ascii=False, indent=indent, sort_keys=sort_keys) + "\n", encoding="utf-8")
    (directory / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=indent, sort_keys=sort_keys) + "\n", encoding="utf-8")
    return directory


def summary_of(index: dict, entry_id: str) -> dict:
    return next(summary for summary in index["entries"] if summary["entry"] == entry_id)


def identify(index, documents, entry_id, name, version, **kinds):
    software = {"software_id": f"software:{name.lower()}", "software_name": name, "version": version,
                "release_id": f"release:{name.lower()}:{version}", "descriptions": [], **kinds}
    documents[entry_id]["software"] = [software]
    documents[entry_id]["curation_status"] = "identified"
    summary = summary_of(index, entry_id)
    summary.update({"curation_status": "identified", "software_name": name, "version": version, **kinds})


def store(publish: Path, public_path: str, content: bytes) -> None:
    target = publish / public_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def rtf_document(publish: Path, key: dict, text: str, path: str) -> dict:
    content = ("{\\rtf1\\ansi " + text + "\\par}").encode("cp1252")
    digest = hashlib.sha256(content).hexdigest()
    public_path = f"store/documents/sha256/{digest[:2]}/{digest}.rtf"
    store(publish, public_path, content)
    return {"key": dict(key), "path": path, "sha256": digest, "size": len(content), "text": text,
            "original": {"sha256": digest, "size": len(content), "public_path": public_path, "media_type": "application/rtf"}}


def candidate_r2(previous: Path, publish: Path, output: Path) -> Path:
    index, documents = read(previous)
    # Pending -> identified with version, content kind and edition.
    identify(index, documents, "K3", "Testkatt", "4.2", content_kind="application", distribution_kind="trial")
    # Pending -> identified; the version stays unknown.
    identify(index, documents, "kcd-8-2001--K1", "Testvakt", "unknown")
    # Known -> unknown version and a corrected name.
    identify(index, documents, "K37", "Winamp (rettet navn, prøvedata)", "unknown")
    # Changed original description.
    documents["kcd-1-2001--K1"]["source_context"]["description"]["value"] = "PRØVEDATA: endret omtale i test-r2."
    # A different screenshot.
    shot = next(asset for asset in documents["kcd-1-2001--K2"]["assets"] if asset["kind"] == "screenshot")
    shot["original"] = synthetic.store_image(publish, synthetic.png(320, 240, "test-r2/new-screenshot"))
    # An attached original text.
    key = documents["kcd-8-2001--K2"]["source_context"]["key"]
    documents["kcd-8-2001--K2"]["source_documents"] = [rtf_document(publish, key, "PRØVEDATA: originaltekst lagt til i test-r2.", "TESTDATA/OMTALE.RTF")]
    # Same bytes on a new storage path: not new content.
    icon = next(asset for asset in documents["kcd-8-2001--K9"]["assets"] if asset["kind"] == "icon")
    moved = "store/moved-in-test-r2/" + icon["original"]["sha256"]
    store(publish, moved, (publish / icon["original"]["public_path"]).read_bytes())
    icon["original"]["public_path"] = moved
    summary_of(index, "kcd-8-2001--K9")["icon"]["original"]["public_path"] = moved
    # A new manifest digest for one CD whose content is unchanged.
    new_manifest = "sha256:" + hashlib.sha256(b"test-r2 manifest").hexdigest()
    for medium in index["media"]:
        if medium["id"] == "kcd-13-2000":
            medium["source_manifest"] = new_manifest
    for summary in index["entries"]:
        if summary["medium_id"] == "kcd-13-2000":
            summary["source_manifest"] = new_manifest
            document = documents[summary["entry"]]
            document["source_manifest"] = new_manifest
            document["source_context"]["key"]["manifest"] = new_manifest
            document["source_context"]["description"]["source_ref"]["manifest"] = new_manifest
    # A new entry, inserted inside its CD so later source order numbers shift.
    template = summary_of(index, "kcd-9-2000--K4")
    position = index["entries"].index(template) + 1
    new_summary = copy.deepcopy(template)
    new_document = copy.deepcopy(documents["kcd-9-2000--K4"])
    title = "Prøvepost lagt til i test-r2"
    new_summary.update({"entry": NEW_ENTRY, "source_entry": "K7", "editorial_title": title})
    key = {"entry": "K7", "manifest": new_document["source_manifest"]}
    new_document.update({"entry": NEW_ENTRY, "source_entry": "K7", "editorial_title": title})
    new_document["source_context"]["key"] = key
    new_document["source_context"]["description"] = {"value": "PRØVEDATA: ny kildepost i test-r2.", "source_ref": {**key, "pointer": "/entries/9/description"}}
    new_document["assets"] = []
    new_summary["icon"] = None
    index["entries"].insert(position, new_summary)
    documents[NEW_ENTRY] = new_document
    # Different layout and key order everywhere.
    return write(output, index, documents, indent=4, sort_keys=False)


def candidate_r3(previous: Path, output: Path) -> Path:
    index, documents = read(previous)
    documents["kcd-1-2001--K1"]["source_context"]["description"]["value"] = "PRØVEDATA: omtalen endret igjen i test-r3."
    identify(index, documents, "K37", "Winamp", "2.77")
    identify(index, documents, "kcd-8-2001--K5", "Winamp", "2.77")
    index["entries"] = [summary for summary in index["entries"] if summary["entry"] != REMOVED_IN_R3]
    del documents[REMOVED_IN_R3]
    return write(output, index, documents, indent=None)


def build_history(work: Path) -> dict:
    """Projections r1-r3, their registers and a shared publish root."""
    r1, publish = synthetic.build_synthetic(work / "r1")
    r2 = candidate_r2(r1, publish, work / "r2-data")
    r3 = candidate_r3(r2, work / "r3-data")
    p1, p2, p3 = (public_updates.load_projection(path) for path in (r1, r2, r3))
    register1 = public_updates.init_register(p1, R1)
    register2 = public_updates.record_release(register1, p1, p2, R2, R2_TIME)
    register3 = public_updates.record_release(register2, p2, p3, R3, R3_TIME)
    paths = {}
    for name, register in (("register1", register1), ("register2", register2), ("register3", register3)):
        paths[name] = work / f"{name}.json"
        paths[name].write_text(public_updates.dumps(register), encoding="utf-8")
    return {"r1": r1, "r2": r2, "r3": r3, "publish": publish, **paths,
            "registers": (register1, register2, register3)}


def package(data: Path, publish: Path, output: Path, updates: Path | None):
    index = json.loads((data / "index.json").read_text(encoding="utf-8"))
    command = [sys.executable, str(ROOT / "scripts" / "build-release.py"), str(data), str(publish),
               "--output", str(output), "--expected-entries", str(len(index["entries"]))]
    if updates:
        command += ["--updates", str(updates)]
    import subprocess
    return subprocess.run(command, capture_output=True, text=True)


def large_fixture(output: Path, entries: int = 5000) -> Path:
    """PRØVEDATA: a servable site with `entries` index rows and one event per row.

    Only the index and the feed are generated; there are no detail documents, so any
    per-entry request would fail visibly. Never packaged, never real history.
    """
    output.mkdir(parents=True)
    (output / "data").mkdir()
    for name in ("index.html", "updates.html", "styles.css", "accessibility.css", "archive-controls.css", "publication.css",
                 "updates.css", "updates-core.js", "updates.js", "landing.js", "landing-updates.js", "collection-core.js", "app.js",
                 "visit-counter.css", "visit-counter-config.js", "visit-counter-core.js", "visit-counter-adapter.js", "visit-counter.js"):
        shutil.copy2(ROOT / name, output / name)
    shutil.copy2(ROOT / "collections.json", output / "collections.json")
    media = [{"id": f"provecd-{n}-1999", "medium": f"Prøve-CD {n}/1999", "publication": synthetic.PUBLICATION,
              "source_manifest": "sha256:" + hashlib.sha256(f"large-{n}".encode()).hexdigest()} for n in range(1, 11)]
    summaries, events = [], []
    releases = [("test-large-2", "2026-05-01T08:00:00Z"), ("test-large-3", "2026-09-01T08:00:00Z")]
    for position in range(entries):
        medium = media[position % len(media)]
        source_entry = f"K{position // len(media) + 1}"
        entry_id = f"{medium['id']}--{source_entry}"
        summaries.append({"entry": entry_id, "medium_id": medium["id"], "medium": medium["medium"], "publication": medium["publication"],
                          "source_entry": source_entry, "source_manifest": medium["source_manifest"], "source_order": position,
                          "curation_status": "identified", "editorial_title": f"Prøvepost {position + 1}",
                          "software_name": f"Prøveprogram {position + 1:04d}", "version": "1.0", "icon": None})
        release_id, published_at = releases[position % 2]
        events.append({"release_id": release_id, "published_at": published_at, "entry": entry_id, "medium_id": medium["id"],
                       "source_entry": source_entry, "type": "added" if position % 5 == 0 else "updated",
                       "changes": [] if position % 5 == 0 else ["version_added"]})
    order = {release_id: n for n, (release_id, _) in enumerate(releases)}
    events.sort(key=lambda event: (order[event["release_id"]], event["entry"]))
    register = {"schema": public_updates.SCHEMA, "projection": public_updates.PROJECTION,
                "baseline": {"release_id": "test-large-1", "projection_sha256": "0" * 64, "entries": []},
                "releases": [{"release_id": release_id, "previous_release_id": previous, "published_at": published_at,
                              "projection_sha256": "1" * 64,
                              "added": sum(e["type"] == "added" and e["release_id"] == release_id for e in events),
                              "updated": sum(e["type"] == "updated" and e["release_id"] == release_id for e in events)}
                             for (release_id, published_at), previous in zip(releases, ["test-large-1", releases[0][0]])],
                "events": events}
    public_updates.validate_register(register)
    index = {"schema": "bootdisk-web-collection-1", "publication": "Bootdisk", "medium": "10 CD-er",
             "media": [{**medium, "legacy_links": False} for medium in media], "entries": summaries}
    (output / "data" / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    (output / "data" / public_updates.FEED_NAME).write_text(json.dumps(register, ensure_ascii=False), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path, help="New directory for the test-r3 package")
    args = parser.parse_args()
    output = args.output.expanduser().absolute()
    if output.exists():
        raise SystemExit(f"Refusing to replace existing path: {output}")
    with tempfile.TemporaryDirectory(prefix="bootdisk-updates-") as temporary:
        history = build_history(Path(temporary))
        result = package(history["r3"], history["publish"], output, history["register3"])
        sys.stdout.write(result.stdout)
        if result.returncode:
            sys.stderr.write(result.stderr)
            raise SystemExit(result.returncode)
    print("PRØVEDATA: invented update history (test-r1..test-r3), not the real archive")


if __name__ == "__main__":
    main()
