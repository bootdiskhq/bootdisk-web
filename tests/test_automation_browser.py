"""Browser checks for the automatic first-pass queue (automation.html).

A real Chromium through Playwright: what the four ways in say, that loading, missing, broken
and empty are different screens with no counts on the broken ones, that search, filters and
page survive opening and closing an entry with the keyboard, that source text is shown
literally, that the page never writes, and that 360 px works.

Skipped when Playwright or a browser is unavailable, as on CI. Locally:

    CURATOR_CHROMIUM=/path/to/chrome python -m unittest tests.test_automation_browser -v
"""
import contextlib
import functools
import http.server
import json
import os
import re
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_URL = "**/tests/fixtures/automation-queue-v1.json"
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "automation-queue-v1.json").read_text(encoding="utf-8"))
PAGE_SIZE = 25

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
class AutomationQueueBrowserTests(unittest.TestCase):
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
        # Release the browser and Playwright so a later browser class can start its own.
        cls._stack.close()

    @contextlib.contextmanager
    def page(self, query="", width=1280, height=900, route=None, ready="#aq-list li"):
        page = self.browser.new_page(viewport={"width": width, "height": height})
        failures, requests = [], []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.on("request", lambda request: requests.append((request.method, request.url)))
        if route:
            page.route(FIXTURE_URL, route)
        page.goto(f"{self.base_url}/automation.html{query}")
        if ready:
            page.wait_for_selector(ready)
        page.requests = requests
        try:
            yield page
            self.assertEqual(failures, [], "the page raised a script error")
            self.assertEqual({method for method, _ in requests}, {"GET"}, "the page only ever reads")
            self.assertEqual(page.evaluate("localStorage.length"), 0, "nothing is stored in the browser")
        finally:
            page.close()

    def text(self, page, selector):
        return page.text_content(selector) or ""

    def open_title(self, page, title):
        page.get_by_role("button", name=title, exact=True).click()
        page.wait_for_selector("#aq-panel:not([hidden])")

    def open_row(self, page, index=0):
        page.locator("#aq-list .aq-open").nth(index).click()
        page.wait_for_selector("#aq-panel:not([hidden])")

    # --- the four ways in -----------------------------------------------------------------

    def test_contract_example_shows_every_stage_and_status_with_its_meaning(self):
        with self.page("?kilde=prove") as page:
            self.assertTrue(page.is_visible("#aq-sample-banner"))
            self.assertIn("Prøvedata", self.text(page, "#aq-sample-banner"))
            self.assertIn("fremtidsscenarier", self.text(page, "#aq-sample-banner"))
            stages = page.locator("#aq-stages li")
            self.assertEqual(stages.count(), 4)
            labels = [stages.nth(i).locator(".aq-stage-label").text_content() for i in range(4)]
            self.assertEqual(labels, ["Trenger din vurdering", "Undersøkes maskinelt", "Forslag klare", "Bevarte vurderinger"])
            self.assertIn("ikke en godkjenning", self.text(page, ".aq-stage-proposals"))
            self.assertIn("ikke oppgaver til deg", self.text(page, ".aq-stage-inspecting"))
            self.assertIn("skjermet", self.text(page, ".aq-stage-protected"))
            legend = self.text(page, "#aq-legend")
            for label in ("Forslag", "Ikke fastslått", "Til maskinell undersøkelse", "Kildene er uenige", "Bevart menneskevurdering"):
                self.assertIn(label, legend)
            rows = self.text(page, "#aq-list")
            for status in ("Forslag:", "Ikke fastslått:", "Til maskinell undersøkelse:", "Kildene er uenige:", "Bevart menneskevurdering:"):
                self.assertIn(status, rows)
            # Unknown fields are mentioned quietly and not as something to approve.
            self.assertIn("Ukjent er ikke en oppgave til deg", self.text(page, "#aq-unknown"))
            # The human count comes only from requires_human, not from machine tasks.
            self.assertIn("1 post trenger din vurdering", self.text(page, "#aq-human-note"))
            self.assertIn("3 planlagte undersøkelser", self.text(page, "#aq-human-note"))

    def test_no_human_work_is_not_presented_as_finished_while_the_machine_has_work(self):
        first_pass = json.loads(json.dumps(FIXTURE))
        first_pass["entries"] = [e for e in first_pass["entries"] if e["stage"] in ("proposals", "inspecting")]
        first_pass["summary"].update(entries=2, human_exceptions=0, machine_tasks=3,
                                     stage_counts={"proposals": 1, "inspecting": 1, "needs_review": 0, "protected": 0},
                                     field_status_counts={"candidate": 4, "retain_unknown": 5, "inspect": 1, "conflict": 0, "preserve": 0})
        body = json.dumps(first_pass)
        with self.page("?kilde=prove", route=lambda route: route.fulfill(status=200, body=body, content_type="application/json")) as page:
            note = self.text(page, "#aq-human-note")
            self.assertIn("Ingen poster trenger din vurdering nå", note)
            self.assertIn("det betyr ikke at programmene er ferdig kuratert", note)
            self.assertEqual(self.text(page, ".aq-stage-needs_review .aq-stage-count"), "0")
            page.click(".aq-stage-needs_review .aq-stage-button")
            page.wait_for_selector("#aq-empty:not([hidden])")
            self.assertIn("Ingen poster passer", self.text(page, "#aq-empty"))
            self.assertNotIn("ferdig", self.text(page, "#aq-empty"))

    # --- states ------------------------------------------------------------------------------

    def test_without_a_chosen_source_nothing_is_loaded_and_no_sample_is_shown(self):
        with self.page("", ready="#aq-source:not([hidden])") as page:
            self.assertFalse(page.is_visible("#aq-sample-banner"))
            self.assertFalse(page.is_visible("#aq-queue"))
            self.assertEqual(self.text(page, "#aq-count"), "")
            self.assertFalse(any(("automation-queue" in url or "automation-sample" in url) for _, url in page.requests))

    def test_loading_is_its_own_state(self):
        held = []
        body = json.dumps(FIXTURE)
        page = self.browser.new_page()
        try:
            # The answer is held back until the loading screen has been checked.
            page.route(FIXTURE_URL, lambda route: held.append(route))
            page.goto(f"{self.base_url}/automation.html?kilde=prove", wait_until="domcontentloaded")
            page.wait_for_selector("#aq-loading:not([hidden])")
            self.assertFalse(page.is_visible("#aq-queue"))
            self.assertFalse(page.is_visible("#aq-error"))
            self.assertEqual(self.text(page, "#aq-count"), "")
            page.wait_for_function("true")
            self.assertEqual(len(held), 1)
            held[0].fulfill(status=200, body=body, content_type="application/json")
            page.wait_for_selector("#aq-list li")
            self.assertFalse(page.is_visible("#aq-loading"))
        finally:
            page.close()

    def assert_error(self, route, kind, title):
        with self.page("?kilde=prove", route=route, ready="#aq-error:not([hidden])") as page:
            self.assertEqual(page.get_attribute("#aq-error", "data-kind"), kind)
            self.assertEqual(self.text(page, "#aq-error-title"), title)
            self.assertFalse(page.is_visible("#aq-queue"), "no counts, no rows")
            self.assertEqual(page.locator("#aq-list li").count(), 0)
            self.assertNotRegex(self.text(page, "main"), r"\b0 (treff|poster)")
            fetched = [url for _, url in page.requests if "automation" in url and url.endswith((".json", "sample.js"))]
            self.assertEqual(len(fetched), 1, f"no second source is tried: {fetched}")
            return self.text(page, "#aq-error-text")

    def test_missing_invalid_json_invalid_schema_and_unknown_values_are_different_errors(self):
        self.assert_error(lambda route: route.fulfill(status=404, body="nope"), "missing", "Fant ikke køfilen")
        self.assert_error(lambda route: route.abort(), "missing", "Fant ikke køfilen")
        self.assert_error(lambda route: route.fulfill(status=200, body="{\"schema\":"), "invalid_json", "Køfilen er ikke gyldig JSON")
        wrong = dict(FIXTURE, schema="bootdisk-automation-queue-0")
        self.assert_error(lambda route: route.fulfill(status=200, body=json.dumps(wrong)), "invalid_schema", "Køfilen følger ikke kontrakten")
        unknown = json.loads(json.dumps(FIXTURE))
        unknown["entries"][0]["fields"][0]["status"] = "approved"
        message = self.assert_error(lambda route: route.fulfill(status=200, body=json.dumps(unknown)), "unknown_value", "Køfilen har en ukjent verdi")
        self.assertIn("approved", message)

    def test_an_empty_run_says_so_and_does_not_claim_the_programs_are_curated(self):
        empty = dict(FIXTURE, entries=[], summary={
            "entries": 0, "field_status_counts": {s: 0 for s in ("candidate", "retain_unknown", "inspect", "conflict", "preserve")},
            "stage_counts": {s: 0 for s in ("proposals", "inspecting", "needs_review", "protected")},
            "machine_tasks": 0, "human_exceptions": 0, "automatic_decisions": 0, "human_decisions": 0})
        with self.page("?kilde=prove", route=lambda route: route.fulfill(status=200, body=json.dumps(empty)),
                       ready="#aq-empty:not([hidden])") as page:
            self.assertIn("Køen er tom", self.text(page, "#aq-empty"))
            self.assertIn("betyr ikke at programmene er kuratert", self.text(page, "#aq-empty"))
            self.assertFalse(page.is_visible("#aq-error"))

    # --- sample marking through the file picker ----------------------------------------------

    def pick_files(self, page, documents):
        page.set_input_files("#aq-file-input", [
            {"name": name, "mimeType": "application/json", "buffer": json.dumps(doc).encode("utf-8")}
            for name, doc in documents])

    def real_documents(self, page, count=2):
        """Snapshots without any sample marking, standing in for real Catalog output."""
        return page.evaluate("""count => new Promise(resolve => {
            const script = document.createElement('script');
            script.src = 'automation-sample.js';
            script.onload = () => resolve(createAutomationSampleSnapshots({ manifests: count, perManifest: 4 })
              .map(doc => { delete doc.fixture; delete doc.fixture_note; return doc; }));
            document.body.append(script);
        })""", count)

    def test_a_marked_file_opened_through_the_file_picker_is_labelled_as_sample_data(self):
        with self.page("?kilde=fil", ready="#aq-file:not([hidden])") as page:
            self.assertFalse(page.is_visible("#aq-sample-banner"))
            # A neutral name: the marking inside the file decides, not the file name.
            self.pick_files(page, [("resultat.json", FIXTURE)])
            page.wait_for_selector("#aq-list li")
            self.assertTrue(page.is_visible("#aq-sample-banner"))
            banner = self.text(page, "#aq-sample-banner")
            self.assertIn("Prøvedata", banner)
            self.assertIn("fixture: true", banner)
            self.assertIn(FIXTURE["fixture_note"], banner)
            self.assertTrue(self.text(page, "#aq-count").startswith("Prøvedata · "))
            page.click("#aq-list .aq-row-needs_review .aq-open")
            page.wait_for_selector("#aq-panel:not([hidden])")
            self.assertTrue(page.is_visible("#aq-sample-banner"), "the banner stays while reading an entry")
            self.assertIn("Prøvedata", self.text(page, "#aq-panel .aq-panel-fixture"))

    def test_real_files_opened_through_the_file_picker_are_not_labelled_as_sample_data(self):
        with self.page("?kilde=fil", ready="#aq-file:not([hidden])") as page:
            documents = self.real_documents(page)
            self.pick_files(page, [(f"cd{i}.json", doc) for i, doc in enumerate(documents, 1)])
            page.wait_for_selector("#aq-list li")
            self.assertFalse(page.is_visible("#aq-sample-banner"))
            self.assertNotIn("Prøvedata", self.text(page, "#aq-count"))
            self.open_row(page)
            self.assertEqual(page.locator("#aq-panel .aq-panel-fixture").count(), 0)

    def test_mixing_real_and_sample_files_is_refused_without_counts(self):
        with self.page("?kilde=fil", ready="#aq-file:not([hidden])") as page:
            documents = self.real_documents(page, 1)
            self.pick_files(page, [("cd1.json", documents[0]), ("eksempel.json", FIXTURE)])
            page.wait_for_selector("#aq-error:not([hidden])")
            self.assertEqual(page.get_attribute("#aq-error", "data-kind"), "mixed_fixture")
            self.assertEqual(self.text(page, "#aq-error-title"), "Prøvedata og ekte køfiler er blandet")
            self.assertFalse(page.is_visible("#aq-queue"))
            self.assertEqual(page.locator("#aq-list li").count(), 0)

    def test_sample_chosen_in_the_address_bar_is_marked_in_list_and_panel(self):
        for query in ("?kilde=prove", "?kilde=syntetisk"):
            with self.page(query) as page:
                self.assertTrue(page.is_visible("#aq-sample-banner"))
                self.assertTrue(self.text(page, "#aq-count").startswith("Prøvedata · "), query)
                self.open_row(page)
                self.assertIn("Prøvedata", self.text(page, "#aq-panel .aq-panel-fixture"), query)

    # --- the panel ---------------------------------------------------------------------------

    def test_the_panel_shows_proposal_reason_rule_and_evidence_and_nothing_is_approved(self):
        with self.page("?kilde=prove") as page:
            page.click("#aq-list .aq-row-needs_review .aq-open")
            page.wait_for_selector("#aq-panel:not([hidden])")
            panel = self.text(page, "#aq-panel")
            self.assertIn("director-first-pass-1", panel)
            self.assertIn("version-not-established-1", panel)
            self.assertIn("Syntetisk eksempel: undersøkelsen fant to ulike programversjoner.", panel)
            version = page.locator('#aq-panel .aq-field[data-field="version"] .aq-evidence-item')
            self.assertEqual(version.count(), 2, "conflicting evidence is shown side by side")
            self.assertEqual([version.nth(i).locator(".aq-verbatim").text_content() for i in range(2)],
                             ["Product version 1.0", "Product version 2.0"])
            boxes = [version.nth(i).bounding_box() for i in range(2)]
            self.assertAlmostEqual(boxes[0]["y"], boxes[1]["y"], delta=2, msg="side by side on a wide screen")
            # null is shown as not established, never as the word null or as a deletion.
            self.assertIn("Ikke fastslått", self.text(page, '#aq-panel .aq-field[data-field="version"] .aq-proposed'))
            self.assertIsNone(re.search(r"\bnull\b", panel))
            self.assertNotRegex(panel.lower(), r"slett")
            # "godkjent" only ever appears as "ikke godkjent".
            self.assertEqual(re.findall(r"(\S+) godkjent", panel), ["ikke"] * len(re.findall(r"godkjent", panel)))
            self.assertIn("Spill (game)", self.text(page, '#aq-panel .aq-field[data-field="content_kind"] .aq-proposed'))
            buttons = [b.strip() for b in page.locator("#aq-panel button").all_text_contents()]
            self.assertEqual(set(buttons), {"Tilbake til køen"}, "no approve, save or undo buttons")
            # Hashes and pointers sit behind the technical details.
            self.assertFalse(page.locator("#aq-panel .aq-technical dl").first.is_visible())

    def test_the_protected_entry_is_shown_as_preserved_not_as_unknown_work(self):
        with self.page("?kilde=prove") as page:
            page.click("#aq-list .aq-row-protected .aq-open")
            page.wait_for_selector("#aq-panel:not([hidden])")
            fields = page.locator("#aq-panel .aq-field")
            self.assertEqual(fields.count(), 5)
            for i in range(5):
                self.assertIn("Bevart menneskevurdering", fields.nth(i).locator(".aq-field-status").text_content())
                self.assertIn("Menneskevurderingen står", fields.nth(i).locator(".aq-proposed").text_content())

    def test_the_original_description_keeps_its_spaces_and_line_breaks_and_markup_stays_text(self):
        with self.page("?kilde=syntetisk") as page:
            # Entry 11 of the sample: every eleventh blurb has markup-like text.
            page.fill("#aq-search", "Nordlystegn 12")
            page.wait_for_selector("text=Prøvepost Nordlystegn 12")
            self.open_title(page, "Prøvepost Nordlystegn 12")
            expected = page.evaluate("""() => createAutomationSampleSnapshots({ manifests: 1, perManifest: 12 })[0]
                .entries[11].fields.find(f => f.field === 'description').proposed""")
            self.assertIn("<script>", expected)
            self.assertIn("\r\n", expected)
            shown = page.locator('#aq-panel .aq-field[data-field="description"] .aq-proposed pre').text_content()
            self.assertEqual(shown, expected)
            self.assertEqual(page.locator("#aq-panel b, #aq-panel script").count(), 0, "no markup from the source was created")
            evidence = page.locator('#aq-panel .aq-field[data-field="description"] .aq-evidence .aq-verbatim').text_content()
            self.assertEqual(evidence, expected)
            self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('#aq-panel pre')).whiteSpace"), "pre-wrap")

    def test_the_same_k_id_on_two_cds_opens_two_different_panels(self):
        with self.page("?kilde=syntetisk&q=K1&sort=source") as page:
            page.wait_for_selector("#aq-list li")
            sources = page.locator("#aq-list .aq-row-source").all_text_contents()
            self.assertTrue(sources[0].startswith("Kildepost K1 · CD 1 av 125"))
            self.assertTrue(any(s.startswith("Kildepost K1 · CD 2 av 125") for s in sources))
            second = next(i for i, s in enumerate(sources) if s.startswith("Kildepost K1 · CD 2 av 125"))
            seen = []
            for index in (0, second):
                self.open_row(page, index)
                manifest = page.url.split("manifest=")[1].split("&")[0]
                refs = page.locator("#aq-panel .aq-evidence-item .aq-technical dd").all_text_contents()
                menu = page.locator('#aq-panel .aq-field[data-field="identity"] .aq-verbatim').first.text_content()
                seen.append((manifest, menu))
                self.assertTrue(all(ref.startswith("sha256:") is False or ref.replace(":", "%3A") == manifest
                                    for ref in refs[0::3]), "every piece of evidence belongs to this CD")
                page.keyboard.press("Escape")
                page.wait_for_selector("#aq-panel", state="hidden")
            self.assertNotEqual(seen[0][0], seen[1][0])
            self.assertNotEqual(seen[0][1], seen[1][1])

    # --- round trip, keyboard, focus ---------------------------------------------------------

    def test_search_filters_and_page_survive_open_and_close_with_focus_back_on_the_row(self):
        with self.page("?kilde=syntetisk") as page:
            page.fill("#aq-search", "kvasar")
            page.select_option("#aq-stage", "inspecting")
            page.select_option("#aq-status", "retain_unknown")
            page.wait_for_function("document.querySelector('#aq-page').textContent.includes('av')")
            page.click("#aq-next")
            page.wait_for_function("document.querySelector('#aq-page').textContent.startsWith('Side 2')")
            self.assertEqual(page.evaluate("document.activeElement.id"), "aq-results-title",
                             "after turning the page the keyboard starts at the results")
            before = (self.text(page, "#aq-count"), self.text(page, "#aq-page"), page.url)
            row = page.locator("#aq-list .aq-open").nth(3)
            title = row.text_content()
            row.focus()
            page.keyboard.press("Enter")
            page.wait_for_selector("#aq-panel:not([hidden])")
            self.assertEqual(page.evaluate("document.activeElement.id"), "aq-panel-title")
            self.assertEqual(self.text(page, "#aq-panel-title"), title)
            self.assertIn("post=", page.url)
            page.keyboard.press("Escape")
            page.wait_for_selector("#aq-panel", state="hidden")
            self.assertEqual((self.text(page, "#aq-count"), self.text(page, "#aq-page"), page.url), before)
            self.assertEqual(page.evaluate("document.activeElement.textContent"), title)
            self.assertEqual(page.input_value("#aq-search"), "kvasar")
            self.assertEqual(page.input_value("#aq-stage"), "inspecting")
            self.assertEqual(page.input_value("#aq-status"), "retain_unknown")

            # The close button and the browser's back button do the same.
            page.locator("#aq-list .aq-open").nth(5).click()
            page.wait_for_selector("#aq-panel:not([hidden])")
            page.go_back()
            page.wait_for_selector("#aq-panel", state="hidden")
            self.assertEqual(page.url, before[2])
            page.locator("#aq-list .aq-open").nth(1).click()
            page.wait_for_selector("#aq-panel:not([hidden])")
            page.click("#aq-close-bottom")
            page.wait_for_selector("#aq-panel", state="hidden")
            self.assertEqual(page.url, before[2])

            # A reload of a shared address opens the same entry again.
            page.locator("#aq-list .aq-open").nth(2).click()
            page.wait_for_selector("#aq-panel:not([hidden])")
            opened = self.text(page, "#aq-panel-title")
            page.reload()
            page.wait_for_selector("#aq-panel:not([hidden])")
            self.assertEqual(self.text(page, "#aq-panel-title"), opened)

    def test_the_panel_does_not_trap_the_keyboard(self):
        with self.page("?kilde=prove") as page:
            self.open_row(page)
            outside = False
            for _ in range(60):
                page.keyboard.press("Tab")
                if not page.evaluate("document.querySelector('#aq-panel').contains(document.activeElement)"):
                    outside = True
                    break
            self.assertTrue(outside, "Tab leaves the panel")
            page.focus("#aq-panel-title")
            page.keyboard.press("Shift+Tab")
            self.assertEqual(page.evaluate("document.activeElement.id"), "aq-close")
            page.keyboard.press("Enter")
            page.wait_for_selector("#aq-panel", state="hidden")

    def test_focus_is_visible_and_reading_order_follows_the_screen(self):
        with self.page("?kilde=prove") as page:
            page.focus("#aq-list .aq-open")
            page.keyboard.press("Shift+Tab")
            page.keyboard.press("Tab")
            outline = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
            self.assertNotEqual(outline, "none")
            headings = page.evaluate("[...document.querySelectorAll('main h1, main h2:not([hidden])')].filter(h => h.offsetParent).map(h => h.textContent)")
            self.assertEqual(headings[0], "Automatisk førstegjennomgang")
            self.assertIn("Poster", headings)
            self.open_row(page)
            order = page.evaluate("""[...document.querySelectorAll('#aq-panel h2, #aq-panel h3')].map(h => h.textContent)""")
            self.assertEqual(order[0], "Prøveprogram – motstridende versjoner")
            self.assertEqual(order[1:], ["Identitet", "Versjon", "Innholdstype", "Utgave", "Beskrivelse"])

    # --- scale and narrow screens ------------------------------------------------------------

    def test_five_thousand_entries_build_one_page_and_respond_quickly(self):
        started = time.perf_counter()
        with self.page("?kilde=syntetisk") as page:
            loaded = time.perf_counter() - started
            self.assertIn("5 000", self.text(page, "#aq-count").replace(" ", " "))
            self.assertEqual(page.locator("#aq-list li").count(), PAGE_SIZE)
            self.assertEqual(page.locator("#aq-panel .aq-field").count(), 0, "no panel is built before one is opened")
            timings = page.evaluate("""async () => {
              const input = document.querySelector('#aq-search');
              const out = {};
              for (const text of ['kvasar', 'K17', 'polarsjakk', '']) {
                const t = performance.now();
                input.value = text;
                input.dispatchEvent(new Event('input'));
                out['search ' + (text || '(tomt)')] = performance.now() - t;
              }
              const t = performance.now();
              document.querySelector('#aq-list .aq-open').click();
              out.open = performance.now() - t;
              return out;
            }""")
            self.assertEqual(page.locator("#aq-panel .aq-field").count(), 5)
            print(f"\n5000 entries in Chromium: page load {loaded * 1000:.0f} ms, "
                  + ", ".join(f"{name} {ms:.1f} ms" for name, ms in timings.items()))
            for name, ms in timings.items():
                self.assertLess(ms, 250, name)

    def test_360_px_has_no_horizontal_scroll_in_the_list_or_the_panel(self):
        with self.page("?kilde=syntetisk&q=Kvasarlyd+51", width=360, height=740) as page:
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 360)
            self.open_title(page, "Prøvepost Kvasarlyd 51")  # entry 50: the long description
            self.assertGreater(len(self.text(page, '#aq-panel .aq-field[data-field="description"] .aq-proposed')), 1000)
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 360)
            page.click("#aq-panel .aq-technical summary >> nth=0")
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 360)


if __name__ == "__main__":
    unittest.main()
