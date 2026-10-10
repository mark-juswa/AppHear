"""Offline, review-required FemaleASL alphabet -> existing Wolf3D human.

No lexical signs are synthesized. Anatomical segment/palm frames map rotations;
target bone lengths, meshes, skinning and all existing word actions stay intact.
Requires development-only NumPy and decoded source JSON from the companion tool.
"""
import bisect
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import numpy as np

from importlib.machinery import SourceFileLoader
packer = SourceFileLoader('packer', str(Path(__file__).with_name('bundle-text-to-sign-avatar.py'))).load_module()

def rotation(q):
    x,y,z,w = np.array(q)/np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])

def quaternion(m):
    # Eigenvector form is stable for 180-degree rotations as well as ordinary poses.
    a,b,c=m[0]; d,e,f=m[1]; g,h,i=m[2]
    k=np.array([[a-e-i,b+d,c+g,h-f],[b+d,e-a-i,f+h,c-g],
                [c+g,f+h,i-a-e,d-b],[h-f,c-g,d-b,a+e+i]])/3
    values,vectors=np.linalg.eigh(k)
    q=vectors[:,np.argmax(values)]
    return q if q[3]>=0 else -q

def unit(v):
    return v/np.linalg.norm(v)

def frame(y,z):
    y=unit(y); z=unit(z-np.dot(z,y)*y); x=unit(np.cross(y,z))
    return np.column_stack((x,y,z))

def skeleton(nodes):
    parents={c:i for i,n in enumerate(nodes) for c in n.get('children',[])}
    order=[]
    def visit(i):
        if i in order:return
        if i in parents:visit(parents[i])
        order.append(i)
    for i in range(len(nodes)):visit(i)
    return parents,order

def world(nodes, parents, order, overrides=None):
    result={}
    overrides=overrides or {}
    for i in order:
        n=nodes[i]; t=np.array(overrides.get((i,'translation'),n.get('translation',[0,0,0])))
        r=rotation(overrides.get((i,'rotation'),n.get('rotation',[0,0,0,1])))
        s=overrides.get((i,'scale'),n.get('scale',[1,1,1]))
        local=np.eye(4); local[:3,:3]=r@np.diag(s); local[:3,3]=t
        if 'matrix' in n:local=np.array(n['matrix']).reshape((4,4),order='F')
        result[i]=result.get(parents.get(i),np.eye(4))@local
    return result

def orient(matrix):
    return matrix[:3,:3]/np.linalg.norm(matrix[:3,:3],axis=0)

def sample(channel,t):
    times=channel['times']; j=max(0,min(len(times)-1,bisect.bisect_right(times,t)-1))
    a=np.array(channel['values'][j])
    if j==len(times)-1 or channel['interpolation']=='STEP':return a
    b=np.array(channel['values'][j+1]); ratio=max(0,(t-times[j])/(times[j+1]-times[j]))
    if channel['path']=='rotation':
        if np.dot(a,b)<0:b=-b
        q=a*(1-ratio)+b*ratio
        return q/np.linalg.norm(q)
    return a*(1-ratio)+b*ratio

