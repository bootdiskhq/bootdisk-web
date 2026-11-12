"""Original CD menus (docs/cd-menu.md) built from invented PRØVEDATA menus.

The menus come from tests/synthetic_cd_menu.py and are built through the real release
gates and scripts/cd-menu-matrix.py. They say nothing about the real CDs; the real
checks are listed in the PR and run against Stian's copies on the Mac.
"""
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))
import cd_menu  # noqa: E402
import synthetic_cd_menu as synthetic  # noqa: E402
from test_publication import serve  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment dependent
    sync_playwright = None

FIRST, SECOND, PLAIN = "prove-1-2099", "prove-2-2099", "prove-3-2099"


def tree_hashes(root: Path, skip: str | None = None) -> dict:
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file() and not (skip and path.relative_to(root).parts[0] == skip)}


class SyntheticSite:
    """One built archive with menus, shared by the tests of a class."""

    @classmethod
    def build_site(cls):
        cls._temp = tempfile.TemporaryDirectory(prefix="bootdisk-cd-menu-test-")
        root = Path(cls._temp.name)
        cls.work = root / "work"
        cls.work.mkdir()
        cls.site = root / "site"
        cls.fixture = synthetic.build(cls.site, cls.work)
        cls.before_menus = tree_hashes(cls.site)
        synthetic.build_menus(cls.site, cls.work)
        cls.index = json.loads((cls.site / "data/index.json").read_text(encoding="utf-8"))
        cls.menus = json.loads((cls.site / "cd-meny/menus.json").read_text(encoding="utf-8"))
        cls.reports = {medium: json.loads((cls.site / "cd-meny" / medium / "menu-index.json").read_text(encoding="utf-8"))
                       for medium in synthetic.WITH_MENU}


