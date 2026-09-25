import importlib.util
import json
from pathlib import Path
import sys
import unittest
import test_collection
ROOT=test_collection.ROOT
sys.path.insert(0,str(ROOT/'scripts'))
from frontend_contract import validate_frontend_data
spec=importlib.util.spec_from_file_location('append_posts',ROOT/'scripts/append-source-posts.py');app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
spec=importlib.util.spec_from_file_location('release_scope',ROOT/'scripts/build-release.py');release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

class SupplementalTests(unittest.TestCase):
    setUp=test_collection.CollectionTests.setUp
    medium=test_collection.CollectionTests.medium
    build=test_collection.CollectionTests.build
    def setup_addition(self):
        self.medium('old','K1','a',True);self.build()
        base=self.root/'output';before=(base/'k1.json').read_bytes()
        source=self.root/'old';doc=json.loads((source/'k1.json').read_text())
        (source/'k1.json').unlink()
        doc['entry']='Tool12';key={'entry':'Tool12','manifest':'sha256:'+'b'*64};doc['source_context']['key']=key;doc['source_context']['description']['source_ref']=key
        # Valid identity-bearing image, independent of rendering.
        asset={'entry':'Tool12','kind':'icon','source_path':'cast#BITD:1','original':{'sha256':'c'*64,'size':1,'public_path':'store/a'},'derivatives':[]}
        doc['assets']=[asset]
        (source/'tool12.json').write_text(json.dumps(doc))
        (source/'index.json').write_text(json.dumps({'publication':'Test','medium':'old','entries':[{'entry':'Tool12','curation_status':'pending'}]}))
        self.config.write_text(json.dumps({'media':[{'id':'old','data':'old'}]}))
        return base,before,source
    def test_append_preserves_original_bytes_and_binding(self):
        base,before,source=self.setup_addition();out=self.root/'combined';index=app.append_posts(base,self.config,out)
        self.assertEqual((out/'k1.json').read_bytes(),before)
        self.assertEqual(len(index['entries']),2)
        validate_frontend_data(out,2)
        doc=json.loads((out/'old--tool12.json').read_text());doc['source_manifest']='sha256:'+'d'*64
        (out/'old--tool12.json').write_text(json.dumps(doc))
        with self.assertRaises(ValueError):validate_frontend_data(out)
    def test_missing_artwork_rejected_before_output(self):
        base,_,source=self.setup_addition();p=source/'tool12.json';doc=json.loads(p.read_text());doc['assets']=[];p.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError,'artwork'):app.append_posts(base,self.config,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
    def test_existing_coverage_is_not_weakened_by_supplement(self):
        medium={'id':'x','source_manifest':'a','image_requirements':{'all_entries':['screenshot']},'supplemental_manifests':['b'],'supplemental_image_requirements':{'b':['icon']}}
        old={'medium_id':'x','source_manifest':'a','entry':'old','assets':[]}
        new={'medium_id':'x','source_manifest':'b','entry':'new','assets':[{'kind':'icon'}]}
        with self.assertRaisesRegex(ValueError,'No images|Missing screenshot'):release.validate_image_coverage({'media':[medium]},[(None,old),(None,new)])
        old['assets']=[{'kind':'screenshot'}];release.validate_image_coverage({'media':[medium]},[(None,old),(None,new)])
        new['assets']=[]
        with self.assertRaisesRegex(ValueError,'supplemental'):release.validate_image_coverage({'media':[medium]},[(None,old),(None,new)])
