"""Retarget the existing YOU clip to the resident human, for local preview review.

No reference video is copied and no motion/handshape is invented. Source and
target anatomical segment/palm frames establish each bone-space conversion.
Existing 230 actions and their binary data must remain byte-identical.
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


def main():
    android = Path(__file__).resolve().parents[1]
    word = sys.argv[2] if len(sys.argv) > 2 else 'you'
    plans = {
        'you': ('you', ['you'], 'Second-person singular addressee', 'y/you'),
        'you_all': ('you-all', ['you all', 'all of you'], 'Plural addressees', 'y/you'),
        'again': ('again', ['again', 'repeat', 'do over'], 'Repeat or do something again', 'a/again'),
    }
    filename, english, meaning, reference = plans[word]
    source_path = android / f'app/src/main/assets/asl_animations/{filename}.glb'
    target_path = Path(sys.argv[3]) if len(sys.argv) > 3 else android / 'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb'
    source = h.Model(source_path)
    target = h.Model(target_path)
    manifest = json.loads(target_path.with_suffix('.json').read_text())
    assert len(target.animations) == 230 + len(manifest.get('wordAdditions', []))
    assert word not in {entry['id'] for entry in manifest.get('wordAdditions', [])}, 'Already appended'
    preserved_count = len(target.animations)
    source_tracks = source.tracks(filename)
    sw = r.world(source.nodes, source.parents, source.order)
    tw = r.world(target.nodes, target.parents, target.order)
    mapping = {}
    conversions = {}
    for side, letter in [('Right', 'r'), ('Left', 'l')]:
        def pair(tname, sname, tchild, schild):
            t, s = target.names[tname], source.names[sname]
            palm_s = np.cross(sw[source.names[f'{letter}_handIndex1_JNT']][:3, 3] - sw[source.names[f'{letter}_handPinky1_JNT']][:3, 3],
                              sw[source.names[f'{letter}_handMiddle1_JNT']][:3, 3] - sw[source.names[f'{letter}_hand_JNT']][:3, 3])
            palm_t = np.cross(tw[target.names[side + 'HandIndex1']][:3, 3] - tw[target.names[side + 'HandPinky1']][:3, 3],
                              tw[target.names[side + 'HandMiddle1']][:3, 3] - tw[target.names[side + 'Hand']][:3, 3])
            # Source terminal joints have no tip: extend their preceding segment.
            sy = sw[source.names[schild]][:3, 3] - sw[s][:3, 3] if schild else sw[s][:3, 3] - sw[source.parents[s]][:3, 3]
            ty = tw[target.names[tchild]][:3, 3] - tw[t][:3, 3]
            fs, ft = r.frame(sy, palm_s), r.frame(ty, palm_t)
            conversions[t] = (r.orient(sw[s]).T @ fs) @ (r.orient(tw[t]).T @ ft).T
            mapping[t] = s
        pair(side + 'Arm', f'{letter}_arm_JNT', side + 'ForeArm', f'{letter}_forearm_JNT')
        pair(side + 'ForeArm', f'{letter}_forearm_JNT', side + 'Hand', f'{letter}_hand_JNT')
        pair(side + 'Hand', f'{letter}_hand_JNT', side + 'HandMiddle1', f'{letter}_handMiddle1_JNT')
        for finger in ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky']:
            for joint in range(1, 4):
                pair(side + 'Hand' + finger + str(joint), f'{letter}_hand{finger}{joint}_JNT',
                     side + 'Hand' + finger + str(joint + 1), f'{letter}_hand{finger}{joint + 1}_JNT' if joint < 3 else None)
    times = sorted({t for c in source_tracks for t in c['times']})
    duration = max(times)
    rotations = {i: [] for i in target.order if 'matrix' not in target.nodes[i]}
    frame_error = 0.
    for t in times:
        world = source.pose(source_tracks, t)
        result = {}
        for i in target.order:
            parent = result.get(target.parents.get(i), np.eye(3))
            desired = r.orient(world[mapping[i]]) @ conversions[i] if i in mapping else None
            local = parent.T @ desired if desired is not None else r.rotation(target.nodes[i].get('rotation', [0, 0, 0, 1]))
            result[i] = parent @ local
            if desired is not None:
                frame_error = max(frame_error, float(np.max(np.abs(result[i] - desired))))
            if i in rotations:
                rotations[i].append(r.quaternion(local).tolist())
    # Rest endpoints permit neutral return; source signing trajectory is intact.
    output_times = [0.] + [t + .20 for t in times] + [duration + .40]
    gltf = copy.deepcopy(target.g)
    binary = bytearray(target.binary[:gltf['buffers'][0]['byteLength']])
    preserved_binary = bytes(binary)
    def accessor(values, kind):
        values = np.asarray(values, dtype='<f4')
        assert np.isfinite(values).all()
        while len(binary) % 4:
            binary.append(0)
        view = len(gltf['bufferViews'])
        gltf['bufferViews'].append(dict(buffer=0, byteOffset=len(binary), byteLength=values.nbytes))
        binary.extend(values.tobytes())
        index = len(gltf['accessors'])
        a = dict(bufferView=view, componentType=5126, count=len(values), type=kind)
        if kind == 'SCALAR':
            a.update(min=[min(output_times)], max=[max(output_times)])
        gltf['accessors'].append(a)
        return index
    animation = dict(name=f'SIGN_{word.upper()}_HUMAN_RETARGETED_PREVIEW', samplers=[], channels=[])
    input_index = accessor(output_times, 'SCALAR')
    for i, active_values in rotations.items():
        values = [target.nodes[i].get('rotation', [0, 0, 0, 1])] + active_values + [target.nodes[i].get('rotation', [0, 0, 0, 1])]
        for j in range(1, len(values)):
            if np.dot(values[j-1], values[j]) < 0:
                values[j] = (-np.array(values[j])).tolist()
        for prop, kind, v in [('rotation', 'VEC4', values), ('translation', 'VEC3', [target.nodes[i].get('translation', [0, 0, 0])] * len(values)),
                              ('scale', 'VEC3', [target.nodes[i].get('scale', [1, 1, 1])] * len(values))]:
            sampler = len(animation['samplers'])
            animation['samplers'].append(dict(input=input_index, output=accessor(v, kind), interpolation='LINEAR'))
            animation['channels'].append(dict(sampler=sampler, target=dict(node=i, path=prop)))
    gltf['animations'].append(animation)
    assert gltf['animations'][:preserved_count] == target.g['animations'] and bytes(binary[:len(preserved_binary)]) == preserved_binary
    assert frame_error < 1e-10
    gltf['buffers'][0]['byteLength'] = len(binary)
    encoded = json.dumps(gltf, separators=(',', ':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    binary += b'\0' * (-len(binary) % 4)
    payload = struct.pack('<III', 0x46546c67, 2, 12+8+len(encoded)+8+len(binary)) + struct.pack('<II', len(encoded), 0x4e4f534a) + encoded + struct.pack('<II', len(binary), 0x004e4942) + binary
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else target_path
    output.write_bytes(payload)
    manifest['sha256'] = hashlib.sha256(payload).hexdigest()
    manifest['wordAdditions'] = manifest.get('wordAdditions', []) + [dict(id=word, english=english, animationName=animation['name'], durationMs=round(output_times[-1]*1000),
        sourceAsset=f'asl_animations/{filename}.glb', sourceSha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        reference=f'https://www.lifeprint.com/asl101/pages-signs/{reference}.htm', meaning=meaning,
        status='UNREVIEWED_RETARGETED_PREVIEW', license='Existing AppHear motion/rig provenance unresolved; reference link only, no reference media copied')]
    manifest['vocabularyExpansion'] = dict(version=1, preservedActions=230, lastSourceFrames=len(times), anatomicalFrameError=frame_error,
        qualifiedAslValidation=False, sourceGeometryUnchanged=True)
    output.with_suffix('.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(dict(output=str(output), sha256=manifest['sha256'], animations=len(gltf['animations']), frames=len(times))))


if __name__ == '__main__':
    main()
