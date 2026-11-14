"""Kontaktskjemaet: kjerne, PHP-mottak, pakke og lekkasjekontroll (docs/kontaktskjema.md).

Simulert, ikke ekte: CAPTCHA-leverandøren (lokal falsk siteverify), e-postutsending (falsk
sendmail for mail(), lokal SMTP-server med selvsignert STARTTLS) og webhotellet (php -S med
home/www og home/bootdisk-privat). Alle adresser, nøkler og passord er oppdiktede. Ingen test
sender ekte e-post eller snakker med en ekte CAPTCHA-leverandør eller med bootdisk.no.

Uten Node eller PHP hoppes de aktuelle klassene over, og det er ikke bestått.
"""
from __future__ import annotations

import base64
import contextlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import contact_harness as h  # noqa: E402

NODE = shutil.which("node")
CHECKER = ROOT / "scripts" / "check-private-config.py"
MESSAGE = "Hei! Jeg har Komputer for alle CD 3/1999.\nSe https://bootdisk.no/index.html?entry=K37 – æøå."
READER = "leser@eksempel.invalid"


def node(script: str) -> None:
    prelude = (
        "const assert = require('node:assert/strict');\n"
        f"const core = require({str(ROOT / 'contact-core.js')!r});\n"
    )
    result = subprocess.run([NODE, "-e", prelude + script + "\nconsole.log('NODE-FERDIG');"], capture_output=True, text=True, cwd=ROOT)
    if result.returncode or "NODE-FERDIG" not in result.stdout:
        raise AssertionError(result.stderr or result.stdout)


