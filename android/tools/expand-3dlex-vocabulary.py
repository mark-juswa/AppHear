"""Audit/convert unused official ASL motions; never synthesize a missing sign.

Requires NumPy/Pillow and the pinned external converter source (not shipped in
the APK). Existing AppHear helpers provide the target rig. The source converter
is executed only for its audited Scene/Converter definitions, with no downloads,
entry-point execution or file mutation. Output is staged for review, not installed.
"""
import argparse, ast, collections, copy, hashlib, importlib.util, json, re, struct, time, zipfile
from pathlib import Path
import numpy as np

SOURCE_SHA='46f6b33f3b1ed76bd9de73618484e12932096c62350875c9e2d8a6d30f736384'
ARCHIVE_SHA='bac3e8ca0dbcc45eec0952a20dd04f28cc38131baddc8a354a72da673af0bdc7'
BASE_SHA='7975abceb4c75e09cab995600d6b852edbd608a44e4e4a07550746544f7e7aec'
def sha(b):return hashlib.sha256(b).hexdigest()

def exclude_terminal_hip_reset(scene,H):
    """Some exports end with a global flip into the exact skeleton bind pose.

    Require independent reset signatures at the final retained raw frame only:
    either an exact skeleton bind reset or the pinned partially baked container
    reset with near-bind articulation. Never repair an interior frame, flatten
    a signing joint, or relax the downstream 90-degree/frame gate.
    """
    hips=next((t for t in scene.tracks if t['path']=='rotation' and scene.nodes[t['node']]['name']=='Hips'),None)
    if hips is None:return
    times=np.asarray(hips['times']);values=np.asarray(hips['values'])
    end=int(np.searchsorted(times,scene.duration+1e-6,side='right'))-1
    if end<2 or abs(times[end]-scene.duration)>1e-5:return
    dt=float(times[end]-times[end-1])
    # Use world orientation: the exported Armature also resets by 90 degrees.
    node=scene.names['Hips'];before=scene.pose(float(times[end-1]));after=scene.pose(float(times[end]))
    delta=H.r.orient(before[node]).T@H.r.orient(after[node])
    angle=float(np.degrees(np.arccos(np.clip((np.trace(delta)-1)/2,-1,1))))
    if angle<=90 or not 0<dt<=1/12+1e-6:return
    reset=scene.excluded_reset
    rotation_tracks=[t for t in scene.tracks if t['path']=='rotation']
    matches=0
    for t in rotation_tracks:
        q=H.r.sample(t,float(times[end]));q=np.asarray(q)/np.linalg.norm(q)
        rest=np.asarray(scene.nodes[t['node']].get('rotation',[0,0,0,1]));rest=rest/np.linalg.norm(rest)
        matches+=abs(q@rest)>1-1e-6
    fraction=matches/len(rotation_tracks)
    # A terminal global flip plus an exact whole-skeleton bind reset is export
    # evidence. A sign returning naturally to rest without a flip is untouched.
    reset_kind='EXACT_BIND_RESET'
    if fraction<.95:
        # A second publisher export has the same coordinate reset partially
        # interpolated into its final baked sample. Identify the exact container
        # signature, not a generic relaxed hand or an arbitrary rotation limit.
        arm=next((t for t in rotation_tracks if scene.nodes[t['node']]['name']=='Armature'),None)
        if arm is None or angle<150:return
        canonical=np.asarray([.6898379325866699,0,0,.7239638566970825])
        last=np.asarray(H.r.sample(arm,float(times[end])));last/=np.linalg.norm(last)
        previous=np.asarray(H.r.sample(arm,float(times[end-1])));previous/=np.linalg.norm(previous)
        if abs(last@canonical/np.linalg.norm(canonical))<1-1e-10:return
        if abs(previous@np.asarray([0,0,0,1]))<1-1e-10:return
        # Independently require near-bind articulation across the skeleton.
        # Any held/sign-specific handshape rejects this reset classification.
        near_bind=[]
        for t in rotation_tracks:
            name=scene.nodes[t['node']]['name']
            if name in ('Armature','Hips') or name.endswith('Shoulder'):continue
            q=np.asarray(H.r.sample(t,float(times[end])));q/=np.linalg.norm(q)
            rest=np.asarray(scene.nodes[t['node']].get('rotation',[0,0,0,1]),dtype=float);rest/=np.linalg.norm(rest)
            near_bind.append(float(np.degrees(2*np.arccos(np.clip(abs(q@rest),0,1)))))
        if not near_bind or max(near_bind)>2 or np.mean(np.asarray(near_bind)<1.5)<.95:return
        reset_kind='PARTIALLY_BAKED_CONTAINER_RESET'
    if reset is not None and not 0<reset['firstExcludedSeconds']-times[end]<=1/12+1e-6:return
    if reset is None:
        reset=dict(reason='Terminal whole-skeleton bind-pose export reset',
            firstExcludedSeconds=float(times[end]),lastExcludedSeconds=float(times[end]),excludedFrames=0,
            sourceBytesUnchanged=True)
        scene.excluded_reset=reset
    reset['terminalHipReset']=dict(timeSeconds=float(times[end]),jumpDegrees=angle,
        precedingFrameSeconds=float(times[end-1]),bindPoseRotationMatchFraction=fraction,
        signature=reset_kind,
        reason='Terminal global hip flip and publisher export-coordinate reset')
    reset['firstExcludedSeconds']=float(times[end]);reset['excludedFrames']+=1
    scene.duration=float(times[end-1]);reset['retainedThroughSeconds']=scene.duration

