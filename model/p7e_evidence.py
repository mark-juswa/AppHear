"""P7E fixed-15 camera gate. Explicit commands, immutable ancestors, no automatic next run."""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from model.p7dr2_evidence import snapshot as r2_snapshot

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/recognition_upgrade/p7e_camera_cadence_feasibility_01'
R2=ROOT/'artifacts/recognition_upgrade/p7dr2_native_host_path_feasibility_01'
APK=ROOT/'android/app/build/outputs/apk/debug/app-debug.apk'
MODEL=ROOT/'artifacts/recognition_upgrade/p7d_android_runtime_skeleton_feasibility_01/random_skeleton.tflite'
MODEL_SHA='d8617516aa08b4827c7a75276c5de5c0d76a07620a07d212d323992c188ee42e'
ADB='D:/AndroidStudio/Android/Sdk/platform-tools/adb.exe'
REMOTE='/sdcard/Android/data/com.example.apphear/files/p7e'

def sha(p:Path)->str:
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p:Path)->dict:return json.loads(p.read_text(encoding='utf-8'))
def save(name:str,value:object)->None:
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
def adb(*args:str)->str:
    return subprocess.run([ADB,'-s','3ab64582',*args],check=True,capture_output=True,text=True,encoding='utf-8').stdout
def snapshot()->dict:
    files=r2_snapshot()
    for folder in [R2,ROOT/'android/app/src/debug/java/com/example/apphear/p7dr2',ROOT/'android/app/src/test/java/com/example/apphear/p7dr2',ROOT/'android/app/src/debug/cpp',ROOT/'android/app/src/debug/jniLibs']:
        for p in folder.rglob('*'):
            if p.is_file():files[p.relative_to(ROOT).as_posix()]=sha(p)
    files['model/p7dr2_evidence.py']=sha(ROOT/'model/p7dr2_evidence.py')
    return files
def prepare()->None:
    assert not OUT.exists(),'Do not overwrite P7E'
    assert sha(MODEL)==MODEL_SHA
    manifest=read(R2/'artifact_hash_manifest.json')
    assert all(sha(R2/x['path'])==x['sha256'] for x in manifest['artifacts'])
    assert sha(APK)==read(R2/'p7dr2_candidate_identity.json')['apk_sha256']
    OUT.mkdir()
    save('p7e_reference_identity.json',{'files':snapshot(),'model_sha256':MODEL_SHA,
        'debug_manifest_before':sha(ROOT/'android/app/src/debug/AndroidManifest.xml'),
        'R2_original_build_APK_sha256':sha(APK),'R2_APK_archive':'p7dr2_reference.apk'})
    save('p7e_benchmark_protocol.json',{'experiment_id':'P7E_CAMERA_CADENCE_FEASIBILITY_01',
        'experiment':'P7E_CAMERA_CADENCE_FEASIBILITY','variant':'C15_FIXED_AE',
        'only_behavior_change':'CONTROL_AE_TARGET_FPS_RANGE [8,30] inherited -> [15,15] explicit',
        'request_resolution':[480,360],'camera':'DEFAULT_FRONT_CAMERA','format':'RGBA_8888',
        'strategy':'KEEP_ONLY_LATEST','executor':'single worker inherited from R2',
        'smoke':'Untimed: 12 capture results, request and active range must all be [15,15]; no FPS calculated; 30s watchdog only',
        'camera_seconds':60,'camera_warmup_seconds':0,'integrated_warmup_seconds':30,'integrated_seconds':180,
        'minimum_capture_fps':15.0,'minimum_analyzer_fps':15.0,'minimum_completed_fps':15.0,
        'p95_limit_ms':62.7532812,'raw_count_decisions':True,'rounding_for_decisions':False,
        'thermal':'NONE at start and sampled every 5s; non-NONE invalidates, no retries',
        'memory':'sampled every5s; no formal ceiling; no continuous high-water guarantee',
        'start_window':'First analyzer callback epoch; same R2 convention; capture/analyzer timestamps >=start and <end; complete frames must finish <=end',
        'integrated_unlock':'Valid camera-only: capture>=15 AND analyzer>=15 AND request/active [15,15] AND no errors/thermal invalidation',
        'model_sha256':MODEL_SHA,'runtime':'2.16.1','provider':'XNNPACK','threads':2,'variant_compute':3,
        'native_library_rebuilt':False,'post_formal_timing_source_changes_allowed':False,'formal_retry_allowed':False,
        'recognizer':False,'RGB_persisted':False,'S5_S7':False,'automatic_followup':False})
    print('P7E references and prospective protocol recorded')

