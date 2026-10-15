"""Reference-authored candidates on the resident rig; NOT imported/validated ASL.

Append-only offline authoring. No runtime IK, joint limits, new character or media
download. Explicit provenance distinguishes new trajectories from source motion.
Use the independent skin audit and actual Android inspection before packaging.
"""
import copy, hashlib, importlib.util, json, struct, sys
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('everyday',Path(__file__).with_name('expand-text-to-sign-everyday.py'))
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
r,c=e.r,e.c
BASELINE='c8e86f065acd1bb0fe39ee7524daad73324106a53fb8b455bf89744e4a1a778d'
PLANS=[
 ('stop','s/stop','Cease an activity; dominant flat hand edge meets upward other palm, not traffic stop or FINISH'),
 ('understand','u/understand','Comprehend; index opens near forehead; no automatic negation/headshake translation'),
 ('hungry','h/hungry','Hunger; C hand moves down central chest, no intensity or wish alias'),
 ('finish','f/finish','Completion; two five-hands turn outward while separating; no automatic tense/conjunction translation'),
 ('tired','t/tired','Fatigued; bent hands at chest rotate/slump, not a downward chest slide'),
 ('deaf','d/deaf','Deaf; index arcs between cheek near ear and cheek near mouth; not ear/lip contact'),
 ('hearing','h/hearing','Hearing person/community; index circles near mouth, distinct from physical HEAR'),
 ('learn','l/learn','Acquire knowledge; fingertips gather from upward palm and lift toward forehead, no agent suffix'),
 ('rain','r/rain','Ordinary rain; two bent/splayed hands descend twice, no wind/storm intensity'),
 ('now','n/now','Present time; palms-up Y hands descend ONCE, distinct from repeated TODAY'),
]

def smooth(u):
    u=float(np.clip(u,0,1));return u*u*(3-2*u)

