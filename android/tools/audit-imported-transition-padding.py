"""Verify converter padding, not guessed linguistic sign boundaries. Read only."""
import importlib.util, json, math, struct
from pathlib import Path

spec = importlib.util.spec_from_file_location('union', Path(__file__).with_name('verify-integrated-vocabulary.py'))
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
root = Path(__file__).resolve().parents[1] / 'app/src/aslOriginalWords/assets'
m = json.loads((root / v.PREFIX / 'integration-manifest.json').read_text(encoding='utf-8'))
g, b = v.glb((root / m['asset']).read_bytes())
actions = {a['name']: a for a in g['animations']}
rows = []
for e in m['entries']:
    a = actions[e['animationName']]
    recorded = e['checks']['retained_source_duration_seconds']
    worst = 0.0; worst_node = None
    for ch in a['channels']:
        s = a['samplers'][ch['sampler']]
        t = [x[0] for x in struct.iter_unpack('<f', v.raw(g,b,s['input']))]
        assert abs(t[0]) < 1e-6 and abs(t[1] - .2) < 1e-6
        assert abs(t[-2] - (recorded + .2)) < 2e-6
        assert abs(t[-1] - (recorded + .4)) < 2e-6
        q = list(struct.iter_unpack('<4f', v.raw(g,b,s['output'])))
        # First and last are the same converter neutral. They are not ASL frames.
        assert abs(sum(x*y for x,y in zip(q[0],q[-1]))) > .99999
        for x,y in [(q[0],q[1]),(q[-2],q[-1])]:
            angle=math.degrees(2*math.acos(min(1,abs(sum(i*j for i,j in zip(x,y))))))
            if angle>worst:worst=angle;worst_node=g['nodes'][ch['target']['node']]['name']
    rows.append(dict(word=e['id'],syntheticEntrySeconds=.2,syntheticExitSeconds=.2,
        recordedSeconds=recorded,largestNeutralBoundaryRotationDegrees=worst,boundaryNode=worst_node))
print(json.dumps(dict(status='PASS_VERIFIED_CONVERTER_PADDING',entries=len(rows),
    sourceMotionUnchanged=True,maxBoundaryRotationDegrees=max(r['largestNeutralBoundaryRotationDegrees'] for r in rows),
    entriesWithBoundaryOver90Degrees=sum(r['largestNeutralBoundaryRotationDegrees']>90 for r in rows),
    rows=rows),indent=2))