def references()->dict:
    before=read(OUT/'p7e_reference_identity.json')
    after=snapshot()
    assert before['files']==after,'Protected reference changed'
    assert sha(MODEL)==MODEL_SHA
    assert sha(OUT/'p7dr2_reference.apk')==before['R2_original_build_APK_sha256']
    content=(ROOT/'android/app/src/debug/AndroidManifest.xml').read_bytes()
    for line in [b'        <!-- P7E fixed-15 camera experiment: debug-only, explicit opt-in, no production use. -->\n',
                 b'        <activity android:name=".p7e.P7eRuntimeActivity" android:exported="true" />\n']:
        assert content.count(line)==1
        content=content.replace(line,b'')
    assert hashlib.sha256(content).hexdigest()==before['debug_manifest_before']
    return after
def sources()->dict:
    paths=[ROOT/'model/p7e_evidence.py',ROOT/'android/app/src/debug/AndroidManifest.xml',APK,OUT/'p7e_benchmark_protocol.json']
    for folder in ['android/app/src/debug/java/com/example/apphear/p7e','android/app/src/test/java/com/example/apphear/p7e']:
        paths += [p for p in (ROOT/folder).rglob('*') if p.is_file()]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in paths}
def tests()->dict:
    suites=[ET.parse(p).getroot() for p in (ROOT/'android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml')]
    assert suites and all(x.attrib['failures']==x.attrib['errors']=='0' for x in suites)
    assert any(x.attrib['name']=='com.example.apphear.p7e.P7eGateTest' for x in suites)
    return {'passed':True,'tests':sum(int(x.attrib['tests']) for x in suites),'suites':len(suites)}
def bootstrap()->None:
    references()
    with zipfile.ZipFile(APK) as z:
        native=hashlib.sha256(z.read('lib/arm64-v8a/libp7dr2.so')).hexdigest()
    assert native==read(R2/'p7dr2_build_identity.json')['packaged_native_sha256'],'Packaged native changed'
    save('p7e_build_identity.json',{'sources':sources(),'apk_sha256':sha(APK),'packaged_native_sha256':native,
         'native_rebuilt':False,'runtime':'2.16.1','camerax':'1.3.4','JVM_tests':tests()})
    save('host_gate.json',{'authorized_run':'parity','jvm_tests_pass':True,'apk_sha256':sha(APK),'model_sha256':MODEL_SHA})
    print(json.dumps(read(OUT/'p7e_build_identity.json'),indent=2))
def candidate_check()->None:
    references()
    c=read(OUT/'p7e_candidate_identity.json')
    assert c['sources']==sources(),'Frozen P7E source/APK/protocol changed'
    assert c['parity_sha256']==sha(OUT/'parity_result.json') and c['smoke_sha256']==sha(OUT/'smoke_result.json')
def freeze()->None:
    references()
    assert read(OUT/'parity_result.json')['passed']
    assert read(OUT/'smoke_result.json')['passed']
    assert read(OUT/'p7e_build_identity.json')['sources']==sources()
    assert not (OUT/'p7e_candidate_identity.json').exists()
    save('p7e_candidate_identity.json',{'sources':sources(),'apk_sha256':sha(APK),'model_sha256':MODEL_SHA,
         'camera':read(OUT/'smoke_result.json')['camera_metadata'],
         'parity_sha256':sha(OUT/'parity_result.json'),'smoke_sha256':sha(OUT/'smoke_result.json'),
         'inherited_native_sha256':sha(ROOT/'android/app/src/debug/jniLibs/arm64-v8a/libp7dr2.so'),
         'frozen_before_formal_timing':True,'no_post_timing_source_changes':True})
    print('P7E formal timing freeze complete. No source changes/retries now permitted.')
def authorize(run:str)->None:
    assert run in ['smoke','camera','integrated']
    assert not (OUT/f'{run}_result.json').exists(),'No retry'
    if run=='smoke':
        references();assert read(OUT/'p7e_build_identity.json')['sources']==sources()
    else:candidate_check()
    assert read(OUT/'parity_result.json')['passed']
    if run=='integrated':assert read(OUT/'p7e_camera_summary.json')['passed'],'Camera fail: integrated prohibited'
    save('host_gate.json',{'authorized_run':run,'jvm_tests_pass':True,'apk_sha256':sha(APK),'model_sha256':MODEL_SHA,
         'native_parity_verified':True,'candidate_frozen':run!='smoke','camera_pass_verified':run=='integrated'})
    print(adb('push',str(OUT/'host_gate.json'),REMOTE+'/host_gate.json'))
