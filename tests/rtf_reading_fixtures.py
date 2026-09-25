#!/usr/bin/env python3
"""Local test site for the RTF reading view on the detail page.

Builds a servable directory with the page's own static files, the three real development
examples from `tests/fixtures/rtf-reading/real/` and synthetic cases whose titles start
with TESTDATA. Synthetic RTF bytes are generated here so every SHA-256, size and store
path is consistent. Nothing here is release material; see the fixture README.

    python tests/rtf_reading_fixtures.py NEW_DIRECTORY
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "tests/fixtures/rtf-reading/real"
REAL_ENTRIES = ("k37.json", "kcd-1-2001--k1.json", "kcd-8-2001--k5.json")
SITE_FILES = ("index.html", "archive.html", "collection.html", "styles.css", "accessibility.css", "archive-controls.css",
              "entry-controls.css", "publication.css", "app.js", "archive.js", "landing.js", "collection.js",
              "collection-core.js", "collections.json")
PUBLICATION = "TESTDATA"
MEDIUM = "TESTDATA-CD"
MANIFEST = "sha256:" + "7e" * 32
LONG_NAME = "TestdataMedEtUrimeligLangtKatalognavnUtenMellomrom/" + "Programbeskrivelse" * 6 + ".rtf"

# The long text: several paragraphs, Norwegian letters, typographic quotes, a very long word
# and HTML-looking source text that must appear literally and never become markup.
LONG_TEXT = (
    "TESTDATA – lang originaltekst \n"
    "Første avsnitt: Æ, Ø og Å, æ, ø og å, «sitat» og ”Play”-knappen. \n\n"
    "Andre avsnitt beskriver <img src=x onerror=\"window.__rtfXss=1\"> og <b>fet</b> & &amp; bokstavelig.\n\n"
    "Et langt ord: " + "Programvarebevaringsprosjektdokumentasjon" * 4 + ".\n\n"
    + "\n\n".join(f"Avsnitt {n}: Denne teksten er oppdiktet og finnes bare i testdata. Den skal vises uendret, "
                  "med linjeskift og mellomrom slik de står." for n in range(4, 12))
    + "\n"
)


def rtf_bytes(label: str) -> bytes:
    """Stand-in original bytes: never parsed by the page, only downloaded and hashed."""
    return ("{\\rtf1\\ansi\\ansicpg1252{\\fonttbl{\\f0 Arial;}}\\f0 " + label + "\\par}").encode("cp1252")


def published(key: dict, path: str, text: str | None, content: bytes, warning: str | None = None, **overrides) -> tuple[dict, bytes]:
    digest = hashlib.sha256(content).hexdigest()
    doc = {
        "key": dict(key), "pointer": "/entries/0/files/discovered/description_rtf", "path": path,
        "sha256": digest, "size": len(content), "method": "rtf-ansi-text-terminal-nul-1",
        "text": text, "warning": warning, "observation_manifest": "sha256:" + "0" * 64,
        "original": {"sha256": digest, "size": len(content), "object_key": f"documents/sha256/{digest[:2]}/{digest}.rtf",
                     "public_path": f"store/documents/sha256/{digest[:2]}/{digest}.rtf", "media_type": "application/rtf"},
    }
    for field, value in overrides.items():
        if field.startswith("original_"):
            doc["original"][field.removeprefix("original_")] = value
        else:
            doc[field] = value
    return doc, content


def synthetic_entry(entry: str, title: str, description: str | None, documents: list | None) -> dict:
    key = {"manifest": MANIFEST, "entry": entry}
    context = {"key": key, "issues": {"source_ref": key, "value": []}, "menu_groups": {"source_ref": key, "value": ["Testdata"]}}
    if description is not None:
        context["description"] = {"source_ref": {**key, "pointer": "/entries/0/raw/Global"}, "value": description}
    document = {"entry": entry, "editorial_title": title, "publication": PUBLICATION, "medium": MEDIUM,
                "curation_status": "pending", "software": [], "assets": [], "source_context": context}
    if documents is not None:
        document["source_documents"] = documents
    return document


def synthetic_cases() -> tuple[list[dict], dict[str, bytes]]:
    """(entry documents, store files). Each case is named after the matrix row it serves."""
    store: dict[str, bytes] = {}
    entries = []

    def add(entry, title, description, docs):
        attached = []
        for doc, content in docs or ():
            attached.append(doc)
            if content is not None:
                store[doc["original"]["public_path"]] = content
        entries.append(synthetic_entry(entry, title, description, attached if docs is not None else None))

    def key(entry):
        return {"manifest": MANIFEST, "entry": entry}

    add("K901", "TESTDATA Kort omtale og lang RTF", "TESTDATA: kort menyomtale.",
        [published(key("K901"), LONG_NAME, LONG_TEXT, rtf_bytes("TESTDATA lang"))])
    add("K902", "TESTDATA Samme tekst, annen whitespace", "TESTDATA   samme omtale\nmed  annen whitespace.",
        [published(key("K902"), "Samme/No.rtf", "TESTDATA samme omtale \n\n med annen whitespace. \n", rtf_bytes("TESTDATA samme"))])
    add("K903", "TESTDATA Tekst kan ikke vises", "TESTDATA: menyomtalen finnes.",
        [published(key("K903"), "Ukjent/No.rtf", None, rtf_bytes("TESTDATA null"), warning="unsupported RTF font charset")])
    add("K904", "TESTDATA Ingen RTF", "TESTDATA: posten har ingen originaldokumenter.", None)
    add("K905", "TESTDATA Tom dokumentliste", "TESTDATA: tom liste.", [])
    # Row 8: unsafe addresses. The text is readable, so the document still shows, but inert.
    unsafe = []
    for label, href in (("ekstern", "https://example.invalid/store/documents/x.rtf"),
                        ("traversering", "store/documents/sha256/ab/../../../../etc/passwd.rtf"),
                        ("skript", "javascript:window.__rtfLink=1"),
                        ("protokollrelativ", "//example.invalid/a.rtf")):
        doc, _ = published(key("K906"), f"Utrygg/{label}.rtf", f"TESTDATA utrygg adresse: {label}.", rtf_bytes(label),
                           original_public_path=href)
        unsafe.append((doc, None))
    # Right shape, but the hash in the path is not the file's hash.
    doc, content = published(key("K906"), "Utrygg/feil-hash.rtf", "TESTDATA utrygg adresse: feil hash.", rtf_bytes("feil"))
    doc["original"]["public_path"] = f"store/documents/sha256/ab/ab{'0' * 62}.rtf"
    unsafe.append((doc, None))
    # Correct store path, but not declared as RTF: it must not be offered as the original.
    doc, _ = published(key("K906"), "Utrygg/feil-type.rtf", "TESTDATA utrygg adresse: feil type.", rtf_bytes("type"),
                       original_media_type="text/html")
    unsafe.append((doc, None))
    add("K906", "TESTDATA Utrygge adresser", "TESTDATA: menyomtale.", unsafe)
    # A document bound to another source entry must not be shown on this one.
    other, content = published({"manifest": MANIFEST, "entry": "K999"}, "Annen/No.rtf", "TESTDATA fra en annen kildepost.", rtf_bytes("annen"))
    add("K907", "TESTDATA Dokument fra annen kildepost", "TESTDATA: menyomtale.", [(other, content)])
    # Unsafe address and no text: nothing useful to offer, so nothing is shown.
    empty, _ = published(key("K908"), "Utrygg/tom.rtf", None, rtf_bytes("tom"), original_public_path="https://example.invalid/tom.rtf")
    add("K908", "TESTDATA Utrygg adresse uten tekst", "TESTDATA: menyomtale.", [(empty, None)])
    return entries, store


def real_entries() -> list[dict]:
    return [json.loads((REAL / name).read_text(encoding="utf-8")) for name in REAL_ENTRIES]


def build_site(output: Path) -> dict:
    """Write the test site to a new directory and return its index."""
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"{output} must be a new directory")
    (output / "data").mkdir(parents=True)
    for name in SITE_FILES:
        shutil.copy2(ROOT / name, output / name)
    shutil.copytree(REAL / "store", output / "store")
    entries = []
    for document in real_entries():
        served = copy.deepcopy(document)
        served["assets"] = []  # the image bytes were not delivered with the examples
        entries.append(served)
    synthetic, store = synthetic_cases()
    entries.extend(synthetic)
    for public_path, content in store.items():
        target = output / public_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    for document in entries:
        (output / "data" / f"{document['entry'].lower()}.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    index = {"publication": PUBLICATION, "medium": MEDIUM, "testdata": True,
             "entries": [{"entry": d["entry"], "curation_status": d["curation_status"], "editorial_title": d["editorial_title"]} for d in entries]}
    (output / "data" / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output
    index = build_site(output)
    print(f"TESTDATA site with {len(index['entries'])} entries: {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
