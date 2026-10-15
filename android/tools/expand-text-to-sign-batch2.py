"""Candidate-only second batch; preserve Update-1 geometry and every old action.

No new runtime dependency or global finger constraints. Conversion is not linguistic
validation: inspect candidate motion and reject unsuitable clips before packaging.
"""
import importlib.util
from pathlib import Path
import sys
import copy,hashlib,json,struct
import numpy as np

spec=importlib.util.spec_from_file_location('everyday',Path(__file__).with_name('expand-text-to-sign-everyday.py'))
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
BASELINE='11b50d333dae036132515c535bea9b9adbf0d42f43be901bb7c4b36b3bb1e43c'
PLANS=[
 ('again','again',['again','repeat','do over'],'Repeat or do again; bent fingertips arc into flat non-dominant palm','a/again'),
 ('class','class',['class'],'Educational class; two C hands outline a group, not social status','c/class'),
 ('must','critical-must',['must'],'Obligation or necessity; source MUST variant, not every meaning of critical','m/must'),
 ('fingerspell','fingerspell',['fingerspell','fingerspelling','spell'],'Lexical sign about spelling; this does not change the alphabet fallback controller','f/fingerspell'),
 ('so_so','so-so',['so so','so-so'],'Middling condition/so-so; palm-down hand rocks side to side','s/so-so'),
 ('grow_up','grow-up-raised',['grow up'],'Growing from childhood to adulthood; not every sense of raised','g/grow-up'),
]

