"""Correct only the new TIRED candidate's six arm/wrist rotation channels.

Input: candidate checkpoint 1d9abe3 (not Update-2). All finger channels, the other
257 actions, rig and original binary prefix stay byte-identical. This preserves
reviewed candidates without reauthoring them. No runtime controller changes.
"""
import copy,hashlib,importlib.util,json,struct,sys
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('batch',Path(__file__).with_name('expand-text-to-sign-batch3.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
SOURCE='9abc31e5eed7597c96e4cded055176427ea25fb8fd8999a32966409961208990'

def main(source,output,report):
    source,output,report=map(Path,(source,output,report))
    assert hashlib.sha256(source.read_bytes()).hexdigest()==SOURCE
    assert output.resolve()!=source.resolve()
    m=b.e.h.Model(source);author=b.Author(m);name='SIGN_TIRED_HUMAN_AUTHORED_PREVIEW'
    tracks=m.tracks(name);times=next(t['times'] for t in tracks if t['path']=='rotation')
    assert len(times)==79 and abs(times[-1]-2.6)<1e-6
    frames=[author.pose('tired',float(t/2.6)) for t in times]
    g=copy.deepcopy(m.g);binary=bytearray(m.binary[:g['buffers'][0]['byteLength']])
    action=next(a for a in g['animations'] if a['name']==name)
    allowed={m.names[side+part] for side in ['Right','Left'] for part in ['Arm','ForeArm','Hand']}
    changed=0
    for ch in action['channels']:
        node=ch['target']['node']
        if node not in allowed:continue
        assert ch['target']['path']=='rotation'
        values=np.asarray([f[(node,'rotation')] for f in frames],dtype='<f4')
        assert np.isfinite(values).all() and np.max(abs(np.linalg.norm(values,axis=1)-1))<1e-5
        for i in range(1,len(values)):
            if values[i-1]@values[i]<0:values[i]*=-1
        while len(binary)%4:binary.append(0)
        view=len(g['bufferViews']);g['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=values.nbytes));binary.extend(values.tobytes())
        accessor=len(g['accessors']);g['accessors'].append(dict(bufferView=view,componentType=5126,count=len(values),type='VEC4'))
        action['samplers'][ch['sampler']]['output']=accessor;changed+=1
    assert changed==6
    assert [a for a in g['animations'] if a['name']!=name]==[a for a in m.g['animations'] if a['name']!=name]
    for key in ['nodes','skins','meshes','materials','images','textures','scenes']:assert g[key]==m.g[key]
    # Finger data and every sampler except the six explicit arm/wrist outputs
    # remain untouched, including the entire old binary buffer prefix.
    original=m.animations[name]
    for old,new in zip(original['channels'],action['channels']):
        assert old==new
        if old['target']['node'] not in allowed:
            assert original['samplers'][old['sampler']]==action['samplers'][new['sampler']]
    g['buffers'][0]['byteLength']=len(binary);encoded=json.dumps(g,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4)
    data=struct.pack('<III',0x46546c67,2,28+len(encoded)+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    output.write_bytes(data);sha=hashlib.sha256(data).hexdigest()
    metadata=json.loads(source.with_suffix('.json').read_text());metadata['sha256']=sha
    record=dict(sourceBundleSha256=SOURCE,changedRotationChannels=6,unchangedActions=257,
      fingerChannelsUnchanged=True,sourceGeometryUnchanged=True,qualifiedAslValidation=False,
      correction='Bent hands slump downward through wrist rotation around stable chest-area MCP anchors; no downward sliding of the whole hand.')
    metadata['everydayExpansion3']['tiredCorrection']=record
    output.with_suffix('.json').write_text(json.dumps(metadata,indent=2)+'\n')
    report.write_text(json.dumps(dict(bundleSha256=sha,**record),indent=2)+'\n')
    print(json.dumps(dict(bundleSha256=sha,changedRotationChannels=6,unchangedActions=257)))

if __name__=='__main__':main(*sys.argv[1:4])