def main():
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('conversion_source',type=Path)
    p.add_argument('output',type=Path);p.add_argument('--limit',type=int,default=400)
    p.add_argument('--baseline-sha256',default=BASE_SHA);a=p.parse_args()
    source=a.conversion_source.read_bytes();assert sha(source)==SOURCE_SHA,'Unexpected conversion algorithm'
    assert sha(a.archive.read_bytes())==ARCHIVE_SHA,'Not the official ASL motion archive'
    android=Path(__file__).resolve().parents[1];assets=android/'app/src/aslOriginalWords/assets'
    folder=assets/'asl_animations/original_words_v1';manifest=json.loads((folder/'integration-manifest.json').read_text(encoding='utf-8'))
    baseline=folder/'fingerspelling-avatar.glb';assert sha(baseline.read_bytes())==a.baseline_sha256,'Use the explicitly pinned baseline'
    spec=importlib.util.spec_from_file_location('hands',Path(__file__).with_name('audit-text-to-sign-hands.py'))
    H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
    namespace=dict(np=np,copy=copy,json=json,struct=struct,H=H,R=H.r)
    parsed=ast.parse(source.decode('utf-8'))
    definitions=[n for n in parsed.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in {'Scene','Converter','body_frame','palm','pairs'}]
    assert len(definitions)==5
    exec(compile(ast.Module(body=definitions,type_ignores=[]),str(a.conversion_source),'exec'),namespace)
    model=H.Model(baseline);converter=namespace['Converter'](model)
    occupied={s.lower() for e in manifest['baseEntries']+manifest['entries'] for s in e['english']}
    occupied.update(s.lower() for alias in manifest['aliases'] for s in alias['english'])
    a.output.mkdir(parents=True,exist_ok=True)
    rejects=[];accepted=[];source_hashes={e['sourceSha256'] for e in manifest['entries']}
    motion_hashes={e['motionSha256'] for e in manifest['entries']}
    started=time.monotonic()
    # Familiar everyday items first; the remaining nonduplicate source words are audited too.
    priority='action airplane alarm alone always angry animal arrive awake banana bank behind bicycle bird birthday blue boat body bored borrow bottle bowl bus busy call calm careful chair change cheap choose class classroom clock close clothes color come company cook corner country cup dangerous dark day decide deep difficult dirty dream drink drive early east easy eat email emergency evening every example expensive family feel finally first fix flower food forget free friend full future garden give glass go green guess hair happen hate hear heavy high history home hope hot hour house hurry ice important inside internet job key know late learn leave left letter life light listen little long look lose love meet money month more morning most move music name near need new next nice night no north now number office old one only open other outside paper pay people person phone place play please police question quick rain read ready really remember repeat rest right road room run sad same school see send short show sick sister sleep slow small sometimes sorry south speak start still stop store street strong student study summer sun table take talk teach teacher tell thank think thirsty time tired today tomorrow together town train travel tree try turn understand university use visit wait walk want warm wash watch water way week welcome west what when where which white who why wife window with work world write wrong year yellow yes yesterday you young'.split()
    with zipfile.ZipFile(a.archive) as z:
        members=[e for e in z.infolist() if e.filename.endswith('.glb')]
        duplicate=collections.Counter((e.CRC,e.file_size) for e in members)
        eligible={Path(e.filename).stem:e for e in members if re.fullmatch('[a-z]+',Path(e.filename).stem) and Path(e.filename).stem not in occupied}
        order=list(dict.fromkeys([w for w in priority if w in eligible]+sorted(eligible)))
        for word in order:
            e=eligible[word];payload=z.read(e);source_sha=sha(payload)
            if duplicate[e.CRC,e.file_size]>1 or source_sha in source_hashes:
                rejects.append(dict(word=word,reason='Duplicate source payload; requires sense/variant review'));continue
            cache=a.output/(word+'.npz');meta=a.output/(word+'.json')
            try:
                if cache.exists() and meta.exists():
                    record=json.loads(meta.read_text(encoding='utf-8'));assert record['sourceSha256']==source_sha
                    with np.load(cache) as data:times=data['times'];rotations=data['rotations']
                else:
                    scene=namespace['Scene'](payload);exclude_terminal_hip_reset(scene,H)
                    times,frames,checks=converter.convert(scene)
                    rotations=np.asarray([[frame[(i,'rotation')] for i in model.order] for frame in frames],dtype='<f4')
                    motion_sha=sha(rotations.tobytes());assert motion_sha not in motion_hashes,'Duplicate converted motion'
                    record=dict(id=word,english=[word],animationName=f'SIGN_{word.upper()}_3DLEX_ASL_PREVIEW',
                        durationMs=round(float(times[-1])*1000),sourceArchiveMember=e.filename,
                        sourceSha256=source_sha,motionSha256=motion_sha,sourceLanguage='ASL',
                        sourceProject='3D-LEX v1.0 ASL Animation Data',sourceUrl='https://osf.io/mqzyk/',
                        license='CC-BY-4.0',construction='ANATOMICAL_FRAME_RETARGETED_PREVIEW',
                        linguisticValidationStatus='UNREVIEWED',technicalPlaybackStatus='Offline conversion only; rendered review pending',checks=checks)
                    np.savez_compressed(cache,times=times,rotations=rotations)
                    meta.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
                assert record['motionSha256'] not in motion_hashes,'Duplicate converted motion'
                accepted.append(record);source_hashes.add(source_sha);motion_hashes.add(record['motionSha256'])
            except (AssertionError,KeyError,ValueError,FloatingPointError) as error:
                rejects.append(dict(word=word,reason=str(error)))
            if (len(accepted)+len(rejects))%5==0:
                print(json.dumps(dict(accepted=len(accepted),rejected=len(rejects),seconds=round(time.monotonic()-started))),flush=True)
            if len(accepted)>=a.limit:break
        report=dict(status='STAGED_UNREVIEWED_MOTION_CANDIDATES',sourceArchiveSha256=ARCHIVE_SHA,
            converterSha256=SOURCE_SHA,baselineSha256=a.baseline_sha256,sourceFiles=len(members),eligibleNames=len(eligible),
            added=len(accepted),rejected=rejects,entries=accepted,qualifiedAslValidations=0,
            seconds=round(time.monotonic()-started))
        (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k not in ['entries','rejected']}),flush=True)
if __name__=='__main__':main()
