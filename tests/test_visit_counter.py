"""Besøkstelleren: besøksavgrensning, adapter, foreslått PHP-tjeneste og releasekontrakt.

JavaScript-tilfellene kjører den ekte kjernen og adapteren i Node med styrt klokke, minnelagring
og falsk fetch. Tjenestetilfellene starter counter/besok.php i PHPs innebygde server mot en
midlertidig SQLite-fil laget av scripts/visit-counter-db.py; ingen test snakker med produksjon.
Uten Node eller PHP hoppes de aktuelle klassene over, og det er ikke bestått.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import synthetic_collection as synthetic  # noqa: E402

NODE = shutil.which("node")
PHP = shutil.which("php")
DB_TOOL = ROOT / "scripts" / "visit-counter-db.py"
BACKEND = ROOT / "counter" / "besok.php"
ROUTER = ROOT / "tests" / "visit_counter_router.php"
# Portene Stian og Birk bruker til aktive forhåndsvisninger.
RESERVED_PORTS = {8772, 8794, 8795, 8796, 8797, 8798, 8803}
KEY_A = "0123456789abcdef0123456789abcdef"
T0 = 1790000000  # 2026-09-21, styrt klokke for tjenesten
PUBLIC_COUNTER_FILES = {"visit-counter.css", "visit-counter-config.js", "visit-counter-core.js",
                        "visit-counter-adapter.js", "visit-counter.js"}


def node(script: str) -> None:
    prelude = (
        "const assert = require('node:assert/strict');\n"
        f"const core = require({str(ROOT / 'visit-counter-core.js')!r});\n"
        f"const {{ createHttpVisitCounterAdapter, VisitCounterError }} = require({str(ROOT / 'visit-counter-adapter.js')!r});\n"
        "function memoryStorage(initial) { const map = new Map(initial || []);\n"
        "  return { getItem: k => map.has(k) ? map.get(k) : null, setItem: (k, v) => map.set(k, String(v)), map }; }\n"
        "const direct = fn => Promise.resolve().then(fn);\n"
        "let keySeq = 0; const newKey = () => (++keySeq).toString(16).padStart(32, '0');\n"
    )
    # Et løfte som aldri avgjøres lar Node avslutte med kode 0; markøren skiller det fra bestått.
    result = subprocess.run([NODE, "-e", prelude + "(async () => {\n" + script + "\n})().then(() => console.log('NODE-FERDIG'), e => { console.error(e); process.exit(1); });"],
                            capture_output=True, text=True, cwd=ROOT)
    if result.returncode or "NODE-FERDIG" not in result.stdout:
        raise AssertionError(result.stderr or result.stdout or "JavaScript-testen ble aldri ferdig")


@unittest.skipUnless(NODE, "Node er nødvendig for JavaScript-testene")
class VisitPlanTests(unittest.TestCase):
    def test_first_view_counts_and_reload_or_navigation_in_the_same_visit_does_not(self):
        node("""
        const first = core.visitPlan(null, 1000, newKey);
        assert.equal(first.action, 'record');
        let stored = JSON.stringify({ ...first.record, confirmed: true });
        // omlasting og navigering er begge bare en ny sidevisning i samme nettleser
        for (const at of [1000, 5000, 60000, 20 * 60000]) {
          const next = core.visitPlan(stored, at, newKey);
          assert.equal(next.action, 'read', `view at ${at}`);
          assert.equal(next.record.key, first.record.key);
          stored = JSON.stringify(next.record);
        }
        """)

    def test_idle_limit_is_thirty_minutes_after_the_last_view_not_after_the_first(self):
        node("""
        const minute = 60000;
        const start = core.visitPlan(null, 0, newKey);
        let stored = JSON.stringify({ ...start.record, confirmed: true });
        // en sidevisning hvert 25. minutt i to timer er fortsatt ett besøk
        for (let at = 25 * minute; at <= 120 * minute; at += 25 * minute) {
          const plan = core.visitPlan(stored, at, newKey);
          assert.equal(plan.action, 'read');
          stored = JSON.stringify(plan.record);
        }
        const last = JSON.parse(stored).last;
        assert.equal(core.visitPlan(stored, last + 30 * minute, newKey).action, 'read', 'akkurat 30 minutter er samme besøk');
        const fresh = core.visitPlan(stored, last + 30 * minute + 1, newKey);
        assert.equal(fresh.action, 'record');
        assert.notEqual(fresh.record.key, start.record.key);
        """)

    def test_unconfirmed_visit_resends_the_same_key_until_confirmed_or_the_retry_window_ends(self):
        node("""
        const start = core.visitPlan(null, 0, newKey);
        const stored = JSON.stringify(start.record);
        const retry = core.visitPlan(stored, 10 * 60000, newKey);
        assert.equal(retry.action, 'record');
        assert.equal(retry.record.key, start.record.key, 'ny innsending bruker samme nøkkel');
        // et besøk som holdes i live i mer enn 12 timer gir opp innsendingen i stedet for å bytte nøkkel
        let record = start.record, at = 0;
        while (at <= core.VISIT_RETRY_WINDOW_MS) { at += 29 * 60000; record = core.visitPlan(JSON.stringify(record), at, newKey).record; }
        const late = core.visitPlan(JSON.stringify(record), at + 60000, newKey);
        assert.equal(late.action, 'read');
        assert.equal(late.record.key, start.record.key);
        """)

    def test_clock_going_backwards_or_corrupt_storage(self):
        node("""
        const start = core.visitPlan(null, 10 * 3600000, newKey);
        const stored = JSON.stringify({ ...start.record, confirmed: true });
        const back = core.visitPlan(stored, 9 * 3600000, newKey);
        assert.equal(back.action, 'read', 'en klokke som går bakover starter ikke et nytt besøk');
        assert.equal(back.record.last, start.record.last);
        for (const bad of ['{', '[]', 'null', JSON.stringify({ key: 'ABC', started: 1, last: 1, confirmed: false }),
                           JSON.stringify({ key: '0'.repeat(32), started: 'x', last: 1, confirmed: false })]) {
          assert.equal(core.visitPlan(bad, 0, newKey).action, 'record', bad);
        }
        assert.throws(() => core.visitPlan(null, 0, () => 'not-a-key'));
        """)

    def test_confirmation_never_overwrites_a_visit_another_tab_started(self):
        node("""
        const mine = core.visitPlan(null, 0, newKey).record;
        const other = { ...core.visitPlan(null, 40 * 60000, newKey).record };
        assert.equal(core.visitConfirm(JSON.stringify(other), mine.key), null);
        assert.equal(core.visitConfirm(JSON.stringify(mine), mine.key).confirmed, true);
        assert.equal(core.visitConfirm(null, mine.key), null);
        """)

    def test_response_validation_refuses_anything_but_a_whole_total_and_a_real_date(self):
        node("""
        assert.deepEqual(core.visitParseResponse({ total: 0, since: '2026-09-25' }, false), { total: 0, since: '2026-09-25', counted: undefined });
        assert.equal(core.visitParseResponse({ total: 7, since: '2026-09-25', counted: false }, true).counted, false);
        const bad = [null, [], 'x', {}, { total: -1, since: '2026-09-25' }, { total: 1.5, since: '2026-09-25' },
          { total: '12', since: '2026-09-25' }, { total: 2 ** 53, since: '2026-09-25' }, { total: 1 },
          { total: 1, since: '2026-02-30' }, { total: 1, since: '25.09.2026' }, { total: 1, since: 20260925 }];
        for (const body of bad) assert.throws(() => core.visitParseResponse(body, false), JSON.stringify(body));
        assert.throws(() => core.visitParseResponse({ total: 1, since: '2026-09-25' }, true), 'POST-svar må si om besøket ble telt');
        """)

    def test_display_pads_to_six_fields_never_truncates_and_reads_as_one_number(self):
        node("""
        assert.equal(core.visitDigits(0), '000000');
        assert.equal(core.visitDigits(42), '000042');
        assert.equal(core.visitDigits(999999), '999999');
        assert.equal(core.visitDigits(1234567), '1234567');
        assert.equal(core.visitDigits(12345678901), '12345678901');
        assert.equal(core.visitSinceShort('2026-09-05'), '05.09.2026');
        assert.equal(core.visitLabel(1234567, '2026-09-05'), '1\\u00a0234\\u00a0567 besøk siden 5. september 2026');
        assert.equal(core.visitLabel(1, '2026-01-31'), '1 besøk siden 31. januar 2026');
        assert.doesNotMatch(core.visitLabel(5, '2026-09-25'), /unik|person|besøkende/);
        """)


@unittest.skipUnless(NODE, "Node er nødvendig for JavaScript-testene")
class VisitRunTests(unittest.TestCase):
    """Hele sidevisningen med falsk tjeneste: hva sendes, og når."""

    PRELUDE = """
    function fakeService() {
      const counted = new Set(); const calls = [];
      let total = 100; let failNextRecordAfterCounting = false;
      return {
        calls, counted,
        failAfterCounting() { failNextRecordAfterCounting = true; },
        async read() { calls.push(['read']); return { total, since: '2026-09-25' }; },
        async record(key) {
          calls.push(['record', key]);
          const isNew = !counted.has(key);
          if (isNew) { counted.add(key); total += 1; }
          if (failNextRecordAfterCounting) { failNextRecordAfterCounting = false; throw new VisitCounterError('timeout', 'svar tapt'); }
          return { total, since: '2026-09-25', counted: isNew };
        },
        get total() { return total; },
      };
    }
    """

    def test_visit_counts_once_across_views_and_again_after_the_idle_limit(self):
        node(self.PRELUDE + """
        const service = fakeService(), storage = memoryStorage(); let clock = 0;
        const view = () => core.visitRun({ adapter: service, storage, now: () => clock, newKey, withLock: direct });
        assert.equal((await view()).total, 101);
        clock += 5 * 60000; assert.equal((await view()).total, 101);
        clock += 29 * 60000; assert.equal((await view()).total, 101);
        clock += 30 * 60000 + 1; assert.equal((await view()).total, 102);
        assert.deepEqual(service.calls.map(c => c[0]), ['record', 'read', 'read', 'record']);
        """)

    def test_lost_response_is_resent_with_the_same_key_and_not_counted_twice(self):
        node(self.PRELUDE + """
        const service = fakeService(), storage = memoryStorage(); let clock = 0;
        const view = () => core.visitRun({ adapter: service, storage, now: () => clock, newKey, withLock: direct });
        service.failAfterCounting();
        await assert.rejects(view(), e => e.kind === 'timeout');
        clock += 60000;
        const second = await view();
        assert.equal(second.total, 101);
        assert.equal(second.counted, false);
        const keys = service.calls.filter(c => c[0] === 'record').map(c => c[1]);
        assert.equal(keys.length, 2); assert.equal(keys[0], keys[1]);
        clock += 60000; await view();
        assert.equal(service.calls.at(-1)[0], 'read', 'bekreftet besøk sendes ikke igjen');
        """)

    def test_blocked_storage_only_reads_and_never_counts(self):
        node(self.PRELUDE + """
        const service = fakeService();
        const blocked = { getItem() { throw new Error('SecurityError'); }, setItem() { throw new Error('SecurityError'); } };
        const quota = { getItem: () => null, setItem() { throw new Error('QuotaExceededError'); } };
        for (const storage of [blocked, quota]) {
          for (let i = 0; i < 3; i++) {
            const result = await core.visitRun({ adapter: service, storage, now: () => 0, newKey, withLock: direct });
            assert.equal(result.total, 100); assert.equal(result.recorded, false);
          }
        }
        assert.ok(service.calls.every(c => c[0] === 'read'));
        """)

    def test_two_tabs_sharing_storage_under_a_lock_send_one_key(self):
        node(self.PRELUDE + """
        const service = fakeService(), storage = memoryStorage();
        let chain = Promise.resolve();
        const lock = fn => { const run = chain.then(fn); chain = run.catch(() => {}); return run; };
        await Promise.all([1, 2, 3].map(() => core.visitRun({ adapter: service, storage, now: () => 0, newKey, withLock: lock })));
        const keys = new Set(service.calls.filter(c => c[0] === 'record').map(c => c[1]));
        assert.equal(keys.size, 1, 'parallelle faner deler én besøksnøkkel');
        assert.equal(service.total, 101);
        """)


@unittest.skipUnless(NODE, "Node er nødvendig for JavaScript-testene")
class VisitAdapterTests(unittest.TestCase):
    def test_requests_carry_only_the_key_and_no_credentials(self):
        node("""
        const seen = [];
        const fetchImpl = async (url, options) => { seen.push([url, options]);
          return { ok: true, status: 200, json: async () => ({ total: 3, since: '2026-09-25', counted: true }) }; };
        const adapter = createHttpVisitCounterAdapter({ endpoint: 'api/besok.php', fetchImpl, parse: core.visitParseResponse });
        assert.equal((await adapter.record('a'.repeat(32))).total, 3);
        const [url, options] = seen[0];
        assert.equal(url, 'api/besok.php'); assert.equal(options.method, 'POST');
        assert.deepEqual(JSON.parse(options.body), { visit: 'a'.repeat(32) });
        assert.equal(options.credentials, 'omit'); assert.equal(options.cache, 'no-store'); assert.equal(options.referrerPolicy, 'no-referrer');
        """)

    def test_every_failure_becomes_a_typed_error(self):
        node("""
        const make = fetchImpl => createHttpVisitCounterAdapter({ endpoint: 'x', fetchImpl, parse: core.visitParseResponse, timeoutMs: 20 });
        const cases = [
          [async () => { throw new TypeError('Failed to fetch'); }, 'network'],
          [async () => ({ ok: false, status: 503, json: async () => ({ total: 5, since: '2026-09-25' }) }), 'http'],
          [async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError('x'); } }), 'invalid'],
          [async () => ({ ok: true, status: 200, json: async () => ({ total: -4, since: '2026-09-25' }) }), 'invalid'],
          [(url, options) => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new Error('aborted')))), 'timeout'],
        ];
        for (const [fetchImpl, kind] of cases) {
          await assert.rejects(make(fetchImpl).read(), error => error instanceof VisitCounterError && error.kind === kind, kind);
        }
        """)

    def test_client_gives_up_resending_well_before_the_service_forgets_a_key(self):
        source = BACKEND.read_text(encoding="utf-8")
        ttl = eval(re.search(r"const VISIT_KEY_TTL = ([0-9 *]+);", source).group(1))  # noqa: S307 - literal from our file
        core = (ROOT / "visit-counter-core.js").read_text(encoding="utf-8")
        retry = eval(re.search(r"const VISIT_RETRY_WINDOW_MS = ([0-9 *]+);", core).group(1)) / 1000  # noqa: S307
        idle = eval(re.search(r"const VISIT_IDLE_MS = ([0-9 *]+);", core).group(1)) / 1000  # noqa: S307
        self.assertEqual(idle, 30 * 60)
        # Siste mulige innsending: retry-vinduet pluss én inaktivitetsgrense. Den må treffe en kjent nøkkel.
        self.assertLess(retry + idle, ttl)


def free_port() -> int:
    while True:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        if port not in RESERVED_PORTS:
            return port


@contextlib.contextmanager
def php_server(*, router=None, docroot=None, env=None, workers=None, port=None):
    port = port or free_port()
    command = [PHP, "-S", f"127.0.0.1:{port}"]
    if docroot:
        command += ["-t", str(docroot)]
    if router:
        command.append(str(router))
    environment = {key: value for key, value in os.environ.items() if not key.startswith("BOOTDISK_COUNTER")}
    environment.update(env or {})
    if workers:
        environment["PHP_CLI_SERVER_WORKERS"] = str(workers)
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment, cwd=docroot or ROOT)
    try:
        for _ in range(100):
            with contextlib.suppress(OSError), socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("PHP-serveren startet ikke")
        yield f"http://127.0.0.1:{port}"
    finally:
        process.terminate()
        process.wait(timeout=10)


def call(url, method="GET", body=None, origin=None, headers=None):
    data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if origin:
        request.add_header("Origin", origin)
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read() or b"null"), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null"), dict(error.headers)


def init_db(path: Path, since="2026-09-21") -> None:
    subprocess.run([sys.executable, str(DB_TOOL), "init", str(path), "--since", since], check=True, capture_output=True)


def total_in(path: Path) -> int:
    with contextlib.closing(sqlite3.connect(path)) as connection:
        return connection.execute("SELECT total FROM counter").fetchone()[0]


@unittest.skipUnless(PHP, "PHP er nødvendig for tjenestetestene")
class CounterServiceTests(unittest.TestCase):
    ORIGIN = "http://bootdisk.test"

    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.work)
        self.db = self.work / "besok.sqlite"
        init_db(self.db)

    def service(self, now=T0, **extra):
        env = {"BOOTDISK_COUNTER_DB": str(self.db), "BOOTDISK_COUNTER_ORIGIN": self.ORIGIN, "BOOTDISK_COUNTER_NOW": str(now)}
        env.update({f"BOOTDISK_COUNTER_{name.upper()}": str(value) for name, value in extra.items() if name != "workers"})
        return php_server(router=BACKEND, env=env, workers=extra.get("workers"))

    def visit(self, base, key, **kwargs):
        return call(base + "/", "POST", {"visit": key}, origin=kwargs.pop("origin", self.ORIGIN), **kwargs)

    def test_new_key_counts_once_and_a_resent_key_does_not(self):
        with self.service() as base:
            self.assertEqual(call(base + "/")[:2], (200, {"total": 0, "since": "2026-09-21"}))
            status, body, headers = self.visit(base, KEY_A)
            self.assertEqual((status, body), (200, {"total": 1, "since": "2026-09-21", "counted": True, "limited": False}))
            self.assertEqual(headers["Cache-Control"], "no-store")
            for _ in range(3):
                self.assertEqual(self.visit(base, KEY_A)[1]["counted"], False)
            self.assertEqual(self.visit(base, "f" * 32)[1]["total"], 2)
        self.assertEqual(total_in(self.db), 2)

    def test_parallel_requests_lose_no_updates_and_count_each_key_once(self):
        keys = [f"{index:032x}" for index in range(40)]
        with self.service(workers=8) as base:
            with ThreadPoolExecutor(max_workers=24) as pool:
                results = list(pool.map(lambda key: self.visit(base, key), keys * 3))
        self.assertTrue(all(status == 200 for status, _, _ in results), [r[:2] for r in results if r[0] != 200])
        self.assertEqual(sum(body["counted"] for _, body, _ in results), 40)
        self.assertEqual(total_in(self.db), 40)

    def test_restart_keeps_the_total_and_a_missing_database_is_unavailable_not_zero(self):
        with self.service() as base:
            self.visit(base, KEY_A)
        with self.service() as base:
            self.assertEqual(call(base + "/")[1]["total"], 1)
            self.assertFalse(self.visit(base, KEY_A)[1]["counted"], "nøklene overlever omstart")
        self.db.unlink()
        with self.service() as base:
            self.assertEqual(call(base + "/")[:2], (503, {"error": "unavailable"}))
            self.assertEqual(self.visit(base, KEY_A)[0], 503)
        self.assertFalse(self.db.exists(), "tjenesten lager aldri en ny, tom teller")

    def test_redeploying_the_static_site_does_not_touch_the_default_storage_outside_the_web_root(self):
        home = self.work / "home"
        www = home / "www"
        (home / "bootdisk-besok").mkdir(parents=True)
        init_db(home / "bootdisk-besok" / "besok.sqlite")

        def deploy():
            # Deploy-prosedyren fjerner alt i /www som ikke er i den nye releasen.
            if www.exists():
                shutil.rmtree(www)
            (www / "api").mkdir(parents=True)
            shutil.copy2(BACKEND, www / "api" / "besok.php")
            (www / "index.html").write_text("ny release", encoding="utf-8")

        env = {"BOOTDISK_COUNTER_ORIGIN": self.ORIGIN, "BOOTDISK_COUNTER_NOW": str(T0)}
        deploy()
        with php_server(docroot=www, env=env) as base:
            self.assertEqual(call(base + "/api/besok.php", "POST", {"visit": KEY_A}, origin=self.ORIGIN)[1]["total"], 1)
        deploy()
        with php_server(docroot=www, env=env) as base:
            self.assertEqual(call(base + "/api/besok.php")[1]["total"], 1)
        self.assertEqual(sorted(p.name for p in www.rglob("*")), ["api", "besok.php", "index.html"])

    def test_keys_are_forgotten_after_48_hours(self):
        with self.service(now=T0) as base:
            self.visit(base, KEY_A)
        with self.service(now=T0 + 48 * 3600 - 1) as base:
            self.assertFalse(self.visit(base, KEY_A)[1]["counted"])
        with self.service(now=T0 + 48 * 3600) as base:
            self.assertTrue(self.visit(base, KEY_A)[1]["counted"])
        with contextlib.closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM visits").fetchone()[0], 1)

    def test_minute_and_day_limits_cap_how_fast_the_total_can_grow(self):
        with self.service(now=T0, minute_limit=3, day_limit=5) as base:
            results = [self.visit(base, f"{index:032x}")[1] for index in range(5)]
        self.assertEqual([r["counted"] for r in results], [True, True, True, False, False])
        self.assertEqual([r["limited"] for r in results], [False, False, False, True, True])
        with self.service(now=T0 + 60, minute_limit=3, day_limit=5) as base:
            results = [self.visit(base, f"{index + 10:032x}")[1] for index in range(3)]
        self.assertEqual([r["counted"] for r in results], [True, True, False], "døgngrensen på 5 holder")
        self.assertEqual(total_in(self.db), 5)
        with contextlib.closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("SELECT counted, limited FROM daily").fetchall(), [(5, 3)])

    def test_malformed_foreign_or_oversized_requests_change_nothing(self):
        with self.service() as base:
            cases = [
                (call(base + "/", "POST", {"visit": KEY_A}), 403),
                (call(base + "/", "POST", {"visit": KEY_A}, origin="https://evil.example"), 403),
                (call(base + "/", "POST", {"visit": KEY_A}, origin=self.ORIGIN, headers={"Sec-Fetch-Site": "cross-site"}), 403),
                (call(base + "/", "POST", {"visit": KEY_A.upper()}, origin=self.ORIGIN), 400),
                (call(base + "/", "POST", {"visit": KEY_A[:-1]}, origin=self.ORIGIN), 400),
                (call(base + "/", "POST", {"visit": KEY_A + "\n"}, origin=self.ORIGIN), 400),
                (call(base + "/", "POST", {"visit": KEY_A, "total": 999}, origin=self.ORIGIN), 400),
                (call(base + "/", "POST", [KEY_A], origin=self.ORIGIN), 400),
                (call(base + "/", "POST", b"visit=" + KEY_A.encode(), origin=self.ORIGIN, headers={"Content-Type": "text/plain"}), 415),
                (call(base + "/", "POST", json.dumps({"visit": KEY_A, "pad": "x" * 300}).encode(), origin=self.ORIGIN), 413),
                (call(base + "/", "PUT", {"visit": KEY_A}, origin=self.ORIGIN), 405),
                (call(base + "/", "DELETE", origin=self.ORIGIN), 405),
            ]
            for index, ((status, body, _), expected) in enumerate(cases):
                self.assertEqual(status, expected, index)
                self.assertNotIn("total", body or {}, index)
        self.assertEqual(total_in(self.db), 0)

    def test_storage_holds_no_address_or_browser_data(self):
        with self.service() as base:
            self.visit(base, KEY_A, headers={"User-Agent": "Mozilla/5.0 fingerprint-probe"})
        dump = "\n".join(sqlite3.connect(self.db).iterdump())
        for probe in ("127.0.0.1", "fingerprint", "Mozilla", "bootdisk.test"):
            self.assertNotIn(probe, dump)
        with contextlib.closing(sqlite3.connect(self.db)) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            columns = {table: [row[1] for row in connection.execute(f"PRAGMA table_info({table})")] for table in tables}
        self.assertEqual(columns, {"counter": ["id", "total", "since"], "visits": ["key", "expires"],
                                   "daily": ["day", "counted", "limited"], "minutes": ["minute", "counted"]})
        source = BACKEND.read_text(encoding="utf-8")
        for call_name in ("error_log", "file_put_contents", "syslog", "REMOTE_ADDR", "setcookie", "HTTP_USER_AGENT"):
            self.assertNotIn(call_name, source)


class CounterDatabaseToolTests(unittest.TestCase):
    def test_init_refuses_to_overwrite_and_backup_is_a_checked_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            init_db(work / "a.sqlite", since="2026-10-01")
            again = subprocess.run([sys.executable, str(DB_TOOL), "init", str(work / "a.sqlite")], capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            with contextlib.closing(sqlite3.connect(work / "a.sqlite")) as connection:
                connection.execute("UPDATE counter SET total = 4321")
                connection.commit()
            result = subprocess.run([sys.executable, str(DB_TOOL), "backup", str(work / "a.sqlite"), str(work / "b.sqlite")],
                                    capture_output=True, text=True, check=True)
            self.assertIn("integritet: ok", result.stdout)
            self.assertIn("total: 4321", result.stdout)
            self.assertIn("siden: 2026-10-01", result.stdout)
            self.assertEqual(total_in(work / "b.sqlite"), 4321)
            (work / "broken.sqlite").write_bytes(b"not a database")
            broken = subprocess.run([sys.executable, str(DB_TOOL), "status", str(work / "broken.sqlite")], capture_output=True, text=True)
            self.assertNotEqual(broken.returncode, 0)


class CounterReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        data, publish = synthetic.build_synthetic(root / "seven")
        cls.release = root / "release"
        result = synthetic.package(data, publish, cls.release)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.files = {path.relative_to(cls.release).as_posix() for path in cls.release.rglob("*") if path.is_file()}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_release_has_exactly_the_public_counter_files_and_no_backend_or_data(self):
        counter = {name for name in self.files if "visit" in name or "besok" in name or "counter" in name}
        self.assertEqual(counter, PUBLIC_COUNTER_FILES)
        for name in self.files:
            self.assertFalse(name.endswith((".php", ".sqlite", ".sql", ".db")), name)

    def test_packaged_counter_is_switched_off_until_hosting_is_confirmed(self):
        config = (self.release / "visit-counter-config.js").read_text(encoding="utf-8")
        assignments = [line for line in config.splitlines() if line.startswith("window.BOOTDISK_VISIT_COUNTER")]
        self.assertEqual(assignments, ['window.BOOTDISK_VISIT_COUNTER = Object.freeze({ origin: "https://bootdisk.no", endpoint: null });'])
        self.assertIn("BLOKKERT", config)

    def test_public_pages_show_the_counter_and_private_or_error_pages_do_not(self):
        for name in ("index.html", "archive.html", "collection.html"):
            page = (self.release / name).read_text(encoding="utf-8")
            footer = page.split("<footer>", 1)[1].split("</footer>", 1)[0]
            self.assertIn('<p id="visit-counter" class="visit-counter" hidden></p>', footer, name)
            scripts = re.findall(r'<script src="(visit-counter[^"]*)"', page)
            self.assertEqual(scripts, ["visit-counter-config.js", "visit-counter-core.js", "visit-counter-adapter.js", "visit-counter.js"], name)
            self.assertIn('href="visit-counter.css"', page)
        for name in ("404.html", "curate.html", "overview.html", "automation.html"):
            self.assertNotIn("visit-counter", (ROOT / name).read_text(encoding="utf-8"), name)

    def test_deployment_verifier_requires_the_backend_source_to_stay_private(self):
        verifier = (ROOT / "scripts" / "verify-deployment.py").read_text(encoding="utf-8")
        not_public = verifier.split("NOT_PUBLIC = (", 1)[1].split(")", 1)[0]
        for path in ("counter/besok.php", "counter/schema.sql", "scripts/visit-counter-db.py"):
            self.assertIn(f'"{path}"', not_public)


if __name__ == "__main__":
    unittest.main()
