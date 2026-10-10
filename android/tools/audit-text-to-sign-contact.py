"""Independent sampled glTF playback/skin check, including between corrective keys.

python tools/audit-text-to-sign-contact.py BEFORE.glb AFTER.glb OUTPUT_DIR
CPU renderer only; not a device or qualified ASL evaluation.
"""
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image,ImageDraw

spec=importlib.util.spec_from_file_location('contact',Path(__file__).with_name('correct-text-to-sign-love.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

def render(model,mesh,world,draw,offset,angle,label):
    vertices=mesh.skin(world);triangles=mesh.triangles
    theta=np.radians(angle);camera=np.array([[np.cos(theta),0,-np.sin(theta)],[0,1,0],[np.sin(theta),0,np.cos(theta)]])
    v=vertices@camera.T
    def project(p):return (offset[0]+180+p[0]*720,offset[1]+560-(p[1]-.86)*720)
    torso_set=set(mesh.torso_triangles.flatten().tolist())
    for tri in triangles[np.argsort(v[triangles][:,:,2].mean(1))]:
        poly=v[tri]
        normal=np.cross(poly[1]-poly[0],poly[2]-poly[0]);shade=int(130+65*abs(normal[2])/(np.linalg.norm(normal)+1e-9))
        color=(shade-65,shade-5,shade-5) if all(int(i) in torso_set for i in tri) else (shade,shade-20,shade-35)
        draw.polygon([project(p) for p in poly],fill=color)
    draw.text((offset[0]+8,offset[1]+8),label,fill='black')

def main():
    before=c.hands.Model(sys.argv[1]);after=c.hands.Model(sys.argv[2]);out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
    oldmesh=c.ContactMesh(before);newmesh=c.ContactMesh(after)
    for key in ['nodes','skins','meshes','materials','textures','images','scenes']:assert before.g[key]==after.g[key]
    assert before.binary[:before.g['buffers'][0]['byteLength']]==after.binary[:before.g['buffers'][0]['byteLength']]
    assert [a for a in before.g['animations'] if a['name']!='SIGN_LOVE']==[a for a in after.g['animations'] if a['name']!='SIGN_LOVE']
    old=before.animations['SIGN_LOVE'];new=after.animations['SIGN_LOVE']
    allowed={after.names[s+p] for s in ['Left','Right'] for p in ['Arm','ForeArm','Hand']}
    assert len(old['channels'])==len(new['channels'])
    changed=0
    for x,y in zip(old['channels'],new['channels']):
        assert x['target']==y['target']
        if x!=y:
            changed+=1;assert x['target']['node'] in allowed and x['target']['path']=='rotation'
    assert changed==6
    for sampler in new['samplers'][len(old['samplers']):]:
        assert np.all(np.diff(after.data(sampler['input']).flatten())>0), 'Duplicate timestamps'
        assert np.max(np.abs(np.linalg.norm(after.data(sampler['output']),axis=1)-1))<1e-5
    actions=['SIGN_LOVE','SIGN_HELLO','SIGN_BEAUTIFUL','SIGN_HELP','SIGN_THANKS']
    actions+=[f'SIGN_LETTER_{letter}_WOLF3D_PREVIEW' for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
    report=dict(renderer='CPU glTF skinning with SLERP; no device/ASL validation',actions=[],changedChannels=changed,unchangedActions=228)
    for name in actions:
        tracks=after.tracks(name);duration=max(max(t['times']) for t in tracks)
        # 347 poses do not align with the 521 corrective keys: exercise SLERP
        # between keys rather than rechecking only the authored keyframes.
        samples=347 if name=='SIGN_LOVE' else 25
        max_depth={'hand':0.,'forearm':0.};old_depth={'hand':0.,'forearm':0.};held_xy=0.;orientation_error=0.;bone_length_error=0.
        for time in np.linspace(0,duration,samples):
            w=c.pose(after,tracks,float(time));vertices=newmesh.skin(w)
            for side in ['Left','Right']:
                for part,values in newmesh.depths(vertices,side).items():max_depth[part]=max(max_depth[part],float(max(0,values.max())))
            if name=='SIGN_LOVE':
                ow=c.pose(before,before.tracks(name),float(time));ov=oldmesh.skin(ow)
                for side in ['Left','Right']:
                    for part,values in oldmesh.depths(ov,side).items():old_depth[part]=max(old_depth[part],float(max(0,values.max())))
                    hand=after.names[side+'Hand']
                    if .30<=time<=duration-.30:held_xy=max(held_xy,float(np.max(np.abs(w[hand][:2,3]-ow[hand][:2,3]))))
                    orientation_error=max(orientation_error,float(np.max(np.abs(c.r.orient(w[hand])-c.r.orient(ow[hand])))))
                    arm,elbow=after.names[side+'Arm'],after.names[side+'ForeArm']
                    for parent,child in [(arm,elbow),(elbow,hand)]:
                        bone_length_error=max(bone_length_error,abs(float(np.linalg.norm(w[child][:3,3]-w[parent][:3,3])-np.linalg.norm(ow[child][:3,3]-ow[parent][:3,3]))))
        entry=dict(action=name,samples=samples,maxFrontSurfaceDepthMeters=max_depth)
        if name=='SIGN_LOVE':
            entry.update(beforeDepthMeters=old_depth,heldXYErrorMeters=held_xy,wristOrientationMatrixError=orientation_error,boneLengthErrorMeters=bone_length_error)
            assert max_depth['hand']<.003 and max_depth['forearm']<.010, entry
            assert held_xy<.001 and bone_length_error<1e-5,entry
        report['actions'].append(entry)
        image=Image.new('RGB',(4*360,600),'#dde3e4');draw=ImageDraw.Draw(image);time=duration*.5
        for i,(model,mesh,angle,title) in enumerate([(before,oldmesh,0,'BEFORE FRONT'),(after,newmesh,0,'AFTER FRONT'),(before,oldmesh,75,'BEFORE SIDE'),(after,newmesh,75,'AFTER SIDE')]):
            render(model,mesh,c.pose(model,model.tracks(name),time),draw,(i*360,0),angle,name+' '+title)
        image.save(out/(name.lower()+'-comparison.png'))
    (out/'contact-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['actions'][0],indent=2));print(f'Checked {len(actions)} actions. Other signs are measured, not automatically modified.')

if __name__=='__main__':main()