def source_pose(model,neutral,rest,torso,profiles,word,phase,source):
    """Reuse equivalent rig-native B/C/X articulation; retain lexical arm motion.

    FINGERSPELL retains each source joint's flexion component independently,
    removing the axial twist introduced by incompatible source finger axes.
    This correction is scoped to these new actions, never the alphabet/old words.
    """
    envelope=float(np.clip(min(phase/.12,(1-phase)/.12),0,1))
    envelope=envelope*envelope*(3-2*envelope)
    result={i:q for (i,path),q in neutral.items() if path=='rotation'}
    for node,pose in source.items():
        bind=model.nodes[node].get('rotation',[0,0,0,1])
        result[node]=e.blend(neutral.get((node,'rotation'),bind),pose,envelope)
    if 'letters' not in profiles:
        profiles['letters']={}
        for letter in ['B','C','X']:
            tracks=model.tracks(f'SIGN_LETTER_{letter}_WOLF3D_PREVIEW')
            time=max(t['times'][-1] for t in tracks)*.65
            profiles['letters'][letter]={t['node']:e.c.sample(t,time) for t in tracks
              if t['path']=='rotation' and model.nodes[t['node']].get('name','').startswith('RightHand')}
        yes=model.tracks('SIGN_YES');yt=max(t['times'][-1] for t in yes)*.4
        profiles['fist']={t['node']:e.c.sample(t,yt) for t in yes if t['path']=='rotation'}
        # Explicit straight, parallel phalanges for the reference's flat B hand.
        # Native letter clips can include coarticulation, so their mid-clip pose
        # alone is not a reliable static flat-hand donor for lexical signs.
        profiles['flat']=dict(profiles['letters']['B'])
        hand=model.names['RightHand']
        palm=e.r.unit(np.cross(rest[model.names['RightHandIndex1']][:3,3]-rest[model.names['RightHandPinky1']][:3,3],
                              rest[model.names['RightHandMiddle1']][:3,3]-rest[hand][:3,3]))
        direction=e.r.unit(rest[model.names['RightHandMiddle4']][:3,3]-rest[model.names['RightHandMiddle1']][:3,3])
        for finger in ['Index','Middle','Ring','Pinky']:
            parent=e.r.orient(rest[hand])
            for joint in range(1,4):
                node=model.names['RightHand'+finger+str(joint)];child=model.names['RightHand'+finger+str(joint+1)]
                old_axis=rest[child][:3,3]-rest[node][:3,3]
                desired=e.r.frame(direction,palm)@e.r.frame(old_axis,palm).T@e.r.orient(rest[node])
                profiles['flat'][node]=e.r.quaternion(parent.T@desired)
                parent=desired
    letter='C' if word=='class' else 'X' if word=='must' else 'B'
    active=['Right','Left'] if word in ['again','class'] else ['Right']
    mirror=np.diag([-1.,1.,1.])
    for side in ['Right','Left']:
        hand=model.names[side+'Hand']
        palm=e.r.unit(np.cross(rest[model.names[side+'HandIndex1']][:3,3]-rest[model.names[side+'HandPinky1']][:3,3],
                              rest[model.names[side+'HandMiddle1']][:3,3]-rest[hand][:3,3]))
        if side=='Left':palm=-palm
        for finger in ['Thumb','Index','Middle','Ring','Pinky']:
            for joint in range(1,4):
                node=model.names[side+'Hand'+finger+str(joint)]
                bind=np.asarray(model.nodes[node].get('rotation',[0,0,0,1]))
                q=neutral.get((node,'rotation'),bind)
                if side in active:
                    right=model.names['RightHand'+finger+str(joint)]
                    q=profiles['flat'][right]
                    if letter=='C' and finger=='Thumb':q=profiles['letters']['C'][right]
                    elif letter=='X' and finger!='Index':q=profiles['fist'][right]
                    if finger!='Thumb' and letter in ['C','X']:
                        rr=right;rc=model.names['RightHand'+finger+str(joint+1)]
                        rh=model.names['RightHand']
                        pn=e.r.unit(np.cross(rest[model.names['RightHandIndex1']][:3,3]-rest[model.names['RightHandPinky1']][:3,3],rest[model.names['RightHandMiddle1']][:3,3]-rest[rh][:3,3]))
                        ax=e.r.orient(rest[rr]).T@e.r.unit(np.cross(e.r.unit(rest[rc][:3,3]-rest[rr][:3,3]),pn))
                        angle=np.radians(([30,45,15] if letter=='C' else [0,90,0])[joint-1])
                        if letter=='C' or finger=='Index':q=e.multiply(profiles['flat'][right],np.r_[ax*np.sin(angle/2),np.cos(angle/2)])
                    if side=='Left':
                        rp=e.r.orient(rest[model.parents[right]]);lp=e.r.orient(rest[model.parents[node]])
                        delta=rp@e.r.rotation(q)@e.r.rotation(model.nodes[right].get('rotation',[0,0,0,1])).T@rp.T
                        q=e.r.quaternion(lp.T@mirror@delta@mirror@lp@e.r.rotation(bind))
                    child=model.names[side+'Hand'+finger+str(joint+1)]
                    axis=e.r.orient(rest[node]).T@e.r.unit(np.cross(e.r.unit(rest[child][:3,3]-rest[node][:3,3]),palm))
                    if word=='again' and side=='Right' and finger!='Thumb' and joint==1:
                        angle=np.pi/2
                        q=e.multiply(q,np.r_[axis*np.sin(angle/2),np.cos(angle/2)])
                    elif word=='fingerspell' and finger!='Thumb':
                        delta=e.r.quaternion(e.r.rotation(bind).T@e.r.rotation(source[node]))
                        angle=2*np.arctan2(delta[:3]@axis,delta[3])
                        q=e.multiply(q,np.r_[axis*np.sin(angle/2),np.cos(angle/2)])
                    if word=='so_so':
                        # ASLU specifies a five-hand, not the flat B used by
                        # GROW UP. Retain this rig's open, splayed articulation.
                        q=bind
                result[node]=e.blend(neutral.get((node,'rotation'),bind),q,envelope)
    # Source arm lengths do not match the human. Scoped placement correction
    # translates BOTH hands equally, retaining their relative contact geometry.
    # No generic avoidance applies to any old sign, or to the other new signs.
    shift={'again':np.array([0.,0.,.035]),'class':np.array([0.,-.20,.030])}.get(word)
    if shift is not None and envelope>0:
        overrides={(node,'rotation'):q for node,q in result.items()}
        world=e.r.world(model.nodes,model.parents,model.order,overrides)
        if word=='class':
            # Lower the elevated source signing area, not the resting arms.
            # Applying the full offset near neutral would exceed arm reach.
            height=min(world[model.names[s+'Hand']][1,3] for s in ['Right','Left'])
            shift=shift.copy();shift[1]*=np.clip((height-1.3)/.2,0,1)
        for side in ['Right','Left']:
            hand=model.names[side+'Hand']
            goal=world[hand][:3,3]+shift*envelope
            changes,_=e.c.solve_arm(model,world,side,goal,torso,allow_entry_adjustment=True,mesh=profiles['mesh'])
            overrides.update(changes)
            world=e.r.world(model.nodes,model.parents,model.order,overrides)
        result={i:q for (i,path),q in overrides.items() if path=='rotation'}
    return result