@unittest.skipUnless(NODE, "Node er nødvendig for kjernetestene")
class ContactCoreTests(unittest.TestCase):
    def test_email_rules_match_what_the_server_accepts(self):
        node("""
for (const ok of ['a@b.no', 'navn.etternavn@eksempel.invalid', 'x+tag@sub.domene.no']) assert.ok(core.contactValidEmail(ok), ok);
for (const bad of ['', 'a', 'a@', '@b.no', 'a@b', 'a b@c.no', 'a@b.no\\nBcc: c@d.no', 'a@b.no,c@d.no', '<a@b.no>', 'a..b@c.no', '.a@b.no', 'x'.repeat(250) + '@b.no'])
  assert.equal(core.contactValidEmail(bad), false, JSON.stringify(bad));
""")

    def test_check_names_the_first_problem_in_field_order(self):
        node("""
assert.equal(core.contactCheck({ email: 'nei', message: '', captcha: '' }), 'invalid_email');
assert.equal(core.contactCheck({ email: 'a@b.no', message: '   ', captcha: '' }), 'invalid_message');
assert.equal(core.contactCheck({ email: 'a@b.no', message: 'x'.repeat(4001), captcha: 't' }), 'message_too_long');
assert.equal(core.contactCheck({ email: 'a@b.no', message: 'æ'.repeat(4000), captcha: 't' }), null, 'tegn, ikke byte');
assert.equal(core.contactCheck({ email: 'a@b.no', message: 'hei', captcha: '' }), 'captcha_missing');
assert.equal(core.contactCheck({ email: ' a@b.no ', message: ' hei ', captcha: 't' }), null);
assert.deepEqual(core.contactPayload({ email: ' a@b.no ', message: ' hei ', captcha: 't' }), { email: 'a@b.no', message: 'hei', captcha: 't', website: '' });
""")

    def test_only_an_explicit_ok_is_success_and_unknown_codes_are_generic(self):
        node("""
assert.deepEqual(core.contactResult(200, { ok: true }), { ok: true });
assert.deepEqual(core.contactResult(200, { ok: 'yes' }), { ok: false, error: 'unknown' });
assert.deepEqual(core.contactResult(200, null), { ok: false, error: 'unknown' });
assert.deepEqual(core.contactResult(500, { ok: true }), { ok: false, error: 'unknown' });
assert.deepEqual(core.contactResult(403, { ok: false, error: 'captcha_expired' }), { ok: false, error: 'captcha_expired' });
assert.deepEqual(core.contactResult(400, { ok: false, error: 'toString' }), { ok: false, error: 'unknown' });
""")

    def test_every_error_tells_the_reader_that_the_text_is_kept(self):
        node("""
for (const code of Object.keys(core.CONTACT_MESSAGES)) assert.match(core.contactText(code), /Teksten din står fortsatt i skjemaet\\./, code);
assert.equal(core.contactText('finnes-ikke'), core.contactText('unknown'));
""")

    def test_captcha_script_comes_from_a_fixed_list_never_from_the_server(self):
        node("""
assert.deepEqual(core.contactSetup({ ready: false }), { ready: false });
assert.deepEqual(core.contactSetup({ ready: true, provider: 'evil', site_key: 'k' }), { ready: false });
assert.deepEqual(core.contactSetup({ ready: true, provider: 'turnstile', site_key: '' }), { ready: false });
const setup = core.contactSetup({ ready: true, provider: 'hcaptcha', site_key: 'k', script: 'https://evil.invalid/x.js' });
assert.equal(setup.script, core.CONTACT_CAPTCHA_SCRIPTS.hcaptcha);
for (const url of Object.values(core.CONTACT_CAPTCHA_SCRIPTS)) assert.match(url, /^https:\\/\\/(challenges\\.cloudflare\\.com|js\\.hcaptcha\\.com)\\//);
""")

    def test_server_and_browser_agree_on_limits_and_error_codes(self):
        php = (ROOT / "api/kontakt.php").read_text(encoding="utf-8")
        core = (ROOT / "contact-core.js").read_text(encoding="utf-8")
        self.assertEqual(re.search(r"const MAX_MESSAGE_CHARS = (\d+);", php).group(1), re.search(r"const CONTACT_MAX_MESSAGE = (\d+);", core).group(1))
        server_codes = set(re.findall(r"fail\(\d+, '([a-z_]+)'", php)) | set(re.findall(r"return '(captcha_[a-z]+)'", php))
        browser_codes = set(re.findall(r"^  ([a-z_]+): ", core.split("CONTACT_MESSAGES = {")[1].split("};")[0], re.M))
        self.assertTrue(server_codes, "fant ingen feilkoder i api/kontakt.php")
        self.assertLessEqual(server_codes, browser_codes, "hver feilkode fra serveren har en norsk tekst")


