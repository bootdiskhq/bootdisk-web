"""Browser checks for the curator overview prototype.

These drive a real Chromium through Playwright and cover what only a browser can show: that
thousands of entries produce a bounded number of rendered rows, that the round trip to the
decision screen and back restores search, filters, page and keyboard focus, and that the
narrow view keeps every column without a horizontal scroll.

They are skipped when Playwright or a browser is unavailable, which is the case on CI.
Run them locally with:

    pip install playwright && playwright install chromium
    python -m unittest tests.test_overview_browser -v

Set CURATOR_CHROMIUM to a Chromium binary if Playwright's own download is not used.
"""
import contextlib
import functools
import http.server
import os
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE_SIZE = 50

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment dependent
    sync_playwright = None


@contextlib.contextmanager
def serve(directory: Path):
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


@unittest.skipUnless(sync_playwright, "Playwright is required for the browser checks")
class OverviewBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stack = contextlib.ExitStack()
        cls.base_url = cls._stack.enter_context(serve(ROOT))
        playwright = cls._stack.enter_context(sync_playwright())
        try:
            cls.browser = playwright.chromium.launch(executable_path=os.environ.get("CURATOR_CHROMIUM") or None)
        except Exception as error:  # pragma: no cover - environment dependent
            cls._stack.close()
            raise unittest.SkipTest(f"No Chromium available: {error}")
        cls._stack.callback(cls.browser.close)

    @contextlib.contextmanager
    def overview(self, width=1280, height=900, query=""):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        failures = []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.goto(f"{self.base_url}/overview.html{query}", wait_until="networkidle")
        page.wait_for_selector("#overview-rows tr")
        try:
            yield page
            self.assertEqual(failures, [], "the page raised a script error")
        finally:
            page.close()

    def wait_for_count(self, page, previous: str) -> str:
        page.wait_for_function(
            "previous => document.querySelector('#overview-count').textContent !== previous",
            arg=previous)
        return page.text_content("#overview-count")

    def matched(self, page) -> int:
        return page.evaluate(
            "Number(document.querySelector('#overview-count').textContent.replace(/\\u00a0/g, ' ').split(' treff')[0].replace(/\\s/g, ''))")

    def test_thousands_of_entries_render_one_bounded_page_of_rows(self):
        with self.overview() as page:
            self.assertGreaterEqual(self.matched(page), 5000, "the scale set really is loaded")
            self.assertEqual(page.locator("#overview-rows tr").count(), PAGE_SIZE,
                             "only one page of rows exists in the DOM")
            self.assertEqual(page.locator("#overview-rows tr td").count(), PAGE_SIZE * 7,
                             "every rendered row keeps all seven columns")
            page.click("#page-next")
            page.wait_for_function("document.querySelector('#page-state').textContent.startsWith('Side 2')")
            self.assertEqual(page.locator("#overview-rows tr").count(), PAGE_SIZE,
                             "turning the page replaces the rows instead of adding to them")

    def test_search_and_field_filter_combine_and_reset(self):
        with self.overview() as page:
            opening = page.text_content("#overview-count")
            everything = self.matched(page)
            page.fill("#overview-search", "kvasarskriv")
            searched_text = self.wait_for_count(page, opening)
            searched = self.matched(page)
            self.assertLess(searched, everything)
            for title in page.locator("#overview-rows tr td:first-child a").all_text_contents():
                self.assertIn("kvasarskriv", title.lower())

            page.select_option("#overview-field", "needs_review")
            self.wait_for_count(page, searched_text)
            self.assertLessEqual(self.matched(page), searched, "the field filter narrows the search")
            self.assertGreater(page.locator("#overview-rows .row-review").count(), 0,
                               "every remaining row says what needs another look")

            page.click("#overview-reset")
            page.wait_for_function(
                "opening => document.querySelector('#overview-count').textContent === opening",
                arg=opening)
            self.assertEqual(page.evaluate("document.querySelector('#overview-search').value"), "")

    def test_no_hits_explains_itself_instead_of_showing_an_empty_table(self):
        with self.overview() as page:
            page.fill("#overview-search", "ingensomhelstheter")
            page.wait_for_selector("#overview-empty:not([hidden])")
            self.assertEqual(page.locator("#overview-rows tr").count(), 0)
            self.assertIn("Tilbakestill", page.text_content("#overview-empty"))

    def test_opening_a_row_and_coming_back_restores_the_view_and_the_focus(self):
        with self.overview() as page:
            opening = page.text_content("#overview-count")
            page.select_option("#overview-status", "pending")
            filtered = self.wait_for_count(page, opening)
            page.fill("#overview-search", "kart")
            self.wait_for_count(page, filtered)
            page.click("#page-next")
            page.wait_for_function("document.querySelector('#page-state').textContent.startsWith('Side 2')")

            row = page.locator("#overview-rows tr").nth(2)
            entry = row.locator(".row-entry").text_content()
            title = row.locator("a").text_content()
            row.locator("a").click()

            page.wait_for_selector("#entry-heading:not(:empty)")
            self.assertEqual(page.text_content("#entry-id"), entry, "the detail screen opened the chosen row")
            self.assertEqual(page.text_content("#entry-heading"), title)
            self.assertFalse(page.locator("#curate-return").is_hidden(), "the way back is offered")

            page.click("#curate-return a")
            page.wait_for_selector("#overview-rows tr")
            self.assertEqual(page.evaluate("document.querySelector('#overview-search').value"), "kart")
            self.assertEqual(page.evaluate("document.querySelector('#overview-status').value"), "pending")
            self.assertTrue(page.text_content("#page-state").startswith("Side 2"), "the same page came back")
            self.assertEqual(page.evaluate("document.activeElement.textContent"), title,
                             "the keyboard is back on the row that was opened")
            self.assertEqual(page.locator("#overview-rows tr[aria-current='true']").count(), 1)

    def test_a_decision_updates_the_row_and_explains_a_row_that_left_the_filter(self):
        with self.overview(query="?status=pending") as page:
            row = page.locator("#overview-rows tr").first
            entry = row.locator(".row-entry").text_content()
            row.locator("a").click()
            page.wait_for_selector("#entry-heading:not(:empty)")
            self.assertEqual(page.text_content("#entry-id"), entry)

            page.click("#action-commit")
            page.wait_for_function("document.querySelector('#save-state').textContent !== 'Lagrer kladd …'")
            page.click("#curate-return a")
            page.wait_for_selector("#overview-rows tr")

            current = page.locator("#overview-rows tr[aria-current='true']")
            self.assertEqual(current.count(), 1, "the decided row is still where it was")
            self.assertIn("Gjennomgått", current.text_content(), "and shows what the adapter answered")
            self.assertFalse(page.locator("#overview-outside").is_hidden(),
                             "a row that no longer fits the filter says so")

    def test_the_narrow_view_keeps_every_column_without_sideways_scrolling(self):
        with self.overview(width=390, height=780) as page:
            self.assertLessEqual(
                page.evaluate("document.documentElement.scrollWidth"),
                page.evaluate("window.innerWidth") + 1,
                "the narrow view has no horizontal overflow")
            labels = page.evaluate(
                "Array.from(document.querySelectorAll('#overview-rows tr:first-child td'))"
                ".map(cell => getComputedStyle(cell, '::before').content)")
            self.assertTrue(all(label and label != "none" for label in labels),
                            "every cell carries its own visible column label on a narrow screen")
            self.assertEqual(page.locator("#overview-rows tr:first-child td").count(), 7)

    def test_the_table_is_reachable_and_readable_from_the_keyboard(self):
        with self.overview() as page:
            page.click("#overview-search")
            page.keyboard.press("Tab")
            self.assertEqual(page.evaluate("document.activeElement.id"), "overview-status")
            for _ in range(4):
                page.keyboard.press("Tab")
            self.assertEqual(page.evaluate("document.activeElement.tagName"), "A",
                             "the first row link follows the filters in the tab order")
            outline = page.evaluate("getComputedStyle(document.activeElement, ':focus-visible').outlineStyle")
            self.assertNotEqual(outline, "none", "the focused row is visibly focused")
            self.assertEqual(page.locator("#overview-rows tr td[data-label]").count(), PAGE_SIZE * 7,
                             "status is carried by text, not only by colour")

    def test_startup_and_search_stay_within_a_generous_budget(self):
        """Measured, not asserted tightly: CI hardware is unknown, so the bound is loose."""
        with self.overview() as page:
            startup = page.evaluate("performance.now()")
            timing = page.evaluate("""() => {
              const input = document.querySelector('#overview-search');
              const started = performance.now();
              input.value = 'fjordvox';
              input.dispatchEvent(new Event('input'));
              return new Promise(resolve => setTimeout(() => resolve(performance.now() - started), 400));
            }""")
            print(f"\noverview startup {startup:.0f} ms, search round trip {timing:.0f} ms (includes a 150 ms debounce)")
            self.assertLess(startup, 10000, "startup is not pathological")
            self.assertLess(timing, 3000, "a keystroke settles well inside a second on ordinary hardware")


if __name__ == "__main__":
    unittest.main()
