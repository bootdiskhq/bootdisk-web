"""Nettleserkontroller for besøkstelleren i den offentlige bunnteksten.

En release bygd av syntetiske data serveres av PHPs innebygde server sammen med den foreslåtte
tellertjenesten (tests/visit_counter_router.php), mot en midlertidig SQLite-fil. Den pakkede
visit-counter-config.js er avslått; testene erstatter den i nettleseren med en konfigurasjon som
peker på den lokale testtjenesten. Hver side registrerer alle forespørsler, og en forespørsel til
bootdisk.no får testen til å feile.

Hoppes over uten Playwright, Chromium eller PHP (som på CI). Kjør lokalt med:

    pip install playwright && playwright install chromium
    python -m unittest tests.test_visit_counter_browser -v

CURATOR_CHROMIUM kan peke på en Chromium-binær.
"""
from __future__ import annotations

import contextlib
import datetime
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import synthetic_collection as synthetic  # noqa: E402
from test_visit_counter import BACKEND, PHP, ROUTER, free_port, init_db, php_server, total_in  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment dependent
    sync_playwright = None

OSLO = datetime.timezone(datetime.timedelta(hours=2))
T0 = datetime.datetime(2026, 9, 25, 12, 0, tzinfo=OSLO)
MINUTE = datetime.timedelta(minutes=1)
PAGES = ("/", "/collection.html?collection=komputer-for-alle", "/archive.html", "/index.html?entry=K37")


