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
    fetch(args.base_url, "index.html?entry=K37")
    robots = fetch(args.base_url, "robots.txt").decode("utf-8")
    if "Sitemap: https://bootdisk.no/sitemap.xml" not in robots:
        raise RuntimeError("robots.txt does not advertise the production sitemap")
    sitemap = ET.fromstring(fetch(args.base_url, "sitemap.xml"))
    fetch(args.base_url, "definitely-not-a-bootdisk-page", expected_status=404)
    index = json.loads(fetch(args.base_url, "data/index.json"))
    entries = index.get("entries")
    if not isinstance(entries, list) or len(entries) != args.expected_entries:
        raise RuntimeError(f"Expected {args.expected_entries} entries, got {len(entries) if isinstance(entries, list) else 'invalid'}")
    sitemap_urls = {node.text for node in sitemap.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")}
    expected_urls = {"https://bootdisk.no/archive.html", *(f"https://bootdisk.no/index.html?entry={entry['entry']}" for entry in entries)}
    if sitemap_urls != expected_urls:
        raise RuntimeError("Sitemap URLs do not match the archive index")

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
    print("deployment verification: passed")


if __name__ == "__main__":
    main()
