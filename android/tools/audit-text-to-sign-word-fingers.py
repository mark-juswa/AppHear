"""Native-word finger/skin integrity, profile scope, contact and rendered checks."""
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image,ImageDraw

spec=importlib.util.spec_from_file_location('repair',Path(__file__).with_name('correct-text-to-sign-word-fingers.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r);c=r.c

def main():
    before=c.hands.Model(sys.argv[1]);after=c.hands.Model(sys.argv[2]);out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(Path(sys.argv[2]).with_suffix('.json').read_text());profiles=manifest['wordFingerCorrection']['profiles'];allowed={p['animationName']:set(p['correctedNodes']) for p in profiles}
    for key in ['nodes','skins','meshes','materials','textures','images','scenes']:assert before.g[key]==after.g[key]
    assert before.binary[:before.g['buffers'][0]['byteLength']]==after.binary[:before.g['buffers'][0]['byteLength']]
    assert [a for a in before.g['animations'] if a['name'] not in allowed]==[a for a in after.g['animations'] if a['name'] not in allowed]
    report=dict(qualifiedASLValidation=False,renderer='CPU glTF skinning with SLERP, not Android/WebGL',profiles=[],candidates=[],nativeActionsChecked=203,unchangedActions=227,bindMatrixError=after.bind_error,weightSumError=after.weight_error)
    assert after.bind_error<1e-5 and after.weight_error<1e-5
    for a in after.g['animations'][:203]:
        tracks=after.tracks(a['name']);duration=max(max(t['times']) for t in tracks)
        for t in tracks:
            assert np.isfinite(t['values']).all()
            if t['path']=='rotation':assert np.max(np.abs(np.linalg.norm(t['values'],axis=1)-1))<1e-5
        # A warning signature, not authorization to modify another handshape.
        for side in ['Left','Right']:
            severity=0.
            for time in np.linspace(0,duration,9):
                bends=[]
                for f in ['Index','Middle','Ring','Pinky']:
                    node=after.names[side+'Hand'+f+'2'];track=next(t for t in tracks if t['node']==node and t['path']=='rotation')
                    base=np.asarray(after.nodes[node].get('rotation',[0,0,0,1]));bends.append(r.delta(base,c.sample(track,float(time)))[0])
                severity=min(severity,max(bends))
            if severity<-.25:report['candidates'].append(dict(action=a['name'],side=side,signedFlexionComponent=float(severity),status='REQUIRES_SIGN_SPECIFIC_REVIEW_NOT_AUTOMATIC_REPAIR'))
    mesh=c.ContactMesh(after)
    for profile in profiles:
        name=profile['animationName'];old=before.animations[name];new=after.animations[name]
        changed=[]
        for x,y in zip(old['channels'],new['channels']):
            assert x['target']==y['target']
            if x!=y:
                node=after.nodes[x['target']['node']]['name'];assert x['target']['path']=='rotation' and node in allowed[name];changed.append(node)
        assert set(changed)==allowed[name]
        tr=after.tracks(name);du=max(max(t['times']) for t in tr)
        maxdepth={'hand':0.,'forearm':0.};world_error=0.;hand_results={}
        for time in np.linspace(0,du,347 if name=='SIGN_LOVE' else 41):
            w=c.pose(after,tr,float(time));oldw=c.pose(before,before.tracks(name),float(time));v=mesh.skin(w)
            for node in [after.names[side+part] for side in ['Left','Right'] for part in ['Shoulder','Arm','ForeArm','Hand']]:world_error=max(world_error,float(np.max(np.abs(w[node]-oldw[node]))))
            if name=='SIGN_LOVE':
                for side in ['Left','Right']:
                    for part,val in mesh.depths(v,side).items():maxdepth[part]=max(maxdepth[part],float(max(0,val.max())))
        assert world_error==0.,'Arm/wrist transform changed'
        if name=='SIGN_LOVE':assert maxdepth['hand']<.002 and maxdepth['forearm']<.01,(name,maxdepth)
        # Two hands, front and side, matched time and view. Bones expose bend axes.
        for side in ['Left','Right']:
            image=Image.new('RGB',(880,270),'#eef2f2')
            for col,model in enumerate([before,after]):
                world=c.pose(model,model.tracks(name),du*.5)
                for j,(axes,label) in enumerate([((0,1),'FRONT'),((2,1),'SIDE')]):
                    panel=Image.new('RGB',(220,270),'#eef2f2');draw=ImageDraw.Draw(panel)
                    metric=c.hands.render(draw,model,world,side,(0,0),axes=axes,bones=True)
                    draw.text((6,6),('BEFORE' if col==0 else 'AFTER')+' '+side+' '+label,fill='black');image.paste(panel,((col*2+j)*220,0))
                    if j==0:hand_results[('before' if col==0 else 'after')+side]=metric
            image.save(out/(name.lower()+'-'+side.lower()+'-hands.png'))
        report['profiles'].append(dict(action=name,changedChannels=len(changed),armWristMatrixError=world_error,loveTorsoDepthMeters=maxdepth if name=='SIGN_LOVE' else None,handMetrics=hand_results))
    (out/'word-finger-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(profiles=report['profiles'],candidateHands=len(report['candidates']),candidateWords=len({p['action'] for p in report['candidates']}),unchangedActions=227),indent=2))

if __name__=='__main__':main()
