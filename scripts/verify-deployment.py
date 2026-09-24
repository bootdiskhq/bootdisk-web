#!/usr/bin/env python3
"""Verify a deployed Bootdisk Web release over HTTP without browser internals."""
from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from collection_registry import collection_urls

PRODUCTION = "https://bootdisk.no/"
ROOT_CANONICAL = '<link id="canonical-url" rel="canonical" href="https://bootdisk.no/">'
# Local curation, the automatic first-pass queue, their prototype data layers and test fixtures
# must never be public.
NOT_PUBLIC = ("curate.html", "curate.js", "curate-adapter.js", "curate-live-adapter.js", "overview.html",
              "overview-sample.js", "overview-adapter.js", "overview.js", "curator-labels.js", "curator-navigation.js",
              "tests/fixtures/curator-fixtures-v1.json", "scripts/build-release.py",
              "automation.html", "automation.css", "automation.js", "automation-core.js", "automation-adapter.js",
              "automation-sample.js", "tests/fixtures/automation-queue-v1.json", "docs/automation-queue-v1.md")


def fetch(base_url: str, path: str, expected_status: int = 200) -> bytes:
    url = urljoin(base_url.rstrip("/") + "/", path)
    request = Request(url, headers={"User-Agent": "bootdisk-deploy-verifier/0.1"})
    try:
        with urlopen(request, timeout=20) as response:
            status = response.status
            body = response.read()
    except HTTPError as error:
        status = error.code
        body = error.read()
    if status != expected_status:
        raise RuntimeError(f"Expected HTTP {expected_status} from {url}, got {status}")
    return body


def asset_paths(document: dict) -> set[str]:
    paths: set[str] = set()
    for asset in document.get("assets") or []:
        for item in [asset.get("original") or {}, *(asset.get("derivatives") or [])]:
            path = item.get("public_path")
            if path:
                paths.add(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", help="Deployed root, for example https://bootdisk.no/")
    parser.add_argument("--expected-entries", type=int, default=39)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()

    archive = fetch(args.base_url, "archive.html").decode("utf-8")
    if '<link rel="canonical" href="https://bootdisk.no/archive.html">' not in archive:
        raise RuntimeError("Archive canonical URL is missing or incorrect")
    for path in ("", "index.html"):
        front = fetch(args.base_url, path).decode("utf-8")
        if ROOT_CANONICAL not in front or "window.location.replace" in front:
            raise RuntimeError(f"Front page at /{path} lacks the root canonical URL or redirects")
    fetch(args.base_url, "index.html?entry=K37")
    for path in NOT_PUBLIC:
        fetch(args.base_url, path, expected_status=404)
    robots = fetch(args.base_url, "robots.txt").decode("utf-8")
    if "Sitemap: https://bootdisk.no/sitemap.xml" not in robots:
        raise RuntimeError("robots.txt does not advertise the production sitemap")
    sitemap = ET.fromstring(fetch(args.base_url, "sitemap.xml"))
    fetch(args.base_url, "definitely-not-a-bootdisk-page", expected_status=404)
    index = json.loads(fetch(args.base_url, "data/index.json"))
    entries = index.get("entries")
    if not isinstance(entries, list) or len(entries) != args.expected_entries:
        raise RuntimeError(f"Expected {args.expected_entries} entries, got {len(entries) if isinstance(entries, list) else 'invalid'}")
    registry = json.loads(fetch(args.base_url, "collections.json"))
    collection_pages = collection_urls(registry, index, PRODUCTION)
    for url in collection_pages:
        page = fetch(args.base_url, url.removeprefix(PRODUCTION)).decode("utf-8")
        if 'src="collection.js"' not in page:
            raise RuntimeError(f"Collection page is not served: {url}")
    sitemap_locations = [node.text for node in sitemap.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    sitemap_urls = set(sitemap_locations)
    detail_urls = {f"{PRODUCTION}index.html?entry={entry['entry']}" for entry in entries}
    expected_urls = {PRODUCTION, f"{PRODUCTION}archive.html", *collection_pages, *detail_urls}
    if len(sitemap_locations) != len(sitemap_urls) or sitemap_urls != expected_urls:
        raise RuntimeError("Sitemap URLs do not match the front page, archive, collections and archive index")
    if {url for url in sitemap_urls if "index.html?entry=" in url} != detail_urls:
        raise RuntimeError("Sitemap detail links do not match the archive index exactly")

    def fetch_entry(entry: dict) -> tuple[str, dict]:
        entry_id = entry["entry"]
        document = json.loads(fetch(args.base_url, f"data/{entry_id.lower()}.json"))
        if document.get("entry") != entry_id:
            raise RuntimeError(f"Entry mismatch for {entry_id}")
        return entry_id, document

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        documents = list(executor.map(fetch_entry, entries))
    assets = set().union(*(asset_paths(document) for _, document in documents))

    def verify_asset(path: str) -> str:
        body = fetch(args.base_url, path)
        filename = path.rsplit("/", 1)[-1]
        expected_hash = filename.rsplit(".", 1)[0]
        actual_hash = hashlib.sha256(body).hexdigest()
        if actual_hash != expected_hash:
            raise RuntimeError(f"Content hash mismatch for {path}")
        return path

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(verify_asset, sorted(assets)))

    print(f"deployment entries: {len(entries)}")
    print(f"deployment assets: {len(assets)}")
    print(f"deployment collections: {len(collection_pages)}")
    print("deployment verification: passed")


if __name__ == "__main__":
    main()
