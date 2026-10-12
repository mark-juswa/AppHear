"""Check correction scope against Git checkpoint; render before/after hands."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import numpy as np
from PIL import Image,ImageDraw

spec=importlib.util.spec_from_file_location('repair',Path(__file__).with_name('correct-flat-base-text-to-sign-hands.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def main():
    android=Path(__file__).resolve().parents[1]
    relative='app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb'
    target=android/relative;out=android.parents[1]/'AppHear-Word-Finger-Fix-Review'
    raw=subprocess.check_output(['git','show','checkpoint/all-hands-audit-20261011:android/'+relative],cwd=android)
    manifest=json.loads(target.with_suffix('.json').read_text())
    profiles=manifest['flatBaseHandCorrection']['profiles']
    assert hashlib.sha256(raw).hexdigest()==manifest['flatBaseHandCorrection']['sourceSha256']
    # Only this script-owned single temporary file is removed after reading.
    with tempfile.NamedTemporaryFile(suffix='.glb',delete=False) as temporary:
        temporary.write(raw);temporary_path=Path(temporary.name)
    try:before=c.p.c.hands.Model(temporary_path)
    finally:temporary_path.unlink()
    after=c.p.c.hands.Model(target)
    for key in ['nodes','skins','meshes','materials','textures','images','scenes']:assert before.g[key]==after.g[key]
    assert before.binary[:before.g['buffers'][0]['byteLength']]==after.binary[:before.g['buffers'][0]['byteLength']]
    allowed={p['animationName']:set(p['correctedNodes']) for p in profiles}
    assert [a for a in before.g['animations'] if a['name'] not in allowed]==[a for a in after.g['animations'] if a['name'] not in allowed]
    report=dict(qualifiedAslValidation=False,renderer='CPU glTF SLERP and skinning',alphabetActionsUnchanged=26,
                otherActionsUnchanged=226,geometryUnchanged=True,originalBinaryPrefixUnchanged=True,profiles=[])
    for profile in profiles:
        name=profile['animationName'];old=before.animations[name];new=after.animations[name];changed=[]
        for a,b in zip(old['channels'],new['channels']):
            assert a['target']==b['target']
            if a!=b:
                bone=after.nodes[a['target']['node']]['name'];assert bone in allowed[name]
                changed.append(bone)
                old_sampler=old['samplers'][a['sampler']];new_sampler=new['samplers'][b['sampler']]
                assert old_sampler['input']==new_sampler['input']
                assert np.max(np.abs(before.data(old_sampler['output'])[[0,-1]]-after.data(new_sampler['output'])[[0,-1]]))<1e-6
        assert set(changed)==allowed[name]
        tracks=after.tracks(name);duration=max(t['times'][-1] for t in tracks)
        world_error=0.;straight_error=0.
        for time in np.linspace(0,duration,61):
            w=c.p.c.pose(after,tracks,float(time));oldw=c.p.c.pose(before,before.tracks(name),float(time))
            for bone in [s+part for s in ['Left','Right'] for part in ['Shoulder','Arm','ForeArm','Hand']]:
                world_error=max(world_error,float(np.max(np.abs(w[after.names[bone]]-oldw[after.names[bone]]))))
            if .25<=time<=duration-.25:
                for bone in allowed[name]:
                    node=after.names[bone];track=next(t for t in tracks if t['node']==node and t['path']=='rotation')
                    d=c.p.delta(np.asarray(after.nodes[node].get('rotation',[0,0,0,1])),c.p.c.sample(track,float(time)))
                    straight_error=max(straight_error,float(np.linalg.norm(d[:3])))
        assert world_error==0 and straight_error<1e-5,(name,world_error,straight_error)
        image=Image.new('RGB',(880,270),'#eef2f2');draw=ImageDraw.Draw(image);metrics={}
        for column,model in enumerate([before,after]):
            world=c.p.c.pose(model,model.tracks(name),duration*.5)
            for view,axes in enumerate([(0,1),(2,1)]):
                metric=c.p.c.hands.render(draw,model,world,'Left',(220*(column*2+view),0),axes=axes,bones=True)
                draw.text((220*(column*2+view)+6,6),('BEFORE ' if column==0 else 'AFTER ')+name,fill='black')
                if view==0:metrics['before' if column==0 else 'after']=metric
        image.save(out/(name.lower()+'-flat-base-before-after.png'))
        report['profiles'].append(dict(action=name,changedChannels=len(changed),sampledPoses=61,armWristMatrixError=world_error,
                                      heldStraightFingerError=straight_error,handMeshMetrics=metrics,reference=profile['reference']))
    (out/'flat-base-hand-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
