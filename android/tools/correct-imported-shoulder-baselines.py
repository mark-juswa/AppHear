"""Stage rig-specific clavicle calibration; preserve signing hands with arm IK.

Only imported actions with a stable arms-down preroll qualify. No finger,
spine, idle, alphabet, geometry or timing channel is changed. The per-clip
constant local correction retains clavicle movement relative to the source's
initial posture. Two-bone IK preserves wrist positions; wrist compensation
preserves every downstream finger's world pose. Unreachable/unstable clips
are rejected intact. This is a technical preview repair, not ASL validation.
"""
import argparse,copy,hashlib,importlib.util,json,struct
from pathlib import Path
import numpy as np

BASE_SHA='04fda79c9d0b05a75469cb6a9314662bd954aa4a18f6e0872226e145d56f2a76'
def sha(b):return hashlib.sha256(b).hexdigest()
def load_helpers():
    s=importlib.util.spec_from_file_location('hands',Path(__file__).with_name('audit-text-to-sign-hands.py'))
    h=importlib.util.module_from_spec(s);s.loader.exec_module(h);return h
def angle(a,b):
    a=np.asarray(a)/np.linalg.norm(a);b=np.asarray(b)/np.linalg.norm(b)
    return float(np.degrees(2*np.arccos(np.clip(abs(a@b),0,1))))
def swing(a,b):
    a=a/np.linalg.norm(a);b=b/np.linalg.norm(b);v=np.cross(a,b);c=float(a@b)
    if c>1-1e-12:return np.eye(3)
    if c<-1+1e-8:raise ValueError('Antiparallel IK segment; ambiguous bend plane')
    x,y,z=v;k=np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
    return np.eye(3)+k+k@k/(1+c)
def elbow_position(start,target,pole,l1,l2):
    delta=target-start;d=np.linalg.norm(delta)
    if d<1e-6 or d>l1+l2-1e-6 or d<abs(l1-l2)+1e-6:
        raise ValueError('Original wrist target unreachable after clavicle calibration')
    axis=delta/d;along=(l1*l1-l2*l2+d*d)/(2*d)
    normal=pole-start;normal-=axis*(normal@axis)
    if np.linalg.norm(normal)<1e-6:raise ValueError('Ambiguous near-straight elbow plane')
    return start+axis*along+normal/np.linalg.norm(normal)*np.sqrt(max(0,l1*l1-along*along))

def corrected_pose(m,h,original,offsets):
    """Rigid target bones; exact world wrists and downstream finger transforms."""
    R=h.r;old=R.world(m.nodes,m.parents,m.order,original);out=dict(original)
    for side in ['Left','Right']:
        shoulder,arm,fore,hand=[m.names[side+n] for n in ['Shoulder','Arm','ForeArm','Hand']]
        out[(shoulder,'rotation')]=R.quaternion(offsets[side]@R.rotation(original[(shoulder,'rotation')]))
        current=R.world(m.nodes,m.parents,m.order,out)
        start=current[arm][:3,3];target=old[hand][:3,3]
        l1=np.linalg.norm(old[fore][:3,3]-old[arm][:3,3]);l2=np.linalg.norm(old[hand][:3,3]-old[fore][:3,3])
        elbow=elbow_position(start,target,old[fore][:3,3],l1,l2)
        world_arm=swing(old[fore][:3,3]-old[arm][:3,3],elbow-start)@R.orient(old[arm])
        out[(arm,'rotation')]=R.quaternion(R.orient(current[shoulder]).T@world_arm)
        world_fore=swing(old[hand][:3,3]-old[fore][:3,3],target-elbow)@R.orient(old[fore])
        out[(fore,'rotation')]=R.quaternion(world_arm.T@world_fore)
        out[(hand,'rotation')]=R.quaternion(world_fore.T@R.orient(old[hand]))
    new=R.world(m.nodes,m.parents,m.order,out)
    finger_nodes=[i for name,i in m.names.items() if 'Hand' in name]
    error=max(float(np.max(np.abs(old[i]-new[i]))) for i in finger_nodes)
    if error>1e-5:raise ValueError(f'Hand/finger world transform not preserved: {error}')
    return out,new,error

