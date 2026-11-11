"""Archive filtering by content type and CD year, and the new sort orders.

See docs/archive-sort-filter.md. Logic is checked in Node against archive.js itself,
the index extension against the real build scripts, and the page in Chromium against
PRØVEDATA from tests/synthetic_archive.py. None of that says anything about the real
archive; the opt-in RealArchiveAcceptance class does, when BOOTDISK_ARCHIVE_DATA points
to a built data directory (for example Birk's rc27 data):

    BOOTDISK_ARCHIVE_DATA=/path/to/release/data python -m unittest tests.test_archive_sort_filter -v
"""
import contextlib
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import archive_index  # noqa: E402
import public_updates  # noqa: E402
import synthetic_archive  # noqa: E402
from frontend_contract import validate_frontend_data  # noqa: E402
from test_publication import serve  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment dependent
    sync_playwright = None

NODE = shutil.which("node")
NODE_PRELUDE = r"""
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const ctx = vm.createContext({URLSearchParams, Intl});
vm.runInContext(fs.readFileSync('collection-core.js', 'utf8'), ctx);
vm.runInContext(fs.readFileSync('archive.js', 'utf8').split('function fillOptions(')[0], ctx);
const js = name => vm.runInContext(name, ctx);
"""

# Cases for the type rule, as index rows: (row, expected kind, expected basis).
KIND_CASES = [
    ({"content_kind": "game"}, "game", "catalog"),
    ({"content_kind": "game", "menu_groups": ["KProgram"]}, "game", "catalog"),
    ({"content_kind": "application", "menu_groups": ["Spil"]}, "application", "catalog"),
    ({"menu_groups": ["Spill"]}, "game", "menu"),
    ({"menu_groups": ["Spil"]}, "game", "menu"),
    ({"menu_groups": ["games"]}, "game", "menu"),
    ({"menu_groups": ["Spil", "Barn"]}, "game", "menu"),
    ({"menu_groups": ["Spill", "games"]}, "game", "menu"),
    ({"menu_groups": ["Skole"]}, "course", "menu"),
    ({"menu_groups": ["Videokurs"]}, "course", "menu"),
    ({"menu_groups": ["KProgram"]}, "application", "menu"),
    ({"menu_groups": ["programs"]}, "application", "menu"),
    ({"menu_groups": ["Software", "KProgram"]}, "application", "menu"),
    ({"menu_groups": ["Artikler"]}, "article", "menu"),
    ({"menu_groups": ["KProgram", "Spil"]}, "unknown", "conflict"),
    ({"menu_groups": ["Skole", "games"]}, "unknown", "conflict"),
    ({"menu_groups": ["Demoer"]}, "unknown", "none"),
    ({"menu_groups": ["Demoer"], "distribution_kind": "demo"}, "unknown", "none"),
    ({"menu_groups": ["Barn"]}, "unknown", "none"),
    ({"menu_groups": ["Bonus"]}, "unknown", "none"),
    ({"menu_groups": ["Aktuelt"]}, "unknown", "none"),
    ({"menu_groups": []}, "unknown", "none"),
    ({}, "unknown", "none"),
    ({"menu_groups": ["spill"]}, "unknown", "none"),  # exact source values only
    ({"content_kind": "article", "menu_groups": ["Demoer"]}, "unknown", "none"),  # not a Catalog kind
    ({"content_kind": "made_up"}, "unknown", "none"),
    ({"content_kind": None, "menu_groups": ["Galleri"]}, "unknown", "none"),
    ({"editorial_title": "Super Spill 2000", "menu_groups": ["Demoer"]}, "unknown", "none"),  # never from the title
]


def node(script, **data):
    prelude = "const DATA = " + json.dumps(data, ensure_ascii=False) + ";\n"
    subprocess.run([NODE, "-e", NODE_PRELUDE + prelude + script], cwd=ROOT, check=True)


def row(entry, medium, order, title, **extra):
    return {"entry": entry, "medium": medium, "medium_id": medium, "source_order": order, "editorial_title": title,
            "curation_status": "pending", **extra}


