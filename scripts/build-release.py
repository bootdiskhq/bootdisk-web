#!/usr/bin/env python3
"""Build a closed, deployable Bootdisk Web directory from generated projections."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
STATIC_FILES = ("index.html", "archive.html", "404.html", "styles.css", "archive-controls.css", "app.js", "archive.js", "VERSION")


def checked_asset_path(value: object) -> PurePosixPath:
    if not isinstance(value, str):
        raise ValueError(f"Asset public_path must be a string, got {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or path.parts[0] != "store" or ".." in path.parts:
        raise ValueError(f"Unsafe asset public_path: {value!r}")
    return path


def referenced_assets(document: dict) -> set[PurePosixPath]:
    paths: set[PurePosixPath] = set()
    for asset in document.get("assets") or []:
        candidates = [asset.get("original") or {}, *(asset.get("derivatives") or [])]
        for candidate in candidates:
            if candidate.get("public_path"):
                paths.add(checked_asset_path(candidate["public_path"]))
    return paths


def package(frontend_data: Path, publish_root: Path, output: Path, expected_entries: int) -> None:
    frontend_data = frontend_data.resolve()
    publish_root = publish_root.resolve()
    output = output.resolve()
    if output in {Path("/").resolve(), ROOT.resolve(), publish_root, frontend_data}:
        raise ValueError(f"Refusing unsafe output directory: {output}")

    index = json.loads((frontend_data / "index.json").read_text(encoding="utf-8"))
    entries = index.get("entries")
    if not isinstance(entries, list) or len(entries) != expected_entries:
        actual = len(entries) if isinstance(entries, list) else "invalid"
        raise ValueError(f"Expected {expected_entries} index entries, got {actual}")
    entry_ids = [item.get("entry") for item in entries]
    if len(set(entry_ids)) != len(entry_ids) or any(not isinstance(item, str) for item in entry_ids):
        raise ValueError("Index entry ids must be unique strings")

    documents: list[tuple[Path, dict]] = []
    assets: set[PurePosixPath] = set()
    for entry_id in entry_ids:
        source = frontend_data / f"{entry_id.lower()}.json"
        document = json.loads(source.read_text(encoding="utf-8"))
        if document.get("entry") != entry_id:
            raise ValueError(f"Entry mismatch in {source.name}")
        documents.append((source, document))
        assets.update(referenced_assets(document))

    missing = [str(path) for path in sorted(assets) if not (publish_root / Path(*path.parts)).is_file()]
    if missing:
        raise FileNotFoundError("Missing published assets: " + ", ".join(missing))

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temporary:
        stage = Path(temporary) / output.name
        (stage / "data").mkdir(parents=True)
        for name in STATIC_FILES:
            shutil.copy2(ROOT / name, stage / name)
        shutil.copy2(frontend_data / "index.json", stage / "data" / "index.json")
        for source, _ in documents:
            shutil.copy2(source, stage / "data" / source.name)
        for path in assets:
            target = stage / Path(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(publish_root / Path(*path.parts), target)
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(stage, output)

    print(f"release entries: {len(entries)}")
    print(f"release assets: {len(assets)}")
    print(f"release directory: {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("frontend_data", type=Path, help="Generated frontend data directory")
    parser.add_argument("publish_root", type=Path, help="Directory containing store/")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "bootdisk-web")
    parser.add_argument("--expected-entries", type=int, default=39)
    args = parser.parse_args()
    package(args.frontend_data, args.publish_root, args.output, args.expected_entries)


if __name__ == "__main__":
    main()
