import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    def setUp(self):
        self.entry = json.loads((ROOT / "data" / "k37.json").read_text(encoding="utf-8"))

    def test_k37_joins_catalog_identity_and_publish_assets(self):
        self.assertEqual(self.entry["entry"], "K37")
        self.assertEqual(self.entry["software"][0]["software_id"], "software:winamp")
        self.assertEqual(self.entry["software"][0]["version"], "2.76")
        self.assertEqual({asset["kind"] for asset in self.entry["assets"]}, {"icon", "screenshot"})

    def test_assets_remain_bound_to_same_ingest_entry(self):
        for asset in self.entry["assets"]:
            self.assertEqual(asset["entry"], self.entry["entry"])
            self.assertTrue(asset["original"]["public_path"].startswith("/store/assets/sha256/"))
            for derivative in asset["derivatives"]:
                self.assertTrue(derivative["public_path"].startswith("/store/derivatives/"))


if __name__ == "__main__":
    unittest.main()
