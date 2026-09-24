"""Browser checks for the Bootdisk front page, collection page and CD view.

A packaged release built from synthetic data (tests/synthetic_collection.py) is served
over HTTP and driven in Chromium: the public flow, direct reopening, history, states,
keyboard, narrow screens, reduced motion and what the pages request. The data is
invented; these checks say nothing about the real seven-disc archive.

Skipped without Playwright or a browser (as on CI). Run locally with:

    pip install playwright && playwright install chromium
    python -m unittest tests.test_publication_browser -v

Set CURATOR_CHROMIUM to a Chromium binary if Playwright's own download is not used.
"""
import contextlib
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import synthetic_collection as synthetic  # noqa: E402
from test_publication import FICTIONAL, PRODUCTION_REGISTRY, serve  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment dependent
    sync_playwright = None

EXPECTED_ORDER = ["K-CD 15/2001", "K-CD 8/2001", "K-CD 1/2001", "K-CD 13/2000", "K-CD 9/2000", "K-CD 4/2000", "K-CD 1/2000"]
EXPECTED_COUNTS = ["6 kildeposter", "4 kildeposter", "5 kildeposter", "3 kildeposter", "2 kildeposter", "2 kildeposter", "3 kildeposter"]


@unittest.skipUnless(sync_playwright, "Playwright is required for the browser checks")
class PublicationBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stack = contextlib.ExitStack()
        work = Path(cls._stack.enter_context(tempfile.TemporaryDirectory()))
        data, publish = synthetic.build_synthetic(work / "seven")
        result = synthetic.package(data, publish, work / "release")
        if result.returncode:
            raise AssertionError(result.stderr)
        # An eighth disc and a fictional second publication, added through data and registry only.
        data, publish = synthetic.build_synthetic(work / "wider", extra=[
            ("kcd-5-2001", "K-CD 5/2001", synthetic.PUBLICATION, ["K1", "K2"]),
            ("testbladet-2-1999", "Testbladet 2/1999", "TESTBLADET (FIKTIV)", ["K1", "K2"]),
            ("testbladet-10-1999", "Testbladet 10/1999", "TESTBLADET (FIKTIV)", ["K1"])])
        registry = copy.deepcopy(PRODUCTION_REGISTRY)
        registry["collections"].append(FICTIONAL)
        (work / "registry.json").write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
        result = synthetic.package(data, publish, work / "wider-release", work / "registry.json")
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.index = json.loads((work / "release/data/index.json").read_text(encoding="utf-8"))
        cls.base = cls._stack.enter_context(serve(work / "release")).rstrip("/")
        cls.wider = cls._stack.enter_context(serve(work / "wider-release")).rstrip("/")
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
    def page(self, path="/", base=None, width=1280, height=900, routes=(), **context_options):
        context = self.browser.new_context(viewport={"width": width, "height": height}, **context_options)
        page = context.new_page()
        failures, requests = [], []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.on("request", lambda request: requests.append((request.method, request.url)))
        for pattern, handler in routes:
            page.route(pattern, handler)
        page.requests = requests
        page.goto((base or self.base) + path, wait_until="networkidle")
        try:
            yield page
            self.assertEqual(failures, [], "the page raised a script error")
        finally:
            context.close()

    def card_texts(self, page):
        return page.eval_on_selector_all(".disc-card", "cards => cards.map(card => [card.querySelector('.disc-label').textContent, card.querySelector('.disc-count').textContent])")

    def test_root_and_index_show_the_front_page_without_redirect(self):
        for path in ("/", "/index.html"):
            with self.subTest(path), self.page(path) as page:
                self.assertEqual(page.url, self.base + path)
                self.assertEqual(page.text_content("h1:visible"), "Bootdisk")
                self.assertFalse(page.is_visible("#entry-view"))
                feature = page.locator(".collection-feature")
                self.assertEqual(feature.count(), 1)
                self.assertEqual(feature.locator("h3").text_content(), "Komputer for alle")
                self.assertEqual(feature.locator(".collection-stats dd").all_text_contents(), ["7", "25"])
                self.assertEqual(feature.locator("a").get_attribute("href"), "collection.html?collection=komputer-for-alle")
                self.assertEqual(page.get_attribute("text=Alle kildeposter >> nth=0", "href"), "archive.html")
                self.assertEqual(page.get_attribute("link[rel=canonical]", "href"), "https://bootdisk.no/")

    def test_front_page_collection_cd_entry_and_back(self):
        with self.page("/") as page:
            page.click("text=Utforsk Komputer for alle")
            page.wait_for_selector(".disc-card")
            self.assertEqual(page.url, f"{self.base}/collection.html?collection=komputer-for-alle")
            self.assertEqual(page.title(), "Komputer for alle — Bootdisk")
            page.click(".disc-card:has-text('K-CD 13/2000')")
            page.wait_for_selector(".archive-card")
            self.assertEqual(page.url, f"{self.base}/archive.html?medium=kcd-13-2000")
            self.assertEqual(page.text_content("#archive-title"), "K-CD 13/2000")
            self.assertEqual(page.locator("#archive-breadcrumbs li").all_text_contents(), ["Bootdisk", "Komputer for alle", "K-CD 13/2000"])
            self.assertEqual(page.locator(".archive-card").count(), 3)
            self.assertEqual(page.input_value("#archive-medium"), "kcd-13-2000")
            page.fill("#archive-search", "Prøvepost 2")
            page.wait_for_function("document.querySelectorAll('.archive-card').length === 1")
            self.assertIn("medium=kcd-13-2000", page.url)
            self.assertIn("q=", page.url)
            filtered = page.url
            page.click(".archive-card")
            page.wait_for_selector("#entry-breadcrumbs li[aria-current=page]")
            self.assertEqual(page.url, f"{self.base}/index.html?entry=kcd-13-2000--K2")
            self.assertEqual(page.locator("#entry-breadcrumbs li").all_text_contents(),
                             ["Bootdisk", "Komputer for alle", "K-CD 13/2000", "Prøvepost 2 på K-CD 13/2000"])
            self.assertEqual(page.get_attribute("#entry-breadcrumbs a >> nth=2", "href"), "archive.html?medium=kcd-13-2000")
            self.assertFalse(page.is_visible("#landing"))
            page.go_back()
            page.wait_for_selector(".archive-card")
            self.assertEqual(page.url, filtered)
            self.assertEqual(page.input_value("#archive-search"), "Prøvepost 2")
            self.assertEqual(page.input_value("#archive-medium"), "kcd-13-2000")
            self.assertEqual(page.locator(".archive-card").count(), 1)
            page.click("#medium-links >> text=Tilbake til Komputer for alle")
            page.wait_for_selector(".disc-card")
            self.assertEqual(page.url, f"{self.base}/collection.html?collection=komputer-for-alle")

    def test_direct_reopening_gives_the_same_content(self):
        with self.page("/collection.html?collection=komputer-for-alle") as first, \
                self.page("/collection.html?collection=komputer-for-alle") as second:
            self.assertEqual(self.card_texts(first), self.card_texts(second))
        with self.page("/archive.html?medium=kcd-9-2000") as page:
            self.assertEqual(page.text_content("#archive-title"), "K-CD 9/2000")
            self.assertEqual(page.title(), "K-CD 9/2000 — Komputer for alle — Bootdisk")
            self.assertEqual(page.locator(".archive-card").count(), 2)

    def test_every_disc_once_in_numeric_order_with_counts_from_data(self):
        with self.page("/collection.html?collection=komputer-for-alle") as page:
            cards = self.card_texts(page)
            self.assertEqual([label for label, _ in cards], EXPECTED_ORDER)
            self.assertEqual([count for _, count in cards], EXPECTED_COUNTS)
            self.assertEqual(page.locator(".disc-year-group h3").all_text_contents(), ["2001", "2000"])
            self.assertEqual(page.text_content("#media-summary"), "7 CD-er med til sammen 25 kildeposter. Nyeste utgave først.")
            self.assertEqual(page.locator(".disc-card a").count(), 0, "cards contain no nested links")
            self.assertEqual(page.locator(".disc-card img").count(), 0, "no program screenshot stands in for a cover")
            self.assertEqual(page.locator("#collection-breadcrumbs li").all_text_contents(), ["Bootdisk", "Komputer for alle"])
            self.assertEqual(page.get_attribute("link[rel=canonical]", "href"), "https://bootdisk.no/collection.html?collection=komputer-for-alle")
            self.assertTrue(page.is_visible("text=Om bladet og CD-ene"))
            self.assertEqual(page.locator("#sources-list a").count(), 3)

    def test_eighth_disc_and_second_publication_come_from_data_and_registry(self):
        with self.page("/", base=self.wider) as page:
            features = page.locator(".collection-feature")
            self.assertEqual(features.locator("h3").all_text_contents(), ["Komputer for alle", "Testbladet (fiktiv)"])
            self.assertEqual(features.nth(0).locator("dd").all_text_contents(), ["8", "27"])
            self.assertEqual(features.nth(1).locator("dd").all_text_contents(), ["2", "3"])
        with self.page("/collection.html?collection=komputer-for-alle", base=self.wider) as page:
            labels = [label for label, _ in self.card_texts(page)]
            self.assertEqual(labels[:4], ["K-CD 15/2001", "K-CD 8/2001", "K-CD 5/2001", "K-CD 1/2001"])
            self.assertEqual(len(labels), 8)
            self.assertFalse(any("Testbladet" in label for label in labels))
        with self.page("/collection.html?collection=testbladet-fiktiv", base=self.wider) as page:
            self.assertEqual(self.card_texts(page), [["Testbladet 10/1999", "1 kildepost"], ["Testbladet 2/1999", "2 kildeposter"]])
            self.assertEqual(page.text_content("h1"), "Testbladet (fiktiv)")

    def test_old_and_namespaced_k37_open_their_own_entries(self):
        for entry, name, medium in (("K37", "Winamp", "K-CD 15/2001"), ("kcd-1-2001--K37", "WinZip", "K-CD 1/2001")):
            with self.subTest(entry), self.page(f"/index.html?entry={entry}") as page:
                page.wait_for_selector("#entry-breadcrumbs li[aria-current=page]")
                self.assertEqual(page.text_content("#software-name"), name)
                self.assertEqual(page.text_content("#fact-medium"), medium)
                self.assertEqual(page.locator("#entry-breadcrumbs li").all_text_contents()[1:3], ["Komputer for alle", medium])
                self.assertEqual(page.get_attribute("#canonical-url", "href"), f"https://bootdisk.no/index.html?entry={entry}")

    def test_source_values_with_html_are_text(self):
        with self.page("/archive.html?medium=kcd-1-2001") as page:
            page.wait_for_selector(".archive-card")
            self.assertIn('<img src=x onerror="window.__xss=1"> Prøvepost & "sitat"', page.text_content("#archive-grid"))
        with self.page("/index.html?entry=kcd-1-2001--K40") as page:
            page.wait_for_selector("#entry-breadcrumbs li[aria-current=page]")
            self.assertTrue(page.text_content("#software-name").startswith("<img src=x"))
            self.assertIsNone(page.evaluate("window.__xss"))
            self.assertEqual(page.locator("main img[src=x]").count(), 0)

    def test_front_and_collection_pages_read_only_the_index_and_registry(self):
        for path in ("/", "/collection.html?collection=komputer-for-alle"):
            with self.subTest(path), self.page(path) as page:
                data = sorted({url.split("/", 3)[3] for method, url in page.requests if "/data/" in url or url.endswith(".json")})
                self.assertEqual(data, ["collections.json", "data/index.json"])
                self.assertEqual({method for method, _ in page.requests}, {"GET"})

    def test_states_are_honest(self):
        def fail(status):
            return lambda route: route.fulfill(status=status, body="")

        def body(text):
            return lambda route: route.fulfill(status=200, content_type="application/json", body=text)

        # Truly empty: an index with no media, and a registered collection no medium belongs to.
        empty_index = {**self.index, "media": [], "entries": []}
        with_fictional = copy.deepcopy(PRODUCTION_REGISTRY)
        with_fictional["collections"].append(FICTIONAL)
        # Not empty: media the registry does not bind (a stale registry beside a newer
        # index) must fail, never be dropped from the counts.
        one_unbound = copy.deepcopy(self.index)
        one_unbound["media"][0]["publication"] = "UNREGISTERED"
        none_bound = copy.deepcopy(PRODUCTION_REGISTRY)
        none_bound["collections"][0]["publication_values"] = ["INGEN MEDIER HAR DENNE VERDIEN"]
        kfa = "/collection.html?collection=komputer-for-alle"
        cases = [
            ("/", [("**/collections.json", fail(404))], "#landing-status", "error", "ikke at arkivet er tomt"),
            ("/", [("**/data/index.json", body("{ ugyldig"))], "#landing-status", "error", "ikke at arkivet er tomt"),
            ("/", [("**/data/index.json", body(json.dumps(empty_index)))], "#landing-status", "empty", "Ingen samlinger er publisert"),
            ("/", [("**/data/index.json", body(json.dumps(one_unbound)))], "#landing-status", "error", "ikke at arkivet er tomt"),
            ("/", [("**/collections.json", body(json.dumps(none_bound)))], "#landing-status", "error", "ikke at arkivet er tomt"),
            ("/collection.html?collection=testbladet-fiktiv", [("**/collections.json", body(json.dumps(with_fictional)))], "#media-status", "empty", "ingen publiserte CD-er"),
            (kfa, [("**/data/index.json", body(json.dumps(one_unbound)))], "#media-status", "error", "ikke at samlingen er tom"),
            (kfa, [("**/collections.json", body(json.dumps(none_bound)))], "#media-status", "error", "ikke at samlingen er tom"),
            ("/collection.html?collection=komputer-for-alle", [("**/data/index.json", fail(500))], "#media-status", "error", "ikke at samlingen er tom"),
            ("/collection.html?collection=komputer-for-alle", [("**/data/index.json", body('{"entries": 3}'))], "#media-status", "error", "ikke at samlingen er tom"),
            ("/collection.html?collection=komputer-for-alle", [("**/collections.json", body("[]"))], "#collection-status", "error", "ikke at samlingen er tom"),
            ("/collection.html?collection=finnes-ikke", [], "#collection-status", "unknown", "ingen samling med denne adressen"),
            ("/collection.html?collection=..%2F..%2Fdata%2Findex", [], "#collection-status", "unknown", "ingen samling med denne adressen"),
            ("/collection.html", [], "#collection-status", "unknown", "Ingen samling er valgt"),
        ]
        for path, routes, selector, state, text in cases:
            with self.subTest(path=path, state=state, text=text), self.page(path, routes=routes) as page:
                page.wait_for_selector(f"{selector}[data-state={state}]")
                self.assertIn(text, page.text_content(selector))
                self.assertEqual(page.locator(".disc-card").count(), 0)
                self.assertEqual(page.locator(".collection-feature").count(), 0)
                self.assertNotIn(">0<", page.inner_html("main"), "a failure is not a zero count")
                if selector == "#collection-status":
                    self.assertEqual(page.get_attribute("meta[name=robots]", "content"), "noindex")
                    self.assertEqual(page.locator("link[rel=canonical]").count(), 0)
                self.assertFalse(any("../" in url for _, url in page.requests))

    def test_unknown_and_unsafe_entries_are_not_the_front_page(self):
        for query, heading in (("?entry=K999", "Fant ikke arkivposten"), ("?entry=..%2Fsecret", "Fant ikke arkivposten"),
                               ("?entry=", "Fant ikke arkivposten"), ("?entry=kcd-99-2000--K1", "Fant ikke arkivposten")):
            with self.subTest(query), self.page(f"/index.html{query}") as page:
                page.wait_for_selector("#entry-error:not([hidden])")
                self.assertEqual(page.text_content("#software-name"), heading)
                self.assertFalse(page.is_visible("#landing"))
                self.assertEqual(page.get_attribute("meta[name=robots]", "content"), "noindex")
                self.assertEqual(page.locator("#canonical-url").count(), 0)
                self.assertFalse(any("secret" in url for _, url in page.requests if "/data/" in url))
        with self.page("/archive.html?medium=finnes-ikke") as page:
            page.wait_for_selector(".archive-card")
            self.assertIn("Fant ikke CD-en", page.text_content("#archive-notice"))
            self.assertEqual(page.text_content("#archive-title"), "Programvarearkivet")

    def test_keyboard_reaches_every_card_with_visible_focus(self):
        with self.page("/collection.html?collection=komputer-for-alle") as page:
            page.keyboard.press("Tab")
            self.assertEqual(page.evaluate("document.activeElement.className"), "skip-link")
            reached = []
            for _ in range(40):
                page.keyboard.press("Tab")
                element = page.evaluate("""() => { const e = document.activeElement; const s = getComputedStyle(e);
                    return {cls: e.className, label: e.querySelector?.('.disc-label')?.textContent ?? e.textContent, outline: s.outlineStyle, border: s.borderColor}; }""")
                if element["cls"] == "disc-card":
                    if element["label"] in reached:
                        break
                    reached.append(element["label"])
                    self.assertTrue(element["outline"] != "none" or element["border"] == "rgb(98, 230, 255)", "focus is visible")
            self.assertEqual(reached, EXPECTED_ORDER)
            # Focus has wrapped around to the first card again; Enter follows its link.
            page.keyboard.press("Enter")
            page.wait_for_url("**/archive.html?medium=kcd-15-2001")

    def test_heading_order_and_reading_order(self):
        with self.page("/collection.html?collection=komputer-for-alle") as page:
            headings = page.eval_on_selector_all("main h1, main h2, main h3", "items => items.filter(h => h.offsetParent).map(h => h.tagName + ' ' + h.textContent)")
            self.assertEqual(headings[:3], ["H1 Komputer for alle", "H2 Om bladet og CD-ene", "H2 CD-er i samlingen"])
            self.assertEqual(headings[3:5], ["H3 2001", "H3 2000"])
            self.assertEqual(headings[5:], ["H2 Om kildepostene", "H2 Kilder"])
        with self.page("/") as page:
            headings = page.eval_on_selector_all("main h1, main h2, main h3", "items => items.filter(h => h.offsetParent).map(h => h.tagName + ' ' + h.textContent)")
            self.assertEqual(headings, ["H1 Bootdisk", "H2 Samlinger", "H3 Komputer for alle"])

    def test_narrow_screen_has_no_horizontal_scroll(self):
        for path in ("/", "/collection.html?collection=komputer-for-alle", "/archive.html?medium=kcd-13-2000", "/index.html?entry=kcd-1-2001--K37"):
            with self.subTest(path), self.page(path, width=360, height=740) as page:
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 360)

    def test_disc_labels_fit_inside_their_cards(self):
        for width in (1280, 1100, 1024, 800, 360):
            with self.subTest(width=width), self.page("/collection.html?collection=komputer-for-alle", width=width) as page:
                spill = page.evaluate("""[...document.querySelectorAll('.disc-card')].filter(card =>
                    card.querySelector('.disc-label').getBoundingClientRect().right > card.getBoundingClientRect().right).length""")
                self.assertEqual(spill, 0)

    def test_desktop_archive_cd_view_has_no_horizontal_scroll(self):
        with self.page("/archive.html?medium=kcd-13-2000", width=1280) as page:
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 1280)

    def test_reduced_motion_stops_card_movement(self):
        with self.page("/collection.html?collection=komputer-for-alle", reduced_motion="reduce") as page:
            page.hover(".disc-card >> nth=0")
            self.assertEqual(page.eval_on_selector(".disc-card", "card => getComputedStyle(card).transitionDuration"), "0s")
            self.assertEqual(page.eval_on_selector(".disc-card", "card => getComputedStyle(card).transform"), "none")
            self.assertEqual(page.eval_on_selector(".cursor", "cursor => getComputedStyle(cursor).animationName"), "none")

    def test_without_javascript_the_pages_explain_themselves(self):
        for path in ("/", "/collection.html?collection=komputer-for-alle"):
            with self.subTest(path), self.page(path, java_script_enabled=False) as page:
                self.assertIn("trenger JavaScript", page.text_content("main"))
                self.assertTrue(page.is_visible("text=Alle kildeposter"))
        with self.page("/", java_script_enabled=False) as page:
            self.assertEqual(page.text_content("h1:visible"), "Bootdisk")


if __name__ == "__main__":
    unittest.main()
