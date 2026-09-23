#!/usr/bin/env python3
"""Deterministic synthetic archive data for the public collection pages.

Everything here is invented test material shaped like the real seven-disc release:
single-medium projections per CD, a Web collection built by `build-collection.py`,
and a small Publish-like store with real image bytes so the release gate and the HTTP
verifier can run end to end. Titles say "Prøvepost", descriptions say they are
synthetic, and the entry counts deliberately differ from the real discs. It is never
production content and must not be reported as a result for the real archive.

Build a servable synthetic preview package with:

    python tests/synthetic_collection.py OUTPUT_DIRECTORY
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLICATION = "KOMPUTER FOR ALLE"

# (medium id, label, legacy links, source entries). Counts are synthetic on purpose.
SEVEN_DISCS = (
    ("kcd-15-2001", "K-CD 15/2001", True, ["K3", "K13", "K26", "K32", "K37", "K38"]),
    ("kcd-1-2001", "K-CD 1/2001", False, ["K1", "K2", "K3", "K37", "K40"]),
    ("kcd-8-2001", "K-CD 8/2001", False, ["K1", "K2", "K5", "K9"]),
    ("kcd-13-2000", "K-CD 13/2000", False, ["K1", "K2", "K3"]),
    ("kcd-9-2000", "K-CD 9/2000", False, ["K1", "K4"]),
    ("kcd-4-2000", "K-CD 4/2000", False, ["Spil1", "K1D1"]),
    ("kcd-1-2000", "K-CD 1/2000", False, ["Spil1", "Spil2", "K2D1"]),
)

# Entries whose identity the acceptance checks: the old K37 and the new namespaced K37.
SPECIAL = {
    ("kcd-15-2001", "K37"): {"title": "WinAmp 2.76", "software": ("software:winamp", "Winamp", "2.76")},
    ("kcd-1-2001", "K37"): {"title": "WinZip 8.0", "software": ("software:winzip", "WinZip", "8.0")},
    # Same program name on another disc: counted as its own source entry there.
    ("kcd-8-2001", "K5"): {"title": "WinAmp 2.76", "software": ("software:winamp", "Winamp", "2.76")},
    # Source values containing HTML must be shown as text.
    ("kcd-1-2001", "K40"): {"title": '<img src=x onerror="window.__xss=1"> Prøvepost & "sitat"'},
    ("kcd-13-2000", "K3"): {"no_images": True},
}


def png(width: int, height: int, seed: str) -> bytes:
    """A small deterministic RGB PNG; the colour comes from the seed."""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    base = bytes(40 + value // 3 for value in digest[:3])
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            band = ((x // 8) + (y // 8)) % 2
            row += bytes(min(255, channel + (24 if band else 0)) for channel in base)
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def store_image(store_root: Path, data: bytes) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    public_path = f"store/assets/sha256/{digest[:2]}/{digest[2:4]}/{digest}"
    target = store_root / public_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"sha256": digest, "public_path": public_path}


def write_medium(inputs: Path, store_root: Path, medium_id: str, label: str, entries: list[str],
                 publication: str = PUBLICATION, pending_all: bool = False) -> Path:
    data = inputs / medium_id
    data.mkdir(parents=True)
    manifest = "sha256:" + hashlib.sha256(medium_id.encode("utf-8")).hexdigest()
    summaries = []
    for position, source_entry in enumerate(entries):
        special = SPECIAL.get((medium_id, source_entry), {}) if publication == PUBLICATION else {}
        title = special.get("title", f"Prøvepost {position + 1} på {label}")
        software = []
        status = "pending"
        if "software" in special and not pending_all:
            software_id, name, version = special["software"]
            software = [{"software_id": software_id, "software_name": name, "version": version, "descriptions": []}]
            status = "identified"
        assets = []
        if not special.get("no_images"):
            for kind, size in (("icon", (32, 32)), ("screenshot", (320, 240))):
                original = store_image(store_root, png(*size, f"{medium_id}/{source_entry}/{kind}"))
                assets.append({"entry": source_entry, "kind": kind, "source_path": f"{source_entry}/{kind}.png",
                               "original": original, "derivatives": []})
        key = {"entry": source_entry, "manifest": manifest}
        document = {
            "entry": source_entry, "publication": publication, "medium": label, "editorial_title": title,
            "curation_status": status, "software": software, "assets": assets,
            "source_context": {"key": key, "description": {
                "value": f"Syntetisk prøvetekst for {label}, kildepost {source_entry}. Dette er ikke en original CD-omtale.",
                "source_ref": {**key, "pointer": f"/entries/{position}/description"}}},
        }
        (data / f"{source_entry.lower()}.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        summary = {"entry": source_entry, "curation_status": status, "editorial_title": title,
                   "software_name": software[0]["software_name"] if software else None,
                   "version": software[0]["version"] if software else None,
                   "icon": assets[0] if assets else None}
        summaries.append(summary)
    (data / "index.json").write_text(json.dumps({"publication": publication, "medium": label, "entries": summaries},
                                                ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def load_builder():
    spec = importlib.util.spec_from_file_location("build_collection", ROOT / "scripts" / "build-collection.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "scripts"))
    spec.loader.exec_module(module)
    return module


def build_synthetic(work: Path, discs=SEVEN_DISCS, extra: list[tuple[str, str, str, list[str]]] = ()) -> tuple[Path, Path]:
    """Write inputs under `work`; return (collection data directory, publish root).

    `extra` adds media as (id, label, publication, entries), for example an eighth CD or
    a fictional second publication.
    """
    inputs = work / "inputs"
    store_root = work / "publish"
    store_root.mkdir(parents=True)
    media = []
    for medium_id, label, legacy, entries in discs:
        write_medium(inputs, store_root, medium_id, label, entries)
        media.append({"id": medium_id, "data": f"inputs/{medium_id}", "legacy_links": legacy})
    for medium_id, label, publication, entries in extra:
        write_medium(inputs, store_root, medium_id, label, entries, publication=publication)
        media.append({"id": medium_id, "data": f"inputs/{medium_id}"})
    config = work / "collection.json"
    config.write_text(json.dumps({"media": media}, ensure_ascii=False, indent=2), encoding="utf-8")
    output = work / "collection-data"
    load_builder().build_collection(config, output)
    return output, store_root


def package(data: Path, publish_root: Path, output: Path, collections: Path | None = None) -> subprocess.CompletedProcess:
    index = json.loads((data / "index.json").read_text(encoding="utf-8"))
    command = [sys.executable, str(ROOT / "scripts" / "build-release.py"), str(data), str(publish_root),
               "--output", str(output), "--expected-entries", str(len(index["entries"]))]
    if collections:
        command += ["--collections", str(collections)]
    return subprocess.run(command, capture_output=True, text=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path, help="New directory for the synthetic release package")
    args = parser.parse_args()
    output = args.output.expanduser().absolute()
    if output.exists():
        raise SystemExit(f"Refusing to replace existing path: {output}")
    with tempfile.TemporaryDirectory(prefix="bootdisk-synthetic-") as temporary:
        data, publish_root = build_synthetic(Path(temporary))
        result = package(data, publish_root, output)
        sys.stdout.write(result.stdout)
        if result.returncode:
            sys.stderr.write(result.stderr)
            shutil.rmtree(output, ignore_errors=True)
            raise SystemExit(result.returncode)
    print("synthetic preview: invented test data, not the real archive")


if __name__ == "__main__":
    main()
