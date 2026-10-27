"""Reproduce only the reviewed ARRIVE hand/contact candidate.

Requires the pinned pre-update bundle and previously staged official ASL motion.
Writes candidate NPZ/JSON files only. The caller must repeat mesh/native review
before packaging; this is not a generic correction for other ASL contact signs.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse, hashlib, importlib.util, json
from typing import Any
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser(description='Stage the named ARRIVE reference-guided hand/contact repair; never modify the running app')
parser.add_argument('--baseline',type=Path,required=True)
parser.add_argument('--source-dir',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if args.output.resolve()==args.source_dir.resolve():parser.error("Use a separate staging output")
if any((args.output/name).exists() for name in ["arrive.npz","arrive.json","report.json"]):parser.error("Candidate output already exists; do not overwrite it")
root=Path(__file__).resolve().parents[2];out=args.output;out.mkdir(parents=True,exist_ok=True)
def mod(name: str,p: Path) -> Any:
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
c=mod('contact',root/'android/tools/correct-text-to-sign-love.py');ik=mod('arm',root/'android/tools/correct-imported-shoulder-baselines.py');R=c.r
asset=args.baseline
assert hashlib.sha256(asset.read_bytes()).hexdigest()=='803b7bfe2638ae0faf258e45274f921ef2eb9849b28ca8ff1b31e1195beb1185'
m=c.hands.Model(asset);mesh=c.ContactMesh(m)
handtris={s:mesh.triangles[np.all(mesh.hand[s][mesh.triangles],axis=1)] for s in ['Left','Right']}
# Full boundary triangles prevent a missing surface from appearing collision-free.
handtris_all={s:mesh.triangles[np.any(mesh.hand[s][mesh.triangles],axis=1)] for s in ['Left','Right']}
handpoints={s:np.flatnonzero(mesh.hand[s])[::2] for s in ['Left','Right']}
records=[]
for word in ['arrive']:
 meta=json.loads((args.source_dir/(word+'.json')).read_text())
 assert meta['sourceSha256']=="d2f7f169a68b528cb4aed324039609442f381adcc42d6b294a8d1f30ce14d81a", 'Unexpected original ARRIVE source'
 assert meta['motionSha256']=="11163ee9a04a13af6c7e4ffe40102a992c74b4fcb8f622cc783fa48275323d76", 'Unexpected staged ARRIVE motion'
 with np.load(args.source_dir/(word+'.npz')) as data:times=data['times'].copy();original=data['rotations'].copy()
 assert hashlib.sha256(original.astype('<f4').tobytes()).hexdigest()==meta['motionSha256']
 values=original.copy(); order_index={node:j for j,node in enumerate(m.order)}
 # Transfer the existing B finger pose through anatomical rest frames; preserve source thumbs.
 rest=R.world(m.nodes,m.parents,m.order)
 donor_tracks=m.tracks('SIGN_LETTER_B_WOLF3D_PREVIEW');donor_time=max(t['times'][-1] for t in donor_tracks)*.5
 donor={(t['node'],t['path']):c.sample(t,donor_time) for t in donor_tracks if t['path']=='rotation' and m.nodes[t['node']].get('name','').startswith('RightHand') and m.nodes[t['node']].get('name')!='RightHand'}
 donor_world=R.world(m.nodes,m.parents,m.order,donor)
 def hand_frame(side: str) -> np.ndarray:
  forward=rest[m.names[side+'HandMiddle1']][:3,3]-rest[m.names[side+'Hand']][:3,3]
  across=rest[m.names[side+'HandIndex1']][:3,3]-rest[m.names[side+'HandPinky1']][:3,3]
  x=R.unit(across);y=R.unit(forward-x*(forward@x));return np.column_stack([x,y,R.unit(np.cross(x,y))])
 mirror=hand_frame('Left')@np.diag([1,1,-1])@hand_frame('Right').T
 desired_left={}
 for finger in ['Index','Middle','Ring','Pinky']:
  for joint in range(1,4):
   rn=m.names['RightHand'+finger+str(joint)];ln=m.names['LeftHand'+finger+str(joint)]
   delta=R.orient(donor_world[rn])@R.orient(rest[rn]).T
   desired_left[ln]=mirror@delta@mirror.T@R.orient(rest[ln])
   values[1:-1,order_index[rn]]=donor[(rn,'rotation')]
 for node in m.order:
  if node not in desired_left:continue
  parent_rotation=desired_left.get(m.parents[node],R.orient(rest[m.parents[node]]))
  values[1:-1,order_index[node]]=R.quaternion(parent_rotation.T@desired_left[node])
 poses=[{(node,'rotation'):values[k,j] for j,node in enumerate(m.order)} for k in range(len(times))]
 worlds=[R.world(m.nodes,m.parents,m.order,p) for p in poses]
 vv=[mesh.skin(w) for w in worlds]
 normals=[];centers=[]
 for w in worlds:
  a=w[m.names['LeftHandIndex1']][:3,3]-w[m.names['LeftHandPinky1']][:3,3]
  b=w[m.names['LeftHandMiddle1']][:3,3]-w[m.names['LeftHand']][:3,3]
  x=R.unit(a);y=R.unit(b-x*(b@x));z=R.unit(np.cross(x,y));normals.append(np.column_stack([x,y,z]))
  centers.append(w[m.names['RightHand']][:3,3]-w[m.names['LeftHand']][:3,3])
 # Establish the approach side from the first hands-raised frame before contact.
 active=[i for i,w in enumerate(worlds[1:-1],1) if min(w[m.names[s+'Hand']][1,3] for s in ['Left','Right'])>w[m.names['Hips']][1,3]+.2 and np.linalg.norm(centers[i])<.35]
 assert active,'No interpretable two-hand approach'
 approach=active[0]; sign=1 if centers[approach]@normals[approach][:,2]>=0 else -1
 shifts=[]
 for k,(w,v,basis) in enumerate(zip(worlds,vv,normals)):
  if k in [0,len(times)-1] or np.linalg.norm(centers[k])>.35:shifts.append(0.);continue
  b=basis.copy();b[:,2]*=sign
  right=v[handpoints['Right']]@b;left=v[handtris_all['Left']]@b
  surface=c.front_surface(right,left)
  back_points=right.copy();back_points[:,2]*=-1;back_tri=left.copy();back_tri[:,:,2]*=-1
  back=-c.front_surface(back_points,back_tri)
  # A point behind a disjoint hand is not a penetration. Require a closed-surface witness.
  inside=np.isfinite(surface)&np.isfinite(back)&(surface-right[:,2]>.0005)&(right[:,2]-back>.0005)
  left_points=v[handpoints['Left']]@b;right_tris=v[handtris_all['Right']]@b
  rf=c.front_surface(left_points,right_tris);lp=left_points.copy();lp[:,2]*=-1;rt=right_tris.copy();rt[:,:,2]*=-1
  rb=-c.front_surface(lp,rt)
  inside_other=np.isfinite(rf)&np.isfinite(rb)&(rf-left_points[:,2]>.0005)&(left_points[:,2]-rb>.0005)
  gap=surface-right[:,2];finite=np.isfinite(gap)
  correction=max(0.,float(gap[finite].max(initial=-np.inf))+.001) if inside.any() or inside_other.any() else 0.
  if correction>.05:raise ValueError((word,'Hand contact needs >5cm adjustment; review before enabling',k,float(times[k]),correction))
  shifts.append(correction)
 shifts=np.asarray(shifts)
 # Smooth a clearance envelope, keeping it no lower than the measured surface.
 for _ in range(5):shifts[1:-1]=np.maximum(shifts[1:-1],(shifts[:-2]+2*shifts[1:-1]+shifts[2:])/4)
 max_rotation_error=0.;max_wrist_error=0.
 for k in range(1,len(times)-1):
  if shifts[k]<1e-8:continue
  old=worlds[k];side='Right';arm,fore,hand=[m.names[side+n] for n in ['Arm','ForeArm','Hand']]
  start=old[arm][:3,3];target=old[hand][:3,3]+normals[k][:,2]*sign*shifts[k]
  l1=np.linalg.norm(old[fore][:3,3]-start);l2=np.linalg.norm(old[hand][:3,3]-old[fore][:3,3])
  elbow=ik.elbow_position(start,target,old[fore][:3,3],l1,l2)
  wr=ik.swing(old[fore][:3,3]-start,elbow-start)@R.orient(old[arm])
  fr=ik.swing(old[hand][:3,3]-old[fore][:3,3],target-elbow)@R.orient(old[fore])
  for n,rot in [(arm,R.orient(old[m.parents[arm]]).T@wr),(fore,wr.T@fr),(hand,fr.T@R.orient(old[hand]))]:
   values[k,order_index[n]]=R.quaternion(rot);poses[k][(n,'rotation')]=values[k,order_index[n]]
  new=R.world(m.nodes,m.parents,m.order,poses[k]);max_wrist_error=max(max_wrist_error,float(np.linalg.norm(new[hand][:3,3]-target)))
  for name,node in m.names.items():
   if name and name.startswith('RightHand'):
    max_rotation_error=max(max_rotation_error,float(np.max(abs(R.orient(old[node])-R.orient(new[node])))))
 assert max_rotation_error<1e-5 and max_wrist_error<1e-5
 for j in range(values.shape[1]):
  for k in range(1,len(values)):
   if values[k-1,j]@values[k,j]<0:values[k,j]*=-1
 steps=np.degrees(2*np.arccos(np.clip(abs(np.sum(values[2:-1]*values[1:-2],axis=2)),0,1)))
 assert float(steps.max())<90,('Abrupt corrected rotation',float(steps.max()))
 meta.update(motionSha256=hashlib.sha256(values.astype('<f4').tobytes()).hexdigest(),technicalPlaybackStatus='Staged correction; mesh/native review pending',handCorrection=dict(method='Named flat-hand profile plus one-sided palm-contact clearance and fixed-wrist-orientation arm IK',sourceMotionSha256=hashlib.sha256(original.astype('<f4').tobytes()).hexdigest(),sourceThumbsPreserved=True,fingerPoseDonorAction='SIGN_LETTER_B_WOLF3D_PREVIEW',leftPoseTransfer='Anatomical rest-frame reflection, not Euler sign changes',maxWristShiftMm=float(shifts.max()*1000),maximumHandOrientationMatrixError=max_rotation_error,maximumWristPositionErrorMeters=max_wrist_error,reference='https://www.lifeprint.com/asl101/pages-signs/a/arrive.htm',validation='UNREVIEWED; correction is not proof of ASL accuracy'))
 np.savez_compressed(out/(word+'.npz'),times=times,rotations=values)
 (out/(word+'.json')).write_text(json.dumps(meta,indent=2));records.append(meta)
 print(word,'STAGED','wrist shift mm',round(float(shifts.max()*1000),2),flush=True)
(out/'report.json').write_text(json.dumps(dict(added=len(records),entries=records,baselineSha256='803b7bfe2638ae0faf258e45274f921ef2eb9849b28ca8ff1b31e1195beb1185',sourceArchiveSha256='6ee2bd5b7ead8f601d2d77345cc6fcfe0b9a323970ca6a9ec316c408298336eb',status='STAGED_ONLY_NOT_ENABLED'),indent=2))
