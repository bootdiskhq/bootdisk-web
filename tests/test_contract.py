import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    def setUp(self):
        self.entry = json.loads((ROOT / "data" / "k37.json").read_text(encoding="utf-8"))

    def test_entry_joins_catalog_identity_and_publish_assets(self):
        self.assertEqual(self.entry["entry"], "K37")
        self.assertEqual(self.entry["software"][0]["software_id"], "software:winamp")
        self.assertEqual(self.entry["software"][0]["version"], "2.76")
        self.assertEqual({asset["kind"] for asset in self.entry["assets"]}, {"icon", "screenshot"})

    def test_source_context_is_data_not_page_markup(self):
        self.assertEqual(self.entry["publication"], "KOMPUTER FOR ALLE")
        self.assertEqual(self.entry["medium"], "K-CD 15/2001")
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("K37</dd>", html)
        self.assertNotIn("K-CD 15/2001</dd>", html)

    def test_assets_remain_bound_to_same_ingest_entry(self):
        for asset in self.entry["assets"]:
            self.assertEqual(asset["entry"], self.entry["entry"])
            self.assertTrue(asset["original"]["public_path"].startswith("store/assets/sha256/"))
            for derivative in asset["derivatives"]:
                self.assertTrue(derivative["public_path"].startswith("store/derivatives/"))

    def test_browser_selects_entry_document_from_query_parameter(self):
        javascript = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn('new URLSearchParams(window.location.search).get("entry")', javascript)
        self.assertIn('`data/${entryId}.json`', javascript)
        self.assertIn('window.location.replace("archive.html")', javascript)

    def test_entry_navigation_follows_index_instead_of_guessing_ids(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="previous-entry"', html)
        self.assertIn('id="next-entry"', html)
        self.assertIn('fetch("data/index.json")', javascript)
        self.assertIn('index.entries[position - 1]', javascript)
        self.assertIn('index.entries[position + 1]', javascript)
        self.assertNotIn('Number(entry.entry.slice(1))', javascript)
        self.assertIn('entry?.software_name ?? entry?.editorial_title ?? entry?.entry', javascript)
        self.assertIn('link.textContent = `← ${entryName(previous)}`', javascript)
        self.assertIn('link.textContent = `${entryName(next)} →`', javascript)
        self.assertIn('event.key === "ArrowLeft"', javascript)
        self.assertIn('event.key === "ArrowRight"', javascript)

    def test_entry_reports_loading_errors_and_source_metadata_accessibly(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="page-description"', html)
        self.assertIn('aria-busy="true"', html)
        self.assertIn('id="entry-error" role="alert"', html)
        self.assertIn('document.querySelector("#page-description").content', javascript)
        self.assertIn('setAttribute("aria-busy", "false")', javascript)

    def test_pages_support_keyboard_reduced_motion_and_no_script_states(self):
        for name in ("index.html", "archive.html", "404.html"):
            html = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn('class="skip-link" href="#main-content"', html)
            self.assertIn('id="main-content"', html)
            self.assertIn('href="accessibility.css"', html)
        self.assertIn("<noscript>", (ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertIn("<noscript>", (ROOT / "archive.html").read_text(encoding="utf-8"))
        css = (ROOT / "accessibility.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion: reduce", css)

    def test_entry_presents_human_status_and_descriptive_screenshot_alt(self):
        javascript = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn('identified: "Identifisert"', javascript)
        self.assertIn('pending: "Venter på identifisering"', javascript)
        self.assertIn('screenshot.alt = `Skjermbilde fra ${name}`', javascript)

    def test_builder_emits_archive_index_without_inventing_identity(self):
        builder = (ROOT / "scripts" / "build-frontend-data.py").read_text(encoding="utf-8")
        self.assertIn('args.output / "index.json"', builder)
        self.assertIn('entry.get("editorial_title")', builder)
        self.assertIn('software.get("software_name")', builder)
        self.assertNotIn("software_name = editorial", builder)

    def test_archive_links_back_to_generic_entry_renderer(self):
        javascript = (ROOT / "archive.js").read_text(encoding="utf-8")
        self.assertIn('index.html?entry=${encodeURIComponent(entry.entry)}', javascript)
        self.assertIn('fetch("data/index.json")', javascript)
        self.assertNotIn("innerHTML", javascript)

    def test_archive_filters_are_shareable_and_preserve_source_truth(self):
        html = (ROOT / "archive.html").read_text(encoding="utf-8")
        javascript = (ROOT / "archive.js").read_text(encoding="utf-8")
        self.assertIn('id="archive-status"', html)
        self.assertIn('id="archive-sort"', html)
        self.assertIn('id="archive-reset"', html)
        self.assertIn('entry.curation_status === status', javascript)
        self.assertIn('new URLSearchParams(window.location.search)', javascript)
        self.assertIn('window.history.replaceState', javascript)
        self.assertIn('id="archive-empty"', html)
        self.assertIn('empty.hidden = entries.length !== 0', javascript)

    def test_release_includes_archive_filter_styles(self):
        builder = (ROOT / "scripts" / "build-release.py").read_text(encoding="utf-8")
        self.assertIn('"archive-controls.css"', builder)
        self.assertIn('"entry-controls.css"', builder)
        self.assertIn('"accessibility.css"', builder)

    def test_release_builder_runs_stable_frontend_contract(self):
        builder = (ROOT / "scripts" / "build-release.py").read_text(encoding="utf-8")
        contract = (ROOT / "docs" / "frontend-data-contract.md").read_text(encoding="utf-8")
        self.assertIn("validate_frontend_data(frontend_data, expected_entries)", builder)
        self.assertIn("Frontend-datakontrakt 1.0", contract)

    def test_frontend_contract_accepts_complete_projection(self):
        script = ROOT / "scripts" / "frontend_contract.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.json").write_text(json.dumps({
                "publication": "Test",
                "medium": "Test medium",
                "entries": [{"entry": "K1", "curation_status": "identified"}],
            }), encoding="utf-8")
            (root / "k1.json").write_text(json.dumps({
                "entry": "K1",
                "publication": "Test",
                "medium": "Test medium",
                "curation_status": "identified",
                "software": [],
                "assets": [],
            }), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), str(root), "--expected-entries", "1"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("frontend contract: 1 entries valid", result.stdout)

    def test_frontend_contract_rejects_cross_entry_asset(self):
        script = ROOT / "scripts" / "frontend_contract.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.json").write_text(json.dumps({
                "publication": "Test",
                "medium": "Test medium",
                "entries": [{"entry": "K1", "curation_status": "identified"}],
            }), encoding="utf-8")
            (root / "k1.json").write_text(json.dumps({
                "entry": "K1",
                "publication": "Test",
                "medium": "Test medium",
                "curation_status": "identified",
                "software": [],
                "assets": [{
                    "entry": "K2",
                    "kind": "icon",
                    "original": {"public_path": "store/icon", "sha256": "a" * 64},
                    "derivatives": [],
                }],
            }), encoding="utf-8")
            result = subprocess.run([sys.executable, str(script), str(root)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("asset entry must equal K1", result.stderr)

    def test_builder_replaces_stale_output_and_sorts_source_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "catalog.json"
            publish = root / "publish.json"
            output = root / "data"
            output.mkdir()
            (output / "k99.json").write_text("{}\n", encoding="utf-8")
            catalog.write_text(
                json.dumps([
                    {"entry": "K10", "editorial_title": "Ten", "occurrences": [], "software": []},
                    {"entry": "K2", "editorial_title": "Two", "occurrences": [], "software": []},
                ]),
                encoding="utf-8",
            )
            publish.write_text(json.dumps({"assets": []}), encoding="utf-8")

            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build-frontend-data.py"), str(catalog), str(publish), "--output", str(output)],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertFalse((output / "k99.json").exists())
            index = json.loads((output / "index.json").read_text(encoding="utf-8"))
            self.assertEqual([item["entry"] for item in index["entries"]], ["K2", "K10"])

    def test_release_builder_copies_only_referenced_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontend = root / "data"
            publish = root / "publish"
            output = root / "release"
            frontend.mkdir()
            asset_path = Path("store/assets/sha256/aa/icon.bin")
            (publish / asset_path).parent.mkdir(parents=True)
            (publish / asset_path).write_bytes(b"icon")
            unreferenced = publish / "store/assets/sha256/bb/private.bin"
            unreferenced.parent.mkdir(parents=True)
            unreferenced.write_bytes(b"do not publish")
            (frontend / "index.json").write_text(json.dumps({
                "publication": "Test",
                "medium": "Test medium",
                "entries": [{"entry": "K1", "curation_status": "identified"}],
            }), encoding="utf-8")
            (frontend / "k1.json").write_text(json.dumps({
                "entry": "K1",
                "publication": "Test",
                "medium": "Test medium",
                "curation_status": "identified",
                "software": [],
                "assets": [{
                    "entry": "K1",
                    "kind": "icon",
                    "original": {"public_path": asset_path.as_posix(), "sha256": "a" * 64},
                    "derivatives": [],
                }],
            }), encoding="utf-8")

            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build-release.py"), str(frontend), str(publish), "--output", str(output), "--expected-entries", "1"],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual((output / asset_path).read_bytes(), b"icon")
            self.assertFalse((output / "store/assets/sha256/bb/private.bin").exists())
            self.assertTrue((output / "404.html").is_file())

    def test_release_builder_rejects_asset_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontend = root / "data"
            publish = root / "publish"
            frontend.mkdir()
            publish.mkdir()
            (frontend / "index.json").write_text(json.dumps({
                "publication": "Test",
                "medium": "Test medium",
                "entries": [{"entry": "K1", "curation_status": "identified"}],
            }), encoding="utf-8")
            (frontend / "k1.json").write_text(json.dumps({
                "entry": "K1",
                "publication": "Test",
                "medium": "Test medium",
                "curation_status": "identified",
                "software": [],
                "assets": [{
                    "entry": "K1",
                    "kind": "icon",
                    "original": {"public_path": "store/../secret", "sha256": "a" * 64},
                    "derivatives": [],
                }],
            }), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build-release.py"), str(frontend), str(publish), "--output", str(root / "release"), "--expected-entries", "1"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unsafe asset public_path", result.stderr)

    def test_release_artifact_zip_is_deterministic(self):
        script = ROOT / "scripts" / "build-release-artifact.py"
        spec = importlib.util.spec_from_file_location("release_artifact", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "bootdisk-web-test"
            source.mkdir()
            (source / "b.txt").write_text("second\n", encoding="utf-8")
            (source / "a.txt").write_text("first\n", encoding="utf-8")
            first = root / "first.zip"
            second = root / "second.zip"
            module.deterministic_zip(source, first)
            module.deterministic_zip(source, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(module.sha256(first), module.sha256(second))

    def test_deployment_verifier_checks_documents_assets_hashes_and_404(self):
        verifier = (ROOT / "scripts" / "verify-deployment.py").read_text(encoding="utf-8")
        self.assertIn('fetch(args.base_url, "archive.html")', verifier)
        self.assertIn('fetch(args.base_url, "data/index.json")', verifier)
        self.assertIn('expected_status=404', verifier)
        self.assertIn('f"data/{entry_id.lower()}.json"', verifier)
        self.assertIn('hashlib.sha256(body).hexdigest()', verifier)
        self.assertIn('ThreadPoolExecutor(max_workers=args.workers)', verifier)
        self.assertIn('executor.map(fetch_entry, entries)', verifier)
        self.assertIn('executor.map(verify_asset, sorted(assets))', verifier)
        self.assertNotIn("ftp.domeneshop.no", verifier)


if __name__ == "__main__":
    unittest.main()