class ContactMarkupTests(unittest.TestCase):
    PUBLIC = ("index.html", "archive.html", "collection.html", "updates.html", "om-prosjektet.html", "404.html")

    def read(self, name):
        return (ROOT / name).read_text(encoding="utf-8")

    def test_about_comes_right_after_latest_changes_on_every_public_page(self):
        for name in self.PUBLIC:
            with self.subTest(name):
                nav = re.search(r'<nav class="site-nav" aria-label="Hovedmeny">(.*?)</nav>', self.read(name)).group(1)
                labels = re.findall(r">([^<>]+)</a>", nav)
                self.assertEqual(labels, ["Forside", "Samlinger", "Alle kildeposter", "Siste endringer", "Om prosjektet"])
                self.assertIn('<a href="om-prosjektet.html"', nav)
                current = re.findall(r'<a href="([^"]+)" aria-current="page">', nav)
                self.assertEqual(current, ["om-prosjektet.html"] if name == "om-prosjektet.html" else current)

    def test_source_entries_share_the_front_page_header(self):
        # Kildepostene er index.html?entry=…; overskriften er statisk og skjules aldri i entry-view.
        css = self.read("publication.css") + self.read("catalog.css")
        self.assertNotRegex(css, r"\.entry-view\s+\.site-(header|nav)")

    def test_page_text_covers_the_order(self):
        text = re.sub(r"<[^>]+>", " ", self.read("om-prosjektet.html"))
        for phrase in ("CD-menyene", "Skjermbildene", "Omtalene", "Kursene", "Kontakt oss", "E-postadressen din", "Melding",
                       "lenken", "kildepost", "rettelse"):
            self.assertIn(phrase, text)
        self.assertLess(text.index("Har du en plate"), text.index("Kontakt oss"), "skjemaet står under teksten")

    def test_form_fields_are_labelled_and_the_trap_is_out_of_reach(self):
        html = self.read("om-prosjektet.html")
        for field in ("contact-email", "contact-message", "contact-website"):
            self.assertIn(f'<label for="{field}">', html)
        self.assertRegex(html, r'id="contact-email"[^>]*type="email"[^>]*autocomplete="email"')
        self.assertRegex(html, r'<div class="contact-trap" aria-hidden="true">.*tabindex="-1"')

    def test_no_real_or_private_values_in_versioned_files(self):
        tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True).stdout.split()
        for name in tracked + ["api/kontakt.php", "om-prosjektet.html", "contact.js", "contact-core.js", "docs/kontaktskjema.md"]:
            path = ROOT / name
            if not path.is_file() or path.suffix in (".png", ".jpg", ".zip", ".pdf", ".iso"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            with self.subTest(name):
                # Ekte mottaker på domenet står aldri i repositoryet; bare example.invalid og oppdiktede testverdier.
                self.assertNotRegex(text, r"[A-Za-z0-9._%+-]+@bootdisk\.no", "e-postadresse på bootdisk.no i versjonert fil")

    def test_example_config_uses_only_placeholders(self):
        text = self.read("docs/examples/kontakt-config.example.php")
        addresses = set(re.findall(r"[\w.+-]+@[\w.-]+", text))
        self.assertTrue(addresses)
        self.assertTrue(all(a.endswith(".invalid") for a in addresses), addresses)
        self.assertIn("plassholder", text)

    def test_private_config_is_ignored_by_git(self):
        for name in ("kontakt-config.php", "bootdisk-privat/kontakt-config.php", "api/kontakt-config.php"):
            result = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", name])
            self.assertEqual(result.returncode, 0, f"{name} er ikke ignorert")
        self.assertNotEqual(subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "api/kontakt.php"]).returncode, 0)


