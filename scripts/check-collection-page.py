#!/usr/bin/env python3
"""Check a served Bootdisk release in a real browser: front page, collection and CD pages.

Use it for acceptance against real data. It reads what the pages actually render, so a
count that only exists in JSON does not pass. Requires Playwright and Chromium:

    python scripts/check-collection-page.py http://127.0.0.1:8797/ \\
        --expect "K-CD 15/2001=39" --expect "K-CD 8/2001=32" ...

The discs must appear exactly once each, in the given order (newest first), with the
given number of source entries; each CD link must open a filtered archive with that
many cards, and the front page totals must equal the sums.
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--collection", default="komputer-for-alle")
    parser.add_argument("--expect", action="append", required=True, metavar="LABEL=COUNT",
                        help="Expected disc label and source-entry count, in expected order")
    parser.add_argument("--chromium", default=os.environ.get("CURATOR_CHROMIUM"))
    args = parser.parse_args()
    expected = [(label.strip(), int(count)) for label, count in (item.rsplit("=", 1) for item in args.expect)]
    base = args.base_url.rstrip("/")

    from playwright.sync_api import sync_playwright

    problems = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chromium or None)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        page.goto(f"{base}/", wait_until="networkidle")
        if not page.url.rstrip("/").endswith(base.split("//", 1)[1]):
            problems.append(f"front page redirected to {page.url}")
        feature = page.locator(f".collection-feature:has(a[href='collection.html?collection={args.collection}'])")
        totals = feature.locator(".collection-stats dd").all_text_contents()
        want = [str(len(expected)), str(sum(count for _, count in expected))]
        print(f"front page: {totals[0] if totals else '?'} CD-er, {totals[1] if len(totals) > 1 else '?'} kildeposter")
        if [value.replace(" ", "").replace(" ", "") for value in totals] != want:
            problems.append(f"front page totals {totals} != {want}")

        page.goto(f"{base}/collection.html?collection={args.collection}", wait_until="networkidle")
        cards = page.eval_on_selector_all(".disc-card", """cards => cards.map(card => [
            card.querySelector('.disc-label').textContent, card.querySelector('.disc-count').textContent, card.getAttribute('href')])""")
        seen = [(label, int(count.split()[0].replace(" ", ""))) for label, count, _ in cards]
        for label, count in seen:
            print(f"{label}: {count} kildeposter")
        if seen != expected:
            problems.append(f"collection cards {seen} != {expected}")

        for label, _, href in cards:
            page.goto(f"{base}/{href}", wait_until="networkidle")
            shown = page.locator(".archive-card").count()
            title = page.text_content("#archive-title")
            want_count = dict(expected).get(label)
            print(f"{href}: «{title}», {shown} kort")
            if title != label or shown != want_count:
                problems.append(f"{href} shows «{title}» with {shown} cards, expected «{label}» with {want_count}")
        if errors:
            problems.append(f"script errors: {errors}")
        browser.close()

    for problem in problems:
        print(f"FEIL: {problem}", file=sys.stderr)
    print("collection page check: " + ("failed" if problems else "passed"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
