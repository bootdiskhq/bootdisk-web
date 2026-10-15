"""Public loaders must revalidate mutable data, even with a fresh cached copy."""
import shutil,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(shutil.which('node'),'Node required')
class PublicCacheTests(unittest.TestCase):
 def test_all_public_loaders_revalidate(self):
  subprocess.run(['node','-e',r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
(async()=>{
 for(const file of ['archive.js','app.js']){
  const calls=[];
  const ctx=vm.createContext({URLSearchParams,console,window:{location:{search:'?entry=K37'}},
   fetch:(url,options)=>{calls.push({url,options});return new Promise(()=>{});}});
  // Run the real initial loader; responses stay pending so DOM rendering is irrelevant.
  vm.runInContext(fs.readFileSync(file,'utf8').split('render().catch')[0],ctx);
  vm.runInContext('render()',ctx);
  assert.deepStrictEqual(calls.map(c=>c.url),file==='archive.js'?['data/index.json']:['data/k37.json','data/index.json']);
  for(const c of calls)assert.equal(c.options?.cache,'no-cache',file+' must revalidate '+c.url);
 }
 const ctx=vm.createContext({console});
 vm.runInContext(fs.readFileSync('collection-core.js','utf8'),ctx);
 // The update overview's two loaders (updates-core.js) revalidate too.
 const uctx=vm.createContext({URLSearchParams,console,Intl,Date});
 vm.runInContext(fs.readFileSync('updates-core.js','utf8'),uctx);
 const seen=[];
 const ufetch=async(url,options)=>{seen.push([url,options?.cache]);return{ok:true,status:200,json:async()=>url.endsWith('index.json')?{entries:[]}:{schema:'bootdisk-public-updates-v2',releases:[],events:[]}};};
 await uctx.loadUpdates(ufetch);await uctx.loadUpdateIndex(ufetch);
 assert.deepStrictEqual(seen,[['data/public-updates.json','no-cache'],['data/index.json','no-cache']]);
 const fetcher=async(url,options)=>({ok:true,json:async()=>({status:options?.cache==='no-cache'?'identified':'pending'})});
 const result=await ctx.loadJson('data/index.json',fetcher);
 assert.equal(result.status,'identified');
 await assert.rejects(ctx.loadJson('data/index.json',async()=>({ok:false,status:503})),/503/);
})();
"""],cwd=ROOT,check=True)
