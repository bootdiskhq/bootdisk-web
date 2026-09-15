#!/usr/bin/env python3
"""Prepare a locally servable Bootdisk Web preview from Publish output.

The web app keeps /store paths deployment-neutral. For a local preview we expose the
Publish store through a symlink instead of copying or mutating preserved artifacts.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("publish_root", type=Path, help="Directory containing publish-manifest.json and store/")
    args = parser.parse_args()
    source = args.publish_root.expanduser().resolve() / "store"
    target = Path(__file__).resolve().parents[1] / "store"
    if not source.is_dir():
        raise SystemExit(f"Publish store not found: {source}")
    if target.is_symlink() or target.exists():
        if target.is_symlink() and target.resolve() == source:
            print(f"store already points to {source}")
            return
        raise SystemExit(f"Refusing to replace existing path: {target}")
    os.symlink(source, target, target_is_directory=True)
    print(f"store -> {source}")


if __name__ == "__main__":
    main()
