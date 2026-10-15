"""Public update history (bootdisk-public-updates-v1) without a browser.

The generator, the register rules, the release builder and the HTTP verifier run on the
labelled test history in tests/synthetic_updates.py (PRØVEDATA). The page logic in
updates-core.js runs in Node against the same packaged feed and index. Browser
behaviour is in test_public_updates_browser.py. Nothing here touches the real rc11/rc12
data; that acceptance is documented in docs/public-updates.md.
"""
import contextlib
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import public_updates as pu  # noqa: E402
import synthetic_updates as su  # noqa: E402
from test_publication import serve, sitemap_urls  # noqa: E402

NODE = shutil.which("node")
SCRIPT = ROOT / "scripts" / "public_updates.py"


def events_by_entry(register, release_id):
    return {event["entry"]: (event["type"], event["changes"]) for event in register["events"] if event["release_id"] == release_id}


class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stack = contextlib.ExitStack()
        cls.root = Path(cls._stack.enter_context(tempfile.TemporaryDirectory()))
        cls.history = su.build_history(cls.root / "history")
        cls.p1, cls.p2, cls.p3 = (pu.load_projection(cls.history[name]) for name in ("r1", "r2", "r3"))
        cls.register1, cls.register2, cls.register3 = cls.history["registers"]

    @classmethod
    def tearDownClass(cls):
        cls._stack.close()

    def test_r2_and_r3_give_exactly_the_expected_events(self):
        self.assertEqual(events_by_entry(self.register3, su.R2), su.EXPECTED_R2)
        self.assertEqual(events_by_entry(self.register3, su.R3), su.EXPECTED_R3)

    def test_new_entry_is_added_and_others_are_never_new(self):
        added = [event["entry"] for event in self.register3["events"] if event["type"] == "added"]
        self.assertEqual(added, [su.NEW_ENTRY])
        event = next(event for event in self.register3["events"] if event["entry"] == su.NEW_ENTRY)
        self.assertEqual((event["medium_id"], event["source_entry"]), ("kcd-9-2000", "K7"))

    def test_pending_to_identified_keeps_unknown_version_unknown(self):
        self.assertEqual(self.p2["kcd-8-2001--K1"]["visible"]["version"], None)
        self.assertEqual(su.EXPECTED_R2["kcd-8-2001--K1"], ("updated", ["identified", "name_added"]))
        self.assertNotIn("version_added", events_by_entry(self.register2, su.R2)["kcd-8-2001--K1"][1])

    def test_known_to_unknown_is_a_removal_not_a_clarification(self):
        self.assertEqual(events_by_entry(self.register2, su.R2)["K37"], ("updated", ["name_changed", "version_removed"]))

    def test_technical_changes_alone_give_no_event(self):
        # Moved storage path, new manifest digest, renumbered source order and new JSON layout in r2.
        r2 = events_by_entry(self.register2, su.R2)
        self.assertNotIn("kcd-8-2001--K9", r2)
        self.assertFalse(any(entry.startswith("kcd-13-2000--") for entry in r2))
        changed_layout = (self.history["r2"] / "kcd-1-2000--spil1.json").read_text(encoding="utf-8")
        original_layout = (self.history["r1"] / "kcd-1-2000--spil1.json").read_text(encoding="utf-8")
        self.assertNotEqual(changed_layout, original_layout)
        self.assertNotIn("kcd-1-2000--Spil1", r2)
        unchanged = len(self.p2) - len(r2)
        self.assertEqual(pu.summarize(self.p1, self.p2, pu.diff(self.p1, self.p2))["unchanged"], unchanged)

    def test_unchanged_rebuild_and_identical_new_release_give_zero_events(self):
        self.assertEqual(pu.diff(self.p3, self.p3), [])
        work = self.root / "rebuild"
        index, documents = su.read(self.history["r3"])
        rebuilt = su.write(work / "data", index, documents, indent=8, sort_keys=False)
        self.assertEqual(pu.fingerprint(pu.load_projection(rebuilt)), pu.fingerprint(self.p3))
        register = pu.record_release(self.register3, self.p3, pu.load_projection(rebuilt), "test-r4", "2026-11-01T12:00:00Z")
        self.assertEqual(register["releases"][-1]["added"], 0)
        self.assertEqual(register["releases"][-1]["updated"], 0)
        self.assertEqual(len(register["events"]), len(self.register3["events"]))

    def test_each_visible_field_has_its_code(self):
        base = pu.visible_projection({"curation_status": "pending", "editorial_title": "A", "software": [], "assets": [],
                                      "source_context": {"key": {"entry": "K1", "manifest": "m"}}})
        cases = {
            "menu_title_changed": {"menu_title": "B"},
            "description_added": {"description": "Tekst", "description_source": "cd"},
            "icon_added": {"icon": "a" * 64},
            "screenshot_added": {"screenshot": "b" * 64},
            "source_document_added": {"source_documents": [{"sha256": "c" * 64, "text": None, "path": "X.RTF"}]},
            "source_issues_added": {"source_issues": True},
            "content_kind_added": {"content_kind": "game"},
            "distribution_kind_added": {"distribution_kind": "demo"},
        }
        for code, change in cases.items():
            with self.subTest(code):
                self.assertEqual(pu.change_codes(base, {**base, **change}), [code])
        withdrawn = pu.change_codes({**base, "status": "identified", "software_name": "X"}, base)
        self.assertEqual(withdrawn, ["identification_withdrawn", "name_removed"])
        confirmed = pu.change_codes({**base, "status": "interpreted"}, {**base, "status": "identified"})
        self.assertEqual(confirmed, ["identification_confirmed"])

    def test_storage_path_and_derivatives_are_not_content(self):
        asset = {"kind": "icon", "original": {"sha256": "a" * 64, "public_path": "store/a"}, "derivatives": [{"kind": "thumbnail", "sha256": "d" * 64, "public_path": "store/d"}]}
        moved = copy.deepcopy(asset)
        moved["original"]["public_path"] = "store/elsewhere"
        moved["derivatives"][0].update({"sha256": "e" * 64, "public_path": "store/e"})
        document = {"curation_status": "pending", "software": [], "source_context": {}}
        self.assertEqual(pu.visible_projection({**document, "assets": [asset]}), pu.visible_projection({**document, "assets": [moved]}))
        rtf = {"key": {"entry": "K1", "manifest": "m"}, "sha256": "f" * 64, "text": "T", "path": "A.RTF",
               "original": {"sha256": "f" * 64, "public_path": "store/documents/x"}}
        moved_rtf = copy.deepcopy(rtf)
        moved_rtf["original"]["public_path"] = "store/documents/y"
        context = {"key": {"entry": "K1", "manifest": "m"}}
        self.assertEqual(pu.visible_projection({**document, "source_context": context, "source_documents": [rtf]}),
                         pu.visible_projection({**document, "source_context": context, "source_documents": [moved_rtf]}))

    def test_same_release_twice_is_idempotent(self):
        again = pu.record_release(self.register3, self.p2, self.p3, su.R3, su.R3_TIME)
        self.assertEqual(pu.dumps(again), pu.dumps(self.register3))

    def test_conflicting_reuse_of_a_release_id_is_refused(self):
        with self.assertRaisesRegex(pu.UpdatesError, "already registered as published at"):
            pu.record_release(self.register3, self.p2, self.p3, su.R3, "2026-10-25T08:00:00Z")
        with self.assertRaisesRegex(pu.UpdatesError, "already registered with other content"):
            pu.record_release(self.register3, self.p1, self.p3, su.R3, su.R3_TIME)
        with self.assertRaisesRegex(pu.UpdatesError, "baseline"):
            pu.record_release(self.register3, self.p3, self.p3, su.R1, "2026-12-01T00:00:00Z")

    def test_previous_projection_must_be_the_last_published_one(self):
        with self.assertRaisesRegex(pu.UpdatesError, "not the register's last published state"):
            pu.record_release(self.register3, self.p2, self.p3, "test-r4", "2026-12-01T00:00:00Z")

    def test_publication_time_is_explicit_utc_and_moves_forward(self):
        for value in ("2026-10-15T09:30:00", "2026-10-15T09:30:00+02:00", "2026-10-15", "2026-02-30T10:00:00Z", None):
            with self.subTest(value), self.assertRaises(pu.UpdatesError):
                pu.record_release(self.register3, self.p3, self.p3, "test-r4", value)
        with self.assertRaisesRegex(pu.UpdatesError, "must be later"):
            pu.record_release(self.register3, self.p3, self.p3, "test-r4", su.R3_TIME)
        result = subprocess.run([sys.executable, str(SCRIPT), "record", str(self.history["r3"]), str(self.history["r3"]),
                                 "--register", str(self.history["register3"]), "--release-id", "test-r4",
                                 "--output", str(self.root / "no-time.json")], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--published-at", result.stderr)
        self.assertFalse((self.root / "no-time.json").exists())

    def test_first_baseline_has_no_dates_and_no_new_entries(self):
        self.assertEqual(self.register1["releases"], [])
        self.assertEqual(self.register1["events"], [])
        self.assertEqual(len(self.register1["baseline"]["entries"]), len(self.p1))
        self.assertEqual(set(self.register1["baseline"]), {"release_id", "projection_sha256", "entries"})

    def test_record_with_baseline_in_one_step_matches_init_then_record(self):
        output = self.root / "one-step.json"
        result = subprocess.run([sys.executable, str(SCRIPT), "record", str(self.history["r1"]), str(self.history["r2"]),
                                 "--baseline-release-id", su.R1, "--release-id", su.R2, "--published-at", su.R2_TIME,
                                 "--output", str(output), "--expect-added", "1", "--expect-updated", "6"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), pu.dumps(self.register2))
        refused = subprocess.run([sys.executable, str(SCRIPT), "record", str(self.history["r1"]), str(self.history["r2"]),
                                  "--baseline-release-id", su.R1, "--release-id", su.R2, "--published-at", su.R2_TIME,
                                  "--output", str(output)], capture_output=True, text=True)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("refusing to replace", refused.stderr)

    def test_expectations_fail_loudly(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "preview", str(self.history["r1"]), str(self.history["r2"]),
                                 "--expect-updated", "88"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected 88 updated, got 6", result.stderr)

    def test_preview_writes_nothing(self):
        before = sorted(path.name for path in self.root.rglob("*"))
        result = subprocess.run([sys.executable, str(SCRIPT), "preview", str(self.history["r2"]), str(self.history["r3"]),
                                 "--show", "K37"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nothing was written", result.stdout)
        self.assertIn('"changes": ["name_changed", "version_added"]', result.stdout)
        self.assertEqual(sorted(path.name for path in self.root.rglob("*")), before)

    def test_rebinding_a_public_id_is_refused(self):
        moved = copy.deepcopy(self.p3)
        moved["K37"] = {**moved["K37"], "source_entry": "K38"}
        with self.assertRaisesRegex(pu.UpdatesError, "must keep its source binding"):
            pu.diff(self.p3, moved)

    def test_register_validation_rejects_broken_history(self):
        def broken(change):
            register = copy.deepcopy(self.register3)
            change(register)
            return register
        cases = {
            "schema": lambda r: r.update(schema="bootdisk-public-updates-v0"),
            "duplicate event": lambda r: r["events"].insert(1, copy.deepcopy(r["events"][0])),
            "unknown code": lambda r: r["events"][0]["changes"].append("faster"),
            "unknown type": lambda r: r["events"][0].update(type="deleted"),
            "time mismatch": lambda r: r["events"][0].update(published_at="2026-03-28T23:31:00Z"),
            "local time": lambda r: r["releases"][0].update(published_at="2026-03-29T00:30:00+01:00"),
            "count": lambda r: r["releases"][0].update(updated=7),
            "chain": lambda r: r["releases"][1].update(previous_release_id="test-r0"),
            "order": lambda r: r["events"].reverse(),
            "added with codes": lambda r: next(e for e in r["events"] if e["type"] == "added").update(changes=["icon_added"]),
            "extra field": lambda r: r["events"][0].update(local_path="/Users/someone/x"),
            "time goes back": lambda r: r["releases"][1].update(published_at="2026-01-01T00:00:00Z"),
        }
        for name, change in cases.items():
            with self.subTest(name), self.assertRaises(pu.UpdatesError):
                pu.validate_register(broken(change))

    def test_events_must_bind_to_the_index_and_describe_the_data(self):
        index = json.loads((self.history["r3"] / "index.json").read_text(encoding="utf-8"))
        pu.validate_register(self.register3, index, pu.fingerprint(self.p3))
        register = copy.deepcopy(self.register3)
        next(e for e in register["events"] if e["entry"] == "K37")["source_entry"] = "K38"
        with self.assertRaisesRegex(pu.UpdatesError, "does not match the archive index"):
            pu.validate_register(register, index)
        with self.assertRaisesRegex(pu.UpdatesError, "does not describe this frontend data"):
            pu.validate_register(self.register2, index, pu.fingerprint(self.p3))

    def test_register_has_only_public_fields(self):
        text = pu.dumps(self.register3)
        for word in ("/tmp", "/Users", "local-results", "curation", "receipt", "store/"):
            self.assertNotIn(word, text)


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stack = contextlib.ExitStack()
        cls.root = Path(cls._stack.enter_context(tempfile.TemporaryDirectory()))
        cls.history = su.build_history(cls.root / "history")
        cls.release = cls.root / "release"
        result = su.package(cls.history["r3"], cls.history["publish"], cls.release, cls.history["register3"])
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.plain = cls.root / "plain"
        result = su.package(cls.history["r3"], cls.history["publish"], cls.plain, None)
        if result.returncode:
            raise AssertionError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls._stack.close()

    def test_package_contains_page_feed_and_nothing_private(self):
        published = {path.relative_to(self.release).as_posix() for path in self.release.rglob("*") if path.is_file()}
        for name in ("updates.html", "updates.js", "updates-core.js", "landing-updates.js", "updates.css", "data/public-updates.json"):
            self.assertIn(name, published)
        for path in published:
            self.assertFalse(any(word in path for word in ("curat", "overview", "automation", "fixture", "tests/", "sample", "scripts/", "docs/", "synthetic")), path)
        self.assertEqual((self.release / "data/public-updates.json").read_bytes(), self.history["register3"].read_bytes())

    def test_sitemap_and_canonical_include_the_updates_page_only_with_history(self):
        self.assertIn("https://bootdisk.no/updates.html", sitemap_urls(self.release))
        self.assertNotIn("https://bootdisk.no/updates.html", sitemap_urls(self.plain))
        page = (self.release / "updates.html").read_text(encoding="utf-8")
        self.assertIn('<link rel="canonical" href="https://bootdisk.no/updates.html">', page)
        self.assertFalse((self.plain / "data/public-updates.json").exists())
        self.assertTrue((self.plain / "updates.html").exists())

    def test_release_refuses_explicit_invalid_or_stale_history(self):
        broken = self.root / "broken.json"
        register = json.loads(self.history["register3"].read_text(encoding="utf-8"))
        register["events"][0]["changes"] = ["faster"]
        broken.write_text(json.dumps(register), encoding="utf-8")
        for name, path, message in (("invalid", broken, "unknown change code"),
                                    ("stale", self.history["register2"], "does not describe this frontend data"),
                                    ("missing", self.root / "nope.json", "not found")):
            with self.subTest(name):
                result = su.package(self.history["r3"], self.history["publish"], self.root / f"out-{name}", path)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse((self.root / f"out-{name}").exists())

    def test_contract_cli_validates_register_with_data(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/frontend_contract.py"), str(self.release / "data"),
                                 "--updates", str(self.release / "data/public-updates.json")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("public updates: 10 events in 2 releases valid", result.stdout)

    def test_published_package_can_be_the_previous_projection_of_the_next_release(self):
        projection = pu.load_projection(self.release / "data")
        self.assertEqual(pu.fingerprint(projection), self.history["registers"][2]["releases"][-1]["projection_sha256"])

    def test_http_verifier_checks_the_deployed_history(self):
        command = [sys.executable, str(ROOT / "scripts" / "verify-deployment.py")]
        entries = str(len(json.loads((self.release / "data/index.json").read_text(encoding="utf-8"))["entries"]))
        with serve(self.release) as base:
            result = subprocess.run([*command, base, "--expected-entries", entries, "--require-updates"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deployment update events: 10", result.stdout)
        with serve(self.plain) as base:
            result = subprocess.run([*command, base, "--expected-entries", entries], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("deployment update history: none", result.stdout)
            result = subprocess.run([*command, base, "--expected-entries", entries, "--require-updates"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
        stale = self.root / "stale-deploy"
        shutil.copytree(self.release, stale)
        shutil.copy2(self.history["register2"], stale / "data/public-updates.json")
        with serve(stale) as base:
            result = subprocess.run([*command, base, "--expected-entries", entries], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Deployed update history is invalid", result.stderr)
        leaked = self.root / "leaked"
        shutil.copytree(self.release, leaked)
        (leaked / "scripts").mkdir()
        shutil.copy2(SCRIPT, leaked / "scripts/public_updates.py")
        with serve(leaked) as base:
            result = subprocess.run([*command, base, "--expected-entries", entries], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("scripts/public_updates.py", result.stderr)

    def test_release_artifact_reports_the_history(self):
        output = self.root / "artifact"
        # The artifact report hashes Publish's manifest; the test store has a stand-in.
        (self.history["publish"] / "publish-manifest.json").write_text('{"note": "PRØVEDATA"}\n', encoding="utf-8")
        result = subprocess.run([sys.executable, str(ROOT / "scripts/build-release-artifact.py"), str(self.history["publish"]),
                                 "--frontend-data", str(self.history["r3"]), "--output", str(output),
                                 "--expected-entries", "25", "--updates", str(self.history["register3"])], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(next(output.glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(report["updates"]["baseline_release_id"], su.R1)
        self.assertEqual([(r["release_id"], r["added"], r["updated"]) for r in report["updates"]["releases"]], [(su.R2, 1, 6), (su.R3, 0, 3)])


NODE_CORE = r"""
const fs = require('node:fs'), vm = require('node:vm'), strict = require('node:assert/strict');
// Arrays made inside the vm context have another prototype; compare their JSON form.
const plain = value => JSON.parse(JSON.stringify(value));
const assert = Object.assign(Object.create(strict), {deepEqual: (a, b, m) => strict.deepEqual(plain(a), plain(b), m)});
const ctx = vm.createContext({URLSearchParams, URL, Intl, Date, console});
vm.runInContext(fs.readFileSync('updates-core.js', 'utf8'), ctx);
const core = name => vm.runInContext(name, ctx);
"""


@unittest.skipUnless(NODE, "Node.js is required for the update page logic")
class PageLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stack = contextlib.ExitStack()
        root = Path(cls._stack.enter_context(tempfile.TemporaryDirectory()))
        history = su.build_history(root / "history")
        cls.feed = json.loads(history["register3"].read_text(encoding="utf-8"))
        cls.index = json.loads((history["r3"] / "index.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls._stack.close()

    def node(self, script, **data):
        prelude = "const DATA = " + json.dumps(data, ensure_ascii=False) + ";\n"
        result = subprocess.run([NODE, "-e", NODE_CORE + prelude + script], cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            self.fail(result.stderr[-3000:])

    def test_one_row_per_entry_with_its_latest_event_and_no_removed_entries(self):
        self.node(r"""
const rows = core('latestUpdates')(DATA.feed, DATA.index);
const ids = rows.map(row => row.event.entry);
assert.equal(new Set(ids).size, ids.length);
assert.ok(!ids.includes('kcd-1-2001--K2'), 'removed entry must not be shown');
const k1 = rows.find(row => row.event.entry === 'kcd-1-2001--K1');
assert.equal(k1.event.release_id, 'test-r3');
// Same program on two CDs stays two rows.
assert.deepEqual(rows.filter(row => row.summary.software_name === 'Winamp').map(row => row.event.entry), ['K37', 'kcd-8-2001--K5']);
// Newest first, then entry id in code-point order.
assert.deepEqual(ids, ['K37', 'kcd-1-2001--K1', 'kcd-8-2001--K5', 'K3', 'kcd-8-2001--K1', 'kcd-8-2001--K2', 'kcd-9-2000--K7']);
const shuffled = {...DATA.feed, events: [...DATA.feed.events].reverse()};
assert.deepEqual(core('latestUpdates')(shuffled, DATA.index).map(row => row.event.entry), ids);
""", feed=self.feed, index=self.index)

    def test_explanations_are_concrete_and_honest(self):
        self.node(r"""
const explain = core('updateExplanation');
const summaries = Object.fromEntries(DATA.index.entries.map(s => [s.entry, s]));
const event = (entry, changes, type = 'updated') => ({entry, type, changes, published_at: '2026-01-01T00:00:00Z'});
assert.equal(explain(event('K3', ['identified', 'name_added', 'version_added', 'content_kind_added', 'distribution_kind_added']), summaries['K3']),
  'Programnavn og versjon avklart. Innholdstype avklart: program. Utgave avklart: prøveversjon.');
assert.equal(explain(event('kcd-8-2001--K1', ['identified', 'name_added']), summaries['kcd-8-2001--K1']),
  'Program identifisert, versjonen er fortsatt ukjent.');
const unknown = {...summaries['K37'], version: 'unknown'};
assert.equal(explain(event('K37', ['name_changed', 'version_removed']), unknown), 'Programnavn endret. Versjonen er ikke lenger oppgitt.');
assert.ok(!/avklart/.test(explain(event('K37', ['version_removed']), unknown)));
assert.equal(explain(event('K37', ['version_changed']), summaries['K37']), 'Versjon endret: 2.77.');
assert.equal(explain(event('x', ['source_document_added']), summaries['kcd-8-2001--K2']), 'Vedlagt originaltekst lagt til.');
assert.equal(explain(event('x', ['description_changed', 'screenshot_changed']), summaries['kcd-1-2001--K1']), 'Omtale endret. Skjermbilde byttet.');
assert.equal(explain(event('x', [], 'added'), summaries['kcd-9-2000--K7']), 'Ny kildepost i arkivet.');
// Every code has a phrase.
for (const code of core('UPDATE_CODES')) if (code !== 'identified') assert.ok(core('UPDATE_PHRASES')[code], code);
""", index=self.index)

    def test_codes_match_the_python_contract(self):
        self.node("assert.deepEqual(core('UPDATE_CODES'), DATA.codes);", codes=list(pu.CHANGE_CODES))

    def test_names_never_show_ids_or_hashes(self):
        self.node(r"""
const name = core('updateName');
assert.equal(name({entry: 'kcd-1-2001--Tool3a', software_name: null, editorial_title: null}), 'Kildepost uten navn i CD-menyen');
assert.equal(name({entry: 'K3', software_name: null, editorial_title: 'Menytittel'}), 'Menytittel');
assert.equal(name({entry: 'K3', software_name: 'Testkatt', editorial_title: 'Menytittel'}), 'Testkatt');
""")

    def test_dates_are_norwegian_in_oslo_around_midnight_and_summer_time(self):
        self.node(r"""
const format = core('formatUpdateDate');
assert.equal(format('2026-03-28T23:30:00Z'), '29. mars 2026');   // CET, the night summer time starts
assert.equal(format('2026-03-28T22:59:59Z'), '28. mars 2026');
assert.equal(format('2026-10-24T22:30:00Z'), '25. oktober 2026'); // CEST, the night summer time ends
assert.equal(format('2026-10-24T21:59:59Z'), '24. oktober 2026');
assert.equal(format('2026-12-31T23:00:00Z'), '1. januar 2027');
""")

    def test_filters_and_search_cover_the_whole_dataset(self):
        self.node(r"""
const rows = core('latestUpdates')(DATA.feed, DATA.index);
const filter = core('filterUpdates');
assert.deepEqual(filter(rows, 'added', '').map(r => r.event.entry), ['kcd-9-2000--K7']);
assert.equal(filter(rows, 'updated', '').length, 6);
assert.deepEqual(filter(rows, 'all', 'winamp').map(r => r.event.entry), ['K37', 'kcd-8-2001--K5']);
assert.deepEqual(filter(rows, 'updated', 'k-cd 8/2001').map(r => r.event.entry), ['kcd-8-2001--K5', 'kcd-8-2001--K1', 'kcd-8-2001--K2']);
assert.deepEqual(filter(rows, 'added', 'winamp'), []);
assert.deepEqual(JSON.parse(JSON.stringify(core('updateParameters')('?type=added&q=Win'))), {type: 'added', query: 'Win'});
assert.equal(core('updateParameters')('?type=deleted').type, 'all');
assert.equal(core('updateSearch')('updated', ' kcd '), '?type=updated&q=kcd');
assert.equal(core('updateSearch')('all', ''), '');
""", feed=self.feed, index=self.index)

    def test_feed_validation_and_loading_states(self):
        self.node(r"""
const problem = core('updatesProblem');
assert.equal(problem(DATA.feed), null);
const bad = JSON.parse(JSON.stringify(DATA.feed)); bad.events[0].changes = ['faster'];
assert.match(problem(bad), /endringskode/);
assert.match(problem({schema: 'x'}), /skjema/);
const load = core('loadUpdates');
(async () => {
  const calls = [];
  const fetcher = status => async (url, options) => { calls.push(options); return {status, ok: status === 200, json: async () => DATA.feed}; };
  assert.equal(await load(fetcher(404)), null);
  assert.equal((await load(fetcher(200))).schema, 'bootdisk-public-updates-v1');
  await assert.rejects(load(fetcher(500)), /HTTP 500/);
  await assert.rejects(load(async () => ({status: 200, ok: true, json: async () => { throw new SyntaxError('x'); }})), /ikke gyldig JSON/);
  assert.ok(calls.every(options => options.cache === 'no-cache'));
})().catch(error => { console.error(error); process.exit(1); });
""", feed=self.feed)

    def test_five_thousand_rows_filter_quickly(self):
        self.node(r"""
const summaries = [], events = [];
for (let i = 0; i < 5000; i++) {
  const entry = `provecd-${i % 10}-1999--K${i}`;
  summaries.push({entry, software_name: `Prøveprogram ${i}`, medium: `Prøve-CD ${i % 10}/1999`});
  events.push({entry, release_id: 'r', published_at: '2026-05-01T08:00:00Z', type: i % 5 ? 'updated' : 'added', changes: i % 5 ? ['version_added'] : []});
}
let start = Date.now();
const rows = core('latestUpdates')({events}, {entries: summaries});
for (const query of ['prøveprogram 4999', 'prøve-cd 3', 'finnes ikke', '']) core('filterUpdates')(rows, 'updated', query);
const elapsed = Date.now() - start;
assert.equal(rows.length, 5000);
assert.ok(elapsed < 1000, `took ${elapsed} ms`);
""")


if __name__ == "__main__":
    unittest.main()
