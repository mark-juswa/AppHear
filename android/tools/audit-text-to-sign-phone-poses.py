"""Compare debug phone finger transforms with actual glTF tracks; not ASL validation."""
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np

spec = importlib.util.spec_from_file_location('contact', Path(__file__).with_name('correct-text-to-sign-love.py'))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
model = c.hands.Model(sys.argv[1])
report = json.loads(Path(sys.argv[2]).read_text())
results = []
for sample in report['samples']:
    tracks = {(t['node'], t['path']): t for t in model.tracks(sample['name'])}
    errors = []
    for bone in sample['bones']:
        node = model.names[bone['name']]
        track = tracks.get((node, 'rotation'))
        expected = c.sample(track, sample['time']) if track else model.nodes[node].get('rotation', [0, 0, 0, 1])
        expected = np.asarray(expected) / np.linalg.norm(expected)
        actual = np.asarray(bone['q']) / np.linalg.norm(bone['q'])
        errors.append(float(np.degrees(2 * np.arccos(np.clip(abs(actual @ expected), 0, 1)))))
    target = next(a for a in sample['actions'] if a['name'] == sample['name'])
    others = [a for a in sample['actions'] if a['name'] != sample['name'] and a['enabled'] and a['weight'] > 1e-6]
    results.append(dict(label=sample['label'], action=sample['name'], maxFingerRotationErrorDegrees=max(errors),
                        effectiveWeight=target['weight'], interferingActions=others))
passed = all(r['maxFingerRotationErrorDegrees'] < .02 and r['effectiveWeight'] > .999 and not r['interferingActions'] for r in results)
output = dict(renderer=report['renderer'], samples=len(results), exactPoseGatePassed=passed,
              linguisticValidation=False, results=results)
Path(sys.argv[3]).write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps(dict(samples=len(results), passed=passed, maxRotationErrorDegrees=max(r['maxFingerRotationErrorDegrees'] for r in results)), indent=2))
if '--require-pass' in sys.argv[4:] and not passed:
    raise SystemExit('Phone did not reach source letter poses at full animation weight')
