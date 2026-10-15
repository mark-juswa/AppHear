"""Independent structural/skin checks for ten new previews, not ASL validation."""
import csv,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
s=importlib.util.spec_from_file_location('contact',Path(__file__).with_name('correct-text-to-sign-love.py'))
c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
before,candidate,report=map(Path,sys.argv[1:4])
a,b=c.hands.Model(before),c.hands.Model(candidate)
registry=json.loads(candidate.with_suffix('.json').read_text())
assert hashlib.sha256(before.read_bytes()).hexdigest()==registry['everydayExpansion']['baselineSha256']
assert hashlib.sha256(candidate.read_bytes()).hexdigest()==registry['sha256']
assert b.g['animations'][:232]==a.g['animations']
assert b.binary[:a.g['buffers'][0]['byteLength']]==a.binary[:a.g['buffers'][0]['byteLength']]
for k in ['nodes','skins','meshes','materials','textures','images','scenes']:assert a.g[k]==b.g[k],k
mesh=c.ContactMesh(b);results=[]
for e in registry['wordAdditions'][-10:]:
 tracks=b.tracks(e['animationName']);duration=max(t['times'][-1] for t in tracks)
 for t in tracks:
  assert np.isfinite(t['values']).all() and np.all(np.diff(t['times'])>0)
  assert t['path']=='rotation', 'New actions must not stretch/reposition bones'
  assert np.max(np.abs(np.linalg.norm(t['values'],axis=1)-1))<1e-5
 depths=[];handspread=[]
 for time in np.linspace(0,duration,41):
  w=c.pose(b,tracks,float(time));v=mesh.skin(w)
  for side in ['Right','Left']:
   d=mesh.depths(v,side)
   depths.append([float(max(0,np.max(d[p]))) for p in ['hand','forearm']])
  handspread.append((w[b.names['RightHandIndex4']][:3,3]-w[b.names['RightHandPinky4']][:3,3]).tolist())
 results.append(dict(id=e['id'],namedAction=e['animationName'],sampledFrames=41,finiteUnitQuaternions=True,
   maxHandFrontSurfaceDepthMm=float(np.max(np.array(depths)[:,0])*1000),
   maxForearmFrontSurfaceDepthMm=float(np.max(np.array(depths)[:,1])*1000),
   rightIndexPinkySpanMeters=np.linalg.norm(handspread,axis=1).tolist(),qualifiedAslValidation=False))
 print(e['id'],results[-1]['maxHandFrontSurfaceDepthMm'],flush=True)
result=dict(bundleSha256=registry['sha256'],existingActionsPreserved=232,newActions=10,geometryAndSkinUnchanged=True,
  qualifiedAslValidations=0,checks=results,collisionLimit='Front torso/face projection only; not full mesh collision or linguistic evaluation')
report.write_text(json.dumps(result,indent=2)+'\n')
# Complete active word inventory: asset presence is separate from visual and
# linguistic review. Unbounded spelling fallback is not a lexical dictionary.
android=Path(__file__).resolve().parents[1]
original=json.loads((android/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1/manifest.json').read_text())
frozen=json.loads((android/'app/src/main/assets/asl_animations/manifest.json').read_text())
lookup={e['id']:e for e in frozen['clips']}
inventory=[]
for e in original['replacements']+original['newClips']:
 base=lookup.get(e['id'],{})
 inventory.append(dict(id=e['id'],english=' | '.join(e.get('aliases',base.get('aliases',[]))),
   animationName=e['animationName'],animationExists=e['animationName'] in b.animations,
   newInThisBatch=False,visualReviewThisBatch='Not repeated',linguisticValidation='UNREVIEWED'))
for e in registry['wordAdditions']:
 inventory.append(dict(id=e['id'],english=' | '.join(e['english']),animationName=e['animationName'],
   animationExists=e['animationName'] in b.animations,newInThisBatch=e['id'] in {p['id'] for p in results},
   visualReviewThisBatch='See Android capture report' if e['id'] in {p['id'] for p in results} else 'Not repeated',
   linguisticValidation='UNREVIEWED'))
assert len(inventory)==216 and len({e['id'] for e in inventory})==216
with report.with_name('everyday-ten-vocabulary-inventory.csv').open('w',newline='',encoding='utf-8') as f:
 writer=csv.DictWriter(f,fieldnames=list(inventory[0]));writer.writeheader();writer.writerows(inventory)