class BuilderTests(SyntheticSite, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_site()

    @classmethod
    def tearDownClass(cls):
        cls._temp.cleanup()

    def menu_pages(self, medium=FIRST):
        folder = self.site / "cd-meny" / medium
        return {path.relative_to(folder).as_posix(): path.read_text(encoding="utf-8") for path in sorted(folder.rglob("*.html"))}

    def test_every_source_post_gets_its_own_page_or_anchor(self):
        report = self.reports[FIRST]
        self.assertEqual(report["routes"], {
            f"{FIRST}--K1": "html/program1.html",
            f"{FIRST}--K2": "html/articles.html#post-K2",
            f"{FIRST}--K3": "html/articles.html#post-K3",
            f"{FIRST}--K4": "html/videos.html#post-K4",
        })
        self.assertEqual(report["shared_pages"], {"html/articles.html": ["K2", "K3"]})
        pages = self.menu_pages()
        for anchor, title in (("post-K2", "Prøveartikkel A"), ("post-K3", "Prøveartikkel B")):
            block = re.search(rf'<div id="{anchor}" class="guide bd-anchor">(.*?)<p class="bd-post">(.*?)</p></div>', pages["html/articles.html"])
            self.assertIsNotNone(block, anchor)
            self.assertIn(title, block[1], "the anchor sits on the post's own description")
            self.assertIn(f"index.html?entry={FIRST}--{anchor[5:]}", block[2])
        self.assertIn(f'<a class="bd-back" href="../../../index.html?entry={FIRST}--K1">← Til kildeposten: Prøveprogram Én</a>', pages["html/program1.html"])

    def test_registry_lists_only_approved_media_with_their_own_manifest(self):
        self.assertEqual(self.menus["schema"], "bootdisk-cd-menu-index-1")
        self.assertEqual(sorted(self.menus["media"]), [FIRST, SECOND])
        refs = {medium["id"]: medium["source_manifest"] for medium in self.index["media"]}
        for medium, menu in self.menus["media"].items():
            self.assertEqual(menu["manifest"], refs[medium])
            self.assertEqual(menu["start"], f"cd-meny/{medium}/default.html")
            for key, route in menu["routes"].items():
                self.assertTrue(key.startswith(medium + "--"), "a medium never routes another medium's post")
                self.assertTrue(route.startswith(f"cd-meny/{medium}/"), route)
        approved_one = subprocess.run([sys.executable, str(ROOT / "scripts/cd-menu-matrix.py"), "--config", str(self.fixture["config"]),
                                       "--index", str(self.fixture["index"]), "--site", str(self.site), "--report-dir", str(self.work / "one"),
                                       "--approve", SECOND, "--only", SECOND], capture_output=True, text=True, check=True)
        self.assertIn("menus.json: 1 medier", approved_one.stdout)
        try:
            self.assertEqual(sorted(json.loads((self.site / "cd-meny/menus.json").read_text(encoding="utf-8"))["media"]), [SECOND])
        finally:
            synthetic.build_menus(self.site, self.work)

    def test_a_broken_original_page_keeps_the_post_and_explains(self):
        report = self.reports[FIRST]
        self.assertEqual(report["status"], "review")
        self.assertIn("html/broken.html", report["broken_pages"])
        self.assertNotIn(f"{FIRST}--K5", report["routes"])
        self.assertIn(f"{FIRST}--K5", [entry["entry"] for entry in self.index["entries"]], "the source post stays")
        pages = self.menu_pages()
        self.assertNotIn("html/broken.html", pages)
        self.assertIn("Ødelagt side <small class=\"bd-note\">(originalsiden er ødelagt på CD-en og vises ikke)</small>", pages["default.html"])
        self.assertIn(f'index.html?entry={FIRST}--K5">Prøveprogram Ødelagt</a>: originalsiden er ødelagt på CD-en', pages["index.html"])

    def test_no_script_handler_form_frame_or_external_address_survives(self):
        for medium in synthetic.WITH_MENU:
            for name, text in self.menu_pages(medium).items():
                with self.subTest(medium=medium, page=name):
                    self.assertIn(f'<meta http-equiv="Content-Security-Policy" content="{cd_menu.CSP}">', text)
                    self.assertIn("script-src 'none'", cd_menu.CSP)
                    body = text.split("</head>", 1)[1]
                    self.assertNotRegex(body.lower(), r"<(script|iframe|frame|object|embed|form|input|button|textarea|select|link|meta|style|base)\b")
                    self.assertNotRegex(body, r"\son[a-z]+\s*=", "no event handlers")
                    self.assertNotRegex(body, r"(?i)javascript:|https?:|//example|\bstyle=")
                    self.assertNotIn("example.invalid", text)
                    self.assertNotRegex(body, r"track\(\)|color:red|alert", "removed elements leave no text behind")
            css = (self.site / "cd-meny" / medium / "html/main.css").read_text(encoding="utf-8")
            self.assertNotRegex(css, r"(?i)expression|@import|https?:|alert")
            self.assertIn('url("../img/bg.gif")', css)

    def test_disabled_functions_are_named_and_counted(self):
        pages = self.menu_pages()
        program = pages["html/program1.html"]
        for label, reason in (("Installer", cd_menu.OFF_INSTALL), ("Les PDF", cd_menu.OFF_PDF), ("Se video", cd_menu.OFF_VIDEO)):
            self.assertIn(f'<span class="bd-off">{label} <small class="bd-note">({reason})</small></span>', program)
        self.assertIn(f"({cd_menu.OFF_EXTERNAL})", pages["default.html"])
        self.assertIn("(skjemaet er ikke aktivt i arkivvisningen)", pages["default.html"])
        self.assertNotIn("Søk", program, "the template's search box is removed with its scripts")
        self.assertEqual(sum(self.reports[FIRST]["disabled"].values()), self.reports[FIRST]["counts"]["disabled"])

    def test_original_text_and_errors_are_kept(self):
        front = self.menu_pages()["default.html"]
        self.assertIn("Denne utgaven er CD 17.", front, "editorial errors stay as on the CD")
        self.assertIn("Prøveprogram Én", self.menu_pages()["html/program1.html"], "Windows-1252 text is decoded")

    def test_paths_are_checked_after_decoding_and_ambiguous_names_refused(self):
        program = self.menu_pages()["html/program1.html"]
        self.assertIn('<span class="bd-off">Rømning <small class="bd-note">(siden er ikke med i arkivvisningen)</small></span>', program)
        self.assertIn('<span class="bd-off">Bakstrek', program)
        self.assertIn('<a href="articles.html">Til artiklene</a>', program, "case-folded match, unknown fragment dropped")
        source = cd_menu.Source({"file_inventory": [{"path": "html/a.html", "size": 1, "sha256": "0"}, {"path": "img/X.png", "size": 1, "sha256": "0"},
                                                    {"path": "img/x.png", "size": 1, "sha256": "0"}]}, None)
        cases = {"../../etc/passwd": "utenfor CD-en", "%2e%2e/%2e%2e/etc/passwd": "utenfor CD-en", "/etc/passwd": "ugyldig sti",
                 "..\\a.html": "ugyldig sti", "a%5c..%5ca.html": "ugyldig sti", "a%00.html": "ugyldig sti", "http://x/": "ekstern",
                 "//x/a": "ekstern", "../img/x.PNG": "tvetydig", "missing.html": "finnes ikke på CD-en"}
        for url, reason in cases.items():
            with self.subTest(url):
                self.assertEqual(source.resolve("html/a.html", url), (None, reason))
        self.assertEqual(source.resolve("html/a.html", "A.HTML"), ("html/a.html", None))
        report = self.reports[FIRST]
        self.assertIn({"page": "default.html", "url": "img/DUP.png", "reason": "tvetydig"}, report["missing_images"])
        self.assertNotIn("img/Dup.png", [row["path"] for row in report["images"]])

    def test_images_are_verified_and_missing_ones_marked(self):
        report = self.reports[FIRST]
        self.assertEqual(sorted(row["path"] for row in report["images"]), ["img/bg.gif", "img/logo.png", "img/shot.jpg"])
        self.assertEqual([row.get("note") for row in report["images"] if row["path"] == "img/shot.jpg"], ["filendelsen stemmer ikke med bildeformatet"])
        front = self.menu_pages()["default.html"]
        self.assertEqual(front.count("[Bildet mangler på CD-en]"), 1)
        self.assertEqual(front.count("[Bildet vises ikke i arkivvisningen]"), 2)
        self.assertIn({"page": "html/main.css", "url": "../img/missing-css.png", "reason": "finnes ikke på CD-en"}, report["missing_images"])
        folder = self.site / "cd-meny" / FIRST
        for row in report["images"]:
            self.assertEqual(hashlib.sha256((folder / row["path"]).read_bytes()).hexdigest(), row["sha256"])
        self.assertFalse((folder / "install").exists() or (folder / "js").exists(), "nothing outside the selection is copied")

    def test_archive_data_and_history_are_untouched(self):
        after = tree_hashes(self.site, skip="cd-meny")
        before = {name: digest for name, digest in self.before_menus.items() if not name.startswith("cd-meny/")}
        self.assertEqual(after, before, "the menus write only under cd-meny/")
        self.assertEqual(json.loads((self.site / "cd-meny/menus.json").read_text(encoding="utf-8"))["schema"], cd_menu.REGISTRY_SCHEMA)

    def test_release_ships_an_empty_register(self):
        self.assertEqual(json.loads(json.dumps({"schema": cd_menu.REGISTRY_SCHEMA, "media": {}})), {"schema": cd_menu.REGISTRY_SCHEMA, "media": {}})
        self.assertIn("cd-meny/menus.json", self.before_menus, "build-release.py writes an empty register")


class BlockingTests(unittest.TestCase):
    """A blocked medium keeps the menu that is already built and never stops the others."""

    @classmethod
    def setUpClass(cls):
        cls._temp = tempfile.TemporaryDirectory(prefix="bootdisk-cd-menu-block-")
        root = Path(cls._temp.name)
        cls.work, cls.site = root / "work", root / "site"
        cls.work.mkdir()
        cls.fixture = synthetic.build(cls.site, cls.work)
        synthetic.build_menus(cls.site, cls.work)
        cls.index = json.loads(cls.fixture["index"].read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls._temp.cleanup()

    def setUp(self):
        self.good = tree_hashes(self.site / "cd-meny" / FIRST)

    def tearDown(self):
        self.assertEqual(tree_hashes(self.site / "cd-meny" / FIRST), self.good, "the existing menu is untouched")

    def build(self, manifest=None, source=None, index=None):
        menu = self.fixture["menus"][FIRST]
        return cd_menu.build_medium(FIRST, manifest or menu["manifest"], source or menu["source"], index or self.index, self.site)

    def copy_source(self) -> Path:
        target = self.work / f"source-{self._testMethodName}"
        shutil.copytree(self.fixture["menus"][FIRST]["source"], target)
        return target

    def test_changed_bytes_block(self):
        source = self.copy_source()
        (source / "img/logo.png").write_bytes(synthetic.png((9, 9, 9)))
        report = self.build(source=source)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("img/logo.png: byte stemmer ikke med manifestet", report["blocked"])

    def test_symlink_in_the_selection_blocks(self):
        source = self.copy_source()
        (source / "img/logo.png").unlink()
        (source / "img/logo.png").symlink_to(source / "img/bg.gif")
        self.assertIn("symbolsk lenke", self.build(source=source)["blocked"])

    def test_unknown_template_blocks(self):
        source = self.copy_source()
        manifest = json.loads(self.fixture["menus"][FIRST]["manifest"].read_text(encoding="utf-8"))
        changed = (source / "default.html").read_bytes().replace(b'id="menu"', b'id="sidebar"')
        (source / "default.html").write_bytes(changed)
        for item in manifest["file_inventory"]:
            if item["path"] == "default.html":
                item.update(size=len(changed), sha256=hashlib.sha256(changed).hexdigest())
        path = self.work / "unknown-template.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        index = json.loads(json.dumps(self.index))
        ref = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        for entry in index["entries"]:
            if entry["medium_id"] == FIRST:
                entry["source_manifest"] = ref
        report = self.build(manifest=path, source=source, index=index)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("ukjent menymal", report["blocked"])

    def test_other_manifest_blocks_and_gives_no_routes(self):
        other = self.fixture["menus"][SECOND]["manifest"]
        report = cd_menu.build_medium(FIRST, other, self.fixture["menus"][SECOND]["source"], self.index, self.site)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("annet manifest", report["blocked"])

    def test_unknown_format_and_missing_source_block(self):
        manifest = json.loads(self.fixture["menus"][FIRST]["manifest"].read_text(encoding="utf-8"))
        manifest["source"]["format"] = "kcd-flash-menu-1"
        path = self.work / "flash.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertIn("ukjent menyformat", self.build(manifest=path)["blocked"])
        self.assertEqual(cd_menu.build_medium(FIRST, self.fixture["menus"][FIRST]["manifest"], None, self.index, self.site)["status"], "blocked")

    def test_dry_run_reads_only_the_manifest_and_writes_nothing(self):
        report = cd_menu.build_medium(FIRST, self.fixture["menus"][FIRST]["manifest"], None, self.index, None, dry_run=True)
        self.assertEqual(report["status"], "dry_run")
        self.assertEqual(len(report["routes"]), 4, "entry pages embedded in the manifest are bound and checked")
        self.assertTrue(report["unchecked"]["template"])
        self.assertNotIn("kildeutvalget mangler filer", report["problems"])

    def test_one_blocked_medium_does_not_stop_the_matrix(self):
        config = json.loads(self.fixture["config"].read_text(encoding="utf-8"))
        config["media"].insert(0, {"id": "prove-9-2099", "manifest": "missing/manifest.json"})
        config["media"].insert(1, {"id": FIRST, "manifest": str(self.fixture["menus"][SECOND]["manifest"]), "source": str(self.fixture["menus"][SECOND]["source"])})
        path = self.work / "matrix-blocked.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        result = subprocess.run([sys.executable, str(ROOT / "scripts/cd-menu-matrix.py"), "--config", str(path), "--index", str(self.fixture["index"]),
                                 "--site", str(self.site), "--report-dir", str(self.work / "blocked-report"), "--approve", f"{FIRST},{SECOND}"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = {(row["medium_id"], row["status"]) for row in json.loads((self.work / "blocked-report/report.json").read_text(encoding="utf-8"))["media"]}
        self.assertIn(("prove-9-2099", "blocked"), rows)
        self.assertIn((FIRST, "blocked"), rows)
        self.assertIn((SECOND, "review"), rows)
        report = (self.work / "blocked-report/RAPPORT.md").read_text(encoding="utf-8")
        self.assertIn("| prove-9-2099 | sperret |", report)
        self.assertIn("Det er ikke en godkjenning", report)
        # The good FIRST menu built earlier is still registered from its own menu-index.json.
        menus = json.loads((self.site / "cd-meny/menus.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(menus["media"]), [FIRST, SECOND])


def run_matrix(fixture, site, report, *options):
    return subprocess.run([sys.executable, str(ROOT / "scripts/cd-menu-matrix.py"), "--config", str(fixture["config"]),
                           "--index", str(fixture["index"]), "--site", str(site), "--report-dir", str(report), *options],
                          capture_output=True, text=True)


class PublishingTests(unittest.TestCase):
    """What ends up under cd-meny/ in the package, and building through path aliases."""

    def test_alias_path_to_the_site_is_accepted(self):
        # macOS reaches its temporary folder through /var → /private/var. The boundary
        # check must compare canonical paths on both sides.
        with tempfile.TemporaryDirectory() as temporary:
            real = Path(temporary) / "real"
            real.mkdir()
            alias = Path(temporary) / "alias"
            alias.symlink_to(real, target_is_directory=True)
            fixture = synthetic.build(alias / "site", (alias / "work"))
            self.assertNotEqual(alias / "site", (alias / "site").resolve())
            report = cd_menu.build_medium(FIRST, fixture["menus"][FIRST]["manifest"], fixture["menus"][FIRST]["source"],
                                          json.loads(fixture["index"].read_text(encoding="utf-8")), alias / "site")
            self.assertEqual(report["status"], "review", report.get("blocked"))
            self.assertTrue((real / "site/cd-meny" / FIRST / "html/program1.html").is_file())
            leftovers = [path.name for path in (real / "site/cd-meny").iterdir() if path.name.startswith(".")]
            self.assertEqual(leftovers, [], "no temporary folder left behind")

    def test_output_outside_the_menu_folder_is_still_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root / "work"
            work.mkdir()
            fixture = synthetic.build(root / "site", work)
            build = cd_menu.MenuBuild(FIRST, fixture["menus"][FIRST]["manifest"], fixture["menus"][FIRST]["source"],
                                      json.loads(fixture["index"].read_text(encoding="utf-8")))
            report = build.build()
            build.files["../escape.html"] = b"x"
            with self.assertRaises(cd_menu.BuildBlocked):
                cd_menu.write_menu(root / "site", FIRST, build, report)
            self.assertFalse((root / "site/cd-meny/escape.html").exists())
            self.assertEqual([path.name for path in (root / "site/cd-meny").iterdir()], ["menus.json"], "the temporary folder is cleaned up")

    def test_only_approved_media_are_in_the_package_even_after_a_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work, site = root / "work", root / "site"
            work.mkdir()
            fixture = synthetic.build(site, work)
            outside = tree_hashes(site, skip="cd-meny")
            preview = run_matrix(fixture, site, root / "preview", "--preview-all")
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertEqual(sorted(path.name for path in (site / "cd-meny").iterdir()), ["menus.json", FIRST, SECOND])

            package = run_matrix(fixture, site, root / "package", "--approve", FIRST)
            self.assertEqual(package.returncode, 0, package.stderr)
            self.assertEqual(sorted(path.name for path in (site / "cd-meny").iterdir()), ["menus.json", FIRST],
                             "the preview menu of the unapproved medium is gone")
            self.assertEqual(sorted(json.loads((site / "cd-meny/menus.json").read_text(encoding="utf-8"))["media"]), [FIRST])
            self.assertEqual(tree_hashes(site, skip="cd-meny"), outside, "nothing outside cd-meny/ changes")
            report = json.loads((root / "package/report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["published"], [FIRST])
            rows = {row["medium_id"]: row for row in report["media"]}
            self.assertEqual((rows[SECOND]["status"], rows[SECOND]["published"]), ("review", False), "still built and checked, not written")
            self.assertEqual(len(rows[SECOND]["routes"]), 4)
            self.assertIn(f"Godkjent og med i `cd-meny/`: {FIRST}.", (root / "package/RAPPORT.md").read_text(encoding="utf-8"))

            again = run_matrix(fixture, site, root / "package2", "--approve", FIRST)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(sorted(path.name for path in (site / "cd-meny").iterdir()), ["menus.json", FIRST])

            (site / "cd-meny/notes.txt").write_text("ikke vårt", encoding="utf-8")
            before = tree_hashes(site / "cd-meny")
            stopped = run_matrix(fixture, site, root / "package3", "--approve", SECOND)
            self.assertEqual(stopped.returncode, 1)
            self.assertIn("stoppet før bygging: ukjent innhold", stopped.stdout)
            self.assertEqual(tree_hashes(site / "cd-meny"), before, "stopped before building: nothing written, removed or registered")
            self.assertEqual(sorted(json.loads((site / "cd-meny/menus.json").read_text(encoding="utf-8"))["media"]), [FIRST])


class FindManifestTests(unittest.TestCase):
    def test_finds_manifests_by_hash_never_by_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site, work = root / "site", root / "work"
            work.mkdir()
            fixture = synthetic.build(site, work)
            decoy = root / "results/run/prove-1-2099-observe/manifest.json"
            decoy.parent.mkdir(parents=True)
            decoy.write_bytes(fixture["menus"][FIRST]["manifest"].read_bytes() + b" ")
            partial = root / "results/.prove-2-2099.partial/manifest.json"
            partial.parent.mkdir(parents=True)
            shutil.copy2(fixture["menus"][SECOND]["manifest"], partial)
            sources = root / "menu-source"
            shutil.copytree(fixture["menus"][FIRST]["source"], sources / FIRST)
            out = root / "matrix.json"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/find-cd-menu-manifests.py"), "--index", str(fixture["index"]),
                                     "--root", str(root / "results"), "--root", str(work / "manifests"), "--sources", str(sources), "--out", str(out)],
                                    capture_output=True, text=True, check=True)
            config = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual([row["id"] for row in config["media"]], [FIRST, SECOND])
            self.assertEqual(config["media"][0]["manifest"], str(fixture["menus"][FIRST]["manifest"].resolve()))
            self.assertEqual(config["media"][0]["source"], str((sources / FIRST).resolve()))
            self.assertNotIn("source", config["media"][1])
            self.assertEqual(json.loads(result.stdout)["not_found_or_not_html"], [PLAIN])


@unittest.skipUnless(shutil.which("bsdtar") or shutil.which("tar"), "tar required")
class ExtractSourceTests(unittest.TestCase):
    """The Mac extraction, run on a tar archive standing in for a finished CD image."""

    def test_copies_only_the_menu_selection_and_checks_every_byte(self):
        import tarfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = synthetic.menu_files("Prøve-CD 1/2099", "Prøve")
            disc = root / "disc"
            for name, data in files.items():
                (disc / name).parent.mkdir(parents=True, exist_ok=True)
                (disc / name).write_bytes(data)
            image = root / "image.tar"
            with tarfile.open(image, "w") as archive:
                for name in sorted(files):
                    archive.add(disc / name, arcname="./" + name)
            manifest = {"media": {"sha256": hashlib.sha256(image.read_bytes()).hexdigest()},
                        "file_inventory": [{"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in files.items()]}
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            command = [sys.executable, str(ROOT / "scripts/extract-cd-menu-source.py"), "--image", str(image), "--manifest", str(manifest_path)]
            result = subprocess.run(command + ["--dest", str(root / "out")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)  # img/Dup.png and img/dup.png share a folded name
            report = json.loads(result.stdout)
            self.assertEqual(sorted(row["path"] for row in report["problems"]), ["img/Dup.png", "img/dup.png"])
            copied = sorted(path.relative_to(root / "out").as_posix() for path in (root / "out").rglob("*") if path.is_file())
            self.assertEqual(copied, ["default.html", "html/articles.html", "html/broken.html", "html/main.css", "html/program1.html",
                                      "html/videos.html", "img/bg.gif", "img/logo.png", "img/shot.jpg"])
            self.assertEqual(sorted(path.name for path in root.iterdir()), ["disc", "image.tar", "manifest.json", "out"], "no temporary folder left")
            again = subprocess.run(command + ["--dest", str(root / "out")], capture_output=True, text=True)
            self.assertEqual((again.returncode, json.loads(again.stdout)["status"]), (1, "exists"), "an existing copy is never replaced")
            manifest["media"]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            wrong = subprocess.run(command + ["--dest", str(root / "out2")], capture_output=True, text=True)
            self.assertEqual(json.loads(wrong.stdout)["status"], "blocked")
            self.assertFalse((root / "out2").exists())


@unittest.skipUnless(shutil.which("node"), "Node required")
class FrontendGateTests(unittest.TestCase):
    def test_links_are_offered_only_for_the_same_manifest_and_own_folder(self):
        ref = "sha256:" + "a" * 64
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const ctx=vm.createContext({console});
vm.runInContext(fs.readFileSync('collection-core.js','utf8'),ctx);
const route=(m,e)=>vm.runInContext('cdMenuRoute',ctx)(m,e), start=(m,id)=>vm.runInContext('cdMenuStart',ctx)(m,id);
const REF=process.argv[1];
const menus={schema:'bootdisk-cd-menu-index-1',media:{'prove-1-2099':{manifest:REF,start:'cd-meny/prove-1-2099/default.html',routes:{
 'prove-1-2099--K1':'cd-meny/prove-1-2099/html/program1.html','prove-1-2099--K2':'cd-meny/prove-1-2099/html/articles.html#post-K2',
 'prove-1-2099--K3':'cd-meny/prove-2-2099/html/articles.html','prove-1-2099--K4':'https://example.invalid/x.html',
 'prove-1-2099--K5':'cd-meny/prove-1-2099/../../index.html','prove-1-2099--K6':'cd-meny/prove-1-2099/html/a.html#x" onclick="y'}},
 'prove-2-2099':{manifest:'sha256:short',start:'cd-meny/prove-2-2099/default.html',routes:{}}}};
const entry=(key,manifest=REF,medium='prove-1-2099')=>({entry:key,medium_id:medium,source_manifest:manifest});
assert.equal(route(menus,entry('prove-1-2099--K1')),'cd-meny/prove-1-2099/html/program1.html');
assert.equal(route(menus,entry('prove-1-2099--K2')),'cd-meny/prove-1-2099/html/articles.html#post-K2');
for(const key of ['K3','K4','K5','K6','K9'])assert.equal(route(menus,entry('prove-1-2099--'+key)),null,key);
assert.equal(route(menus,entry('prove-1-2099--K1','sha256:'+'b'.repeat(64))),null,'another manifest');
assert.equal(route(menus,entry('prove-1-2099--K1',REF,'prove-2-2099')),null,'another medium');
assert.equal(route(menus,{entry:'K1',medium_id:'prove-1-2099',source_manifest:REF}),null,'legacy key without medium');
assert.equal(route({...menus,schema:'x'},entry('prove-1-2099--K1')),null);
assert.equal(route(null,entry('prove-1-2099--K1')),null);
assert.equal(route(menus,entry('__proto__')),null);
assert.equal(start(menus,'prove-1-2099'),'cd-meny/prove-1-2099/default.html');
assert.equal(start(menus,'prove-2-2099'),null,'invalid manifest ref');
assert.equal(start(menus,'prove-3-2099'),null);
assert.equal(start(menus,'constructor'),null);
(async()=>{
 assert.equal(await vm.runInContext('loadCdMenus',ctx)(async()=>({ok:false,status:404})),null);
 assert.equal(await vm.runInContext('loadCdMenus',ctx)(async()=>({ok:true,json:async()=>{throw new Error('x')}})),null);
 const seen=[];await vm.runInContext('loadCdMenus',ctx)(async(url,options)=>{seen.push([url,options.cache]);return{ok:true,json:async()=>menus};});
 assert.deepEqual(seen,[['cd-meny/menus.json','no-cache']]);
})().catch(error=>{console.error(error);process.exit(1);});
"""
        subprocess.run(["node", "-e", script, ref], cwd=ROOT, check=True)


@unittest.skipUnless(sync_playwright, "Playwright is required for the browser checks")
class CdMenuBrowserTests(SyntheticSite, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_site()
        cls._stack = contextlib.ExitStack()
        cls._stack.callback(cls._temp.cleanup)
        cls.base = cls._stack.enter_context(serve(cls.site)).rstrip("/")
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
    def page(self, path, width=1280, height=900, **options):
        context = self.browser.new_context(viewport={"width": width, "height": height}, **options)
        page = context.new_page()
        problems, requests, broken = [], [], []
        page.on("pageerror", lambda error: problems.append(str(error)))
        # Chromium asks for /favicon.ico on the first page of a context; the archive
        # has no icon, on menu pages or elsewhere, so that one 404 is not a finding.
        page.on("console", lambda message: message.type == "error" and not message.location.get("url", "").endswith("/favicon.ico")
                and problems.append(message.text))
        page.on("request", lambda request: requests.append(request.url))
        page.on("response", lambda response: response.status >= 400 and not response.url.endswith(("/data/public-updates.json", "/favicon.ico"))
                and broken.append(f"{response.status} {response.url}"))
        page.goto(self.base + path, wait_until="networkidle")
        try:
            yield page
            self.assertEqual(problems, [], "console, CSP or script errors")
            self.assertEqual(broken, [], "broken local requests")
            self.assertEqual([url for url in requests if not url.startswith(self.base)], [], "no external requests")
        finally:
            context.close()

    def assert_inert(self, page):
        active = page.evaluate("""() => ({
            scripts: document.scripts.length,
            controls: document.querySelectorAll('form,input,button,select,textarea,iframe,object,embed,video,audio').length,
            handlers: [...document.querySelectorAll('*')].filter(el => [...el.attributes].some(a => a.name.startsWith('on'))).length,
            external: [...document.querySelectorAll('a[href],img[src]')].map(el => el.href || el.src).filter(u => !u.startsWith(location.origin)).length})""")
        self.assertEqual(active, {"scripts": 0, "controls": 0, "handlers": 0, "external": 0})

    def test_front_page_category_description_and_back(self):
        with self.page(f"/archive.html?medium={FIRST}") as page:
            launch = page.locator("a.disc-menu-launch")
            self.assertEqual(launch.text_content(), "Bla i CD-menyen →")
            launch.click()
            page.wait_for_url("**/cd-meny/prove-1-2099/default.html")
            self.assertEqual(page.locator(".bd-bar .bd-brand").text_content(), "Bootdisk · Prøve-CD 1/2099 · original CD-meny")
            self.assert_inert(page)
            page.locator("#menu a", has_text="Artikler").click()
            page.wait_for_url("**/html/articles.html")
            page.locator("#post-K3 .bd-post a").click()
            page.wait_for_url(f"**/index.html?entry={FIRST}--K3")
            page.wait_for_selector("a.disc-menu-launch")
            self.assertEqual(page.locator("a.disc-menu-launch").text_content(), "Åpne omtalen i CD-menyen →")
            page.locator("a.disc-menu-launch").click()
            page.wait_for_url("**/html/articles.html#post-K3")
            self.assertEqual(page.evaluate("document.querySelector(':target')?.id"), "post-K3")
            page.locator(".bd-bar a", has_text="CD-oversikt i Bootdisk").click()
            page.wait_for_url(f"**/archive.html?medium={FIRST}")

    def test_every_route_round_trips_from_a_direct_bookmark(self):
        for medium, menu in self.menus["media"].items():
            for key, route in menu["routes"].items():
                with self.subTest(key), self.page(f"/index.html?entry={key}") as page:
                    link = page.wait_for_selector("a.disc-menu-launch")
                    self.assertEqual(link.get_attribute("href"), route)
                    page.goto(f"{self.base}/{route}", wait_until="networkidle")
                    page_path, _, anchor = route.partition("#")
                    back = page.locator(f"#{anchor} .bd-post a" if anchor else ".bd-bar a.bd-back")
                    self.assertEqual(back.count(), 1)
                    self.assertEqual(urlsplit(urljoin(page.url, back.get_attribute("href"))).query, f"entry={key}")
                    if anchor:
                        self.assertEqual(page.evaluate("document.querySelector(':target')?.id"), anchor)
                    self.assert_inert(page)

    def test_posts_without_a_menu_or_route_get_no_link(self):
        for path in (f"/index.html?entry={PLAIN}--K1", f"/index.html?entry={FIRST}--K5", f"/archive.html?medium={PLAIN}"):
            with self.subTest(path), self.page(path) as page:
                page.wait_for_selector('main[aria-busy="false"]' if "index.html" in path else "#medium-links a", state="attached")
                self.assertEqual(page.locator("a.disc-menu-launch").count(), 0)

    def test_keyboard_reaches_archive_bar_then_menu(self):
        with self.page(f"/cd-meny/{FIRST}/html/program1.html") as page:
            page.keyboard.press("Tab")
            self.assertEqual(page.evaluate("document.activeElement.className"), "bd-back", "the archive's way back comes first")
            for _ in range(5):
                page.keyboard.press("Tab")
            self.assertEqual(page.evaluate("document.activeElement.textContent"), "Program")
            outline = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
            self.assertNotEqual(outline, "none", "focus is visible")
            page.keyboard.press("Enter")
            page.wait_for_url("**/html/program1.html")

    def test_no_dead_internal_links_or_images_and_nothing_active(self):
        seen = set()
        for medium in self.menus["media"]:
            folder = self.site / "cd-meny" / medium
            for file in sorted(folder.rglob("*.html")):
                path = "/" + file.relative_to(self.site).as_posix()
                with self.subTest(path), self.page(path, width=390, height=844) as page:
                    self.assert_inert(page)
                    targets = page.evaluate("[...document.querySelectorAll('a[href]')].map(a => a.href)")
                    broken = page.evaluate("[...document.images].filter(i => !i.complete || i.naturalWidth === 0).map(i => i.src)")
                    self.assertEqual(broken, [], "every image shown loads")
                    for target in targets:
                        url, _, fragment = target.partition("#")
                        if (url, fragment) in seen:
                            continue
                        seen.add((url, fragment))
                        response = page.request.get(url)
                        self.assertEqual(response.status, 200, target)
                        if fragment and "/cd-meny/" in url:
                            self.assertIn(f'id="{fragment}"', response.text(), target)

    def test_mobile_view_keeps_the_bar_and_has_no_page_scroll(self):
        with self.page(f"/cd-meny/{FIRST}/html/articles.html", width=320, height=640) as page:
            self.assertTrue(page.locator(".bd-bar").is_visible())
            width = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
            self.assertLessEqual(width[0], width[1], "no horizontal page scroll; wide originals scroll inside .bd-original")


if __name__ == "__main__":
    unittest.main()
