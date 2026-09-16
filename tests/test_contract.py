import json
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
            self.assertTrue(asset["original"]["public_path"].startswith("/store/assets/sha256/"))
            for derivative in asset["derivatives"]:
                self.assertTrue(derivative["public_path"].startswith("/store/derivatives/"))

    def test_browser_selects_entry_document_from_query_parameter(self):
        javascript = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn('new URLSearchParams(window.location.search).get("entry")', javascript)
        self.assertIn('`data/${entryId}.json`', javascript)

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


if __name__ == "__main__":
    unittest.main()
