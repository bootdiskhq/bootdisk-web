#!/usr/bin/env python3
"""Build disposable frontend entry documents from Catalog and Publish projections.

Catalog remains authoritative for semantic identity. Publish remains authoritative for
web assets. This script only joins both views through stable ingest entry ids and
verified artifact hashes; it never infers software identity from filenames or titles.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def public_path(object_key: str | None) -> str | None:
    return f"/store/{object_key.lstrip('/')}" if object_key else None


def project_asset(asset: dict) -> dict:
    original = dict(asset.get("original") or {})
    original["public_path"] = public_path(original.get("object_key"))
    derivatives = []
    for item in asset.get("derivatives") or []:
        projected = dict(item)
        projected["public_path"] = public_path(projected.get("object_key"))
        derivatives.append(projected)
    return {
        "entry": asset.get("entry_source_id"),
        "kind": asset.get("kind"),
        "source_path": asset.get("source_path"),
        "original": original,
        "derivatives": derivatives,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog_projection", type=Path, help="JSON emitted by bootdisk_catalog.presentation")
    parser.add_argument("publish_manifest", type=Path, help="publish-manifest.json emitted by bootdisk-publish")
    parser.add_argument("--output", type=Path, default=Path("data"))
    parser.add_argument("--publication", default="KOMPUTER FOR ALLE")
    parser.add_argument("--medium", default="K-CD 15/2001")
    args = parser.parse_args()

    catalog = json.loads(args.catalog_projection.read_text(encoding="utf-8"))
    publish = json.loads(args.publish_manifest.read_text(encoding="utf-8"))
    if not isinstance(catalog, list) or not isinstance(publish.get("assets"), list):
        raise SystemExit("Expected a Catalog projection array and a Publish manifest with assets")

    assets_by_entry: dict[str, list[dict]] = {}
    for asset in publish["assets"]:
        entry_id = asset.get("entry_source_id")
        if entry_id:
            assets_by_entry.setdefault(entry_id, []).append(asset)

    args.output.mkdir(parents=True, exist_ok=True)
    written = 0
    for entry in catalog:
        entry_id = entry.get("entry")
        if not entry_id:
            continue
        occurrence_hashes = {
            occurrence["artifact_id"].removeprefix("artifact:sha256:")
            for occurrence in entry.get("occurrences") or []
            if str(occurrence.get("artifact_id", "")).startswith("artifact:sha256:")
        }
        joined_assets = []
        for asset in assets_by_entry.get(entry_id, []):
            sha256 = (asset.get("original") or {}).get("sha256")
            # Entry ids alone are not enough: require the published bytes to be an
            # occurrence Catalog actually observed for this same source entry.
            if sha256 in occurrence_hashes:
                joined_assets.append(project_asset(asset))

        document = dict(entry)
        document["publication"] = args.publication
        document["medium"] = args.medium
        document["assets"] = joined_assets
        target = args.output / f"{entry_id.lower()}.json"
        target.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written += 1

    print(f"frontend entries: {written}")


if __name__ == "__main__":
    main()
