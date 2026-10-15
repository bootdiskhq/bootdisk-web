#!/usr/bin/env python3
"""Public update history: which source entries were added or visibly changed, and when.

Contract `bootdisk-public-updates-v2` (docs/public-updates.md). The register is a
small, explicitly maintained JSON document. It is never derived from the clock, file
times, CD years or index order:

* `init` records an existing published projection as a dateless baseline. Nothing in
  a baseline is "new".
* `record` compares the last published projection with the candidate projection that
  is being published, and appends one release with its explicit UTC publication time.
  Running it again for the same release and the same content returns the same
  register; reusing a release id with another time or other content is refused.
* `preview` shows what `record` would register, and writes nothing.
* `validate` checks a register, optionally against the frontend data it will ship with.

Only the visible projection below is compared, never raw JSON. Formatting, key order,
storage paths, manifest digests, build times, internal release ids, source order and
technical provenance do not create events. The register holds only public facts:
release ids, UTC times, public entry ids, their source binding and change codes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "bootdisk-public-updates-v2"
# The definition of "visible" is versioned with the register: a projection with other
# fields gives other fingerprints and needs a new contract version, not a silent reset.
PROJECTION = "visible-v2"
FEED_NAME = "public-updates.json"

ENTRY_ID = re.compile(r"(?:[a-z0-9]+(?:-[a-z0-9]+)*--)?[A-Za-z][A-Za-z0-9]{0,63}")
RELEASE_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+-]{0,63}")
UTC_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
SHA256 = re.compile(r"[0-9a-f]{64}")
EVENT_TYPES = ("added", "updated")

# Display vocabularies, mirrored from app.js. A value the page shows as "Ukjent" is unknown.
CONTENT_KINDS = {"application", "game", "course", "image_collection", "font_collection", "reference"}
DISTRIBUTION_KINDS = {"full", "demo", "trial", "update"}

# Source-issue codes are not shown as such: app.js turns them into at most two notes.
# The projection holds the notes a reader sees, so two codes with the same note are equal.
SHARED_CONTROL_ISSUE = "shared_warning_control_not_runtime_tested"
SOURCE_NOTES = ("untested_shared_control", "unresolved_file_references")

# Controlled change codes, in the order they are stored and explained.
CHANGE_CODES = (
    "identified", "identification_confirmed", "interpreted", "identification_withdrawn",
    "name_added", "name_changed", "name_removed",
    "version_added", "version_changed", "version_removed",
    "content_kind_added", "content_kind_changed", "content_kind_removed",
    "distribution_kind_added", "distribution_kind_changed", "distribution_kind_removed",
    "menu_title_changed",
    "description_added", "description_changed", "description_removed",
    "icon_added", "icon_changed", "icon_removed",
    "screenshot_added", "screenshot_changed", "screenshot_removed",
    "source_document_added", "source_document_changed", "source_document_removed",
    "source_issues_added", "source_issues_changed", "source_issues_removed",
)
CODE_ORDER = {code: position for position, code in enumerate(CHANGE_CODES)}


class UpdatesError(ValueError):
    """A register, projection or request that must not be published."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise UpdatesError(message)


# --- The visible projection -------------------------------------------------------------

def _known(value: object) -> str | None:
    """`null`, blank and "unknown" are all shown as unknown."""
    if not isinstance(value, str) or not value.strip() or value == "unknown":
        return None
    return value


def _first_asset_hash(assets: list, kind: str) -> str | None:
    for asset in assets:
        if isinstance(asset, dict) and asset.get("kind") == kind:
            return (asset.get("original") or {}).get("sha256")
    return None