@unittest.skipUnless(NODE, "Node.js is required for the archive logic tests")
class ArchiveLogicTests(unittest.TestCase):
    def test_type_rule_matches_the_python_report(self):
        for case, kind, basis in KIND_CASES:
            self.assertEqual(archive_index.archive_kind(case), (kind, basis), case)
        node("""
for (const [entry, kind, basis] of DATA.cases) {
  const result = js('archiveKind')(entry);
  assert.deepEqual([result.kind, result.basis], [kind, basis], JSON.stringify(entry));
}""", cases=KIND_CASES)

    def test_labels_show_the_basis_and_keep_the_edition(self):
        node("""
const label = js('contentLabel');
assert.equal(label({content_kind: 'game', distribution_kind: 'full'}), 'Spill, fullversjon');
assert.equal(label({menu_groups: ['Spil']}), 'Spill (CD-meny)');
assert.equal(label({menu_groups: ['Skole']}), 'Kurs / veiledning (CD-meny)');
assert.equal(label({menu_groups: ['Demoer'], distribution_kind: 'demo'}), 'Demo');
assert.equal(label({menu_groups: ['KProgram', 'Spil']}), null);
assert.equal(label({}), null);
""")

    def test_sorting_orders_but_never_changes_the_set(self):
        rows = [
            row("a", "K-CD 2/2001", 0, "Prøvepost: Samme navn", menu_groups=["KProgram"]),
            row("b", "K-CD 10/2001", 1, "Prøvepost: Samme navn", menu_groups=["Software"]),
            row("c", "K-CD 2/2001", 2, "Prøvepost: Ærfugl", menu_groups=["Spil"]),
            row("d", "K-CD 5/2000", 3, "Prøvepost: Åpent", menu_groups=["Spill"]),
            row("e", "Uten år", 4, "Prøvepost: Øving", menu_groups=["games"]),
            row("f", "K-CD 10/2001", 5, "Prøvepost: Zebra", content_kind="game"),
            row("g", "K-CD 1/2013", 6, "Prøvepost: Aktuelt", menu_groups=["Aktuelt"]),
            row("h", "K-CD 2/2001", 7, "Prøvepost: Bok", menu_groups=["Skole"]),
            row("i", "K-CD 10/2001", 8, "Prøvepost: Konflikt", menu_groups=["Spil", "KProgram"]),
        ]
        node("""
const sort = (s, rows = DATA.rows) => Array.from(js('sortEntries')(rows, s), e => e.entry);
assert.deepEqual(sort('source'), ['a','b','c','d','e','f','g','h','i']);
// Navn A–Å: Z, Æ, Ø, Å in Norwegian order; equal names keep source order.
assert.deepEqual(sort('name'), ['g','h','i','a','b','f','c','e','d']);
// CD-år: issue 10 before 2 newest first, 2 before 10 oldest first, source order within a CD,
// and the CD without a year last both ways.
assert.deepEqual(sort('year-desc'), ['g','b','f','i','a','c','h','d','e']);
assert.deepEqual(sort('year-asc'), ['d','a','c','h','b','f','i','g','e']);
// Innholdstype A–Å: Kurs, Program, Spill; title within a type; unknown last.
assert.deepEqual(sort('type'), ['h','a','b','f','c','e','d','g','i']);
for (const s of ['source','name','type','year-desc','year-asc','nonsense'])
  assert.deepEqual([...sort(s)].sort(), DATA.rows.map(r => r.entry).sort(), s);
// Stable whatever order the input has.
const reversed = [...DATA.rows].reverse();
for (const s of ['name','type','year-desc','year-asc']) assert.deepEqual(sort(s, reversed), sort(s), s);
""", rows=rows)

    def test_type_sort_puts_titles_in_norwegian_order(self):
        rows = [row("a", "K-CD 1/2001", 0, "Prøvepost: Åpent", menu_groups=["Spil"]),
                row("b", "K-CD 1/2001", 1, "Prøvepost: Ærfugl", menu_groups=["Spil"]),
                row("c", "K-CD 1/2001", 2, "Prøvepost: Zebra", menu_groups=["Spil"]),
                row("d", "K-CD 1/2001", 3, "Prøvepost: Øving", menu_groups=["Spil"])]
        node("assert.deepEqual(Array.from(js('sortEntries')(DATA.rows, 'type'), e => e.entry), ['c','b','d','a']);", rows=rows)

    def test_filters_combine_and_options_come_from_the_data(self):
        rows = [
            row("a", "K-CD 2/2001", 0, "Prøvepost: Kurs", menu_groups=["Skole"]),
            row("b", "K-CD 10/2001", 1, "Prøvepost: Kurs to", content_kind="course", curation_status="identified"),
            row("c", "K-CD 5/2000", 2, "Prøvepost: Kurs gammel", menu_groups=["Videokurs"]),
            row("d", "Uten år", 3, "Prøvepost: Ukjent", menu_groups=["Demoer"]),
            row("e", "K-CD 2/2001", 4, "Prøvepost: Artikkel", menu_groups=["Artikler"]),
        ]
        node("""
const ids = (...args) => Array.from(js('filterEntries')(DATA.rows, ...args), e => e.entry);
assert.deepEqual(ids('', 'all', 'all', 'course', '2001'), ['a','b']);
assert.deepEqual(ids('to', 'all', 'all', 'course', '2001'), ['b']);
assert.deepEqual(ids('', 'pending', 'all', 'course', '2001'), ['a']);
assert.deepEqual(ids('', 'all', 'K-CD 2/2001', 'course', 'all'), ['a']);
assert.deepEqual(ids('', 'all', 'all', 'unknown', 'all'), ['d']);
assert.deepEqual(ids('', 'all', 'all', 'all', 'unknown'), ['d']);
assert.deepEqual(ids('', 'all', 'all', 'game', 'all'), []);
const types = Array.from(js('archiveTypeOptions')(DATA.rows), o => o.label);
assert.deepEqual(types, ['Program', 'Spill', 'Kurs / veiledning', 'Artikkel', 'Ikke oppgitt']);
const years = Array.from(js('archiveYearOptions')(DATA.rows), o => o.value);
assert.deepEqual(years, ['2001', '2000', 'unknown']);
assert.equal(js('archiveTypeParameter')('game'), 'game');
assert.equal(js('archiveTypeParameter')('spill'), null);
assert.equal(js('archiveTypeParameter')('toString'), null);
assert.equal(js('archiveYearParameter')('2001'), '2001');
assert.equal(js('archiveYearParameter')('20O1'), null);
assert.equal(js('archiveSortParameter')('name'), 'name');
assert.equal(js('archiveSortParameter')('year-desc'), 'year-desc');
assert.equal(js('archiveSortParameter')('bogus'), 'source');
""", rows=rows)


