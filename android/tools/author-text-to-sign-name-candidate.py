"""Author a quarantined two-H-hand/double-contact NAME review candidate.

This tool never registers NAME, changes the production bundle or enables playback.
Its output needs mesh/contact inspection, device rendering and qualified ASL review.
Reference facts: https://www.lifeprint.com/asl101/pages-signs/n/name.htm
No Lifeprint media or external SiGML data is copied into the output.
"""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import numpy as np
spec=importlib.util.spec_from_file_location('retarget',Path(__file__).with_name('retarget-text-to-sign-alphabet.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def main():
    android=Path(__file__).resolve().parents[1]
    _,g,binary=r.packer.read(android/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb')
    nodes=g['nodes']; parents,order=r.skeleton(nodes); ids={n.get('name'):i for i,n in enumerate(nodes)}
    def data(index):
        a=g['accessors'][index];v=g['bufferViews'][a['bufferView']];n={'SCALAR':1,'VEC3':3,'VEC4':4}[a['type']]
        return np.frombuffer(binary,dtype='<f4',offset=v.get('byteOffset',0)+a.get('byteOffset',0),count=a['count']*n).reshape((-1,n)).copy()
    h=next(a for a in g['animations'] if a['name']=='SIGN_LETTER_H_WOLF3D_PREVIEW')
    pose={}
    for c in h['channels']:
        s=h['samplers'][c['sampler']]
        channel=dict(path=c['target']['path'],times=data(s['input']).flatten().tolist(),values=data(s['output']).tolist(),interpolation='LINEAR')
        pose[(c['target']['node'],c['target']['path'])]=r.sample(channel,.8)
    rest=r.world(nodes,parents,order); mirror=np.diag([-1,1,1])
    finger_pose={}
    for finger in ['Thumb','Index','Middle','Ring','Pinky']:
        for j in range(1,4):
            right=ids[f'RightHand{finger}{j}'];left=ids[f'LeftHand{finger}{j}']
            qr=r.rotation(pose[(right,'rotation')]);bind_r=r.rotation(nodes[right]['rotation']);bind_l=r.rotation(nodes[left]['rotation'])
            finger_pose[right]=qr;finger_pose[left]=mirror@(qr@bind_r.T)@mirror@bind_l
    def solve(side, wrist, direction):
        arm,fore,hand=[ids[side+n] for n in ['Arm','ForeArm','Hand']]
        middle=ids[side+'HandMiddle1'];index=ids[side+'HandIndex1'];pinky=ids[side+'HandPinky1']
        palm=np.cross(np.array(nodes[index]['translation'])-np.array(nodes[pinky]['translation']),nodes[middle]['translation'])
        hand_rotation=r.frame(direction,np.array([0,1,0]))@r.frame(np.array(nodes[middle]['translation']),palm).T
        points=[]
        for finger in ['Index','Middle']:
            m=np.eye(4)
            for j in range(1,3):
                bone=ids[side+'Hand'+finger+str(j)];local=np.eye(4)
                local[:3,:3]=finger_pose[bone];local[:3,3]=nodes[bone]['translation'];m=m@local
            points.append(m[:3,3])
        wrist=wrist-hand_rotation@np.mean(points,axis=0)
        shoulder=rest[arm][:3,3];upper=np.linalg.norm(rest[fore][:3,3]-shoulder);lower=np.linalg.norm(rest[hand][:3,3]-rest[fore][:3,3])
        vector=wrist-shoulder;distance=np.linalg.norm(vector);axis=r.unit(vector)
        assert abs(upper-lower)<distance<upper+lower, 'Unreachable candidate hand target'
        along=(upper*upper-lower*lower+distance*distance)/(2*distance)
        pole=np.array([1 if side=='Left' else -1,-.4,0]);pole=r.unit(pole-np.dot(pole,axis)*axis)
        elbow=shoulder+axis*along+pole*np.sqrt(upper*upper-along*along)
        desired={};dorsal=np.array([0,1,0])
        for bone,child,end in [(arm,fore,elbow),(fore,hand,wrist)]:
            local_axis=np.array(nodes[child]['translation']);reference=np.array([0,0,1])
            desired[bone]=r.frame(end-(shoulder if bone==arm else elbow),dorsal)@r.frame(local_axis,reference).T
        middle=ids[side+'HandMiddle1'];index=ids[side+'HandIndex1'];pinky=ids[side+'HandPinky1']
        palm=np.cross(np.array(nodes[index]['translation'])-np.array(nodes[pinky]['translation']),nodes[middle]['translation'])
        desired[hand]=hand_rotation
        return desired
    times=[0,.3,.50,.65,.85,1.0,1.15,1.4,1.75]
    records={i:[] for i in order if 'matrix' not in nodes[i]};kinematics=[]
    for t in times:
        active=t not in [0,1.75]
        desired={}
        if active:
            # Crossing finger directions at chest-level neutral space; dominant hand taps twice.
            dy={.3:.05,.50:.05,.65:0,.85:.05,1.0:.05,1.15:0,1.4:0}[t]
            center=np.array([0,1.20,.27]);rd=r.unit(np.array([1,0,1]));ld=r.unit(np.array([-1,0,1]))
            desired.update(solve('Right',center+np.array([0,.015+dy,0]),rd))
            desired.update(solve('Left',center-np.array([0,.015,0]),ld))
        worldrot={}
        for i in order:
            parent=worldrot.get(parents.get(i),np.eye(3))
            local=parent.T@desired[i] if i in desired else finger_pose[i] if active and i in finger_pose else r.rotation(nodes[i].get('rotation',[0,0,0,1]))
            worldrot[i]=parent@local
            if i in records:records[i].append(r.quaternion(local).tolist())
        w=r.world(nodes,parents,order,{(i,'rotation'):records[i][-1] for i in records})
        kin= dict(time=t,rightWrist=w[ids['RightHand']][:3,3].tolist(),leftWrist=w[ids['LeftHand']][:3,3].tolist())
        if active:kin['candidateFingerSeparationMeters']=float(np.linalg.norm(w[ids['RightHandIndex3']][:3,3]-w[ids['LeftHandIndex3']][:3,3]))
        kinematics.append(kin)
    out=bytearray(binary[:g['buffers'][0]['byteLength']])
    def accessor(values,kind):
        values=np.array(values,dtype='<f4')
        while len(out)%4:out.append(0)
        view=len(g['bufferViews']);g['bufferViews'].append(dict(buffer=0,byteOffset=len(out),byteLength=values.nbytes));out.extend(values.tobytes())
        index=len(g['accessors']);a=dict(bufferView=view,componentType=5126,count=len(values),type=kind)
        if kind=='SCALAR':a.update(min=[min(times)],max=[max(times)])
        g['accessors'].append(a);return index
    a=dict(name='CANDIDATE_NAME_TWO_H_DOUBLE_CONTACT_NOT_REVIEWED',samplers=[],channels=[]);input_index=accessor(times,'SCALAR')
    for i,values in records.items():
        for j in range(1,len(values)):
            if np.dot(values[j-1],values[j])<0:values[j]=(-np.array(values[j])).tolist()
        for prop,kind,v in [('rotation','VEC4',values),('translation','VEC3',[nodes[i].get('translation',[0,0,0])]*len(times)),('scale','VEC3',[nodes[i].get('scale',[1,1,1])]*len(times))]:
            sampler=len(a['samplers']);a['samplers'].append(dict(input=input_index,output=accessor(v,kind),interpolation='LINEAR'));a['channels'].append(dict(sampler=sampler,target=dict(node=i,path=prop)))
    g['animations']=[a];g['buffers'][0]['byteLength']=len(out)
    encoded=json.dumps(g,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);out+=b'\0'*(-len(out)%4)
    payload=struct.pack('<III',0x46546c67,2,12+8+len(encoded)+8+len(out))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(out),0x004e4942)+out
    folder=Path(sys.argv[1]);folder.mkdir(parents=True,exist_ok=True);(folder/'name-review-candidate.glb').write_bytes(payload)
    (folder/'name-review-candidate.json').write_text(json.dumps(dict(status='QUARANTINED_NOT_REGISTERED',
        sourceReference='https://www.lifeprint.com/asl101/pages-signs/n/name.htm',
        description='Two H-handshape review candidate, chest neutral space, crossed finger axes, two dominant-hand lowering movements',
        limitations=['Finger contact and palm orientation require visual correction/review','Not reviewed by qualified ASL signers','No question non-manual markers','Not enabled or packaged as NAME'],kinematics=kinematics),indent=2))
    print('Authored quarantined NAME candidate. Dictionary continues using N-A-M-E.')

if __name__=='__main__':main()
