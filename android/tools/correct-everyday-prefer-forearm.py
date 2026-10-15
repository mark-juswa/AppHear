"""Candidate-only chin calibration/mesh solve; preserves PREFER's finger shape."""
import copy,hashlib,importlib.util,json,struct,sys
from pathlib import Path
import numpy as np
s=importlib.util.spec_from_file_location('c',Path(__file__).with_name('correct-text-to-sign-love.py'))
c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
source,output,report=map(Path,sys.argv[1:4])
assert source.resolve()!=output.resolve()
raw=source.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='53d72bd7d1598d35883aca6b22858c78ac6c40dd0349ca54d515623178984cdc'
m=c.hands.Model(source);mesh=c.ContactMesh(m)
name='SIGN_PREFER_HUMAN_RETARGETED_PREVIEW';tracks=m.tracks(name)
neutral=c.pose(m,m.tracks('SIGN_RELAXED_NEUTRAL'),0)
torso=mesh.skin(neutral)[mesh.torso_triangles]
hand=m.names['RightHand'];allowed={m.names['Right'+p] for p in ['Arm','ForeArm','Hand']}
times=next(t['times'] for t in tracks if t['node']==hand)
frames=[];max_position=0.;max_rotation=0.
duration=max(times)
chin_shift=np.array([0.,1.51-1.475,float(c.front_surface(np.array([[0.,1.51,0.]]),torso)[0]-
                                         c.front_surface(np.array([[0.,1.475,0.]]),torso)[0])])
for time in times:
 world=c.pose(m,tracks,time)
 phase=np.clip((time-.35)/(duration-.70),0,1)
 envelope=np.clip(min(phase/.12,(1-phase)/.12),0,1);envelope=envelope*envelope*(3-2*envelope)
 shift=chin_shift*envelope
 changes,_=c.solve_arm(m,world,'Right',world[hand][:3,3]+shift,torso,allow_entry_adjustment=True,mesh=mesh)
 updated=c.pose(m,tracks,time,changes)
 for i in m.order:
  if m.nodes[i].get('name','').startswith('RightHand'):
   max_position=max(max_position,float(np.linalg.norm(updated[i][:3,3]-world[i][:3,3]-shift)))
   max_rotation=max(max_rotation,float(np.max(np.abs(c.r.orient(updated[i])-c.r.orient(world[i])))))
 assert max_position<1e-5 and max_rotation<1e-5, 'Keep the finger shape while moving the contact to the actual chin'
 frames.append(changes)
g=copy.deepcopy(m.g);binary=bytearray(m.binary[:g['buffers'][0]['byteLength']])
action=next(a for a in g['animations'] if a['name']==name)
for channel in action['channels']:
 node=channel['target']['node']
 if node not in allowed or channel['target']['path']!='rotation':continue
 sampler=action['samplers'][channel['sampler']]
 values=[f[(node,'rotation')] for f in frames]
 for j in range(1,len(values)):
  if np.dot(values[j-1],values[j])<0:values[j]=(-np.asarray(values[j])).tolist()
 values=np.asarray(values,dtype='<f4')
 assert np.isfinite(values).all() and np.max(np.abs(np.linalg.norm(values,axis=1)-1))<1e-5
 while len(binary)%4:binary.append(0)
 view=len(g['bufferViews']);g['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=values.nbytes));binary.extend(values.tobytes())
 index=len(g['accessors']);g['accessors'].append(dict(bufferView=view,componentType=5126,count=len(values),type='VEC4'));sampler['output']=index
assert [a for a in g['animations'] if a['name']!=name]==[a for a in m.g['animations'] if a['name']!=name]
g['buffers'][0]['byteLength']=len(binary);encoded=json.dumps(g,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4)
payload=struct.pack('<III',0x46546c67,2,28+len(encoded)+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
output.write_bytes(payload);sha=hashlib.sha256(payload).hexdigest()
metadata=json.loads(source.with_suffix('.json').read_text());metadata['sha256']=sha
record=dict(sourceSha256=hashlib.sha256(raw).hexdigest(),animationName=name,changedNodes=['RightArm','RightForeArm','RightHand'],
            calibratedChinHeightMeters=1.51,contactShiftMeters=chin_shift.tolist(),
            maxFingerRelativePositionErrorMeters=max_position,maxWorldHandRotationMatrixChange=max_rotation,
            otherActionsPreserved=241,fingerChannelsUnchanged=True,qualifiedAslValidation=False)
metadata['everydayExpansion']['preferForearmRefinement']=record
output.with_suffix('.json').write_text(json.dumps(metadata,indent=2)+'\n');report.write_text(json.dumps(dict(bundleSha256=sha,**record),indent=2)+'\n')
print(json.dumps(dict(bundleSha256=sha,**record)))
