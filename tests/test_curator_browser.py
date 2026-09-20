"""Browser checks for the curator screen.

These drive a real Chromium through Playwright and cover what only a browser can show:
that preserved source text is rendered as text, that shortcuts stay out of text entry,
that focus moves predictably, and that the narrow view has no horizontal overflow.

They are skipped when Playwright or a browser is unavailable, which is the case on CI.
Run them locally with:

    pip install playwright && playwright install chromium
    python -m unittest tests.test_curator_browser -v

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
class CuratorBrowserTests(unittest.TestCase):
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

    @classmethod
    def tearDownClass(cls):
        cls._stack.close()

    @contextlib.contextmanager
    def curator(self, width=1280, height=900):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        failures = []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.goto(f"{self.base_url}/curate.html", wait_until="networkidle")
        page.wait_for_selector("#entry-heading:not(:empty)")
        try:
            yield page
            self.assertEqual(failures, [], "the page raised a script error")
        finally:
            page.close()

    def test_preserved_source_text_is_never_rendered_as_markup(self):
        with self.curator() as page:
            page.click(".queue-item:has-text('Cpu-Z') button")
            page.wait_for_function("document.querySelector('#entry-id').textContent === 'K23'")
            page.click("#evidence-panel > summary")
            observation = page.text_content("#evidence-list")
            # The K23 observation literally contains "Cpu-Z version <b>1.10</b>".
            self.assertIn("<b>1.10</b>", observation, "the bytes are shown as the source recorded them")
            self.assertEqual(page.locator("#evidence-list b").count(), 0, "no element was created from source text")
            self.assertEqual(page.locator("#evidence-list a").count(), 0, "source text produces no file links")
            self.assertEqual(page.locator("#source-members a").count(), 0, "package members are not links")
            self.assertEqual(page.locator("#source-members script").count(), 0)

    def test_shortcut_ignores_typing_but_works_from_the_page_body(self):
        with self.curator() as page:
            page.click(".queue-item:has-text('Cpu-Z') button")
            page.wait_for_function("document.querySelector('#entry-id').textContent === 'K23'")

            page.click("#claim-version")
            page.keyboard.type("g")
            self.assertEqual(page.input_value("#claim-version"), "1.10g", "the key went into the field")
            self.assertEqual(page.text_content("#entry-id"), "K23", "typing did not approve the entry")

            page.keyboard.press("Control+a")
            page.keyboard.type("1.10")
            page.locator("#entry-heading").click()
            page.keyboard.press("g")
            page.wait_for_function("document.querySelector('#entry-id').textContent !== 'K23'")
            self.assertEqual(page.evaluate("document.activeElement.id"), "entry-heading", "focus moved to the new entry")

    def test_narrow_view_has_no_horizontal_overflow(self):
        with self.curator(width=390, height=844) as page:
            overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            self.assertLessEqual(overflow, 1, "the narrow view must not scroll sideways")
            decision_top = page.evaluate("document.querySelector('.decision-panel').getBoundingClientRect().top")
            queue_top = page.evaluate("document.querySelector('.queue-panel').getBoundingClientRect().top")
            self.assertLess(decision_top, queue_top, "the decision comes before the queue on a narrow screen")

    def test_every_control_has_a_visible_label_and_a_focus_ring(self):
        with self.curator() as page:
            unlabelled = page.evaluate("""
                Array.from(document.querySelectorAll('#claim-form input, #claim-form select, #claim-form textarea'))
                  .filter(control => !control.labels || control.labels.length === 0)
                  .map(control => control.id || control.name)
            """)
            self.assertEqual(unlabelled, [], "every claim control has a visible label")
            self.assertTrue(page.locator("#save-state[role='status'][aria-live='polite']").count())
            self.assertTrue(page.locator("#decision-error[role='alert']").count())

    def test_using_a_proposal_shows_exactly_what_would_be_approved(self):
        """Review #28: the form must never display a different claim than the draft holds."""
        with self.curator() as page:
            page.click(".queue-item:has-text('Cpu-Z') button")
            page.wait_for_function("document.querySelector('#entry-id').textContent === 'K23'")

            page.fill("#claim-version", "9.99")
            page.click('.claim-field:has(#claim-version) .claim-proposal button')

            # The proposal is 1.10 supported by the two payload observations only.
            self.assertEqual(page.input_value("#claim-version"), "1.10", "the field shows the applied proposal")
            checked = page.eval_on_selector_all(
                '#claim-form input[id^="evidence-version-"]',
                "nodes => nodes.filter(n => n.checked).map(n => n.id.replace('evidence-version-', ''))",
            )
            self.assertEqual(checked, ["K23-e3", "K23-e4"], "the evidence boxes match the proposal")

            # A proposal is never accepted on the curator's behalf.
            self.assertTrue(page.is_checked("#assessment-version-accepted") or page.is_checked("#assessment-version-unresolved"))

            # What the screen shows is what survives a save and a reload.
            page.wait_for_selector("#save-state[data-status='saved']")
            page.reload(wait_until="networkidle")
            page.wait_for_selector("#entry-heading:not(:empty)")
            self.assertEqual(page.input_value("#claim-version"), "1.10", "the saved draft matches what was shown")
            reloaded = page.eval_on_selector_all(
                '#claim-form input[id^="evidence-version-"]',
                "nodes => nodes.filter(n => n.checked).map(n => n.id.replace('evidence-version-', ''))",
            )
            self.assertEqual(reloaded, ["K23-e3", "K23-e4"])

    def test_typing_is_never_interrupted_by_a_redraw(self):
        """The reconciliation must not touch the control the curator is typing in."""
        with self.curator() as page:
            page.click(".queue-item:has-text('Cpu-Z') button")
            page.wait_for_function("document.querySelector('#entry-id').textContent === 'K23'")

            page.click("#claim-version")
            page.keyboard.press("Control+a")
            page.keyboard.type("2.05")
            # Let autosave land while the field still has focus.
            page.wait_for_selector("#save-state[data-status='saved']")
            self.assertEqual(page.input_value("#claim-version"), "2.05", "the typed value survived the save render")
            self.assertEqual(page.evaluate("document.activeElement.id"), "claim-version", "focus stayed put")

            # Continue typing at the caret; nothing was reset behind the curator's back.
            page.keyboard.type("b")
            self.assertEqual(page.input_value("#claim-version"), "2.05b")

    def test_a_session_without_browser_storage_says_so(self):
        """Review #27 P3: an ephemeral session is explicit, never an implied saved draft."""
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            # A browser that refuses site data, as a private window with storage blocked does.
            page.add_init_script(
                "Object.defineProperty(window, 'localStorage', {"
                "  get() { throw new DOMException('blocked', 'SecurityError'); }"
                "});"
            )
            page.goto(f"{self.base_url}/curate.html", wait_until="networkidle")
            page.wait_for_selector("#entry-heading:not(:empty)")
            banner = page.text_content("#fixture-banner")
            self.assertIn("Nettleserlagring er ikke tilgjengelig", banner)
            self.assertIn("forsvinner når siden lastes på nytt", banner)
            # The screen still works; it just promises nothing durable.
            page.fill("#claim-version", "1.10-flyktig")
            self.assertEqual(page.input_value("#claim-version"), "1.10-flyktig")
        finally:
            page.close()

    def test_a_simulated_write_failure_keeps_the_edit_and_stops_the_advance(self):
        with self.curator() as page:
            page.click(".queue-item:has-text('Cpu-Z') button")
            page.wait_for_function("document.querySelector('#entry-id').textContent === 'K23'")
            page.click("#simulation-panel > summary")
            page.select_option("#simulate-fault", "write_failed")
            page.fill("#claim-version", "1.10-uferdig")
            page.click("#action-commit")
            page.wait_for_selector("#decision-error:not([hidden])")

            self.assertEqual(page.text_content("#entry-id"), "K23", "a failed write does not advance the queue")
            self.assertEqual(page.input_value("#claim-version"), "1.10-uferdig", "the typed value is kept on screen")
            self.assertTrue(page.is_visible("#action-retry"), "the failed operation can be retried")


if __name__ == "__main__":
    unittest.main()
