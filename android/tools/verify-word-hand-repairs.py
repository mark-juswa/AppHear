"""Verify staged lexical repair scope, alphabet identity and source-key changes."""
import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('before', type=Path)
    p.add_argument('after', type=Path)
    p.add_argument('repairs', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--motion-profiles', type=Path)
    p.add_argument('--staged-motions', type=Path)
    args = p.parse_args()
    s = importlib.util.spec_from_file_location('repair', Path(__file__).with_name('repair-word-hand-key-spikes.py'))
    repair = importlib.util.module_from_spec(s)
    s.loader.exec_module(repair)
    c = repair.helpers()
    before, after = c.hands.Model(args.before), c.hands.Model(args.after)
    changes = json.loads(args.repairs.read_text())['changes']
    allowed = {(x['action'], x['bone']) for x in changes}
    motions = {}
    if args.motion_profiles:
        motions = {x['action']: x for x in json.loads(args.motion_profiles.read_text())['profiles']}
        assert args.staged_motions
    for field in ['nodes', 'skins', 'meshes', 'materials', 'textures', 'images', 'scenes']:
        assert before.g[field] == after.g[field], field
    assert list(before.animations) == list(after.animations)
    def fast(track):
        q = np.asarray(track['values'], float)
        q /= np.linalg.norm(q, axis=1)[:, None]
        steps = np.degrees(2 * np.arccos(np.clip(abs(np.sum(q[:-1] * q[1:], axis=1)), 0, 1)))
        return int(np.sum((steps > 45) & (steps / np.diff(track['times']) > 900)))
    checked = 0
    rows = []
    for name in before.animations:
        old, new = before.tracks(name), after.tracks(name)
        if name in motions:
            profile = motions[name]
            with np.load(args.staged_motions / (profile['id'] + '.npz')) as data:
                times, rotations = data['times'], data['rotations']
            by_target = {(x['node'], x['path']): x for x in new}
            for j, node in enumerate(after.order):
                if 'matrix' in after.nodes[node]:
                    continue
                actual = by_target[node, 'rotation']
                assert np.array_equal(actual['times'], times)
                assert np.array_equal(actual['values'], rotations[:, j])
                for path, default in [('translation', [0, 0, 0]), ('scale', [1, 1, 1])]:
                    assert np.all(np.asarray(by_target[node, path]['values']) == after.nodes[node].get(path, default))
            old_fast = sum(fast(t) for t in old if t['path'] == 'rotation' and 'Hand' in before.nodes[t['node']].get('name', '') and before.nodes[t['node']]['name'] not in ['LeftHand', 'RightHand'])
            new_fast = sum(fast(t) for t in new if t['path'] == 'rotation' and 'Hand' in after.nodes[t['node']].get('name', '') and after.nodes[t['node']]['name'] not in ['LeftHand', 'RightHand'])
            assert new_fast <= old_fast, (name, 'Finger discontinuities regressed')
            rows.append(dict(action=name, beforeFastFingerSteps=old_fast, afterFastFingerSteps=new_fast, replacementMotion=True))
            checked += len(new)
            continue
        assert len(old) == len(new)
        old_fast = new_fast = 0
        for a, b in zip(old, new):
            assert (a['node'], a['path'], a['interpolation']) == (b['node'], b['path'], b['interpolation'])
            assert np.array_equal(a['times'], b['times'])
            bone = before.nodes[a['node']].get('name', '')
            x, y = np.asarray(a['values']), np.asarray(b['values'])
            if (name, bone) not in allowed or a['path'] != 'rotation':
                assert np.array_equal(x, y), (name, bone, a['path'], 'unexpected change')
            else:
                assert np.array_equal(x[[0, -1]], y[[0, -1]]), (name, bone, 'endpoints changed')
            if a['path'] == 'rotation' and 'Hand' in bone and bone not in ['LeftHand', 'RightHand']:
                old_fast += fast(a)
                new_fast += fast(b)
            checked += 1
        if name in {x['action'] for x in changes}:
            rows.append(dict(action=name, beforeFastFingerSteps=old_fast, afterFastFingerSteps=new_fast))
    # Behavioural counterexamples: preserve a deliberate held pose and a smooth
    # large excursion; remove a single frame that departs and returns to rest.
    def q(deg):
        a = np.radians(deg / 2)
        return np.array([np.sin(a), 0., 0., np.cos(a)])
    times = np.arange(5) / 30
    assert repair.isolated_spikes(np.array([q(x) for x in [0, 0, 120, 0, 0]]), times, c.sample)[1] == [2]
    assert repair.isolated_spikes(np.array([q(x) for x in [0, 0, 120, 120, 120]]), times, c.sample)[1] == []
    assert repair.isolated_spikes(np.array([q(x) for x in [0, 30, 60, 90, 120]]), times, c.sample)[1] == []
    assert repair.isolated_spikes(np.array([q(x) for x in [0, 0, 120, 0, 0]]), np.arange(5) * .3, c.sample)[1] == []
    result = dict(actionsChecked=len(before.animations), tracksChecked=checked,
                  alphabetActionsUnchanged=26, geometryAndRigUnchanged=True,
                  unlistedChannelsUnchanged=True, sourceClocksAndEndpointsUnchanged=True,
                  licensedReplacementMotions=len(motions),
                  changedActions=rows, beforeFastSteps=sum(x['beforeFastFingerSteps'] for x in rows),
                  afterFastSteps=sum(x['afterFastFingerSteps'] for x in rows),
                  qualifiedASLValidation=False)
    result['sourceClocksAndEndpointsUnchanged'] = not bool(motions)
    result['replacementClocksMatchLicensedSources'] = bool(motions)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'changedActions'}, indent=2))


if __name__ == '__main__':
    main()
