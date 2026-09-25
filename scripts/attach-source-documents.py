"""Join supplemental documents by exact source binding into a new disposable data tree."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import os
from frontend_contract import validate_frontend_data


def attach(data, publications, output):
    data, output = Path(data), Path(output)
    index = validate_frontend_data(data)
    documents = {e['entry']: json.loads((data/(e['entry'].lower()+'.json')).read_text()) for e in index['entries']}
    bindings = {(d.get('source_context',{}).get('key',{}).get('manifest'), d.get('source_context',{}).get('key',{}).get('entry')): d for d in documents.values()}
    seen = set()
    for pub in publications:
        if pub.get('schema') != 'bootdisk-published-documents-1': raise ValueError('unsupported documents')
        for doc in pub['documents']:
            key = (doc['key']['manifest'], doc['key']['entry'])
            if key not in bindings or key[0] != pub['manifest'] or key in seen: raise ValueError('unmatched/duplicate document source')
            seen.add(key)
            bindings[key]['source_documents'] = [doc]
    if output.exists(): raise ValueError('output must be new')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        stage=Path(temp)/'data';shutil.copytree(data,stage)
        for key,doc in documents.items(): (stage/(key.lower()+'.json')).write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
        validate_frontend_data(stage)
        os.rename(stage,output)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('data');p.add_argument('publications',nargs='+');p.add_argument('--output',required=True);a=p.parse_args()
    attach(a.data,[json.loads(Path(f).read_text()) for f in a.publications],a.output)