@unittest.skipUnless(h.PHP, "PHP er nødvendig for tjenestetestene")
class ContactServiceTests(unittest.TestCase):
    def setUp(self):
        self._stack = contextlib.ExitStack()
        self.work = Path(self._stack.enter_context(tempfile.TemporaryDirectory()))
        self.verifier = h.Verifier()
        self._stack.callback(self.verifier.close)
        self.hotel = h.Webhotel(self.work)
        self._stack.callback(self.hotel.stop)
        self.config = h.base_config(self.hotel.state, self.verifier, self.hotel.origin)

    def tearDown(self):
        self._stack.close()

    def start(self, config="default", env=None):
        self.hotel.write_config(self.config if config == "default" else config)
        return self.hotel.start(env)

    def post(self, body=None, **overrides):
        payload = {"email": READER, "message": MESSAGE, "captcha": "ok-token", "website": ""}
        payload.update(body or {})
        kwargs = {"origin": self.hotel.origin}
        kwargs.update(overrides)
        return h.call(self.hotel.url + "/api/kontakt.php", "POST", payload, **kwargs)

    def assertNothingSent(self):
        self.assertEqual(self.hotel.sent(), [])

    # --- oppsett -------------------------------------------------------------------------

    def test_get_reports_public_setup_only(self):
        self.start()
        status, body, headers, raw = h.call(self.hotel.url + "/api/kontakt.php")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ready": True, "provider": "turnstile", "site_key": h.FAKE_SITE_KEY, "max_message": 4000})
        self.assertEqual(headers["Cache-Control"], "no-store")
        for value in h.SERVER_ONLY_VALUES:
            self.assertNotIn(value.encode(), raw)

    def test_missing_config_is_not_ready_and_refuses_to_send(self):
        self.start(config=None)
        self.assertEqual(h.call(self.hotel.url + "/api/kontakt.php")[1], {"ready": False})
        status, body, _, _ = self.post()
        self.assertEqual((status, body), (503, {"ok": False, "error": "not_configured"}))
        self.assertEqual(self.verifier.calls, [], "ingen CAPTCHA-kontroll uten oppsett")
        self.assertNothingSent()

    def test_incomplete_config_is_refused(self):
        broken = [
            ("recipient",), ("sender",), ("client_salt",), ("allowed_origin",), ("state_dir",),
            ("captcha", "secret"), ("captcha", "site_key"), ("captcha", "provider"), ("transport",),
        ]
        for path in broken:
            with self.subTest(path):
                config = json.loads(json.dumps(self.config))
                target = config
                for key in path[:-1]:
                    target = target[key]
                del target[path[-1]]
                self.hotel.write_config(config)
                self.hotel.start()
                try:
                    self.assertEqual(h.call(self.hotel.url + "/api/kontakt.php")[1], {"ready": False})
                    self.assertEqual(self.post()[0], 503)
                finally:
                    self.hotel.stop()
        self.assertNothingSent()

    def test_bad_values_in_config_are_refused(self):
        cases = {
            "recipient with header": {"recipient": h.FAKE_RECIPIENT + "\r\nBcc: x@y.invalid"},
            "short salt": {"client_salt": "kort"},
            "unknown provider": {"captcha": {**self.config["captcha"], "provider": "egen"}},
            "origin with path": {"allowed_origin": self.hotel.origin + "/"},
            "missing state dir": {"state_dir": str(self.work / "finnes-ikke")},
            "cleartext smtp login": {"transport": {"type": "smtp", "host": "127.0.0.1", "security": "none", "username": "u", "password": "p"}},
        }
        for label, change in cases.items():
            with self.subTest(label):
                self.hotel.write_config({**self.config, **change})
                self.hotel.start()
                try:
                    self.assertEqual(h.call(self.hotel.url + "/api/kontakt.php")[1], {"ready": False})
                finally:
                    self.hotel.stop()

    def test_config_or_state_inside_the_web_root_is_never_used(self):
        inside = self.hotel.www / "kontakt-config.php"
        self.hotel.write_config(self.config, inside)
        self.hotel.start(env={"BOOTDISK_CONTACT_CONFIG": str(inside)})
        try:
            self.assertEqual(h.call(self.hotel.url + "/api/kontakt.php")[1], {"ready": False})
            self.assertEqual(self.post()[0], 503)
        finally:
            self.hotel.stop()
        state = self.hotel.www / "tilstand"
        state.mkdir()
        self.hotel.write_config({**self.config, "state_dir": str(state)})
        self.hotel.start()
        self.assertEqual(h.call(self.hotel.url + "/api/kontakt.php")[1], {"ready": False})
        self.assertIn("webroten", self.hotel.error_log())

    def test_default_config_path_is_beside_the_web_root(self):
        source = (ROOT / "api/kontakt.php").read_text(encoding="utf-8")
        self.assertIn("dirname(__DIR__, 2) . '/bootdisk-privat/kontakt-config.php'", source)
        self.start()  # home/www/api/kontakt.php -> home/bootdisk-privat/kontakt-config.php, ingen miljøvariabel
        self.assertTrue(h.call(self.hotel.url + "/api/kontakt.php")[1]["ready"])

    # --- gyldig innsending -----------------------------------------------------------------

    def test_valid_submission_sends_one_mail_with_fixed_sender_and_validated_reply_to(self):
        self.start()
        status, body, _, _ = self.post()
        self.assertEqual((status, body), (200, {"ok": True}))
        self.assertEqual(len(self.verifier.calls), 1)
        self.assertEqual(self.verifier.calls[0]["secret"], h.FAKE_SECRET)
        self.assertEqual(self.verifier.calls[0]["response"], "ok-token")
        [mail] = self.hotel.sent()
        message = mail["message"]
        self.assertEqual(message["To"], h.FAKE_RECIPIENT)
        self.assertEqual(message["Reply-To"], READER)
        self.assertEqual(message["From"].addresses[0].addr_spec, h.FAKE_SENDER)
        self.assertEqual(str(message["Subject"]), "Melding fra kontaktskjemaet på Bootdisk")
        self.assertIsNone(message["Cc"])
        self.assertIsNone(message["Bcc"])
        self.assertIn("-f" + h.FAKE_SENDER, mail["args"], "fast konvoluttavsender")
        text = message.get_content()
        self.assertIn(MESSAGE, text)
        self.assertIn(READER, text)

    def test_state_file_holds_no_address_or_text(self):
        self.start()
        self.post()
        state = (self.hotel.state / "kontakt-grenser.json").read_text()
        for value in ("127.0.0.1", READER, "Komputer", h.FAKE_SALT):
            self.assertNotIn(value, state)

    def test_honeypot_answers_like_success_but_sends_nothing(self):
        self.start()
        self.assertEqual(self.post({"website": "http://spam.invalid"})[:2], (200, {"ok": True}))
        self.assertNothingSent()

    # --- adressefeil og felter ---------------------------------------------------------------

    def test_invalid_reply_address_is_refused_before_captcha(self):
        self.start()
        for bad in ("", "ikke-en-adresse", "a@b.no\r\nBcc: offer@eksempel.invalid", "a@b.no, c@d.invalid", "<a@b.invalid>",
                    "x" * 250 + "@b.invalid", 42):
            with self.subTest(bad=bad):
                status, body, _, _ = self.post({"email": bad})
                self.assertEqual((status, body), (422, {"ok": False, "error": "invalid_email"}))
        self.assertEqual(self.verifier.calls, [])
        self.assertNothingSent()

    def test_empty_or_too_long_message_is_refused(self):
        self.start()
        self.assertEqual(self.post({"message": "   "})[1]["error"], "invalid_message")
        self.assertEqual(self.post({"message": "æ" * 4001})[1]["error"], "message_too_long")
        self.assertEqual(self.verifier.calls, [])
        self.assertNothingSent()

    def test_requests_that_are_not_the_form_are_refused(self):
        self.start()
        url = self.hotel.url + "/api/kontakt.php"
        self.assertEqual(self.post(origin="https://elsewhere.invalid")[:2], (403, {"ok": False, "error": "forbidden_origin"}))
        self.assertEqual(self.post(origin=None)[0], 403)
        self.assertEqual(h.call(url, "POST", b"email=a", origin=self.hotel.origin, content_type="application/x-www-form-urlencoded")[0], 415)
        self.assertEqual(h.call(url, "POST", b"{nei", origin=self.hotel.origin)[0], 400)
        self.assertEqual(h.call(url, "POST", b"x" * 70000, origin=self.hotel.origin)[0], 413)
        self.assertEqual(h.call(url, "PUT", b"{}", origin=self.hotel.origin)[0], 405)
        self.assertNothingSent()

    # --- CAPTCHA ----------------------------------------------------------------------------

    def test_captcha_outcomes(self):
        self.start()
        cases = {
            "": (422, "captcha_missing"),
            "expired-token": (403, "captcha_expired"),
            "seen-token": (403, "captcha_expired"),
            "bad-token": (403, "captcha_rejected"),
            "wrong-host-token": (200, None),
            "fault-token": (503, "captcha_unavailable"),
        }
        for token, (status, code) in cases.items():
            with self.subTest(token=token):
                result = self.post({"captcha": token}, origin=self.hotel.origin)
                self.assertEqual(result[0], status)
                if code:
                    self.assertEqual(result[1], {"ok": False, "error": code})
                time.sleep(0.01)
            if len(self.verifier.calls) >= 2:
                # Hyppighetsgrensen er 3; nullstill tilstanden mellom tilfellene.
                (self.hotel.state / "kontakt-grenser.json").unlink(missing_ok=True)
        self.assertEqual(len(self.hotel.sent()), 1, "bare den godkjente sendes")

    def test_expected_hostname_is_enforced_when_configured(self):
        self.config["captcha"]["hostname"] = "127.0.0.1"
        self.start()
        self.assertEqual(self.post({"captcha": "wrong-host-token"})[1], {"ok": False, "error": "captcha_rejected"})
        self.assertEqual(self.post({"captcha": "ok-token"})[1], {"ok": True})
        self.assertEqual(len(self.hotel.sent()), 1)

    def test_captcha_provider_down_or_secret_wrong_is_unavailable(self):
        self.verifier.down = True
        self.start()
        self.assertEqual(self.post()[:2], (503, {"ok": False, "error": "captcha_unavailable"}))
        self.verifier.down = False
        self.hotel.stop()
        self.config["captcha"]["secret"] = "feil-hemmelighet"
        self.start()
        self.assertEqual(self.post()[:2], (503, {"ok": False, "error": "captcha_unavailable"}))
        self.assertNothingSent()
        log = self.hotel.error_log()
        self.assertNotIn("feil-hemmelighet", log)
        self.assertNotIn("ok-token", log)

    # --- sendefeil og grenser ----------------------------------------------------------------

    def test_send_failure_is_reported(self):
        self.start()
        self.hotel.fail_sending()
        self.assertEqual(self.post()[:2], (502, {"ok": False, "error": "send_failed"}))
        log = self.hotel.error_log()
        self.assertIn("sending feilet", log)
        for value in (READER, "Komputer", h.FAKE_RECIPIENT):
            self.assertNotIn(value, log, "loggen har ikke innhold eller adresser")

    def test_frequent_submissions_are_limited_per_client(self):
        self.config["rate_limit"] = {"window": 3, "per_client": 2, "per_day": 40}
        self.start()
        self.assertEqual(self.post()[0], 200)
        self.assertEqual(self.post({"captcha": "bad-token"})[0], 403, "avviste forsøk teller også")
        status, body, headers, _ = self.post()
        self.assertEqual((status, body), (429, {"ok": False, "error": "rate_limited"}))
        self.assertTrue(1 <= int(headers["Retry-After"]) <= 3)
        self.assertEqual(len(self.verifier.calls), 2, "ingen CAPTCHA-kontroll når grensen er nådd")
        time.sleep(3.2)
        self.assertEqual(self.post()[0], 200)
        self.assertEqual(len(self.hotel.sent()), 2)

    def test_daily_total_is_limited(self):
        self.config["rate_limit"] = {"window": 600, "per_client": 10, "per_day": 2}
        self.start()
        self.assertEqual([self.post()[0] for _ in range(3)], [200, 200, 429])

    def test_unwritable_state_refuses_to_send(self):
        self.start()
        (self.hotel.state / "kontakt-grenser.json").mkdir()  # fopen feiler
        self.assertEqual(self.post()[:2], (503, {"ok": False, "error": "not_configured"}))
        self.assertNothingSent()


