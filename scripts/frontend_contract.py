#!/usr/bin/env python3
"""Validate Bootdisk Web's stable generated-data contract."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath

ENTRY_ID = re.compile(r"(?:[a-z0-9]+(?:-[a-z0-9]+)*--)?[A-Za-z][A-Za-z0-9]{0,63}")
SHA256 = re.compile(r"[0-9a-f]{64}")
CURATION_STATUSES = {"identified", "pending"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_public_path(value: object, context: str) -> None:
    require(isinstance(value, str), f"{context}: public_path must be a string")
    path = PurePosixPath(value)
    require(
        not path.is_absolute() and path.parts and path.parts[0] == "store" and ".." not in path.parts,
        f"{context}: Unsafe asset public_path {value!r}",
    )


def validate_asset(asset: object, entry_id: str, context: str) -> None:
    require(isinstance(asset, dict), f"{context}: asset must be an object")
    require(asset.get("entry") == entry_id, f"{context}: asset entry must equal {entry_id}")
    require(asset.get("kind") in {"icon", "screenshot"}, f"{context}: unsupported asset kind")
    candidates = [("original", asset.get("original"))]
    candidates.extend((f"derivatives[{position}]", item) for position, item in enumerate(asset.get("derivatives") or []))
    for name, candidate in candidates:
        require(isinstance(candidate, dict), f"{context}.{name}: asset representation must be an object")
        validate_public_path(candidate.get("public_path"), f"{context}.{name}")
        require(SHA256.fullmatch(str(candidate.get("sha256", ""))) is not None, f"{context}.{name}: invalid sha256")


def validate_software(software: object, context: str) -> None:
    require(isinstance(software, dict), f"{context}: software must be an object")
    descriptions = software.get("descriptions", [])
    require(isinstance(descriptions, list), f"{context}.descriptions must be an array")
    for position, description in enumerate(descriptions):
        label = f"{context}.descriptions[{position}]"
        require(isinstance(description, dict), f"{label} must be an object")
        require(isinstance(description.get("description_id"), str), f"{label}: missing description_id")
        require(isinstance(description.get("language"), str), f"{label}: missing language")
        require(isinstance(description.get("text"), str) and description["text"].strip(), f"{label}: text must be non-empty")


def validate_frontend_data(root: Path, expected_entries: int | None = None) -> dict:
    index_path = root / "index.json"
    require(index_path.is_file(), "Missing index.json")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    require(isinstance(index, dict), "index.json must contain an object")
    require(isinstance(index.get("publication"), str) and index["publication"].strip(), "index publication must be non-empty")
    require(isinstance(index.get("medium"), str) and index["medium"].strip(), "index medium must be non-empty")
    entries = index.get("entries")
    require(isinstance(entries, list), "index entries must be an array")
    if expected_entries is not None:
        require(len(entries) == expected_entries, f"Expected {expected_entries} index entries, got {len(entries)}")

    collection = index.get("schema") == "bootdisk-web-collection-1"
    media = index.get("media", [])
    if collection:
        require(isinstance(media, list) and bool(media), "collection media must be non-empty")
        require(all(isinstance(m, dict) and isinstance(m.get("id"), str) for m in media), "invalid media")
        require(len({m["id"] for m in media}) == len(media), "duplicate medium id")
        require(sum(m.get("legacy_links") is True for m in media) <= 1, "multiple legacy media")
        for medium in media:
            require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", medium["id"]) is not None, "invalid medium id")
            require(re.fullmatch(r"sha256:[0-9a-f]{64}", str(medium.get("source_manifest", ""))) is not None, "invalid source manifest")
            for field in ("publication", "medium"):
                require(isinstance(medium.get(field), str) and bool(medium[field].strip()), f"missing medium {field}")
    entry_ids: list[str] = []
    for position, summary in enumerate(entries):
        context = f"index.entries[{position}]"
        require(isinstance(summary, dict), f"{context} must be an object")
        entry_id = summary.get("entry")
        require(isinstance(entry_id, str) and ENTRY_ID.fullmatch(entry_id) is not None, f"{context}: invalid entry id")
        require(entry_id.lower() != "index", f"{context}: reserved entry id")
        require(summary.get("curation_status") in CURATION_STATUSES, f"{context}: invalid curation_status")
        if collection:
            require(type(summary.get("source_order")) is int and summary["source_order"] == position, "invalid collection source order")
        entry_ids.append(entry_id)

    require(len(entry_ids) == len(set(entry_ids)), "Index entry ids must be unique")
    require(len({i.lower() for i in entry_ids}) == len(entry_ids), "Entry filenames collide")
    if not collection and all(re.fullmatch(r"K[0-9]+", i) for i in entry_ids):
        require(entry_ids == sorted(entry_ids, key=lambda value: int(value[1:])), "Index entries must follow source order")

    for summary in entries:
        entry_id = summary["entry"]
        path = root / f"{entry_id.lower()}.json"
        require(path.is_file(), f"Missing detail document for {entry_id}")
        document = json.loads(path.read_text(encoding="utf-8"))
        require(isinstance(document, dict), f"{path.name} must contain an object")
        require(document.get("entry") == entry_id, f"{path.name}: entry mismatch")
        context = index
        if collection:
            matches = [m for m in media if m["id"] == summary.get("medium_id")]
            require(len(matches) == 1, f"{path.name}: unknown medium")
            context = matches[0]
            for label in ("publication", "medium"):
                require(summary.get(label) == context[label], f"{path.name}: summary {label} mismatch")
            for key in ("medium_id", "source_entry", "source_manifest"):
                require(document.get(key) == summary.get(key) and isinstance(document.get(key), str), f"{path.name}: {key} mismatch")
            require(document["source_manifest"] == context.get("source_manifest"), f"{path.name}: manifest mismatch")
            expected_id = document["source_entry"] if context.get("legacy_links") else context["id"] + "--" + document["source_entry"]
            require(entry_id == expected_id, f"{path.name}: qualified entry mismatch")
            key = document.get("source_context", {}).get("key", {})
            require(key == {"entry": document["source_entry"], "manifest": document["source_manifest"]}, f"{path.name}: source binding mismatch")
            for field in ("description", "menu_groups", "issues"):
                observation = document["source_context"].get(field)
                if observation is not None:
                    require(isinstance(observation, dict), f"{path.name}: invalid observation")
                    ref = observation.get("source_ref", {})
                    require(all(ref.get(k) == v for k, v in key.items()), f"{path.name}: cross-source observation")
                    if field == "description":
                        require(isinstance(observation.get("value"), str), f"{path.name}: description must be text")
                    else:
                        require(isinstance(observation.get("value"), list) and all(isinstance(v, str) for v in observation["value"]), f"{path.name}: invalid {field}")
        require(document.get("publication") == context["publication"], f"{path.name}: publication mismatch")
        require(document.get("medium") == context["medium"], f"{path.name}: medium mismatch")
        require(document.get("curation_status") in CURATION_STATUSES, f"{path.name}: invalid curation_status")
        require(document.get("curation_status") == summary.get("curation_status"), f"{path.name}: summary status mismatch")
        require(isinstance(document.get("software"), list), f"{path.name}: software must be an array")
        for position, software in enumerate(document["software"]):
            validate_software(software, f"{path.name}.software[{position}]")
        require(isinstance(document.get("assets"), list), f"{path.name}: assets must be an array")
        for position, asset in enumerate(document["assets"]):
            validate_asset(asset, entry_id, f"{path.name}.assets[{position}]")
        if summary.get("icon") is not None:
            validate_asset(summary["icon"], entry_id, f"{path.name}.index.icon")
            require(summary["icon"] in document["assets"], f"{path.name}: index icon missing from detail")

    expected_files = {"index.json", *(f"{entry_id.lower()}.json" for entry_id in entry_ids)}
    actual_files = {path.name for path in root.glob("*.json")}
    require(actual_files == expected_files, f"Unexpected generated JSON files: {sorted(actual_files - expected_files)}")
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("frontend_data", type=Path)
    parser.add_argument("--expected-entries", type=int)
    args = parser.parse_args()
    index = validate_frontend_data(args.frontend_data, args.expected_entries)
    print(f"frontend contract: {len(index['entries'])} entries valid")


if __name__ == "__main__":
    main()
