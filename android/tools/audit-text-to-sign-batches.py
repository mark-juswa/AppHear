"""Inventory requested words against actual single-avatar assets; not ASL validation."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct

BATCHES = [
    "NAME MY YOUR YOU ME WHAT WHO HOW HELLO GOODBYE NICE MEET FRIEND PERSON DEAF HEARING",
    "YES NO PLEASE THANK_YOU SORRY HELP NEED WANT UNDERSTAND KNOW REPEAT WAIT STOP GO COME WHERE",
    "HAPPY SAD TIRED HUNGRY THIRSTY SICK GOOD BAD OKAY HOT COLD FEEL LOVE LIKE",
    "EAT DRINK SLEEP WORK STUDY LEARN READ WRITE WALK SIT STAND HOME SCHOOL FOOD WATER",
    "TODAY TOMORROW YESTERDAY NOW LATER TIME MORNING AFTERNOON NIGHT WEATHER RAIN SUNNY WIND WHEN WHY WHICH",
]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    android = Path(__file__).resolve().parents[1]
    assets = android / 'app/src/aslOriginalWords/assets'
    manifest = json.loads((assets / 'asl_animations/original_words_v1/manifest.json').read_text())
    base_bytes = (android / 'app/src/main/assets/asl_animations/manifest.json').read_bytes()
    assert hashlib.sha256(base_bytes).hexdigest() == manifest['baseManifestSha256']
    base = {e['id']: e for e in json.loads(base_bytes)['clips']}
    entries = [dict(base[e['id']], **e) for e in manifest['replacements']] + manifest['newClips']
    aliases = {}
    for entry in entries:
        payload = (assets / entry['asset']).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == entry['sha256'], entry['id']
        assert len(payload) == entry['bytes']
        assert struct.unpack_from('<III', payload) == (0x46546c67, 2, len(payload))
        gltf = json.loads(payload[20:20+struct.unpack_from('<I', payload, 12)[0]])
        assert [a['name'] for a in gltf['animations']] == [entry['animationName']]
        for form in entry['aliases'] + [entry['id'], entry['displayText']]:
            key = ' '.join(form.lower().split())
            assert key not in aliases or aliases[key]['id'] == entry['id'], key
            aliases[key] = entry
    alias_manifest = json.loads((android / 'app/src/main/assets/asl_animations/existing_aliases_asl.json').read_text())
    for addition in alias_manifest['aliases']:
        target = next(e for e in entries if e['id'] == addition['signId'])
        assert target['asset'] == addition['asset'] and target['sha256'] == addition['sha256']
        for form in addition['english']:
            key = ' '.join(form.lower().split())
            assert key not in aliases or aliases[key]['id'] == target['id']
            aliases[key] = target
    rows = []
    for batch, words in enumerate(BATCHES, 1):
        for word in words.split():
            target = word.replace('_', ' ')
            entry = aliases.get(target.lower())
            rows.append(dict(batch=batch, target=target, signId=entry['id'] if entry else None,
                asset=entry['asset'] if entry else None, glossLabel=entry['sourceName'] if entry else None,
                animationName=entry['animationName'] if entry else None,
                technicalStatus='FILE_AND_NAMED_ANIMATION_CHECKED' if entry else 'MISSING_COMPATIBLE_ANIMATION',
                devicePlaybackTested=False, linguisticValidation='UNREVIEWED',
                motionLicense='Existing source provenance unresolved' if entry else None,
                newInputAlias=target == 'GOODBYE'))
    summary = dict(targetWords=len(rows), existingCompatibleClipMappings=sum(r['signId'] is not None for r in rows),
        missingCompatibleAnimations=sum(r['signId'] is None for r in rows), newMotionAssets=0,
        newInputAliases=1, deviceTestedPlayableWordCount=0, linguisticallyVerifiedWords=0,
        batches=[dict(batch=b, targets=sum(r['batch']==b for r in rows),
            availablePreviewMappings=sum(r['batch']==b and r['signId'] is not None for r in rows),
            missing=[r['target'] for r in rows if r['batch']==b and r['signId'] is None]) for b in range(1,6)],
        words=rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir/'vocabulary-progress.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    with (args.output_dir/'vocabulary-progress.csv').open('w',newline='',encoding='utf-8') as file:
        writer=csv.DictWriter(file,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({k:v for k,v in summary.items() if k!='words'},indent=2))

if __name__ == '__main__':
    main()
