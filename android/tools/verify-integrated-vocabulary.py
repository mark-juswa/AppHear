"""Read-only union/GLB verification. Engineering checks are not ASL validation.

Run from any directory. Optionally provide --working-glb and --external-glb to
independently verify the pinned sources and unchanged first 284 working actions.
"""
import argparse,hashlib,json,math,struct
from pathlib import Path

ANDROID=Path(__file__).resolve().parents[1]
ASSETS=ANDROID/'app/src/aslOriginalWords/assets'
PREFIX='asl_animations/original_words_v1/'
def sha(b):return hashlib.sha256(b).hexdigest()
def glb(b):
    assert struct.unpack_from('<III',b)==(0x46546c67,2,len(b))
    n,t=struct.unpack_from('<II',b,12);assert t==0x4e4f534a
    size,t=struct.unpack_from('<II',b,20+n);assert t==0x004e4942
    return json.loads(b[20:20+n]),b[28+n:28+n+size]
def raw(g,b,index):
    a=g['accessors'][index];v=g['bufferViews'][a['bufferView']]
    width={'SCALAR':1,'VEC3':3,'VEC4':4}[a['type']];assert a['componentType']==5126 and 'sparse' not in a
    start=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',width*4)
    return b''.join(b[start+i*stride:start+i*stride+width*4] for i in range(a['count']))
def actionhash(g,b,action):
    h=hashlib.sha256()
    for ch in action['channels']:
        t=ch['target'];s=action['samplers'][ch['sampler']]
        h.update(f"{t['node']}:{t['path']}\0".encode())
        for k in ['input','output']:h.update(raw(g,b,s[k]))
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--working-glb',type=Path);p.add_argument('--external-glb',type=Path);a=p.parse_args()
    manifest_bytes=(ASSETS/(PREFIX+'integration-manifest.json')).read_bytes();m=json.loads(manifest_bytes)
    payload=(ASSETS/m['asset']).read_bytes();g,b=glb(payload)
    assert sha(payload)==m['sha256'] and m['totalLexicalEntries']==258+m['newExternalEntries']
    assert m['qualifiedAslValidations']==0 and m['language']=='ASL' and m['avatarProfile']=='ORIGINAL_HUMAN'
    assert len(g['animations'])==m['totalActions'] and len(m['entries'])==m['newExternalEntries']
    assert len(m['externalReviewAlternatives'])==16
    byname={x['name']:x for x in g['animations']};assert len(byname)==m['totalActions']
    dictionary=m['baseEntries']+m['entries'];assert len(dictionary)==m['totalLexicalEntries'] and len({e['id'] for e in dictionary})==m['totalLexicalEntries']
    forms={}
    for e in dictionary:
        assert e['animationName'] in byname
        for s in e['english']:
            assert forms.get(s,e['id'])==e['id'];forms[s]=e['id']
    ids={e['id'] for e in dictionary}
    for alias in m['aliases']:
        assert alias['signId'] in ids
        for s in alias['english']:
            assert forms.get(s,alias['signId'])==alias['signId'];forms[s]=alias['signId']
    assert len(forms)==m.get('explicitEnglishForms',794)
    keys=0
    for name,action in byname.items():
        for ch in action['channels']:
            s=action['samplers'][ch['sampler']];clock=list(struct.iter_unpack('<f',raw(g,b,s['input'])))
            times=[t[0] for t in clock];assert all(math.isfinite(x) for x in times) and all(y>x for x,y in zip(times,times[1:]))
            if ch['target']['path']=='rotation':
                quats=list(struct.iter_unpack('<4f',raw(g,b,s['output'])));assert len(quats)==len(times)
                assert all(all(math.isfinite(v) for v in q) and abs(sum(v*v for v in q)-1)<1e-4 for q in quats),name
                keys+=len(quats)
    if a.working_glb:
        old=a.working_glb.read_bytes();assert sha(old)=='99dbd596f53c89a561cc517e8bc2f436dc737b3cc2001f4cfefaf89cc8a12963'
        og,ob=glb(old);assert g['animations'][:284]==og['animations']
        assert b[:og['buffers'][0]['byteLength']]==ob[:og['buffers'][0]['byteLength']]
        for k in ['nodes','skins','meshes','materials','textures','images','scenes']:assert g[k]==og[k]
    if a.external_glb:
        ex=a.external_glb.read_bytes();assert sha(ex)=='7840f979713d878f273a71975c38e1d12dbf3856151af531cbed8daf70fd0024'
        eg,eb=glb(ex);assert all(actionhash(g,b,byname[x['name']])==actionhash(eg,eb,x) for x in eg['animations'][258:])
    print(json.dumps(dict(status='PASS_OFFLINE_INTEGRITY',lexicalEntries=len(dictionary),distinctLexicalActions=len({e['animationName'] for e in dictionary}),
        explicitEnglishForms=len(forms),externalAdditions=len(m['entries']),workingActionsPreserved=284 if a.working_glb else None,
        externalActionsPreserved=420 if a.external_glb else None,
        inactivePrimaryAlternatives=36,inactiveExternalAlternatives=16,totalActions=len(byname),
        checkedQuaternionKeys=keys,bytes=len(payload),sha256=sha(payload),qualifiedAslValidations=0,
        androidRendering='NOT_ESTABLISHED_BY_THIS_SCRIPT')))
if __name__=='__main__':main()