def load_builder(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def file_hashes(root: Path, skip=("index.json",)):
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(root.iterdir()) if path.is_file() and path.name not in skip}


class ArchiveIndexBuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_build_projects_the_menu_groups_of_each_entry(self):
        synthetic_archive.build(self.root / "release")
        index = json.loads((self.root / "release/data/index.json").read_text(encoding="utf-8"))
        for summary in index["entries"]:
            document = json.loads((self.root / "release/data" / f"{summary['entry'].lower()}.json").read_text(encoding="utf-8"))
            observed = document["source_context"].get("menu_groups")
            if observed is None:
                self.assertNotIn("menu_groups", summary)
            else:
                self.assertEqual(summary["menu_groups"], observed["value"])
        self.assertTrue(any("menu_groups" not in summary for summary in index["entries"]), "a row without the observation stays without it")

    def test_contract_rejects_menu_groups_that_differ_from_the_entry(self):
        synthetic_archive.build(self.root / "release")
        data = self.root / "release/data"
        index = json.loads((data / "index.json").read_text(encoding="utf-8"))
        row = next(summary for summary in index["entries"] if summary.get("menu_groups") == ["Demoer"])
        row["menu_groups"] = ["Spill"]
        (data / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "menu_groups differ"):
            validate_frontend_data(data)
        row["menu_groups"] = ["Demoer"]
        missing = next(summary for summary in index["entries"] if "menu_groups" not in summary)
        missing["menu_groups"] = []
        (data / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "menu_groups differ"):
            validate_frontend_data(data)

    def test_extending_an_old_index_changes_only_the_index_and_no_published_history(self):
        import synthetic_catalog
        synthetic_catalog.build(self.root / "release", entries=120, media=5)
        old = self.root / "release/data"
        index = json.loads((old / "index.json").read_text(encoding="utf-8"))
        self.assertFalse(any("menu_groups" in summary for summary in index["entries"]), "the fixture is an old index")
        register = public_updates.load_register(old / "public-updates.json")
        before_print = public_updates.fingerprint(public_updates.load_projection(old))
        _, extended = archive_index.extend(old, self.root / "extended")
        new = self.root / "extended"
        self.assertEqual(len(extended["entries"]), len(index["entries"]))
        self.assertEqual(file_hashes(new), file_hashes(old), "entry documents and update history are byte-identical")
        for before, after in zip(index["entries"], extended["entries"]):
            self.assertEqual({k: v for k, v in after.items() if k != "menu_groups"}, before)
            self.assertIn("menu_groups", after)
        self.assertEqual(public_updates.fingerprint(public_updates.load_projection(new)), before_print, "no update events from a view change")
        public_updates.validate_register(register, extended, before_print)
        with self.assertRaisesRegex(ValueError, "new directory"):
            archive_index.extend(old, new)

    def test_appending_posts_extends_the_rows_already_published(self):
        appender = load_builder("append_posts", "append-source-posts.py")
        synthetic_archive.build(self.root / "release")
        base = self.root / "base"
        shutil.copytree(self.root / "release/data", base)
        index = json.loads((base / "index.json").read_text(encoding="utf-8"))
        for summary in index["entries"]:
            summary.pop("menu_groups", None)  # as published before this change
        (base / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        # One supplemental source post on an existing CD.
        extra = self.root / "extra"
        extra.mkdir()
        manifest = "sha256:" + "e" * 64
        key = {"entry": "Spil9", "manifest": manifest}
        document = {"entry": "Spil9", "publication": synthetic_archive.PUBLICATION, "medium": "K-CD 2/2001",
                    "editorial_title": "Prøvepost: Tillegg", "curation_status": "pending", "software": [],
                    "assets": [{"entry": "Spil9", "kind": "icon", "source_path": "x.png",
                                "original": {"public_path": "store/x.png", "sha256": "f" * 64}, "derivatives": []}],
                    "source_context": {"key": key, "description": {"source_ref": key, "value": "PRØVEDATA"},
                                       "menu_groups": {"source_ref": key, "value": ["games"]}}}
        (extra / "spil9.json").write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        (extra / "index.json").write_text(json.dumps({"publication": synthetic_archive.PUBLICATION, "medium": "K-CD 2/2001",
                                                      "entries": [{"entry": "Spil9", "curation_status": "pending"}]}), encoding="utf-8")
        (self.root / "extra.json").write_text(json.dumps({"media": [{"id": "kcd-2-2001", "data": str(extra)}]}), encoding="utf-8")
        result = appender.append_posts(base, self.root / "extra.json", self.root / "out")
        rows = {summary["entry"]: summary for summary in result["entries"]}
        self.assertEqual(rows["kcd-2-2001--Spil9"]["menu_groups"], ["games"])
        self.assertEqual(rows["kcd-2-2001--K1"]["menu_groups"], ["Spil"])
        validate_frontend_data(self.root / "out")


@unittest.skipUnless(sync_playwright, "Playwright is required for the browser checks")
class ArchiveBrowserTests(unittest.TestCase):
    """PRØVEDATA in Chromium. Not the real archive."""

    @classmethod
    def setUpClass(cls):
        cls._stack = contextlib.ExitStack()
        work = Path(cls._stack.enter_context(tempfile.TemporaryDirectory()))
        synthetic_archive.build(work / "release")
        cls.index = json.loads((work / "release/data/index.json").read_text(encoding="utf-8"))
        cls.base = cls._stack.enter_context(serve(work / "release")).rstrip("/")
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
    def page(self, path, width=1280, height=900, old_index=False):
        context = self.browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        problems, requests = [], []
        page.on("pageerror", lambda error: problems.append(str(error)))
        page.on("console", lambda message: message.type == "error" and problems.append(message.text))
        page.on("request", lambda request: requests.append(request.url))
        if old_index:
            stripped = {**self.index, "entries": [{k: v for k, v in e.items() if k != "menu_groups"} for e in self.index["entries"]]}
            page.route("**/data/index.json", lambda route: route.fulfill(status=200, content_type="application/json",
                                                                         body=json.dumps(stripped, ensure_ascii=False)))
        page.requests = requests
        page.goto(self.base + path, wait_until="networkidle")
        page.wait_for_selector("#archive-count:not(:empty)")
        try:
            yield page
            self.assertEqual(problems, [], "console or script errors")
        finally:
            context.close()

    def rows(self, page):
        return page.eval_on_selector_all(".archive-table tbody tr", """rows => rows.map(r => ({
            title: r.querySelector('.archive-card').textContent, href: r.querySelector('.archive-card').getAttribute('href'),
            medium: r.cells[1].textContent, year: r.cells[2].textContent, kind: r.cells[3].textContent}))""")

    def test_only_games_newest_cd_first_then_a_to_z_keeps_the_same_games(self):
        with self.page("/archive.html?type=game&sort=year-desc") as page:
            self.assertEqual(page.input_value("#archive-type"), "game")
            self.assertEqual(page.input_value("#archive-sort"), "year-desc")
            rows = self.rows(page)
            self.assertEqual([r["title"] for r in rows], [
                "Prøvepost: Øvingsspill", "Prøveprogram: Bekreftet spill", "Prøvepost: Spill fra menyen",
                "Prøvepost: Ærfugl", "Prøvepost: Åpent spill", "Prøvepost: Spill uten år"])
            kinds = {r["kind"] for r in rows}
            self.assertIn("Spill, fullversjon", kinds, "a registered game type")
            self.assertIn("Spill (CD-meny)", kinds, "a game documented by the CD menu")
            titles = {r["title"] for r in rows}
            self.assertNotIn("Prøvepost: Bare demo", titles, "Demoer alone is not a game")
            self.assertNotIn("Prøvepost: Typekonflikt", titles)
            self.assertNotIn("Prøveprogram: Kjent program mot spillmeny", titles, "a known type wins over the menu")
            self.assertEqual(page.text_content("#archive-count"), f"6 av {len(self.index['entries'])} poster")
            page.select_option("#archive-sort", "name")
            self.assertEqual(page.url, f"{self.base}/archive.html?type=game&sort=name")
            by_name = self.rows(page)
            self.assertEqual(sorted(r["href"] for r in by_name), sorted(r["href"] for r in rows), "same games")
            self.assertEqual([r["title"] for r in by_name], [
                "Prøvepost: Spill fra menyen", "Prøvepost: Spill uten år", "Prøvepost: Ærfugl",
                "Prøvepost: Øvingsspill", "Prøvepost: Åpent spill", "Prøveprogram: Bekreftet spill"])
            for request in page.requests:
                self.assertNotRegex(request, r"/data/(?!index\.json)[^/]+\.json", "no detail request per row")

    def test_course_without_content_kind_and_cd_year(self):
        with self.page("/archive.html?type=course&year=2001") as page:
            self.assertEqual([r["title"] for r in self.rows(page)], ["Prøvepost: Kurs fra Skole"])
            self.assertEqual(self.rows(page)[0]["kind"], "Kurs / veiledning (CD-meny)")
        with self.page("/archive.html?type=course") as page:
            self.assertEqual({r["kind"] for r in self.rows(page)}, {"Kurs / veiledning (CD-meny)", "Kurs / veiledning"})

    def test_sorting_never_changes_the_number_of_hits(self):
        with self.page("/archive.html?q=pr%C3%B8vepost&status=pending") as page:
            counts = set()
            for value in ("source", "name", "type", "year-desc", "year-asc"):
                page.select_option("#archive-sort", value)
                counts.add((page.text_content("#archive-count"), tuple(sorted(r["href"] for r in self.rows(page)))))
            self.assertEqual(len(counts), 1)

    def test_type_sort_groups_types_and_puts_unknown_and_unknown_year_last(self):
        with self.page("/archive.html?sort=type") as page:
            kinds = [r["kind"].split(" (")[0].split(",")[0] for r in self.rows(page)]
            self.assertEqual(kinds[-8:], ["Ikke oppgitt"] * 7 + ["Demo"])
            self.assertEqual(kinds[0], "Artikkel")
            self.assertEqual([k for i, k in enumerate(kinds) if i == 0 or kinds[i - 1] != k],
                             ["Artikkel", "Kurs / veiledning", "Program", "Skriftpakke", "Spill", "Ikke oppgitt", "Demo"])
        for sort in ("year-desc", "year-asc"):
            with self.subTest(sort), self.page(f"/archive.html?sort={sort}") as page:
                years = [r["year"] for r in self.rows(page)]
                self.assertEqual(years[-2:], ["Ikke oppgitt", "Ikke oppgitt"])
                media = [r["medium"] for r in self.rows(page)]
                ten, two = media.index("K-CD 10/2001"), media.index("K-CD 2/2001")
                self.assertTrue(ten < two if sort == "year-desc" else two < ten, "issue 10 vs 2 compared as numbers")

    def test_filter_choices_are_derived_and_labelled(self):
        with self.page("/archive.html") as page:
            types = page.eval_on_selector_all("#archive-type option", "o => o.map(x => [x.value, x.textContent])")
            self.assertEqual(types, [["all", "Alle typer"], ["application", "Program"], ["game", "Spill"], ["course", "Kurs / veiledning"],
                                     ["article", "Artikkel"], ["font_collection", "Skriftpakke"], ["unknown", "Ikke oppgitt"]])
            years = page.eval_on_selector_all("#archive-year option", "o => o.map(x => x.value)")
            self.assertEqual(years, ["all", "2013", "2001", "2000", "unknown"])
            sorts = page.eval_on_selector_all("#archive-sort option", "o => o.map(x => x.textContent)")
            self.assertEqual(sorts, ["Kilderekkefølge", "Navn A–Å", "Innholdstype A–Å", "CD-år: nyeste først", "CD-år: eldste først"])
            for control in ("archive-search", "archive-medium", "archive-status", "archive-type", "archive-year", "archive-sort"):
                self.assertTrue(page.locator(f"label[for={control}]").is_visible(), control)

    def test_old_bookmarks_and_invalid_parameters(self):
        with self.page("/archive.html?q=samme&medium=kcd-10-2001&status=pending&sort=name") as page:
            self.assertEqual([r["medium"] for r in self.rows(page)], ["K-CD 10/2001"])
            self.assertEqual(page.url, f"{self.base}/archive.html?q=samme&medium=kcd-10-2001&status=pending&sort=name")
        with self.page("/archive.html?type=spill&year=1999&sort=x&q=spill&status=pending") as page:
            self.assertIn("Ukjent innholdstype", page.text_content("#archive-notice"))
            self.assertIn("Fant ikke CD-året", page.text_content("#archive-notice"))
            self.assertEqual(page.input_value("#archive-search"), "spill", "other choices survive")
            self.assertEqual(page.input_value("#archive-status"), "pending")
            self.assertEqual((page.input_value("#archive-type"), page.input_value("#archive-year"), page.input_value("#archive-sort")), ("all", "all", "source"))
            self.assertEqual(page.url, f"{self.base}/archive.html?q=spill&status=pending")

    def test_url_post_back_reload_and_reset(self):
        path = "/archive.html?q=pr%C3%B8vepost&type=game&year=2001&sort=year-desc"
        with self.page(path) as page:
            before = (self.rows(page), page.text_content("#archive-count"))
            self.assertEqual(len(before[0]), 4)
            url = page.url
            page.locator(".archive-card").first.click()
            page.wait_for_selector("#entry-breadcrumbs li[aria-current=page]")
            page.go_back()
            page.wait_for_selector(".archive-card")
            self.assertEqual(page.url, url)
            self.assertEqual((self.rows(page), page.text_content("#archive-count")), before)
            page.reload(wait_until="networkidle")
            page.wait_for_selector(".archive-card")
            self.assertEqual((self.rows(page), page.text_content("#archive-count")), before)
            page.click("#archive-reset")
            self.assertEqual(page.url, f"{self.base}/archive.html")
            self.assertEqual(page.text_content("#archive-count"), f"{len(self.index['entries'])} av {len(self.index['entries'])} poster")
            self.assertEqual(page.evaluate("document.activeElement.id"), "archive-search")

    def test_valid_combination_without_hits_offers_a_way_back(self):
        with self.page("/archive.html?type=article&year=2000") as page:
            self.assertTrue(page.locator("#archive-empty").is_visible())
            self.assertEqual(page.locator(".archive-card").count(), 0)
            self.assertEqual(page.text_content("#archive-count"), f"0 av {len(self.index['entries'])} poster")
            page.click("#archive-empty-reset")
            self.assertTrue(page.locator("#archive-empty").is_hidden())
            self.assertEqual(page.locator(".archive-card").count(), len(self.index["entries"]))

    def test_old_index_without_menu_groups_uses_known_types_only(self):
        with self.page("/archive.html?type=game&sort=year-desc", old_index=True) as page:
            self.assertEqual([r["title"] for r in self.rows(page)], ["Prøveprogram: Bekreftet spill"])
            page.select_option("#archive-type", "unknown")
            self.assertEqual(page.locator(".archive-card").count(), len(self.index["entries"]) - 4)
            types = page.eval_on_selector_all("#archive-type option", "o => o.map(x => x.value)")
            self.assertEqual(types, ["all", "application", "game", "course", "font_collection", "unknown"])

    def test_narrow_screens_keep_labels_focus_and_no_sideways_scroll(self):
        for width in (320, 375):
            with self.subTest(width), self.page("/archive.html?type=game&year=2001&sort=name", width=width, height=740) as page:
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), width)
                for control in ("archive-type", "archive-year", "archive-sort"):
                    label = page.locator(f"label[for={control}]")
                    self.assertTrue(label.is_visible())
                    box = page.locator(f"#{control}").bounding_box()
                    self.assertLessEqual(box["x"] + box["width"], width)
                page.focus("#archive-search")
                order = []
                for _ in range(7):
                    page.keyboard.press("Tab")
                    order.append(page.evaluate("document.activeElement.id"))
                self.assertEqual(order, ["archive-medium", "archive-status", "archive-type", "archive-year", "archive-sort", "archive-reset", ""])
                page.focus("#archive-type")
                outline = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
                self.assertNotEqual(outline, "none", "visible keyboard focus")


