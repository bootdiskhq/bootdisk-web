import json
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

    def test_entry_reports_loading_errors_and_source_metadata_accessibly(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="page-description"', html)
        self.assertIn('aria-busy="true"', html)
        self.assertIn('id="entry-error" role="alert"', html)
        self.assertIn('document.querySelector("#page-description").content', javascript)
        self.assertIn('setAttribute("aria-busy", "false")', javascript)

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
            (frontend / "index.json").write_text(json.dumps({"entries": [{"entry": "K1"}]}), encoding="utf-8")
            (frontend / "k1.json").write_text(json.dumps({"entry": "K1", "assets": [{"original": {"public_path": asset_path.as_posix()}}]}), encoding="utf-8")

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
            (frontend / "index.json").write_text(json.dumps({"entries": [{"entry": "K1"}]}), encoding="utf-8")
            (frontend / "k1.json").write_text(json.dumps({"entry": "K1", "assets": [{"original": {"public_path": "store/../secret"}}]}), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build-release.py"), str(frontend), str(publish), "--output", str(root / "release"), "--expected-entries", "1"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unsafe asset public_path", result.stderr)


if __name__ == "__main__":
    unittest.main()
