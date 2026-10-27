"""Stage explicit, source-attributed replacement motions on the resident human.

Input caches come from the pinned anatomical-frame converter and separately
reviewed selection report. Action names and vocabulary stay fixed. Never writes
the installed source asset; apply only after parity and rendered review.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('candidate', type=Path)
    p.add_argument('staged', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('report', type=Path)
    a = p.parse_args()
    assert a.output.resolve() != a.candidate.resolve()
    spec = importlib.util.spec_from_file_location('keys', Path(__file__).with_name('repair-word-hand-key-spikes.py'))
    keys = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(keys)
    c = keys.helpers()
    m = c.hands.Model(a.candidate)
    g = copy.deepcopy(m.g)
    binary = bytearray(m.binary[:g['buffers'][0]['byteLength']])
    config = json.loads(Path(__file__).with_name('word-motion-replacement-profiles.json').read_text())
    profiles = config['profiles']
    cache = {}
    def accessor(values, kind):
        values = np.asarray(values, dtype='<f4')
        assert np.isfinite(values).all()
        key = (kind, len(values), values.tobytes())
        if key in cache:
            return cache[key]
        binary.extend(b'\0' * (-len(binary) % 4))
        view = len(g['bufferViews'])
        g['bufferViews'].append(dict(buffer=0, byteOffset=len(binary), byteLength=values.nbytes))
        binary.extend(values.tobytes())
        i = len(g['accessors'])
        item = dict(bufferView=view, componentType=5126, count=len(values), type=kind)
        if kind == 'SCALAR':
            item.update(min=[float(values.min())], max=[float(values.max())])
        g['accessors'].append(item)
        cache[key] = i
        return i
    for profile in profiles:
        name = profile['action']
        index = next(i for i, x in enumerate(g['animations']) if x['name'] == name)
        data = np.load(a.staged / (profile['id'] + '.npz'))
        times, rotations = data['times'], data['rotations']
        assert rotations.shape == (len(times), len(m.order), 4)
        assert np.max(abs(np.linalg.norm(rotations, axis=2) - 1)) < 1e-5
        assert np.all(np.diff(times) > 0)
        assert round(float(times[-1]) * 1000) == profile['durationMs']
        meta = json.loads((a.staged / (profile['id'] + '.json')).read_text())
        assert meta['sourceSha256'] == profile['sourceSha256']
        clock = accessor(times, 'SCALAR')
        endpoints = accessor([0., float(times[-1])], 'SCALAR')
        action = dict(name=name, samplers=[], channels=[])
        for j, node_id in enumerate(m.order):
            node = m.nodes[node_id]
            if 'matrix' in node:
                continue
            for path, values, kind, inp in [
                ('rotation', rotations[:, j], 'VEC4', clock),
                ('translation', [node.get('translation', [0, 0, 0])] * 2, 'VEC3', endpoints),
                ('scale', [node.get('scale', [1, 1, 1])] * 2, 'VEC3', endpoints)
            ]:
                sampler = len(action['samplers'])
                action['samplers'].append(dict(input=inp, output=accessor(values, kind), interpolation='LINEAR'))
                action['channels'].append(dict(sampler=sampler, target=dict(node=node_id, path=path)))
        g['animations'][index] = action
    payload = keys.write_bundle(g, binary)
    a.output.write_bytes(payload)
    report = dict(sourceCandidateSha256=hashlib.sha256(a.candidate.read_bytes()).hexdigest(),
                  sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload),
                  profiles=profiles, actionNamesAndVocabularyUnchanged=True,
                  qualifiedASLValidation=False)
    a.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'profiles'}, indent=2))


if __name__ == '__main__':
    main()
