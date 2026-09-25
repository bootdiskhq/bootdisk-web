#!/usr/bin/env python3
"""Build a closed, deployable Bootdisk Web directory from generated projections."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from xml.sax.saxutils import escape
from pathlib import Path, PurePosixPath

from collection_registry import collection_urls
from frontend_contract import validate_frontend_data

ROOT = Path(__file__).resolve().parents[1]
STATIC_FILES = ("index.html", "archive.html", "collection.html", "404.html", "styles.css", "accessibility.css", "archive-controls.css",
                "entry-controls.css", "publication.css", "app.js", "archive.js", "landing.js", "collection.js", "collection-core.js",
                "visit-counter.css", "visit-counter-config.js", "visit-counter-core.js", "visit-counter-adapter.js",
                "visit-counter.js", "VERSION")
DEFAULT_COLLECTIONS = ROOT / "collections.json"
DEFAULT_BASE_URL = "https://bootdisk.no/"


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
    for doc in document.get("source_documents", []):
        paths.add(checked_asset_path(doc["original"]["public_path"]))
    return paths


def discovery_files(stage: Path, entry_ids: list[str], base_url: str, collection_pages: list[str] = ()) -> None:
    base_url = base_url.rstrip("/") + "/"
    urls = [base_url, f"{base_url}archive.html", *collection_pages, *(f"{base_url}index.html?entry={entry_id}" for entry_id in entry_ids)]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "".join(f"  <url><loc>{escape(url)}</loc></url>\n" for url in urls)
    sitemap += "</urlset>\n"
    (stage / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (stage / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base_url}sitemap.xml\n", encoding="utf-8")


def validate_image_coverage(index, documents):
    """A readable archive is not complete when a whole medium lost its images."""
    for medium in index.get("media", []):
        entries = [doc for _, doc in documents if doc.get("medium_id") == medium["id"]]
        assets = [asset for doc in entries for asset in doc["assets"]]
        exception = medium.get("images_unavailable_reason")
        if not assets and not (isinstance(exception, str) and exception.strip()):
            raise ValueError(f"No images for medium {medium['id']}; explicit source limitation required")
        requirements = medium.get("image_requirements", {})
        for kind in requirements.get("all_entries", []):
            if kind not in ("icon", "screenshot"):
                raise ValueError("Unknown required image kind")
            missing = [doc["entry"] for doc in entries if not any(a["kind"] == kind for a in doc["assets"])]
            if missing:
                raise ValueError(f"Missing {kind}: {', '.join(missing)}")
        for kind, minimum in requirements.get("minimum_counts", {}).items():
            if kind not in ("icon", "screenshot") or type(minimum) is not int or minimum < 0:
                raise ValueError("Invalid image coverage requirement")
            covered = sum(any(a["kind"] == kind for a in doc["assets"]) for doc in entries)
            if covered < minimum:
                raise ValueError(f"Insufficient {kind} coverage for {medium['id']}: {covered} < {minimum}")
        minimum = medium.get("description_requirements", {}).get("minimum_count", 0)
        if type(minimum) is not int or minimum < 0:
            raise ValueError("Invalid description coverage requirement")
        descriptions = [(doc.get("source_context", {}).get("description") or {}).get("value") for doc in entries]
        covered = sum(isinstance(text, str) and bool(text.strip()) for text in descriptions)
        if covered < minimum:
            raise ValueError(f"Insufficient description coverage for {medium['id']}: {covered} < {minimum}")


def load_registry(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"Collection registry not found: {path}") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"Collection registry {path} is not valid JSON: {error}") from None


def package(frontend_data: Path, publish_root: Path, output: Path, expected_entries: int, base_url: str = DEFAULT_BASE_URL,
            collections: Path = DEFAULT_COLLECTIONS) -> None:
    frontend_data = frontend_data.resolve()
    publish_root = publish_root.resolve()
    output = output.resolve()
    if output in {Path("/").resolve(), ROOT.resolve(), publish_root, frontend_data}:
        raise ValueError(f"Refusing unsafe output directory: {output}")

    index = validate_frontend_data(frontend_data, expected_entries)
    entries = index["entries"]
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

    validate_image_coverage(index, documents)
    registry = load_registry(collections)
    collection_pages = collection_urls(registry, index, base_url.rstrip("/") + "/")

    missing = [str(path) for path in sorted(assets) if not (publish_root / Path(*path.parts)).is_file()]
    if missing:
        raise FileNotFoundError("Missing published assets: " + ", ".join(missing))

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as temporary:
        stage = Path(temporary) / output.name
        (stage / "data").mkdir(parents=True)
        for name in STATIC_FILES:
            shutil.copy2(ROOT / name, stage / name)
        shutil.copy2(collections, stage / "collections.json")
        discovery_files(stage, entry_ids, base_url, collection_pages)
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
    print(f"release collections: {len(collection_pages)}")
    print(f"release directory: {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("frontend_data", type=Path, help="Generated frontend data directory")
    parser.add_argument("publish_root", type=Path, help="Directory containing store/")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "bootdisk-web")
    parser.add_argument("--expected-entries", type=int, default=39)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--collections", type=Path, default=DEFAULT_COLLECTIONS, help="Collection registry (default: collections.json)")
    args = parser.parse_args()
    package(args.frontend_data, args.publish_root, args.output, args.expected_entries, args.base_url, args.collections)


if __name__ == "__main__":
    main()
