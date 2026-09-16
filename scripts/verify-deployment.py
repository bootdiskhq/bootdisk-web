#!/usr/bin/env python3
"""Verify a deployed Bootdisk Web release over HTTP without browser internals."""
from __future__ import annotations

import argparse
import hashlib
import json
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
    args = parser.parse_args()

    fetch(args.base_url, "archive.html")
    fetch(args.base_url, "index.html?entry=K37")
    fetch(args.base_url, "definitely-not-a-bootdisk-page", expected_status=404)
    index = json.loads(fetch(args.base_url, "data/index.json"))
    entries = index.get("entries")
    if not isinstance(entries, list) or len(entries) != args.expected_entries:
        raise RuntimeError(f"Expected {args.expected_entries} entries, got {len(entries) if isinstance(entries, list) else 'invalid'}")

    assets: set[str] = set()
    for entry in entries:
        entry_id = entry["entry"]
        document = json.loads(fetch(args.base_url, f"data/{entry_id.lower()}.json"))
        if document.get("entry") != entry_id:
            raise RuntimeError(f"Entry mismatch for {entry_id}")
        assets.update(asset_paths(document))

    for path in sorted(assets):
        body = fetch(args.base_url, path)
        filename = path.rsplit("/", 1)[-1]
        expected_hash = filename.rsplit(".", 1)[0]
        actual_hash = hashlib.sha256(body).hexdigest()
        if actual_hash != expected_hash:
            raise RuntimeError(f"Content hash mismatch for {path}")

    print(f"deployment entries: {len(entries)}")
    print(f"deployment assets: {len(assets)}")
    print("deployment verification: passed")


if __name__ == "__main__":
    main()
