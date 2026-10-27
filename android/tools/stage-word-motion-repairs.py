"""Reproduce the selected licensed motion repairs using the pinned external converter.
Neither application files nor the original archive are modified.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,ast,copy,hashlib,importlib.util,json,time,zipfile
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser(description='Stage source-attributed repairs on the existing human; no installed asset changes')
parser.add_argument('archive',type=Path);parser.add_argument('converter',type=Path);parser.add_argument('baseline',type=Path);parser.add_argument('output',type=Path)
args=parser.parse_args();r=Path(__file__).resolve().parents[2];out=args.output;stage=out/'source-motion';stage.mkdir(parents=True,exist_ok=True)
archive_digest=hashlib.sha256()
with args.archive.open('rb') as stream:
 for chunk in iter(lambda:stream.read(1024*1024),b''):archive_digest.update(chunk)
assert archive_digest.hexdigest()=='bac3e8ca0dbcc45eec0952a20dd04f28cc38131baddc8a354a72da673af0bdc7','Unexpected source archive'
profiles=json.loads((r/'android/tools/word-motion-replacement-profiles.json').read_text())['profiles']
inputs=[{k:e[k] for k in ['id','word','action','sourceWord','member']} for e in profiles]
def mod(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
H=mod('h',r/'android/tools/audit-text-to-sign-hands.py');expand=mod('expand',r/'android/tools/expand-3dlex-vocabulary.py');shoulder=mod('shoulder',r/'android/tools/correct-imported-shoulder-baselines.py')
source=args.converter.read_bytes();assert hashlib.sha256(source).hexdigest()==expand.SOURCE_SHA
ns=dict(np=np,copy=copy,json=json,struct=__import__('struct'),H=H,R=H.r)
tree=ast.parse(source.decode());defs=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in {'Scene','Converter','body_frame','palm','pairs'}];exec(compile(ast.Module(body=defs,type_ignores=[]),'pinned-converter','exec'),ns)
m=H.Model(args.baseline);converter=ns['Converter'](m);accepted=[];rejected=[];started=time.monotonic()
protected={'SIGN_YES','SIGN_LOVE','SIGN_I','SIGN_YOU','SIGN_YOUR'}
with zipfile.ZipFile(args.archive) as z:
 for n,e in enumerate(inputs):
  try:
   if e['action'] in protected:raise ValueError('Preserve the existing user-approved/corrected sign; a warning alone is insufficient')
   cache=stage/(e['id']+'.npz');meta=stage/(e['id']+'.json');payload=z.read(e['member'])
   if cache.exists():
    record=json.loads(meta.read_text());assert record['sourceSha256']==hashlib.sha256(payload).hexdigest();accepted.append(record);continue
   scene=ns['Scene'](payload);expand.exclude_terminal_hip_reset(scene,H);times,frames,checks=converter.convert(scene)
   calibration='Intentional source posture preserved'
   original=frames[1];world=H.r.world(m.nodes,m.parents,m.order,original);hips=world[m.names['Hips']][:3,3]
   wrist_height=max(world[m.names[s+'Hand']][1,3]-hips[1] for s in ['Left','Right'])
   first=min(4,len(frames)-2);travel=max(np.linalg.norm(H.r.world(m.nodes,m.parents,m.order,f)[m.names[s+'Hand']][:3,3]-world[m.names[s+'Hand']][:3,3]) for f in frames[1:1+first] for s in ['Left','Right'])
   if wrist_height<.15 and travel<.02:
    offsets={s:H.r.rotation(converter.neutral[(m.names[s+'Shoulder'],'rotation')])@H.r.rotation(original[(m.names[s+'Shoulder'],'rotation')]).T for s in ['Left','Right']}
    corrected=[frames[0]]
    for f in frames[1:-1]:corrected.append(shoulder.corrected_pose(m,H,f,offsets)[0])
    frames=corrected+[frames[-1]];calibration='Stable source preroll calibrated to existing relaxed shoulders; world hand/finger poses preserved'
   rotations=np.asarray([[f[(i,'rotation')] for i in m.order] for f in frames],dtype='<f4')
   for j in range(rotations.shape[1]):
    for k in range(1,len(rotations)):
     if rotations[k-1,j]@rotations[k,j]<0:rotations[k,j]*=-1
   dots=abs(np.sum(rotations[1:]*rotations[:-1],axis=2)).clip(0,1);steps=np.degrees(2*np.arccos(dots));assert steps[1:-1].max()<90,'Post-calibration abrupt joint step'
   record=dict(**e,sourceSha256=hashlib.sha256(payload).hexdigest(),durationMs=round(float(times[-1])*1000),checks=checks,shoulderCalibration=calibration,sourceUrl='https://osf.io/mqzyk/',license='CC-BY-4.0',qualifiedASLValidation=False)
   np.savez_compressed(cache,times=times,rotations=rotations);meta.write_text(json.dumps(record,indent=2));accepted.append(record)
  except (AssertionError,ValueError,KeyError) as exc:rejected.append(dict(**e,reason=str(exc)))
  if (n+1)%10==0:print('PROGRESS',n+1,'accepted',len(accepted),'rejected',len(rejected),'seconds',round(time.monotonic()-started),flush=True)
(stage/'conversion-report.json').write_text(json.dumps(dict(accepted=accepted,rejected=rejected,seconds=time.monotonic()-started),indent=2));print('COMPLETE',len(accepted),len(rejected),flush=True)