def log(label:str)->str:
    pid=adb('shell','pidof','com.example.apphear').strip();assert pid.isdigit()
    value=adb('logcat','-d','--pid='+pid,'-s','P7E:I','tflite:I','AndroidRuntime:E')
    path=OUT/f'logcat_{label}.txt';assert not path.exists();path.write_text(value,encoding='utf-8')
    return value
def go()->None:
    candidate_check()
    evidence=log('integrated_ready')
    assert 'READY run=integrated' in evidence
    assert re.search(r'Replacing 44 out of 44 node\(s\).*yielding 1 partitions',evidence)
    save('go_integrated.json',{'delegation_44_of_44':True,'apk_sha256':sha(APK)})
    print(adb('push',str(OUT/'go_integrated.json'),REMOTE+'/go_integrated.json'))
def stats(values:list)->dict:
    v=sorted(values)
    def q(p:float)->float|None:
        if not v:return None
        k=p*(len(v)-1);i=int(k);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(k-i)
    return {'count':len(v),'p50':q(.5),'p90':q(.9),'p95':q(.95),'max':max(v) if v else None}
def collect(run:str)->None:
    assert run in ['parity','smoke','camera','integrated']
    target=OUT/f'{run}_result.json';assert not target.exists()
    print(adb('pull',REMOTE+'/'+target.name,str(target)))
    evidence=log(run+'_complete');r=read(target)
    if run=='parity':
        save('p7e_native_parity_verification.json',r)
        save('p7e_preflight_provider_partitioning.json',{'matches':re.findall(r'Replacing (\d+) out of (\d+) node\(s\).*yielding (\d+) partitions',evidence)})
        print(json.dumps(r,indent=2));return
    if run=='smoke':
        save('p7e_camera_capability.json',r)
        print(json.dumps(r,indent=2));return
    candidate_check()
    assert r['model_sha256']==MODEL_SHA and r['runtime']=='2.16.1' and r['threads']==2 and r['variant']==3
    assert r['device']=='M2101K7AG' and r['soc']=='SM6150' and r['android']=='12'
    assert r['precision']=='FP32' and r['provider']=='XNNPACK'
    seconds=r['measured_seconds'];start=r['measurement_start_ns'];end=r['measurement_end_ns']
    assert seconds==(60 if run=='camera' else 180)
    assert r['warmup_seconds']==(0 if run=='camera' else 30)
    assert end-start==seconds*1e9
    captures=r['capture_rows'];arrivals=r['arrival_rows'];rows=r['samples']
    assert len(captures)==r['capture_completions'] and len(arrivals)==r['analyzer_callbacks'] and len(rows)==r['completed']
    assert all(start<=x[0]<end for x in captures+arrivals)
    assert all(start<=x['start_ns']<=x['end_ns']<=end for x in rows)
    assert all(len(x)==8 and x[7]==0 for x in arrivals)
    capture_fps=len(captures)/seconds;analyzer_fps=len(arrivals)/seconds;completed_fps=len(rows)/seconds
    assert capture_fps==r['capture_fps'] and analyzer_fps==r['analyzer_fps'] and completed_fps==r['completed_fps']
    policy=bool(captures) and all(x[4:8]==[15,15,15,15] for x in captures)
    valid=not r['errors'] and all(x['thermal']==0 for x in r['memory'])
    metrics={k:stats([x[k] for x in rows]) for k in ['preprocess_ms','backend_native_ms','invoke_wall_ms','output_read_ms','decoder_ms','restore_ms','perception_ms']}
    camera_pass=valid and policy and capture_fps>=15 and analyzer_fps>=15
    passed=camera_pass if run=='camera' else camera_pass and completed_fps>=15 and metrics['perception_ms']['p95'] is not None and metrics['perception_ms']['p95']<=62.7532812
    if run=='camera':assert bool(r['camera_screen_pass'])==bool(camera_pass)
    summary={'run':run,'valid':valid,'policy_exact':policy,'passed':bool(passed),
        'capture_count':len(captures),'analyzer_count':len(arrivals),'completed_count':len(rows),'seconds':seconds,
        'capture_fps':capture_fps,'analyzer_fps':analyzer_fps,'completed_fps':completed_fps,
        'latency_ms':metrics,'camera_metadata':r['camera_metadata'],'frame_metadata':r['frame_metadata'],
        'requested_ranges':sorted(set(tuple(x[6:8]) for x in captures)),
        'active_ranges':sorted(set(tuple(x[4:6]) for x in captures)),
        'source_metadata_variants':sorted(set(tuple(x[2:]) for x in arrivals)),
        'sensor_gap_ms':stats([(b[1]-a[1])/1e6 for a,b in zip(captures,captures[1:]) if a[1]>=0 and b[1]>=0]),
        'frame_duration_ms':stats([x[2]/1e6 for x in captures if x[2]>=0]),
        'exposure_ms':stats([x[3]/1e6 for x in captures if x[3]>=0]),
        'model_load_ms':r['model_load_ms'],'errors':r['errors'],'raw_sha256':sha(target),'no_rounding':True}
    save(f'p7e_{run}_summary.json',summary)
    print(json.dumps(summary,indent=2))

