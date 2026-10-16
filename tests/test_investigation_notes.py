import unittest
from test_source_catalog import pu

class InvestigationNotesTests(unittest.TestCase):
    def doc(self):
        key={'manifest':'sha256:'+'a'*64,'entry':'K1'}
        return {'source_context':{'key':key,'issues':{'value':['conflicting_launch_targets']}},
                'source_catalog':{'key':dict(key),'file_association':{'explanation':{'explanation':'Originalknappen peker feil.'}}}}
    def test_explanation_replaces_generic_warning(self):
        self.assertEqual(pu.visible_projection(self.doc())['source_notes'],['investigation:Originalknappen peker feil.'])
    def test_wrong_source_falls_back(self):
        d=self.doc(); d['source_catalog']['key']['entry']='K2'
        self.assertEqual(pu.visible_projection(d)['source_notes'],['unresolved_file_references'])
    def test_changed_text_is_public_change(self):
        d=self.doc(); before=pu.visible_projection(d)
        d['source_catalog']['file_association']['explanation']['explanation']='Ny forklaring.'
        self.assertIn('source_issues_changed',pu.change_codes(before,pu.visible_projection(d)))
    def test_private_completion_date_does_not_create_update(self):
        d=self.doc(); before=pu.visible_projection(d)
        d['source_catalog']['file_association']['explanation']['completed_at']='2026-10-16'
        self.assertEqual(pu.change_codes(before,pu.visible_projection(d)),[])

    def test_browser_helper_uses_same_source_binding(self):
        import shutil,subprocess
        from pathlib import Path
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        script='''const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx=vm.createContext({});vm.runInContext(fs.readFileSync('app.js','utf8').split('async function render()')[0],ctx);
const key={manifest:'sha256:a',entry:'K1'};
ctx.entry={source_context:{key},source_catalog:{key:{...key},file_association:{explanation:{explanation:'Forklaring.'}}}};
assert.equal(vm.runInContext('sourceInvestigationExplanation(entry)',ctx),'Forklaring.');
ctx.entry.source_catalog.key.entry='K2';assert.equal(vm.runInContext('sourceInvestigationExplanation(entry)',ctx),null);
'''
        subprocess.run([node,'-e',script],cwd=Path(__file__).resolve().parents[1],check=True,capture_output=True)
