"""Candidate-only ME/YOU pointing repair on the existing human; not ASL validation.

No global joint limits, player changes or rig edits. Geometry determines finger
flexion axes. ASLU references guide deictic direction; qualified review remains
required. Inspect the generated candidate on Android before applying it.
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
from PIL import Image, ImageDraw

spec = importlib.util.spec_from_file_location('prior', Path(__file__).with_name('correct-text-to-sign-word-fingers.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
c, r = p.c, p.c.r
BASELINE = 'c04f873aa44d7c31fdf688d423d18100843535067acab0223418ea9340fa34b5'
NAMES = ['SIGN_I', 'SIGN_YOU_HUMAN_RETARGETED_PREVIEW']


def blend(a, b, weight):
    return c.sample(dict(path='rotation', interpolation='LINEAR', times=[0., 1.], values=[a, b]), weight)


def write_glb(document, binary, path):
    document['buffers'][0]['byteLength'] = len(binary)
    encoded = json.dumps(document, separators=(',', ':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    raw = bytes(binary) + b'\0' * (-len(binary) % 4)
    payload = struct.pack('<III', 0x46546c67, 2, 28+len(encoded)+len(raw))
    payload += struct.pack('<II', len(encoded), 0x4e4f534a)+encoded
    payload += struct.pack('<II', len(raw), 0x004e4942)+raw
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    android = Path(__file__).resolve().parents[1]
    source = args.source or android/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == BASELINE
    model = c.hands.Model(source)
    rest = r.world(model.nodes, model.parents, model.order)
    neutral_tracks = model.tracks('SIGN_RELAXED_NEUTRAL')
    neutral = {(t['node'], t['path']): c.sample(t, 0.) for t in neutral_tracks}
    neutral_world = c.pose(model, neutral_tracks, 0.)
    mesh = c.ContactMesh(model)
    torso = mesh.skin(neutral_world)[mesh.torso_triangles]
    arm, elbow, hand = [model.names['Right'+part] for part in ['Arm', 'ForeArm', 'Hand']]
    palm = r.unit(np.cross(rest[model.names['RightHandIndex1']][:3, 3]-rest[model.names['RightHandPinky1']][:3, 3],
                           rest[model.names['RightHandMiddle1']][:3, 3]-rest[hand][:3, 3]))
    index = r.unit(rest[model.names['RightHandIndex4']][:3, 3]-rest[model.names['RightHandIndex1']][:3, 3])
    palm_local = r.orient(rest[hand]).T @ palm
    index_tip_local = r.orient(rest[hand]).T @ (rest[model.names['RightHandIndex4']][:3, 3]-rest[hand][:3, 3])
    fixed = {}
    donor = model.tracks('SIGN_YES')
    donor_time = max(t['times'][-1] for t in donor)*.4
    for finger in ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky']:
        for joint in [1, 2, 3]:
            node = model.names['RightHand'+finger+str(joint)]
            bind = np.array(model.nodes[node].get('rotation', [0, 0, 0, 1]))
            if finger == 'Index':
                fixed[node] = bind
            elif finger == 'Thumb':
                fixed[node] = c.sample(next(t for t in donor if t['node']==node and t['path']=='rotation'), donor_time)
            else:
                child = model.names['RightHand'+finger+str(joint+1)]
                direction = r.unit(rest[child][:3, 3]-rest[node][:3, 3])
                axis = r.orient(rest[node]).T @ r.unit(np.cross(direction, palm))
                angle = np.radians([80, 95, 50][joint-1])/2
                fixed[node] = r.unit(p.multiply(bind, np.r_[axis*np.sin(angle), np.cos(angle)]))
    document = copy.deepcopy(model.g)
    binary = bytearray(model.binary[:document['buffers'][0]['byteLength']])
    profiles = []

    def accessor(values, kind):
        values = np.asarray(values, dtype='<f4')
        while len(binary)%4: binary.append(0)
        view = len(document['bufferViews'])
        document['bufferViews'].append(dict(buffer=0, byteOffset=len(binary), byteLength=values.nbytes))
        binary.extend(values.tobytes())
        result = len(document['accessors'])
        entry = dict(bufferView=view, componentType=5126, count=len(values), type=kind)
        if kind == 'SCALAR': entry.update(min=[float(values.min())], max=[float(values.max())])
        document['accessors'].append(entry)
        return result

    for name in NAMES:
        is_you = name != 'SIGN_I'
        tracks = model.tracks(name)
        duration = max(t['times'][-1] for t in tracks)
        left = {model.names['Left'+part] for part in ['Shoulder', 'Arm', 'ForeArm', 'Hand']} if is_you else set()
        allowed = set(fixed) | {arm, elbow, hand} | left
        if is_you:
            direction, normal = np.array([0., 0., 1.]), np.array([0., -1., 0.])
            wrist = np.array([-.12, 1.25, .38])
            target_tip = None
        else:
            direction = r.unit(np.array([.8, -.03, -.6]))
            normal = r.unit(np.cross([0., 1., 0.], direction))
            target_tip = np.array([-.01, 1.30, 0.])
            target_tip[2] = c.front_surface(target_tip[None], torso)[0]+.020
        hand_rotation = r.frame(direction, normal) @ r.frame(index, palm).T @ r.orient(rest[hand])
        if not is_you: wrist = target_tip-hand_rotation@index_tip_local

        @cache
        def correction(time):
            overrides = {}
            if is_you:
                for node in allowed: overrides[(node, 'rotation')] = neutral[(node, 'rotation')]
            original_world = c.pose(model, tracks, time, overrides)
            u = min(1., max(0., min(time/.35, (duration-time)/.35)))
            weight = u*u*(3-2*u)
            for node, target in fixed.items():
                old = overrides.get((node, 'rotation'), c.sample(next(t for t in tracks if t['node']==node and t['path']=='rotation'), time))
                overrides[(node, 'rotation')] = blend(old, target, weight)
            goal = original_world[hand][:3, 3]*(1-weight)+wrist*weight
            # Lift in front of the torso before reaching the signing area.
            goal[2] += .065*np.sin(np.pi*weight)
            goal_rotation = r.rotation(blend(r.quaternion(r.orient(original_world[hand])), r.quaternion(hand_rotation), weight))
            solver_world = original_world.copy()
            solver_world[hand] = original_world[hand].copy()
            solver_world[hand][:3, :3] = goal_rotation @ r.orient(original_world[hand]).T @ original_world[hand][:3, :3]
            changes, _ = c.solve_arm(model, solver_world, 'Right', goal, torso, allow_entry_adjustment=True)
            overrides.update(changes)
            world = c.pose(model, tracks, time, overrides)
            fa = r.orient(world[elbow])
            axis = r.unit(world[hand][:3, 3]-world[elbow][:3, 3])
            bind_hand = np.array(model.nodes[hand].get('rotation', [0, 0, 0, 1]))
            a = fa@r.rotation(bind_hand)@palm_local
            b = goal_rotation@palm_local
            a, b = a-axis*(a@axis), b-axis*(b@axis)
            if np.linalg.norm(a)>1e-6 and np.linalg.norm(b)>1e-6:
                a, b = r.unit(a), r.unit(b)
                angle = np.arctan2(axis@np.cross(a, b), a@b)*weight
                k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
                roll = np.eye(3)+np.sin(angle)*k+(1-np.cos(angle))*(k@k)
                fa = roll@fa
                overrides[(elbow, 'rotation')] = r.quaternion(r.orient(world[arm]).T@fa)
                overrides[(hand, 'rotation')] = r.quaternion(fa.T@goal_rotation)
            if time == 0 or abs(time-duration)<1e-6:
                for node in allowed:
                    overrides[(node, 'rotation')] = neutral[(node, 'rotation')] if is_you else c.sample(next(t for t in tracks if t['node']==node and t['path']=='rotation'), time)
            return overrides

        times = np.linspace(0., duration, 361, dtype=np.float32)
        frames = [correction(float(t)) for t in times]
        print(name, 'pose frames generated', flush=True)
        animation = next(a for a in document['animations'] if a['name']==name)
        dense_input = accessor(times, 'SCALAR')
        for channel in animation['channels']:
            node = channel['target']['node']
            if node not in allowed or channel['target']['path']!='rotation': continue
            old_sampler = animation['samplers'][channel['sampler']]
            if node in {arm, elbow, hand}:
                key_input = dense_input
                values = [frame[(node, 'rotation')] for frame in frames]
            else:
                key_input = old_sampler['input']
                key_times = model.data(key_input).flatten()
                values = [correction(float(t))[(node, 'rotation')] for t in key_times]
            values = np.asarray(values)
            for i in range(1, len(values)):
                if values[i-1]@values[i]<0: values[i] = -values[i]
            sampler = len(animation['samplers'])
            animation['samplers'].append(dict(input=key_input, output=accessor(values, 'VEC4'), interpolation='LINEAR'))
            channel['sampler'] = sampler
        profiles.append(dict(animationName=name, changedNodes=sorted(model.nodes[n]['name'] for n in allowed),
                             desiredIndexDirection=direction.tolist(), wristTargetMeters=wrist.tolist(),
                             chestTipTargetMeters=None if target_tip is None else target_tip.tolist()))
    sha = write_glb(document, binary, args.output)
    after = c.hands.Model(args.output)
    after_mesh = c.ContactMesh(after)
    for old, new in zip(model.g['animations'], document['animations']):
        if old['name'] not in NAMES: continue
        profile = next(x for x in profiles if x['animationName']==old['name'])
        changed = set()
        for a, b in zip(old['channels'], new['channels']):
            assert a['target']==b['target']
            if a!=b:
                assert a['target']['path']=='rotation'
                changed.add(model.nodes[a['target']['node']]['name'])
        assert changed==set(profile['changedNodes'])
    for key in ['nodes', 'skins', 'meshes', 'materials', 'textures', 'images', 'scenes']: assert model.g[key]==document[key]
    assert [a for a in model.g['animations'] if a['name'] not in NAMES]==[a for a in document['animations'] if a['name'] not in NAMES]
    assert model.binary[:model.g['buffers'][0]['byteLength']]==after.binary[:model.g['buffers'][0]['byteLength']]
    for profile in profiles:
        name = profile['animationName']
        tr = after.tracks(name)
        duration = max(t['times'][-1] for t in tr)
        depth = dict(hand=0., forearm=0.)
        for time in np.linspace(0., duration, 401):
            world = c.pose(after, tr, float(time))
            vertices = after_mesh.skin(world)
            for part, values in after_mesh.depths(vertices, 'Right').items():
                depth[part] = max(depth[part], float(max(0., values.max())))
        world = c.pose(after, tr, duration*.4)
        a, b = [world[after.names['RightHandIndex'+str(j)]][:3, 3] for j in [1, 4]]
        profile.update(frontTorsoDepthMeters=depth, heldDirectionCosine=float(r.unit(b-a)@np.array(profile['desiredIndexDirection'])),
                       heldTipMeters=b.tolist(), technicallyPassed=depth['hand']<.005 and depth['forearm']<.010)
        image = Image.new('RGB', (880, 270), '#eef2f2')
        draw = ImageDraw.Draw(image)
        for i, m in enumerate([model, after]):
            for j, axes in enumerate([(0, 1), (2, 1)]):
                cell = (220*(i*2+j), 0)
                c.hands.render(draw, m, c.pose(m, m.tracks(name), duration*.4), 'Right', cell, axes=axes, bones=True)
                draw.text((cell[0]+3, 3), ('BEFORE ' if i==0 else 'AFTER ')+name, fill='black')
        image.save(args.report.with_name(args.report.stem+'-'+name+'.png'))
    report = dict(sourceSha256=BASELINE, sha256=sha, qualifiedASLValidation=False, status='UNREVIEWED_POINTING_PREVIEW',
                  unchangedActions=len(document['animations'])-2, profiles=profiles, transitionSeconds=.35, surfaceSamples=401,
                  references=['https://www.lifeprint.com/asl101/pages-signs/m/me.htm', 'https://www.lifeprint.com/asl101/pages-signs/y/you.htm'],
                  limitations='Front torso proxy only; requires Android inspection and qualified ASL review. Thumb reuses existing YES. No imported images or motion data.')
    protected = ['SIGN_LOVE', 'SIGN_YES', 'SIGN_HELP']+[name for name in model.animations if name.startswith('SIGN_LETTER_')]
    report['preservedAnimationHashes'] = {name: hashlib.sha256(json.dumps(model.animations[name], separators=(',', ':')).encode()).hexdigest() for name in protected}
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    assert all(x['technicallyPassed'] and x['heldDirectionCosine']>.999 for x in profiles), 'Candidate fails pointing/surface gate; do not apply'


if __name__ == '__main__': main()
