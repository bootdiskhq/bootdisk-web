#!/usr/bin/env python3
"""Validate Bootdisk Web's collection registry against a generated archive index.

The registry (`collections.json`) is Web-owned presentation configuration: a stable
local key, editorial text, sources and an explicit binding to the `publication`
values found on media. It is not a Catalog identity. The browser applies the same
rules in `collection-core.js`; this gate refuses to package a registry that would
put a medium under the wrong collection, or under none.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCHEMA = "bootdisk-web-collections-1"
INDEX_SCHEMA = "bootdisk-web-collection-1"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
ENTRY_LINK = re.compile(r"index\.html\?entry=((?:[a-z0-9]+(?:-[a-z0-9]+)*--)?[A-Za-z][A-Za-z0-9]{0,63})")
SOURCE_HREF = re.compile(
    r"(?:index\.html\?entry=(?:[a-z0-9]+(?:-[a-z0-9]+)*--)?[A-Za-z][A-Za-z0-9]{0,63}"
    r"|archive\.html(?:\?medium=[a-z0-9]+(?:-[a-z0-9]+)*)?"
    r"|https://[^\s\"'<>\\]+)"
)


def fail(message: str) -> None:
    raise ValueError(f"collections.json: {message}")


def text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_registry(registry: object) -> dict:
    if not isinstance(registry, dict):
        fail("must contain an object")
    if registry.get("schema") != SCHEMA:
        fail(f"schema must be {SCHEMA!r}")
    collections = registry.get("collections")
    if not isinstance(collections, list) or not collections:
        fail("collections must be a non-empty array")
    ids: set[str] = set()
    claimed: dict[str, str] = {}
    for position, collection in enumerate(collections):
        if not isinstance(collection, dict):
            fail(f"collections[{position}] must be an object")
        key = collection.get("id")
        if not isinstance(key, str) or not SLUG.fullmatch(key):
            fail(f"collections[{position}].id must be a lowercase slug such as 'komputer-for-alle'")
        if key in ids:
            fail(f"collection id {key!r} is used more than once")
        ids.add(key)
        for field in ("title", "summary", "lede"):
            if not text(collection.get(field)):
                fail(f"collection {key!r} needs a non-empty {field}")
        if "history_title" in collection and not text(collection["history_title"]):
            fail(f"collection {key!r} has an empty history_title")
        values = collection.get("publication_values")
        if not isinstance(values, list) or not values:
            fail(f"collection {key!r} needs publication_values: the exact medium publication strings it presents")
        for value in values:
            if not text(value):
                fail(f"collection {key!r} has an empty publication value")
            if value in claimed:
                fail(f"publication value {value!r} is bound to both {claimed[value]!r} and {key!r}; bind it to exactly one collection")
            claimed[value] = key
        history = collection.get("history")
        if not isinstance(history, list) or not all(text(paragraph) for paragraph in history):
            fail(f"collection {key!r} history must be a list of non-empty paragraphs")
        sources = collection.get("sources")
        if not isinstance(sources, list):
            fail(f"collection {key!r} needs a sources list")
        for source in sources:
            if not isinstance(source, dict) or not text(source.get("label")) or not isinstance(source.get("href"), str) \
                    or not SOURCE_HREF.fullmatch(source["href"]):
                fail(f"collection {key!r} has an invalid source link {source!r}")
    return registry


def index_media(index: dict) -> list[dict]:
    """Media as the browser sees them; a 1.0 single-medium index is its own medium."""
    if index.get("schema") == INDEX_SCHEMA:
        return [{"id": medium["id"], "publication": medium["publication"], "medium": medium["medium"],
                 "entries": sum(entry.get("medium_id") == medium["id"] for entry in index["entries"])}
                for medium in index["media"]]
    return [{"id": None, "publication": index["publication"], "medium": index["medium"], "entries": len(index["entries"])}]


def bind_registry(registry: dict, index: dict) -> dict[str, list[dict]]:
    """Return media per collection id. Every medium must belong to exactly one collection."""
    validate_registry(registry)
    owner = {value: collection["id"] for collection in registry["collections"] for value in collection["publication_values"]}
    bound: dict[str, list[dict]] = {collection["id"]: [] for collection in registry["collections"]}
    for medium in index_media(index):
        key = owner.get(medium["publication"])
        if key is None:
            label = medium["id"] or medium["medium"]
            fail(f"medium {label!r} has publication {medium['publication']!r}, which no collection lists in "
                 "publication_values; add it to the right collection (or a new one) before packaging")
        bound[key].append(medium)
    entry_ids = {entry["entry"] for entry in index["entries"]}
    for collection in registry["collections"]:
        for source in collection["sources"]:
            link = ENTRY_LINK.fullmatch(source["href"])
            if link and link.group(1) not in entry_ids:
                fail(f"collection {collection['id']!r} cites {source['href']!r}, which is not in the archive index")
    return bound


def collection_urls(registry: dict, index: dict, base_url: str) -> list[str]:
    """Public collection pages: only collections that actually have media."""
    bound = bind_registry(registry, index)
    return [f"{base_url}collection.html?collection={collection['id']}"
            for collection in registry["collections"] if bound[collection["id"]]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("frontend_data", type=Path)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    index = json.loads((args.frontend_data / "index.json").read_text(encoding="utf-8"))
    for key, media in bind_registry(registry, index).items():
        print(f"{key}: {len(media)} media, {sum(m['entries'] for m in media)} entries")


if __name__ == "__main__":
    main()
