"""Candidate-only conversion of ten existing AppHear motions to its resident rig.

No external media, generic handshape, joint clamp or linguistic certification.
Preserves all existing motion/geometry bytes. Inspect candidates before packaging.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import numpy as np

spec = importlib.util.spec_from_file_location('hands', Path(__file__).with_name('audit-text-to-sign-hands.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
r = h.r
spec_c = importlib.util.spec_from_file_location('contact', Path(__file__).with_name('correct-text-to-sign-love.py'))
c = importlib.util.module_from_spec(spec_c)
spec_c.loader.exec_module(c)
BASELINE = '82fab0b6693c5bdaef8433e25d4f417a51f0ede522ab9e9154e4f8cff7fddeb8'
PLANS = [
    ('best', 'best', ['best'], 'Best in a comparison; GOOD-derived upward movement', 'b/best'),
    ('better', 'better', ['better'], 'Better in a comparison; GOOD-derived outward movement', 'b/better'),
    ('divorce', 'divorce', ['divorce'], 'Divorce; two D hands separate with outward palm rotation', 'd/divorce'),
    ('from', 'from', ['from'], 'Origin or source; dominant index changes to X while pulling away', 'f/from'),
    ('grandma', 'grandma', ['grandma', 'grandmother'], 'Grandmother; open hand moves forward from chin', 'g/grandma'),
    ('grandpa', 'grandpa', ['grandpa', 'grandfather'], 'Grandfather; open hand moves forward from forehead', 'g/grandpa'),
    ('here', 'here', ['here'], 'This location; palms-up relaxed hands circle near waist', 'h/here'),
    ('parents', 'parents', ['parents'], 'Parents; successive mother/father locations', 'p/parents'),
    ('prefer', 'prefer-favorite', ['prefer', 'favorite'], 'Preference / favorite; middle finger taps chin, not lips', 'p/prefer'),
    ('single', 'single-alone-something-someone', ['single'], 'Single / alone context-dependent index-circle variation', 's/single'),
]

def digest(data):
    return hashlib.sha256(data).hexdigest()

def multiply(a,b):
    av,bv=np.asarray(a[:3]),np.asarray(b[:3])
    return np.r_[a[3]*bv+b[3]*av+np.cross(av,bv),a[3]*b[3]-av@bv]

def blend(a,b,u):
    return c.sample(dict(path='rotation',times=[0.,1.],values=[a,b],interpolation='LINEAR'),u)

def reference_pose(model,neutral,rest,torso,hand_profiles,word,phase,source_rotations):
    """Scoped reference-guided keyframe corrections, NOT qualified ASL review.

    Geometry-derived flexion axes replace malformed curls only on these new
    actions. Contact trajectories are authored on this rig; source thumb and
    wrist form is retained for comparisons/divorce. No old motion is changed.
    """
    override=dict(neutral)
    envelope=np.clip(min(phase/.12,(1-phase)/.12),0,1)
    envelope=envelope*envelope*(3-2*envelope)
    if phase<1e-6 or phase>1-1e-6:
        return {i:q for (i,path),q in neutral.items() if path=='rotation'}
    active_sides=['Right','Left'] if word in ['from','here','divorce'] else ['Right']
    for side in active_sides:
        for part in ['Arm','ForeArm','Hand']:
            i=model.names[side+part]
            override[(i,'rotation')]=source_rotations[i]
    # Anatomical open/curled finger axes: independent joints, no global clamp.
    for side in active_sides:
        hand=model.names[side+'Hand']
        palm=r.unit(np.cross(rest[model.names[side+'HandIndex1']][:3,3]-rest[model.names[side+'HandPinky1']][:3,3],
                             rest[model.names[side+'HandMiddle1']][:3,3]-rest[hand][:3,3]))
        if side=='Left': palm=-palm
        for finger in ['Thumb','Index','Middle','Ring','Pinky']:
            for joint in range(1,4):
                i=model.names[side+'Hand'+finger+str(joint)]
                bind=np.asarray(model.nodes[i].get('rotation',[0,0,0,1]))
                q=bind
                angles=[0,0,0]
                if word in ['best','better'] and finger!='Thumb':
                    close=np.clip((phase-.22)/.30,0,1);angles=np.array([80,95,50])*close
                elif word in ['from','single'] and finger not in ['Thumb','Index']:
                    angles=[80,95,50]
                elif word=='from' and side=='Right' and finger=='Index':
                    angles=[0,65*np.clip((phase-.30)/.32,0,1),10]
                elif word=='here' and finger!='Thumb': angles=[8,8,5]
                elif word=='prefer' and finger=='Middle': angles=[45,0,0]
                elif word=='divorce':
                    q=source_rotations[i] # Actual D-hand source articulation, not a generic fist.
                if any(angles):
                    child=model.names[side+'Hand'+finger+str(joint+1)]
                    direction=r.unit(rest[child][:3,3]-rest[i][:3,3])
                    axis=r.orient(rest[i]).T@r.unit(np.cross(direction,palm))
                    angle=np.radians(angles[joint-1])/2
                    q=r.unit(multiply(bind,np.r_[axis*np.sin(angle),np.cos(angle)]))
                if finger=='Thumb' and word in ['best','better']: q=source_rotations[i]
                if finger=='Thumb' and word in ['from','single']: q=hand_profiles['thumb'][i]
                if word in ['grandma','grandpa','parents']: q=hand_profiles['five'][i]
                override[(i,'rotation')]=blend(neutral.get((i,'rotation'),bind),q,envelope)
    world=r.world(model.nodes,model.parents,model.order,override)
    movement=np.clip((phase-.17)/.66,0,1)
    for side in active_sides:
        hand=model.names[side+'Hand']; sign=-1 if side=='Right' else 1
        # These locations follow the linked reference's signing area. Exact
        # contact/repetition/style remains review-required, not a grammar rule.
        if word in ['grandma','grandpa','parents']:
            chin=hand_profiles.get('familyChin',1.51);forehead=hand_profiles.get('familyForehead',1.70)
            y=chin if word=='grandma' else forehead
            if word=='parents': y=chin+(forehead-chin)*np.clip((movement-.25)/.45,0,1)
            z=float(c.front_surface(np.array([[0.,y,0.]]),torso)[0])+.018
            if not np.isfinite(z): z=.145
            if word!='parents':
                z+=.18*movement
                y+=.025*np.sin(4*np.pi*movement)
            # Five-hand palm faces across the signer, with the thumb toward
            # the chin/forehead. A front-facing palm put the wrist behind the
            # contact point and drove the heel of the hand into the face.
            direction=np.array([0.,1.,0.]);normal=np.asarray(hand_profiles.get('familyNormal',[1.,0.,0.]))
            rot=r.frame(direction,normal)@r.frame(
                world[model.names[side+'HandMiddle4']][:3,3]-world[hand][:3,3],
                np.cross(world[model.names[side+'HandIndex1']][:3,3]-world[model.names[side+'HandPinky1']][:3,3],
                         world[model.names[side+'HandMiddle1']][:3,3]-world[hand][:3,3])).T@r.orient(world[hand])
            tip=model.names[side+'HandThumb4']
            local=r.orient(world[hand]).T@(world[tip][:3,3]-world[hand][:3,3])
            goal=np.array([-.015,y,z])-rot@local
        elif word=='prefer':
            direction=np.array([0.,1.,0.]);normal=np.array([0.,0.,-1.])
            palm=np.cross(rest[model.names[side+'HandIndex1']][:3,3]-rest[model.names[side+'HandPinky1']][:3,3],
                          rest[model.names[side+'HandMiddle1']][:3,3]-rest[hand][:3,3])
            rot=r.frame(direction,normal)@r.frame(rest[model.names[side+'HandMiddle4']][:3,3]-rest[hand][:3,3],palm).T@r.orient(rest[hand])
            tip=model.names[side+'HandMiddle4'];local=r.orient(world[hand]).T@(world[tip][:3,3]-world[hand][:3,3])
            y=1.475;z=float(c.front_surface(np.array([[0.,y,0.]]),torso)[0])+.030+.012*(1-np.cos(4*np.pi*movement))
            goal=np.array([0.,y,z])-rot@local
        elif word=='here':
            direction=np.array([0.,0.,1.]);normal=np.array([0.,1.,0.])
            palm=np.cross(rest[model.names[side+'HandIndex1']][:3,3]-rest[model.names[side+'HandPinky1']][:3,3],
                          rest[model.names[side+'HandMiddle1']][:3,3]-rest[hand][:3,3])
            if side=='Left': palm=-palm
            rot=r.frame(direction,normal)@r.frame(rest[model.names[side+'HandMiddle4']][:3,3]-rest[hand][:3,3],palm).T@r.orient(rest[hand])
            goal=np.array([sign*(.18+.025*np.sin(4*np.pi*movement)),1.12,.25+.025*np.cos(4*np.pi*movement)])
        else:
            rot=r.orient(world[hand])
            if word=='from':
                goal=np.array([-.12-.10*movement,1.22,.26]) if side=='Right' else np.array([.025,1.22,.26])
            elif word=='single': goal=np.array([-.17+.012*np.cos(4*np.pi*movement),1.22,.27+.012*np.sin(4*np.pi*movement)])
            elif word=='divorce': goal=np.array([sign*(.075+.16*movement),1.26,.27])
            elif word=='better': goal=np.array([-.04-.15*movement,1.44+.07*movement,.29])
            else: goal=np.array([-.04-.15*movement,1.43+.21*movement-.08*np.sin(np.pi*movement),.29])
        # Two-bone solution preserves bone lengths and the chosen wrist frame.
        neutral_world=r.world(model.nodes,model.parents,model.order,neutral)
        goal=neutral_world[hand][:3,3]*(1-envelope)+goal*envelope
        # Position-space entry/exit goes in front of the body; interpolating
        # full arm quaternions alone swept the hand through the torso.
        goal[2]+=.13*np.sin(np.pi*envelope)
        rot=r.rotation(blend(r.quaternion(r.orient(neutral_world[hand])),r.quaternion(rot),envelope))
        solver={i:v.copy() for i,v in world.items()}
        solver[hand][:3,:3]=rot@r.orient(world[hand]).T@world[hand][:3,:3]
        changes,_=c.solve_arm(model,solver,side,goal,torso,allow_entry_adjustment=True,
                              mesh=hand_profiles.get('mesh') if word in ['from','grandma','prefer'] else None)
        override.update(changes)
        world=r.world(model.nodes,model.parents,model.order,override)
        # Put axial roll into the forearm instead of twisting the wrist. World
        # hand orientation and every finger pose remain unchanged.
        elbow=model.names[side+'ForeArm'];arm=model.names[side+'Arm']
        fa=r.orient(world[elbow]);axis=r.unit(world[hand][:3,3]-world[elbow][:3,3])
        palm=np.cross(rest[model.names[side+'HandIndex1']][:3,3]-rest[model.names[side+'HandPinky1']][:3,3],rest[model.names[side+'HandMiddle1']][:3,3]-rest[hand][:3,3])
        palm_local=r.orient(rest[hand]).T@r.unit(palm)
        aa=fa@r.rotation(model.nodes[hand].get('rotation',[0,0,0,1]))@palm_local;bb=rot@palm_local
        aa-=axis*(aa@axis);bb-=axis*(bb@axis)
        if np.linalg.norm(aa)>1e-6 and np.linalg.norm(bb)>1e-6:
            aa,bb=r.unit(aa),r.unit(bb);angle=np.arctan2(axis@np.cross(aa,bb),aa@bb)
            k=np.array([[0,-axis[2],axis[1]],[axis[2],0,-axis[0]],[-axis[1],axis[0],0]])
            fa=(np.eye(3)+np.sin(angle)*k+(1-np.cos(angle))*(k@k))@fa
            override[(elbow,'rotation')]=r.quaternion(r.orient(world[arm]).T@fa)
            override[(hand,'rotation')]=r.quaternion(fa.T@rot)
            world=r.world(model.nodes,model.parents,model.order,override)
    return {i:q for (i,path),q in override.items() if path=='rotation'}

def generate(source_bundle, output, report_path, *, plans=PLANS, baseline=BASELINE,
             pose_function=reference_pose, audit_key='everydayExpansion',
             correction_notes='Reference-guided handshape/contact keyframes on resident rig; independent anatomical curl axes; unvalidated timing/style. Original source action retained in repository.'):
    source_bundle, output, report_path = map(Path, (source_bundle, output, report_path))
    payload = source_bundle.read_bytes()
    assert digest(payload) == baseline, 'Use the checkpoint bundle, never overwrite/reprocess a newer bundle'
    assert output.resolve() != source_bundle.resolve(), 'Candidate output must be separate'
    target = h.Model(source_bundle)
    manifest = json.loads(source_bundle.with_suffix('.json').read_text())
    android = Path(__file__).resolve().parents[1]
    raw_root = android / 'app/src/main/assets'
    old_names = set(target.animations)
    existing = json.loads((android / 'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/manifest.json').read_text())
    ids = {e['id'] for e in existing['replacements'] + existing['newClips']}
    ids.update(e['id'] for e in manifest['wordAdditions'])
    assert not ids.intersection(p[0] for p in plans), 'Candidate entries already exist'
    preserved_count = len(target.g['animations'])
    gltf = copy.deepcopy(target.g)
    original_binary = target.binary[:gltf['buffers'][0]['byteLength']]
    binary = bytearray(original_binary)
    tw = r.world(target.nodes, target.parents, target.order)
    neutral_tracks = target.tracks('SIGN_RELAXED_NEUTRAL')
    neutral = {(c['node'], c['path']): r.sample(c, 0) for c in neutral_tracks}
    mesh=c.ContactMesh(target)
    torso=mesh.skin(r.world(target.nodes,target.parents,target.order,neutral))[mesh.torso_triangles]
    thumb_pose={}
    for side,donor_name in [('Right','SIGN_YES'),('Left','SIGN_CALL__TO_CALL_SOMEONE_S_NAME')]:
        donor=target.tracks(donor_name);time=max(t['times'][-1] for t in donor)*.4
        for joint in range(1,4):
            node=target.names[side+'HandThumb'+str(joint)]
            thumb_pose[node]=c.sample(next(t for t in donor if t['node']==node and t['path']=='rotation'),time)
    # Open articulation was checked against the source/reference, not adopted
    # from the MOTHER clip: transplanting that posed thumb failed contact checks.
    # Contact height is calibrated to this mesh's chin, not its neck pivot.
    five_pose={i:target.nodes[i].get('rotation',[0,0,0,1]) for i in target.order if
               target.nodes[i].get('name','').startswith('RightHand') and target.nodes[i]['name']!='RightHand'}
    hand_profiles=dict(thumb=thumb_pose,five=five_pose,mesh=mesh)
    checks = []
    for word, filename, english, meaning, reference in plans:
        source_path = raw_root / f'asl_animations/{filename}.glb'
        source = h.Model(source_path)
        assert len(source.animations)==1, (filename, list(source.animations))
        source_action = next(iter(source.animations))
        tracks = source.tracks(source_action)
        sw = r.world(source.nodes, source.parents, source.order)
        mapping, conversions = {}, {}
        for side, letter in [('Right', 'r'), ('Left', 'l')]:
            palm_s = np.cross(sw[source.names[f'{letter}_handIndex1_JNT']][:3, 3] - sw[source.names[f'{letter}_handPinky1_JNT']][:3, 3],
                              sw[source.names[f'{letter}_handMiddle1_JNT']][:3, 3] - sw[source.names[f'{letter}_hand_JNT']][:3, 3])
            palm_t = np.cross(tw[target.names[side+'HandIndex1']][:3, 3] - tw[target.names[side+'HandPinky1']][:3, 3],
                              tw[target.names[side+'HandMiddle1']][:3, 3] - tw[target.names[side+'Hand']][:3, 3])
            def pair(tname, sname, tchild, schild):
                ti, si = target.names[tname], source.names[sname]
                sy = sw[source.names[schild]][:3,3]-sw[si][:3,3] if schild else sw[si][:3,3]-sw[source.parents[si]][:3,3]
                ty = tw[target.names[tchild]][:3,3]-tw[ti][:3,3]
                conversions[ti] = (r.orient(sw[si]).T @ r.frame(sy,palm_s)) @ (r.orient(tw[ti]).T @ r.frame(ty,palm_t)).T
                mapping[ti] = si
            pair(side+'Arm', letter+'_arm_JNT', side+'ForeArm', letter+'_forearm_JNT')
            pair(side+'ForeArm', letter+'_forearm_JNT', side+'Hand', letter+'_hand_JNT')
            pair(side+'Hand', letter+'_hand_JNT', side+'HandMiddle1', letter+'_handMiddle1_JNT')
            for finger in ['Thumb','Index','Middle','Ring','Pinky']:
                for j in range(1,4):
                    pair(side+'Hand'+finger+str(j), f'{letter}_hand{finger}{j}_JNT', side+'Hand'+finger+str(j+1),
                         f'{letter}_hand{finger}{j+1}_JNT' if j<3 else None)
        times = sorted({float(t) for c in tracks for t in c['times']})
        assert times and all(np.isfinite(times)) and times[0] >= 0
        duration = times[-1]
        output_times = [0.] + [t+.35 for t in times] + [duration+.70]
        assert all(b>a for a,b in zip(output_times,output_times[1:]))
        rotations = {i: [] for i in target.order if 'matrix' not in target.nodes[i]}
        max_error = 0.
        for time in times:
            world = source.pose(tracks,time)
            result = {}
            source_rotations={}
            for i in target.order:
                parent = result.get(target.parents.get(i), np.eye(3))
                desired = r.orient(world[mapping[i]])@conversions[i] if i in mapping else None
                local = parent.T@desired if desired is not None else r.rotation(neutral.get((i,'rotation'),target.nodes[i].get('rotation',[0,0,0,1])))
                result[i] = parent@local
                if i in mapping:
                    max_error = max(max_error,float(np.max(np.abs(result[i]-desired))))
                    source_rotations[i]=r.quaternion(local).tolist()
            corrected=pose_function(target,neutral,tw,torso,hand_profiles,word,time/duration,source_rotations)
            for i in rotations: rotations[i].append(corrected.get(i,target.nodes[i].get('rotation',[0,0,0,1])))
        def accessor(values, kind):
            values = np.asarray(values,dtype='<f4')
            assert np.isfinite(values).all()
            while len(binary)%4: binary.append(0)
            view = len(gltf['bufferViews'])
            gltf['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=values.nbytes))
            binary.extend(values.tobytes())
            index = len(gltf['accessors'])
            a = dict(bufferView=view,componentType=5126,count=len(values),type=kind)
            if kind=='SCALAR': a.update(min=[min(output_times)],max=[max(output_times)])
            gltf['accessors'].append(a)
            return index
        animation = dict(name=f'SIGN_{word.upper()}_HUMAN_RETARGETED_PREVIEW',samplers=[],channels=[])
        assert animation['name'] not in old_names
        inp = accessor(output_times,'SCALAR')
        # Explicit baseline rotations on every skeleton node prevent previous-sign leakage.
        # Only source-mapped arm/hand/finger nodes move. No bone-length/scale changes.
        for i in target.order:
            if 'matrix' in target.nodes[i]: continue
            q = list(neutral.get((i,'rotation'),target.nodes[i].get('rotation',[0,0,0,1])))
            values = [q]+rotations.get(i,[q]*len(times))+[q]
            for j in range(1,len(values)):
                if np.dot(values[j-1],values[j])<0: values[j]=(-np.asarray(values[j])).tolist()
            sampler = len(animation['samplers'])
            animation['samplers'].append(dict(input=inp,output=accessor(values,'VEC4'),interpolation='LINEAR'))
            animation['channels'].append(dict(sampler=sampler,target=dict(node=i,path='rotation')))
        gltf['animations'].append(animation)
        entry = dict(id=word,english=english,animationName=animation['name'],durationMs=round(output_times[-1]*1000),
            sourceAsset=f'asl_animations/{filename}.glb',sourceSha256=digest(source_path.read_bytes()),
            reference=f'https://www.lifeprint.com/asl101/pages-signs/{reference}.htm',meaning=meaning,
            status='UNREVIEWED_RETARGETED_PREVIEW',language='ASL',gloss=[word.upper()],
            license='Existing AppHear motion/rig provenance unresolved; local development preview only. Reference links only, no reference media copied.',
            linguisticValidationStatus='UNREVIEWED',technicalPlaybackStatus='Candidate: device review required')
        entry['correctionNotes']=correction_notes
        manifest['wordAdditions'].append(entry)
        assert max_error<1e-10
        checks.append(dict(id=word,sourceAction=source_action,sourceSha256=entry['sourceSha256'],frames=len(times),
            anatomicalFrameError=max_error,mappedNodes=len(mapping),reference=entry['reference'],qualifiedAslValidation=False))
        print(word,'candidate frames prepared',flush=True)
    for key in ['nodes','skins','meshes','materials','textures','images','scenes']:
        assert target.g[key]==gltf[key],key
    assert gltf['animations'][:preserved_count]==target.g['animations']
    assert bytes(binary[:len(original_binary)])==original_binary
    gltf['buffers'][0]['byteLength']=len(binary)
    encoded=json.dumps(gltf,separators=(',',':')).encode()
    encoded+=b' '*(-len(encoded)%4)
    binary+=b'\0'*(-len(binary)%4)
    payload=struct.pack('<III',0x46546c67,2,12+8+len(encoded)+8+len(binary))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    output.write_bytes(payload)
    manifest['sha256']=digest(payload)
    manifest[audit_key]=dict(version=1,baselineSha256=baseline,preservedActions=preserved_count,newLexicalActions=len(plans),
        sourceGeometryUnchanged=True,qualifiedAslValidations=0,checks=checks)
    output.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    report=dict(bundleSha256=manifest['sha256'],animations=len(gltf['animations']),checks=checks,
        existingActionsByteIdentical=True,geometryAndSkinUnchanged=True,qualifiedAslValidations=0)
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__': generate(*sys.argv[1:4])