def main():
    source=json.loads(Path(sys.argv[1]).read_text())
    assert source['sourceSha256']=='645da29f5e8a24dc7da2f4b6e23ca2e87fb91254958f5053ba0281080ec0a524'
    android=Path(__file__).resolve().parents[1]
    target=android/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/resident-avatar.glb'
    _,gltf,bin_data=packer.read(target)
    assert len(gltf['animations'])==203, 'Regenerate original bundle before retargeting'
    nodes=gltf['nodes']; snodes=source['nodes'][:345]
    sp,so=skeleton(snodes); tp,to=skeleton(nodes)
    sw=world(snodes,sp,so); tw=world(nodes,tp,to)
    si={n['name']:i for i,n in enumerate(snodes[:342])}; ti={n['name']:i for i,n in enumerate(nodes)}
    mapping={}; conversions={}
    for side,letter in [('Right','r'),('Left','l')]:
        def pair(target_name,source_name,child_target,child_source):
            t=ti[target_name]; s=si[source_name]
            palm_s=np.cross(sw[si['index_01_'+letter]][:3,3]-sw[si['pinky_01_'+letter]][:3,3],
                            sw[si['middle_01_'+letter]][:3,3]-sw[si['hand_'+letter]][:3,3])
            palm_t=np.cross(tw[ti[side+'HandIndex1']][:3,3]-tw[ti[side+'HandPinky1']][:3,3],
                            tw[ti[side+'HandMiddle1']][:3,3]-tw[ti[side+'Hand']][:3,3])
            fs=frame(sw[si[child_source]][:3,3]-sw[s][:3,3],palm_s)
            ft=frame(tw[ti[child_target]][:3,3]-tw[t][:3,3],palm_t)
            conversions[t]=(orient(sw[s]).T@fs)@(orient(tw[t]).T@ft).T
            mapping[t]=s
        pair(side+'Arm','upperarm_'+letter,side+'ForeArm','lowerarm_'+letter)
        pair(side+'ForeArm','lowerarm_'+letter,side+'Hand','hand_'+letter)
        pair(side+'Hand','hand_'+letter,side+'HandMiddle1','middle_01_'+letter)
        for finger in ['Thumb','Index','Middle','Ring','Pinky']:
            for j in range(1,4):
                # Last source phalanx has no tip node: use its own local X axis.
                src=finger.lower()+f'_{j:02d}_'+letter
                if j<3:
                    pair(side+'Hand'+finger+str(j),src,side+'Hand'+finger+str(j+1),finger.lower()+f'_{j+1:02d}_'+letter)
                else:
                    t=ti[side+'Hand'+finger+'3']; s=si[src]
                    # Source phalanges point +X on left and -X on right; target points +Y.
                    y_s=np.array([1 if letter=='l' else -1,0,0]); y_t=nodes[ti[side+'Hand'+finger+'4']].get('translation')
                    # Use the preceding segment's dorsal axis for consistent distal twist.
                    parent_t=ti[side+'Hand'+finger+'2']; parent_s=si[finger.lower()+'_02_'+letter]
                    z_s=orient(sw[s]).T@(orient(sw[parent_s])@np.array([0,1,0]))
                    z_t=orient(tw[t]).T@(orient(tw[parent_t])@np.array([0,0,1]))
                    conversions[t]=frame(y_s,z_s)@frame(np.array(y_t),z_t).T; mapping[t]=s
    binary=bytearray(bin_data[:gltf['buffers'][0]['byteLength']])
    def accessor(values,kind):
        values=np.asarray(values,dtype='<f4'); flat=values.flatten();
        while len(binary)%4:binary.append(0)
        view=len(gltf['bufferViews']); gltf['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=flat.nbytes))
        binary.extend(flat.tobytes()); index=len(gltf['accessors'])
        a=dict(bufferView=view,componentType=5126,count=len(values),type=kind)
        if kind=='SCALAR':a.update(min=[float(flat.min())],max=[float(flat.max())])
        gltf['accessors'].append(a); return index
    entries=[]; audit=[]
    for a in source['animations']:
        letter=a['name'].split('_')[2]; channels=a['channels']
        start=min(min(c['times']) for c in channels); end=max(max(c['times']) for c in channels)
        times=sorted({max(start,min(end,t)) for c in channels for t in c['times']})
        # Explicit neutral endpoints distinguish repeated letters using clip completion,
        # rather than wall-clock delays. Source hand motion is retained between endpoints.
        output_times=[0]+[t-start+0.25 for t in times]+[end-start+0.50]
        rotations={i:[nodes[i].get('rotation',[0,0,0,1])] for i in to if 'matrix' not in nodes[i]}
        max_frame_error=0.0; hand_positions=[]
        for t in times:
            poses={(c['node'],c['path']):sample(c,t) for c in channels}
            source_world=world(snodes,sp,so,poses)
            result={}
            for i in to:
                parent=result.get(tp.get(i),np.eye(3))
                if i in mapping:
                    desired=orient(source_world[mapping[i]])@conversions[i]
                    local=parent.T@desired
                    max_frame_error=max(max_frame_error,float(np.max(np.abs(parent@local-desired))))
                else:local=rotation(nodes[i].get('rotation',[0,0,0,1]))
                result[i]=parent@local
                if i in rotations:rotations[i].append(quaternion(local).tolist())
            hand_positions.append(source_world[si['hand_r']][:3,3].tolist())
        animation=dict(name=f'SIGN_LETTER_{letter}_WOLF3D_PREVIEW',samplers=[],channels=[])
        time_index=accessor(output_times,'SCALAR')
        for i,values in rotations.items():
            values.append(nodes[i].get('rotation',[0,0,0,1]))
            # Quaternion hemisphere continuity avoids unnecessary full-turn interpolation.
            for j in range(1,len(values)):
                if np.dot(values[j-1],values[j])<0:values[j]=(-np.array(values[j])).tolist()
            sampler=len(animation['samplers']); animation['samplers'].append(dict(input=time_index,output=accessor(values,'VEC4'),interpolation='LINEAR'))
            animation['channels'].append(dict(sampler=sampler,target=dict(node=i,path='rotation')))
            # Reset translations/scales left by a previous word action, retaining bind lengths.
            for prop,kind,default in [('translation','VEC3',[0,0,0]),('scale','VEC3',[1,1,1])]:
                sampler=len(animation['samplers']); animation['samplers'].append(dict(input=time_index,output=accessor([nodes[i].get(prop,default)]*len(output_times),kind),interpolation='LINEAR'))
                animation['channels'].append(dict(sampler=sampler,target=dict(node=i,path=prop)))
        gltf['animations'].append(animation)
        entries.append(dict(letter=letter.lower(),id='letter_'+letter.lower(),animationName=animation['name'],durationMs=round(output_times[-1]*1000)))
        span=np.ptp(np.array(hand_positions),axis=0)
        audit.append(dict(letter=letter,sourceHandMotionSpan=span.tolist(),rotationFrameError=max_frame_error,
                          sourceSamples=len(times),sourceDurationMs=round((end-start)*1000)))
    assert len(entries)==26 and {e['letter'] for e in entries}==set('abcdefghijklmnopqrstuvwxyz')
    gltf['buffers'][0]['byteLength']=len(binary)
    encoded=json.dumps(gltf,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4)
    payload=struct.pack('<III',0x46546c67,2,12+8+len(encoded)+8+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    output=target.with_name('fingerspelling-avatar.glb');output.write_bytes(payload)
    manifest=dict(schemaVersion=1,language='ASL',avatarProfile='ORIGINAL_HUMAN',asset='asl_animations/original_words_v1/fingerspelling-avatar.glb',
                  sha256=hashlib.sha256(payload).hexdigest(),sourceSha256=source['sourceSha256'],status='UNREVIEWED_RETARGETED_PREVIEW',
                  source='Existing AppHear FemaleASL alphabet; motion rights/provenance unresolved',
                  reference='https://www.lifeprint.com/asl101/fingerspelling/fingerspelling.htm',letters=entries,audit=audit,
                  nameLexicalStatus='MISSING; use N-A-M-E fallback; external SiGML has no joint-space motion')
    output.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(bytes=len(payload),sha256=manifest['sha256'],letters=len(entries),animations=len(gltf['animations']),audit=audit[-1]),indent=2))

if __name__=='__main__':main()
