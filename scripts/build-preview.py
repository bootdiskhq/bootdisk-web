#!/usr/bin/env python3
"""Build all disposable web data needed for a local Bootdisk preview.

This orchestrates existing projections rather than reimplementing Catalog or Publish.
The resulting JSON can be deleted and rebuilt at any time from authoritative inputs.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_DATA = ROOT / "scripts" / "build-frontend-data.py"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog_root", type=Path)
    parser.add_argument("ingest_manifest", type=Path)
    parser.add_argument("publish_manifest", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "data")
    parser.add_argument("--publication", default="KOMPUTER FOR ALLE")
    parser.add_argument("--medium", default="K-CD 15/2001")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="bootdisk-web-") as temporary:
        projection = Path(temporary) / "catalog-presentation.json"
        result = subprocess.run(
            [sys.executable, "-m", "bootdisk_catalog.presentation", str(args.catalog_root.expanduser()), str(args.ingest_manifest.expanduser())],
            check=True,
            capture_output=True,
            text=True,
        )
        # Validate before handing data to the web joiner. This catches accidental CLI
        # chatter or a changed Catalog contract before it becomes frontend content.
        json.loads(result.stdout)
        projection.write_text(result.stdout, encoding="utf-8")
        subprocess.run(
            [sys.executable, str(BUILD_DATA), str(projection), str(args.publish_manifest.expanduser()), "--output", str(args.output.expanduser()), "--publication", args.publication, "--medium", args.medium],
            check=True,
        )


if __name__ == "__main__":
    main()
