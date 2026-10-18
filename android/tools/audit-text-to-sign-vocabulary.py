"""Check vocabulary expansion against the retained APK; no ASL accuracy claims."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import zipfile
import numpy as np

spec = importlib.util.spec_from_file_location('hands', Path(__file__).with_name('audit-text-to-sign-hands.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def document(payload):
    length = struct.unpack_from('<I', payload, 12)[0]
    gltf = json.loads(payload[20:20+length])
    binary = payload[28+length:]
    return gltf, binary


def main():
    baseline_apk, new_apk, output = map(Path, sys.argv[1:4])
    path = 'assets/asl_animations/original_words_v1/fingerspelling-avatar.glb'
    with zipfile.ZipFile(baseline_apk) as z:
        old = z.read(path)
    with zipfile.ZipFile(new_apk) as z:
        new = z.read(path)
        manifest = json.loads(z.read(path.replace('.glb', '.json')))
    before, before_bin = document(old)
    after, after_bin = document(new)
    assert len(before['animations']) == 230 and len(after['animations']) == 232
    for key in ['nodes', 'skins', 'meshes', 'materials', 'textures', 'images', 'scenes']:
        assert before[key] == after[key], key
    assert before['animations'] == after['animations'][:230]
    assert before_bin[:before['buffers'][0]['byteLength']] == after_bin[:before['buffers'][0]['byteLength']]
    assert hashlib.sha256(new).hexdigest() == manifest['sha256']
    # APK assets/resources must stay identical outside the three declared vocabulary files.
    allowed = {path, path.replace('.glb', '.json'), 'assets/asl_animations/existing_aliases_asl.json'}
    with zipfile.ZipFile(baseline_apk) as a, zipfile.ZipFile(new_apk) as b:
        ap = {p for p in a.namelist() if p.startswith(('assets/', 'res/'))}
        bp = {p for p in b.namelist() if p.startswith(('assets/', 'res/'))}
        assert ap == bp
        changed = [p for p in sorted(ap) if hashlib.sha256(a.read(p)).digest() != hashlib.sha256(b.read(p)).digest()]
        assert set(changed) == allowed, changed
    android = Path(__file__).resolve().parents[1]
    target_path = android / 'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb'
    model = h.Model(target_path)
    checks = []
    for entry in manifest['wordAdditions']:
        tracks = model.tracks(entry['animationName'])
        duration = max(c['times'][-1] for c in tracks)
        for c in tracks:
            assert np.isfinite(c['values']).all()
            assert np.all(np.diff(c['times']) > 0)
            if c['path'] == 'rotation':
                assert np.max(np.abs(np.linalg.norm(c['values'], axis=1)-1)) < 1e-5
        positions = []
        for t in np.linspace(.3, duration-.3, 61):
            w = model.pose(tracks, float(t))
            positions.append(w[model.names['RightHand']][:3, 3].tolist())
        checks.append(dict(id=entry['id'], namedAction=entry['animationName'], finiteQuaternionData=True,
                           samples=61, rightWristSpanMeters=np.ptp(positions, axis=0).tolist(), qualifiedAslValidation=False))
    report = dict(originalActionsPreserved=230, namedActions=232, wordEntriesAdded=3, newMotionActions=2,
                  newAlternativeForms=['mom', 'mum', 'dad', 'okay'], qualifiedAslValidations=0,
                  originalGeometryAndBinaryTracksPreserved=True, resourcePaths=len(ap), changedResourcePaths=changed,
                  apkSha256=hashlib.sha256(new_apk.read_bytes()).hexdigest(), checks=checks,
                  devicePlayback='Not run: no connected phone/emulator', grammar='No new validated sentence translation',
                  rejectedCandidate='AGAIN retarget: hand contact unresolved; not registered or packaged')
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
