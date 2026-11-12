"""Browser checks for the retro catalogue presentation (docs/retro-catalog.md).

The pages are driven in Chromium against a package built by tests/synthetic_catalog.py:
PRØVEDATA in the size of Birk's local preview (1705 source entries on 29 CDs) with the
hard cases the contract allows. The data is invented; these checks say nothing about
the real archive and do not replace Birk's acceptance on real data.

Skipped without Playwright or a browser. Run locally with:

    pip install playwright && playwright install chromium
    python -m unittest tests.test_retro_catalog_browser -v
"""
import contextlib
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import synthetic_catalog  # noqa: E402
from test_publication import serve  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment dependent
    sync_playwright = None

PUBLIC_PAGES = ("index.html", "archive.html", "collection.html", "updates.html", "404.html")
LOCAL_TOOLS = ("curate.html", "overview.html", "automation.html")
STATUS_LABELS = {"identified": "Identifisert", "interpreted": "Foreløpig identifisering",
                 "source_documented": "Oppgitt på CD-en", "pending": "Venter på identifisering"}


def effective_status(entry):
    if entry["curation_status"] == "pending" and entry.get("source_catalog_status") == "documented":
        return "source_documented"
    if entry.get("identification_status") == "interpreted":
        return "interpreted"
    return entry["curation_status"]


