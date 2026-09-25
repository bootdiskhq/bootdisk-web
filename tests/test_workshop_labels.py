import shutil
import subprocess
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class WorkshopLabelTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node.js required')
    def test_technical_route_is_not_display_name(self):
        script=r"""
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
for(const file of ['app.js','archive.js']) {
 const context=vm.createContext({});
 vm.runInContext(fs.readFileSync(file,'utf8').split('function sourceLabel(entry)')[0]+'function sourceLabel(entry)'+fs.readFileSync(file,'utf8').split('function sourceLabel(entry)')[1].split('\n}\n')[0]+'\n}',context);
 for(const id of ['Tool53616e647261','kcd-1-2001--Tool41646452656d6f7665']) {
   const record={entry:id,editorial_title:'Sandra'};
   assert.equal(context.sourceLabel(record),'Verktøymenyen');
   assert.equal(record.entry,id);
   assert.equal(record.editorial_title,'Sandra');
 }
 assert.equal(context.sourceLabel({entry:'kcd-1-2001--K1',source_entry:'K1'}),'K1');
 assert.equal(context.sourceLabel({entry:'ToolPro'}),'ToolPro');
}
"""
        subprocess.run([shutil.which('node'),'-e',script],cwd=ROOT,check=True)
