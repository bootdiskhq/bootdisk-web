#!/usr/bin/env python3
"""Combine manifest-bound projections; public route names are not Catalog IDs."""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from frontend_contract import validate_frontend_data, require

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MANIFEST = re.compile(r"sha256:[0-9a-f]{64}")


def build_collection(config_path: Path, output: Path):
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    inputs = config.get("media")
    require(isinstance(inputs, list) and bool(inputs), "media must be a non-empty array")
    media, summaries, documents = [], [], {}
    seen_media, seen_manifests = set(), set()
    legacy_count = 0
    for item in inputs:
        slug = item.get("id")
        require(isinstance(slug, str) and SLUG.fullmatch(slug), "invalid medium id")
        require(slug not in seen_media, "duplicate medium id")
        seen_media.add(slug)
        legacy = item.get("legacy_links", False)
        require(isinstance(legacy, bool), "legacy_links must be boolean")
        legacy_count += legacy
        require(legacy_count <= 1, "only one medium may retain legacy links")
        data = (config_path.parent / item["data"]).resolve()
        index = validate_frontend_data(data)
        require(index.get("schema") != "bootdisk-web-collection-1", "input must be a single-medium projection")
        medium = {"id": slug, "publication": index["publication"], "medium": index["medium"], "legacy_links": legacy}
        for field in ("image_requirements", "images_unavailable_reason"):
            if field in item:
                medium[field] = deepcopy(item[field])
        manifest_ref = None
        for summary in index["entries"]:
            source_id = summary["entry"]
            require(re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,63}", source_id), "invalid source id")
            require(not legacy or re.fullmatch(r"K[0-9]+", source_id), "legacy links require historical K-number ids")
            document = json.loads((data / f"{source_id.lower()}.json").read_text(encoding="utf-8"))
            key = document.get("source_context", {}).get("key", {})
            require(key.get("entry") == source_id and MANIFEST.fullmatch(str(key.get("manifest", ""))), "missing/mismatched source binding")
            if manifest_ref is None:
                manifest_ref = key["manifest"]
            require(key["manifest"] == manifest_ref, "one medium contains multiple manifests")
            for field in ("description", "menu_groups", "issues"):
                observation = document["source_context"].get(field)
                if observation is not None:
                    ref = observation.get("source_ref", {})
                    require(all(ref.get(k) == v for k, v in key.items()), "cross-source observation")
            route = source_id if legacy else slug + "--" + source_id
            require(route.lower() not in documents, "case-insensitive public route collision")
            metadata = {"entry": route, "source_entry": source_id, "source_manifest": manifest_ref,
                        "medium_id": slug, "medium": index["medium"], "publication": index["publication"],
                        "source_order": len(summaries)}
            document.update(metadata)
            for asset in document["assets"]:
                asset["entry"] = route
            projected = deepcopy(summary)
            projected.update(metadata)
            if projected.get("icon"):
                projected["icon"]["entry"] = route
            summaries.append(projected)
            documents[route.lower()] = document
        require(manifest_ref is not None, "empty medium")
        require(manifest_ref not in seen_manifests, "duplicate source manifest")
        seen_manifests.add(manifest_ref)
        medium["source_manifest"] = manifest_ref
        media.append(medium)
    index = {"schema": "bootdisk-web-collection-1", "publication": "Bootdisk", "medium": f"{len(media)} CD-er",
             "media": media, "entries": summaries}
    output = output.absolute()
    require(not output.exists() and not output.is_symlink(), "output must be a new directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".collection-", dir=output.parent))
    try:
        for name, document in {**documents, "index": index}.items():
            (stage / (name + ".json")).write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        validate_frontend_data(stage, len(summaries))
        os.rename(stage, output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path, help="JSON with media: [{id, data, legacy_links?}]")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    index = build_collection(args.config, args.output)
    print(f"collection: {len(index['entries'])} entries from {len(index['media'])} media")


if __name__ == "__main__":
    main()