@unittest.skipUnless(h.PHP and shutil.which("openssl"), "PHP og openssl er nødvendig for SMTP-testene")
class ContactSmtpTests(unittest.TestCase):
    def run_with(self, smtp_config, **smtp_options):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            work = Path(directory)
            verifier = h.Verifier()
            stack.callback(verifier.close)
            smtp = h.Smtp(work, **smtp_options)
            stack.callback(smtp.close)
            hotel = h.Webhotel(work)
            stack.callback(hotel.stop)
            config = h.base_config(hotel.state, verifier, hotel.origin)
            config["transport"] = {"type": "smtp", "port": smtp.port, **smtp_config(smtp)}
            hotel.write_config(config)
            hotel.start()
            result = h.call(hotel.url + "/api/kontakt.php", "POST", {"email": READER, "message": MESSAGE, "captcha": "ok-token"}, origin=hotel.origin)
            self.assertEqual(hotel.sent(), [], "SMTP bruker ikke mail()")
            return result, smtp

    def test_starttls_with_login(self):
        result, smtp = self.run_with(lambda s: {"host": "localhost", "security": "starttls", "username": h.FAKE_SMTP_USER,
                                                "password": h.FAKE_SMTP_PASSWORD, "ca_file": str(s.cert)}, tls=True)
        self.assertEqual(result[:2], (200, {"ok": True}))
        [mail] = smtp.messages
        self.assertTrue(mail["secure"])
        self.assertEqual(smtp.logins, [(h.FAKE_SMTP_USER, h.FAKE_SMTP_PASSWORD)])
        self.assertEqual((mail["from"], mail["to"]), (h.FAKE_SENDER, [h.FAKE_RECIPIENT]))
        plain = "\n".join(smtp.plain_commands)
        self.assertNotIn(base64.b64encode(h.FAKE_SMTP_PASSWORD.encode()).decode(), plain, "passordet går aldri i klartekst")
        self.assertIn(b"Reply-To: <" + READER.encode() + b">", mail["data"])

    def test_untrusted_certificate_is_refused(self):
        result, smtp = self.run_with(lambda s: {"host": "localhost", "security": "starttls", "username": h.FAKE_SMTP_USER,
                                                "password": h.FAKE_SMTP_PASSWORD}, tls=True)
        self.assertEqual(result[:2], (502, {"ok": False, "error": "send_failed"}))
        self.assertEqual(smtp.logins, [])

    def test_plain_local_relay_without_login(self):
        result, smtp = self.run_with(lambda s: {"host": "127.0.0.1", "security": "none"})
        self.assertEqual(result[:2], (200, {"ok": True}))
        self.assertEqual(smtp.messages[0]["to"], [h.FAKE_RECIPIENT])

    def test_refused_recipient_is_a_send_failure(self):
        result, smtp = self.run_with(lambda s: {"host": "127.0.0.1", "security": "none"}, refuse_rcpt=True)
        self.assertEqual(result[:2], (502, {"ok": False, "error": "send_failed"}))
        self.assertEqual(smtp.messages, [])


