"""Om prosjektet og kontaktskjemaet i Chromium (docs/kontaktskjema.md).

Siden kjøres fra en ekte releasepakke (PRØVEDATA fra tests/synthetic_collection.py) i PHPs
innebygde server, med api/kontakt.php og privat konfig ved siden av webroten slik som på
webhotellet. Simulert: CAPTCHA-widgeten (et lite falskt Turnstile-skript som svarer på
challenges.cloudflare.com i nettleseren), leverandørens siteverify (lokal falsk tjeneste) og
e-postutsendingen (falsk sendmail). Ingen ekte e-post sendes, og ingen ekstern tjeneste brukes.

Hoppes over uten Playwright, Chromium eller PHP. Kjør med:

    pip install playwright==1.63.0
    CURATOR_CHROMIUM=/sti/til/chrome python -m unittest tests.test_contact_browser -v
"""
from __future__ import annotations

import contextlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import contact_harness as h  # noqa: E402
import synthetic_collection  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment dependent
    sync_playwright = None

FAKE_TURNSTILE = r"""
window.turnstile = {
  widgets: [],
  render(el, opts) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'fake-captcha';
    button.textContent = 'Jeg er ikke en robot';
    button.addEventListener('click', () => { button.textContent = 'Bekreftet'; opts.callback(window.__nextToken || 'ok-token'); });
    el.appendChild(button);
    this.widgets.push({ opts, button });
    return this.widgets.length - 1;
  },
  reset(id) { this.widgets[id].button.textContent = 'Jeg er ikke en robot'; window.__resets = (window.__resets || 0) + 1; },
};
window.__expire = () => window.turnstile.widgets[0].opts['expired-callback']();
if (typeof window.bootdiskCaptchaReady === 'function') window.bootdiskCaptchaReady();
"""
EMAIL = "leser@eksempel.invalid"
TEXT = "Jeg har K-CD 15/2001. Lenke: http://127.0.0.1/index.html?entry=K37\nHilsen en leser – æøå"
KEPT = "Teksten din står fortsatt i skjemaet."


