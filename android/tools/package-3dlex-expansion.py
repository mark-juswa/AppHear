"""Append staged, checked rotations to an explicitly pinned human bundle.

Run only after reviewing conversion report.json. Never changes old animation,
alphabet, rig, geometry, or recognition assets. Git checkpoint is the rollback.
"""
import argparse,copy,csv,hashlib,importlib.util,json,re,struct
from pathlib import Path
import numpy as np

def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(value):return (json.dumps(value,indent=2,ensure_ascii=True)+'\n').encode('utf-8')
def replace(path,pattern,value):
    text=path.read_text(encoding='utf-8');text,n=re.subn(pattern,value,text);assert n==1,(path,pattern,n)
    path.write_text(text,encoding='utf-8',newline='\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('staged',type=Path)
    p.add_argument('--compact-buffer-views',action='store_true',help='Deduplicate identical raw storage without changing accessor values');p.add_argument('--baseline-sha256',default='7975abceb4c75e09cab995600d6b852edbd608a44e4e4a07550746544f7e7aec');a=p.parse_args()
    android=Path(__file__).resolve().parents[1];root=android.parent
    folder=android/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1'
    path=folder/'fingerspelling-avatar.glb';old=path.read_bytes()
    assert sha(old)==a.baseline_sha256,'Unexpected baseline; do not reapply'
    spec=importlib.util.spec_from_file_location('union',Path(__file__).with_name('verify-integrated-vocabulary.py'))
    v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    g,b=v.glb(old);g=copy.deepcopy(g);binary=bytearray(b[:g['buffers'][0]['byteLength']])
    before=json.loads((folder/'integration-manifest.json').read_text(encoding='utf-8'));m=copy.deepcopy(before)
    report=json.loads((a.staged/'report.json').read_text(encoding='utf-8'))
    assert report['baselineSha256']==sha(old),'Candidates belong to another baseline'
    old_actions=len(g['animations']);old_entries=before['totalLexicalEntries']
    old_additions=before['newExternalEntries'];old_forms=before['explicitEnglishForms']
    assert old_actions==before['totalActions']
    entries=report['entries'];assert len(entries)==report['added'] and entries
    ids={e['id'] for e in m['baseEntries']+m['entries']};names={x['name'] for x in g['animations']}
    parents={c:i for i,n in enumerate(g['nodes']) for c in n.get('children',[])};order=[]
    def visit(i):
        if i in order:return
        if i in parents:visit(parents[i])
        order.append(i)
    for i in range(len(g['nodes'])):visit(i)
    def accessor(values,kind):
        values=np.asarray(values,dtype='<f4');assert np.isfinite(values).all()
        binary.extend(b'\0'*(-len(binary)%4));vi=len(g['bufferViews'])
        g['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=values.nbytes));binary.extend(values.tobytes())
        ai=len(g['accessors']);item=dict(bufferView=vi,componentType=5126,count=len(values),type=kind)
        if kind=='SCALAR':item.update(min=[float(values.min())],max=[float(values.max())])
        g['accessors'].append(item);return ai
    for entry in entries:
        assert entry['id'] not in ids and entry['animationName'] not in names
        with np.load(a.staged/(entry['id']+'.npz')) as data:
            times=data['times'];rotations=data['rotations']
        assert sha(rotations.astype('<f4').tobytes())==entry['motionSha256']
        assert rotations.shape==(len(times),len(order),4) and np.all(np.diff(times)>0)
        assert np.max(np.abs(np.sum(rotations**2,axis=2)-1))<1e-4
        assert abs(times[1]-.2)<1e-6 and abs((times[-1]-times[-2])-.2)<1e-6
        inp=accessor(times,'SCALAR');action=dict(name=entry['animationName'],samplers=[],channels=[])
        for j,i in enumerate(order):
            if 'matrix' in g['nodes'][i]:continue
            q=rotations[:,j].copy()
            for k in range(1,len(q)):
                if q[k-1]@q[k]<0:q[k]*=-1
            si=len(action['samplers']);action['samplers'].append(dict(input=inp,output=accessor(q,'VEC4'),interpolation='LINEAR'))
            action['channels'].append(dict(sampler=si,target=dict(node=i,path='rotation')))
        g['animations'].append(action);ids.add(entry['id']);names.add(entry['animationName'])
    assert g['animations'][:old_actions]==v.glb(old)[0]['animations'] and binary[:len(b)]==b
    if a.compact_buffer_views:
        # Lossless buffer-view deduplication. Preserve every old accessor and action.
        original_bytes=bytes(binary);compact=bytearray();seen_views={}
        for view in g['bufferViews']:
            assert view['buffer']==0
            start=view.get('byteOffset',0);raw=original_bytes[start:start+view['byteLength']]
            key=(len(raw),sha(raw))
            if key in seen_views:
                offset=seen_views[key];assert compact[offset:offset+len(raw)]==raw
            else:
                compact.extend(b'\0'*(-len(compact)%4));offset=len(compact);compact.extend(raw);seen_views[key]=offset
            view['byteOffset']=offset
        old_g,old_b=v.glb(old)
        for old_view,new_view in zip(old_g['bufferViews'],g['bufferViews']):
            old_offset=old_view.get('byteOffset',0);b0=new_view.get('byteOffset',0);size=old_view['byteLength']
            assert old_b[old_offset:old_offset+size]==compact[b0:b0+size]
            assert {k:v0 for k,v0 in old_view.items() if k!='byteOffset'}=={k:v0 for k,v0 in new_view.items() if k!='byteOffset'}
        assert g['accessors'][:len(old_g['accessors'])]==old_g['accessors']
        for key in ['nodes','meshes','skins','images','materials','textures']:
            assert g.get(key)==old_g.get(key),key
        binary=compact
    g['buffers'][0]['byteLength']=len(binary);meta=json.dumps(g,separators=(',',':')).encode();meta+=b' '*(-len(meta)%4)
    binary.extend(b'\0'*(-len(binary)%4))
    payload=struct.pack('<III',0x46546c67,2,28+len(meta)+len(binary))+struct.pack('<II',len(meta),0x4e4f534a)+meta+struct.pack('<II',len(binary),0x004e4942)+binary
    new_sha=sha(payload);count=len(entries)
    m['entries']+=entries;m['sha256']=new_sha;m['totalActions']=old_actions+count
    m['totalLexicalEntries']=old_entries+count;m['newExternalEntries']=old_additions+count;m['explicitEnglishForms']=old_forms+count
    if 'direct3dLexExpansion' in m:
        m.setdefault('previousDirect3dLexExpansions',[]).append(copy.deepcopy(m['direct3dLexExpansion']))
    m['direct3dLexExpansion']=dict(previousBundleSha256=sha(old),previousLexicalEntries=old_entries,newEntries=count,
        sourceArchiveSha256=report['sourceArchiveSha256'],sourceUrl='https://osf.io/mqzyk/',
        license='CC-BY-4.0',terminalBindResetCorrection=True,qualifiedAslValidations=0)
    forms={}
    for e in m['baseEntries']+m['entries']:
        for form in e['english']:assert forms.get(form,e['id'])==e['id'];forms[form]=e['id']
    for alias in m['aliases']:
        for form in alias['english']:assert forms.get(form,alias['signId'])==alias['signId'];forms[form]=alias['signId']
    assert len(forms)==m['explicitEnglishForms']
    manifest=encoded(m);fingers=json.loads((folder/'fingerspelling-avatar.json').read_text(encoding='utf-8'))
    fingers['sha256']=new_sha;fingers['direct3dLexExpansion']=m['direct3dLexExpansion']
    domain=android/'app/src/main/java/com/example/apphear/domain/texttoasl'
    # All checks complete before mutation. Every pre-existing action/binary byte survives exactly.
    path.write_bytes(payload);(folder/'integration-manifest.json').write_bytes(manifest)
    (folder/'fingerspelling-avatar.json').write_bytes(encoded(fingers))
    replace(domain/'AslFingerspellingBundle.kt',r'const val SHA256 = "[a-f0-9]+"',f'const val SHA256 = "{new_sha}"')
    replace(domain/'AslFingerspellingBundle.kt',r'const val ACTION_COUNT = \d+',f'const val ACTION_COUNT = {old_actions+count}')
    replace(domain/'AslIntegratedVocabulary.kt',r'const val MANIFEST_SHA256 = "[a-f0-9]+"',f'const val MANIFEST_SHA256 = "{sha(manifest)}"')
    replace(domain/'AslIntegratedVocabulary.kt',r'const val ENTRIES = \d+',f'const val ENTRIES = {old_entries+count}')
    replace(domain/'AslIntegratedVocabulary.kt',r'const val ADDITIONS = \d+',f'const val ADDITIONS = {old_additions+count}')
    record=dict(newLexicalEntries=count,totalLexicalEntries=old_entries+count,totalActions=old_actions+count,englishForms=old_forms+count,
        bundleSha256=new_sha,manifestSha256=sha(manifest),preservedActionCount=old_actions,oldActionsUnchanged=True,alphabetAndGeometryUnchanged=True,
        qualifiedAslValidations=0)
    (a.staged/'packaging.json').write_bytes(encoded(record));print(json.dumps(record))
if __name__=='__main__':main()
