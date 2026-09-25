#!/usr/bin/env python3
"""Append independently observed source posts without rebinding existing decisions."""
import argparse
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
from frontend_contract import validate_frontend_data, require

spec=importlib.util.spec_from_file_location('collection_builder',Path(__file__).with_name('build-collection.py'))
collection=importlib.util.module_from_spec(spec);spec.loader.exec_module(collection)


def append_posts(base, config_path, output):
    base=Path(base).resolve();config_path=Path(config_path).resolve();output=Path(output).absolute()
    index=deepcopy(validate_frontend_data(base))
    require(index.get('schema')=='bootdisk-web-collection-1','base must be a collection')
    require(not output.exists() and not output.is_symlink(),'output must be new')
    config=json.loads(config_path.read_text());inputs=config.get('media',[])
    require(isinstance(inputs,list) and bool(inputs),'missing supplemental media')
    require(all(not i.get('legacy_links') for i in inputs),'supplements must use qualified links')
    for item in inputs:
        matches=[m for m in index['media'] if m['id']==item['id']]
        require(len(matches)==1,'supplement refers to unknown medium')
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.supplement-',dir=output.parent))
    try:
        with tempfile.TemporaryDirectory(prefix='source-posts-') as temp:
            added=Path(temp)/'data';extra=collection.build_collection(config_path,added)
            for medium in extra['media']:
                current=next(m for m in index['media'] if m['id']==medium['id'])
                require(all(current[k]==medium[k] for k in ('publication','medium')),'supplement medium labels differ')
                manifest=medium['source_manifest']
                previous=[current['source_manifest'],*current.get('supplemental_manifests',[])]
                require(manifest not in previous,'source already included')
                current.setdefault('supplemental_manifests',[]).append(manifest)
                current.setdefault('supplemental_image_requirements',{})[manifest]=['icon']
            existing={e['entry'].lower() for e in index['entries']}
            for summary in extra['entries']:
                name=summary['entry'].lower()
                require(name not in existing,'supplement replaces an existing route')
                existing.add(name)
                doc=json.loads((added/(name+'.json')).read_text())
                require(any(a['kind']=='icon' for a in doc['assets']),'supplement lacks original artwork')
                desc=(doc.get('source_context',{}).get('description') or {}).get('value')
                require(isinstance(desc,str) and bool(desc.strip()),'supplement lacks source description')
                doc['source_order']=summary['source_order']=len(index['entries'])
                index['entries'].append(summary)
                (stage/(name+'.json')).write_text(json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
        # Copy existing cards verbatim, including decisions, RTF links and evidence.
        for summary in validate_frontend_data(base)['entries']:
            name=summary['entry'].lower()+'.json';shutil.copyfile(base/name,stage/name)
        (stage/'index.json').write_text(json.dumps(index,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
        validate_frontend_data(stage,len(index['entries']))
        os.rename(stage,output)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return index


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('base',type=Path);p.add_argument('config',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=append_posts(a.base,a.config,a.output);print('entries:',len(result['entries']))
if __name__=='__main__':main()