class CatalogMarkupTests(unittest.TestCase):
    """Static rules that need no browser."""

    def test_public_pages_load_the_catalog_stylesheet_last_and_versioned(self):
        for name in PUBLIC_PAGES:
            with self.subTest(name):
                html = (ROOT / name).read_text(encoding="utf-8")
                sheets = re.findall(r'<link rel="stylesheet" href="([^"]+)"', html)
                self.assertEqual(sheets[-1], "catalog.css?v=cdmenu1", "catalog.css overrides, so it comes last")
                self.assertNotIn("window-buttons", html, "no fake window buttons")
                self.assertNotIn("<marquee", html.lower())
                external = re.findall(r'<(?:script[^>]*\ssrc|link rel="(?:stylesheet|preload|icon)"[^>]*\shref)="((?:https?:)?//[^"]*)"', html)
                self.assertEqual(external, [], "no external scripts, styles or fonts")

    def test_local_tools_do_not_load_the_public_catalog_style(self):
        for name in LOCAL_TOOLS:
            with self.subTest(name):
                self.assertNotIn("catalog.css", (ROOT / name).read_text(encoding="utf-8"))

    def test_changed_scripts_carry_a_new_cache_version(self):
        self.assertIn('src="archive.js?v=cdmenu1"', (ROOT / "archive.html").read_text(encoding="utf-8"))
        self.assertIn('src="collection.js?v=retro-catalog1"', (ROOT / "collection.html").read_text(encoding="utf-8"))

    def test_catalog_css_is_released_and_self_contained(self):
        release = (ROOT / "scripts/build-release.py").read_text(encoding="utf-8")
        self.assertIn('"catalog.css"', release)
        css = (ROOT / "catalog.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"@import|url\(", "no fonts or images fetched by the stylesheet")
        self.assertNotRegex(css, r"@keyframes|animation:(?!\s*none)", "nothing blinks or moves")


@unittest.skipUnless(sync_playwright, "Playwright is required for the browser checks")
class RetroCatalogBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stack = contextlib.ExitStack()
        work = Path(cls._stack.enter_context(tempfile.TemporaryDirectory()))
        cls.report = synthetic_catalog.build(work / "release")
        cls.index = json.loads((work / "release/data/index.json").read_text(encoding="utf-8"))
        cls.base = cls._stack.enter_context(serve(work / "release")).rstrip("/")
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
    def page(self, path="/", width=1280, height=900, **options):
        context = self.browser.new_context(viewport={"width": width, "height": height}, **options)
        page = context.new_page()
        problems, requests, broken = [], [], []
        page.on("pageerror", lambda error: problems.append(str(error)))
        page.on("console", lambda message: message.type == "error" and problems.append(message.text))
        page.on("request", lambda request: requests.append(request.url))
        page.on("response", lambda response: response.status >= 400 and not response.url.endswith("/data/public-updates.json")
                and broken.append(f"{response.status} {response.url}"))
        page.requests = requests
        page.goto(self.base + path, wait_until="networkidle")
        try:
            yield page
            self.assertEqual(problems, [], "console or script errors")
            self.assertEqual(broken, [], "broken local requests")
            self.assertEqual([url for url in requests if not url.startswith(self.base)], [], "no external requests")
        finally:
            context.close()

    def test_scale_every_cd_and_count_comes_from_the_index(self):
        counts = {}
        for entry in self.index["entries"]:
            counts[entry["medium"]] = counts.get(entry["medium"], 0) + 1
        self.assertEqual((len(counts), sum(counts.values())), (29, 1705))
        with self.page("/") as page:
            self.assertEqual(page.locator(".collection-stats dd").all_text_contents(), ["29", "1 705"])
        with self.page("/collection.html?collection=komputer-for-alle") as page:
            cards = page.eval_on_selector_all(".disc-card", "cards => cards.map(c => [c.querySelector('.disc-label').textContent, c.querySelector('.disc-count').textContent])")
            self.assertEqual(len(cards), 29)
            self.assertEqual({label: int(re.sub(r"\D", "", count)) for label, count in cards}, counts)
            # Year groups: newest first, each with totals that add up to the CDs below it.
            for group in page.locator(".disc-year-group").all():
                year = group.locator("h3").text_content()
                labels = group.locator(".disc-label").all_text_contents()
                self.assertTrue(all(label.endswith(f"/{year}") for label in labels))
                expected = f"{len(labels)} CD{'-er' if len(labels) != 1 else ''} · {sum(counts[l] for l in labels):,} kildeposter".replace(",", " ")
                self.assertEqual(group.locator(".disc-year-count").text_content(), expected)
            years = page.locator(".disc-year-group h3").all_text_contents()
            self.assertEqual(years, sorted(years, reverse=True))
            self.assertEqual(page.text_content("#media-summary"), "29 CD-er med til sammen 1 705 kildeposter. Nyeste utgave først.")

    def test_front_collection_cd_entry_and_back_keep_the_filter(self):
        medium = self.index["media"][16]
        with self.page("/") as page:
            page.click("text=Utforsk Komputer for alle")
            page.click(f".disc-card:has-text('{medium['medium']}')")
            page.wait_for_selector(".archive-card")
            self.assertEqual(page.url, f"{self.base}/archive.html?medium={medium['id']}")
            rows = [e for e in self.index["entries"] if e["medium_id"] == medium["id"]]
            self.assertEqual(page.locator(".archive-card").count(), len(rows))
            page.select_option("#archive-status", "source_documented")
            page.fill("#archive-search", "prøvepost")
            filtered = page.url
            first = page.locator(".archive-card").first
            name = first.text_content()
            first.click()
            page.wait_for_selector("#entry-breadcrumbs li[aria-current=page]")
            self.assertEqual(page.text_content("#software-name"), name)
            self.assertEqual(page.text_content("#fact-status"), "Oppgitt på CD-en")
            page.go_back()
            page.wait_for_selector(".archive-card")
            self.assertEqual(page.url, filtered)
            self.assertEqual(page.input_value("#archive-status"), "source_documented")

    def test_archive_rows_show_human_titles_cd_year_content_and_the_detail_status(self):
        with self.page("/archive.html") as page:
            page.wait_for_selector(".archive-table")
            self.assertEqual(page.locator(".archive-table th").all_text_contents(), ["Tittel", "CD", "År", "Innhold", "Status"])
            rows = page.eval_on_selector_all(".archive-table tbody tr", """rows => rows.map(r => ({
                title: r.querySelector('.archive-card').textContent, medium: r.cells[1].textContent,
                year: r.cells[2].textContent, kind: r.cells[3].textContent, status: r.cells[4].textContent,
                mark: r.querySelector('.archive-status-mark').textContent}))""")
            self.assertEqual(len(rows), 1705)
            for entry, row in zip(self.index["entries"], rows):
                self.assertEqual(row["title"], entry["software_name"] or entry["editorial_title"])
                self.assertNotRegex(row["title"], r"^K\d+$", "a source id is never the title")
                self.assertEqual(row["medium"], entry["medium"])
                self.assertEqual(row["year"], entry["medium"].rsplit("/", 1)[1])
                self.assertTrue(row["status"].endswith(STATUS_LABELS[effective_status(entry)]))
                self.assertTrue(row["mark"].strip(), "status has a shape mark as well as colour")
                if not entry.get("content_kind") and not entry.get("distribution_kind"):
                    self.assertEqual(row["kind"], "Ikke oppgitt")
        # The detail page says the same status for one entry of each kind.
        samples = {}
        for entry in self.index["entries"]:
            samples.setdefault(effective_status(entry), entry)
        self.assertEqual(set(samples), set(STATUS_LABELS))
        for status, entry in samples.items():
            with self.subTest(status), self.page(f"/index.html?entry={entry['entry']}") as page:
                page.wait_for_selector("#entry-breadcrumbs li[aria-current=page]")
                self.assertEqual(page.text_content("#fact-status"), STATUS_LABELS[status])

    def test_header_search_and_menu_lead_into_the_archive(self):
        with self.page("/collection.html?collection=komputer-for-alle") as page:
            self.assertEqual(page.locator(".site-nav a").all_text_contents(), ["Forside", "Samlinger", "Alle kildeposter", "Siste endringer"])
            page.fill("#site-search-q", "fjordspill")
            page.press("#site-search-q", "Enter")
            page.wait_for_selector(".archive-card")
            self.assertEqual(page.url, f"{self.base}/archive.html?q=fjordspill")
            self.assertEqual(page.input_value("#archive-search"), "fjordspill")
            expected = sum("fjordspill" in (e["editorial_title"] + " " + (e["software_name"] or "")).lower() for e in self.index["entries"])
            self.assertEqual(page.locator(".archive-card").count(), expected)
            self.assertEqual(page.get_attribute(".site-nav a[aria-current=page]", "href"), "archive.html")
        with self.page("/archive.html?q=finnesikkexyz") as page:
            page.wait_for_selector("#archive-empty:not([hidden])")
            self.assertEqual(page.locator(".archive-card").count(), 0)
            self.assertEqual(page.text_content("#archive-count"), "0 av 1705 poster")

    def test_long_titles_and_html_like_titles_stay_inside_their_cells_as_text(self):
        for width in (1280, 768, 375, 320):
            with self.subTest(width=width), self.page("/archive.html?medium=" + self.index["media"][0]["id"], width=width) as page:
                page.wait_for_selector(".archive-card")
                spill = page.evaluate("""[...document.querySelectorAll('.archive-table td')].filter(td =>
                    td.scrollWidth > td.clientWidth + 1).length""")
                self.assertEqual(spill, 0)
                self.assertIn("Programvarebevaringsdokumentasjonsverktøy", page.text_content("#archive-grid"))
                self.assertIn('<img src=x onerror="window.__catalogXss=1">', page.text_content("#archive-grid"))
                self.assertEqual(page.locator("main img[src=x]").count(), 0)
                self.assertIsNone(page.evaluate("window.__catalogXss"))

    def test_no_horizontal_scroll_at_common_widths_and_200_percent_zoom(self):
        paths = ("/", "/collection.html?collection=komputer-for-alle", "/archive.html?q=skrive", "/index.html?entry=K2",
                 "/updates.html", "/404.html")
        # 200 % zoom on a 1280 px window lays the page out at 640 CSS px.
        for width in (320, 375, 640, 768, 1280):
            for path in paths:
                with self.subTest(width=width, path=path), self.page(path, width=width, height=800) as page:
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                    self.assertTrue(page.is_visible(".site-nav"))
                    if path != "/404.html":
                        overlap = page.evaluate("""() => { const a = document.querySelector('.site-header').getBoundingClientRect();
                            const b = document.querySelector('main').getBoundingClientRect(); return a.bottom > b.top + 1; }""")
                        self.assertFalse(overlap)

    def test_mobile_archive_stacks_each_row_with_labelled_fields(self):
        with self.page("/archive.html?q=skrive", width=375, height=800) as page:
            page.wait_for_selector(".archive-card")
            row = page.locator(".archive-table tbody tr").first
            self.assertEqual(row.evaluate("r => getComputedStyle(r).display"), "block")
            self.assertFalse(page.is_visible(".archive-table thead"))
            self.assertIn("Status: ", row.locator(".archive-cell-status").evaluate("c => getComputedStyle(c, '::before').content"))

    def test_keyboard_focus_is_visible_through_header_menu_and_rows(self):
        with self.page("/archive.html?q=skrive") as page:
            page.wait_for_selector(".archive-card")
            page.keyboard.press("Tab")
            self.assertEqual(page.evaluate("document.activeElement.className"), "skip-link")
            seen = []
            for _ in range(12):
                page.keyboard.press("Tab")
                seen.append(page.evaluate("""() => { const e = document.activeElement, s = getComputedStyle(e);
                    return {text: e.textContent.trim() || e.id, outline: s.outlineStyle, shadow: s.boxShadow}; }"""))
            texts = [item["text"] for item in seen]
            self.assertLess(texts.index("Alle kildeposter"), texts.index("archive-search"))
            for item in seen:
                self.assertTrue(item["outline"] != "none" or item["shadow"] != "none", f"visible focus on {item['text']}")
            for _ in range(10):
                page.keyboard.press("Tab")
                if page.evaluate("document.activeElement.className") == "archive-card":
                    break
            self.assertEqual(page.evaluate("document.activeElement.className"), "archive-card")
            self.assertNotEqual(page.evaluate("getComputedStyle(document.activeElement).outlineStyle"), "none")

    def test_logo_underscore_never_blinks(self):
        with self.page("/") as page:
            self.assertEqual(page.eval_on_selector(".cursor", "c => getComputedStyle(c).animationName"), "none")

    def test_missing_images_leave_no_broken_pictures(self):
        no_icon = next(e for e in self.index["entries"] if e["icon"] is None)
        with self.page(f"/archive.html?medium={no_icon['medium_id']}") as page:
            page.wait_for_selector(".archive-card")
            # Icons load lazily; scroll through the CD so every row's icon is requested.
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_load_state("networkidle")
            self.assertEqual(page.evaluate("[...document.images].filter(i => i.complete && i.naturalWidth === 0).length"), 0)
            row = page.locator(f".archive-table tr:has(a[href='index.html?entry={no_icon['entry']}'])")
            self.assertEqual(row.locator("img").count(), 0)
            self.assertEqual(row.locator(".archive-card-icon").text_content(), "?")
        with self.page(f"/index.html?entry={no_icon['entry']}") as page:
            page.wait_for_selector("#entry-breadcrumbs li[aria-current=page]")
            self.assertFalse(page.is_visible("#software-icon"))
            self.assertEqual(page.evaluate("[...document.images].filter(i => i.offsetParent !== null && i.naturalWidth === 0).length"), 0)

    def test_unknown_version_reads_ikke_oppgitt(self):
        entry = next(e for e in self.index["entries"] if e["version"] == "unknown")
        with self.page(f"/index.html?entry={entry['entry']}") as page:
            page.wait_for_selector("#entry-breadcrumbs li[aria-current=page]")
            self.assertEqual(page.text_content("#fact-version"), "Ikke oppgitt")


if __name__ == "__main__":
    unittest.main()
