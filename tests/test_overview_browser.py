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

    @contextlib.contextmanager
    def detail_from_overview(self, query="?status=pending"):
        """The detail screen as the curator reaches it: by clicking a row in the overview."""
        with self.overview(query=query) as page:
            row = page.locator("#overview-rows tr").first
            entry = row.locator(".row-entry").text_content()
            row.locator("a").click()
            page.wait_for_selector("#entry-heading:not(:empty)")
            self.assertEqual(page.text_content("#entry-id"), entry)
            self.assertFalse(page.locator("#curate-return").is_hidden(), "the way back is offered")
            yield page, entry

    def test_returning_right_after_typing_saves_the_text_as_a_draft(self):
        """Correction order finding 2: a click before the autosave delay must not lose the text."""
        with self.detail_from_overview() as (page, entry):
            # Type and click back inside one synchronous task, so the 900 ms autosave cannot
            # have run: only the return gate can have saved this.
            still_here = page.evaluate("""() => {
              const input = document.querySelector('#claim-version');
              input.value = '7.77-retur';
              input.dispatchEvent(new Event('input', { bubbles: true }));
              document.querySelector('#curate-return a').click();
              return window.location.pathname.endsWith('curate.html');
            }""")
            self.assertTrue(still_here, "the page is not left in the same task as the click")

            page.wait_for_selector("#overview-rows tr")
            current = page.locator("#overview-rows tr[aria-current='true']")
            self.assertEqual(current.count(), 1, "the row that was open is back in place")
            self.assertIn(entry, current.text_content())
            self.assertIn("Kladd: 7.77-retur", current.text_content(),
                          "the text came back as a draft")
            self.assertNotIn("7.77-retur", current.locator("td").nth(2).locator("span").first.text_content(),
                             "and never as the approved value")

    def test_a_failed_save_stops_the_return_and_keeps_the_text(self):
        """Correction order finding 2: return is blocked on a save failure, with the text intact."""
        with self.detail_from_overview() as (page, _entry):
            page.evaluate("""() => {
              const fault = document.querySelector('#simulate-fault');
              fault.value = 'write_failed';
              fault.dispatchEvent(new Event('change', { bubbles: true }));
              const input = document.querySelector('#claim-version');
              input.value = '8.88-feil';
              input.dispatchEvent(new Event('input', { bubbles: true }));
              document.querySelector('#curate-return a').click();
            }""")
            page.wait_for_selector("#curate-return-error:not([hidden])")
            self.assertTrue(page.url.split("?")[0].endswith("curate.html"), "the page was not left")
            self.assertIn("lagret", page.text_content("#curate-return-error").lower())
            self.assertEqual(page.input_value("#claim-version"), "8.88-feil", "the text is still there")

    def test_a_revision_conflict_stops_the_return_and_keeps_the_text(self):
        """Correction order finding 2: a conflict has to be resolved before leaving."""
        with self.detail_from_overview() as (page, _entry):
            page.evaluate("""() => {
              const fault = document.querySelector('#simulate-fault');
              fault.value = 'revision_conflict';
              fault.dispatchEvent(new Event('change', { bubbles: true }));
              const input = document.querySelector('#claim-version');
              input.value = '9.99-konflikt';
              input.dispatchEvent(new Event('input', { bubbles: true }));
              document.querySelector('#curate-return a').click();
            }""")
            page.wait_for_selector("#curate-return-error:not([hidden])")
            self.assertTrue(page.url.split("?")[0].endswith("curate.html"), "the page was not left")
            self.assertIn("konflikt", page.text_content("#curate-return-error").lower())
            self.assertEqual(page.input_value("#claim-version"), "9.99-konflikt", "the text is still there")
            self.assertFalse(page.locator("#conflict-panel").is_hidden(),
                             "and the conflict is offered for resolution instead")

    def test_returning_during_a_running_decision_neither_navigates_nor_decides_twice(self):
        """Correction order finding 2: no unsafe navigation while a decision is in flight."""
        with self.detail_from_overview() as (page, entry):
            page.evaluate("""() => {
              document.querySelector('#action-commit').click();
              document.querySelector('#curate-return a').click();
            }""")
            page.wait_for_selector("#curate-return-error:not([hidden])")
            self.assertTrue(page.url.split("?")[0].endswith("curate.html"), "the page was not left")
            self.assertIn("beslutningen", page.text_content("#curate-return-error").lower())

            page.wait_for_function("document.querySelector('#save-state').textContent !== 'Lagrer kladd …'")
            self.assertTrue(page.locator("#decision-error").is_hidden(),
                            "the blocked click started no second decision that could fail")

            page.click("#curate-return a")
            page.wait_for_selector("#overview-rows tr")
            current = page.locator("#overview-rows tr[aria-current='true']")
            self.assertEqual(current.count(), 1, "the decided row is where it was left")
            self.assertIn(entry, current.text_content())
            self.assertIn("Gjennomgått", current.text_content(),
                          "the single decision took effect")

    def test_the_return_link_runs_the_same_gate_from_the_keyboard(self):
        """The link is reached by keyboard too, so Enter must not take a shortcut past the gate."""
        with self.detail_from_overview() as (page, _entry):
            page.evaluate("""() => {
              const fault = document.querySelector('#simulate-fault');
              fault.value = 'write_failed';
              fault.dispatchEvent(new Event('change', { bubbles: true }));
              const input = document.querySelector('#claim-version');
              input.value = '5.55-tastatur';
              input.dispatchEvent(new Event('input', { bubbles: true }));
              document.querySelector('#curate-return-link').focus();
            }""")
            page.keyboard.press("Enter")
            page.wait_for_selector("#curate-return-error:not([hidden])")
            self.assertTrue(page.url.split("?")[0].endswith("curate.html"),
                            "keyboard activation is stopped by the same rule as a click")
            self.assertEqual(page.input_value("#claim-version"), "5.55-tastatur", "the text is kept")
            self.assertEqual(page.evaluate("document.activeElement.id"), "curate-return-link",
                             "and the keyboard stays on the link that was stopped")

    def test_a_modified_click_keeps_the_page_and_its_draft_where_they_are(self):
        """Ctrl-click opens a second tab; the original page and its unsaved text must not move."""
        with self.detail_from_overview() as (page, _entry):
            page.fill("#claim-version", "6.66-ny-fane")
            before = page.url
            page.click("#curate-return-link", modifiers=["Control"])
            page.wait_for_timeout(200)
            self.assertEqual(page.url, before, "the original page did not navigate")
            self.assertEqual(page.input_value("#claim-version"), "6.66-ny-fane", "and still holds its text")
            self.assertTrue(page.locator("#curate-return-error").is_hidden(),
                            "a modified click is ordinary browser behaviour, not a blocked return")

    def test_changing_only_the_source_selection_shows_up_as_draft_work_in_the_overview(self):
        """Correction order remaining fault 2, end to end: a new source selection is visible work."""
        with self.detail_from_overview() as (page, entry):
            # Point the version claim at one more source, leaving value, assessment and
            # reason exactly as they were.
            added = page.evaluate("""() => {
              const boxes = Array.from(document.querySelectorAll('#claim-form input[id^="evidence-version-"]'));
              const spare = boxes.find(box => !box.checked);
              if (!spare) return null;
              spare.checked = true;
              spare.dispatchEvent(new Event('change', { bubbles: true }));
              return spare.id;
            }""")
            self.assertIsNotNone(added, "the entry offers a second source to point at")
            page.wait_for_function("document.querySelector('#save-state').dataset.status === 'saved'")

            page.click("#curate-return a")
            page.wait_for_selector("#overview-rows tr")
            current = page.locator("#overview-rows tr[aria-current='true']")
            self.assertEqual(current.count(), 1)
            self.assertIn(entry, current.text_content())
            text = current.text_content()
            self.assertIn("kildebelegg", text, "the row says the source selection changed")
            self.assertNotIn("Fullstendig avklart", text,
                             "and an unapproved source change is not a resolution")

    def test_a_restored_cd_description_stays_read_only_through_a_draft_and_a_return(self):
        """Rule D: the verbatim CD text is not editable, in the page and in the data layer."""
        # Sorted by source, the first row is K1 of the first manifest, one of the entries
        # whose description the catalogue restored verbatim.
        with self.overview(query="?sort=source&status=all") as page:
            page.locator("#overview-rows tr td:first-child a").first.click()
            page.wait_for_selector("#entry-heading:not(:empty)")
            self.assertEqual(page.text_content("#entry-id"), "K1")

            description = page.locator("#claim-description")
            self.assertTrue(description.evaluate("box => box.readOnly"),
                            "a restored CD description is read-only on the page")
            original = description.input_value()
            self.assertIn("Syntetisk omtale av", original, "and shows the CD's own words")
            self.assertIn("Gjengitt ordrett fra CD-en",
                          page.text_content(".claim-field:has(#claim-description)"),
                          "with the explanation next to it")

            # The curator's own notes go in the reason, and that saves normally.
            page.click(".claim-field:has(#claim-description) .claim-detail summary")
            page.fill("#reason-description", "Egen vurdering; originalteksten står.")
            page.wait_for_function("document.querySelector('#save-state').dataset.status === 'saved'")

            page.click("#curate-return a")
            page.wait_for_selector("#overview-rows tr")
            page.locator("#overview-rows tr[aria-current='true'] td:first-child a").click()
            page.wait_for_selector("#entry-heading:not(:empty)")
            self.assertEqual(page.locator("#claim-description").input_value(), original,
                             "the original text survived the draft save and the round trip")
            self.assertEqual(page.evaluate("document.querySelector('#reason-description').value"),
                             "Egen vurdering; originalteksten står.",
                             "while the curator's own reason was kept")

            # Forcing a different text past the read-only field is refused by the adapter
            # too, the way the local service refuses it.
            page.evaluate("""() => {
              const box = document.querySelector('#claim-description');
              box.value = 'FORSØK PÅ Å SKRIVE OVER ORIGINALEN';
              box.dispatchEvent(new Event('input', { bubbles: true }));
            }""")
            page.wait_for_function("document.querySelector('#save-state').dataset.status === 'error'")
            self.assertIn("lik CD-omtalen", page.text_content("#decision-error"),
                          "with a message that says where own notes belong")
            self.assertFalse(page.locator("#curate-return a").is_disabled())
            page.click("#curate-return a")
            page.wait_for_selector("#curate-return-error:not([hidden])")
            self.assertTrue(page.url.split("?")[0].endswith("curate.html"),
                            "and the refused write stops the return instead of hiding it")

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
