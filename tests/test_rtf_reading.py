"""The RTF reading view on the detail page (renderSourceDocuments in app.js).

Data checks run everywhere. The browser checks serve the TESTDATA site from
tests/rtf_reading_fixtures.py (three real development examples plus synthetic cases)
and are skipped without Playwright or Chromium, as on CI. Run locally with:

    CURATOR_CHROMIUM=/path/to/chrome python -m unittest tests.test_rtf_reading -v
"""
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))
import rtf_reading_fixtures as fixtures  # noqa: E402
from frontend_contract import validate_frontend_data  # noqa: E402
from test_publication import serve  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment dependent
    sync_playwright = None

# The three examples exactly as delivered with the work order (2026-09-25).
DELIVERED = {
    "k37.json": "0181ea6696c235a4dc6dcee7fa057d0b353290fbe3b790b5be7e3576624f8284",
    "kcd-1-2001--k1.json": "33e3ba3fba65404c2e6a0e9df73deb4dc9ca9547b7c58257bf7f71bbfa876252",
    "kcd-8-2001--k5.json": "b382f340a3c928760b8b46fb5f44893df18e5db5056e01c602176ae5d0ccba43",
}
SUMMARY = "Les originaltekst fra CD-en (RTF)"


def real(name):
    return json.loads((fixtures.REAL / name).read_text(encoding="utf-8"))


