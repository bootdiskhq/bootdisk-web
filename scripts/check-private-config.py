#!/usr/bin/env python3
"""Kontroller at private driftsverdier ikke har lekket inn i Git eller i en releasepakke.

Verdiene (mottakeradresse, avsender, CAPTCHA-nøkler, SMTP-passord, salt …) leses fra en fil
med én verdi per linje. Filen skal ligge utenfor repositoryet. Skriptet skriver aldri ut en
verdi, bare nummeret dens og hvor den ble funnet.

    python scripts/check-private-config.py --values-file ~/privat/verdier.txt \\
        --git origin/main..HEAD --tree dist/bootdisk-web --zip dist/bootdisk-web-1.2.0.zip

Kontrollene:
  --git RANGE  commit-meldinger og differ i RANGE, pluss endringer som ikke er committet,
               og grennavnet.
  --tree DIR   hver fil under DIR (binært), og filnavn som bare hører til privat oppsett.
  --zip ZIP    hver fil i ZIP-arkivet, og navnene i det.

Hver verdi søkes som den er, uten hensyn til store og små bokstaver, og URL-kodet (@ som %40).
Utgangskode 0: ingen funn. 1: funn. 2: feil bruk. Se docs/kontaktskjema.md.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_NAMES = ("kontakt-config.php", "bootdisk-privat")
MIN_LENGTH = 6


def read_values(path: Path) -> list[str]:
    values = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    values = [value for value in values if value and not value.startswith("#")]
    short = [index for index, value in enumerate(values, 1) if len(value) < MIN_LENGTH]
    if short:
        raise SystemExit(f"verdi {short} er kortere enn {MIN_LENGTH} tegn og gir falske funn; bruk hele verdien")
    if not values:
        raise SystemExit("verdifilen er tom")
    return values


def needles(values: list[str]) -> list[tuple[int, bytes]]:
    found: list[tuple[int, bytes]] = []
    for number, value in enumerate(values, 1):
        variants = {value.lower(), quote(value, safe="").lower()}
        found.extend((number, variant.encode("utf-8")) for variant in variants)
    return found


def scan_bytes(data: bytes, where: str, wanted: list[tuple[int, bytes]], hits: list[str]) -> None:
    lowered = data.lower()
    for number in sorted({number for number, needle in wanted if needle in lowered}):
        hits.append(f"verdi #{number} i {where}")


def private_name(path: PurePosixPath) -> bool:
    return any(part in PRIVATE_NAMES for part in path.parts)


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True).stdout


def scan_git(range_: str, wanted, hits: list[str]) -> int:
    scan_bytes(git("log", "-p", "--format=commit %H%n%B", range_), f"git log -p {range_}", wanted, hits)
    scan_bytes(git("diff", "HEAD"), "endringer som ikke er committet", wanted, hits)
    scan_bytes(git("rev-parse", "--abbrev-ref", "HEAD"), "grennavnet", wanted, hits)
    untracked = git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    for name in filter(None, untracked):
        path = ROOT / name.decode("utf-8")
        if path.is_file():
            scan_bytes(path.read_bytes(), f"usporet fil {name.decode('utf-8')}", wanted, hits)
    changed = git("diff", "--name-only", range_).decode("utf-8").split()
    for name in changed:
        if private_name(PurePosixPath(name)):
            hits.append(f"privat filnavn i {range_}: {name}")
    return len(changed)


def scan_tree(directory: Path, wanted, hits: list[str]) -> int:
    count = 0
    for path in sorted(directory.rglob("*")):
        relative = PurePosixPath(path.relative_to(directory).as_posix())
        if private_name(relative):
            hits.append(f"privat filnavn i {directory}: {relative}")
        if path.is_file():
            count += 1
            scan_bytes(path.read_bytes(), f"{directory.name}/{relative}", wanted, hits)
    return count


def scan_zip(archive: Path, wanted, hits: list[str]) -> int:
    count = 0
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            name = PurePosixPath(info.filename)
            if private_name(name):
                hits.append(f"privat filnavn i {archive.name}: {name}")
            if not info.is_dir():
                count += 1
                scan_bytes(bundle.read(info), f"{archive.name}:{name}", wanted, hits)
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--values-file", type=Path, required=True, help="Én privat verdi per linje; filen ligger utenfor repositoryet")
    parser.add_argument("--git", metavar="RANGE", help="Git-område, for eksempel origin/main..HEAD")
    parser.add_argument("--tree", type=Path, action="append", default=[], help="Katalog som skal kontrolleres (kan gjentas)")
    parser.add_argument("--zip", type=Path, action="append", default=[], help="ZIP-arkiv som skal kontrolleres (kan gjentas)")
    args = parser.parse_args(argv)
    if not (args.git or args.tree or args.zip):
        parser.error("oppgi minst én av --git, --tree og --zip")
    values_file = args.values_file.resolve()
    if values_file.is_relative_to(ROOT.resolve()):
        parser.error("verdifilen ligger i repositoryet; flytt den ut, så den aldri kan bli committet")
    wanted = needles(read_values(values_file))
    hits: list[str] = []
    if args.git:
        print(f"git {args.git}: {scan_git(args.git, wanted, hits)} endrede filer kontrollert")
    for directory in args.tree:
        print(f"katalog {directory}: {scan_tree(directory, wanted, hits)} filer kontrollert")
    for archive in args.zip:
        print(f"zip {archive}: {scan_zip(archive, wanted, hits)} filer kontrollert")
    for hit in hits:
        print(f"FUNN: {hit}")
    print("privat konfig: " + ("LEKKASJE" if hits else "ingen funn"))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
