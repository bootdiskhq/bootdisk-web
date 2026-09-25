import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('attach_documents',ROOT/'scripts/attach-source-documents.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class SourceDocumentTests(unittest.TestCase):
    def test_exact_binding_preserves_card_and_wrong_disc_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);data=root/'data';data.mkdir();key={'manifest':'sha256:'+'a'*64,'entry':'K1'}
            card={'entry':'K1','publication':'Test','medium':'CD','curation_status':'pending','software':[],'assets':[],'source_context':{'key':key,'description':{'value':'Keep original','source_ref':key}}}
            (data/'k1.json').write_text(json.dumps(card));(data/'index.json').write_text(json.dumps({'publication':'Test','medium':'CD','entries':[{'entry':'K1','curation_status':'pending'}]}))
            sha='b'*64;doc={'key':key,'sha256':sha,'size':12,'text':'Other original','original':{'sha256':sha,'size':12,'media_type':'application/rtf','public_path':f'store/documents/sha256/bb/{sha}.rtf'}}
            pub={'schema':'bootdisk-published-documents-1','manifest':key['manifest'],'documents':[doc]}
            module.attach(data,[pub],root/'out');result=json.loads((root/'out/k1.json').read_text())
            self.assertEqual(result.pop('source_documents'),[doc]);self.assertEqual(result,card)
            self.assertEqual(json.loads((data/'k1.json').read_text()),card)
            doc['key']={'manifest':'sha256:'+'c'*64,'entry':'K1'}
            with self.assertRaises(ValueError):module.attach(data,[pub],root/'bad')
            self.assertFalse((root/'bad').exists())
            doc['key']=key;doc['original']['public_path']='https://example.com/unsafe.rtf'
            with self.assertRaises(ValueError):module.attach(data,[pub],root/'unsafe')
            self.assertFalse((root/'unsafe').exists())
