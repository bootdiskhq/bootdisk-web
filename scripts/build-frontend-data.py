#!/usr/bin/env python3
"""Build disposable frontend documents from Catalog and Publish projections.

Catalog remains authoritative for semantic identity. Publish remains authoritative for
web assets. This script only joins both views through stable ingest entry ids and
verified artifact hashes; it never infers software identity from filenames or titles.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ENTRY_ID = re.compile(r"[A-Za-z][A-Za-z0-9]{0,63}")


def public_path(object_key: str | None) -> str | None:
    return f"store/{object_key.lstrip('/')}" if object_key else None


def project_asset(asset: dict) -> dict:
    original = dict(asset.get("original") or {})
    original["public_path"] = public_path(original.get("object_key"))
    derivatives = []
    for item in asset.get("derivatives") or []:
        projected = dict(item)
        projected["public_path"] = public_path(projected.get("object_key"))
        derivatives.append(projected)
    return {"entry": asset.get("entry_source_id"), "kind": asset.get("kind"), "source_path": asset.get("source_path"), "original": original, "derivatives": derivatives}


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

    documents: dict[Path, str] = {}
    index = []
    seen_entries: set[str] = set()
    for entry in catalog:
        entry_id = entry.get("entry")
        if not entry_id:
            continue
        if not isinstance(entry_id, str) or not ENTRY_ID.fullmatch(entry_id):
            raise SystemExit(f"Invalid source entry id: {entry_id!r}")
        if entry_id.lower() == "index":
            raise SystemExit("Reserved source entry id: index")
        if entry_id.lower() in seen_entries:
            raise SystemExit(f"Duplicate source entry id: {entry_id}")
        seen_entries.add(entry_id.lower())
        occurrence_hashes = {occurrence["artifact_id"].removeprefix("artifact:sha256:") for occurrence in entry.get("occurrences") or [] if str(occurrence.get("artifact_id", "")).startswith("artifact:sha256:")}
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
        documents[target] = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

        software = (entry.get("software") or [{}])[0]
        icon = next((asset for asset in joined_assets if asset.get("kind") == "icon"), None)
        if icon is None:
            icon = next((asset for asset in joined_assets if asset.get("kind") == "screenshot"), None)
        index.append({"entry": entry_id, "editorial_title": entry.get("editorial_title"), "curation_status": entry.get("curation_status"), "software_name": software.get("software_name"), "version": software.get("version"), "identification_status": software.get("status"), "content_kind": software.get("content_kind"), "distribution_kind": software.get("distribution_kind"), "icon": icon})

    # The index is also disposable presentation data. It intentionally contains only
    # enough information to browse into an entry; detailed evidence stays per entry.
    if all(re.fullmatch(r"K[0-9]+", item["entry"]) for item in index):
        index.sort(key=lambda item: int(item["entry"][1:]))
    documents[args.output / "index.json"] = json.dumps({"publication": args.publication, "medium": args.medium, "entries": index}, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    # Only replace generated JSON after every input and join has validated. This
    # prevents a failed build from leaving a half-written presentation tree, while
    # removing stale entry documents from earlier source revisions.
    args.output.mkdir(parents=True, exist_ok=True)
    for stale in args.output.glob("*.json"):
        if stale not in documents:
            stale.unlink()
    for target, content in documents.items():
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
    print(f"frontend entries: {len(index)}")


if __name__ == "__main__":
    main()
