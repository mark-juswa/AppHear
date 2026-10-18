"""Remove audited alphabet entry/release resets, retaining source signing motion.

Offline only. All word actions (including corrected LOVE) and geometry stay intact.
No finger/shoulder clamp, new gesture, idle layer or Android dependency.
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

def main():
    root=Path(__file__).resolve().parents[1]/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1'
    target=root/'fingerspelling-avatar.glb';manifest_path=target.with_suffix('.json')
    manifest=json.loads(manifest_path.read_text());raw=target.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==manifest['sha256']
    if manifest.get('signingPosture'):
        print('Signing posture already prepared; no changes');return
    assert manifest['sha256']=='bcd0e4b634b267baf3979f3193958520469ba91f69cd265406b76e9873d07d11'
    model=c.hands.Model(target);g=copy.deepcopy(model.g)
    binary=bytearray(model.binary[:g['buffers'][0]['byteLength']]);audit=[]
    def accessor(values,kind):
        values=np.asarray(values,dtype='<f4')
        while len(binary)%4:binary.append(0)
        index=len(g['bufferViews']);g['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=values.nbytes));binary.extend(values.tobytes())
        entry=dict(bufferView=index,componentType=5126,count=len(values),type=kind)
        if kind=='SCALAR':entry.update(min=[float(values.min())],max=[float(values.max())])
        result=len(g['accessors']);g['accessors'].append(entry);return result
    for letter in manifest['letters']:
        name=letter['animationName'];tracks=model.tracks(name);duration=max(max(t['times']) for t in tracks)
        # These exact fixtures have 250ms added bind endpoints plus ~250ms
        # source raising/lowering. J/Z traces occupy the retained central span.
        start=.50;end=duration-.50;hold=.18
        assert end-start>=.70
        animation=next(a for a in g['animations'] if a['name']==name)
        animation['samplers']=[]
        for channel,track in zip(animation['channels'],tracks):
            times=sorted({start,end}|{float(t) for t in track['times'] if start<t<end})
            output=[c.sample(track,t).tolist() for t in times]
            output.append(output[-1]);new_times=[t-start for t in times]+[end-start+hold]
            # Float32 duplicates are not valid glTF input times.
            assert np.all(np.diff(np.asarray(new_times,dtype=np.float32))>0)
            sampler=len(animation['samplers']);animation['samplers'].append(dict(
                input=accessor(new_times,'SCALAR'),output=accessor(output,'VEC4' if track['path']=='rotation' else 'VEC3'),interpolation='LINEAR'))
            channel['sampler']=sampler
        letter['durationMs']=round((end-start+hold)*1000)
        audit.append(dict(letter=letter['letter'],sourceStartSeconds=start,sourceEndSeconds=end,
                          holdSeconds=hold,durationSeconds=end-start+hold))
    assert [a for a in g['animations'] if not a['name'].startswith('SIGN_LETTER_')]==[
        a for a in model.g['animations'] if not a['name'].startswith('SIGN_LETTER_')]
    # A constant copy of the existing human's actual neutral pose supports a
    # mixer fade after the entire queue. It has no signing or breathing gesture.
    idle=dict(name='SIGN_RELAXED_NEUTRAL',samplers=[],channels=[])
    idle_times=accessor([0.,1.],'SCALAR')
    for track in model.tracks('SIGN_HELLO'):
        pose=c.sample(track,0.).tolist();sampler=len(idle['samplers'])
        idle['samplers'].append(dict(input=idle_times,output=accessor([pose,pose],'VEC4' if track['path']=='rotation' else 'VEC3'),interpolation='LINEAR'))
        idle['channels'].append(dict(sampler=sampler,target=dict(node=track['node'],path=track['path'])))
    g['animations'].append(idle)
    g['buffers'][0]['byteLength']=len(binary)
    encoded=json.dumps(g,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4)
    payload=struct.pack('<III',0x46546c67,2,12+8+len(encoded)+8+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    manifest['signingPosture']=dict(status='UNREVIEWED_SIGNING_WINDOW',sourceSha256=manifest['sha256'],
        method='Remove per-letter rest/raising/lowering; preserve signing-span poses; append held release for transitions',letters=audit)
    manifest['sha256']=hashlib.sha256(payload).hexdigest()
    target.write_bytes(payload);manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(sha256=manifest['sha256'],letters=len(audit),bytes=len(payload)),indent=2))

if __name__=='__main__':main()
