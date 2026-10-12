"""Exact repair-boundary and real skinned mesh checks, not ASL validation."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

spec = importlib.util.spec_from_file_location('repair', Path(__file__).with_name('correct-closed-fist-text-to-sign-hands.py'))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def main() -> None:
    before, after = [c.p.c.hands.Model(Path(x)) for x in sys.argv[1:3]]
    output = Path(sys.argv[3])
    assert before.binary[:before.g['buffers'][0]['byteLength']] == after.binary[:before.g['buffers'][0]['byteLength']]
    for key in ['nodes', 'skins', 'meshes', 'materials', 'textures', 'images', 'scenes']:
        assert before.g[key] == after.g[key]
    report = dict(qualifiedASLValidation=False, unchangedActions=0, profiles=[])
    for old, new in zip(before.g['animations'], after.g['animations']):
        name = old['name']
        if name not in c.PROFILES:
            assert old == new
            report['unchangedActions'] += 1
            continue
        allowed = {s+'Hand'+f+str(j) for s, f in c.PROFILES[name] for j in [1, 2, 3]}
        changed = set()
        for a, b in zip(old['channels'], new['channels']):
            assert a['target'] == b['target']
            if a == b:
                continue
            changed.add(before.nodes[a['target']['node']]['name'])
            os, ns = old['samplers'][a['sampler']], new['samplers'][b['sampler']]
            assert os['input'] == ns['input']
            assert np.max(np.abs(before.data(os['output'])[[0,-1]] - after.data(ns['output'])[[0,-1]])) < 1e-6
        assert changed == allowed
        tracks = after.tracks(name)
        duration = max(t['times'][-1] for t in tracks)
        matrix_error = 0.
        for time in np.linspace(0, duration, 61):
            ow = c.p.c.pose(before, before.tracks(name), float(time))
            nw = c.p.c.pose(after, tracks, float(time))
            for side in ['Left', 'Right']:
                for part in ['Shoulder', 'Arm', 'ForeArm', 'Hand']:
                    node = after.names[side+part]
                    matrix_error = max(matrix_error, float(np.max(np.abs(ow[node]-nw[node]))))
        assert matrix_error == 0
        image = Image.new('RGB', (880,540), '#eef2f2')
        draw = ImageDraw.Draw(image)
        metrics = {}
        for row, side in enumerate(['Left', 'Right']):
            for column, model in enumerate([before, after]):
                world = c.p.c.pose(model, model.tracks(name), duration*.4)
                for view, axes in enumerate([(0,1),(2,1)]):
                    cell = (220*(2*column+view),270*row)
                    metric = c.p.c.hands.render(draw, model, world, side, cell, axes=axes, bones=True)
                    draw.text((cell[0]+4,cell[1]+4), ('BEFORE ' if column==0 else 'AFTER ')+name+' '+side, fill='black')
                    if view==0:
                        metrics[side+('Before' if column==0 else 'After')] = metric
        image.save(output/(name.lower()+'-closed-fist-before-after.png'))
        report['profiles'].append(dict(action=name, changedChannels=len(changed), armWristMatrixError=matrix_error, sampledPoses=61, meshMetrics=metrics))
    assert report['unchangedActions']==230
    (output/'closed-fist-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