class Author:
    def __init__(self,model):
        self.m=model;self.rest=r.world(model.nodes,model.parents,model.order)
        neutral_tracks=model.tracks('SIGN_RELAXED_NEUTRAL')
        # Idle also stores translation/scale. Never quaternion-normalize those
        # vectors: it changes hierarchy length internally even if output writes
        # rotations only. New actions intentionally inherit the immutable bind
        # translations/scales; require that idle agrees before authoring.
        for track in neutral_tracks:
            if track['path']=='rotation':continue
            default=[1,1,1] if track['path']=='scale' else [0,0,0]
            assert np.allclose(c.sample(track,0),model.nodes[track['node']].get(track['path'],default),atol=2e-6)
        self.neutral={(t['node'],t['path']):c.sample(t,0) for t in neutral_tracks if t['path']=='rotation'}
        self.mesh=c.ContactMesh(model)
        self.torso=self.mesh.skin(r.world(model.nodes,model.parents,model.order,self.neutral))[self.mesh.torso_triangles]
        self.poses={}
        for letter in ['B','C','O','Y']:
            ts=model.tracks(f'SIGN_LETTER_{letter}_WOLF3D_PREVIEW');at=max(t['times'][-1] for t in ts)*.65
            self.poses[letter]={t['node']:c.sample(t,at) for t in ts if t['path']=='rotation'}
        ts=model.tracks('SIGN_YES');at=max(t['times'][-1] for t in ts)*.4
        self.fist={t['node']:c.sample(t,at) for t in ts if t['path']=='rotation'}
        self.flat={}
        hand=model.names['RightHand'];w=self.rest
        palm=r.unit(np.cross(w[model.names['RightHandIndex1']][:3,3]-w[model.names['RightHandPinky1']][:3,3],w[model.names['RightHandMiddle1']][:3,3]-w[hand][:3,3]))
        direction=r.unit(w[model.names['RightHandMiddle4']][:3,3]-w[model.names['RightHandMiddle1']][:3,3])
        for finger in ['Thumb','Index','Middle','Ring','Pinky']:
            parent=r.orient(w[hand])
            for j in range(1,4):
                i=model.names['RightHand'+finger+str(j)];child=model.names['RightHand'+finger+str(j+1)]
                if finger=='Thumb': self.flat[i]=self.poses['B'][i];continue
                desired=r.frame(direction,palm)@r.frame(w[child][:3,3]-w[i][:3,3],palm).T@r.orient(w[i])
                self.flat[i]=r.quaternion(parent.T@desired);parent=desired

    def fingers(self,side,shape,amount=0):
        m,w=self.m,self.rest;values={};mirror=np.diag([-1.,1.,1.])
        hand=m.names['RightHand']
        palm=r.unit(np.cross(w[m.names['RightHandIndex1']][:3,3]-w[m.names['RightHandPinky1']][:3,3],w[m.names['RightHandMiddle1']][:3,3]-w[hand][:3,3]))
        for f in ['Thumb','Index','Middle','Ring','Pinky']:
            for j in range(1,4):
                right=m.names['RightHand'+f+str(j)];i=m.names[side+'Hand'+f+str(j)]
                bind=m.nodes[right].get('rotation',[0,0,0,1]);q=self.flat[right]
                if shape in ['Y','O']:q=self.poses[shape][right]
                elif shape in ['index','flick']:
                    q=self.flat[right] if f=='Index' else self.fist[right]
                    if shape=='flick' and f=='Thumb':q=self.poses['O'][right]
                    if shape=='flick' and f=='Index':q=e.blend(self.poses['O'][right],self.flat[right],amount)
                elif shape in ['five','rain']:q=bind
                if f!='Thumb':
                    angles=[0,0,0]
                    if shape=='C':angles=[30,45,15]
                    elif shape=='bent':angles=[80,0,0]
                    elif shape=='rain':angles=[35,15,5]
                    if any(angles):
                        child=m.names['RightHand'+f+str(j+1)]
                        axis=r.orient(w[right]).T@r.unit(np.cross(r.unit(w[child][:3,3]-w[right][:3,3]),palm))
                        a=np.radians(angles[j-1])/2
                        q=e.multiply(bind if shape=='rain' else self.flat[right],np.r_[axis*np.sin(a),np.cos(a)])
                elif shape=='C':q=self.poses['C'][right]
                if side=='Left':
                    rp=r.orient(w[m.parents[right]]);lp=r.orient(w[m.parents[i]])
                    delta=rp@r.rotation(q)@r.rotation(bind).T@rp.T
                    q=r.quaternion(lp.T@mirror@delta@mirror@lp@r.rotation(m.nodes[i].get('rotation',[0,0,0,1])))
                values[(i,'rotation')]=q
        return values

    def orientation(self,side,direction,palm):
        m,w=self.m,self.rest;h=m.names[side+'Hand']
        p=np.cross(w[m.names[side+'HandIndex1']][:3,3]-w[m.names[side+'HandPinky1']][:3,3],w[m.names[side+'HandMiddle1']][:3,3]-w[h][:3,3])
        if side=='Left':p=-p
        return r.frame(np.array(direction,float),np.array(palm,float))@r.frame(w[m.names[side+'HandMiddle4']][:3,3]-w[h][:3,3],p).T@r.orient(w[h])

    def place(self,overrides,side,point,direction,palm,anchor=None):
        """Fixed-length arm IK preserves the reference hand orientation/articulation."""
        m=self.m;hand=m.names[side+'Hand'];world=r.world(m.nodes,m.parents,m.order,overrides)
        rot=self.orientation(side,direction,palm)
        if anchor:
            node=m.names[side+'Hand'+anchor]
            local=r.orient(world[hand]).T@(world[node][:3,3]-world[hand][:3,3])
            point=np.asarray(point)-rot@local
        overrides[(hand,'rotation')]=r.quaternion(r.orient(world[m.parents[hand]]).T@rot)
        world=r.world(m.nodes,m.parents,m.order,overrides)
        changes,_=c.solve_arm(m,world,side,np.asarray(point),self.torso,allow_entry_adjustment=True,mesh=self.mesh)
        overrides.update(changes)

    def surface(self,x,y,gap=.012):
        z=float(c.front_surface(np.array([[x,y,0.]]),self.torso)[0])
        return z+gap if np.isfinite(z) else .16

    def pose(self,word,u):
        # The lexical movement occupies the middle; entry/release are neutral
        # blends. Alphabet and existing lexical tracks are never processed here.
        active=smooth(min(u/.18,(1-u)/.18));t=float(np.clip((u-.22)/.56,0,1));p=smooth(t)
        out=dict(self.neutral)
        two=word in ['stop','finish','tired','learn','rain','now']
        sides=['Left','Right'] if two else ['Right']
        for side in sides:
            shape={'understand':'flick','hungry':'C','finish':'five','deaf':'index','hearing':'index','tired':'bent','rain':'rain','now':'Y'}.get(word,'flat')
            out.update(self.fingers(side,shape,smooth((t-.22)/.20)))
            if word=='learn' and side=='Right':
                opened=self.fingers(side,'five');closed=self.fingers(side,'O')
                out.update({key:e.blend(q,closed[key],smooth((t-.10)/.25)) for key,q in opened.items()})
        if word=='stop':
            self.place(out,'Left',[.02,1.18,.34],[-1,0,0],[0,1,0])
            w=r.world(self.m.nodes,self.m.parents,self.m.order,out)
            palm=(w[self.m.names['LeftHandIndex1']][:3,3]+w[self.m.names['LeftHandPinky1']][:3,3]+w[self.m.names['LeftHand']][:3,3])/3
            # Dominant little-finger edge descends to the other palm, not into it.
            at=palm+np.array([0,.009+.15*(1-p),0])
            self.place(out,'Right',at,[0,0,1],[1,0,0],anchor='Pinky2')
        elif word=='hungry':
            y=1.40-.22*p
            self.place(out,'Right',[-.09,y,.26],[1,0,0],[0,0,-1])
        elif word=='finish':
            for side in sides:
                sign=-1 if side=='Right' else 1;a=np.pi*p
                self.place(out,side,[sign*(.16+.07*p),1.32,.33],[0,1,0],[sign*np.sin(a),0,-np.cos(a)])
                # Spread the hand's axial roll through the forearm rather than
                # putting a 180-degree twist into a single wrist joint.
                w=r.world(self.m.nodes,self.m.parents,self.m.order,out)
                arm,elbow,hand=[self.m.names[side+part] for part in ['Arm','ForeArm','Hand']]
                fa=r.orient(w[elbow]);rot=r.orient(w[hand]);axis=r.unit(w[hand][:3,3]-w[elbow][:3,3])
                palm=np.cross(self.rest[self.m.names[side+'HandIndex1']][:3,3]-self.rest[self.m.names[side+'HandPinky1']][:3,3],self.rest[self.m.names[side+'HandMiddle1']][:3,3]-self.rest[hand][:3,3])
                local=r.orient(self.rest[hand]).T@r.unit(palm)
                aa=fa@r.rotation(self.m.nodes[hand].get('rotation',[0,0,0,1]))@local;bb=rot@local
                aa-=axis*(aa@axis);bb-=axis*(bb@axis)
                if min(np.linalg.norm(aa),np.linalg.norm(bb))>1e-6:
                    aa,bb=r.unit(aa),r.unit(bb);angle=np.arctan2(axis@np.cross(aa,bb),aa@bb)
                    k=np.array([[0,-axis[2],axis[1]],[axis[2],0,-axis[0]],[-axis[1],axis[0],0]])
                    fa=(np.eye(3)+np.sin(angle)*k+(1-np.cos(angle))*(k@k))@fa
                    out[(elbow,'rotation')]=r.quaternion(r.orient(w[arm]).T@fa)
                    out[(hand,'rotation')]=r.quaternion(fa.T@rot)
        elif word=='deaf':
            x=-.080+.035*p;y=1.61-.095*p
            self.place(out,'Right',[x,y,self.surface(x,y,.014)+.025*np.sin(np.pi*p)],[.7,.7,0],[0,0,-1],anchor='Index4')
        elif word=='hearing':
            a=4*np.pi*t;y=1.505+.018*np.sin(a);z=.23-.018*np.cos(a)
            self.place(out,'Right',[-.01,y,z],[1,0,0],[0,0,-1],anchor='Index3')
        elif word=='understand':
            self.place(out,'Right',[-.14,1.59,.19],[0,1,0],[0,0,-1])
        elif word=='tired':
            for side in sides:
                sign=-1 if side=='Right' else 1
                # Slump is a wrist orientation change around a chest contact,
                # not a sliding hand trajectory or a global shoulder lock.
                a=np.radians(15+65*p)
                self.place(out,side,[sign*.14,1.36,.25],[0,np.cos(a),-np.sin(a)],[0,-np.sin(a),-np.cos(a)],anchor='Middle1')
        elif word=='learn':
            self.place(out,'Left',[.02,1.28,.29],[-1,0,0],[0,1,0])
            w=r.world(self.m.nodes,self.m.parents,self.m.order,out)
            start=(w[self.m.names['LeftHandIndex1']][:3,3]+w[self.m.names['LeftHandPinky1']][:3,3])/2+np.array([0,.025,0])
            goal=start*(1-p)+np.array([-.07,1.65,.20])*p
            a=-3*np.pi/4*(1-p)
            self.place(out,'Right',goal,[0,np.cos(a),np.sin(a)],[0,np.sin(a),-np.cos(a)],anchor='Middle4')
        elif word=='rain':
            # Two downward strokes; five/bent fingers depict droplets.
            drop=.5-.5*np.cos(4*np.pi*t)
            for side in sides:
                sign=-1 if side=='Right' else 1
                self.place(out,side,[sign*.18,1.60-.20*drop,.28],[0,0,1],[0,-1,0])
        elif word=='now':
            for side in sides:
                sign=-1 if side=='Right' else 1
                self.place(out,side,[sign*.18,1.21-.09*p,.30],[0,0,1],[0,1,0])
        out={key:e.blend(self.neutral.get(key,self.m.nodes[key[0]].get('rotation',[0,0,0,1])),q,active) for key,q in out.items()}
        # A rotation-only neutral blend can sweep the forearm into the body
        # even when both endpoints are clear. Correct that elbow path at the
        # SAME wrist target/orientation; never push sign contact/fingers away.
        world=r.world(self.m.nodes,self.m.parents,self.m.order,out)
        if word in ['stop','learn'] and (u<.18 or u>.82):
            # Lift forward before crossing the waist/chest, and release outward
            # before lowering. The held lexical trajectory/contact is unchanged.
            transition=u/.18 if u<.18 else (1-u)/.18
            clearance=.12*np.sin(np.pi*transition)**2
            for side in sides:
                shoulder,elbow,hand=[self.m.names[side+part] for part in ['Arm','ForeArm','Hand']]
                reach=np.linalg.norm(world[elbow][:3,3]-world[shoulder][:3,3])+np.linalg.norm(world[hand][:3,3]-world[elbow][:3,3])-.0001
                v=world[hand][:3,3]-world[shoulder][:3,3];direction=np.array([0.,1.,1.]);dot=float(v@direction)
                # Solve the reach sphere along the proposed entry path; keep
                # the original guarded IK solver and the original bone lengths.
                safe=max(0.,(-dot+np.sqrt(max(0.,dot*dot-2*(v@v-reach*reach))))/2)
                offset=min(clearance,safe)
                goal=world[hand][:3,3]+direction*offset
                changes,_=c.solve_arm(self.m,world,side,goal,self.torso,allow_entry_adjustment=True,mesh=self.mesh)
                out.update(changes);world=r.world(self.m.nodes,self.m.parents,self.m.order,out)
        vertices=self.mesh.skin(world)
        for side in sides:
            depths=self.mesh.depths(vertices,side)
            if float(depths['forearm'].max())>.002:
                hand=self.m.names[side+'Hand']
                changes,_=c.solve_arm(self.m,world,side,world[hand][:3,3],self.torso,mesh=self.mesh)
                out.update(changes);world=r.world(self.m.nodes,self.m.parents,self.m.order,out)
        assert all(path=='rotation' for _,path in out)
        for side in sides:
            for a,b in [('Arm','ForeArm'),('ForeArm','Hand')]:
                x,y=[self.m.names[side+part] for part in [a,b]]
                assert abs(np.linalg.norm(world[x][:3,3]-world[y][:3,3])-np.linalg.norm(self.rest[x][:3,3]-self.rest[y][:3,3]))<1e-6
        return out

