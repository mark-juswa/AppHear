"""Generate a LOVE-only reference-guided, unvalidated fist/wrist candidate.

This never overwrites production assets. Supply the pinned baseline with
--source after production is updated. Inspect the candidate on Android and
review the generated surface/scope report before applying it separately.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
from functools import cache

import numpy as np
from PIL import Image,ImageDraw

parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--report',type=Path,required=True)
args=parser.parse_args()
android=Path(__file__).resolve().parents[1]
tools=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('prior',tools/'correct-text-to-sign-word-fingers.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
source=args.source or android/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='907944cee4c3ea684d4eddc8b734db75a1c21e06e04d3092f9fbdab7cbdd7fd1'
model=p.c.hands.Model(source);tracks=model.tracks('SIGN_LOVE')
rest=p.c.r.world(model.nodes,model.parents,model.order)
g=copy.deepcopy(model.g);binary=bytearray(model.binary[:g['buffers'][0]['byteLength']])
animation=next(a for a in g['animations'] if a['name']=='SIGN_LOVE')
duration=max(t['times'][-1] for t in tracks)
fixed={};palm_local={};audit=[]
for side in ['Left','Right']:
    hand=model.names[side+'Hand']
    sign=1 if side=='Right' else -1
    n=sign*np.cross(rest[model.names[side+'HandIndex1']][:3,3]-rest[model.names[side+'HandPinky1']][:3,3],rest[model.names[side+'HandMiddle1']][:3,3]-rest[hand][:3,3])
    palm_local[side]=p.c.r.orient(rest[hand]).T@p.c.r.unit(n)
    normal=p.c.r.unit(n)
    for finger in ['Index','Middle','Ring','Pinky']:
        for joint,angle in [(1,80),(2,95),(3,50)]:
            node=model.names[side+'Hand'+finger+str(joint)]
            child=model.names[side+'Hand'+finger+str(joint+1)]
            direction=p.c.r.unit(rest[child][:3,3]-rest[node][:3,3])
            axis=p.c.r.orient(rest[node]).T@p.c.r.unit(np.cross(direction,normal))
            radians=np.radians(angle)/2
            delta=np.r_[axis*np.sin(radians),np.cos(radians)]
            fixed[node]=p.c.r.unit(p.multiply(np.array(model.nodes[node].get('rotation',[0,0,0,1])),delta))

@cache
def wrist_pose(time):
    w=p.c.pose(model,tracks,time);original_world=w;changes={};angles={}
    # Preserve the already collision-checked approach and final release. Apply
    # the new placement only after the arms have reached the signing area.
    u=min(1.,max(0.,min((time-.30)/.25,(duration-.30-time)/.25)))
    weight=u*u*(3-2*u)
    for side in ['Left','Right']:
        arm,elbow,hand=[model.names[side+part] for part in ['Arm','ForeArm','Hand']]
        shoulder,old_elbow,old_hand=[w[n][:3,3] for n in [arm,elbow,hand]]
        # Reference-guided preview: fists on opposite upper chest, forearms
        # diagonal from lowered elbows. No other clip uses this target.
        target=np.array([-.060 if side=='Left' else .060,1.335,.225 if side=='Left' else .295])
        target=old_hand*(1-weight)+target*weight
        axis=p.c.r.unit(target-shoulder);dist=np.linalg.norm(target-shoulder)
        l1=np.linalg.norm(old_elbow-shoulder);l2=np.linalg.norm(old_hand-old_elbow)
        along=(l1*l1-l2*l2+dist*dist)/(2*dist)
        center=shoulder+axis*along;radius=np.sqrt(max(0,l1*l1-along*along))
        preferred=np.array([.10 if side=='Left' else -.10,1.16,.235])
        preferred=old_elbow*(1-weight)+preferred*weight
        pole=p.c.r.unit(preferred-center-axis*((preferred-center)@axis))
        new_elbow=center+radius*pole
        arm_goal=p.c.between(old_elbow-shoulder,new_elbow-shoulder)@p.c.r.orient(w[arm])
        fore_goal=p.c.between(old_hand-old_elbow,target-new_elbow)@p.c.r.orient(w[elbow])
        changes[(arm,'rotation')]=p.c.r.quaternion(p.c.r.orient(w[model.parents[arm]]).T@arm_goal)
        changes[(elbow,'rotation')]=p.c.r.quaternion(arm_goal.T@fore_goal)
    w=p.c.pose(model,tracks,time,changes)
    for side in ['Left','Right']:
        arm,elbow,hand=[model.names[side+part] for part in ['Arm','ForeArm','Hand']]
        fa=p.c.r.orient(w[elbow]);axis=p.c.r.unit(w[hand][:3,3]-w[elbow][:3,3])
        base=np.asarray(model.nodes[hand].get('rotation',[0,0,0,1]))
        neutral=fa@p.c.r.rotation(base)
        normal=neutral@palm_local[side]
        normal=p.c.r.unit(normal-axis*(normal@axis))
        desired=np.array([0.,0.,-1.]);desired=p.c.r.unit(desired-axis*(desired@axis))
        angle=np.arctan2(axis@np.cross(normal,desired),normal@desired)
        # Axial roll stays in the forearm instead of concentrating it at the
        # wrist. Align the palm toward the chest and keep the wrist straight.
        k=np.array([[0,-axis[2],axis[1]],[axis[2],0,-axis[0]],[-axis[1],axis[0],0]])
        roll=np.eye(3)+np.sin(angle)*k+(1-np.cos(angle))*(k@k)
        goal=p.c.r.quaternion(p.c.r.orient(w[arm]).T@roll@fa)
        old=changes[(elbow,'rotation')]
        fore_local=p.c.sample(dict(path='rotation',interpolation='LINEAR',times=[0,1],values=[old,goal]),weight)
        changes[(elbow,'rotation')]=fore_local
        fore_world=p.c.r.orient(w[arm])@p.c.r.rotation(fore_local)
        old_hand_world=p.c.r.quaternion(p.c.r.orient(original_world[hand]))
        target_hand_world=p.c.r.quaternion(fore_world@p.c.r.rotation(base))
        hand_world=p.c.sample(dict(path='rotation',interpolation='LINEAR',times=[0,1],values=[old_hand_world,target_hand_world]),weight)
        changes[(hand,'rotation')]=p.c.r.quaternion(fore_world.T@p.c.r.rotation(hand_world))
        angles[side]=float(np.degrees(angle))
    return changes,angles

for channel in animation['channels']:
    node=channel['target']['node'];name=model.nodes[node].get('name','')
    if channel['target']['path']!='rotation' or (name not in ['LeftArm','LeftForeArm','LeftHand','RightArm','RightForeArm','RightHand'] and node not in fixed):continue
    sampler=animation['samplers'][channel['sampler']]
    times=model.data(sampler['input']).flatten()
    if node in fixed:
        values=[]
        for time,q in zip(times,model.data(sampler['output'])):
            u=min(1.,max(0.,min((float(time)-.30)/.25,(duration-.30-float(time))/.25)));weight=u*u*(3-2*u)
            values.append(p.c.sample(dict(path='rotation',interpolation='LINEAR',times=[0,1],values=[q,fixed[node]]),weight))
        values=np.asarray(values,dtype='<f4')
    else:values=np.asarray([wrist_pose(float(t))[0][(node,'rotation')] for t in times],dtype='<f4')
    for i in range(1,len(values)):
        if values[i-1]@values[i]<0:values[i]=-values[i]
    original=model.data(sampler['output'])
    for i,time in enumerate(times):
        if time<=.30 or time>=duration-.30:values[i]=original[i]
    assert np.max(np.abs(np.linalg.norm(values,axis=1)-1))<1e-5
    while len(binary)%4:binary.append(0)
    view=len(g['bufferViews']);g['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=values.nbytes));binary.extend(values.tobytes())
    accessor=len(g['accessors']);g['accessors'].append(dict(bufferView=view,componentType=5126,count=len(values),type='VEC4'))
    index=len(animation['samplers']);animation['samplers'].append(dict(input=sampler['input'],output=accessor,interpolation='LINEAR'));channel['sampler']=index

g['buffers'][0]['byteLength']=len(binary)
encoded=json.dumps(g,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4)
payload=struct.pack('<III',0x46546c67,2,28+len(encoded)+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
target=args.output;target.write_bytes(payload)
print('LOVE pose candidate generated; checking its surface path',flush=True)

# The pinned baseline itself has a brief release-hand penetration. Preserve
# its wrist orientation while rerouting only the affected hand path forward.
candidate=p.c.hands.Model(target);contact=p.c.ContactMesh(candidate)
candidate_tracks=candidate.tracks('SIGN_LOVE')
arm_nodes={candidate.names[s+x] for s in ['Left','Right'] for x in ['Arm','ForeArm','Hand']}
arm_times=next(t['times'] for t in candidate_tracks if t['node'] in arm_nodes and t['path']=='rotation')
worlds=[p.c.pose(candidate,candidate_tracks,float(t)) for t in arm_times]
vertices=[contact.skin(w) for w in worlds]
clearance={}
for side in ['Left','Right']:
    shifts=np.array([max(0,float(contact.depths(v,side)['hand'].max())+.004) for v in vertices])
    shifts[0]=shifts[-1]=0
    for _ in range(4):shifts[1:-1]=np.maximum(shifts[1:-1],(shifts[:-2]+2*shifts[1:-1]+shifts[2:])/4)
    clearance[side]=shifts
corrections={node:[] for node in arm_nodes}
for index,(time,w) in enumerate(zip(arm_times,worlds)):
    changes={}
    for side in ['Left','Right']:
        if clearance[side][index]>.00001:
            goal=w[candidate.names[side+'Hand']][:3,3].copy();goal[2]+=clearance[side][index]
            delta,_=p.c.solve_arm(candidate,w,side,goal,vertices[index][contact.torso_triangles],allow_entry_adjustment=True,mesh=contact)
            changes.update(delta)
    for node in arm_nodes:
        old=p.c.sample(next(t for t in candidate_tracks if t['node']==node and t['path']=='rotation'),float(time))
        corrections[node].append(changes.get((node,'rotation'),old))
    if index%100==0:print('Surface reroute frame',index,flush=True)
for channel in animation['channels']:
    node=channel['target']['node']
    if node not in arm_nodes or channel['target']['path']!='rotation':continue
    sampler=animation['samplers'][channel['sampler']]
    assert np.array_equal(model.data(sampler['input']).flatten(),np.array(arm_times))
    values=np.asarray(corrections[node],dtype='<f4')
    for i in range(1,len(values)):
        if values[i-1]@values[i]<0:values[i]=-values[i]
    old_channel=next(t for t in candidate_tracks if t['node']==node and t['path']=='rotation')
    values[0]=old_channel['values'][0];values[-1]=old_channel['values'][-1]
    while len(binary)%4:binary.append(0)
    view=len(g['bufferViews']);g['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=values.nbytes));binary.extend(values.tobytes())
    accessor=len(g['accessors']);g['accessors'].append(dict(bufferView=view,componentType=5126,count=len(values),type='VEC4'))
    index=len(animation['samplers']);animation['samplers'].append(dict(input=sampler['input'],output=accessor,interpolation='LINEAR'));channel['sampler']=index
g['buffers'][0]['byteLength']=len(binary)
encoded=json.dumps(g,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4)
payload=struct.pack('<III',0x46546c67,2,28+len(encoded)+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
target.write_bytes(payload)
after=p.c.hands.Model(target);mesh=p.c.ContactMesh(after)
allowed={s+part for s in ['Left','Right'] for part in ['Arm','ForeArm','Hand']}|{model.nodes[n]['name'] for n in fixed}
changed=set()
for old,new in zip(model.g['animations'],g['animations']):
    if old['name']!='SIGN_LOVE':assert old==new;continue
    for a,b in zip(old['channels'],new['channels']):
        assert a['target']==b['target']
        if a!=b:
            name=model.nodes[a['target']['node']]['name'];changed.add(name)
            assert name in allowed and a['target']['path']=='rotation'
            os,ns=old['samplers'][a['sampler']],new['samplers'][b['sampler']]
            assert os['input']==ns['input']
            times=model.data(os['input']).flatten()
            mask=(times<=.30)|(times>=duration-.30) if name not in {s+x for s in ['Left','Right'] for x in ['Arm','ForeArm','Hand']} else (times==times[0])|(times==times[-1])
            assert np.array_equal(model.data(os['output'])[mask],after.data(ns['output'])[mask])
assert changed==allowed
for key in ['nodes','skins','meshes','materials','textures','images','scenes']:assert model.g[key]==g[key]
assert model.binary[:model.g['buffers'][0]['byteLength']]==after.binary[:model.g['buffers'][0]['byteLength']]
report=dict(sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),sha256=hashlib.sha256(payload).hexdigest(),animationName='SIGN_LOVE',changedNodes=sorted(changed),unchangedActions=len(g['animations'])-1,qualifiedASLValidation=False,status='UNREVIEWED_REFERENCE_GUIDED_PREVIEW',reference='https://www.lifeprint.com/asl101/pages-signs/l/love.htm',preservedFingerEntryReleaseSeconds=.30,transitionSeconds=.25,fingerFlexionDegrees=[80,95,50],maximumAdditionalClearanceMeters={s:float(v.max()) for s,v in clearance.items()},samples=[])
max_position_error=0.;max_depth=0.;max_forearm_depth=0.
candidate_final_tracks=after.tracks('SIGN_LOVE')
for time in np.linspace(0,duration,641):
    before_world=p.c.pose(model,tracks,float(time));after_world=p.c.pose(after,candidate_final_tracks,float(time));vertices=mesh.skin(after_world)
    for side in ['Left','Right']:
        node=model.names[side+'Hand'];max_position_error=max(max_position_error,float(np.max(np.abs(before_world[node][:3,3]-after_world[node][:3,3]))))
        max_depth=max(max_depth,float(max(0,mesh.depths(vertices,side)['hand'].max())))
        max_forearm_depth=max(max_forearm_depth,float(max(0,mesh.depths(vertices,side)['forearm'].max())))
report.update(maxWristDisplacementMeters=max_position_error,maxFrontTorsoHandDepthMeters=max_depth,maxFrontTorsoForearmDepthMeters=max_forearm_depth,heldForearmRollDegrees=wrist_pose(duration*.4)[1],surfaceSamples=641,limitations='Front-surface torso proxy only; not full mesh or arm-arm collision. Low-poly mesh and thumb articulation remain. Requires Android visual testing and qualified ASL review.')
image=Image.new('RGB',(880,540),'#eef2f2');draw=ImageDraw.Draw(image)
for row,side in enumerate(['Left','Right']):
    for column,m in enumerate([model,after]):
        w=p.c.pose(m,m.tracks('SIGN_LOVE'),duration*.4)
        for view,axes in enumerate([(0,1),(2,1)]):
            cell=(220*(column*2+view),270*row);metrics=p.c.hands.render(draw,m,w,side,cell,axes=axes,bones=True)
            draw.text((cell[0]+3,cell[1]+3),('BEFORE ' if column==0 else 'PROTOTYPE ')+side,fill='black')
            if view==0:report['samples'].append(dict(side=side,version='before' if column==0 else 'prototype',metrics=metrics))
image.save(args.report.with_suffix('.png'))
report['surfaceGatePassed']=max_depth<.002 and max_forearm_depth<.010
args.report.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
assert report['surfaceGatePassed'], 'Candidate fails torso surface gate; do not apply'