class ContactPackageTests(unittest.TestCase):
    """Pakken med oppdiktede private verdier plantet rundt den: ingen av dem kommer med."""

    @classmethod
    def setUpClass(cls):
        import synthetic_collection  # noqa: PLC0415
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        cls.synthetic = synthetic_collection
        cls.values = cls.root / "privat-verdier.txt"
        cls.values.write_text("# oppdiktede verdier\n" + "\n".join(h.FAKE_VALUES) + "\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def build(self, name, plant=None):
        frontend, publish = self.synthetic.build_synthetic(self.root / f"{name}-source")
        if plant:
            plant(frontend, publish)
        output = self.root / name
        return output, self.synthetic.package(frontend, publish, output)

    def check(self, *args):
        return subprocess.run([sys.executable, str(CHECKER), "--values-file", str(self.values), *args], capture_output=True, text=True)

    def test_package_contains_the_form_and_no_private_values(self):
        def plant(frontend, publish):
            # En operatør har lagt den private konfigen ved siden av dataene og i store/.
            for target in (frontend / "kontakt-config.php", publish / "store" / "kontakt-config.php", frontend.parent / "bootdisk-privat" / "kontakt-config.php"):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("<?php return ['recipient' => '%s', 'client_salt' => '%s'];" % (h.FAKE_RECIPIENT, h.FAKE_SALT))
        output, result = self.build("release", plant)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("om-prosjektet.html", "contact.js", "contact-core.js", "api/kontakt.php"):
            self.assertTrue((output / name).is_file(), name)
        self.assertFalse(any(p.name == "kontakt-config.php" or p.suffix == ".md" for p in output.rglob("*")))
        self.assertFalse((output / "docs").exists())
        archive = self.root / "release.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            for path in output.rglob("*"):
                bundle.write(path, path.relative_to(output).as_posix())
        checked = self.check("--tree", str(output), "--zip", str(archive))
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn("privat konfig: ingen funn", checked.stdout)

    def test_builder_refuses_a_release_that_carries_private_config(self):
        builder = (ROOT / "scripts/build-release.py").read_text(encoding="utf-8")
        self.assertIn("refuse_private_config(stage)", builder)
        sys.path.insert(0, str(ROOT / "scripts"))
        import importlib.util  # noqa: PLC0415
        spec = importlib.util.spec_from_file_location("release_builder_contact", ROOT / "scripts/build-release.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        stage = self.root / "stage"
        (stage / "api").mkdir(parents=True)
        shutil.copy2(ROOT / "api/kontakt.php", stage / "api/kontakt.php")
        module.refuse_private_config(stage)  # selve mottaket er ikke konfig
        (stage / "api/oppsett.php").write_text("<?php return ['recipient' => 'x@y.invalid'];")
        with self.assertRaisesRegex(ValueError, "private configuration"):
            module.refuse_private_config(stage)
        (stage / "api/oppsett.php").unlink()
        (stage / "bootdisk-privat").mkdir()
        with self.assertRaisesRegex(ValueError, "Private server configuration"):
            module.refuse_private_config(stage)

    def test_checker_finds_planted_values_without_printing_them(self):
        tree = self.root / "lekk"
        (tree / "api").mkdir(parents=True)
        (tree / "ok.html").write_text("ingen hemmeligheter")
        (tree / "api" / "x.js").write_text("const to = '" + h.FAKE_RECIPIENT.upper() + "';")
        (tree / "y.txt").write_text("secret=" + h.FAKE_SECRET.replace("-", "%2D"))
        (tree / "z.txt").write_text("mailto:" + h.FAKE_SENDER.replace("@", "%40"))
        result = self.check("--tree", str(tree))
        self.assertEqual(result.returncode, 1)
        self.assertIn("verdi #1 i lekk/api/x.js", result.stdout)
        self.assertIn("verdi #2 i lekk/z.txt", result.stdout)
        for value in h.FAKE_VALUES:
            self.assertNotIn(value, result.stdout + result.stderr, "skriptet skriver aldri ut en verdi")

    def test_checker_flags_private_file_names_and_refuses_values_inside_the_repo(self):
        tree = self.root / "navn"
        (tree / "bootdisk-privat").mkdir(parents=True)
        (tree / "bootdisk-privat" / "tomt.txt").write_text("")
        self.assertEqual(self.check("--tree", str(tree)).returncode, 1)
        inside = ROOT / "build" / "verdier.txt"
        inside.parent.mkdir(exist_ok=True)
        inside.write_text("\n".join(h.FAKE_VALUES))
        try:
            result = subprocess.run([sys.executable, str(CHECKER), "--values-file", str(inside), "--tree", str(tree)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("ligger i repositoryet", result.stderr)
        finally:
            inside.unlink()

    def test_git_history_of_this_branch_has_no_fake_server_values_outside_the_tests(self):
        # Testverdiene står bevisst i tests/contact_harness.py og her. Alt annet må være rent.
        base = subprocess.run(["git", "-C", str(ROOT), "merge-base", "HEAD", "origin/main"], capture_output=True, text=True)
        if base.returncode:
            self.skipTest("origin/main er ikke hentet")
        diff = subprocess.run(["git", "-C", str(ROOT), "diff", base.stdout.strip(), "--", ".", ":(exclude)tests/contact_harness.py",
                               ":(exclude)tests/test_contact.py", ":(exclude)tests/test_contact_browser.py"],
                              capture_output=True, text=True, check=True).stdout
        for value in h.FAKE_VALUES:
            self.assertNotIn(value, diff)


if __name__ == "__main__":
    unittest.main()