@unittest.skipUnless(sync_playwright and PHP, "Playwright og PHP er nødvendig for nettleserkontrollene")
class VisitCounterBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stack = contextlib.ExitStack()
        work = Path(cls._stack.enter_context(tempfile.TemporaryDirectory()))
        data, publish = synthetic.build_synthetic(work / "seven")
        release = work / "release"
        result = synthetic.package(data, publish, release)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.db = work / "besok.sqlite"
        port = free_port()
        cls.base = f"http://127.0.0.1:{port}"
        cls._stack.enter_context(php_server(router=ROUTER, docroot=release, port=port, workers=4, env={
            "BOOTDISK_COUNTER_SCRIPT": str(BACKEND), "BOOTDISK_COUNTER_DB": str(cls.db),
            "BOOTDISK_COUNTER_ORIGIN": cls.base}))
        cls.test_config = ("window.BOOTDISK_VISIT_COUNTER = Object.freeze("
                           + json.dumps({"origin": cls.base, "endpoint": "api/besok.php"}) + ");")
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
        if self.db.exists():
            self.db.unlink()
        init_db(self.db, since="2026-09-25")

    def set_total(self, total):
        with contextlib.closing(sqlite3.connect(self.db)) as connection:
            connection.execute("UPDATE counter SET total = ?", (total,))
            connection.commit()

    @contextlib.contextmanager
    def context(self, configured=True, width=1280, height=900, **options):
        context = self.browser.new_context(viewport={"width": width, "height": height}, **options)
        context.requests, context.failures, context.production = [], [], []
        context.on("request", lambda request: context.requests.append((request.method, request.url, request.post_data)))
        context.route("**/*", lambda route: (context.production.append(route.request.url), route.abort())
                      if not route.request.url.startswith(self.base) else route.fallback())
        if configured:
            context.route(f"{self.base}/visit-counter-config.js",
                          lambda route: route.fulfill(body=self.test_config, content_type="text/javascript"))
        context.clock.set_fixed_time(T0)
        try:
            yield context
            self.assertEqual(context.failures, [], "siden kastet en skriptfeil")
            self.assertEqual(context.production, [], "ingen forespørsler utenfor testserveren")
        finally:
            context.close()

    def open(self, context, path, page=None, state="ready"):
        page = page or context.new_page()
        if not hasattr(page, "_watched"):
            page.on("pageerror", lambda error: context.failures.append(str(error)))
            page._watched = True
        page.goto(self.base + path, wait_until="load")
        if state:
            page.wait_for_selector(f"#visit-counter[data-state={state}]")
        return page

    def shown(self, page):
        return page.eval_on_selector("#visit-counter", """root => ({
            digits: Array.from(root.querySelectorAll('.visit-counter-digit'), cell => cell.textContent).join(''),
            caption: root.querySelector('.visit-counter-caption')?.textContent ?? null,
            label: root.querySelector('.visit-counter-text')?.textContent ?? null,
            text: root.textContent })""")

    def posts(self, context):
        return [body for method, url, body in context.requests if method == "POST" and url.endswith("/api/besok.php")]

    def test_packaged_config_is_off_and_makes_no_counter_request(self):
        with self.context(configured=False) as context:
            for path in PAGES:
                page = self.open(context, path, state=None)
                page.wait_for_load_state("networkidle")
                self.assertTrue(page.eval_on_selector("#visit-counter", "root => root.hidden && !root.offsetHeight"), path)
                page.close()
            self.assertFalse([url for _, url, _ in context.requests if "besok" in url])
        self.assertEqual(total_in(self.db), 0)

    def test_an_activated_production_config_stays_silent_outside_bootdisk_no(self):
        """Lokal utvikling og forhåndsvisninger av en aktivert release teller aldri mot produksjon."""
        activated = 'window.BOOTDISK_VISIT_COUNTER = Object.freeze({ origin: "https://bootdisk.no", endpoint: "https://bootdisk.no/api/besok.php" });'
        with self.context(configured=False) as context:
            context.route(f"{self.base}/visit-counter-config.js", lambda route: route.fulfill(body=activated, content_type="text/javascript"))
            for path in PAGES:
                page = self.open(context, path, state=None)
                page.wait_for_load_state("networkidle")
                self.assertTrue(page.eval_on_selector("#visit-counter", "root => root.hidden && !root.offsetHeight"), path)
                page.close()
            self.assertFalse([url for _, url, _ in context.requests if "besok" in url])

    def test_one_visit_counts_once_across_front_collection_archive_detail_and_reload(self):
        with self.context() as context:
            page = None
            for path in PAGES:
                page = self.open(context, path, page)
                shown = self.shown(page)
                self.assertEqual(shown["digits"], "000001", path)
                self.assertEqual(shown["caption"], "Besøk siden 25.09.2026")
                self.assertEqual(shown["label"], "1 besøk siden 25. september 2026")
            page.reload()
            page.wait_for_selector("#visit-counter[data-state=ready]")
            self.assertEqual(self.shown(page)["digits"], "000001")
            self.assertEqual(len(self.posts(context)), 1)
        self.assertEqual(total_in(self.db), 1)

    def test_a_new_visit_counts_only_after_thirty_idle_minutes(self):
        with self.context() as context:
            page = self.open(context, "/")
            context.clock.set_fixed_time(T0 + 29 * MINUTE)
            self.open(context, "/archive.html", page)
            self.assertEqual(self.shown(page)["digits"], "000001")
            context.clock.set_fixed_time(T0 + 29 * MINUTE + 30 * MINUTE)
            self.open(context, "/archive.html", page)
            self.assertEqual(self.shown(page)["digits"], "000001", "nøyaktig 30 minutter er samme besøk")
            context.clock.set_fixed_time(T0 + 59 * MINUTE + 30 * MINUTE + datetime.timedelta(seconds=1))
            self.open(context, "/archive.html", page)
            self.assertEqual(self.shown(page)["digits"], "000002")
            keys = [json.loads(body)["visit"] for body in self.posts(context)]
            self.assertEqual(len(set(keys)), 2)
        self.assertEqual(total_in(self.db), 2)

    def test_parallel_tabs_opened_together_count_one_visit(self):
        with self.context() as context:
            pages = [context.new_page() for _ in range(4)]
            for page, path in zip(pages, PAGES):
                page.on("pageerror", lambda error: context.failures.append(str(error)))
                page.evaluate(f"location.href = {json.dumps(self.base + path)}")
            for page in pages:
                page.wait_for_selector("#visit-counter[data-state=ready]")
            self.assertEqual(len({json.loads(body)["visit"] for body in self.posts(context)}), 1)
        self.assertEqual(total_in(self.db), 1)

    def test_lost_response_shows_unavailable_and_the_reload_resends_the_same_key(self):
        with self.context() as context:
            page = context.new_page()
            lost = []

            def lose_first_answer(route):
                if route.request.method == "POST" and not lost:
                    route.fetch()  # tjenesten teller, men svaret når aldri siden
                    lost.append(route.request.post_data)
                    route.abort("timedout")
                else:
                    route.fallback()
            page.route(f"{self.base}/api/besok.php", lose_first_answer)
            self.open(context, "/", page, state="unavailable")
            self.assertEqual(self.shown(page)["text"], "Teller utilgjengelig")
            self.assertEqual(total_in(self.db), 1)
            page.reload()
            page.wait_for_selector("#visit-counter[data-state=ready]")
            self.assertEqual(self.shown(page)["digits"], "000001")
            posts = self.posts(context)
            self.assertEqual(len(posts), 2)
            self.assertEqual(posts[0], posts[1])
        self.assertEqual(total_in(self.db), 1)

    def test_failures_show_unavailable_while_the_archive_keeps_working(self):
        failures = {
            "nettverk": lambda route: route.abort("failed"),
            "503": lambda route: route.fulfill(status=503, body='{"error":"unavailable"}', content_type="application/json"),
            "ikke JSON": lambda route: route.fulfill(body="<html>feil</html>", content_type="text/html"),
            "negativ": lambda route: route.fulfill(body='{"total":-1,"since":"2026-09-25","counted":true}', content_type="application/json"),
            "tekst": lambda route: route.fulfill(body='{"total":"12","since":"2026-09-25","counted":true}', content_type="application/json"),
            "uten dato": lambda route: route.fulfill(body='{"total":12,"counted":true}', content_type="application/json"),
        }
        for name, handler in failures.items():
            with self.subTest(name), self.context() as context:
                page = context.new_page()
                page.route(f"{self.base}/api/besok.php", handler)
                self.open(context, "/archive.html", page, state="unavailable")
                page.wait_for_selector(".archive-card")
                self.assertGreater(page.locator(".archive-card").count(), 0)
                shown = self.shown(page)
                self.assertEqual(shown["text"], "Teller utilgjengelig")
                self.assertEqual(shown["digits"], "", "ingen sifre, heller ikke nuller")

    def test_missing_database_is_unavailable_not_zero(self):
        self.db.unlink()
        with self.context() as context:
            page = self.open(context, "/", state="unavailable")
            self.assertEqual(self.shown(page)["text"], "Teller utilgjengelig")
        self.assertFalse(self.db.exists())

    def test_blocked_storage_shows_the_total_without_counting(self):
        self.set_total(41)
        blocked = "Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('blokkert', 'SecurityError'); } });"
        with self.context() as context:
            context.add_init_script(blocked)
            page = None
            for path in PAGES:
                page = self.open(context, path, page)
                self.assertEqual(self.shown(page)["digits"], "000041")
            self.assertEqual(self.posts(context), [])
        self.assertEqual(total_in(self.db), 41)

    def test_large_totals_grow_without_overlap_or_clipping_on_narrow_screens(self):
        for width in (320, 360, 1280):
            self.set_total(123456788)  # hver bredde er en ny nettleser og dermed et nytt besøk
            with self.subTest(width=width), self.context(width=width, height=740) as context:
                page = self.open(context, "/index.html?entry=K37")
                self.assertEqual(self.shown(page)["digits"], "123456789")
                geometry = page.evaluate("""() => {
                    const cells = Array.from(document.querySelectorAll('.visit-counter-digit'), cell => cell.getBoundingClientRect());
                    const root = document.getElementById('visit-counter').getBoundingClientRect();
                    return { cells: cells.map(r => [r.left, r.right, r.top, r.bottom]), root: [root.left, root.right],
                             scroll: document.documentElement.scrollWidth, width: window.innerWidth,
                             clipped: Array.from(document.querySelectorAll('.visit-counter-digit')).some(c => c.scrollWidth > c.clientWidth) };
                }""")
                self.assertLessEqual(geometry["scroll"], geometry["width"], "ingen horisontal rulling")
                self.assertFalse(geometry["clipped"])
                cells = geometry["cells"]
                for left, right in zip(cells, cells[1:]):
                    self.assertLessEqual(left[1], right[0] + 0.5, "sifferfeltene overlapper ikke")
                    self.assertEqual(left[2], right[2], "sifrene holder seg på én linje")
                self.assertGreaterEqual(cells[0][0], 0)
                self.assertLessEqual(cells[-1][1], geometry["width"])

    def test_counter_reserves_its_space_so_nothing_moves_when_the_total_arrives(self):
        with self.context() as context:
            page = context.new_page()
            held = []
            page.route(f"{self.base}/api/besok.php", lambda route: held.append(route))
            self.open(context, "/archive.html", page, state="pending")
            page.wait_for_selector(".archive-card")
            measure = """() => { const root = document.getElementById('visit-counter').getBoundingClientRect();
                const footer = document.querySelector('footer').getBoundingClientRect();
                const main = document.querySelector('main').getBoundingClientRect();
                return { height: root.height, top: root.top + scrollY, footer: footer.top + scrollY, footerHeight: footer.height, main: main.bottom + scrollY }; }"""
            before = page.evaluate(measure)
            self.assertEqual(self.shown(page)["digits"].strip(), "")
            self.assertEqual(len(self.shown(page)["digits"]), 6)
            while not held:
                page.wait_for_timeout(20)
            held[0].fallback()
            page.wait_for_selector("#visit-counter[data-state=ready]")
            self.assertEqual(page.evaluate(measure), before)

        with self.context() as context:
            page = context.new_page()
            page.route(f"{self.base}/api/besok.php", lambda route: route.abort("failed"))
            self.open(context, "/archive.html", page, state="unavailable")
            page.wait_for_selector(".archive-card")
            self.assertEqual(page.evaluate(measure)["footerHeight"], before["footerHeight"], "feiltilstanden har samme høyde")

    def test_screen_readers_get_one_label_and_the_counter_is_quiet_and_still(self):
        self.set_total(1233)
        with self.context(reduced_motion="no-preference") as context:
            page = self.open(context, "/")
            facts = page.eval_on_selector("#visit-counter", """root => ({
                hidden: Array.from(root.children, child => [child.className, child.getAttribute('aria-hidden')]),
                live: root.closest('[aria-live],[role=status],[role=alert]') !== null || root.querySelector('[aria-live],[role]') !== null,
                focusable: root.querySelectorAll('a,button,input,[tabindex]').length,
                animation: Array.from(root.querySelectorAll('*'), el => getComputedStyle(el).animationName).filter(n => n !== 'none'),
                transition: Array.from(root.querySelectorAll('*'), el => getComputedStyle(el).transitionDuration).filter(d => d !== '0s') })""")
            self.assertEqual(facts["hidden"], [["visit-counter-digits", "true"], ["visit-counter-caption", "true"], ["visit-counter-text", None]])
            self.assertFalse(facts["live"], "totalen leses ikke opp av seg selv")
            self.assertEqual(facts["focusable"], 0)
            self.assertEqual(facts["animation"], [])
            self.assertEqual(facts["transition"], [])
            snapshot = page.locator("footer").aria_snapshot()
            self.assertIn("1 234 besøk siden 25. september 2026", snapshot.replace(" ", " "))
            self.assertNotIn("0 0 1 2", snapshot)
            # Tastaturet går forbi telleren: siste fokus i siden er ikke inne i bunnteksten.
            for _ in range(80):
                page.keyboard.press("Tab")
                self.assertFalse(page.evaluate("document.activeElement.closest('#visit-counter') !== null"))


if __name__ == "__main__":
    unittest.main()
