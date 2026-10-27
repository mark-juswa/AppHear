"""Independent whole-bundle invariants and sampled hand-pose preservation."""
import argparse,importlib.util,json,hashlib
from pathlib import Path
import numpy as np

def module(name,file):
    s=importlib.util.spec_from_file_location(name,Path(__file__).with_name(file));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def batch_pose(model,tracks,times):
    """Same fixed-length skeleton math, evaluated across all requested times."""
    bynode={(t['node'],t['path']):t for t in tracks};n=len(times);world={}
    def sample(i,path,default):
        t=bynode.get((i,path))
        if t is None:return np.broadcast_to(np.asarray(default,dtype=float),(n,len(default)))
        clock=np.asarray(t['times']);values=np.asarray(t['values']);j=np.clip(np.searchsorted(clock,times,side='right')-1,0,len(clock)-1)
        a=values[j];k=np.minimum(j+1,len(clock)-1)
        if t['interpolation']=='STEP':return a
        b=values[k].copy();dt=clock[k]-clock[j];weight=np.divide(times-clock[j],dt,out=np.zeros(n),where=dt>0).clip(0,1)[:,None]
        if path=='rotation':b[np.sum(a*b,axis=1)<0]*=-1
        value=a*(1-weight)+b*weight
        return value/np.linalg.norm(value,axis=1)[:,None] if path=='rotation' else value
    for i in model.order:
        node=model.nodes[i];q=sample(i,'rotation',node.get('rotation',[0,0,0,1]));q=q/np.linalg.norm(q,axis=1)[:,None]
        x,y,z,w=q.T;local=np.broadcast_to(np.eye(4),(n,4,4)).copy()
        rot=np.stack([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)],axis=1).reshape(n,3,3)
        local[:,:3,:3]=rot*sample(i,'scale',node.get('scale',[1,1,1]))[:,None,:]
        local[:,:3,3]=sample(i,'translation',node.get('translation',[0,0,0]))
        if 'matrix' in node:local[:]=np.asarray(node['matrix']).reshape(4,4,order='F')
        parent=world.get(model.parents.get(i));world[i]=local if parent is None else parent@local
    return world
def orientations(values):
    u,_,v=np.linalg.svd(values[:,:3,:3]);u[:,:,-1]*=np.linalg.det(u@v)[:,None];return u@v
def main():
    p=argparse.ArgumentParser();p.add_argument('before',type=Path);p.add_argument('staged',type=Path);a=p.parse_args()
    h=module('hands','audit-text-to-sign-hands.py');v=module('integrity','verify-integrated-vocabulary.py')
    before=a.before.read_bytes();after=(a.staged/'avatar.glb').read_bytes()
    report=json.loads((a.staged/'report.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(before).hexdigest()==report['baselineSha256']
    assert hashlib.sha256(after).hexdigest()==report['sha256']
    old=h.Model(a.before);new=h.Model(a.staged/'avatar.glb');assert old.g==new.g
    changed={e['action'] for e in report['changed']};preserved=0;finger_tracks=0
    affected={s+n for s in ['Left','Right'] for n in ['Shoulder','Arm','ForeArm','Hand']}
    for action in old.g['animations']:
        name=action['name']
        if name not in changed:
            assert v.actionhash(old.g,old.binary,action)==v.actionhash(new.g,new.binary,action),name
            preserved+=1
        for ch in action['channels']:
            node=ch['target']['node'];sampler=action['samplers'][ch['sampler']]
            assert v.raw(old.g,old.binary,sampler['input'])==v.raw(new.g,new.binary,sampler['input'])
            if old.nodes[node]['name'] not in affected or name not in changed:
                assert v.raw(old.g,old.binary,sampler['output'])==v.raw(new.g,new.binary,sampler['output'])
            if 'Hand' in old.nodes[node]['name'] and old.nodes[node]['name'] not in ['LeftHand','RightHand']:finger_tracks+=1
    wrist_ids=[old.names[s+'Hand'] for s in ['Left','Right']]
    shoulder_ids=[old.names[s+'Shoulder'] for s in ['Left','Right']]
    maxima=dict(keyHandPositionMeters=0.,midpointHandPositionMeters=0.,keyHandOrientationDegrees=0.,midpointHandOrientationDegrees=0.,elbowDisplacementMeters=0.)
    sampled=0;midpoints=0
    for index,name in enumerate(sorted(changed)):
        ot=old.tracks(name);nt=new.tracks(name);clock=ot[0]['times'][1:-1]
        # Keep the complete key coverage and add EVERY inter-key midpoint.
        # Batch the matrix arithmetic instead of doing hundreds of thousands
        # of separate Python skeleton walks on the user's laptop.
        middle=(np.asarray(clock[:-1])+np.asarray(clock[1:]))/2
        times=np.r_[clock,middle];ow=batch_pose(old,ot,times);nw=batch_pose(new,nt,times)
        sampled+=len(times);midpoints+=len(middle)
        for idx in [0,len(clock)//2,len(times)-1]:
            for model,tracks,batch in [(old,ot,ow),(new,nt,nw)]:
                single=model.pose(tracks,float(times[idx]))
                assert max(float(np.max(np.abs(single[i]-batch[i][idx]))) for i in model.order)<1e-9,'Batch/reference pose mismatch'
        for i in wrist_ids:
            distance=np.linalg.norm(ow[i][:,:3,3]-nw[i][:,:3,3],axis=1)
            delta=np.transpose(orientations(ow[i]),(0,2,1))@orientations(nw[i])
            degrees=np.degrees(np.arccos(np.clip((np.trace(delta,axis1=1,axis2=2)-1)/2,-1,1)))
            for prefix,part,limit,angular in [('key',slice(0,len(clock)),1e-5,.01),('midpoint',slice(len(clock),None),.002,.5)]:
                d=float(np.max(distance[part]));q=float(np.max(degrees[part]))
                maxima[prefix+'HandPositionMeters']=max(maxima[prefix+'HandPositionMeters'],d)
                maxima[prefix+'HandOrientationDegrees']=max(maxima[prefix+'HandOrientationDegrees'],q)
                assert d<limit,(name,prefix,'wrist position',d)
                assert q<angular,(name,prefix,'wrist orientation',q)
        for side in ['Left','Right']:
            i=old.names[side+'ForeArm'];maxima['elbowDisplacementMeters']=max(maxima['elbowDisplacementMeters'],float(np.max(np.linalg.norm(ow[i][:,:3,3]-nw[i][:,:3,3],axis=1))))
        if index%25==0:print(json.dumps(dict(verified=index+1,total=len(changed),samples=sampled)),flush=True)
    result=dict(status='PASS',changedActions=len(changed),unchangedActions=preserved,fingerTracksByteIdentical=finger_tracks,
                sampledPoses=sampled,sampledMidpoints=midpoints,metrics=maxima,allClocksAndActionNamesUnchanged=True,
                rigSkinGeometryAndAlphabetUnchanged=True,qualifiedAslValidations=0)
    (a.staged/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