def contract_tree(root, documents):
    """A minimal generated-data tree for Birk's validator: one publication and medium."""
    root.mkdir(parents=True)
    first = documents[0]
    index = {"publication": first["publication"], "medium": first["medium"],
             "entries": [{"entry": d["entry"], "curation_status": d["curation_status"]} for d in documents]}
    (root / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    for document in documents:
        (root / f"{document['entry'].lower()}.json").write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return root


class RtfFixtureDataTests(unittest.TestCase):
    def test_real_examples_are_unchanged_and_their_originals_match(self):
        for name, digest in DELIVERED.items():
            with self.subTest(name):
                self.assertEqual(hashlib.sha256((fixtures.REAL / name).read_bytes()).hexdigest(), digest)
                for doc in real(name)["source_documents"]:
                    content = (fixtures.REAL / doc["original"]["public_path"]).read_bytes()
                    self.assertEqual(hashlib.sha256(content).hexdigest(), doc["original"]["sha256"])
                    self.assertEqual(len(content), doc["original"]["size"])

    def test_real_examples_cover_the_three_reading_cases(self):
        k37, k1, k5 = (real(name) for name in DELIVERED)
        normalize = lambda value: re.sub(r"\s+", " ", value or "").strip()
        self.assertNotEqual(normalize(k37["source_documents"][0]["text"]), normalize(k37["source_context"]["description"]["value"]))
        self.assertEqual(normalize(k1["source_documents"][0]["text"]), normalize(k1["source_context"]["description"]["value"]))
        self.assertIsNone(k5["source_documents"][0]["text"])

    def test_valid_fixtures_pass_the_data_contract_and_unsafe_ones_do_not(self):
        entries, _ = fixtures.synthetic_cases()
        by_id = {d["entry"]: d for d in entries}
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            validate_frontend_data(contract_tree(work / "valid", [by_id[i] for i in ("K901", "K902", "K903", "K904", "K905")]))
            for name in DELIVERED:
                validate_frontend_data(contract_tree(work / name, [real(name)]))
            # The page's own guard is defence in depth: the build already refuses these.
            for entry in ("K906", "K907", "K908"):
                with self.subTest(entry), self.assertRaises(ValueError):
                    validate_frontend_data(contract_tree(work / entry, [by_id[entry]]))

    def test_test_data_never_reaches_the_release_allowlist(self):
        spec = importlib.util.spec_from_file_location("build_release", ROOT / "scripts/build-release.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in module.STATIC_FILES:
            self.assertFalse(name.startswith("tests"), name)
            self.assertNotIn("rtf_reading", name)

    def test_source_text_is_never_parsed_as_markup(self):
        source = (ROOT / "app.js").read_text(encoding="utf-8")
        body = source[source.index("function renderSourceDocuments"):source.index("function requestedEntry")]
        for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "DOMParser", "document.write"):
            self.assertNotIn(sink, body)


@unittest.skipUnless(sync_playwright, "Playwright is required for the browser checks")
class RtfReadingBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stack = contextlib.ExitStack()
        work = Path(cls._stack.enter_context(tempfile.TemporaryDirectory()))
        cls.site = work / "site"
        cls.index = fixtures.build_site(cls.site)
        cls.base = cls._stack.enter_context(serve(cls.site)).rstrip("/")
        cls.synthetic = {d["entry"]: d for d in fixtures.synthetic_cases()[0]}
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
    def page(self, entry, width=1280, height=900, routes=(), **context_options):
        context = self.browser.new_context(viewport={"width": width, "height": height}, accept_downloads=True, **context_options)
        page = context.new_page()
        failures, requests = [], []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.on("request", lambda request: requests.append(request.url))
        for pattern, handler in routes:
            page.route(pattern, handler)
        page.requests = requests
        page.goto(f"{self.base}/index.html?entry={entry}", wait_until="networkidle")
        page.wait_for_function("document.querySelector('main').getAttribute('aria-busy') === 'false'")
        try:
            yield page
            self.assertEqual(failures, [], "the page raised a script error")
        finally:
            context.close()

    def documents(self, page):
        return page.locator("#source-documents")

    def assert_download(self, page, doc):
        """Row 9: the link really delivers the original bytes, not just an <a> in the DOM."""
        link = self.documents(page).get_by_role("link", name="Last ned originalfil")
        self.assertEqual(link.count(), 1)
        self.assertEqual(link.get_attribute("download"), doc["path"].split("/")[-1])
        with page.expect_download() as info:
            link.click()
        download = info.value
        self.assertEqual(download.suggested_filename, doc["path"].split("/")[-1])
        content = Path(download.path()).read_bytes()
        self.assertEqual(hashlib.sha256(content).hexdigest(), doc["original"]["sha256"])
        self.assertEqual(len(content), doc["original"]["size"])
        response = page.request.get(f"{self.base}/{doc['original']['public_path']}")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["content-type"], "application/rtf")

    # Row 1 ---------------------------------------------------------------------------
    def test_short_menu_description_and_longer_real_rtf_can_be_opened_and_closed(self):
        doc = real("k37.json")["source_documents"][0]
        with self.page("K37") as page:
            self.assertEqual(page.text_content("#software-description"), "Med WinAmp kan du spille musikk-cd-er og mp3-filer.")
            self.assertTrue(page.is_visible("#source-documents"))
            summary = page.locator("#source-documents summary")
            self.assertEqual(summary.count(), 1)
            self.assertEqual(summary.text_content(), SUMMARY)
            text = page.locator(".rtf-source-text")
            self.assertFalse(text.is_visible())
            summary.click()
            self.assertTrue(text.is_visible())
            self.assertEqual(text.text_content(), doc["text"])
            self.assertIn("Klikk på \"Les guide\"", text.inner_text())
            summary.click()
            self.assertFalse(text.is_visible())
            self.assertEqual(page.locator("#source-documents").text_content().count("unsupported"), 0)
            meta = page.text_content(".source-document-meta")
            self.assertEqual(meta, "WinAmp/No.rtf · RTF · 613 byte")
            self.assert_download(page, doc)

    # Row 2 ---------------------------------------------------------------------------
    def test_text_that_only_differs_in_whitespace_is_not_shown_twice(self):
        cases = (("K902", self.synthetic["K902"]["source_documents"][0], "samme omtale"),
                 ("kcd-1-2001--K1", real("kcd-1-2001--k1.json")["source_documents"][0], "I dette spillet skal du hjelpe Asterix"))
        for entry, doc, phrase in cases:
            with self.subTest(entry), self.page(entry) as page:
                self.assertEqual(page.locator("#source-documents details").count(), 0)
                self.assertEqual(page.locator(".rtf-source-text").count(), 0)
                self.assertEqual(page.inner_text("main").count(phrase), 1)
                self.assertEqual(page.text_content(".source-document-note"), "Samme tekst finnes i originalfilen fra CD-en.")
                self.assert_download(page, doc)
        with self.page("kcd-1-2001--K1") as page:
            self.assertEqual(page.text_content(".source-document-meta"), "Asterix/No.rtf · RTF · 6,9 kB")

    # Row 3 ---------------------------------------------------------------------------
    def test_text_null_explains_briefly_and_still_offers_the_original(self):
        cases = (("K903", self.synthetic["K903"]["source_documents"][0]),
                 ("kcd-8-2001--K5", real("kcd-8-2001--k5.json")["source_documents"][0]))
        for entry, doc in cases:
            with self.subTest(entry), self.page(entry) as page:
                self.assertTrue(page.is_visible("#source-documents"))
                self.assertEqual(page.locator("#source-documents details").count(), 0)
                self.assertEqual(page.text_content(".source-document-note"),
                                 "Originalteksten fra CD-en kan ikke vises her, men originalfilen kan lastes ned.")
                self.assertNotIn("charset", page.inner_text("main"))
                self.assertNotIn("unsupported", page.inner_text("main"))
                self.assert_download(page, doc)
        with self.page("kcd-8-2001--K5") as page:
            self.assertIn("Nå kan du skifte ut pauseskjermen din selv.", page.text_content("#software-description"))
            self.assertEqual(page.text_content(".source-document-meta"), "Freesaver/No.rtf · RTF · 4,3 kB")

    # Row 4 ---------------------------------------------------------------------------
    def test_entries_without_documents_get_no_section(self):
        for entry in ("K904", "K905", "K907", "K908"):
            with self.subTest(entry), self.page(entry) as page:
                self.assertFalse(page.is_visible("#source-documents"))
                self.assertTrue(page.eval_on_selector("#source-documents", "node => node.hidden"))
                self.assertEqual(page.eval_on_selector("#source-documents", "node => node.childElementCount"), 0)
                self.assertTrue(page.is_visible("#software-description"))
                self.assertNotIn("TESTDATA fra en annen kildepost", page.inner_text("body"))

    # Row 5 ---------------------------------------------------------------------------
    def test_long_multiparagraph_html_like_text_is_rendered_literally_and_wraps(self):
        doc = self.synthetic["K901"]["source_documents"][0]
        for width in (1280, 375, 320):
            with self.subTest(width), self.page("K901", width=width) as page:
                page.click("#source-documents summary")
                text = page.locator(".rtf-source-text")
                self.assertEqual(text.text_content(), doc["text"])
                self.assertEqual(text.evaluate("node => node.children.length"), 0)
                self.assertEqual(page.locator("#source-documents img, #source-documents b").count(), 0)
                self.assertIsNone(page.evaluate("window.__rtfXss"))
                self.assertIn("\n\nAvsnitt 5:", text.inner_text())
                self.assertIn("Æ, Ø og Å, æ, ø og å, «sitat» og ”Play”-knappen.", text.inner_text())
                for selector in (".rtf-source-text", ".source-document-meta", "#source-documents summary"):
                    box = page.eval_on_selector(selector, "node => [node.scrollWidth, node.clientWidth]")
                    self.assertLessEqual(box[0], box[1], selector)
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                self.assertEqual(page.text_content(".source-document-meta"), f"{fixtures.LONG_NAME} · RTF · 67 byte")

    # Row 6 ---------------------------------------------------------------------------
    def test_keyboard_opens_and_closes_with_visible_focus_in_reading_order(self):
        with self.page("K37") as page:
            order = []
            for _ in range(12):
                page.keyboard.press("Tab")
                order.append(page.evaluate("""() => { const node = document.activeElement;
                    return node.tagName === 'SUMMARY' ? 'summary' : node.id || node.textContent.trim(); }"""))
                if order[-1] == "next-entry":
                    break
            self.assertLess(order.index("Winamp") if "Winamp" in order else order.index("K-CD 15/2001"), order.index("summary"))
            self.assertEqual(order[order.index("summary") + 1], "Last ned originalfil")
            self.assertLess(order.index("Last ned originalfil"), order.index("next-entry"))
            page.focus("#source-documents summary")
            outline = page.eval_on_selector("#source-documents summary", "node => getComputedStyle(node).outlineStyle")
            self.assertNotEqual(outline, "none")
            details = page.locator("#source-documents details")
            page.keyboard.press("Enter")
            self.assertTrue(details.evaluate("node => node.open"))
            self.assertTrue(page.is_visible(".rtf-source-text"))
            page.keyboard.press("Space")
            self.assertFalse(details.evaluate("node => node.open"))
            self.assertFalse(page.is_visible(".rtf-source-text"))
            self.assertEqual(page.evaluate("location.search"), "?entry=K37")

    # Row 7 ---------------------------------------------------------------------------
    def test_narrow_screens_do_not_scroll_sideways_or_overlap_navigation(self):
        for width in (320, 375):
            for entry in ("K37", "K901", "K906", "kcd-8-2001--K5"):
                with self.subTest(width=width, entry=entry), self.page(entry, width=width, height=740) as page:
                    if page.locator("#source-documents summary").count():
                        page.click("#source-documents summary")
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                    boxes = page.evaluate("""() => {
                        const box = node => node && !node.hidden ? node.getBoundingClientRect().toJSON() : null;
                        return {docs: box(document.querySelector('#source-documents')),
                                others: ['.breadcrumbs', '#software-description', '.window', '.entry-navigation']
                                  .map(sel => box(document.querySelector(sel))).filter(Boolean)}; }""")
                    docs = boxes["docs"]
                    self.assertLessEqual(docs["right"], width)
                    for other in boxes["others"]:
                        overlaps = docs["top"] < other["bottom"] and other["top"] < docs["bottom"]
                        self.assertFalse(overlaps, other)

    # Row 8 ---------------------------------------------------------------------------
    def test_unsafe_download_addresses_never_become_links(self):
        with self.page("K906") as page:
            self.assertEqual(page.locator("#source-documents a").count(), 0)
            self.assertEqual(page.locator("#source-documents .source-document").count(), 6)
            metas = page.locator(".source-document-meta").all_text_contents()
            self.assertTrue(all(m.endswith("originalfilen er ikke tilgjengelig") for m in metas), metas)
            for summary in page.locator("#source-documents summary").all():
                summary.click()
            shown = page.locator(".rtf-source-text").all_text_contents()
            self.assertEqual(len(shown), 6)
            self.assertIn("TESTDATA utrygg adresse: traversering.", shown)
            self.assertFalse(any("example.invalid" in url or "passwd" in url for url in page.requests))
            self.assertIsNone(page.evaluate("window.__rtfLink"))
            self.assertNotIn("example.invalid", page.content())

    # Row 10 --------------------------------------------------------------------------
    def test_detail_navigation_breadcrumbs_and_arrow_keys_still_work(self):
        with self.page("K37") as page:
            self.assertEqual(page.locator("#entry-breadcrumbs li").all_text_contents(), ["Bootdisk", "Komputer for alle", "K-CD 15/2001", "Winamp"])
            self.assertFalse(page.is_visible("#previous-entry"))
            page.click("#source-documents summary")
            page.click("#next-entry")
            page.wait_for_function("document.querySelector('main').getAttribute('aria-busy') === 'false'")
            self.assertTrue(page.url.endswith("entry=kcd-1-2001--K1"))
            self.assertEqual(page.text_content("h1:visible"), "Asterix")
            page.keyboard.press("ArrowRight")
            page.wait_for_url("**entry=kcd-8-2001--K5")
            page.wait_for_function("document.querySelector('main').getAttribute('aria-busy') === 'false'")
            self.assertEqual(page.text_content("h1:visible"), "Freesaver MP3")
            page.go_back()
            page.wait_for_function("document.querySelector('main').getAttribute('aria-busy') === 'false'")
            self.assertEqual(page.text_content("h1:visible"), "Asterix")

    def test_existing_error_view_hides_source_documents(self):
        def without_entry(route):
            index = json.loads((self.site / "data/index.json").read_text(encoding="utf-8"))
            index["entries"] = [e for e in index["entries"] if e["entry"] != "K37"]
            route.fulfill(status=200, content_type="application/json", body=json.dumps(index))
        context = self.browser.new_context()
        try:
            page = context.new_page()
            page.route("**/data/index.json", without_entry)
            page.goto(f"{self.base}/index.html?entry=K37", wait_until="networkidle")
            self.assertTrue(page.is_visible("#entry-error"))
            self.assertEqual(page.text_content("#entry-error"), "Arkivposten kunne ikke lastes.")
            self.assertFalse(page.is_visible("#source-documents"))
            self.assertFalse(page.is_visible(".entry-navigation"))
            page.goto(f"{self.base}/index.html?entry=K404", wait_until="networkidle")
            self.assertEqual(page.text_content("#entry-error"), "Det finnes ingen arkivpost med denne adressen.")
            self.assertFalse(page.is_visible("#source-documents"))
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()
