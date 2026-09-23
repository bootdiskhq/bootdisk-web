import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from frontend_contract import validate_frontend_data
spec = importlib.util.spec_from_file_location('collection', ROOT / 'scripts/build-collection.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'collection.json'
        self.inputs = []

    def medium(self, slug, entry, digest, legacy=False):
        data = self.root / slug
        data.mkdir()
        key = {'manifest': 'sha256:' + digest * 64, 'entry': entry}
        detail = {'entry': entry, 'publication': 'Test', 'medium': slug,
                  'curation_status': 'pending', 'software': [], 'assets': [],
                  'source_context': {'key': key, 'description': {'value': 'Original\r\ntekst', 'source_ref': {**key, 'pointer': '/entries/0/text'}}}}
        (data / (entry.lower() + '.json')).write_text(json.dumps(detail))
        (data / 'index.json').write_text(json.dumps({'publication': 'Test', 'medium': slug,
             'entries': [{'entry': entry, 'curation_status': 'pending', 'editorial_title': slug}]}))
        self.inputs.append({'id': slug, 'data': slug, 'legacy_links': legacy})
        self.config.write_text(json.dumps({'media': self.inputs}))
        return data / (entry.lower() + '.json')

    def build(self):
        return module.build_collection(self.config, self.root / 'output')

    def test_two_equal_source_ids_are_distinct_and_legacy_link_survives(self):
        self.medium('old', 'K1', 'a', True)
        self.medium('new', 'K1', 'b')
        result = self.build()
        self.assertEqual([e['entry'] for e in result['entries']], ['K1', 'new--K1'])
        self.assertEqual([e['source_entry'] for e in result['entries']], ['K1', 'K1'])
        validate_frontend_data(self.root / 'output', 2)
        new = json.loads((self.root / 'output/new--k1.json').read_text())
        self.assertEqual(new['software'], [])
        self.assertEqual(new['source_context']['description']['value'], 'Original\r\ntekst')
        self.assertEqual(new['source_context']['key']['entry'], 'K1')

    def test_director_ids_preserve_case_and_source_order(self):
        self.medium('director', 'Spil1', 'a')
        result = self.build()
        self.assertEqual(result['entries'][0]['entry'], 'director--Spil1')
        self.assertTrue((self.root / 'output/director--spil1.json').exists())

    def test_cross_source_description_fails_before_output(self):
        path = self.medium('one', 'K1', 'a')
        doc = json.loads(path.read_text())
        doc['source_context']['description']['source_ref']['entry'] = 'K2'
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, 'cross-source observation'):
            self.build()
        self.assertFalse((self.root / 'output').exists())

    def test_duplicate_manifest_is_rejected(self):
        self.medium('one', 'K1', 'a')
        self.medium('two', 'K1', 'a')
        with self.assertRaisesRegex(ValueError, 'duplicate source manifest'):
            self.build()

    def test_two_legacy_media_cannot_overwrite_history(self):
        self.medium('one', 'K1', 'a', True)
        self.medium('two', 'K1', 'b', True)
        with self.assertRaisesRegex(ValueError, 'only one medium'):
            self.build()

    def test_existing_output_is_never_overwritten(self):
        self.medium('one', 'K1', 'a')
        self.build()
        marker = self.root / 'output/human-note.txt'
        marker.write_text('keep')
        with self.assertRaisesRegex(ValueError, 'new directory'):
            self.build()
        self.assertEqual(marker.read_text(), 'keep')

    def test_namespace_traversal_is_rejected(self):
        self.medium('one', 'K1', 'a')
        self.inputs[0]['id'] = '../secret'
        self.config.write_text(json.dumps({'media': self.inputs}))
        with self.assertRaisesRegex(ValueError, 'invalid medium id'):
            self.build()

    def test_release_remains_static_and_keeps_both_discs(self):
        self.medium('old', 'K1', 'a', True)
        self.medium('new', 'Spil1', 'b')
        self.build()
        subprocess.run([sys.executable, str(ROOT / 'scripts/build-release.py'), str(self.root / 'output'),
                        str(self.root), '--output', str(self.root / 'release'), '--expected-entries', '2'], check=True, capture_output=True)
        files = {p.name for p in (self.root / 'release').iterdir()}
        self.assertFalse(any('curat' in p or 'overview' in p or 'review' in p for p in files))
        self.assertTrue((self.root / 'release/data/k1.json').exists())
        self.assertTrue((self.root / 'release/data/new--spil1.json').exists())
        self.assertIn('entry=new--Spil1', (self.root / 'release/sitemap.xml').read_text())

    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_filter_sort_and_route_validation(self):
        script = r'''
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const ctx=vm.createContext({URLSearchParams, window:{location:{search:'?entry=new--Spil1'}}});
vm.runInContext(fs.readFileSync('archive.js','utf8').split('async function render()')[0],ctx);
const entries=[{entry:'new--Spil1',medium_id:'new',medium:'K-CD 1/2000',source_order:1,curation_status:'pending'},
{entry:'K1',medium_id:'old',source_order:0,curation_status:'identified'}];
assert.deepEqual(Array.from(ctx.filterEntries(entries,'','all','new'),e=>e.entry),['new--Spil1']);
assert.equal(ctx.filterEntries(entries,'1/2000','pending').length,1);
assert.deepEqual(Array.from(ctx.sortEntries(entries,'source'),e=>e.entry),['K1','new--Spil1']);
vm.runInContext(fs.readFileSync('app.js','utf8').split('async function render()')[0],ctx);
assert.equal(ctx.requestedEntry(),'new--spil1');
ctx.window.location.search='?entry=K37'; assert.equal(ctx.requestedEntry(),'k37');
for(const input of ['../secret','/secret','new--../../x','<script>','new--']) {
 ctx.window.location.search='?entry='+encodeURIComponent(input); assert.throws(()=>ctx.requestedEntry());
}
'''
        subprocess.run([shutil.which('node'), '-e', script], cwd=ROOT, check=True)
