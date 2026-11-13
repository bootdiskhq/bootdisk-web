"""Attach PDFs recorded on a source post, using the original CD as byte evidence."""
import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath


def bind(document, read_pdf, store):
    attached = []
    for occurrence in document.get("occurrences", []):
        path = occurrence["path"]
        if not path.lower().endswith(".pdf"):
            continue
        relative = PurePosixPath(path)
        match = re.fullmatch(r"artifact:sha256:([0-9a-f]{64})", occurrence["artifact_id"])
        if relative.is_absolute() or ".." in relative.parts or not match:
            raise ValueError(f"Invalid PDF occurrence: {path}")
        digest = match[1]
        raw = read_pdf(path, digest)
        if hashlib.sha256(raw).hexdigest() != digest or not raw.startswith(b"%PDF-"):
            raise ValueError(f"PDF differs from source record: {path}")
        target = store / "pdf" / (digest + ".pdf")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(raw)
        elif target.read_bytes() != raw:
            raise ValueError(f"Damaged published PDF: {target}")
        item = {"source_path": path, "sha256": digest}
        if item not in attached:
            attached.append(item)
    if attached:
        document["source_pdfs"] = attached
    return bool(attached)


def attach(data, source, store):
    root = source.resolve()
    def read_pdf(path, digest):
        file = (root / path).resolve()
        file.relative_to(root)
        return file.read_bytes()
    for row in json.loads((data / "index.json").read_text())["entries"]:
        file = data / (row["entry"].lower() + ".json")
        document = json.loads(file.read_text())
        if bind(document, read_pdf, store):
            file.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("data", "source", "store"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    attach(args.data, args.source, args.store)