@unittest.skipUnless(os.environ.get("BOOTDISK_ARCHIVE_DATA"), "set BOOTDISK_ARCHIVE_DATA to a built data directory for real acceptance")
@unittest.skipUnless(sync_playwright, "Playwright is required for the browser checks")
class RealArchiveAcceptance(unittest.TestCase):
    """Real data: extends a copy of the given data and opens the archive on it.

    The given directory is only read. The copy gets this checkout's public pages and,
    when DATA/../store exists, a link to it for icons.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ["BOOTDISK_ARCHIVE_DATA"]).expanduser().resolve()
        cls._stack = contextlib.ExitStack()
        work = Path(cls._stack.enter_context(tempfile.TemporaryDirectory()))
        cls.site = work / "site"
        cls.site.mkdir()
        release = load_builder("release_builder", "build-release.py")
        for name in release.STATIC_FILES:
            shutil.copy2(ROOT / name, cls.site / name)
        shutil.copy2(cls.source.parent / "collections.json" if (cls.source.parent / "collections.json").exists() else ROOT / "collections.json", cls.site / "collections.json")
        if (cls.source.parent / "store").is_dir():
            (cls.site / "store").symlink_to(cls.source.parent / "store")
        cls.before_hashes = file_hashes(cls.source)
        cls.before, cls.after = archive_index.extend(cls.source, cls.site / "data")
        print("\n" + archive_index.report("before", cls.before) + "\n" + archive_index.report("after", cls.after))
        cls.base = cls._stack.enter_context(serve(cls.site)).rstrip("/")
        playwright = cls._stack.enter_context(sync_playwright())
        cls.browser = playwright.chromium.launch(executable_path=os.environ.get("CURATOR_CHROMIUM") or None)
        cls._stack.callback(cls.browser.close)

    @classmethod
    def tearDownClass(cls):
        cls._stack.close()

    def test_source_data_untouched_and_counts_preserved(self):
        self.assertEqual(file_hashes(self.source), self.before_hashes)
        self.assertEqual(file_hashes(self.site / "data"), {k: v for k, v in self.before_hashes.items()})
        self.assertEqual([e["entry"] for e in self.after["entries"]], [e["entry"] for e in self.before["entries"]])
        self.assertEqual(public_updates.fingerprint(public_updates.load_projection(self.site / "data")),
                         public_updates.fingerprint(public_updates.load_projection(self.source)))

    def test_games_newest_first_include_both_bases_and_no_demo_only_rows(self):
        page = self.browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(self.base + "/archive.html?type=game&sort=year-desc", wait_until="networkidle")
        page.wait_for_selector(".archive-card")
        rows = page.eval_on_selector_all(".archive-table tbody tr", "rows => rows.map(r => [r.querySelector('.archive-card').getAttribute('href'), r.cells[3].textContent])")
        kinds = {kind for _, kind in rows}
        self.assertTrue(any(kind.startswith("Spill") and "(CD-meny)" not in kind for kind in kinds), "a registered game")
        self.assertTrue(any("Spill (CD-meny)" in kind for kind in kinds), "a game from the CD menu")
        by_entry = {e["entry"]: e for e in self.after["entries"]}
        for href, _ in rows:
            entry = by_entry[href.split("entry=", 1)[1]]
            self.assertNotEqual(entry.get("menu_groups"), ["Demoer"], "Demoer alone is not a game")
        expected = sum(archive_index.archive_kind(e)[0] == "game" for e in self.after["entries"])
        self.assertEqual(len(rows), expected)
        page.select_option("#archive-sort", "name")
        self.assertEqual(sorted(h for h, _ in rows), sorted(page.eval_on_selector_all(".archive-card", "a => a.map(x => x.getAttribute('href'))")))
        page.close()

    def test_skole_post_without_content_kind_is_found_as_course(self):
        skole = [e for e in self.after["entries"] if not e.get("content_kind") and archive_index.archive_kind(e) == ("course", "menu")
                 and "Skole" in (e.get("menu_groups") or [])]
        self.assertTrue(skole, "the data has a Skole entry without content_kind")
        page = self.browser.new_page()
        page.goto(self.base + "/archive.html?type=course", wait_until="networkidle")
        page.wait_for_selector(".archive-card")
        hrefs = set(page.eval_on_selector_all(".archive-card", "a => a.map(x => x.getAttribute('href'))"))
        self.assertIn(f"index.html?entry={skole[0]['entry']}", hrefs)
        page.close()


if __name__ == "__main__":
    unittest.main()
