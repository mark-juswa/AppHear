import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,ast,copy,hashlib,importlib.util,json,struct,time
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser(description='Stage official FBX-derived ASL candidates; never install automatically')
parser.add_argument('staging',type=Path);parser.add_argument('conversion_source',type=Path)
parser.add_argument('--baseline-sha256',required=True);args=parser.parse_args()
r=Path(__file__).resolve().parents[2];q=args.staging;out=q/'staged';out.mkdir(exist_ok=True)
def mod(name,p):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def sha(data):return hashlib.sha256(data).hexdigest()
def file_sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
assert file_sha(q/'ASL_ANIM_FBX.zip')=='6ee2bd5b7ead8f601d2d77345cc6fcfe0b9a323970ca6a9ec316c408298336eb','Not the checksum-verified official FBX archive'
verification=json.loads((q/'fbx-download-verification.json').read_text());assert verification['status']=='PASS' and verification['sha256']=='6ee2bd5b7ead8f601d2d77345cc6fcfe0b9a323970ca6a9ec316c408298336eb'
H=mod('H',r/'android/tools/audit-text-to-sign-hands.py');expand=mod('expand',r/'android/tools/expand-3dlex-vocabulary.py');directional=mod('directional',r/'android/tools/retarget-3dlex-fbx-directions.py');shoulder=mod('shoulder',r/'android/tools/correct-imported-shoulder-baselines.py')
source=args.conversion_source.read_bytes();assert sha(source)==expand.SOURCE_SHA
ns=dict(np=np,copy=copy,json=json,struct=struct,H=H,R=H.r);exec(compile(ast.Module(body=[n for n in ast.parse(source.decode()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in {'Scene','Converter','body_frame','palm','pairs'}],type_ignores=[]),'pinned-converter','exec'),ns)
baseline=r/'android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb';assert sha(baseline.read_bytes())==args.baseline_sha256
m=H.Model(baseline);converter=ns['Converter'](m);manifest=json.loads(baseline.with_name('integration-manifest.json').read_text());occupied={s.lower() for e in manifest['baseEntries']+manifest['entries'] for s in e['english']};occupied.update(s.lower() for e in manifest['aliases'] for s in e['english']);source_hashes={e['sourceSha256'] for e in manifest['entries']};motion_hashes=set();accepted=[];rejected=[];started=time.monotonic()
for e in json.loads((q/'probe-clocks.json').read_text()):
    word=e['word']
    if word in occupied:continue
    try:
        raw=Path(e['path']).read_bytes();assert sha(raw)==e['sourceSha256'];payload=(q/'fbx-glb-normalized'/f'{word}.glb').read_bytes();scene=ns['Scene'](payload);expand.exclude_terminal_hip_reset(scene,H)
        method='FIXED_ANATOMICAL_FRAME'
        try:times,frames,checks=converter.convert(scene)
        except AssertionError as exc:
            if not exc.args or not isinstance(exc.args[0],tuple) or exc.args[0][0]!='Bone direction transfer exceeds one degree':raise
            times,frames,checks=directional.convert(converter,scene,H,ns['body_frame']);method='SOURCE_DIRECTION_WITH_MINIMAL_SWING'
        original=frames[1];world=H.r.world(m.nodes,m.parents,m.order,original);hips=world[m.names['Hips']][:3,3];wrist_height=max(world[m.names[s+'Hand']][1,3]-hips[1] for s in ['Left','Right']);first=min(4,len(frames)-2)
        travel=max(np.linalg.norm(H.r.world(m.nodes,m.parents,m.order,f)[m.names[s+'Hand']][:3,3]-world[m.names[s+'Hand']][:3,3]) for f in frames[1:1+first] for s in ['Left','Right']);calibration='Meaningful source posture retained'
        if wrist_height<.15 and travel<.02:
            offsets={s:H.r.rotation(converter.neutral[(m.names[s+'Shoulder'],'rotation')])@H.r.rotation(original[(m.names[s+'Shoulder'],'rotation')]).T for s in ['Left','Right']}
            frames=[frames[0]]+[shoulder.corrected_pose(m,H,f,offsets)[0] for f in frames[1:-1]]+[frames[-1]];calibration='Stable arms-down preroll calibrated; wrist positions and world finger rotations preserved by IK'
        rotations=np.asarray([[f[(i,'rotation')] for i in m.order] for f in frames],dtype='<f4')
        for j in range(rotations.shape[1]):
            for k in range(1,len(rotations)):
                if rotations[k-1,j]@rotations[k,j]<0:rotations[k,j]*=-1
        steps=np.degrees(2*np.arccos(np.clip(abs(np.sum(rotations[2:-1]*rotations[1:-2],axis=2)),0,1)));assert float(steps.max())<90,('Post-calibration abrupt step',float(steps.max()))
        motion_sha=sha(rotations.tobytes());assert motion_sha not in motion_hashes,'Duplicate candidate motion';motion_hashes.add(motion_sha)
        record=dict(id=word,english=[word],animationName=f'SIGN_{word.upper()}_3DLEX_ASL_PREVIEW',durationMs=round(float(times[-1])*1000),sourceArchiveMember=e['archiveMember'],sourceSha256=e['sourceSha256'],motionSha256=motion_sha,sourceLanguage='ASL',sourceProject='3D-LEX v1.0 ASL Animation Data',sourceUrl='https://osf.io/mqzyk/',license='CC-BY-4.0',construction='FBX_SOURCE_MOTION_RETARGETED_PREVIEW',linguisticValidationStatus='UNREVIEWED',technicalPlaybackStatus='Staged only; native and hand review pending',sourceFormat='FBX',conversionMethod=method,sourceKeyTimeOriginTicks=e['originTicks'],sourceSkeletalKeyTimesPreserved=True,sourceSkeletonGlbSha256=sha(payload),threeVersion='0.180.0',shoulderCalibration=calibration,checks=checks)
        np.savez_compressed(out/(word+'.npz'),times=times,rotations=rotations);(out/(word+'.json')).write_text(json.dumps(record,indent=2));accepted.append(record);print(word,'PASS',method,flush=True)
    except (AssertionError,ValueError,KeyError,FloatingPointError) as exc:rejected.append(dict(word=word,reason=str(exc)));print(word,'REJECT',str(exc),flush=True)
    (out/'progress.json').write_text(json.dumps(dict(accepted=len(accepted),rejected=len(rejected),last=word,seconds=round(time.monotonic()-started))))
report=dict(status='STAGED_UNREVIEWED_FBX_MOTION_CANDIDATES',sourceArchiveSha256=verification['sha256'],sourceArchive='ASL_ANIM_FBX.zip',converterSha256=expand.SOURCE_SHA,baselineSha256=sha(baseline.read_bytes()),sourceFiles=938,eligibleNames=262,added=len(accepted),entries=accepted,rejected=rejected,staticRejected=json.loads((q/'fbx-member-audit.json').read_text())['staticRejected'],qualifiedAslValidations=0,seconds=round(time.monotonic()-started));(out/'report.json').write_text(json.dumps(report,indent=2));print('STAGED',len(accepted),'REJECTED',len(rejected),flush=True)
