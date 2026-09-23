#!/usr/bin/env python3
"""Build a deploy directory, deterministic ZIP and machine-readable release report."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_PREVIEW = ROOT / "scripts" / "build-preview.py"
BUILD_RELEASE = ROOT / "scripts" / "build-release.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(root: Path) -> str:
    """Hash relative paths and file hashes so a generated projection has one identity."""
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def deterministic_zip(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            relative = Path(source.name) / path.relative_to(source)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("publish_root", type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--frontend-data", type=Path)
    source.add_argument("--catalog-root", type=Path)
    parser.add_argument("--ingest-manifest", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--expected-entries", type=int, default=39)
    args = parser.parse_args()
    if args.catalog_root and not args.ingest_manifest:
        parser.error("--ingest-manifest is required with --catalog-root")

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    release = output / f"bootdisk-web-{version}"
    archive = output / f"bootdisk-web-{version}.zip"
    report = output / f"bootdisk-web-{version}.json"

    with tempfile.TemporaryDirectory(prefix="bootdisk-release-") as temporary:
        data = args.frontend_data.expanduser().resolve() if args.frontend_data else Path(temporary) / "data"
        if args.catalog_root:
            subprocess.run([
                sys.executable, str(BUILD_PREVIEW), str(args.catalog_root.expanduser()),
                str(args.ingest_manifest.expanduser()), str(args.publish_root.expanduser() / "publish-manifest.json"),
                "--output", str(data),
            ], check=True)
        subprocess.run([
            sys.executable, str(BUILD_RELEASE), str(data), str(args.publish_root.expanduser()),
            "--output", str(release), "--expected-entries", str(args.expected_entries),
        ], check=True)
        frontend_data_sha256 = sha256_tree(data)

    deterministic_zip(release, archive)
    index = json.loads((release / "data" / "index.json").read_text(encoding="utf-8"))
    documents = [json.loads((release / "data" / f"{e['entry'].lower()}.json").read_text(encoding="utf-8")) for e in index["entries"]]
    coverage = []
    for medium in index.get("media", []):
        selected = [d for d in documents if d.get("medium_id") == medium["id"]]
        coverage.append({"medium_id": medium["id"], "entries": len(selected),
                         **{kind + "_entries": sum(any(a["kind"] == kind for a in d["assets"]) for d in selected)
                            for kind in ("icon", "screenshot")}})
    payload = {
        "schema": "bootdisk-web-release-0.1",
        "version": version,
        "entries": len(index["entries"]),
        "media": index.get("media", []),
        "pending_entries": sum(e.get("curation_status") == "pending" for e in index["entries"]),
        "image_coverage": coverage,
        "description_coverage": [{"medium_id": m["id"], "entries": sum(
            isinstance((d.get("source_context", {}).get("description") or {}).get("value"), str)
            and bool(d["source_context"]["description"]["value"].strip())
            for d in documents if d.get("medium_id") == m["id"])} for m in index.get("media", [])],
        "store_files": sum(1 for path in (release / "store").rglob("*") if path.is_file()),
        "zip": {"name": archive.name, "sha256": sha256(archive), "size": archive.stat().st_size},
        "inputs": {
            "frontend_data_sha256": frontend_data_sha256,
            "ingest_manifest_sha256": sha256(args.ingest_manifest.expanduser()) if args.ingest_manifest else None,
            "publish_manifest_sha256": sha256(args.publish_root.expanduser() / "publish-manifest.json"),
        },
    }
    temporary = report.with_suffix(report.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, report)
    print(f"release zip: {archive}")
    print(f"release report: {report}")


if __name__ == "__main__":
    main()
