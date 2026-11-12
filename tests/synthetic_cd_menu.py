#!/usr/bin/env python3
"""PRØVEDATA for the original CD menus (docs/cd-menu.md).

Tiny, invented menus in the K-CD template (``default.html`` with ``#wrapper``,
``#menu`` and ``#contentwrapper``, pages in ``html/``) with one hard case each: a
program page, articles and a video course on shared pages, a page with an undefined
Windows-1252 byte, an image missing on the CD, two names that differ only in case,
scripts, event handlers, frames, forms, installers, PDF and video controls, external
links and a path that tries to leave the CD. No text, image or layout comes from a
real CD.

The archive around the menus is built through the real gates (build-collection.py and
build-release.py) and the menus through scripts/cd-menu-matrix.py, so the source posts
carry the SHA-256 of the invented manifests exactly as published data does.

    python tests/synthetic_cd_menu.py NEW_DIRECTORY
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
PUBLICATION = "PRØVEDATA CD-MENY"
REGISTRY = {"schema": "bootdisk-web-collections-1", "collections": [{
    "id": "provedata-cd-meny", "title": "Prøvedata for CD-menyer", "publication_values": [PUBLICATION],
    "summary": "PRØVEDATA: oppdiktet samling for test av originalmenyer. Ikke produksjonsinnhold.",
    "lede": "PRØVEDATA: oppdiktet samling.", "history": [], "sources": []}]}

WITH_MENU = ("prove-1-2099", "prove-2-2099")
MEDIA = [("prove-1-2099", "Prøve-CD 1/2099"), ("prove-2-2099", "Prøve-CD 2/2099"), ("prove-3-2099", "Prøve-CD 3/2099")]


def png(rgb=(200, 40, 40)) -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(rgb) * 4 for _ in range(4))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


GIF = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"


def page(title: str, content: str, prefix: str = "../") -> str:
    return (f'<html><head><meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1"><title>{title}</title>'
            f'<link rel="stylesheet" href="{prefix}html/main.css"><script src="{prefix}js/menu.js"></script></head>'
            f'<body onload="start()"><div id="wrapper"><div id="menu"><ul>'
            f'<li><a href="{prefix}default.html">Forside</a></li><li><a href="{prefix}html/program1.html">Program</a></li>'
            f'<li><a href="{prefix}html/articles.html">Artikler</a></li><li><a href="{prefix}html/videos.html">Videokurs</a></li></ul>'
            f'<div id="search"><input type="text" id="q"><input type="button" id="searchbutton" value="Søk" onclick="search()"></div></div>'
            f'<div id="contentwrapper">{content}</div></div><style>.z{{color:red}}</style><script>track()</script></body></html>')


def menu_files(label: str, word: str) -> dict[str, bytes]:
    """The files of one invented CD, keyed by their path on the CD."""
    front = page(label, '<div id="content"><h1>Velkommen til PRØVEDATA</h1><p style="float:left;background:url(http://example.invalid/x.gif)">'
                        'Denne utgaven er CD 17.</p><img src="img/logo.png" width="40" height="20" alt="Logo">'
                        '<img src="img/gone.png" alt="Borte"><img src="img/DUP.png" alt="Tvetydig"><img src="http://example.invalid/t.gif">'
                        '<iframe src="http://example.invalid/"></iframe><a href="html/broken.html">Ødelagt side</a> '
                        '<a href="http://www.example.invalid/">Nettsted</a> <a href="install/setup.exe">Installer</a> '
                        '<a href="#" onclick="window.print()">Skriv ut</a> <form action="http://example.invalid/"><input type="submit" value="Send"></form></div>', "")
    program = page(f"{word} program", f'<div id="content"><h1>{word}program Én</h1><img src="../img/shot.jpg" alt="Skjermbilde">'
                                     '<p onclick="steal()">PRØVEDATA: oppdiktet omtale.</p><a href="../install/setup.exe">Installer</a> '
                                     "<a href=\"javascript:openPdf('guide.pdf')\">Les PDF</a> <input type=\"button\" value=\"Se video\" onclick=\"show('v.flv')\">"
                                     '<a href="../%2e%2e/%2e%2e/etc/passwd">Rømning</a> <a href="..\\..\\x.html">Bakstrek</a> '
                                     '<a href="Articles.html#a">Til artiklene</a></div>')
    articles = page("Artikler", "".join(
        f'<div class="guide"><div class="guideheadline">{word}artikkel {name}</div><p>PRØVEDATA: om {name}.</p>'
        f'<input type="button" value="Les veiledning" onclick="article(\'{name}.pdf\')"></div>' for name in ("A", "B")))
    videos = page("Videokurs", f'<div class="video"><div class="videoheadline">{word}video C</div><input type="button" value="Spill av" onclick="show(\'c.flv\')"></div>')
    broken = page("Ødelagt", f'<div id="content"><h1>{word}program Ødelagt</h1></div>').encode("cp1252").replace(b"</h1>", b"\x81</h1>")
    css = ("body{background:#fff url(../img/bg.gif)}.x{background:url('../img/missing-css.png')}"
           ".y{width:expression(alert(1))}@import url(http://example.invalid/y.css);#wrapper{width:600px}")
    return {"default.html": front.encode("cp1252"), "html/program1.html": program.encode("cp1252"),
            "html/articles.html": articles.encode("cp1252"), "html/videos.html": videos.encode("cp1252"),
            "html/broken.html": broken, "html/main.css": css.encode("cp1252"), "img/logo.png": png(),
            "img/bg.gif": GIF, "img/shot.jpg": png((40, 40, 200)), "img/Dup.png": png((1, 2, 3)), "img/dup.png": png((3, 2, 1)),
            "install/setup.exe": b"MZ PROVEDATA", "js/menu.js": b"alert(1)"}


ENTRIES = [("K1", "html/program1.html", "{w}program Én", "Programmer"), ("K2", "html/articles.html", "{w}artikkel A", "Artikler"),
           ("K3", "html/articles.html", "{w}artikkel B", "Artikler"), ("K4", "html/videos.html", "{w}video C", "Videokurs"),
           ("K5", "html/broken.html", "{w}program Ødelagt", "Programmer")]


def write_menu(root: Path, medium_id: str, label: str) -> tuple[Path, Path, str]:
    """Write the extracted selection and the observe manifest for one invented CD."""
    word = "Prøve" if medium_id == "prove-1-2099" else "Annen"
    files = menu_files(label, word)
    source = root / "menu-source" / medium_id
    for name, data in files.items():
        if name.endswith((".html", ".css", ".png", ".gif", ".jpg")):
            (source / name).parent.mkdir(parents=True, exist_ok=True)
            (source / name).write_bytes(data)
    entries = [{"source_id": sid, "normalized": {"title": title.format(w=word)},
                "evidence": {"html_menu": {"page": path, "observation": {"title": title.format(w=word), "category": category}}}}
               for sid, path, title, category in ENTRIES]
    manifest = {"schema": "bootdisk-ingest-manifest-1", "media": {"sha256": hashlib.sha256(medium_id.encode()).hexdigest()},
                "source": {"format": "kcd-html-menu-1", "documents": {path: {"raw_base64": base64.b64encode(files[path]).decode()}
                                                                      for path in sorted({row[1] for row in ENTRIES})}},
                "file_inventory": [{"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in sorted(files.items())],
                "entries": entries}
    path = root / "manifests" / medium_id / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return path, source, "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def projection(root: Path, medium_id: str, label: str, manifest: str) -> Path:
    data = root / "projection" / medium_id
    data.mkdir(parents=True)
    word = "Prøve" if medium_id == "prove-1-2099" else "Annen"
    rows = []
    for position, (sid, _page, title, category) in enumerate(ENTRIES):
        title = title.format(w=word)
        key = {"entry": sid, "manifest": manifest}
        context = {"key": key, "description": {"source_ref": {**key, "pointer": f"/entries/{position}/raw"}, "value": f"PRØVEDATA: menyomtale for {title}."},
                   "menu_groups": {"source_ref": {**key, "pointer": f"/entries/{position}/normalized/categories"}, "value": [category]}}
        document = {"entry": sid, "publication": PUBLICATION, "medium": label, "editorial_title": title, "curation_status": "pending",
                    "software": [], "assets": [], "source_context": context}
        (data / f"{sid.lower()}.json").write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        rows.append({"entry": sid, "editorial_title": title, "curation_status": "pending", "software_name": None, "version": None,
                     "identification_status": None, "content_kind": None, "distribution_kind": None, "source_catalog_status": None, "icon": None})
    (data / "index.json").write_text(json.dumps({"publication": PUBLICATION, "medium": label, "entries": rows}, ensure_ascii=False), encoding="utf-8")
    return data


def build(output: Path, work: Path) -> dict:
    """Build the archive into the new directory ``output``; menu inputs stay in ``work``."""
    spec = importlib.util.spec_from_file_location("collection_builder", ROOT / "scripts" / "build-collection.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    menus, media = {}, []
    for medium_id, label in MEDIA:
        if medium_id in WITH_MENU:
            manifest, source, ref = write_menu(work, medium_id, label)
            menus[medium_id] = {"manifest": manifest, "source": source, "ref": ref}
        else:
            ref = "sha256:" + hashlib.sha256(f"cd-menu/{medium_id}".encode()).hexdigest()
        media.append({"id": medium_id, "data": str(projection(work, medium_id, label, ref)), "legacy_links": False,
                      "images_unavailable_reason": "PRØVEDATA uten bilder"})
    (work / "collection.json").write_text(json.dumps({"media": media}, ensure_ascii=False), encoding="utf-8")
    builder.build_collection(work / "collection.json", work / "data")
    (work / "publish").mkdir()
    (work / "collections.json").write_text(json.dumps(REGISTRY, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "build-release.py"), str(work / "data"), str(work / "publish"),
                             "--output", str(output), "--expected-entries", str(len(ENTRIES) * len(MEDIA)),
                             "--collections", str(work / "collections.json")], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    config = {"schema": "bootdisk-cd-menu-matrix-1",
              "media": [{"id": medium, "manifest": str(item["manifest"]), "source": str(item["source"])} for medium, item in menus.items()]}
    (work / "matrix.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return {"menus": menus, "config": work / "matrix.json", "index": output / "data" / "index.json"}


def build_menus(output: Path, work: Path, approve=WITH_MENU) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "cd-menu-matrix.py"), "--config", str(work / "matrix.json"),
                           "--index", str(output / "data" / "index.json"), "--site", str(output), "--report-dir", str(work / "report"),
                           "--approve", ",".join(approve)], capture_output=True, text=True, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path)
    parser.add_argument("--work", type=Path, help="keep the invented menu inputs here (default: a new temporary folder)")
    args = parser.parse_args()
    output = args.output.expanduser().absolute()
    if output.exists():
        raise SystemExit(f"Refusing to replace existing path: {output}")
    if args.work:
        args.work.mkdir(parents=True)
    work = args.work or Path(tempfile.mkdtemp(prefix="bootdisk-cd-menu-"))
    build(output, work)
    build_menus(output, work)
    print(f"PRØVEDATA: {len(MEDIA)} invented CDs, {len(WITH_MENU)} with an invented menu, in {output}. Not the real archive.")


if __name__ == "__main__":
    main()