def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--words');a=p.parse_args()
    h=load_helpers();R=h.r;root=Path(__file__).resolve().parents[2]
    folder=root/'android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1'
    asset=folder/'fingerspelling-avatar.glb';payload=asset.read_bytes();assert sha(payload)==BASE_SHA
    manifest=json.loads((folder/'integration-manifest.json').read_text(encoding='utf-8'))
    m=h.Model(asset);g=copy.deepcopy(m.g);binary=bytearray(m.binary)
    neutral={(t['node'],t['path']):R.sample(t,0) for t in m.tracks('SIGN_RELAXED_NEUTRAL') if t['path']=='rotation'}
    a.output.mkdir(parents=True,exist_ok=True);changed=[];skipped=[]
    names={x['name']:x for x in g['animations']}
    usecount={}
    for action in g['animations']:
        for sampler in action['samplers']:usecount[sampler['output']]=usecount.get(sampler['output'],0)+1
    selected=manifest['entries'] if not a.words else [e for e in manifest['entries'] if e['id'] in a.words.split(',')]
    assert not a.words or len(selected)==len(set(a.words.split(',')))
    for e in selected:
        action=names[e['animationName']];tracks=m.tracks(e['animationName'])
        duration=max(t['times'][-1] for t in tracks)
        lookup={(t['node'],t['path']):t for t in tracks}
        source_frames=[m.pose(tracks,t) for t in [.2,.2416667,.2833333,.325]]
        hips=source_frames[0][m.names['Hips']][:3,3]
        max_height=max(float(f[m.names[s+'Hand']][1,3]-hips[1]) for f in source_frames for s in ['Left','Right'])
        travel=max(float(np.linalg.norm(f[m.names[s+'Hand']][:3,3]-source_frames[0][m.names[s+'Hand']][:3,3])) for f in source_frames[1:] for s in ['Left','Right'])
        try:
            if max_height>=.15 or travel>=.02:raise ValueError('No stable arms-down preroll; preserve intentional posture')
            offsets={};initial={}
            for side in ['Left','Right']:
                node=m.names[side+'Shoulder'];track=lookup[(node,'rotation')];first=R.sample(track,.2)
                if max(angle(first,R.sample(track,t)) for t in [.2416667,.2833333,.325])>2:
                    raise ValueError('Clavicle already moving in preroll; preserve intentional movement')
                offsets[side]=R.rotation(neutral[(node,'rotation')])@R.rotation(first).T
                initial[side]=angle(neutral[(node,'rotation')],first)
            if max(initial.values())<.5:raise ValueError('Already aligned to the rig neutral')
            clock=np.asarray(tracks[0]['times']);assert all(np.array_equal(t['times'],clock) for t in tracks)
            samples=[];max_error=0.;correction_steps=[]
            for time in clock[1:-1]:
                original={(t['node'],t['path']):R.sample(t,float(time)) for t in tracks}
                pose,world,error=corrected_pose(m,h,original,offsets);max_error=max(max_error,error)
                samples.append(pose)
            updates=[]
            affected={m.names[s+n] for s in ['Left','Right'] for n in ['Shoulder','Arm','ForeArm','Hand']}
            for ch in action['channels']:
                node=ch['target']['node']
                if ch['target']['path']!='rotation' or node not in affected:continue
                sampler=action['samplers'][ch['sampler']];index=sampler['output'];assert usecount[index]==1
                acc=g['accessors'][index];view=g['bufferViews'][acc['bufferView']]
                assert acc['componentType']==5126 and acc['type']=='VEC4' and 'byteStride' not in view
                q=m.data(index).copy();before=q.copy();q[1:-1]=[f[(node,'rotation')] for f in samples]
                for j in range(1,len(q)):
                    if q[j-1]@q[j]<0:q[j]*=-1
                inner_steps=[angle(a,b) for a,b in zip(q[1:-2],q[2:-1])]
                if max(inner_steps,default=0)>=90:raise ValueError('IK creates abrupt rotation; keep original clip')
                corrections=[R.rotation(new)@R.rotation(old).T for new,old in zip(q[1:-1],before[1:-1])]
                variation=[angle(R.quaternion(a),R.quaternion(b)) for a,b in zip(corrections,corrections[1:])]
                if max(variation,default=0)>10:raise ValueError('Unstable IK compensation; keep original clip')
                correction_steps.extend(variation)
                updates.append((view.get('byteOffset',0)+acc.get('byteOffset',0),q.astype('<f4').tobytes()))
            assert len(updates)==8
            for offset,data in updates:binary[offset:offset+len(data)]=data
            changed.append(dict(id=e['id'],action=e['animationName'],initialClavicleOffsetDegrees=initial,
                maxHandWorldMatrixError=max_error,maxCompensationStepDegrees=max(correction_steps,default=0),
                frames=len(samples),fingerLocalTracksUnchanged=True,timingUnchanged=True))
            print(json.dumps(dict(changed=len(changed),skipped=len(skipped),word=e['id'])),flush=True)
        except (ValueError,AssertionError) as error:
            skipped.append(dict(id=e['id'],reason=str(error)))
    assert len(changed)+len(skipped)==len(selected)
    # No buffer offsets, geometry, skeleton, clocks or action identities change.
    assert g==m.g
    meta=json.dumps(g,separators=(',',':')).encode();meta+=b' '*(-len(meta)%4)
    out=struct.pack('<III',0x46546c67,2,28+len(meta)+len(binary))+struct.pack('<II',len(meta),0x4e4f534a)+meta+struct.pack('<II',len(binary),0x004e4942)+binary
    (a.output/'avatar.glb').write_bytes(out)
    report=dict(status='STAGED_SHOULDER_CALIBRATION_PREVIEW',baselineSha256=BASE_SHA,sha256=sha(out),
                entriesRetained=743,actionsRetained=821,selectedCount=len(selected),changed=changed,skipped=skipped,qualifiedAslValidations=0,
                correction='Per-clip preroll clavicle calibration; exact wrist targets and finger world poses preserved using two-bone arm IK')
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(changed=len(changed),skipped=len(skipped),sha256=report['sha256'])),flush=True)
if __name__=='__main__':main()
