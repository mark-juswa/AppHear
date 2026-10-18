"""Reuse the same rig's YES finger articulation in two explicit preview repairs.

No global constraints. LOVE keeps its crossed arms; I/ME keeps its
pointing index. Alphabet, YES, meshes, weights and all other clips stay
byte-identical. Left-hand articulation is mirrored through actual rest frames.
Qualified ASL review is still required.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

import numpy as np

spec = importlib.util.spec_from_file_location('prior', Path(__file__).with_name('correct-text-to-sign-word-fingers.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
BASELINES = {
    '292914132fa3ec325206ac65c347691709364566870a521230187949b46d3bfd',
    '266a7dff1531221ef4482d8ed6242ac9f3cab9fde2f92ebb1f71d82020e14554',
}
PROFILES = {
    'SIGN_LOVE': [('Left', f) for f in ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky']] + [('Right', f) for f in ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky']],
    'SIGN_I': [('Right', f) for f in ['Thumb', 'Middle', 'Ring', 'Pinky']],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    android = Path(__file__).resolve().parents[1]
    target = android / 'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb'
    manifest = json.loads(target.with_suffix('.json').read_text())
    if manifest.get('closedFistCorrection', {}).get('profileVersion') == 2:
        print('Closed-fist correction already applied; no changes')
        return
    source_sha = hashlib.sha256(target.read_bytes()).hexdigest()
    assert source_sha == manifest['sha256'] and source_sha in BASELINES
    assert args.apply != bool(args.output), 'Choose either --output candidate or --apply'
    model = p.c.hands.Model(target)
    rest = p.c.r.world(model.nodes, model.parents, model.order)
    donor = model.tracks('SIGN_YES')
    donor_time = .4 * max(t['times'][-1] for t in donor)
    donor_by_node = {t['node']: t for t in donor if t['path'] == 'rotation'}
    g = copy.deepcopy(model.g)
    binary = bytearray(model.binary[:g['buffers'][0]['byteLength']])
    profiles = []
    for name, fingers in PROFILES.items():
        animation = next(a for a in g['animations'] if a['name'] == name)
        allowed = {side + 'Hand' + f + str(j) for side, f in fingers for j in [1, 2, 3]}
        changed = []
        for channel in animation['channels']:
            node = channel['target']['node']
            bone = model.nodes[node].get('name', '')
            if channel['target']['path'] != 'rotation' or bone not in allowed:
                continue
            right = model.names[bone.replace('Left', 'Right')]
            fixed = p.c.sample(donor_by_node[right], donor_time)
            if bone.startswith('Left'):
                # Mirror the bind-relative rotation, not absolute quaternions:
                # left/right local axes and rest orientations are different.
                rb = np.asarray(model.nodes[right].get('rotation', [0, 0, 0, 1]))
                lb = np.asarray(model.nodes[node].get('rotation', [0, 0, 0, 1]))
                d = p.c.r.rotation(p.delta(rb, fixed))
                rr, lr = p.c.r.orient(rest[right]), p.c.r.orient(rest[node])
                mirror = np.diag([-1., 1., 1.])
                mapped = lr.T @ mirror @ rr @ d @ rr.T @ mirror @ lr
                fixed = p.c.r.unit(p.multiply(lb, p.c.r.quaternion(mapped)))
            sampler = animation['samplers'][channel['sampler']]
            times = model.data(sampler['input']).flatten()
            source = model.data(sampler['output'])
            values = []
            for time, q in zip(times, source):
                u = min(1., max(0., min(float(time), float(times[-1] - time)) / .18))
                weight = u * u * (3 - 2 * u)
                values.append(p.c.sample(dict(path='rotation', interpolation='LINEAR', times=[0., 1.], values=[q, fixed]), weight))
            values = np.asarray(values, dtype='<f4')
            for j in range(1, len(values)):
                if np.dot(values[j-1], values[j]) < 0:
                    values[j] = -values[j]
            # q and -q represent the same rotation. Keep the exact source
            # endpoint encodings too; glTF SLERP resolves the sign on release.
            values[0], values[-1] = source[0], source[-1]
            assert np.max(np.abs(np.linalg.norm(values, axis=1) - 1)) < 1e-5
            while len(binary) % 4:
                binary.append(0)
            view = len(g['bufferViews'])
            g['bufferViews'].append(dict(buffer=0, byteOffset=len(binary), byteLength=values.nbytes))
            binary.extend(values.tobytes())
            accessor = len(g['accessors'])
            g['accessors'].append(dict(bufferView=view, componentType=5126, count=len(values), type='VEC4'))
            index = len(animation['samplers'])
            animation['samplers'].append(dict(input=sampler['input'], output=accessor, interpolation=sampler.get('interpolation', 'LINEAR')))
            channel['sampler'] = index
            changed.append(bone)
        assert set(changed) == allowed
        profiles.append(dict(animationName=name, correctedNodes=changed))
    for key in ['nodes', 'skins', 'meshes', 'materials', 'textures', 'images', 'scenes']:
        assert g[key] == model.g[key]
    assert [a for a in g['animations'] if a['name'] not in PROFILES] == [a for a in model.g['animations'] if a['name'] not in PROFILES]
    g['buffers'][0]['byteLength'] = len(binary)
    encoded = json.dumps(g, separators=(',', ':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    binary += b'\0' * (-len(binary) % 4)
    payload = struct.pack('<III', 0x46546c67, 2, 28+len(encoded)+len(binary)) + struct.pack('<II', len(encoded), 0x4e4f534a) + encoded + struct.pack('<II', len(binary), 0x004e4942) + binary
    sha = hashlib.sha256(payload).hexdigest()
    if args.output:
        args.output.write_bytes(payload)
    else:
        target.write_bytes(payload)
        manifest['sha256'] = sha
        manifest['closedFistCorrection'] = dict(profileVersion=2, sourceSha256=source_sha, donorAnimation='SIGN_YES', donorTimeSeconds=donor_time, profiles=profiles,
            qualifiedASLValidation=False, method='Scoped existing YES finger/thumb articulation; rest-frame left-hand mirroring; 180ms entry/release; source timestamps/endpoints retained; ME index, wrists/arms/body and all other actions unchanged',
            references=['https://www.lifeprint.com/asl101/pages-signs/l/love.htm', 'https://www.lifeprint.com/asl101/pages-signs/m/me.htm', 'https://www.lifeprint.com/asl101/pages-signs/y/yes.htm'])
        target.with_suffix('.json').write_text(json.dumps(manifest, indent=2)+'\n')
        loader = android / 'app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt'
        text = loader.read_text()
        assert source_sha in text
        loader.write_text(text.replace(source_sha, sha))
    print(json.dumps(dict(sha256=sha, profiles=profiles), indent=2))


if __name__ == '__main__':
    main()
