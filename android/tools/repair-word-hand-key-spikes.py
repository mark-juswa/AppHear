"""Stage conservative lexical finger repairs; never constrain the live skeleton.

An isolated >65 degree excursion that returns to neighbours within 25 degrees
in <=100 ms is interpolated between those existing anchors. Consecutive suspect
keys and endpoints are excluded. Sustained handshapes, wrist/arm trajectories,
idle and every alphabet action are preserved. Explicit reference-guided flat
and closed-hand profiles address separately confirmed articulation failures.
The output remains a technical preview pending qualified ASL review.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

import numpy as np


def helpers():
    spec = importlib.util.spec_from_file_location('contact', Path(__file__).with_name('correct-text-to-sign-love.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def angle(a, b):
    return float(np.degrees(2 * np.arccos(np.clip(abs(a @ b), 0, 1))))


def isolated_spikes(values, times, sample):
    """Remove only return-to-pose outliers; do not low-pass a complete sign."""
    q = np.array(values, dtype=float)
    q /= np.linalg.norm(q, axis=1)[:, None]
    candidates = set()
    for i in range(1, len(q) - 1):
        if times[i + 1] - times[i - 1] > .100001:
            continue
        if (min(angle(q[i - 1], q[i]), angle(q[i], q[i + 1])) > 65
                and angle(q[i - 1], q[i + 1]) < 25):
            candidates.add(i)
    # Adjacent outliers have no independently trusted anchor: leave for review.
    indices = sorted(i for i in candidates if i - 1 not in candidates and i + 1 not in candidates)
    out = np.array(values, dtype=float)
    for i in indices:
        out[i] = sample(dict(path='rotation', interpolation='LINEAR',
                             times=[times[i - 1], times[i + 1]],
                             values=[q[i - 1], q[i + 1]]), times[i])
    return out, indices


def write_bundle(g, binary):
    g['buffers'][0]['byteLength'] = len(binary)
    encoded = json.dumps(g, separators=(',', ':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    binary += b'\0' * (-len(binary) % 4)
    return (struct.pack('<III', 0x46546c67, 2, 28 + len(encoded) + len(binary))
            + struct.pack('<II', len(encoded), 0x4e4f534a) + encoded
            + struct.pack('<II', len(binary), 0x004e4942) + binary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    assert args.output.resolve() != args.source.resolve(), 'Stage a candidate before applying it'
    c = helpers()
    config = json.loads(Path(__file__).with_name('word-hand-repair-profiles.json').read_text())
    source_sha = hashlib.sha256(args.source.read_bytes()).hexdigest()
    assert source_sha == config['sourceSha256'], 'Unknown baseline: audit before editing'
    m = c.hands.Model(args.source)
    root = Path(__file__).resolve().parents[2]
    import csv
    entries = list(csv.DictReader((root / 'COMBINED_NEW_VOCABULARY.csv').open(encoding='utf-8-sig')))
    lexical = {e['AnimationAction'] for e in entries}
    profiles = {p['action']: p for p in config['profiles']}
    donor = {t['node']: t for t in m.tracks('SIGN_YES') if t['path'] == 'rotation'}
    donor_time = .4 * max(t['times'][-1] for t in donor.values())
    g = copy.deepcopy(m.g)
    binary = bytearray(m.binary[:g['buffers'][0]['byteLength']])
    uses = {}
    for animation in g['animations']:
        for sampler in animation['samplers']:
            uses[sampler['output']] = uses.get(sampler['output'], 0) + 1
    changed = []
    for animation in g['animations']:
        action = animation['name']
        if action not in lexical:
            continue
        profile = profiles.get(action, {})
        for channel in animation['channels']:
            node = channel['target']['node']
            name = m.nodes[node].get('name', '')
            if (channel['target']['path'] != 'rotation' or 'Hand' not in name
                    or name in ['LeftHand', 'RightHand'] or not name.endswith(('1', '2', '3'))):
                continue
            sampler = animation['samplers'][channel['sampler']]
            original = m.data(sampler['output'])
            times = m.data(sampler['input']).flatten()
            values, indices = isolated_spikes(original, times, c.sample)
            side = 'Left' if name.startswith('Left') else 'Right'
            thumb = 'Thumb' in name
            fixed = None
            reason = 'ISOLATED_RETURN_TO_POSE_SPIKE'
            if ((side in profile.get('flatSides', []) and not thumb)
                    or (side in profile.get('straightThumbSides', []) and thumb)):
                fixed = np.array(m.nodes[node].get('rotation', [0, 0, 0, 1]), dtype=float)
                reason = 'REFERENCE_GUIDED_FLAT_HAND'
            elif side in profile.get('fistSides', []) and not thumb:
                assert side == 'Right', 'Mirror through rest frames before using a left donor'
                fixed = c.sample(donor[node], donor_time)
                reason = 'REFERENCE_GUIDED_CLOSED_FINGERS_EXISTING_YES'
            if fixed is not None:
                for i, time in enumerate(times):
                    u = np.clip(min(float(time), float(times[-1] - time)) / .18, 0, 1)
                    weight = u * u * (3 - 2 * u)
                    values[i] = c.sample(dict(path='rotation', interpolation='LINEAR',
                                             times=[0., 1.], values=[original[i], fixed]), weight)
            values = np.asarray(values, dtype='<f4')
            values[0], values[-1] = original[0], original[-1]
            if np.array_equal(values, original):
                continue
            # Do not rewrite channels just because float64 normalization differs.
            if not indices and fixed is None:
                continue
            assert np.max(abs(np.linalg.norm(values, axis=1) - 1)) < 1e-5
            accessor_id = sampler['output']
            accessor = g['accessors'][accessor_id]
            view = g['bufferViews'][accessor['bufferView']]
            if uses[accessor_id] == 1 and view.get('byteStride', 16) == 16:
                offset = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
                binary[offset:offset + values.nbytes] = values.tobytes()
                if 'min' in accessor:
                    accessor['min'] = values.min(0).tolist()
                if 'max' in accessor:
                    accessor['max'] = values.max(0).tolist()
            else:
                while len(binary) % 4:
                    binary.append(0)
                view_id = len(g['bufferViews'])
                g['bufferViews'].append(dict(buffer=0, byteOffset=len(binary), byteLength=values.nbytes))
                binary.extend(values.tobytes())
                accessor_id = len(g['accessors'])
                g['accessors'].append(dict(bufferView=view_id, componentType=5126, count=len(values), type='VEC4'))
                sampler['output'] = accessor_id
            changed.append(dict(action=action, bone=name, reason=reason,
                                repairedKeyIndices=indices,
                                reference=profile.get('reference'),
                                maximumChangeDegrees=max(angle(a / np.linalg.norm(a), b / np.linalg.norm(b))
                                                         for a, b in zip(original, values))))
    payload = write_bundle(g, binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    report = dict(sourceSha256=source_sha, candidateSha256=hashlib.sha256(payload).hexdigest(),
                  changedActions=len({e['action'] for e in changed}), changedChannels=len(changed),
                  changes=changed, qualifiedASLValidation=False,
                  method='Isolated return-to-pose key repair plus explicit reference-guided hand profiles; no global constraints')
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'changes'}, indent=2))


if __name__ == '__main__':
    main()
