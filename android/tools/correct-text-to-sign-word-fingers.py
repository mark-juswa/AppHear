"""Repair explicitly reviewed native finger-axis profiles, never clamp all signs.

Local quaternion delta is measured relative to the actual bind pose. Only the
negative X flexion component is reflected for allow-listed finger tracks; swing,
other axes, angular magnitude, thumb opposition, body and timing are preserved.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import numpy as np

spec=importlib.util.spec_from_file_location('contact',Path(__file__).with_name('correct-text-to-sign-love.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

def multiply(a,b):
    return np.r_[a[3]*b[:3]+b[3]*a[:3]+np.cross(a[:3],b[:3]),a[3]*b[3]-a[:3]@b[:3]]

def delta(base,q):
    q=multiply(base*np.array([-1,-1,-1,1]),q)
    return -q if q[3]<0 else q

def repair(base,q):
    d=delta(base,np.asarray(q,dtype=float));d[0]=abs(d[0])
    return c.r.unit(multiply(base,d))

def main():
    config=json.loads(Path(__file__).with_name('native-word-hand-profiles.json').read_text())
    root=Path(__file__).resolve().parents[1]/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1'
    target=root/'fingerspelling-avatar.glb';manifest_path=target.with_suffix('.json');manifest=json.loads(manifest_path.read_text())
    raw=target.read_bytes();source=hashlib.sha256(raw).hexdigest();assert source==manifest['sha256']
    if manifest.get('wordFingerCorrection'):
        print('Native finger correction already applied; no changes');return
    assert source==config['sourceSha256'],'Unknown baseline: review before applying profiles'
    model=c.hands.Model(target);g=copy.deepcopy(model.g);binary=bytearray(model.binary[:g['buffers'][0]['byteLength']]);profiles=[]
    for profile in config['profiles']:
        animation=next(a for a in g['animations'] if a['name']==profile['animationName']);changed=[]
        names={side+'Hand'+finger+str(j) for side in profile['sides'] for finger in profile['fingers'] for j in profile['joints']}
        for channel in animation['channels']:
            node=channel['target']['node'];name=model.nodes[node].get('name','')
            if channel['target']['path']!='rotation' or name not in names:continue
            old=animation['samplers'][channel['sampler']];base=np.asarray(model.nodes[node].get('rotation',[0,0,0,1]))
            source_values=model.data(old['output']);times=model.data(old['input']).flatten();duration=float(times[-1])
            values=[]
            for time,q in zip(times,source_values):
                # Keep the source neutral endpoints and ease the correction
                # over entry/release. This also preserves the existing arm
                # contact clearance while the final hand lowers past the torso.
                u=min(1.,max(0.,min(float(time),duration-float(time))/.18));weight=u*u*(3-2*u)
                values.append(c.sample(dict(path='rotation',interpolation='LINEAR',times=[0.,1.],values=[q,repair(base,q)]),weight))
            values=np.asarray(values,dtype='<f4')
            for i in range(1,len(values)):
                if np.dot(values[i-1],values[i])<0:values[i]=-values[i]
            assert np.max(np.abs(np.linalg.norm(values,axis=1)-1))<1e-5
            while len(binary)%4:binary.append(0)
            view=len(g['bufferViews']);g['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=values.nbytes));binary.extend(values.tobytes())
            accessor=len(g['accessors']);g['accessors'].append(dict(bufferView=view,componentType=5126,count=len(values),type='VEC4'))
            index=len(animation['samplers']);animation['samplers'].append(dict(input=old['input'],output=accessor,interpolation=old.get('interpolation','LINEAR')))
            channel['sampler']=index;changed.append(name)
        assert set(changed)==names
        profiles.append(dict(**profile,correctedNodes=changed))
    g['buffers'][0]['byteLength']=len(binary)
    encoded=json.dumps(g,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4)
    payload=struct.pack('<III',0x46546c67,2,12+8+len(encoded)+8+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    manifest['wordFingerCorrection']=dict(status=config['status'],sourceSha256=source,profiles=profiles,
        method='Bind-relative negative local-X finger-flexion reflection; exact source times/endpoints, 180ms correction envelope; thumbs and all non-profile channels unchanged',
        qualifiedASLValidation=False)
    manifest['sha256']=hashlib.sha256(payload).hexdigest()
    target.write_bytes(payload);manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(sha256=manifest['sha256'],profiles=len(profiles),channels=sum(len(p['correctedNodes']) for p in profiles)),indent=2))

if __name__=='__main__':main()
