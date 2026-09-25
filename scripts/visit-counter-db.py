#!/usr/bin/env python3
"""Opprett, kontroller og sikkerhetskopier besøkstellerens SQLite-database.

    python scripts/visit-counter-db.py init   BESOK.sqlite [--since 2026-10-01]
    python scripts/visit-counter-db.py status BESOK.sqlite
    python scripts/visit-counter-db.py backup BESOK.sqlite KOPI.sqlite

`init` er den eneste måten databasen blir til på; counter/besok.php lager den aldri selv.
Startdatoen er dagen telleren settes i drift og vises som «Besøk siden …». Se
docs/visit-counter.md for oppsett, sikkerhetskopi og gjenoppretting.
"""
from __future__ import annotations

import argparse
import datetime
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "counter" / "schema.sql"


def today_oslo() -> str:
    return datetime.datetime.now(ZoneInfo("Europe/Oslo")).date().isoformat()


def init(path: Path, since: str) -> None:
    datetime.date.fromisoformat(since)
    if path.exists():
        raise SystemExit(f"Nekter å overskrive en eksisterende teller: {path}")
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        connection.execute("INSERT INTO counter (id, total, since) VALUES (1, 0, ?)", (since,))
        connection.commit()
    finally:
        connection.close()
    print(f"opprettet {path} med total 0 siden {since}")


def open_existing(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise SystemExit(f"Finner ikke telleren: {path}")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def status(path: Path) -> None:
    connection = open_existing(path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        total, since = connection.execute("SELECT total, since FROM counter WHERE id = 1").fetchone()
        days = connection.execute("SELECT day, counted, limited FROM daily ORDER BY day DESC LIMIT 14").fetchall()
        keys = connection.execute("SELECT count(*) FROM visits").fetchone()[0]
    finally:
        connection.close()
    print(f"integritet: {integrity}")
    print(f"skjemaversjon: {version}")
    print(f"total: {total}")
    print(f"siden: {since}")
    print(f"besøksnøkler i minnet: {keys}")
    for day, counted, limited in days:
        print(f"{day}: {counted} telt, {limited} avvist av grensene")
    if integrity != "ok" or version != 1:
        raise SystemExit(1)


def backup(path: Path, target: Path) -> None:
    if target.exists():
        raise SystemExit(f"Nekter å overskrive: {target}")
    source = open_existing(path)
    copy = sqlite3.connect(target)
    try:
        source.backup(copy)
    finally:
        copy.close()
        source.close()
    status(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("init")
    command.add_argument("database", type=Path)
    command.add_argument("--since", default=None, help="Startdato (ÅÅÅÅ-MM-DD), standard er dagens dato i Norge")
    command = commands.add_parser("status")
    command.add_argument("database", type=Path)
    command = commands.add_parser("backup")
    command.add_argument("database", type=Path)
    command.add_argument("target", type=Path)
    args = parser.parse_args()
    if args.command == "init":
        init(args.database, args.since or today_oslo())
    elif args.command == "status":
        status(args.database)
    else:
        backup(args.database, args.target)


if __name__ == "__main__":
    sys.exit(main())
