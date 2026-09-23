"""Front page, collection registry and collection pages without a browser.

The build-side checks run the real release builder and HTTP verifier on synthetic
data (tests/synthetic_collection.py); the page logic is exercised in Node against the
same generated index. Browser behaviour is in test_publication_browser.py.
"""
import contextlib
import copy
import functools
import http.server
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from collection_registry import bind_registry, validate_registry  # noqa: E402
import synthetic_collection as synthetic  # noqa: E402

SITEMAP = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
PRODUCTION_REGISTRY = json.loads((ROOT / "collections.json").read_text(encoding="utf-8"))
FICTIONAL = {
    "id": "testbladet-fiktiv",
    "title": "Testbladet (fiktiv)",
    "publication_values": ["TESTBLADET (FIKTIV)"],
    "summary": "Fiktiv testpublikasjon. Finnes ikke og er ikke produksjonsinnhold.",
    "lede": "Fiktiv testpublikasjon for å bevise at en andre samling kan legges til med konfigurasjon.",
    "history": ["Denne teksten er bare testdata."],
    "sources": [],
}


def sitemap_urls(release: Path) -> list[str]:
    return [node.text for node in ET.parse(release / "sitemap.xml").findall(f"{SITEMAP}url/{SITEMAP}loc")]


@contextlib.contextmanager
def serve(directory: Path):
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(directory)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()


def run_node(script: str, **data) -> None:
    prelude = "const DATA = " + json.dumps(data, ensure_ascii=False) + ";\n"
    subprocess.run([shutil.which("node"), "-e", prelude + script], cwd=ROOT, check=True)


NODE_CORE = r"""
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const ctx = vm.createContext({URLSearchParams, URL});
vm.runInContext(fs.readFileSync('collection-core.js', 'utf8'), ctx);
const core = name => vm.runInContext(name, ctx);
"""


class RegistryTests(unittest.TestCase):
    def test_production_registry_is_valid_and_names_komputer_for_alle(self):
        validate_registry(PRODUCTION_REGISTRY)
        [collection] = PRODUCTION_REGISTRY["collections"]
        self.assertEqual(collection["id"], "komputer-for-alle")
        self.assertEqual(collection["publication_values"], ["KOMPUTER FOR ALLE"])
        words = len(" ".join([collection["lede"], *collection["history"]]).split())
        self.assertGreaterEqual(words, 150)
        self.assertLessEqual(words, 300)

    def test_registry_text_carries_no_counts(self):
        """Counts come from data: an eighth CD must not make the editorial text wrong."""
        text = json.dumps(PRODUCTION_REGISTRY, ensure_ascii=False)
        for forbidden in ("178", "sju CD", "7 CD", "39 ", "gratisprogram", "fullversjon"):
            self.assertNotIn(forbidden, text)

    def test_invalid_registries_are_rejected_with_a_reason(self):
        cases = {
            "used more than once": lambda r: r["collections"].append(copy.deepcopy(r["collections"][0]) | {"publication_values": ["X"]}),
            "bound to both": lambda r: r["collections"].append(copy.deepcopy(FICTIONAL) | {"publication_values": ["KOMPUTER FOR ALLE"]}),
            "lowercase slug": lambda r: r["collections"][0].update(id="../komputer"),
            "invalid source link": lambda r: r["collections"][0]["sources"].append({"label": "x", "href": "javascript:alert(1)"}),
            "publication_values": lambda r: r["collections"][0].update(publication_values=[]),
            "schema": lambda r: r.update(schema="annet"),
        }
        for message, mutate in cases.items():
            with self.subTest(message):
                registry = copy.deepcopy(PRODUCTION_REGISTRY)
                mutate(registry)
                with self.assertRaisesRegex(ValueError, message):
                    validate_registry(registry)

    def test_every_medium_needs_exactly_one_collection(self):
        index = {"schema": "bootdisk-web-collection-1", "publication": "Bootdisk", "medium": "2 CD-er",
                 "media": [{"id": "kcd-1-2000", "publication": "KOMPUTER FOR ALLE", "medium": "K-CD 1/2000"},
                           {"id": "annet-1", "publication": "ANNET BLAD", "medium": "Annet 1/1999"}],
                 "entries": [{"entry": "K26", "medium_id": "kcd-1-2000"}, {"entry": "K13", "medium_id": "kcd-1-2000"},
                             {"entry": "K32", "medium_id": "kcd-1-2000"}, {"entry": "annet-1--K1", "medium_id": "annet-1"}]}
        with self.assertRaisesRegex(ValueError, "'ANNET BLAD', which no collection lists"):
            bind_registry(PRODUCTION_REGISTRY, index)
        index["media"].pop()
        index["entries"].pop()
        self.assertEqual([m["id"] for m in bind_registry(PRODUCTION_REGISTRY, index)["komputer-for-alle"]], ["kcd-1-2000"])
        index["entries"].pop(0)
        with self.assertRaisesRegex(ValueError, "index.html\\?entry=K26.*not in the archive index"):
            bind_registry(PRODUCTION_REGISTRY, index)

    def test_legacy_single_medium_index_binds_by_its_root(self):
        index = {"publication": "KOMPUTER FOR ALLE", "medium": "K-CD 15/2001",
                 "entries": [{"entry": key} for key in ("K13", "K26", "K32", "K37")]}
        [medium] = bind_registry(PRODUCTION_REGISTRY, index)["komputer-for-alle"]
        self.assertEqual((medium["medium"], medium["entries"]), ("K-CD 15/2001", 4))


class SyntheticReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.data, cls.publish = synthetic.build_synthetic(cls.root / "seven")
        cls.release = cls.root / "release"
        result = synthetic.package(cls.data, cls.publish, cls.release)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.index = json.loads((cls.release / "data" / "index.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_release_contains_the_public_pages_and_nothing_private(self):
        published = {path.relative_to(self.release).as_posix() for path in self.release.rglob("*") if path.is_file()}
        for name in ("index.html", "collection.html", "collection.js", "collection-core.js", "landing.js",
                     "publication.css", "collections.json", "archive.html", "app.js"):
            self.assertIn(name, published)
        for path in published:
            self.assertFalse(any(word in path for word in ("curat", "overview", "fixture", "tests/", "sample", "scripts/")), path)
        self.assertEqual(json.loads((self.release / "collections.json").read_text(encoding="utf-8")), PRODUCTION_REGISTRY)

    def test_sitemap_lists_front_page_collection_and_every_detail_link_exactly(self):
        urls = sitemap_urls(self.release)
        self.assertEqual(len(urls), len(set(urls)))
        details = {f"https://bootdisk.no/index.html?entry={entry['entry']}" for entry in self.index["entries"]}
        self.assertEqual(set(urls), {"https://bootdisk.no/", "https://bootdisk.no/archive.html",
                                     "https://bootdisk.no/collection.html?collection=komputer-for-alle", *details})
        self.assertIn("https://bootdisk.no/index.html?entry=K37", urls)
        self.assertIn("https://bootdisk.no/index.html?entry=kcd-1-2001--K37", urls)

    def test_http_verifier_passes_and_catches_a_missing_detail_link_or_a_public_curator(self):
        command = [sys.executable, str(ROOT / "scripts" / "verify-deployment.py")]
        with serve(self.release) as base:
            result = subprocess.run([*command, base, "--expected-entries", str(len(self.index["entries"]))], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("deployment collections: 1", result.stdout)

        broken = self.root / "broken-sitemap"
        shutil.copytree(self.release, broken)
        sitemap = (broken / "sitemap.xml").read_text(encoding="utf-8")
        (broken / "sitemap.xml").write_text(sitemap.replace("<url><loc>https://bootdisk.no/index.html?entry=K37</loc></url>\n", ""), encoding="utf-8")
        with serve(broken) as base:
            result = subprocess.run([*command, base, "--expected-entries", str(len(self.index["entries"]))], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Sitemap URLs do not match", result.stderr)

        leaked = self.root / "leaked-curator"
        shutil.copytree(self.release, leaked)
        shutil.copy2(ROOT / "curate.html", leaked / "curate.html")
        with serve(leaked) as base:
            result = subprocess.run([*command, base, "--expected-entries", str(len(self.index["entries"]))], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Expected HTTP 404", result.stderr)

    def test_unregistered_publication_stops_the_build_with_a_clear_message(self):
        work = self.root / "unregistered"
        data, publish = synthetic.build_synthetic(work, extra=[("testbladet-1", "Testbladet 1/1999", "TESTBLADET (FIKTIV)", ["K1"])])
        result = synthetic.package(data, publish, work / "release")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("'TESTBLADET (FIKTIV)', which no collection lists in publication_values", result.stderr)
        self.assertFalse((work / "release").exists())

    def test_invalid_registry_json_stops_the_build(self):
        registry = self.root / "invalid.json"
        registry.write_text("{ not json", encoding="utf-8")
        result = synthetic.package(self.data, self.publish, self.root / "invalid-release", registry)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is not valid JSON", result.stderr)

    def test_second_fictional_publication_is_configuration_not_code(self):
        work = self.root / "two-publications"
        data, publish = synthetic.build_synthetic(work, extra=[
            ("testbladet-2-1999", "Testbladet 2/1999", "TESTBLADET (FIKTIV)", ["K1", "K2"]),
            ("testbladet-10-1999", "Testbladet 10/1999", "TESTBLADET (FIKTIV)", ["K1"])])
        registry = copy.deepcopy(PRODUCTION_REGISTRY)
        registry["collections"].append(FICTIONAL)
        registry_path = work / "collections.json"
        registry_path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
        result = synthetic.package(data, publish, work / "release", registry_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        urls = sitemap_urls(work / "release")
        self.assertIn("https://bootdisk.no/collection.html?collection=testbladet-fiktiv", urls)
        self.assertIn("https://bootdisk.no/collection.html?collection=komputer-for-alle", urls)
        bound = bind_registry(registry, json.loads((work / "release/data/index.json").read_text(encoding="utf-8")))
        self.assertEqual([m["id"] for m in bound["testbladet-fiktiv"]], ["testbladet-2-1999", "testbladet-10-1999"])
        self.assertEqual(len(bound["komputer-for-alle"]), 7)

    def test_legacy_single_medium_projection_still_packages(self):
        work = self.root / "legacy"
        synthetic.write_medium(work / "inputs", work / "publish", "kcd-15-2001", "K-CD 15/2001", ["K13", "K26", "K32", "K37"])
        data = work / "inputs" / "kcd-15-2001"
        result = synthetic.package(data, work / "publish", work / "release")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("https://bootdisk.no/collection.html?collection=komputer-for-alle", sitemap_urls(work / "release"))

    @unittest.skipUnless(shutil.which("node"), "Node required")
    def test_collection_view_counts_sorts_and_groups_from_the_index_alone(self):
        run_node(NODE_CORE + r"""
const view = core('collectionView')(DATA.registry, DATA.index, DATA.registry.collections[0]);
assert.deepEqual(Array.from(view.media, m => m.label),
  ['K-CD 15/2001', 'K-CD 8/2001', 'K-CD 1/2001', 'K-CD 13/2000', 'K-CD 9/2000', 'K-CD 4/2000', 'K-CD 1/2000']);
assert.deepEqual(Array.from(view.years, y => y.year), [2001, 2000]);
assert.equal(view.entryCount, DATA.index.entries.length);
const counts = Object.fromEntries(view.media.map(m => [m.id, m.count]));
assert.deepEqual(counts, {'kcd-15-2001': 6, 'kcd-8-2001': 4, 'kcd-1-2001': 5, 'kcd-13-2000': 3, 'kcd-9-2000': 2, 'kcd-4-2000': 2, 'kcd-1-2000': 3});
// Same program on two discs: two source entries, one on each disc.
assert.equal(DATA.index.entries.filter(e => e.software_name === 'Winamp').length, 2);
assert.equal(view.media.find(m => m.id === 'kcd-13-2000').href, 'archive.html?medium=kcd-13-2000');
assert.equal(core('publishedCollections')(DATA.registry, DATA.index).length, 1);
""", registry=PRODUCTION_REGISTRY, index=self.index)

    @unittest.skipUnless(shutil.which("node"), "Node required")
    def test_an_eighth_disc_appears_without_code_changes(self):
        work = self.root / "eight"
        data, publish = synthetic.build_synthetic(work, extra=[("kcd-5-2001", "K-CD 5/2001", synthetic.PUBLICATION, ["K1", "K2"])])
        result = synthetic.package(data, publish, work / "release")
        self.assertEqual(result.returncode, 0, result.stderr)
        index = json.loads((work / "release/data/index.json").read_text(encoding="utf-8"))
        run_node(NODE_CORE + r"""
const view = core('collectionView')(DATA.registry, DATA.index, DATA.registry.collections[0]);
assert.equal(view.media.length, 8);
assert.deepEqual(Array.from(view.years[0].media, m => m.label), ['K-CD 15/2001', 'K-CD 8/2001', 'K-CD 5/2001', 'K-CD 1/2001']);
assert.equal(view.entryCount, 27);
""", registry=PRODUCTION_REGISTRY, index=index)


@unittest.skipUnless(shutil.which("node"), "Node required")
class CollectionCoreTests(unittest.TestCase):
    def test_issue_numbers_sort_numerically_and_are_not_months(self):
        run_node(NODE_CORE + r"""
const labels = ['K-CD 9/2000', 'K-CD 13/2000', 'K-CD 1/2001', 'K-CD 15/2001', 'K-CD 8/2001', 'K-CD 4/2000', 'K-CD 1/2000'];
const sorted = labels.map(label => ({label})).sort(core('compareMedia')).map(m => m.label);
assert.deepEqual(sorted, ['K-CD 15/2001', 'K-CD 8/2001', 'K-CD 1/2001', 'K-CD 13/2000', 'K-CD 9/2000', 'K-CD 4/2000', 'K-CD 1/2000']);
assert.deepEqual({...core('parseIssue')('K-CD 13/2000')}, {issue: 13, year: 2000});
assert.equal(core('parseIssue')('Spesialutgave'), null);
// Unparseable labels go last, in natural order, instead of disappearing.
const mixed = [{label: 'Ekstra-CD 10'}, {label: 'K-CD 2/1999'}, {label: 'Ekstra-CD 9'}].sort(core('compareMedia')).map(m => m.label);
assert.deepEqual(mixed, ['K-CD 2/1999', 'Ekstra-CD 9', 'Ekstra-CD 10']);
""")

    def test_registry_and_index_problems_are_reported_not_zeroed(self):
        run_node(NODE_CORE + r"""
const registryProblem = core('registryProblem'), indexProblem = core('indexProblem');
assert.equal(registryProblem(DATA.registry), null);
assert.match(registryProblem(null), /ikke et objekt/);
assert.match(registryProblem({schema: 'bootdisk-web-collections-1', collections: []}), /ingen samlinger/);
const twice = structuredClone(DATA.registry); twice.collections.push({...twice.collections[0], id: 'kopi'});
assert.match(registryProblem(twice), /koblet til flere samlinger/);
const unsafe = structuredClone(DATA.registry); unsafe.collections[0].sources.push({label: 'x', href: 'javascript:alert(1)'});
assert.match(registryProblem(unsafe), /ugyldig kildelenke/);
assert.match(indexProblem([]), /ikke et objekt/);
assert.match(indexProblem({entries: 'x'}), /mangler kildeposter/);
assert.match(indexProblem({schema: 'bootdisk-web-collection-1', media: [{id: '../x', publication: 'A', medium: 'B'}], entries: []}), /ugyldig ID/);
assert.match(indexProblem({schema: 'bootdisk-web-collection-1', media: [], entries: [{entry: 'K1', medium_id: 'x'}]}), /ukjent medium/);
""", registry=PRODUCTION_REGISTRY)

    def test_unknown_publications_and_unsafe_ids_never_select_a_collection(self):
        run_node(NODE_CORE + r"""
const index = {schema: 'bootdisk-web-collection-1', publication: 'Bootdisk', medium: '2 CD-er',
  media: [{id: 'kcd-1-2000', publication: 'KOMPUTER FOR ALLE', medium: 'K-CD 1/2000'},
          {id: 'annet-1', publication: 'ANNET BLAD', medium: 'Annet 1/1999'}],
  entries: [{entry: 'kcd-1-2000--K1', medium_id: 'kcd-1-2000'}, {entry: 'annet-1--K1', medium_id: 'annet-1'}]};
const kfa = DATA.registry.collections[0];
const view = core('collectionView')(DATA.registry, index, kfa);
assert.deepEqual(Array.from(view.media, m => m.id), ['kcd-1-2000']);
assert.equal(view.entryCount, 1);
for (const id of [null, '', '../komputer-for-alle', 'KOMPUTER-FOR-ALLE', '<script>', 'finnes-ikke'])
  assert.equal(core('collectionById')(DATA.registry, id), null, String(id));
assert.equal(core('collectionById')(DATA.registry, 'komputer-for-alle'), kfa);
// A single-medium 1.0 index is one medium whose content is the whole archive.
const legacy = core('indexMedia')({publication: 'KOMPUTER FOR ALLE', medium: 'K-CD 15/2001', entries: [{entry: 'K1'}, {entry: 'K2'}]});
assert.deepEqual(JSON.parse(JSON.stringify(legacy)), [{id: null, publication: 'KOMPUTER FOR ALLE', label: 'K-CD 15/2001', count: 2, href: 'archive.html'}]);
""", registry=PRODUCTION_REGISTRY)

    def test_entry_breadcrumbs_name_collection_disc_and_entry(self):
        run_node(r"""
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const ctx = vm.createContext({URLSearchParams, URL, window: {location: {search: ''}}});
vm.runInContext(fs.readFileSync('collection-core.js', 'utf8'), ctx);
vm.runInContext(fs.readFileSync('app.js', 'utf8').split('async function render()')[0], ctx);
const trail = (entry, registry) => JSON.parse(JSON.stringify(ctx.breadcrumbTrail(entry, 'WinZip', registry)));
assert.equal(ctx.requestedEntry(), null, 'no entry parameter is the front page, not a redirect');
const entry = {entry: 'kcd-1-2001--K37', publication: 'KOMPUTER FOR ALLE', medium: 'K-CD 1/2001', medium_id: 'kcd-1-2001'};
assert.deepEqual(trail(entry, DATA.registry), [
  {label: 'Bootdisk', href: './'}, {label: 'Komputer for alle', href: 'collection.html?collection=komputer-for-alle'},
  {label: 'K-CD 1/2001', href: 'archive.html?medium=kcd-1-2001'}, {label: 'WinZip', href: null}]);
assert.equal(trail(entry, null)[1].href, 'archive.html', 'without the registry the archive is the parent');
assert.equal(trail({...entry, publication: 'ANNET'}, DATA.registry)[1].label, 'Alle kildeposter');
for (const input of ['', '../x', 'kcd-1-2001--../K1', '<b>']) {
  ctx.window.location.search = '?entry=' + encodeURIComponent(input);
  assert.throws(() => ctx.requestedEntry(), undefined, input);
}
""".replace("DATA.registry", json.dumps(PRODUCTION_REGISTRY, ensure_ascii=False)))


class PublicPageSourceTests(unittest.TestCase):
    def test_new_pages_render_source_values_as_text(self):
        for name in ("collection-core.js", "collection.js", "landing.js", "archive.js", "app.js"):
            source = (ROOT / name).read_text(encoding="utf-8")
            for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
                self.assertNotIn(forbidden, source, f"{name} uses {forbidden}")

    def test_pages_do_not_hardcode_disc_cards_or_counts(self):
        for name in ("index.html", "collection.html", "collection.js", "landing.js", "collection-core.js"):
            source = (ROOT / name).read_text(encoding="utf-8")
            for forbidden in ("178", "K-CD 13/2000", "kcd-13-2000", "K-CD 15/2001</", "kcd", "fetch(`data/${"):
                self.assertNotIn(forbidden, source, f"{name} contains {forbidden}")

    def test_front_page_metadata_and_states(self):
        index = (ROOT / "index.html").read_text(encoding="utf-8")
        collection = (ROOT / "collection.html").read_text(encoding="utf-8")
        self.assertIn('<link id="canonical-url" rel="canonical" href="https://bootdisk.no/">', index)
        self.assertIn('<meta id="og-url" property="og:url" content="https://bootdisk.no/">', index)
        for html in (index, collection):
            self.assertIn("<noscript>", html)
            self.assertIn('class="skip-link" href="#main-content"', html)
            self.assertIn('href="accessibility.css"', html)
        self.assertNotIn('rel="canonical"', collection, "the collection canonical depends on the query and is set by script")
        self.assertIn('href="archive.html">Alle kildeposter</a>', index)


if __name__ == "__main__":
    unittest.main()