def generate(source,output,report):
    source,output,report=map(Path,(source,output,report));payload=source.read_bytes()
    assert hashlib.sha256(payload).hexdigest()==BASELINE
    assert source.resolve()!=output.resolve()
    model=e.h.Model(source);author=Author(model);meta=json.loads(source.with_suffix('.json').read_text())
    android=Path(__file__).resolve().parents[1]
    original=json.loads((android/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/manifest.json').read_text())
    ids={v['id'] for v in original['replacements']+original['newClips']+meta['wordAdditions']}
    assert not ids.intersection(p[0] for p in PLANS)
    g=copy.deepcopy(model.g);binary=bytearray(model.binary[:g['buffers'][0]['byteLength']]);preserved=len(g['animations'])
    source_asset='asl_animations/original_words_v1/resident-avatar.glb'
    rig_sha=hashlib.sha256((android/'app/src/aslOriginalWords/assets'/source_asset).read_bytes()).hexdigest()
    def accessor(values,kind):
        data=np.asarray(values,dtype='<f4');assert np.isfinite(data).all()
        while len(binary)%4:binary.append(0)
        view=len(g['bufferViews']);g['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=data.nbytes));binary.extend(data.tobytes())
        i=len(g['accessors']);a=dict(bufferView=view,componentType=5126,count=len(data),type=kind)
        if kind=='SCALAR':a.update(min=[float(data.min())],max=[float(data.max())])
        g['accessors'].append(a);return i
    for word,reference,meaning in PLANS:
        duration=3.0 if word in ['learn','deaf','rain'] else 2.6
        times=np.linspace(0,duration,79,dtype=np.float32)
        frames=[author.pose(word,float(t/duration)) for t in times]
        name=f'SIGN_{word.upper()}_HUMAN_AUTHORED_PREVIEW'
        action=dict(name=name,samplers=[],channels=[]);inp=accessor(times,'SCALAR')
        for node in model.order:
            if 'matrix' in model.nodes[node]:continue
            key=(node,'rotation');bind=model.nodes[node].get('rotation',[0,0,0,1])
            values=np.asarray([f.get(key,bind) for f in frames])
            for j in range(1,len(values)):
                if values[j-1]@values[j]<0:values[j]*=-1
            sampler=len(action['samplers']);action['samplers'].append(dict(input=inp,output=accessor(values,'VEC4'),interpolation='LINEAR'))
            action['channels'].append(dict(sampler=sampler,target=dict(node=node,path='rotation')))
        g['animations'].append(action)
        meta['wordAdditions'].append(dict(id=word,english=[word],animationName=name,durationMs=round(duration*1000),
          sourceAsset=source_asset,sourceSha256=rig_sha,sourceRole='Resident rig/mesh provenance only; NOT an imported animation for this word',
          construction='REFERENCE_AUTHORED_PREVIEW',status='UNREVIEWED_NATIVE_VARIANT_PREVIEW',language='ASL',gloss=[word.upper()],
          reference=f'https://www.lifeprint.com/asl101/pages-signs/{reference}.htm',meaning=meaning,
          license='New local reference-authored keyframes; existing AppHear human rig provenance unresolved. No reference media copied; no redistribution rights asserted.',
          linguisticValidationStatus='UNREVIEWED',technicalPlaybackStatus='Candidate: Android visual review required',
          correctionNotes='Sign-specific trajectory and handshape on actual rig; no global joint clamps or edits to old animations. Non-manual grammar not certified.'))
        print(word,'native candidate prepared',flush=True)
    assert g['animations'][:preserved]==model.g['animations']
    for k in ['nodes','skins','meshes','materials','textures','images','scenes']:assert g[k]==model.g[k]
    g['buffers'][0]['byteLength']=len(binary);encoded=json.dumps(g,separators=(',',':')).encode();encoded+=b' '*(-len(encoded)%4);binary+=b'\0'*(-len(binary)%4)
    data=struct.pack('<III',0x46546c67,2,28+len(encoded)+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    output.write_bytes(data);meta['sha256']=hashlib.sha256(data).hexdigest()
    audit=dict(version=1,baselineSha256=BASELINE,preservedActions=preserved,newLexicalActions=len(PLANS),sourceGeometryUnchanged=True,qualifiedAslValidations=0,
       construction='REFERENCE_AUTHORED_PREVIEW',checks=[dict(id=p[0],reference=f'https://www.lifeprint.com/asl101/pages-signs/{p[1]}.htm') for p in PLANS])
    meta['everydayExpansion3']=audit;output.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n');report.write_text(json.dumps(audit,indent=2)+'\n')
    print(meta['sha256'])

if __name__=='__main__':generate(*sys.argv[1:4])