def visible_projection(document: dict) -> dict:
    """What a reader of the detail page and the archive card actually sees.

    Compared fields: displayed software name and version, identification status,
    content kind, distribution kind, the CD menu title, the displayed description
    (text and whether it is the CD's own), the first icon and first screenshot by
    content hash of the original, the attached original texts (content hash, readable
    text and the CD file name shown next to them) and whether source issues are shown.

    Left out on purpose: storage paths (`public_path`), derivative files, manifest
    digests, Catalog release/identification ids, source order, medium and publication
    labels (collection-level, not entry content), JSON layout and every timestamp.
    """
    software = (document.get("software") or [None])[0] or {}
    status = "interpreted" if software.get("status") == "interpreted" else document.get("curation_status")
    context = document.get("source_context") or {}
    source_description = (context.get("description") or {}).get("value") if context.get("description") else None
    descriptions = software.get("descriptions") or []
    curated = next((item.get("text") for item in descriptions if item.get("language") == "nb-NO"), None)
    if curated is None and descriptions:
        curated = descriptions[0].get("text")
    # app.js: `source_context.description.value ?? preferredDescription(software)`.
    if source_description is not None:
        description, description_source = source_description, "cd"
    else:
        description, description_source = curated, "curated" if curated is not None else None
    if not description:
        description, description_source = None, None
    key = context.get("key")
    documents = []
    for item in document.get("source_documents") or []:
        if key is None or item.get("key") != key:
            continue  # app.js only shows original texts bound to this entry's own source
        text = item.get("text") if isinstance(item.get("text"), str) and item["text"].strip() else None
        digest = (item.get("original") or {}).get("sha256") or item.get("sha256")
        documents.append({"sha256": digest, "text": text, "path": item.get("path")})
    documents.sort(key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
    assets = document.get("assets") or []
    issues = (context.get("issues") or {}).get("value") or []
    # app.js: one note when the shared-control code is present, one when any other code is.
    notes = []
    if SHARED_CONTROL_ISSUE in issues:
        notes.append("untested_shared_control")
    if any(issue != SHARED_CONTROL_ISSUE for issue in issues):
        notes.append("unresolved_file_references")
    return {
        "status": status,
        "software_name": _known(software.get("software_name")),
        "version": _known(software.get("version")),
        "content_kind": software.get("content_kind") if software.get("content_kind") in CONTENT_KINDS else None,
        "distribution_kind": software.get("distribution_kind") if software.get("distribution_kind") in DISTRIBUTION_KINDS else None,
        "menu_title": _known(document.get("editorial_title")),
        "description": description,
        "description_source": description_source,
        "icon": _first_asset_hash(assets, "icon"),
        "screenshot": _first_asset_hash(assets, "screenshot"),
        "source_documents": documents,
        "source_notes": notes,
    }


def load_projection(root: Path) -> dict[str, dict]:
    """Entry id -> binding and visible projection, from a validated frontend data directory.

    Only `index.json` and the entry documents it names are read; a published package's
    own `public-updates.json` beside them is ignored here.
    """
    from frontend_contract import validate_frontend_data

    root = Path(root)
    try:
        index = validate_frontend_data(root)
    except ValueError as error:
        raise UpdatesError(f"{root}: invalid frontend data: {error}") from None
    entries = {}
    for summary in index["entries"]:
        entry_id = summary["entry"]
        document = json.loads((root / f"{entry_id.lower()}.json").read_text(encoding="utf-8"))
        entries[entry_id] = {
            "medium_id": summary.get("medium_id"),
            "source_entry": summary.get("source_entry"),
            "visible": visible_projection(document),
        }
    return entries


def fingerprint(projection: dict[str, dict]) -> str:
    """One identity for what readers see; independent of formatting and storage."""
    payload = {"projection": PROJECTION, "entries": {key: value["visible"] for key, value in sorted(projection.items())}}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# --- Differences ---------------------------------------------------------------------------

def _transition(field: str, before, after) -> list[str]:
    if before == after:
        return []
    if before is None:
        return [f"{field}_added"]
    if after is None:
        return [f"{field}_removed"]
    return [f"{field}_changed"]


def change_codes(before: dict, after: dict) -> list[str]:
    """Controlled codes for a visible change; an empty list means no event."""
    codes: list[str] = []
    old_status, new_status = before["status"], after["status"]
    if old_status != new_status:
        if new_status == "identified":
            codes.append("identification_confirmed" if old_status == "interpreted" else "identified")
        elif new_status == "interpreted":
            codes.append("interpreted")
        else:
            codes.append("identification_withdrawn")
    codes += _transition("name", before["software_name"], after["software_name"])
    for field in ("version", "content_kind", "distribution_kind"):
        codes += _transition(field, before[field], after[field])
    if before["menu_title"] != after["menu_title"]:
        codes.append("menu_title_changed")
    if (before["description"], before["description_source"]) != (after["description"], after["description_source"]):
        codes += _transition("description", before["description"], after["description"]) or ["description_changed"]
    for field in ("icon", "screenshot"):
        codes += _transition(field, before[field], after[field])
    codes += _transition("source_document", before["source_documents"] or None, after["source_documents"] or None)
    codes += _transition("source_issues", before["source_notes"] or None, after["source_notes"] or None)
    return sorted(codes, key=CODE_ORDER.__getitem__)


def diff(previous: dict[str, dict], candidate: dict[str, dict]) -> list[dict]:
    """Events for entries added to, or visibly changed in, the candidate.

    Entries missing from the candidate get no event (no deletion notices). An id that
    is bound to another medium or source entry than before is refused rather than
    reported as an update: public ids are stable, and a K-code alone is not unique.
    """
    events = []
    for entry_id in sorted(candidate):
        after = candidate[entry_id]
        before = previous.get(entry_id)
        binding = {"medium_id": after["medium_id"], "source_entry": after["source_entry"]}
        if before is None:
            events.append({"entry": entry_id, **binding, "type": "added", "changes": []})
            continue
        for field in ("medium_id", "source_entry"):
            require(before[field] is None or after[field] is None or before[field] == after[field],
                    f"{entry_id}: {field} changed from {before[field]!r} to {after[field]!r}; "
                    "a public entry id must keep its source binding")
        codes = change_codes(before["visible"], after["visible"])
        if codes:
            events.append({"entry": entry_id, **binding, "type": "updated", "changes": codes})
    return events


# --- Register ------------------------------------------------------------------------------

def _utc(value: object, context: str) -> datetime:
    require(isinstance(value, str) and UTC_TIME.fullmatch(value) is not None,
            f"{context}: publication time must be explicit UTC like 2026-10-15T09:30:00Z, got {value!r}")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise UpdatesError(f"{context}: {value!r} is not a real time") from None


def latest_state(register: dict) -> tuple[str, str]:
    """(release id, projection fingerprint) of the newest published state."""
    if register["releases"]:
        last = register["releases"][-1]
        return last["release_id"], last["projection_sha256"]
    return register["baseline"]["release_id"], register["baseline"]["projection_sha256"]


def validate_register(register: object, index: dict | None = None, data_fingerprint: str | None = None) -> dict:
    """Structural and historical checks; with `index`, also source bindings of shown events.

    `data_fingerprint` is the fingerprint of the frontend data the register ships with:
    the register's newest state must describe exactly that data.
    """
    require(isinstance(register, dict), "register must be an object")
    require(register.get("schema") == SCHEMA, f"register schema must be {SCHEMA!r}")
    require(register.get("projection") == PROJECTION, f"register projection must be {PROJECTION!r}")
    require(set(register) <= {"schema", "projection", "baseline", "releases", "events"}, "register has unknown fields")
    baseline = register.get("baseline")
    require(isinstance(baseline, dict), "register needs a baseline")
    require(set(baseline) == {"release_id", "projection_sha256", "entries"}, "baseline must have release_id, projection_sha256 and entries only")
    require(isinstance(baseline["release_id"], str) and RELEASE_ID.fullmatch(baseline["release_id"]) is not None, "invalid baseline release_id")
    require(isinstance(baseline["projection_sha256"], str) and SHA256.fullmatch(baseline["projection_sha256"]) is not None, "invalid baseline projection_sha256")
    entries = baseline["entries"]
    require(isinstance(entries, list) and all(isinstance(e, str) and ENTRY_ID.fullmatch(e) for e in entries), "invalid baseline entries")
    require(entries == sorted(set(entries)), "baseline entries must be unique and sorted")

    releases = register.get("releases")
    require(isinstance(releases, list), "releases must be an array")
    seen = {baseline["release_id"]}
    previous_id, previous_time = baseline["release_id"], None
    times = {}
    for position, release in enumerate(releases):
        context = f"releases[{position}]"
        require(isinstance(release, dict), f"{context} must be an object")
        require(set(release) == {"release_id", "previous_release_id", "published_at", "projection_sha256", "added", "updated"},
                f"{context} has missing or unknown fields")
        release_id = release["release_id"]
        require(isinstance(release_id, str) and RELEASE_ID.fullmatch(release_id) is not None, f"{context}: invalid release_id")
        require(release_id not in seen, f"{context}: release_id {release_id!r} is used more than once")
        seen.add(release_id)
        require(release["previous_release_id"] == previous_id, f"{context}: previous_release_id must be {previous_id!r}")
        published = _utc(release["published_at"], context)
        require(previous_time is None or published > previous_time, f"{context}: published_at must be later than the previous release")
        require(isinstance(release["projection_sha256"], str) and SHA256.fullmatch(release["projection_sha256"]) is not None,
                f"{context}: invalid projection_sha256")
        for field in ("added", "updated"):
            require(type(release[field]) is int and release[field] >= 0, f"{context}: invalid {field} count")
        previous_id, previous_time = release_id, published
        times[release_id] = release

    events = register.get("events")
    require(isinstance(events, list), "events must be an array")
    keys = set()
    counts = {release_id: {"added": 0, "updated": 0} for release_id in times}
    order = [release["release_id"] for release in releases]
    sort_keys = []
    for position, event in enumerate(events):
        context = f"events[{position}]"
        require(isinstance(event, dict), f"{context} must be an object")
        require(set(event) == {"release_id", "published_at", "entry", "medium_id", "source_entry", "type", "changes"},
                f"{context} has missing or unknown fields")
        release = times.get(event["release_id"])
        require(release is not None, f"{context}: unknown release_id {event['release_id']!r}")
        require(event["published_at"] == release["published_at"], f"{context}: published_at differs from its release")
        entry_id = event["entry"]
        require(isinstance(entry_id, str) and ENTRY_ID.fullmatch(entry_id) is not None, f"{context}: invalid entry id")
        for field in ("medium_id", "source_entry"):
            require(event[field] is None or (isinstance(event[field], str) and event[field]), f"{context}: invalid {field}")
        require(event["type"] in EVENT_TYPES, f"{context}: type must be added or updated")
        changes = event["changes"]
        require(isinstance(changes, list) and all(code in CODE_ORDER for code in changes), f"{context}: unknown change code")
        require(changes == sorted(set(changes), key=CODE_ORDER.__getitem__), f"{context}: change codes must be unique and in contract order")
        require(bool(changes) == (event["type"] == "updated"), f"{context}: updated needs change codes, added has none")
        key = (event["release_id"], entry_id)
        require(key not in keys, f"{context}: duplicate event for {entry_id} in {event['release_id']}")
        keys.add(key)
        counts[event["release_id"]][event["type"]] += 1
        sort_keys.append((order.index(event["release_id"]), entry_id))
    require(sort_keys == sorted(sort_keys), "events must be ordered by release, then entry id")
    for release_id, release in times.items():
        require(counts[release_id] == {"added": release["added"], "updated": release["updated"]},
                f"release {release_id}: added/updated counts do not match its events")

    if index is not None:
        summaries = {summary["entry"]: summary for summary in index.get("entries", [])}
        for event in events:
            summary = summaries.get(event["entry"])
            if summary is None:
                continue  # removed entries keep their history but are never linked
            for field in ("medium_id", "source_entry"):
                require(event[field] is None or summary.get(field) is None or event[field] == summary.get(field),
                        f"event for {event['entry']} in {event['release_id']}: {field} {event[field]!r} "
                        f"does not match the archive index ({summary.get(field)!r})")
    if data_fingerprint is not None:
        release_id, expected = latest_state(register)
        require(expected == data_fingerprint,
                f"the register's newest state ({release_id}) does not describe this frontend data; "
                "record the release with `public_updates.py record` before packaging it")
    return register


def init_register(baseline_projection: dict[str, dict], release_id: str) -> dict:
    """A first register: the existing published entries are a dateless baseline."""
    require(isinstance(release_id, str) and RELEASE_ID.fullmatch(release_id) is not None, f"invalid release id {release_id!r}")
    register = {"schema": SCHEMA, "projection": PROJECTION,
                "baseline": {"release_id": release_id, "projection_sha256": fingerprint(baseline_projection),
                             "entries": sorted(baseline_projection)},
                "releases": [], "events": []}
    return validate_register(register)


def record_release(register: dict, previous: dict[str, dict], candidate: dict[str, dict],
                   release_id: str, published_at: str) -> dict:
    """Return the register with `release_id` recorded. Idempotent; conflicts are refused."""
    validate_register(register)
    require(isinstance(release_id, str) and RELEASE_ID.fullmatch(release_id) is not None, f"invalid release id {release_id!r}")
    _utc(published_at, "record")
    previous_sha, candidate_sha = fingerprint(previous), fingerprint(candidate)
    known = {item["release_id"]: item for item in register["releases"]}
    if release_id == register["baseline"]["release_id"]:
        raise UpdatesError(f"release {release_id!r} is the register's baseline and cannot be recorded again")
    if release_id in known:
        existing = known[release_id]
        position = register["releases"].index(existing)
        before_sha = register["releases"][position - 1]["projection_sha256"] if position else register["baseline"]["projection_sha256"]
        require(existing["published_at"] == published_at,
                f"release {release_id!r} is already registered as published at {existing['published_at']}, not {published_at}")
        require(existing["projection_sha256"] == candidate_sha and before_sha == previous_sha,
                f"release {release_id!r} is already registered with other content")
        expected = [{k: v for k, v in e.items() if k not in ("release_id", "published_at")}
                    for e in register["events"] if e["release_id"] == release_id]
        require(expected == diff(previous, candidate), f"release {release_id!r} is already registered with other events")
        return register
    last_id, last_sha = latest_state(register)
    require(last_sha == previous_sha,
            f"the previous projection is not the register's last published state ({last_id}); "
            "pass the projection that was actually published last")
    if register["releases"]:
        require(_utc(published_at, "record") > _utc(register["releases"][-1]["published_at"], "register"),
                f"published_at {published_at} must be later than {register['releases'][-1]['published_at']}")
    events = diff(previous, candidate)
    result = json.loads(json.dumps(register))
    result["releases"].append({
        "release_id": release_id, "previous_release_id": last_id, "published_at": published_at,
        "projection_sha256": candidate_sha,
        "added": sum(event["type"] == "added" for event in events),
        "updated": sum(event["type"] == "updated" for event in events),
    })
    result["events"] += [{"release_id": release_id, "published_at": published_at, **event} for event in events]
    return validate_register(result)


def dumps(register: dict) -> str:
    return json.dumps(register, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def load_register(path: Path) -> dict:
    try:
        register = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise UpdatesError(f"update register not found: {path}") from None
    except json.JSONDecodeError as error:
        raise UpdatesError(f"update register {path} is not valid JSON: {error}") from None
    try:
        return validate_register(register)
    except UpdatesError as error:
        raise UpdatesError(f"update register {path}: {error}") from None


def summarize(previous: dict, candidate: dict, events: list[dict]) -> dict:
    changed = {event["entry"] for event in events}
    unchanged = [entry for entry in candidate if entry in previous and entry not in changed]
    codes: dict[str, int] = {}
    for event in events:
        for code in event["changes"]:
            codes[code] = codes.get(code, 0) + 1
    return {
        "added": sum(event["type"] == "added" for event in events),
        "updated": sum(event["type"] == "updated" for event in events),
        "unchanged": len(unchanged),
        "missing_from_candidate": len([entry for entry in previous if entry not in candidate]),
        "change_codes": dict(sorted(codes.items(), key=lambda item: CODE_ORDER[item[0]])),
    }


def _write_new(path: Path, text: str) -> None:
    path = Path(path)
    require(not path.exists(), f"refusing to replace {path}; write the new register to a new path")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _check_expectations(summary: dict, args) -> None:
    for field in ("added", "updated", "unchanged"):
        expected = getattr(args, f"expect_{field}", None)
        require(expected is None or summary[field] == expected, f"expected {expected} {field}, got {summary[field]}")


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Register a published projection as a dateless baseline")
    init.add_argument("published_data", type=Path)
    init.add_argument("--release-id", required=True)
    init.add_argument("--output", type=Path, required=True)

    for name, helptext in (("preview", "Show the events a release would get; writes nothing"),
                           ("record", "Append a published release to a register (new output file)")):
        command = commands.add_parser(name, help=helptext)
        command.add_argument("previous_data", type=Path, help="The projection that was published last")
        command.add_argument("candidate_data", type=Path, help="The projection being published")
        for field in ("added", "updated", "unchanged"):
            command.add_argument(f"--expect-{field}", type=int)
        if name == "record":
            source = command.add_mutually_exclusive_group(required=True)
            source.add_argument("--register", type=Path, help="The register shipped with the previous release")
            source.add_argument("--baseline-release-id", help="Start a register: previous_data becomes a dateless baseline")
            command.add_argument("--release-id", required=True)
            command.add_argument("--published-at", required=True, help="Actual UTC publication time, e.g. 2026-10-15T09:30:00Z")
            command.add_argument("--output", type=Path, required=True)
        command.add_argument("--show", action="append", default=[], metavar="ENTRY", help="Print the event for this entry id")

    validate = commands.add_parser("validate", help="Validate a register, optionally against frontend data")
    validate.add_argument("register", type=Path)
    validate.add_argument("--frontend-data", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            register = init_register(load_projection(args.published_data), args.release_id)
            _write_new(args.output, dumps(register))
            print(f"baseline {args.release_id}: {len(register['baseline']['entries'])} entries, no dates, no events")
        elif args.command in ("preview", "record"):
            previous, candidate = load_projection(args.previous_data), load_projection(args.candidate_data)
            events = diff(previous, candidate)
            summary = summarize(previous, candidate, events)
            print(json.dumps(summary, ensure_ascii=False, indent=1))
            for entry_id in args.show:
                matches = [event for event in events if event["entry"] == entry_id]
                print(f"{entry_id}: {json.dumps(matches[0], ensure_ascii=False) if matches else 'no event'}")
            _check_expectations(summary, args)
            if args.command == "record":
                register = load_register(args.register) if args.register else init_register(previous, args.baseline_release_id)
                register = record_release(register, previous, candidate, args.release_id, args.published_at)
                _write_new(args.output, dumps(register))
                print(f"recorded {args.release_id} at {args.published_at}: {args.output}")
            else:
                print("preview only: nothing was written or registered")
        else:
            index = data_sha = None
            if args.frontend_data:
                index = json.loads((args.frontend_data / "index.json").read_text(encoding="utf-8"))
                data_sha = fingerprint(load_projection(args.frontend_data))
            register = validate_register(load_register(args.register), index, data_sha)
            print(f"update register valid: {len(register['releases'])} releases, {len(register['events'])} events")
    except UpdatesError as error:
        print(f"public updates: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
