#!/usr/bin/env python3
"""Copy the menu selection of finished CD images into separate folders.

One image:

    python3 scripts/extract-cd-menu-source.py --image IMAGE.iso --manifest MANIFEST.json --dest DEST

Every medium of a matrix config, with the image paths taken from intake configs
(``bootdisk-intake-run-1``, ``media[].id`` and ``media[].iso``):

    python3 scripts/extract-cd-menu-source.py --matrix MATRIX.json --intake RUN.json [--intake ...] \\
        --dest-root MENU_SOURCES

Only ``default.html``, the pages and stylesheets in ``html/`` and raster images are
read from an image, with ``bsdtar`` and read access. Programs, PDF files, video,
scripts and everything else stay on the image. Each copied file must match the size
and SHA-256 in the ingest manifest, and the image itself must match the manifest's
media hash (``--skip-image-hash`` only for repeated local runs). A destination must not
exist yet; in batch mode an existing ``MENU_SOURCES/<medium>`` is left alone and
reported as ``exists``. Each copy is made in a temporary sibling folder and renamed
when it is complete.

Use finished images. Do not point this at the CD drive, the ISO queue or files that
are still being copied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

RASTER = (".png", ".gif", ".jpg", ".jpeg")


def selected(path: str) -> bool:
    lower = path.lower()
    parts = PurePosixPath(lower).parts
    if lower == "default.html":
        return True
    if len(parts) == 2 and parts[0] == "html" and lower.endswith((".html", ".css")):
        return True
    return lower.endswith(RASTER)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def extract(image: Path, manifest_path: Path, dest: Path, bsdtar: str, skip_image_hash: bool = False) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if dest.exists():
        return {"status": "exists", "dest": str(dest)}
    if not image.is_file():
        return {"status": "blocked", "reason": f"{image} er ikke en fil"}
    expected = (manifest.get("media") or {}).get("sha256")
    if not skip_image_hash:
        actual = file_hash(image)
        if actual != expected:
            return {"status": "blocked", "reason": "avbildningen stemmer ikke med manifestet", "image_sha256": actual, "manifest_media_sha256": expected}
    inventory = {item["path"]: item for item in manifest["file_inventory"] if selected(item["path"])}
    listing = subprocess.run([bsdtar, "-t", "-f", str(image)], check=True, capture_output=True, text=True).stdout.splitlines()
    members = {}
    for member in listing:
        name = member[2:] if member.startswith("./") else member
        if name and not name.endswith("/"):
            members.setdefault(name.casefold(), []).append(member)
    wanted, problems = {}, []
    for path in inventory:
        matches = members.get(path.casefold(), [])
        if len(matches) != 1:
            problems.append({"path": path, "reason": "finnes ikke i avbildningen" if not matches else "tvetydig navn i avbildningen"})
            continue
        wanted[path] = matches[0]
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{dest.name}-", dir=dest.parent))
    try:
        raw = temporary / ".raw"
        raw.mkdir()
        names = sorted(set(wanted.values()))
        for start in range(0, len(names), 200):
            subprocess.run([bsdtar, "-x", "-f", str(image), "-C", str(raw), "--no-same-owner", "--no-same-permissions", "--", *names[start:start + 200]], check=True)
        copied = 0
        for path, member in sorted(wanted.items()):
            source = raw / member.removeprefix("./")
            item = inventory[path]
            if source.is_symlink() or not source.is_file() or source.stat().st_size != item["size"] or file_hash(source) != item["sha256"]:
                problems.append({"path": path, "reason": "byte stemmer ikke med manifestet"})
                continue
            target = temporary / path
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            copied += 1
        shutil.rmtree(raw)
        temporary.rename(dest)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"status": "ok" if not problems else "with_problems", "copied": copied, "selected": len(inventory), "problems": problems}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--image", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--dest", type=Path)
    parser.add_argument("--matrix", type=Path, help="matrix config (scripts/find-cd-menu-manifests.py) for batch mode")
    parser.add_argument("--intake", type=Path, action="append", default=[], help="intake config with media[].id and media[].iso")
    parser.add_argument("--dest-root", type=Path)
    parser.add_argument("--bsdtar", default=shutil.which("bsdtar") or "/usr/bin/tar")
    parser.add_argument("--skip-image-hash", action="store_true")
    args = parser.parse_args(argv)
    if args.matrix:
        if not args.intake or not args.dest_root:
            parser.error("--matrix needs --intake and --dest-root")
        images = {}
        for path in args.intake:
            for medium in json.loads(path.read_text(encoding="utf-8")).get("media", []):
                if medium.get("id") and medium.get("iso"):
                    images.setdefault(medium["id"], Path(medium["iso"]))
        worst = 0
        for row in json.loads(args.matrix.read_text(encoding="utf-8"))["media"]:
            image = images.get(row["id"])
            if image is None:
                result = {"status": "blocked", "reason": "ingen avbildning i intake-konfigurasjonene"}
            else:
                try:
                    result = extract(image, Path(row["manifest"]), args.dest_root / row["id"], args.bsdtar, args.skip_image_hash)
                except (OSError, subprocess.CalledProcessError, ValueError, KeyError) as error:  # one disc must not stop the rest
                    result = {"status": "blocked", "reason": f"{type(error).__name__}: {error}"}
            print(json.dumps({"medium_id": row["id"], **result}, ensure_ascii=False), flush=True)
            worst = max(worst, {"ok": 0, "exists": 0, "with_problems": 2}.get(result["status"], 1))
        return worst
    if not (args.image and args.manifest and args.dest):
        parser.error("give --image, --manifest and --dest, or --matrix, --intake and --dest-root")
    result = extract(args.image, args.manifest, args.dest, args.bsdtar, args.skip_image_hash)
    print(json.dumps(result, ensure_ascii=False))
    return {"ok": 0, "with_problems": 2}.get(result["status"], 1)


if __name__ == "__main__":
    sys.exit(main())