def correct_again_contact(output,report_path):
    """Enforce reference-required fingertips-to-palm contact at closest approach.

    Preserve the original arc/timing and all finger channels; only the three
    dominant arm/wrist samplers are adjusted through a smooth contact envelope.
    """
    output=Path(output);report_path=Path(report_path)
    model=e.h.Model(output);name='SIGN_AGAIN_HUMAN_RETARGETED_PREVIEW'
    tracks=model.tracks(name);hand=model.names['RightHand'];tip=model.names['RightHandMiddle4']
    times=next(t['times'] for t in tracks if t['node']==hand)
    mesh=e.c.ContactMesh(model);torso=mesh.skin(e.c.pose(model,model.tracks('SIGN_RELAXED_NEUTRAL'),0))[mesh.torso_triangles]
    def contact(world):
        palm=sum(world[model.names['LeftHand'+suffix]][:3,3] for suffix in ['', 'Index1','Pinky1'])/3
        normal=-e.r.unit(np.cross(world[model.names['LeftHandIndex1']][:3,3]-world[model.names['LeftHandPinky1']][:3,3],
                                  world[model.names['LeftHandMiddle1']][:3,3]-world[model.names['LeftHand']][:3,3]))
        return palm+normal*.010
    candidates=[(float(np.linalg.norm(w[tip][:3,3]-contact(w))),t)
      for t in times if .35<t<max(times)-.35 for w in [e.c.pose(model,tracks,t)]]
    before,peak=min(candidates);window=(max(times)-.70)*.30
    frames=[];error=0.
    for time in times:
        w=e.c.pose(model,tracks,time)
        u=abs(time-peak)/window;weight=.5*(1+np.cos(np.pi*u)) if u<1 else 0.
        shift=(contact(w)-w[tip][:3,3])*weight
        if weight>0:
            changes,_=e.c.solve_arm(model,w,'Right',w[hand][:3,3]+shift,torso,allow_entry_adjustment=True,mesh=mesh)
        else:changes={(model.names['Right'+part],'rotation'):next(t for t in tracks if t['node']==model.names['Right'+part])['values'][times.index(time)] for part in ['Arm','ForeArm','Hand']}
        updated=e.c.pose(model,tracks,time,changes)
        error=max(error,float(np.linalg.norm(updated[tip][:3,3]-w[tip][:3,3]-shift)))
        frames.append(changes)
    assert error<1e-5,'Contact correction must preserve finger shape/world orientation'
    g=copy.deepcopy(model.g);binary=bytearray(model.binary[:g['buffers'][0]['byteLength']])
    action=next(a for a in g['animations'] if a['name']==name)
    allowed={model.names['Right'+part] for part in ['Arm','ForeArm','Hand']}
    for channel in action['channels']:
        node=channel['target']['node']
        if node not in allowed:continue
        assert channel['target']['path']=='rotation'
        values=np.asarray([f[(node,'rotation')] for f in frames],dtype='<f4')
        for n in range(1,len(values)):
            if values[n-1]@values[n]<0:values[n]*=-1
        while len(binary)%4:binary.append(0)
        view=len(g['bufferViews']);g['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=values.nbytes));binary.extend(values.tobytes())
        accessor=len(g['accessors']);g['accessors'].append(dict(bufferView=view,componentType=5126,count=len(values),type='VEC4'))
        action['samplers'][channel['sampler']]['output']=accessor
    assert [a for a in g['animations'] if a['name']!=name]==[a for a in model.g['animations'] if a['name']!=name]
    g['buffers'][0]['byteLength']=len(binary);encoded=json.dumps(g,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4)
    data=struct.pack('<III',0x46546c67,2,28+len(encoded)+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    output.write_bytes(data);sha=hashlib.sha256(data).hexdigest()
    metadata=json.loads(output.with_suffix('.json').read_text());metadata['sha256']=sha
    record=dict(contactTimeSeconds=peak,previousTipToPalmSurfaceGapMeters=before,maxFingerRigidShiftErrorMeters=error,
                fingerChannelsUnchanged=True,otherActionsUnchanged=247,qualifiedAslValidation=False)
    metadata['everydayExpansion2']['againContactCorrection']=record
    output.with_suffix('.json').write_text(json.dumps(metadata,indent=2)+'\n')
    report=json.loads(report_path.read_text());report.update(bundleSha256=sha,againContactCorrection=record)
    report_path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(bundleSha256=sha,againContactCorrection=record)))

if __name__=='__main__':
    e.generate(*sys.argv[1:4],plans=PLANS,baseline=BASELINE,pose_function=source_pose,audit_key='everydayExpansion2',
      correction_notes='Actual source arm/wrist motion with equivalent resident-rig B/C/X handshapes, a dominant bent hand for AGAIN, and source-driven independent flexion without axial twist for FINGERSPELL. AGAIN/CLASS have scoped shared placement corrections and fixed-length arm IK. No global finger limits or changes to old words/alphabet. Qualified ASL review still required.')
    correct_again_contact(sys.argv[2],sys.argv[3])
