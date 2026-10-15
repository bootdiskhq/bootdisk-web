import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import public_updates as pu


class SourceCatalogTests(unittest.TestCase):
    def test_source_documented_is_not_product_identified(self):
        before = {"curation_status": "pending", "editorial_title": "Ad-aware", "software": []}
        after = {**before, "source_catalog": {"status": "documented"}}
        old, new = pu.visible_projection(before), pu.visible_projection(after)
        self.assertEqual(new["status"], "source_documented")
        self.assertIsNone(new["version"])
        self.assertIsNone(new["software_name"])
        self.assertEqual(pu.change_codes(old, new), ["source_documented"])

    def test_existing_product_assessment_keeps_precedence(self):
        for status in ("curated", "interpreted"):
            doc = {"curation_status": "identified", "software": [{"status": status}],
                   "source_catalog": {"status": "documented"}}
            self.assertEqual(pu.visible_projection(doc)["status"],
                             "interpreted" if status == "interpreted" else "identified")

    def test_source_conflict_notes_stay_visible(self):
        doc = {"curation_status": "pending", "source_catalog": {"status": "documented"},
               "source_context": {"issues": {"value": ["conflicting_launch_targets"]}}}
        self.assertEqual(pu.visible_projection(doc)["source_notes"], ["unresolved_file_references"])

    def test_withdrawal_keeps_product_and_source_claims_separate(self):
        pending = pu.visible_projection({"curation_status": "pending"})
        documented = {**pending, "status": "source_documented"}
        identified = {**pending, "status": "identified"}
        self.assertEqual(pu.change_codes(documented, pending), ["source_documentation_withdrawn"])
        self.assertEqual(pu.change_codes(identified, documented), ["identification_withdrawn", "source_documented"])

    @unittest.skipUnless(shutil.which("node"), "Node required")
    def test_archive_and_detail_agree_and_filter_excludes_from_pending(self):
        script = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx=vm.createContext({URLSearchParams,window:{location:{search:''}}});
vm.runInContext(fs.readFileSync('archive.js','utf8').split('async function render()')[0],ctx);
vm.runInContext(fs.readFileSync('app.js','utf8').split('async function render()')[0],ctx);
const rows=[{entry:'K1',curation_status:'pending',source_catalog_status:'documented'},
{entry:'K2',curation_status:'pending'}];
ctx.rows=rows;
assert.equal(vm.runInContext('archiveStatusParameter("source_documented")',ctx),'source_documented');
assert.equal(vm.runInContext('archiveStatusParameter("invalid")',ctx),'all');
assert.equal(vm.runInContext('filterEntries(rows,"","pending").length',ctx),1);
assert.equal(vm.runInContext('filterEntries(rows,"","source_documented")[0].entry',ctx),'K1');
assert.equal(vm.runInContext('statusLabel("pending",null,"documented")',ctx),'Oppgitt på CD-en');
assert.equal(vm.runInContext('statusLabel("identified","curated","documented")',ctx),'Identifisert');
'''
        subprocess.run([shutil.which("node"), "-e", script], cwd=ROOT, check=True, capture_output=True)
