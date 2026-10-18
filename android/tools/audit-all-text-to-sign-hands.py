"""Exhaustive current-bundle audit. Development only; never linguistic validation.

Uses actual glTF skinning and shortest-path SLERP. Warnings do not authorize
joint clamps or automatic handshape replacements. Run with OUTPUT directory.
"""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw

spec = importlib.util.spec_from_file_location('correction', Path(__file__).with_name('correct-text-to-sign-word-fingers.py'))
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
h = c.c.hands


def main():
    android = Path(__file__).resolve().parents[1]
    assets = android / 'app/src/aslOriginalWords/assets/asl_animations/original_words_v1'
    path = assets / 'fingerspelling-avatar.glb'
    model = h.Model(path)
    manifest = json.loads(path.with_suffix('.json').read_text())
    native = json.loads((assets / 'manifest.json').read_text())
    output = Path(sys.argv[1]); output.mkdir(parents=True, exist_ok=True)
    entries = native['replacements'] + native['newClips']
    entries = [dict(word=e['sourceName'], action=e['animationName'], asset=e['asset'], sourceSha256=e['sha256'], type='lexical') for e in entries]
    entries += [dict(word=e['id'].upper(), action=e['animationName'], asset=e['sourceAsset'], sourceSha256=e['sourceSha256'], type='lexical', note=e['meaning']) for e in manifest['wordAdditions']]
    entries += [dict(word=letter, action=f'SIGN_LETTER_{letter}_WOLF3D_PREVIEW', asset=str(path.relative_to(android / 'app/src/aslOriginalWords/assets')), type='letter') for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
    assert len(entries) == 232 and len({e['action'] for e in entries}) == 231
    assert model.bind_error < 1e-5 and model.weight_error < 1e-5
    # Explicit hierarchy check: every phalanx must follow its own finger, not
    # a neighbouring digit; each proximal phalanx is parented to the hand.
    hierarchy = []
    for side in ['Left', 'Right']:
        for finger in ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky']:
            for joint in range(1, 4):
                name = side + 'Hand' + finger + str(joint)
                parent = side + 'Hand' + (finger + str(joint - 1) if joint > 1 else '')
                assert model.parents[model.names[name]] == model.names[parent], (name, parent)
                hierarchy.append(dict(bone=name, parent=parent))
    results = {}; pages = []; page = None
    contact_mesh = c.c.ContactMesh(model)
    for index, action in enumerate(dict.fromkeys(e['action'] for e in entries)):
        tracks = model.tracks(action); duration = max(t['times'][-1] for t in tracks)
        targets = [(t['node'], t['path']) for t in tracks]
        assert len(targets) == len(set(targets)), action + ' duplicate target channel'
        for track in tracks:
            assert track['interpolation'] in ['LINEAR', 'STEP'], 'Unsupported CPU sampling mode'
            assert np.isfinite(track['values']).all() and np.all(np.diff(track['times']) > 0)
            if track['path'] == 'rotation':
                assert np.max(np.abs(np.linalg.norm(track['values'], axis=1) - 1)) < 1e-5
        rotations = {t['node']: t for t in tracks if t['path'] == 'rotation'}
        reverse = {}; worst_time = duration * .5; severity = 0.
        spans = {s: [] for s in ['Left', 'Right']}
        contact_depth = {'hand':0.,'forearm':0.}
        for sample_index, time in enumerate(np.linspace(0, duration, 17)):
            world = c.c.pose(model, tracks, float(time))
            # Broad screening only: front torso projection is not a closed-body
            # collision detector and cannot classify intentional ASL contact.
            if sample_index % 2 == 0:
                vertices = contact_mesh.skin(world)
                for side in ['Left','Right']:
                    for part,depths in contact_mesh.depths(vertices,side).items():
                        contact_depth[part]=max(contact_depth[part],float(max(0,depths.max())))
            for side in ['Left', 'Right']:
                spans[side].append(world[model.names[side + 'Hand']][:3, 3])
                bends = []
                for finger in ['Index', 'Middle', 'Ring', 'Pinky']:
                    node = model.names[side + 'Hand' + finger + '2']
                    assert node in rotations, (action, side, finger)
                    base = np.asarray(model.nodes[node].get('rotation', [0, 0, 0, 1]))
                    bends.append(float(c.delta(base, c.c.sample(rotations[node], float(time)))[0]))
                value = max(bends)
                if value < -.25:
                    reverse[side] = min(reverse.get(side, 0.), value)
                    if value < severity: severity = value; worst_time = float(time)
        world = c.c.pose(model, tracks, worst_time)
        if index % 12 == 0:
            page = Image.new('RGB', (880, 12 * 270), '#eef2f2'); pages.append(page)
        row = index % 12
        metrics = {}
        for side_index, side in enumerate(['Left', 'Right']):
            for view_index, axes in enumerate([(0, 1), (2, 1)]):
                cell = (220 * (side_index * 2 + view_index), row * 270)
                draw = ImageDraw.Draw(page)
                metric = h.render(draw, model, world, side, cell, axes=axes, bones=True)
                draw.text((cell[0]+4, cell[1]+4), action.replace('SIGN_', '')[:31], fill='black')
                draw.text((cell[0]+4, cell[1]+20), f'{side} t={worst_time:.2f} / {duration:.2f}', fill='black')
                if view_index == 0: metrics[side] = metric
        results[action] = dict(durationSeconds=duration, sampledPoses=17, finiteUnitQuaternions=True,
                               uniqueTargetChannels=True, reverseFlexionWarnings=reverse,
                               renderedTime=worst_time, handMeshMetrics=metrics,
                               wristSpanMeters={s: np.ptp(spans[s], axis=0).tolist() for s in spans},
                               contactSheet=f'all-hands-{index//12+1:02d}.png',
                               maxFrontSurfaceDepthMeters=contact_depth,contactSamples=9,
                               contactStatus='Front-torso proxy only; intentional contact, back-side signs, clothing and full collision require inspection',
                               qualifiedAslValidation=False)
        if (index + 1) % 12 == 0 or index == 230:
            page.save(output / f'all-hands-{index//12+1:02d}.png')
            print(f'Inspected {index+1}/231 actions', flush=True)
    for entry in entries:
        action = entry['action']; result = results[action]
        assert (android / 'app/src/aslOriginalWords/assets' / entry['asset']).is_file() or (android / 'app/src/main/assets' / entry['asset']).is_file()
        entry.update(animationExists=True, selectedHumanOnly=True, technical=result,
                     status='Needs correction / sign-specific review' if result['reverseFlexionWarnings'] else 'Technically sampled; requires ASL validation')
    report = dict(schemaVersion=1, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  renderer='CPU actual glTF mesh skinning with SLERP; not Android/WebGL',
                  lexicalEntries=206, distinctLexicalActions=205, alphabetLetters=26,
                  qualifiedAslValidations=0, newVocabulary=0, bindMatrixError=model.bind_error,
                  weightSumError=model.weight_error, hierarchy=hierarchy, entries=entries,
                  disclaimer='Finite rotations and skin checks do not prove intended handshape, sign meaning or absence of intersections.')
    (output / 'all-hands-inventory.json').write_text(json.dumps(report, indent=2)+'\n')
    with (output / 'all-hands-inventory.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f); writer.writerow(['Word','Type','Action','Animation exists','Finger issue','Technical correction','ASL validation status','Contact sheet'])
        corrected = {p['animationName'] for p in manifest['wordFingerCorrection']['profiles']}
        new_corrected = {p['animationName'] for p in manifest.get('flatBaseHandCorrection',{}).get('profiles',[])}
        for entry in entries:
            result = entry['technical']
            writer.writerow([entry['word'],entry['type'],entry['action'],True,
                             json.dumps(result['reverseFlexionWarnings']) if result['reverseFlexionWarnings'] else 'No four-finger reverse-bend signature detected; not an accuracy pass',
                             'Reference-guided flat base hand repair' if entry['action'] in new_corrected else 'Prior scoped repair retained' if entry['action'] in corrected else 'Unchanged; audit only',
                             'Requires ASL validation',result['contactSheet']])
    print(json.dumps(dict(entries=len(entries), actions=len(results), warningActions=[a for a,r in results.items() if r['reverseFlexionWarnings']]), indent=2))


if __name__ == '__main__': main()