def finalize()->None:
    after=references()
    if (OUT/'p7e_candidate_identity.json').exists():candidate_check()
    raw={n:read(OUT/f'{n}_result.json') for n in ['camera','integrated'] if (OUT/f'{n}_result.json').exists()}
    summaries={n:read(OUT/f'p7e_{n}_summary.json') for n in raw}
    classification='P7E_FIXED_15_CAMERA_CONFIGURATION_INVALID'
    reason='Configuration or preflight evidence incomplete';next_gate='PROJECT_LEAD_CAMERA_POLICY_REVIEW'
    if 'camera' in summaries:
        c=summaries['camera']
        if not c['policy_exact'] or not c['valid']:
            reason='Policy not established or run invalid; no cadence-only conclusion'
        elif not c['passed']:
            classification='P7E_CAMERA_CADENCE_BELOW_SCREEN';reason='Raw capture and/or analyzer count below 15 FPS';next_gate='PROJECT_LEAD_CAMERA_CADENCE_REVIEW'
        else:
            classification='P7E_CAMERA_CADENCE_SCREEN_PASS';reason='Camera gate passed; integrated pending';next_gate='PROJECT_LEAD_INTEGRATED_RUNTIME_REVIEW'
            if 'integrated' in summaries:
                if summaries['integrated']['passed']:
                    classification='P7E_FAMILY_A_RUNTIME_SKELETON_FEASIBLE';reason='All frozen integrated requirements passed';next_gate='PROJECT_LEAD_FAMILY_A_SEMANTIC_TRAINING_TRANSITION_REVIEW'
                else:
                    classification='P7E_INTEGRATED_RUNTIME_BELOW_SCREEN';reason='At least one integrated criterion failed';next_gate='PROJECT_LEAD_INTEGRATED_RUNTIME_REVIEW'
    prohibited={k:False for k in ['training','teacher_extraction','recognizer_inference','accuracy_evaluation','D10','protected_replay','pristine_data','S5_changed','S7_changed','model_changed','native_optimization','native_rebuild','precision_changed','resolution_changed','provider_changed','thread_count_changed','Family_B','RGB_persisted','production_authorized','automatic_followup']}
    integrity={'integrity':'PASS','before_after_files':{k:{'before':v,'after':after[k]} for k,v in read(OUT/'p7e_reference_identity.json')['files'].items()},
        'progress_tracker_unchanged':True,'production_sources_unchanged':True,'historical_artifacts_unchanged':True,
        'native_library_unchanged':True,'model_unchanged':True,'context_unchanged':True,
        'source_unchanged_after_formal_freeze':(OUT/'p7e_candidate_identity.json').exists(),**prohibited}
    save('p7e_integrity.json',integrity)
    decision={'experiment':'P7E_CAMERA_CADENCE_FEASIBILITY','experiment_id':'P7E_CAMERA_CADENCE_FEASIBILITY_01',
         'classification':classification,'reason':reason,'next_gate':next_gate,'next_gate_executed':False,
         'integrated_executed':'integrated' in raw,**prohibited}
    save('p7e_decision.json',decision)
    save('APPHEAR_RECOGNITION_CANONICAL_STATE_P7E.json',{'parent':'APPHEAR_RECOGNITION_CANONICAL_STATE_P7DR2.json',
        'parent_sha256':sha(R2/'APPHEAR_RECOGNITION_CANONICAL_STATE_P7DR2.json'),
        'P7DR2_status':'P7DR2_NATIVE_HOST_COMPUTE_SCREEN_PASS','prior_reclassified':False,
        'architecture':'FA_DS_SPATIAL_V1','model_sha256':MODEL_SHA,'runtime':'2.16.1','provider':'XNNPACK','threads':2,
        'policy':'POLICY_UNCONFIGURED','variant':'C15_FIXED_AE',**decision})
    save('p7e_memory_summary.json',{'interval_seconds':5,'continuous_high_water_mark':False,'formal_ceiling':None,
        'runs':{n:{'peak_sampled_pss_kib':max(x['pss_kib'] for x in r['memory']),
            'peak_sampled_native_heap_bytes':max(x['native_heap_bytes'] for x in r['memory']),
            'peak_sampled_java_heap_bytes':max(x['java_heap_bytes'] for x in r['memory']),
            'samples':r['memory']} for n,r in raw.items()}})
    save('p7e_thermal_summary.json',{'requirement':'NONE; no retry','runs':{n:{'start':r['memory'][0]['thermal'],'peak':max(x['thermal'] for x in r['memory']),'end':r['memory'][-1]['thermal']} for n,r in raw.items()}})
    save('p7e_runtime_errors.json',{'runs':{n:r['errors'] for n,r in raw.items()},'crashes_observed':0 if raw and all(not r['errors'] for r in raw.values()) else None,'OOM_observed':any('OutOfMemory' in str(r['errors']) for r in raw.values()),'formal_retries':0})
    logs={p.name:re.findall(r'Replacing (\d+) out of (\d+) node\(s\).*yielding (\d+) partitions',p.read_text()) for p in OUT.glob('logcat_*.txt')}
    save('p7e_provider_partitioning.json',{'evidence':logs,'integrated_executed':'integrated' in raw,'enabled_flag_alone_not_proof':True})
    save('p7e_android_changes_manifest.json',{'P7E_sources':sources(),'debug_manifest_added_lines':2,
        'production_changed':False,'R2_native_sources_library_changed':False,'build_configuration_changed':False,
        'only_camera_behavior_change':'AE target range [15,15]','diagnostics_added':'Camera ID/capability checks, per-frame source metadata, raw-count gates, no RGB recording',
        'original_R2_APK_archived_before_build':'p7dr2_reference.apk'})
    lines=['# P7E Camera Cadence Feasibility','',f'Classification: **{classification}**. Integrity: PASS.',
        '',f'Reason: {reason}. Next gate: **{next_gate}**. Next gate executed: NO.',
        '', '## Facts','', 'One intentional camera behavior change: request CONTROL_AE_TARGET_FPS_RANGE=[15,15]. CameraX1.3.4, DEFAULT_FRONT_CAMERA, requested480x360, RGBA8888, KEEP_ONLY_LATEST and worker/close behavior retained. No preview use case added. Actual source recorded separately. Frozen R2 V3 classes/native library reused, no rebuild; TFLite2.16.1 FP32 XNNPACK2threads.',
        '',f'Model SHA256: `{MODEL_SHA}`. R2 remains P7DR2_NATIVE_HOST_COMPUTE_SCREEN_PASS.',
        '', 'Untimed native parity and twelve-result camera configuration smoke precede candidate freeze. Source/APK/protocol hashes are checked before formal execution and at finalization. Native readout remains POLICY_UNCONFIGURED. No smoke FPS is used as evidence.',
        '', '| Run | Seconds | Capture count/FPS | Analyzer count/FPS | Completed count/FPS | Complete p95 ms | Pass |', '|---|---:|---|---|---|---:|---|']
    for n,r in summaries.items():
        lines.append(f'|{n}|{r["seconds"]}|{r["capture_count"]} / {r["capture_fps"]}|{r["analyzer_count"]} / {r["analyzer_fps"]}|{r["completed_count"]} / {r["completed_fps"]}|{r["latency_ms"]["perception_ms"]["p95"]}|{r["passed"]}|')
        lines += ['',f'{n} requested AE={r["requested_ranges"]}; active AE={r["active_ranges"]}; actual source={json.dumps(r["frame_metadata"])}.',
            f'Exposure ms: {r["exposure_ms"]}. Frame duration ms: {r["frame_duration_ms"]}. Sensor gap ms: {r["sensor_gap_ms"]}.']
    lines += ['',f'Integrated executed: {"integrated" in raw}. If camera gate failed, integrated is prohibited—not estimated from old R2 latency.',
        '', 'Raw JSON includes capture callback/sensor timestamps/frame numbers, request/active ranges/exposure/frame duration and analyzer timestamp/source metadata. Count windows and linear-interpolated percentiles are independently recomputed by the frozen host utility. No rounding-based acceptance. Camera-only zero completed perception frames is intentional (no model invocation).',
        '', '## Supported conclusions','',
        ('Fixed15 policy met the camera count screen.' if summaries.get('camera',{}).get('passed') else 'A fixed15 request did not establish the required delivered camera cadence in this governed run. A near15 value below15 is still failure.'),
        '', 'The experiment changes AE policy only, but is not a simultaneous randomized environmental comparison with R2. Exposure/frame-duration differences support a policy/environment interaction interpretation, not exclusive causal attribution. Camera request metadata is distinct from actual delivered FPS.',
        '', '## Hypotheses','', 'AE policy/environment interaction remains a causal hypothesis qualified by measured request/active ranges and delivered cadence. Device scheduling, sensor timing and exposure behavior are not disentangled by this single run. No lighting, AE, resolution, scheduling or provider sweep was performed.',
        '', '## Not established','', 'Landmark accuracy; anatomical hand identity accuracy; recognition accuracy; calibrated confidence; S5/S7 behavior; low-light recognition robustness; production readiness. No teacher extraction, training, recognizer, protected replay, D10 or pristine data.',
        '', 'Memory/PSS/native/Java heap sampled every5seconds; continuous high-water mark unavailable and no formal memory ceiling. Thermal requires sampled NONE. No retries or source modifications after formal freeze.',
        '', 'Protected context remains unchanged. Imprint is audit-only; all experiment documentation is here. Debug-only default-off activity has no production connection. Original R2 build APK preserved here before the build output was replaced; R2 historical artifacts were not rewritten.',
        '', '## Review','', 'Plan alignment: PASS. Source isolation/integrity: PASS. Production readiness: NOT ESTABLISHED. No schema/math change. Runtime outcome follows raw counts, not nominal requested FPS. No next experiment authorized.']
    (OUT/'P7E_CAMERA_CADENCE_FEASIBILITY_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (OUT/'P7E_SOURCE_OF_TRUTH_INDEX.md').write_text('''# P7E source of truth

Read report, canonical state and decision first. P7E is not P7D-R3.

| Claim | Evidence |
|---|---|
| R2 immutable compute success | Parent report/canonical/decision; p7e_reference_identity.json |
| Exact compute path retained | R2 P7dr2Path/P7dr2Native/P7dr2Parity and libp7dr2.so hashes; packaged library hash |
| Camera request | android/app/src/debug/java/com/example/apphear/p7e/P7eRuntimeActivity.kt, Camera2Interop.Extender.setCaptureRequestOption |
| Count gates | same directory/P7eGate.kt; unit boundary tests; model/p7e_evidence.py |
| Capability/smoke | p7e_camera_capability.json; smoke_result.json (not performance evidence) |
| Freeze | p7e_candidate_identity.json, p7e_build_identity.json, p7e_benchmark_protocol.json |
| Cadence/timing | camera_result.json; integrated_result.json only if executed; p7e_*_summary.json |
| Delegation | logcat parity/integrated ready and provider partitioning JSON |
| Protection | p7e_integrity.json before/after hashes; android changes manifest |

Primary API evidence: [Camera2Interop implementation](https://android.googlesource.com/platform/frameworks/support/+/f2e05c341382db64d127118a13451dcaa554b702/camera/camera-camera2/src/main/java/androidx/camera/camera2/interop/Camera2Interop.java), [Camera2 interop reference](https://developer.android.com/reference/kotlin/androidx/camera/camera2/interop/package-summary). Current online API may describe newer deprecations; project remains CameraX1.3.4, no upgrade. Compilation verifies the pinned API. Interop overrides one capture-request key; do not directly manipulate raw CameraCaptureSession state.
''',encoding='utf-8')
    save('artifact_hash_manifest.json',{'self_excluded':True,'algorithm':'SHA256','artifacts':[{'path':p.relative_to(OUT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='artifact_hash_manifest.json']})
    print(json.dumps(decision,indent=2))

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='bootstrap':bootstrap()
    elif sys.argv[1]=='authorize':authorize(sys.argv[2])
    elif sys.argv[1]=='collect':collect(sys.argv[2])
    elif sys.argv[1]=='freeze':freeze()
    elif sys.argv[1]=='go':go()
    elif sys.argv[1]=='finalize':finalize()
