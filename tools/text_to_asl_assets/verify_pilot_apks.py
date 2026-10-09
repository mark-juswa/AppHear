"""Check pilot packaging, flag-off exclusion and original-asset preservation."""
from pathlib import Path
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile

repo = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pilot', type=Path, required=True)
parser.add_argument('--default', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
parser.add_argument('--shared', action='store_true', help='Verify the shared-character variant')
parser.add_argument('--words', action='store_true', help='Verify the 27-clip word expansion')
parser.add_argument('--idle', action='store_true', help='Verify the 27-sign plus new idle variant')
parser.add_argument('--alphabet', action='store_true', help='Verify the 27-sign, idle, full alphabet variant')
args = parser.parse_args()
common_source = repo / 'android/app/src/aslPilot/assets'
assert sum((args.shared, args.words, args.idle, args.alphabet)) <= 1
pilot_source = repo / ('android/app/src/aslAlphabet/assets' if args.alphabet else
                       'android/app/src/aslIdle/assets' if args.idle else
                       'android/app/src/aslWords/assets' if args.words else
                       'android/app/src/aslShared/assets' if args.shared else 'android/app/src/aslPilot/assets')
main_source = repo / 'android/app/src/main/assets'
manifest = json.loads((pilot_source / 'asl_animations/vnext/manifest.json').read_text())
overrides = manifest['clips']
expanded = manifest.get('newClips', [])
idle = [manifest['idle']] if args.idle or args.alphabet else []
letters = manifest.get('letters', []) if args.alphabet else []
if args.words or args.idle or args.alphabet:
    assert len(overrides) == 7 and len(expanded) == 20
if args.alphabet:
    assert manifest['schemaVersion'] == 3 and len(letters) == 24
originals = json.loads((main_source / 'asl_animations/manifest.json').read_text())['clips']
with zipfile.ZipFile(args.pilot) as pilot, zipfile.ZipFile(args.default) as default:
    expected = {'assets/' + clip['asset'] for clip in overrides + expanded + idle + letters}
    bundled = {name for name in pilot.namelist()
               if name.startswith('assets/asl_animations/vnext/') and name.endswith('.glb')}
    assert expected == bundled, 'Unexpected or missing packaged pilot GLB'
    sources = list(pilot_source.rglob('*'))
    if args.shared or args.words or args.idle or args.alphabet:
        sources += [f for f in common_source.rglob('*')
                    if not f.relative_to(common_source).as_posix().startswith('asl_animations/vnext/')]
    for file in sources:
        if file.is_file():
            relative = file.relative_to(pilot_source if file.is_relative_to(pilot_source) else common_source).as_posix()
            assert pilot.read('assets/' + relative) == file.read_bytes(), 'Pilot package differs: ' + relative
    assert not any(name.startswith(('assets/asl_animations/vnext/', 'assets/vendor/asl-decoders/'))
                   or name in ('assets/pilot_player.js', 'assets/model_viewer_pilot.html')
                   for name in default.namelist()), 'Flag-off APK contains pilot payload'
    for clip in originals:
        expected_bytes = (main_source / clip['asset']).read_bytes()
        for archive in (pilot, default):
            assert archive.read('assets/' + clip['asset']) == expected_bytes, 'Original changed: ' + clip['id']
suites = [ET.parse(file).getroot() for file in
          (repo / 'android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')]
report = {'variant': 'alphabet' if args.alphabet else 'idle' if args.idle else 'words' if args.words else 'shared' if args.shared else 'separate',
          'uniqueCharacterGLBs': len(expected),
          'newWords': len(expanded),
          'newIdle': bool(idle),
          'fallbackLetters': len(letters),
          'replacements': [clip['id'] for clip in overrides], 'pilotMiB': round(args.pilot.stat().st_size / 1048576, 2),
          'defaultMiB': round(args.default.stat().st_size / 1048576, 2),
          'pilotSHA256': hashlib.sha256(args.pilot.read_bytes()).hexdigest(),
          'defaultSHA256': hashlib.sha256(args.default.read_bytes()).hexdigest(),
          'allPilotPayloadMatchesSource': True, 'flagOffExcludesPilotAssets': True,
          'originalGLBsUnchangedInBothAPKs': len(originals),
          'JVMTests': sum(int(s.get('tests', '0')) for s in suites),
          'JVMFailures': sum(int(s.get('failures', '0')) for s in suites),
          'JVMErrors': sum(int(s.get('errors', '0')) for s in suites),
          'phoneValidation': 'NOT_ASSESSED_BY_PACKAGING_CHECK'}
assert report['JVMTests'] > 0 and report['JVMFailures'] == report['JVMErrors'] == 0
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
