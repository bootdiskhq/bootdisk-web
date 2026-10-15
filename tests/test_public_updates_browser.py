"""Browser checks for "Sist lagt til og oppdatert" on the front page and updates.html.

Packaged releases built from the labelled test history (tests/synthetic_updates.py,
PRØVEDATA) are served over HTTP and driven in Chromium: rendering, links to existing
detail pages, filters, search, paging, address and back button, the distinct states,
keyboard, narrow screens and what the pages request. A 5 000-row fixture checks search
and paging at scale. The data is invented and says nothing about the real archive.

Skipped without Playwright or a browser (as on CI). A skipped test is not a passed test.
Set CURATOR_CHROMIUM to a Chromium binary if Playwright's own download is not used.
"""
import contextlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import synthetic_updates as su  # noqa: E402
from test_publication import serve  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment dependent
    sync_playwright = None

EXPECTED_ROWS = ["K37", "kcd-1-2001--K1", "kcd-8-2001--K5", "K3", "kcd-8-2001--K1", "kcd-8-2001--K2", "kcd-9-2000--K7"]


@unittest.skipUnless(sync_playwright, "Playwright is required for the browser checks")
class PublicUpdatesBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stack = contextlib.ExitStack()
        work = Path(cls._stack.enter_context(tempfile.TemporaryDirectory()))
        history = su.build_history(work / "history")
        packages = {"main": (history["r3"], history["register3"]), "plain": (history["r3"], None),
                    "baseline": (history["r1"], history["register1"])}
        cls.bases = {}
        for name, (data, register) in packages.items():
            result = su.package(data, history["publish"], work / name, register)
            if result.returncode:
                raise AssertionError(result.stderr)
            cls.bases[name] = cls._stack.enter_context(serve(work / name)).rstrip("/")
        cls.bases["large"] = cls._stack.enter_context(serve(su.large_fixture(work / "large"))).rstrip("/")
        cls.base = cls.bases["main"]
        playwright = cls._stack.enter_context(sync_playwright())
        try:
            cls.browser = playwright.chromium.launch(executable_path=os.environ.get("CURATOR_CHROMIUM") or None)
        except Exception as error:  # pragma: no cover - environment dependent
            cls._stack.close()
            raise unittest.SkipTest(f"No Chromium available: {error}")
        cls._stack.callback(cls.browser.close)

    @classmethod
    def tearDownClass(cls):
        cls._stack.close()

    @contextlib.contextmanager
    def page(self, path="/", base=None, width=1280, height=900, routes=(), wait=None):
        context = self.browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        failures, requests = [], []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.on("request", lambda request: requests.append((request.method, request.url)))
        for pattern, handler in routes:
            page.route(pattern, handler)
        page.requests = requests
        page.goto((base or self.base) + path, wait_until="networkidle")
        if wait:
            page.wait_for_selector(wait)
        try:
            yield page
            self.assertEqual(failures, [], "the page raised a script error")
        finally:
            context.close()

    def rows(self, page, selector="#updates-list"):
        return page.eval_on_selector_all(f"{selector} .update-link", "links => links.map(link => new URL(link.href).searchParams.get('entry'))")

    def data_requests(self, page):
        return sorted({url.split("/", 3)[3] for method, url in page.requests if "/data/" in url or url.endswith(".json")})

    def test_front_page_shows_the_newest_rows_below_the_collections(self):
        with self.page("/", wait="#landing-updates-list .update-link") as page:
            self.assertEqual(self.rows(page, "#landing-updates-list"), EXPECTED_ROWS)
            self.assertEqual(page.locator(".collection-feature").count(), 1)
            order = page.evaluate("[...document.querySelectorAll('#landing section')].map(s => s.className)")
            self.assertLess(order.index("landing-collections"), order.index("landing-updates"))
            self.assertEqual(page.get_attribute("#landing-updates-all a", "href"), "updates.html")
            self.assertEqual(page.text_content("#landing-updates-all a"), "Se alle oppdateringer")
            self.assertIn("Viser nye kildeposter og innholdsendringer publisert på Bootdisk.", page.text_content("#landing-updates"))
            self.assertEqual(self.data_requests(page), ["collections.json", "data/index.json", "data/public-updates.json"])

    def test_front_page_shows_at_most_eight(self):
        with self.page("/", base=self.bases["large"], wait="#landing-updates-list .update-link") as page:
            self.assertEqual(page.locator("#landing-updates-list .update-item").count(), 8)

    def test_rows_show_name_cd_date_badge_and_explanation(self):
        with self.page("/updates.html", wait=".update-link") as page:
            self.assertEqual(self.rows(page), EXPECTED_ROWS)
            first = page.locator(".update-item").nth(3)
            self.assertEqual(first.locator(".update-title strong").text_content(), "Testkatt")
            self.assertEqual(first.locator(".update-version").text_content(), "versjon 4.2")
            self.assertEqual(first.locator(".update-badge").text_content(), "Oppdatert")
            self.assertEqual(first.locator(".update-medium").text_content(), "K-CD 15/2001")
            self.assertEqual(first.locator("time").text_content(), "29. mars 2026")
            self.assertEqual(first.locator("time").get_attribute("datetime"), "2026-03-28T23:30:00Z")
            self.assertEqual(first.locator(".update-explanation").text_content(),
                             "Programnavn og versjon avklart. Innholdstype avklart: program. Utgave avklart: prøveversjon.")
            self.assertEqual(page.locator(".update-item").nth(0).locator("time").text_content(), "25. oktober 2026")
            vakt = page.locator(".update-item").nth(4)
            self.assertEqual(vakt.locator(".update-version").count(), 0)
            self.assertEqual(vakt.locator(".update-explanation").text_content(), "Program identifisert, versjonen er fortsatt ukjent.")
            new = page.locator(".update-item").nth(6)
            self.assertEqual(new.locator(".update-badge").text_content(), "Ny kildepost")
            self.assertEqual(new.locator(".update-icon").text_content(), "P")
            self.assertEqual(new.locator(".update-icon img").count(), 0)
            self.assertEqual(page.locator(".update-item").nth(0).locator(".update-icon img").count(), 1)
            for text in page.locator(".update-title strong").all_text_contents():
                self.assertNotRegex(text, r"^(K\d+|kcd-|Tool|[0-9a-f]{16})")

    def test_rows_link_to_the_existing_detail_pages(self):
        for position, entry, heading in ((6, "kcd-9-2000--K7", "Prøvepost lagt til i test-r2"), (0, "K37", "Winamp")):
            with self.subTest(entry), self.page("/updates.html", wait=".update-link") as page:
                page.locator(".update-link").nth(position).click()
                page.wait_for_selector("#entry-breadcrumbs li[aria-current=page]")
                self.assertEqual(page.url, f"{self.base}/index.html?entry={entry}")
                self.assertEqual(page.text_content("#software-name"), heading)
                self.assertFalse(page.is_visible("#landing-updates"))

    def test_removed_entry_is_not_listed(self):
        with self.page("/updates.html", wait=".update-link") as page:
            self.assertNotIn(su.REMOVED_IN_R3, self.rows(page))
            hrefs = page.eval_on_selector_all(".update-link", "links => links.map(l => l.href)")
            for href in hrefs:
                self.assertEqual(self.browser_status(href), 200)

    def browser_status(self, href):
        entry = href.split("entry=", 1)[1]
        import urllib.request
        with urllib.request.urlopen(f"{self.base}/data/{entry.lower()}.json") as response:
            return response.status

    def test_filters_search_address_and_back_button(self):
        with self.page("/updates.html", wait=".update-link") as page:
            page.check("input[value=added]")
            self.assertEqual(self.rows(page), ["kcd-9-2000--K7"])
            self.assertEqual(page.url, f"{self.base}/updates.html?type=added")
            page.check("input[value=updated]")
            page.fill("#updates-search", "winamp")
            self.assertEqual(self.rows(page), ["K37", "kcd-8-2001--K5"])
            self.assertEqual(page.url, f"{self.base}/updates.html?type=updated&q=winamp")
            self.assertEqual(page.text_content("#updates-count"), "Viser 2 av 2 kildeposter")
            page.fill("#updates-search", "K-CD 8/2001")
            self.assertEqual(self.rows(page), ["kcd-8-2001--K5", "kcd-8-2001--K1", "kcd-8-2001--K2"])
            filtered = page.url
            page.locator(".update-link").first.click()
            page.wait_for_selector("#entry-breadcrumbs li[aria-current=page]")
            page.go_back()
            page.wait_for_selector(".update-link")
            self.assertEqual(page.url, filtered)
            self.assertEqual(page.input_value("#updates-search"), "K-CD 8/2001")
            self.assertTrue(page.is_checked("input[value=updated]"))
            self.assertEqual(len(self.rows(page)), 3)
        with self.page("/updates.html?type=added&q=pr%C3%B8vepost", wait=".update-link") as page:
            self.assertEqual(self.rows(page), ["kcd-9-2000--K7"])
            page.click("#updates-reset")
            self.assertEqual(self.rows(page), EXPECTED_ROWS)
            self.assertEqual(page.url, f"{self.base}/updates.html")

    def test_no_match_is_its_own_state(self):
        with self.page("/updates.html", wait=".update-link") as page:
            page.fill("#updates-search", "finnes ikke")
            self.assertEqual(page.get_attribute("#updates-status", "data-state"), "no-match")
            self.assertEqual(page.text_content("#updates-status"), "Ingen oppdateringer passer med søket eller filteret.")
            self.assertFalse(page.is_visible("#updates-list"))
            self.assertTrue(page.is_visible("#updates-tools"))

    def test_missing_empty_and_failing_history_are_distinct_and_leave_the_site_working(self):
        cases = {
            "missing": (self.bases["plain"], (), "Endringsoversikten er ikke publisert ennå."),
            "empty": (self.bases["baseline"], (), "Ingen nye eller oppdaterte kildeposter er registrert ennå."),
            "error": (self.base, (("**/data/public-updates.json", lambda route: route.fulfill(status=500, body="feil")),),
                      "Endringsoversikten kunne ikke lastes akkurat nå."),
            "invalid": (self.base, (("**/data/public-updates.json", lambda route: route.fulfill(status=200, body="{ikke json", content_type="application/json")),),
                        "Endringsoversikten kunne ikke lastes akkurat nå."),
            "wrong schema": (self.base, (("**/data/public-updates.json", lambda route: route.fulfill(status=200, body='{"schema":"x"}', content_type="application/json")),),
                             "Endringsoversikten kunne ikke lastes akkurat nå."),
        }
        for name, (base, routes, message) in cases.items():
            state = "error" if name in ("invalid", "wrong schema") else name
            with self.subTest(name), self.page("/updates.html", base=base, routes=routes) as page:
                page.wait_for_function("document.querySelector('main').getAttribute('aria-busy') === 'false'")
                self.assertEqual(page.get_attribute("#updates-status", "data-state"), state)
                self.assertIn(message, page.text_content("#updates-status"))
                self.assertFalse(page.is_visible("#updates-tools"))
                self.assertEqual(page.locator(".update-item").count(), 0)
            with self.subTest(f"front page, {name}"), self.page("/", base=base, routes=routes, wait=".collection-feature") as page:
                page.wait_for_timeout(100)
                self.assertEqual(page.locator(".collection-feature").count(), 1)
                self.assertEqual(page.locator(".collection-stats dd").all_text_contents()[0], "7")
                if name == "missing":
                    self.assertFalse(page.is_visible("#landing-updates"))
                elif name == "empty":
                    self.assertEqual(page.get_attribute("#landing-updates-status", "data-state"), "empty")
                    self.assertFalse(page.is_visible("#landing-updates-all"))
                else:
                    self.assertEqual(page.get_attribute("#landing-updates-status", "data-state"), "error")
                    self.assertIn("Samlingene og arkivet er ikke berørt", page.text_content("#landing-updates-status"))
            with self.subTest(f"archive, {name}"), self.page("/archive.html", base=base, routes=routes, wait=".archive-card") as page:
                self.assertGreater(page.locator(".archive-card").count(), 0)

    def test_source_text_is_never_html(self):
        def index_with_html(route):
            response = route.fetch()
            index = response.json()
            for summary in index["entries"]:
                if summary["entry"] == "K3":
                    summary["software_name"] = '<img src=x onerror="window.__updatesXss=1">Testkatt & "sitat"'
            route.fulfill(response=response, body=json.dumps(index), content_type="application/json")
        with self.page("/updates.html", routes=(("**/data/index.json", index_with_html),), wait=".update-link") as page:
            self.assertIn('<img src=x onerror="window.__updatesXss=1">Testkatt & "sitat"', page.locator(".update-title strong").all_text_contents())
            self.assertIsNone(page.evaluate("window.__updatesXss"))
            self.assertEqual(page.locator(".update-title img").count(), 0)

    def test_five_thousand_rows_page_in_portions_of_25_without_per_entry_requests(self):
        started = time.perf_counter()
        with self.page("/updates.html", base=self.bases["large"], wait=".update-link") as page:
            loaded = time.perf_counter() - started
            self.assertEqual(page.locator(".update-item").count(), 25)
            self.assertEqual(page.text_content("#updates-count"), "Viser 25 av 5\u00a0000 kildeposter")
            page.click("#updates-more")
            self.assertEqual(page.locator(".update-item").count(), 50)
            focused = page.evaluate("document.activeElement.closest('.update-item') === document.querySelectorAll('.update-item')[25]")
            self.assertTrue(focused, "focus moves to the first new row")
            started = time.perf_counter()
            page.check("input[value=added]")
            filter_ms = (time.perf_counter() - started) * 1000
            self.assertEqual(page.locator(".update-item").count(), 25, "a new filter starts at the first portion")
            self.assertEqual(page.text_content("#updates-count"), "Viser 25 av 1\u00a0000 kildeposter")
            started = time.perf_counter()
            page.fill("#updates-search", "Prøveprogram 4996")
            search_ms = (time.perf_counter() - started) * 1000
            self.assertEqual(self.rows(page), ["provecd-6-1999--K500"])
            page.fill("#updates-search", "Prøve-CD 1/1999")
            self.assertEqual(page.text_content("#updates-count"), "Viser 25 av 500 kildeposter")
            page.check("input[value=updated]")
            self.assertEqual(page.text_content("#updates-count"), "Viser 0 av 5\u00a0000 kildeposter")
            self.assertEqual(page.get_attribute("#updates-status", "data-state"), "no-match")
            page.fill("#updates-search", "Prøve-CD 3/1999")
            self.assertEqual(page.text_content("#updates-count"), "Viser 25 av 500 kildeposter")
            for _ in range(19):
                page.click("#updates-more")
            self.assertEqual(page.locator(".update-item").count(), 500)
            self.assertFalse(page.is_visible("#updates-more"))
            self.assertEqual(self.data_requests(page), ["data/index.json", "data/public-updates.json"])
            print(f"\n5000 update rows in Chromium: load {loaded * 1000:.0f} ms, filter {filter_ms:.1f} ms, search {search_ms:.1f} ms")
            self.assertLess(filter_ms, 1000)
            self.assertLess(search_ms, 1000)

    def test_keyboard_reaches_filters_search_and_rows_with_visible_focus(self):
        with self.page("/updates.html", wait=".update-link") as page:
            page.focus("#updates-search")
            page.keyboard.press("Shift+Tab")
            self.assertEqual(page.evaluate("document.activeElement.value"), "all")
            page.keyboard.press("ArrowRight")
            self.assertEqual(page.evaluate("document.activeElement.value"), "added")
            self.assertEqual(self.rows(page), ["kcd-9-2000--K7"])
            outline = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
            self.assertNotEqual(outline, "none")
            page.keyboard.press("ArrowLeft")
            for _ in range(3):
                page.keyboard.press("Tab")
            self.assertEqual(page.evaluate("document.activeElement.className"), "update-link")
            style = page.evaluate("[getComputedStyle(document.activeElement).borderColor, getComputedStyle(document.activeElement).outlineStyle]")
            self.assertTrue(style[0] == "rgb(98, 230, 255)" or style[1] != "none", style)
            page.keyboard.press("Enter")
            page.wait_for_selector("#entry-breadcrumbs li[aria-current=page]")
            self.assertIn("index.html?entry=K37", page.url)

    def test_narrow_screens_have_no_horizontal_scroll_and_readable_dates(self):
        for path, wait in (("/updates.html", ".update-link"), ("/", "#landing-updates-list .update-link")):
            for width in (320, 360):
                with self.subTest(path=path, width=width), self.page(path, width=width, height=740, wait=wait) as page:
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                    for box in page.eval_on_selector_all("time", "els => els.map(e => e.getBoundingClientRect().right)"):
                        self.assertLessEqual(box, width)
                    size = page.evaluate("parseFloat(getComputedStyle(document.querySelector('.update-item time')).fontSize)")
                    self.assertGreaterEqual(size, 11)
        with self.page("/updates.html", width=360, wait=".update-link") as page:
            radio = page.evaluate("document.querySelector('.updates-type label').getBoundingClientRect().height")
            self.assertGreaterEqual(radio, 44)


if __name__ == "__main__":
    unittest.main()
