"""Stage exact-ID replacements only; never add vocabulary or alter original assets."""
from pathlib import Path
import argparse
import hashlib
import json
import math

REPO = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--batch', type=Path, default=Path('G:/3d Characters/optimized_apphear3_batch'))
parser.add_argument('--plan', action='store_true')
args = parser.parse_args()
original = json.loads((REPO / 'android/app/src/main/assets/asl_animations/manifest.json').read_text())['clips']
summary = json.loads((args.batch / 'reports/batch-summary.json').read_text())
inventory = json.loads((REPO / 'artifacts/text_to_asl_asset_assessment_20260928/inventory.json').read_text())['new']
records = {entry['id']: entry for entry in summary['completed']}
assert len(records) == len(summary['completed']), 'Duplicate source IDs'
inventory_by_hash = {entry['sha256']: entry for entry in inventory}
clips, payloads = [], {}
for base in original:
    identity = base['id'].upper()
    if identity not in records or base['type'] not in ('letter', 'word'):
        continue
    record = records[identity]
    assert Path(record['source']).stem.upper() == identity, 'Source ID/path mismatch'
    assert record['decodedDataAndOrientedTopologyExact'] and record['validationErrors'] == 0
    source = inventory_by_hash[record['sourceSha256']]
    assert len(source['animations']) == 1
    animation = source['animations'][0]
    duration = math.ceil(animation['end'] * 1000)
    assert 1 <= duration <= 10_000
    asset = 'asl_animations/vnext/' + base['id'] + '.glb'
    clips.append({'id': base['id'], 'sourceId': identity, 'asset': asset,
                  'fallbackAsset': base['asset'], 'animationName': animation['name'],
                  'durationMs': duration, 'sha256': record['sha256'],
                  'profile': 'balanced-ktx2mixed-meshopt-v1',
                  'rigProfile': 'FemaleASL-full-rig-341-875-342'})
    if not args.plan:
        data = Path(record['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == record['sha256'], identity + ' output checksum mismatch'
        assert hashlib.sha256(Path(record['source']).read_bytes()).hexdigest() == record['sourceSha256'], identity + ' source changed'
        payloads[asset] = data
result = {'schemaVersion': 1, 'clips': clips}
if args.plan:
    print(json.dumps({'replacements': [c['id'] for c in clips],
                      'unmappedSourceIds': sorted(set(records) - {c['sourceId'] for c in clips})}, indent=2))
else:
    target = REPO / 'android/app/src/aslPilot/assets'
    existing = {str(p.relative_to(target)).replace('\\', '/')
                for p in (target / 'asl_animations/vnext').glob('*.glb')}
    assert existing <= set(payloads), 'Unreferenced pilot GLBs: archive/review before staging'
    # Verify every input and existing derivative before making any change.
    for asset, data in payloads.items():
        destination = target / asset
        if destination.exists():
            assert destination.read_bytes() == data, 'Refusing to overwrite different derivative: ' + asset
    for asset, data in payloads.items():
        destination = target / asset
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(data)
    manifest = target / 'asl_animations/vnext/manifest.json'
    temporary = manifest.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result, indent=2))
    temporary.replace(manifest)
    print('Staged exact-ID replacements:', ', '.join(c['id'] for c in clips))
    print('Original catalog unchanged; unmatched source signs are not added.')
