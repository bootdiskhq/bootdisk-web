import shutil
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('node'),'Node required')
class LiveAdapterTests(unittest.TestCase):
    def test_transport_replays_exact_payload_and_preserves_conflicts(self):
        program=r'''
const assert=require('node:assert/strict');
const {createLiveAdapter}=require('./curate-live-adapter.js');
(async()=>{
const calls=[];let fail=false;
const conflict={code:'revision_conflict',message:'Changed',retryable:false,field_errors:{},current_entry:{revision:'new'}};
const fetcher=async(path,options)=>{calls.push({path,options});if(path==='/api/session')return {ok:true,json:async()=>({schema:'bootdisk-curator-v1',token:'session',manifest:'m'})};if(fail)return {ok:false,json:async()=>conflict};return {ok:true,json:async()=>({schema:'bootdisk-curator-v1',operation_id:'op'})};};
const adapter=await createLiveAdapter({fetcher});assert.equal(adapter.fixtureMode,false);
const payload={key:{manifest:'m',entry:'K23'},expected_revision:'r',operation_id:'op'};
await adapter.approve(payload);await adapter.approve(payload);
assert.equal(calls[1].options.body,calls[2].options.body);
assert.equal(calls[1].options.headers['X-Bootdisk-Token'],'session');
fail=true;await assert.rejects(adapter.saveDraft(payload),error=>error===conflict);
let attempts=0;
await assert.rejects(createLiveAdapter({fetcher:async()=>{attempts++;throw Error('offline')}}),error=>error.code==='service_unavailable');
assert.equal(attempts,1);
})();
'''
        result=subprocess.run([shutil.which('node'),'-e',program],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_success_unlocks_rendered_controls_and_undo_refreshes_accepted_fields(self):
        program=r'''
const {harness,key,assert}=require('./tests/curator_harness.js');
(async()=>{
const {controller}=harness();await controller.start();await controller.select(key('K23'));
let visibleBusy=null;controller.subscribe(state=>{visibleBusy=state.busy});
await controller.dispatch('commit');assert.equal(visibleBusy,false);
await controller.setFilter('all');await controller.select(key('K23'));
const token=controller.state.draftToken;
await controller.dispatch('undo');assert.equal(visibleBusy,false);
assert.ok(controller.state.draftToken>token,'accepted claim labels must rerender after undo');
})();
'''
        import os
        result=subprocess.run([shutil.which('node'),'-e',program],cwd=ROOT,capture_output=True,text=True,
                              env=dict(os.environ,CURATOR_WEB_ROOT=str(ROOT)))
        self.assertEqual(result.returncode,0,result.stderr)
