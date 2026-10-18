"""Offline LOVE-only torso-contact correction on the existing human.

No new gesture, handshape, runtime physics or Android dependency. The source
crossed-arm path and finger tracks remain; only arm/forearm/wrist rotations
are corrected against the avatar's actual weighted torso surface. Development
NumPy/Pillow are required by the shared mesh inspection helpers.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import numpy as np

spec=importlib.util.spec_from_file_location('hands',Path(__file__).with_name('audit-text-to-sign-hands.py'))
hands=importlib.util.module_from_spec(spec);spec.loader.exec_module(hands)
r=hands.r

def sample(channel,time):
    # glTF rotation LINEAR means shortest-path spherical interpolation.
    if channel['path']!='rotation' or channel['interpolation']=='STEP':return r.sample(channel,time)
    times=channel['times'];i=max(0,min(len(times)-1,np.searchsorted(times,time,side='right')-1))
    a=np.array(channel['values'][i],dtype=float);a/=np.linalg.norm(a)
    if i==len(times)-1:return a
    b=np.array(channel['values'][i+1],dtype=float);b/=np.linalg.norm(b)
    if np.dot(a,b)<0:b=-b
    t=max(0,(time-times[i])/(times[i+1]-times[i]));dot=np.clip(np.dot(a,b),-1,1)
    if dot>.9995:return r.unit(a*(1-t)+b*t)
    angle=np.arccos(dot)
    return r.unit((np.sin((1-t)*angle)*a+np.sin(t*angle)*b)/np.sin(angle))

def pose(model,tracks,time,overrides=None):
    values={(c['node'],c['path']):sample(c,time) for c in tracks}
    values.update(overrides or {})
    return r.world(model.nodes,model.parents,model.order,values)

def between(x,y):
    x=r.unit(x);y=r.unit(y);cross=np.cross(x,y);dot=np.clip(np.dot(x,y),-1,1)
    if dot>1-1e-10:return np.eye(3)
    if dot<-1+1e-8:
        axis=r.unit(np.cross(x,[1,0,0] if abs(x[0])<.9 else [0,1,0]))
        return 2*np.outer(axis,axis)-np.eye(3)
    k=np.array([[0,-cross[2],cross[1]],[cross[2],0,-cross[0]],[-cross[1],cross[0],0]])
    return np.eye(3)+k+k@k/(1+dot)

def front_surface(points,triangles):
    """Front z of actual torso triangles at each point's x/y; no hit is -inf.

    This is a front-contact constraint for LOVE, not a closed-body signed-distance
    field or a general collision system. Back contact signs must not use it.
    """
    if len(points)>96:
        return np.concatenate([front_surface(points[i:i+96],triangles) for i in range(0,len(points),96)])
    low=points[:,:2].min(0);high=points[:,:2].max(0)
    triangles=triangles[np.all(triangles[:,:,:2].max(1)>=low-1e-5,axis=1)&np.all(triangles[:,:,:2].min(1)<=high+1e-5,axis=1)]
    if not len(triangles):return np.full(len(points),-np.inf)
    p=points[:,None,:2];v=triangles[None,:,:,:2]
    aa=v[:,:,0];b=v[:,:,1]-aa;c=v[:,:,2]-aa;d=p-aa
    denominator=b[:,:,0]*c[:,:,1]-b[:,:,1]*c[:,:,0]
    valid=np.abs(denominator)>1e-10;denominator=np.where(valid,denominator,1)
    u=(d[:,:,0]*c[:,:,1]-d[:,:,1]*c[:,:,0])/denominator
    v=(b[:,:,0]*d[:,:,1]-b[:,:,1]*d[:,:,0])/denominator
    hit=valid&(u>=-1e-5)&(v>=-1e-5)&(u+v<=1+1e-5)
    z=triangles[None,:,0,2]+u*(triangles[None,:,1,2]-triangles[None,:,0,2])+v*(triangles[None,:,2,2]-triangles[None,:,0,2])
    return np.max(np.where(hit,z,-np.inf),axis=1)

class ContactMesh:
    def __init__(self,model):
        self.model=model
        assert len(model.meshes)==1, 'Audit a changed mesh structure before use'
        self.pos,self.weights,self.joints,self.triangles,self.jids,self.ibm=model.meshes[0]
        def mask(names):
            indices=[k for k,j in enumerate(self.jids) if model.nodes[j].get('name') in names]
            return np.sum(self.weights*np.isin(self.joints,indices),axis=1)>.65
        # Include blended collar/shoulder triangles: a strict >65% spine-only
        # mask leaves holes where an elbow can incorrectly appear collision-free.
        torso_ids=[k for k,j in enumerate(self.jids) if model.nodes[j].get('name') in
                   ['Hips','Spine','Spine1','Spine2','Neck','Head','LeftShoulder','RightShoulder']]
        torso_weight=np.sum(self.weights*np.isin(self.joints,torso_ids),axis=1)
        region=(np.abs(self.pos[:,0])<.21)&(self.pos[:,1]>.85)
        self.torso_triangles=self.triangles[(torso_weight[self.triangles].mean(1)>.50)&np.all(region[self.triangles],axis=1)]
        self.hand={side:mask([n for n in model.names if n and side+'Hand' in n]) for side in ['Right','Left']}
        self.forearm={side:mask([side+'ForeArm']) for side in ['Right','Left']}
        self.forearm_local={side:[np.einsum('nij,nj->ni',self.ibm[self.joints[self.forearm[side],i]],self.pos[self.forearm[side]]) for i in range(4)] for side in ['Right','Left']}
    def skin(self,world):
        matrices=np.array([world[j]@self.ibm[k] for k,j in enumerate(self.jids)])
        return sum(np.einsum('nij,nj->ni',matrices[self.joints[:,i]],self.pos)*self.weights[:,i,None] for i in range(4))[:,:3]
    def depths(self,vertices,side):
        surface=vertices[self.torso_triangles]
        return {part:front_surface(vertices[mask[side]],surface)-vertices[mask[side],2]
                for part,mask in [('hand',self.hand),('forearm',self.forearm)]}
    def candidate_forearm(self,world,side,desired,positions):
        mask=self.forearm[side];out=np.zeros((int(mask.sum()),3))
        for slot in range(4):
            local=self.forearm_local[side][slot]
            indices=self.joints[mask,slot]
            for joint_index in np.unique(indices):
                node=self.jids[joint_index];selected=indices==joint_index
                rotation=desired.get(node,world[node][:3,:3]);translation=positions.get(node,world[node][:3,3])
                out[selected]+=(local[selected,:3]@rotation.T+translation)*self.weights[mask,slot][selected,None]
        return out

def solve_arm(model,world,side,target,torso,previous_elbow=None,allow_entry_adjustment=False,mesh=None):
    arm,elbow,hand=[model.names[side+x] for x in ['Arm','ForeArm','Hand']]
    shoulder,old_elbow,old_hand=[world[j][:3,3] for j in [arm,elbow,hand]]
    l1=np.linalg.norm(old_elbow-shoulder);l2=np.linalg.norm(old_hand-old_elbow)
    distance=np.linalg.norm(target-shoulder);axis=r.unit(target-shoulder)
    if l1+l2-distance<.0001 and np.linalg.norm(target-old_hand)<1e-8:
        # A fully extended neutral arm has no useful elbow-circle radius.
        return {(n,'rotation'):r.quaternion(r.orient(world[model.parents[n]]).T@r.orient(world[n])).tolist()
                for n in [arm,elbow,hand]},old_elbow
    if distance>l1+l2:
        # The short lifting/lowering transition can need millimetres of inward
        # XY movement. Keep the contact z and retract XY, never stretch bones.
        assert allow_entry_adjustment or distance-l1-l2<.0001, 'Held crossing target is unreachable'
        reach=l1+l2-.00001
        xy=target[:2]-shoulder[:2]
        safe_xy=np.sqrt(max(0,reach*reach-(target[2]-shoulder[2])**2))
        new_xy=shoulder[:2]+r.unit(xy)*safe_xy
        assert np.linalg.norm(new_xy-target[:2])<.010, 'Entry correction exceeds 1 cm; review it'
        target=target.copy();target[:2]=new_xy
        distance=np.linalg.norm(target-shoulder);axis=r.unit(target-shoulder)
    along=(l1*l1-l2*l2+distance*distance)/(2*distance)
    radius=np.sqrt(max(0,l1*l1-along*along));center=shoulder+axis*along
    pole=r.unit(old_elbow-shoulder-axis*np.dot(old_elbow-shoulder,axis))
    tangent=r.unit(np.cross(axis,pole))
    angles=np.linspace(-np.pi,np.pi,145)
    candidates=center+radius*(np.cos(angles)[:,None]*pole+np.sin(angles)[:,None]*tangent)
    segments=np.array([[c*(1-u)+target*u for u in np.linspace(0,1,9)] for c in candidates])
    surface=front_surface(segments.reshape((-1,3)),torso).reshape((-1,9))
    # Forearm center clearance, scoped to LOVE. Actual mesh verification below
    # checks the result; this is not applied to other signs or to hand contacts.
    penetration=np.maximum(0,surface+.055-segments[:,:,2])
    scores=np.sum((candidates-old_elbow)**2,axis=1)+np.max(penetration,axis=1)**2*1000
    if previous_elbow is not None:scores+=.35*np.sum((candidates-previous_elbow)**2,axis=1)
    def orientations(candidate):
        return {arm:between(old_elbow-shoulder,candidate-shoulder)@r.orient(world[arm]),
                elbow:between(old_hand-old_elbow,target-candidate)@r.orient(world[elbow]),hand:r.orient(world[hand])}
    new_elbow=candidates[int(np.argmin(scores))];desired=orientations(new_elbow)
    if mesh is not None:
        best_depth=np.inf
        for candidate in candidates[np.argsort(scores)]:
            trial=orientations(candidate)
            points=mesh.candidate_forearm(world,side,trial,{arm:shoulder,elbow:candidate,hand:target})
            depth=float(max(0,(front_surface(points,torso)-points[:,2]).max()))
            if depth<best_depth:best_depth=depth;new_elbow=candidate;desired=trial
            if depth<.002:break
    overrides={}
    for node in [arm,elbow,hand]:
        parent=model.parents[node]
        parent_rotation=desired.get(parent,r.orient(world[parent]))
        overrides[(node,'rotation')]=r.quaternion(parent_rotation.T@desired[node]).tolist()
    return overrides,new_elbow

def main():
    android=Path(__file__).resolve().parents[1]
    target=Path(sys.argv[1]) if len(sys.argv)>1 else android/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb'
    manifest_path=target.with_suffix('.json');manifest=json.loads(manifest_path.read_text())
    original=target.read_bytes();source_hash=hashlib.sha256(original).hexdigest()
    assert source_hash==manifest['sha256'], 'Input bundle integrity mismatch'
    if manifest.get('loveCorrection'):
        print('LOVE correction already applied; no file changes');return
    assert source_hash=='54b4e4882ff8d1d3d104f9835b74fce7d5ac6db67a5ef73835e83196a3816c86', 'Review a new baseline before correcting it'
    model=hands.Model(target);mesh=ContactMesh(model);tracks=model.tracks('SIGN_LOVE')
    duration=max(max(c['times']) for c in tracks)
    # Correct only six rotation tracks at 240 Hz. Oversampling protects the
    # contact path between keys, where composed joint SLERPs can bend inward.
    # Float32 timestamps stay strictly
    # increasing; unioning near-identical source/regular times produced duplicates.
    times=np.linspace(0,duration,521,dtype=np.float32).astype(float).tolist()
    worlds=[pose(model,tracks,t) for t in times]
    source_vertices=[mesh.skin(w) for w in worlds]
    entry_end=.30;exit_start=duration-.30
    corrected_nodes=[model.names[side+x] for side in ['Right','Left'] for x in ['Arm','ForeArm','Hand']]
    hand_z={};max_before={'hand':0.,'forearm':0.}
    for side in ['Right','Left']:
        positions=[];reach_limits=[]
        for index,world in enumerate(worlds):
            vertices=source_vertices[index];depths=mesh.depths(vertices,side)
            for part,values in depths.items():max_before[part]=max(max_before[part],float(max(0,values.max())))
            shift=max(0,float(depths['hand'].max())+.008)
            positions.append(world[model.names[side+'Hand']][2,3]+shift)
            shoulder,elbow,wrist=[world[model.names[side+part]][:3,3] for part in ['Arm','ForeArm','Hand']]
            reach=np.linalg.norm(elbow-shoulder)+np.linalg.norm(wrist-elbow)-.00001
            reach_limits.append(shoulder[2]+np.sqrt(max(0,reach*reach-np.sum((wrist[:2]-shoulder[:2])**2))))
        # Smooth the clearance envelope without dropping below the required
        # front contact height; first/last neutral frames remain the source.
        minimum=np.array(positions);limits=np.array(reach_limits)
        limits=np.maximum(minimum,limits)
        smooth=minimum.copy()
        for _ in range(5):
            smooth[1:-1]=np.minimum(limits[1:-1],np.maximum(minimum[1:-1],(smooth[:-2]+2*smooth[1:-1]+smooth[2:])/4))
        hand_z[side]=smooth
    goals={side:np.array([w[model.names[side+'Hand']][:3,3] for w in worlds]) for side in ['Right','Left']}
    for side in goals:
        goals[side][:,2]=hand_z[side]
        def bezier(p0,p1,p2,p3,t):return (1-t)**3*p0+3*(1-t)**2*t*p1+3*(1-t)*t*t*p2+t**3*p3
        start=goals[side][0].copy();entry=goals[side][np.searchsorted(times,entry_end)].copy()
        end=goals[side][-1].copy();exit=goals[side][np.searchsorted(times,exit_start)].copy()
        # Lift forward before crossing; lower after uncrossing. Reroute only
        # approach/release, not the held LOVE contact or finger articulation.
        flight_z=max(entry[2],exit[2],.22)+.025
        for i,time in enumerate(times):
            if time<entry_end:
                p1=np.array([start[0],start[1]+.18,flight_z]);p2=np.array([entry[0],entry[1]-.10,flight_z])
                goals[side][i]=bezier(start,p1,p2,entry,time/entry_end)
            elif time>exit_start:
                p1=np.array([exit[0],exit[1]-.10,flight_z]);p2=np.array([end[0],end[1]+.18,flight_z])
                goals[side][i]=bezier(exit,p1,p2,end,(time-exit_start)/(duration-exit_start))
            if i not in [0,len(times)-1]:
                # A rerouted XY path meets a different part of the torso.
                # Recheck its actual hand surface before solving the arm.
                vertices=source_vertices[i]
                points=vertices[mesh.hand[side]]+goals[side][i]-worlds[i][model.names[side+'Hand']][:3,3]
                depth=front_surface(points,vertices[mesh.torso_triangles])-points[:,2]
                goals[side][i][2]+=max(0,float(depth.max())+.008)
    rotations={node:[] for node in corrected_nodes};previous={};max_after={'hand':0.,'forearm':0.}
    max_xy_error=0.;max_orientation_error=0.;contact_gaps=[];worst=[]
    for index,(time,world) in enumerate(zip(times,worlds)):
        vertices=source_vertices[index];torso=vertices[mesh.torso_triangles];overrides={}
        for side in ['Right','Left']:
            goal=goals[side][index].copy()
            if index in [0,len(times)-1]:
                # Preserve source entry/exit rotations exactly; no collision at rest.
                changes={(n,'rotation'):sample(next(c for c in tracks if c['node']==n and c['path']=='rotation'),time)
                         for n in corrected_nodes if model.nodes[n]['name'].startswith(side)}
            else:
                changes,previous[side]=solve_arm(model,world,side,goal,torso,previous.get(side),time<entry_end or time>exit_start,mesh)
            overrides.update(changes)
        corrected=pose(model,tracks,time,overrides);new_vertices=mesh.skin(corrected)
        for node in corrected_nodes:
            q=np.array(overrides[(node,'rotation')])
            if rotations[node] and np.dot(q,rotations[node][-1])<0:q=-q
            rotations[node].append(q.tolist())
        for side in ['Right','Left']:
            hand=model.names[side+'Hand']
            max_xy_error=max(max_xy_error,float(np.max(np.abs(world[hand][:2,3]-corrected[hand][:2,3]))))
            if entry_end<=time<=exit_start:
                assert np.max(np.abs(world[hand][:2,3]-corrected[hand][:2,3]))<.0001, 'Crossed-arm XY path changed'
            max_orientation_error=max(max_orientation_error,float(np.max(np.abs(r.orient(world[hand])-r.orient(corrected[hand])))))
            for part,values in mesh.depths(new_vertices,side).items():
                if values.max()>max_after[part]:worst.append((round(time,5),side,part,float(values.max())))
                max_after[part]=max(max_after[part],float(max(0,values.max())))
                if part=='hand' and .25<time<1.95 and np.isfinite(values).any():contact_gaps.append(float(-values[np.isfinite(values)].max()))
    assert max_orientation_error<1e-6
    assert max_after['hand']<.002, f'Hand surface check failed: {max_after}; {worst}; do not package'
    assert max_after['forearm']<.010, f'Forearm surface check failed: {max_after}; {worst}; do not package'
    document=copy.deepcopy(model.g);binary=bytearray(model.binary[:document['buffers'][0]['byteLength']])
    def accessor(values,kind):
        values=np.asarray(values,dtype='<f4');data=values.tobytes()
        while len(binary)%4:binary.append(0)
        view=len(document['bufferViews']);document['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=len(data)));binary.extend(data)
        result=len(document['accessors']);entry=dict(bufferView=view,componentType=5126,count=len(values),type=kind)
        if kind=='SCALAR':entry.update(min=[float(values.min())],max=[float(values.max())])
        document['accessors'].append(entry);return result
    animation=next(a for a in document['animations'] if a['name']=='SIGN_LOVE')
    input_index=accessor(times,'SCALAR')
    for channel in animation['channels']:
        node=channel['target']['node']
        if node in rotations and channel['target']['path']=='rotation':
            sampler=len(animation['samplers']);animation['samplers'].append(dict(input=input_index,output=accessor(rotations[node],'VEC4'),interpolation='LINEAR'))
            channel['sampler']=sampler
    document['buffers'][0]['byteLength']=len(binary)
    encoded=json.dumps(document,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4)
    payload=struct.pack('<III',0x46546c67,2,12+8+len(encoded)+8+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    audit=dict(animationName='SIGN_LOVE',status='UNREVIEWED_CONTACT_CORRECTION',sourceBundleSha256=source_hash,
        correctedNodes=[model.nodes[n]['name'] for n in corrected_nodes],samples=len(times),durationSeconds=duration,
        approachReleaseSeconds=.30,crossingXYHeldBetweenSeconds=[entry_end,exit_start],
        reference='https://www.lifeprint.com/asl101/pages-signs/l/love.htm',
        method='LOVE-only actual torso front surface and two-bone arm IK; unchanged finger tracks and wrist world orientation',
        beforeDepthMeters=max_before,afterDepthMeters=max_after,wristXYErrorMeters=max_xy_error,wristOrientationMatrixError=max_orientation_error,
        nearestHandSurfaceGapRangeMeters=[min(contact_gaps),max(contact_gaps)],
        limitations='Front-surface proxy, not all-mesh closed-volume or arm-arm collision; requires device and qualified ASL review')
    manifest['sha256']=hashlib.sha256(payload).hexdigest();manifest['loveCorrection']=audit
    target.write_bytes(payload);manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(sha256=manifest['sha256'],bytes=len(payload),audit=audit),indent=2))

if __name__=='__main__':main()
