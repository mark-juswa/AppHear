"""Offline, explicit sign-specific base-hand repair; no runtime joint limits.

Only restores straight bind-relative finger articulation in six explicitly
reference-guided flat supporting hands. Leaves thumbs, dominant hands,
wrist/arm/body tracks and source times untouched. This pose is not imposed on
other signs or alphabet animations, which require their own articulation.
This is a technical preview correction, not qualified ASL validation.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import numpy as np

spec=importlib.util.spec_from_file_location('prior',Path(__file__).with_name('correct-text-to-sign-word-fingers.py'))
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


def main():
    config=json.loads(Path(__file__).with_name('flat-base-hand-profiles.json').read_text())
    android=Path(__file__).resolve().parents[1]
    target=android/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb'
    manifest=json.loads(target.with_suffix('.json').read_text())
    raw=target.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    assert sha==manifest['sha256']
    if manifest.get('flatBaseHandCorrection'):
        print('Flat-base correction already applied; no changes');return
    assert sha==config['sourceSha256'],'Unknown baseline; inspect before correcting'
    model=p.c.hands.Model(target);g=copy.deepcopy(model.g)
    binary=bytearray(model.binary[:g['buffers'][0]['byteLength']]);profiles=[]
    for profile in config['profiles']:
        animation=next(a for a in g['animations'] if a['name']==profile['animationName'])
        names={profile['side']+'Hand'+finger+str(joint) for finger in ['Index','Middle','Ring','Pinky'] for joint in [1,2,3]}
        changed=[]
        for channel in animation['channels']:
            node=channel['target']['node'];name=model.nodes[node].get('name')
            if channel['target']['path']!='rotation' or name not in names:continue
            sampler=animation['samplers'][channel['sampler']]
            times=model.data(sampler['input']).flatten();source=model.data(sampler['output'])
            base=np.asarray(model.nodes[node].get('rotation',[0,0,0,1]))
            values=[]
            for time,q in zip(times,source):
                # A signed-X repair alone leaves the large source sideways
                # rotations intact. Use this avatar's own straight phalanges
                # for the reference-required flat surface, not a made-up fist.
                fixed=p.c.r.unit(base)
                # Preserve full neutral endpoints; correction eases in/out
                # rather than snapping an otherwise unchanged source clip.
                u=min(1.,max(0.,min(float(time),float(times[-1]-time))/.18))
                values.append(p.c.sample(dict(path='rotation',interpolation='LINEAR',times=[0.,1.],values=[q,fixed]),u*u*(3-2*u)))
            values=np.asarray(values,dtype='<f4')
            for i in range(1,len(values)):
                if np.dot(values[i-1],values[i])<0:values[i]=-values[i]
            assert np.max(np.abs(np.linalg.norm(values,axis=1)-1))<1e-5
            while len(binary)%4:binary.append(0)
            view=len(g['bufferViews']);g['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=values.nbytes));binary.extend(values.tobytes())
            accessor=len(g['accessors']);g['accessors'].append(dict(bufferView=view,componentType=5126,count=len(values),type='VEC4'))
            index=len(animation['samplers']);animation['samplers'].append(dict(input=sampler['input'],output=accessor,interpolation=sampler.get('interpolation','LINEAR')))
            channel['sampler']=index;changed.append(name)
        assert set(changed)==names
        profiles.append(dict(**profile,correctedNodes=changed))
    for key in ['nodes','skins','meshes','materials','textures','images','scenes']:assert g[key]==model.g[key]
    allowed={x['animationName'] for x in profiles}
    assert [a for a in g['animations'] if a['name'] not in allowed]==[a for a in model.g['animations'] if a['name'] not in allowed]
    g['buffers'][0]['byteLength']=len(binary)
    encoded=json.dumps(g,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4)
    payload=struct.pack('<III',0x46546c67,2,28+len(encoded)+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    manifest['flatBaseHandCorrection']=dict(status=config['status'],sourceSha256=sha,profiles=profiles,qualifiedASLValidation=False,
        method='Scoped bind-relative straight-finger pose in six reference-required flat base hands; no runtime constraints; source endpoints/times, thumbs, dominant hands and all other joints preserved')
    manifest['sha256']=hashlib.sha256(payload).hexdigest()
    target.write_bytes(payload);target.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Keep the loader checksum in sync: it must reject corrupted bundle data.
    loader=android/'app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt'
    text=loader.read_text();assert sha in text
    loader.write_text(text.replace(sha,manifest['sha256']))
    print(json.dumps(dict(sha256=manifest['sha256'],correctedActions=len(profiles),correctedChannels=sum(len(x['correctedNodes']) for x in profiles)),indent=2))


if __name__=='__main__':main()