@unittest.skipUnless(sync_playwright and h.PHP, "Playwright og PHP er nødvendig for nettlesertestene")
class ContactBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stack = contextlib.ExitStack()
        cls.work = Path(cls._stack.enter_context(tempfile.TemporaryDirectory()))
        data, publish = synthetic_collection.build_synthetic(cls.work / "source")
        release = cls.work / "release"
        result = synthetic_collection.package(data, publish, release)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.verifier = h.Verifier()
        cls._stack.callback(cls.verifier.close)
        cls.hotel = h.Webhotel(cls.work, site_files=())
        shutil.rmtree(cls.hotel.www)
        shutil.copytree(release, cls.hotel.www)
        cls.config = h.base_config(cls.hotel.state, cls.verifier, cls.hotel.origin)
        cls.hotel.write_config(cls.config)
        cls.base = cls.hotel.start()
        cls._stack.callback(cls.hotel.stop)
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

    def setUp(self):
        self.hotel.write_config(self.config)
        self.hotel.fail_sending(False)
        (self.hotel.state / "kontakt-grenser.json").unlink(missing_ok=True)
        for mail in self.hotel.outbox.glob("*.eml*"):
            mail.unlink()

    @contextlib.contextmanager
    def page(self, path="/om-prosjektet.html", width=1280, height=900, captcha="fake", **options):
        context = self.browser.new_context(viewport={"width": width, "height": height}, **options)
        page = context.new_page()
        problems, posts = [], []
        page.on("pageerror", lambda error: problems.append(str(error)))
        page.on("console", lambda message: message.type == "error" and "Failed to load resource" not in message.text
                and problems.append(message.text))
        page.on("request", lambda request: request.method == "POST" and posts.append(request.url))
        page.route("https://challenges.cloudflare.com/**", (lambda route: route.fulfill(
            status=200, content_type="text/javascript", body=FAKE_TURNSTILE)) if captcha == "fake" else (lambda route: route.abort()))
        page.posts = posts
        page.goto(self.base + path, wait_until="networkidle")
        try:
            yield page
            self.assertEqual(problems, [], "skript- eller konsollfeil")
        finally:
            context.close()

    def fill(self, page, email=EMAIL, text=TEXT):
        page.fill("#contact-email", email)
        page.fill("#contact-message", text)

    def confirm(self, page, token="ok-token"):
        page.evaluate("t => { window.__nextToken = t; }", token)
        page.click(".fake-captcha")
        page.wait_for_selector("#contact-captcha[data-state=ready]")

    def submit_and_wait(self, page):
        page.click("#contact-submit")
        page.wait_for_selector("#contact-feedback[data-state=error], #contact-feedback[data-state=sent]")
        return page.get_attribute("#contact-feedback", "data-state"), page.text_content("#contact-feedback")

    def assertKept(self, page, feedback, email=EMAIL, text=TEXT):
        self.assertIn(KEPT, feedback)
        self.assertEqual(page.input_value("#contact-email"), email)
        self.assertEqual(page.input_value("#contact-message"), text)

    # --- meny --------------------------------------------------------------------------------

    def test_menu_item_follows_latest_changes_everywhere_also_on_source_entries(self):
        for path in ("/", "/index.html?entry=K37", "/archive.html", "/collection.html?collection=komputer-for-alle",
                     "/updates.html", "/404.html", "/om-prosjektet.html"):
            with self.subTest(path), self.page(path) as page:
                if "entry=" in path:
                    page.wait_for_selector("html.entry-view #entry-breadcrumbs li[aria-current=page]")
                labels = page.locator(".site-nav a").all_text_contents()
                self.assertEqual(labels[-2:], ["Siste endringer", "Om prosjektet"])
                self.assertTrue(page.is_visible(".site-nav a[href='om-prosjektet.html']"))
        with self.page("/index.html?entry=K37") as page:
            page.click(".site-nav a[href='om-prosjektet.html']")
            page.wait_for_selector("#contact-form[data-ready=true]")
            self.assertEqual(page.get_attribute(".site-nav a[aria-current=page]", "href"), "om-prosjektet.html")
            self.assertEqual(page.title(), "Om prosjektet — Bootdisk")

    def test_mobile_menu_and_page_fit_narrow_screens(self):
        for width in (320, 360, 414, 768):
            with self.subTest(width=width), self.page(width=width, height=740, is_mobile=True, has_touch=True) as page:
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                if width <= 720:
                    nav = page.locator(".site-nav ul").bounding_box()
                    about = page.locator(".site-nav a[href='om-prosjektet.html']").bounding_box()
                    self.assertAlmostEqual(about["width"], nav["width"], delta=1.5, msg="siste valg får hele raden")
                    button = page.locator("#contact-submit").bounding_box()
                    self.assertGreaterEqual(button["height"], 44)
                    size = page.evaluate("parseFloat(getComputedStyle(document.querySelector('#contact-email')).fontSize)")
                    self.assertGreaterEqual(size, 16, "ingen automatisk zoom på iOS")

    # --- tastatur og mobil -------------------------------------------------------------------

    def test_keyboard_only_submission(self):
        with self.page() as page:
            visited = []
            for _ in range(40):
                page.keyboard.press("Tab")
                current = page.evaluate("document.activeElement.id || document.activeElement.className || document.activeElement.tagName")
                visited.append(current)
                if current == "contact-email":
                    break
            self.assertEqual(visited[0], "skip-link", "hopp-lenken kommer først")
            self.assertEqual(visited[-1], "contact-email")
            page.keyboard.type(EMAIL)
            page.keyboard.press("Tab")
            self.assertEqual(page.evaluate("document.activeElement.id"), "contact-message")
            page.keyboard.type("Rettelse til K37 via tastaturet.")
            page.wait_for_selector(".fake-captcha")
            page.keyboard.press("Tab")
            self.assertEqual(page.evaluate("document.activeElement.className"), "fake-captcha", "fellefeltet hoppes over")
            page.keyboard.press("Space")
            page.wait_for_selector("#contact-captcha[data-state=ready]")
            page.keyboard.press("Tab")
            self.assertEqual(page.evaluate("document.activeElement.id"), "contact-submit")
            page.keyboard.press("Enter")
            page.wait_for_selector("#contact-feedback[data-state=sent]")
            self.assertEqual(page.evaluate("document.activeElement.id"), "contact-feedback", "fokus til kvitteringen")
            self.assertIn("Takk! Meldingen er sendt", page.text_content("#contact-feedback"))
            self.assertEqual(page.input_value("#contact-message"), "")
        [mail] = self.hotel.sent()
        self.assertEqual(mail["message"]["Reply-To"], EMAIL)
        self.assertIn("Rettelse til K37 via tastaturet.", mail["message"].get_content())

    def test_mobile_touch_submission(self):
        with self.page(width=360, height=740, is_mobile=True, has_touch=True) as page:
            page.tap("#contact-email")
            page.fill("#contact-email", EMAIL)
            page.tap("#contact-message")
            page.fill("#contact-message", TEXT)
            page.wait_for_selector(".fake-captcha")
            page.tap(".fake-captcha")
            page.wait_for_selector("#contact-captcha[data-state=ready]")
            page.tap("#contact-submit")
            page.wait_for_selector("#contact-feedback[data-state=sent]")
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 360)
        [mail] = self.hotel.sent()
        self.assertIn(TEXT, mail["message"].get_content())
        self.assertEqual(mail["message"]["To"], h.FAKE_RECIPIENT)

    # --- adressefeil ---------------------------------------------------------------------------

    def test_invalid_address_is_caught_before_sending(self):
        with self.page() as page:
            self.fill(page, email="ikke en adresse")
            state, feedback = self.submit_and_wait(page)
            self.assertEqual(state, "error")
            self.assertIn("e-postadresse", feedback)
            self.assertKept(page, feedback, email="ikke en adresse")
            self.assertEqual(page.get_attribute("#contact-email", "aria-invalid"), "true")
            self.assertEqual(page.evaluate("document.activeElement.id"), "contact-email")
            self.assertEqual(page.get_attribute("#contact-feedback", "role"), "alert")
            self.assertEqual(page.posts, [])

    def test_address_the_server_refuses_keeps_the_text(self):
        with self.page() as page:
            self.fill(page, email="ærlig@eksempel.invalid")  # nettleseren godtar, PHP gjør det ikke
            page.focus("#contact-message")
            self.confirm(page)
            state, feedback = self.submit_and_wait(page)
            self.assertEqual(state, "error")
            self.assertIn("e-postadresse", feedback)
            self.assertKept(page, feedback, email="ærlig@eksempel.invalid")
            self.assertEqual(len(page.posts), 1)
        self.assertEqual(self.hotel.sent(), [])

    # --- CAPTCHA -------------------------------------------------------------------------------

    def test_missing_captcha(self):
        with self.page() as page:
            self.fill(page)
            page.wait_for_selector(".fake-captcha")
            state, feedback = self.submit_and_wait(page)
            self.assertIn("Bekreft i kontrollen", feedback)
            self.assertKept(page, feedback)
            self.assertEqual(page.get_attribute("#contact-captcha", "data-invalid"), "true")
            self.assertEqual(page.posts, [])

    def test_expired_captcha_in_the_browser_and_on_the_server(self):
        with self.page() as page:
            self.fill(page)
            page.wait_for_selector(".fake-captcha")
            self.confirm(page)
            page.evaluate("window.__expire()")
            self.assertEqual(page.get_attribute("#contact-captcha", "data-state"), "expired")
            state, feedback = self.submit_and_wait(page)
            self.assertIn("Bekreft i kontrollen", feedback)
            self.assertEqual(page.posts, [], "utløpt token sendes ikke")
            self.confirm(page, "expired-token")
            state, feedback = self.submit_and_wait(page)
            self.assertIn("ble for gammel", feedback)
            self.assertKept(page, feedback)
            self.assertEqual(page.evaluate("window.__resets"), 1, "kontrollen nullstilles")
            self.confirm(page, "ok-token")
            self.assertEqual(self.submit_and_wait(page)[0], "sent")
        self.assertEqual(len(self.hotel.sent()), 1)

    def test_rejected_captcha(self):
        with self.page() as page:
            self.fill(page)
            page.focus("#contact-email")
            self.confirm(page, "bad-token")
            state, feedback = self.submit_and_wait(page)
            self.assertIn("godtok ikke", feedback)
            self.assertKept(page, feedback)
        self.assertEqual(self.hotel.sent(), [])

    def test_captcha_script_that_cannot_load(self):
        with self.page(captcha="blocked") as page:
            page.focus("#contact-email")
            page.wait_for_selector("#contact-captcha[data-state=error]")
            self.assertIn("lastet ikke", page.text_content("#contact-captcha-note"))
            self.fill(page)
            state, feedback = self.submit_and_wait(page)
            self.assertIn("lastet ikke", feedback)
            self.assertKept(page, feedback)
            self.assertEqual(page.posts, [])

    # --- sendefeil, oppsett og nett ------------------------------------------------------------

    def test_send_failure_keeps_the_text_and_a_retry_works(self):
        self.hotel.fail_sending()
        with self.page() as page:
            self.fill(page)
            page.focus("#contact-email")
            self.confirm(page)
            state, feedback = self.submit_and_wait(page)
            self.assertIn("kom ikke fram", feedback)
            self.assertKept(page, feedback)
            self.hotel.fail_sending(False)
            self.confirm(page)
            self.assertEqual(self.submit_and_wait(page)[0], "sent")
        self.assertEqual(len(self.hotel.sent()), 1)

    def test_missing_setup_lets_the_reader_write_but_not_send(self):
        self.hotel.write_config(None)
        with self.page() as page:
            page.wait_for_selector("#contact-captcha[data-state=unavailable]")
            self.fill(page)
            state, feedback = self.submit_and_wait(page)
            self.assertIn("kan ikke sende meldinger akkurat nå", feedback)
            self.assertKept(page, feedback)
            self.assertEqual(page.posts, [])
            self.assertEqual(page.locator(".fake-captcha").count(), 0, "ingen ekstern kontroll lastes uten oppsett")

    def test_rate_limit_message(self):
        self.hotel.write_config({**self.config, "rate_limit": {"window": 600, "per_client": 1, "per_day": 40}})
        with self.page() as page:
            self.fill(page)
            page.focus("#contact-email")
            self.confirm(page)
            self.assertEqual(self.submit_and_wait(page)[0], "sent")
            self.fill(page)
            self.confirm(page)
            state, feedback = self.submit_and_wait(page)
            self.assertIn("mange meldinger", feedback)
            self.assertKept(page, feedback)

    def test_network_failure_keeps_the_text(self):
        with self.page() as page:
            page.route("**/api/kontakt.php", lambda route: route.abort() if route.request.method == "POST" else route.continue_())
            self.fill(page)
            page.focus("#contact-email")
            self.confirm(page)
            state, feedback = self.submit_and_wait(page)
            self.assertIn("fikk ikke kontakt", feedback)
            self.assertKept(page, feedback)
            self.assertFalse(page.is_disabled("#contact-submit"))

    def test_text_survives_a_reload(self):
        with self.page() as page:
            self.fill(page)
            page.reload(wait_until="networkidle")
            self.assertEqual(page.input_value("#contact-email"), EMAIL)
            self.assertEqual(page.input_value("#contact-message"), TEXT)

    def test_only_the_public_site_key_reaches_the_browser(self):
        with self.page() as page:
            page.focus("#contact-email")
            page.wait_for_selector(".fake-captcha")
            html = page.content() + page.evaluate("JSON.stringify(window.turnstile.widgets.map(w => w.opts.sitekey))")
            self.assertIn(h.FAKE_SITE_KEY, html)
            for value in h.SERVER_ONLY_VALUES:
                self.assertNotIn(value, html)


if __name__ == "__main__":
    unittest.main()
