"""P7DR2 evidence utility: explicit stages, no training or automatic next experiment."""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from model.p7dr1_evidence import snapshot as prior_snapshot

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/recognition_upgrade/p7dr2_native_host_path_feasibility_01'
R1 = ROOT / 'artifacts/recognition_upgrade/p7dr1_runtime_data_path_remediation_01'
MODEL = ROOT / 'artifacts/recognition_upgrade/p7d_android_runtime_skeleton_feasibility_01/random_skeleton.tflite'
MODEL_SHA = 'd8617516aa08b4827c7a75276c5de5c0d76a07620a07d212d323992c188ee42e'
ADB = 'D:/AndroidStudio/Android/Sdk/platform-tools/adb.exe'
APK = ROOT/'android/app/build/outputs/apk/debug/app-debug.apk'
REMOTE = '/sdcard/Android/data/com.example.apphear/files/p7dr2'

def adb(*args: str) -> str:
    return subprocess.run([ADB,'-s','3ab64582',*args],check=True,capture_output=True,text=True,encoding='utf-8').stdout

def sha(p: Path) -> str:
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def save(name: str, value: object) -> None:
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')

def snapshot() -> dict:
    result=prior_snapshot()
    for directory in [R1,ROOT/'android/app/src/debug/java/com/example/apphear/p7dr1',ROOT/'android/app/src/test/java/com/example/apphear/p7dr1']:
        for p in directory.rglob('*'):
            if p.is_file(): result[p.relative_to(ROOT).as_posix()]=sha(p)
    result['model/p7dr1_evidence.py']=sha(ROOT/'model/p7dr1_evidence.py')
    result['android/app/build.gradle.kts']=sha(ROOT/'android/app/build.gradle.kts')
    return result

def prepare() -> None:
    assert not (OUT/'p7dr2_reference_identity.json').exists()
    assert sha(MODEL)==MODEL_SHA
    save('p7dr2_reference_identity.json',{'model_sha256':MODEL_SHA,'files':snapshot(),
         'debug_manifest_before':sha(ROOT/'android/app/src/debug/AndroidManifest.xml')})
    save('p7dr2_benchmark_protocol.json',{
        'experiment':'P7D-R2_NATIVE_HOST_PATH_FEASIBILITY','order':['V0','V1','V2','V3'],
        'variants':{'V0':'P7DR1_JVM_REFERENCE','V1':'P7DR2_NATIVE_PREPROCESS_ONLY','V2':'P7DR2_NATIVE_DECODER_ONLY','V3':'P7DR2_NATIVE_PREPROCESS_AND_DECODER'},
        'warmup_seconds':10,'measured_seconds':30,'geometry':[640,480,2560,4,270],
        'random_java_seed':707,'runtime':'2.16.1','threads':2,'provider':'XNNPACK','precision':'FP32',
        'p95_limit_ms':62.7532812,'minimum_loops_per_second':15,
        'thermal':'Require NONE at start and sampled every5s; non-NONE invalidates and stops; no retry',
        'cooldown':'None specified by parent; no new cooldown sweep','fresh_process_per_variant':True,
        'native_compile':['NDK27.1.12297006','C++17','arm64-v8a','API26','-O3','-fno-fast-math','-ffp-contract=off'],
        'combined_fixtures':'8 cases: source640x480 padded row2572 base17; rotations0/90/180/270 x ramp/random707',
        'combined_input_atol':1e-5,'combined_input_rtol':1e-6,
        'combined_raw_output_atol':1e-5,'combined_raw_output_rtol':1e-6,
        'combined_coordinates_confidence_identity_atol':1e-5,'combined_winners_exact':True,
        'post_timing_source_changes_allowed':False,'automatic_R3':False,
        'camera_protocol':json.loads((R1/'p7dr1_camera_only_protocol.json').read_text()),
        'integrated_protocol':json.loads((R1/'p7dr1_integrated_benchmark_protocol.json').read_text()),
        'camera_low_cadence':'Separate unresolved limitation; never substitute reciprocal processing time for delivered FPS',
        'classifications':{'parity_fail':'P7DR2_NATIVE_HOST_PARITY_FAILED','compute_fail':'P7DR2_NATIVE_HOST_PATH_BELOW_SCREEN',
          'compute_only':'P7DR2_NATIVE_HOST_COMPUTE_SCREEN_PASS','integrated_fail':'P7DR2_NATIVE_HOST_INTEGRATED_BELOW_SCREEN',
          'full_pass':'P7DR2_NATIVE_HOST_RUNTIME_SKELETON_FEASIBLE','pending':'P7DR2_DEVICE_EXECUTION_PENDING'},
        'production_authorized':False})
    print('R2 reference hashes and prospective protocol frozen')

def code_files() -> dict:
    paths=[]
    for name in ['android/app/src/debug/cpp','android/app/src/debug/java/com/example/apphear/p7dr2',
                 'android/app/src/test/java/com/example/apphear/p7dr2','android/app/src/debug/jniLibs']:
        paths += [p for p in (ROOT/name).rglob('*') if p.is_file()]
    paths += [ROOT/'android/app/src/debug/AndroidManifest.xml',ROOT/'android/app/build.gradle.kts',
              ROOT/'model/p7dr2_evidence.py',APK,OUT/'p7dr2_benchmark_protocol.json']
    return {p.relative_to(ROOT).as_posix():sha(p) for p in paths}

def reference_check() -> None:
    original=json.loads((OUT/'p7dr2_reference_identity.json').read_text())
    assert original['files']==snapshot(),'Protected/reference change'
    assert sha(MODEL)==MODEL_SHA
    # Verify exact pre-existing manifest content, permitting only the two new debug lines.
    content=(ROOT/'android/app/src/debug/AndroidManifest.xml').read_bytes()
    for line in [b'        <!-- P7D-R2 native host feasibility, isolated debug-only explicit opt-in. -->\n',
                 b'        <activity android:name=".p7dr2.P7dr2RuntimeActivity" android:exported="true" />\n']:
        assert content.count(line)==1
        content=content.replace(line,b'')
    assert hashlib.sha256(content).hexdigest()==original['debug_manifest_before']

def jvm_tests() -> dict:
    directory=ROOT/'android/app/build/test-results/testDebugUnitTest'
    suites=[ET.parse(p).getroot() for p in directory.glob('TEST-*.xml')]
    assert suites and all(s.attrib['failures']==s.attrib['errors']=='0' for s in suites)
    assert any(s.attrib['name']=='com.example.apphear.p7dr2.P7dr2HarnessTest' for s in suites)
    return {'passed':True,'tests':sum(int(s.attrib['tests']) for s in suites),'suites':len(suites)}

def bootstrap() -> None:
    reference_check()
    tests=jvm_tests()
    with zipfile.ZipFile(APK) as z:
        names=[n for n in z.namelist() if n.endswith('/libp7dr2.so')]
        assert names==['lib/arm64-v8a/libp7dr2.so']
        packaged=hashlib.sha256(z.read(names[0])).hexdigest()
    save('p7dr2_jvm_tests.json',tests)
    save('p7dr2_build_identity.json',{'apk_sha256':sha(APK),'packaged_native_sha256':packaged,
         'sources':code_files(),'native_build':'NDK27.1.12297006 clang18.0.2 arm64-v8a API26 C++17 -O3 -fno-fast-math -ffp-contract=off -static-libstdc++',
         'production_behavior_changed':False,'build_configuration_changed':False,
         'packaging':'Android default src/debug/jniLibs only; no src/main or release configuration edits'})
    save('host_gate.json',{'authorized_run':'parity','jvm_tests_pass':True,'apk_sha256':sha(APK),'model_sha256':MODEL_SHA})
    print(json.dumps({'tests':tests,'apk':sha(APK),'packaged_native':packaged}))

def freeze() -> None:
    reference_check()
    result=json.loads((OUT/'parity_result.json').read_text())
    assert result['passed'],'Parity failed: NO TIMING'
    build=json.loads((OUT/'p7dr2_build_identity.json').read_text())
    assert build['sources']==code_files(),'Code changed since tested APK'
    assert not (OUT/'p7dr2_candidate_identity.json').exists()
    save('p7dr2_candidate_identity.json',{'frozen_before_timing':True,'files':code_files(),
         'apk_sha256':sha(APK),'model_sha256':MODEL_SHA,'native_parity_sha256':sha(OUT/'parity_result.json'),
         'protocol_sha256':sha(OUT/'p7dr2_benchmark_protocol.json'),'jvm_tests':jvm_tests(),
         'production_behavior_changed':False,'post_timing_edits_allowed':False})
    print('Candidate/source/APK/protocol freeze complete; no code changes now permitted')

def candidate_check() -> None:
    reference_check()
    c=json.loads((OUT/'p7dr2_candidate_identity.json').read_text())
    assert c['files']==code_files(),'FROZEN_SOURCE_CHANGED'
    assert c['native_parity_sha256']==sha(OUT/'parity_result.json')

def authorize(run: str) -> None:
    candidate_check()
    assert run in ['V0','V1','V2','V3','camera','integrated']
    assert not (OUT/f'{run}_result.json').exists(),'No retry/overwrite'
    if run in ['V1','V2','V3']:
        prev=json.loads((OUT/f'V{int(run[1])-1}_result.json').read_text())
        assert not prev['errors'] and prev['completed']>0
        assert all(m['thermal']==0 for m in prev['memory'])
    if run in ['camera','integrated']:
        assert json.loads((OUT/'p7dr2_compute_screen_result.json').read_text())['passed']
    if run=='integrated':
        assert not json.loads((OUT/'camera_result.json').read_text())['errors']
    save('host_gate.json',{'authorized_run':run,'jvm_tests_pass':True,'apk_sha256':sha(APK),
         'model_sha256':MODEL_SHA,'native_parity_verified':True,'candidate_frozen':True,
         'compute_pass_verified':run in ['camera','integrated']})
    print(adb('push',str(OUT/'host_gate.json'),REMOTE+'/host_gate.json'))

def capture_log(label: str) -> str:
    pid=adb('shell','pidof','com.example.apphear').strip()
    assert pid.isdigit()
    logs=adb('logcat','-d','--pid='+pid,'-s','P7DR2:I','tflite:I','AndroidRuntime:E')
    target=OUT/f'logcat_{label}.txt'
    assert not target.exists()
    target.write_text(logs,encoding='utf-8')
    return logs

def go(run: str) -> None:
    candidate_check()
    logs=capture_log(run+'_ready')
    assert f'READY run={run}' in logs
    assert re.search(r'Replacing 44 out of 44 node\(s\).*yielding 1 partitions',logs)
    target=f'go_{run}.json'
    assert not (OUT/target).exists()
    save(target,{'delegation_44_of_44':True,'apk_sha256':sha(APK),'model_sha256':MODEL_SHA})
    print(adb('push',str(OUT/target),REMOTE+'/'+target))

def stats(values: list[float]) -> dict:
    a=sorted(values)
    if not a:return {'count':0,'p50':None,'p90':None,'p95':None,'max':None}
    def q(f: float) -> float:
        x=(len(a)-1)*f;i=int(x);return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(x-i)
    return {'count':len(a),'p50':q(.5),'p90':q(.9),'p95':q(.95),'max':a[-1]}

VARIANT_NAMES=['p7dr2_v0_jvm_reference_result.json','p7dr2_v1_native_preprocess_result.json',
               'p7dr2_v2_native_decoder_result.json','p7dr2_v3_native_combined_result.json']

def collect(run: str) -> None:
    target=OUT/f'{run}_result.json'
    assert not target.exists()
    print(adb('pull',REMOTE+'/'+target.name,str(target)))
    capture_log(run+'_complete')
    r=json.loads(target.read_text())
    if run=='parity':
        for stage,name in [('preprocess','p7dr2_native_preprocess_parity.json'),('decoder','p7dr2_native_decoder_parity.json'),('combined','p7dr2_combined_parity.json')]:
            save(name,r.get(stage,{'passed':False,'executed':False,'reason':r.get('error','earlier failure')}))
        print(json.dumps(r,indent=2));return
    candidate_check()
    assert r['run']==run and r['model_sha256']==MODEL_SHA and r['threads']==2
    assert r['device']=='M2101K7AG' and r['soc']=='SM6150' and r['android']=='12'
    assert r['runtime']=='2.16.1' and r['precision']=='FP32' and r['provider']=='XNNPACK'
    rows=r['samples'];assert len(rows)==r['completed']
    assert all(r['measurement_start_ns']<=x['start_ns']<=x['end_ns']<=r['measurement_end_ns'] for x in rows)
    assert r['measurement_end_ns']-r['measurement_start_ns']==r['measured_seconds']*1e9
    assert r['completed_fps']==len(rows)/r['measured_seconds']
    metrics={key:stats([x[key] for x in rows]) for key in ['preprocess_ms','backend_native_ms','invoke_wall_ms','output_read_ms','decoder_ms','restore_ms','perception_ms']}
    metrics['combined_host_ms']=stats([x['preprocess_ms']+x['output_read_ms']+x['decoder_ms']+x['restore_ms'] for x in rows])
    valid=not r['errors'] and all(m['thermal']==0 for m in r['memory'])
    passed=bool(valid and rows and metrics['perception_ms']['p95']<=62.7532812 and r['completed_fps']>=15)
    summary={'run':run,'valid':valid,'completed':len(rows),'measured_seconds':r['measured_seconds'],
             'fps':r['completed_fps'],'latency_ms':metrics,'screen_pass':passed,'raw_sha256':sha(target),
             'errors':r['errors'],'thermal_peak':max(m['thermal'] for m in r['memory']),
             'peak_sampled_pss_kib':max(m['pss_kib'] for m in r['memory'])}
    if run.startswith('V'):
        assert r['warmup_seconds']==10 and r['measured_seconds']==30
        assert r['frame_metadata']=={'width':640,'height':480,'row_stride':2560,'pixel_stride':4,'rotation':270,'synthetic':True}
        save(VARIANT_NAMES[int(run[1])],summary)
        if run=='V3':save('p7dr2_compute_screen_result.json',{'passed':passed,'valid':valid,'p95_ms':metrics['perception_ms']['p95'],
              'fps':r['completed_fps'],'p95_limit_ms':62.7532812,'minimum_fps':15,'rounding_used_for_decision':False})
    else:
        summary.update({'capture_fps':r['capture_fps'],'analyzer_fps':r['analyzer_fps'],
                        'camera_metadata':r['camera_metadata'],'frame_metadata':r['frame_metadata']})
        captures=r['capture_rows']
        summary['frame_duration_ms']=stats([x[2]/1e6 for x in captures if x[2]>=0])
        summary['exposure_ms']=stats([x[3]/1e6 for x in captures if x[3]>=0])
        summary['sensor_gap_ms']=stats([(b[1]-a[1])/1e6 for a,b in zip(captures,captures[1:]) if a[1]>=0 and b[1]>=0])
        summary['active_ae_ranges']=sorted(set(tuple(x[4:6]) for x in captures))
        summary['requested_ae_ranges']=sorted(set(tuple(x[6:8]) for x in captures))
        summary['camera_cadence_status']='CAMERA_CADENCE_AT_OR_ABOVE_15' if min(r['capture_fps'],r['analyzer_fps'])>=15 else 'CAMERA_CADENCE_BELOW_15_CAUSE_NOT_ESTABLISHED'
        save(f'p7dr2_{run}_summary.json',summary)
    print(json.dumps(summary,indent=2))

def finalize() -> None:
    reference_check()
    parity=json.loads((OUT/'parity_result.json').read_text()) if (OUT/'parity_result.json').exists() else {'passed':False}
    names=['V0','V1','V2','V3','camera','integrated']
    raw={n:json.loads((OUT/f'{n}_result.json').read_text()) for n in names if (OUT/f'{n}_result.json').exists()}
    results={n:json.loads((OUT/VARIANT_NAMES[i]).read_text()) for i,n in enumerate(names[:4]) if (OUT/VARIANT_NAMES[i]).exists()}
    for i,n in enumerate(names[:4]):
        if n not in results:save(VARIANT_NAMES[i],{'executed':False,'reason':'Earlier gate incomplete or failed'})
    if (OUT/'p7dr2_candidate_identity.json').exists():candidate_check()
    classification='P7DR2_DEVICE_EXECUTION_PENDING';next_gate='PROJECT_LEAD_DEVICE_EXECUTION_REVIEW'
    if (OUT/'parity_result.json').exists() and not parity['passed']:
        classification='P7DR2_NATIVE_HOST_PARITY_FAILED';next_gate='PROJECT_LEAD_NATIVE_SEMANTIC_REVIEW'
    elif 'V3' in results:
        if not results['V3']['valid']:
            classification='P7DR2_RUNTIME_EVIDENCE_INCOMPLETE';next_gate='PROJECT_LEAD_RUNTIME_EVIDENCE_REVIEW'
        elif not results['V3']['screen_pass']:
            classification='P7DR2_NATIVE_HOST_PATH_BELOW_SCREEN';next_gate='PROJECT_LEAD_FAMILY_A_RUNTIME_CLOSURE_REVIEW'
        else:
            classification='P7DR2_NATIVE_HOST_COMPUTE_SCREEN_PASS';next_gate='PROJECT_LEAD_RUNTIME_CONFIRMATION_REVIEW'
            if 'integrated' in raw:
                integrated=json.loads((OUT/'p7dr2_integrated_summary.json').read_text())
                if not integrated['valid']:
                    classification='P7DR2_RUNTIME_EVIDENCE_INCOMPLETE';next_gate='PROJECT_LEAD_RUNTIME_EVIDENCE_REVIEW'
                elif integrated['screen_pass']:
                    classification='P7DR2_NATIVE_HOST_RUNTIME_SKELETON_FEASIBLE';next_gate='PROJECT_LEAD_P7E_ACCURACY_LABEL_READINESS_REVIEW'
                elif integrated['latency_ms']['perception_ms']['p95']<=62.7532812 and integrated['camera_cadence_status'].startswith('CAMERA_CADENCE_BELOW'):
                    next_gate='PROJECT_LEAD_CAMERA_CADENCE_REVIEW'
                else:
                    classification='P7DR2_NATIVE_HOST_INTEGRATED_BELOW_SCREEN';next_gate='PROJECT_LEAD_FAMILY_A_RUNTIME_CLOSURE_REVIEW'
    delta={}
    if 'V0' in results:
        for name,r in results.items():
            if name=='V0':continue
            delta[name]={}
            for metric in ['preprocess_ms','decoder_ms','combined_host_ms','perception_ms']:
                delta[name][metric]={}
                for q in ['p50','p95']:
                    a=results['V0']['latency_ms'][metric][q];b=r['latency_ms'][metric][q]
                    delta[name][metric][q]={'absolute_candidate_minus_V0_ms':b-a,'percentage_delta':100*(b-a)/a}
            a=results['V0']['fps'];delta[name]['fps_delta']={'absolute':r['fps']-a,'percentage':100*(r['fps']-a)/a}
    save('p7dr2_component_delta_summary.json',{'deltas':delta,'factor':'Host kernel implementation only; JNI marshaling included',
         'not_assumed_additive':True,'order_confound':'Fixed sequential order; descriptive within-session component comparison, not randomized trial'})
    memory={n:{'peak_sampled_pss_kib':max(x['pss_kib'] for x in r['memory']),
               'peak_sampled_native_heap_bytes':max(x['native_heap_bytes'] for x in r['memory']),
               'peak_sampled_java_heap_bytes':max(x['java_heap_bytes'] for x in r['memory']),
               'samples':r['memory']} for n,r in raw.items()}
    save('p7dr2_memory_summary.json',{'runs':memory,'sampling_seconds':5,'continuous_high_water_mark':False,'formal_ceiling':None})
    save('p7dr2_thermal_summary.json',{'runs':{n:{'start':r['memory'][0]['thermal'],'peak':max(x['thermal'] for x in r['memory']),'end':r['memory'][-1]['thermal']} for n,r in raw.items()},'zero_means':'NONE'})
    save('p7dr2_runtime_errors.json',{'runs':{n:r['errors'] for n,r in raw.items()},
         'OOM_observed':any('OutOfMemory' in str(r['errors']) for r in raw.values()),
         'crashes_observed':0 if raw and all(not r['errors'] for r in raw.values()) else None,
         'no_retries_after_timing':True,'no_source_changes_after_timing':True})
    partitions={}
    for p in OUT.glob('logcat_*_ready.txt'):
        matches=re.findall(r'Replacing (\d+) out of (\d+) node\(s\).*yielding (\d+) partitions',p.read_text())
        partitions[p.name]=[{'delegated':int(a),'total':int(b),'partitions':int(c),'fallback_nodes':int(b)-int(a)} for a,b,c in matches]
    save('p7dr2_provider_partitioning.json',{'provider':'TfLiteXNNPackDelegate','evidence':partitions,'per_operator_timing':'NOT_EXPOSED'})
    unchanged={'historical_artifacts_unchanged':True,'P7C_unchanged':True,'P7D_unchanged':True,'P7DR1_unchanged':True,
               'production_sources_unchanged':True,'context_unchanged':True,'progress_tracker_unchanged':True,
               'model_unchanged':True,'candidate_unchanged_after_timing':True,'production_behavior_changed':False}
    prohibited={k:False for k in ['training','teacher_extraction','recognizer_inference','accuracy_evaluation','D10','protected_replay',
                                'pristine_data','S5_changed','S7_changed','V2_changed','DWPose_changed','provider_sweep','thread_sweep',
                                'quantization','FP16','resolution_change','architecture_change','Family_B','automatic_R3']}
    save('p7dr2_integrity.json',{'integrity':'PASS',**unchanged,**prohibited,'model_sha256':MODEL_SHA,
         'progress_before':json.loads((OUT/'p7dr2_reference_identity.json').read_text())['files']['context/progress-tracker.md'],
         'progress_after':sha(ROOT/'context/progress-tracker.md'),'verified_protected_files':len(snapshot()),
         'JVM_tests':json.loads((OUT/'p7dr2_jvm_tests.json').read_text()),'native_parity':parity.get('passed'),
         'imprint':'Audit-only; new artifact documentation, no context edits'})
    save('p7dr2_android_changes_manifest.json',{'sources':code_files(),'production_behavior_changed':False,
         'build_gradle_changed':False,'debug_manifest':'Two new lines only; original remainder hash verified',
         'native_packaging':'src/debug/jniLibs/arm64-v8a only; no release implementation',
         'reference_sources_modified':False,'default_off':True})
    decision={'experiment':'P7D-R2_NATIVE_HOST_PATH_FEASIBILITY','classification':classification,'parity':parity.get('passed'),
              'next_gate':next_gate,'next_gate_executed':False,'production_authorized':False,'automatic_R3_authorized':False,
              'camera_executed':'camera' in raw,'integrated_executed':'integrated' in raw}
    save('p7dr2_decision.json',decision)
    save('APPHEAR_RECOGNITION_CANONICAL_STATE_P7DR2.json',{'parent':'APPHEAR_RECOGNITION_CANONICAL_STATE_P7DR1.json',
         'parent_sha256':sha(R1/'APPHEAR_RECOGNITION_CANONICAL_STATE_P7DR1.json'),
         'formal_P7DR1_status':'P7DR1_RUNTIME_PATH_REMEDIATION_BELOW_SCREEN','prior_results_reclassified':False,
         'architecture':'FA_DS_SPATIAL_V1','model_sha256':MODEL_SHA,'precision':'FP32','runtime':'2.16.1','provider':'XNNPACK','threads':2,
         'policy':'POLICY_UNCONFIGURED','recognition_accuracy':'NOT_ESTABLISHED',**decision,**prohibited})
    lines=['# P7D-R2 Native Host Path Feasibility', '',f'Classification: **{classification}**. Integrity PASS.',
      '', 'This gate changes only host execution of the frozen preprocessing/decoder kernels. No model, resolution, precision, provider or thread changes. Original P7D/R1 failures remain immutable.',
      '',f'Model SHA256: `{MODEL_SHA}`. Xiaomi M2101K7AG / SM6150 / Android12. TFLite2.16.1 FP32 XNNPACK2threads.',
      '', '## Parity and freeze', '',f'Untimed physical native parity: {parity.get("passed")}. See the144 preprocess,32 decoder,12 nonfinite and8 combined case ledgers. No tolerance was changed after results.',
      '', 'All variants and native/JVM tests were implemented before timing. Candidate identity freezes source, library, APK and protocol hashes. Compiler: installed NDK27.1 clang18.0.2, C++17, arm64/API26, -O3 -fno-fast-math -ffp-contract=off. No model export. Native library exists only in debug jniLibs; release sources/build configuration unchanged.',
      '', '## Compute results', '', '| Variant | Preprocess p50 | Decoder p50 | Complete p50 | Complete p95 | Loops/sec |', '|---|---:|---:|---:|---:|---:|']
    for n,r in results.items():
        m=r['latency_ms'];lines.append(f'|{n}|{m["preprocess_ms"]["p50"]:.8f}|{m["decoder_ms"]["p50"]:.8f}|{m["perception_ms"]["p50"]:.8f}|{m["perception_ms"]["p95"]:.8f}|{r["fps"]:.8f}|')
    lines += ['', 'Milliseconds; raw linear-interpolated percentiles.10s warmup/30s measured per variant in V0,V1,V2,V3 order. Synthetic640x480 RGBA row2560 pixel4 rotation270 with Java Random707, batch1 stream1. All complete-frame timestamps must fall inside the fixed window. Do not add stage percentiles to estimate complete-path percentiles.',
      '', 'Common output transfer remains in all variants. JNI marshaling/array access and copied readouts are INCLUDED in native decode/restore time, not hidden. V0 calls the immutable R1 classes. Native preprocessing retains bulk staging and the same caches/four-tap arithmetic; native decoding retains every finite check, spatial order, strict > tie, Double local3 and sigmoid, Float cast then restoration.',
      '', 'Component deltas (absolute and percentage versus same-session V0) are in p7dr2_component_delta_summary.json. Savings are not assumed additive; V3 alone determines the compute screen. Fixed order can confound device-state effects; these are bounded descriptive implementation comparisons, not generalized language benchmarks.',
      '', '## Camera / integrated', '',f'Camera executed: {"camera" in raw}. Integrated executed: {"integrated" in raw}. Camera settings, AE and frame delivery were not tuned. No recognition or S5/S7 execution.',
      '', 'Compute requires BOTH raw p95<=62.7532812ms and>=15 loops/sec. The inherited integrated gate requires30s warmup180s measured, same camera configuration; camera cadence remains separate. A compute pass alone is never a full product pass.']
    for n in ['camera','integrated']:
        p=OUT/f'p7dr2_{n}_summary.json'
        if p.exists():
            v=json.loads(p.read_text());lines += ['',f'{n}: capture FPS={v["capture_fps"]}, analyzer FPS={v["analyzer_fps"]}, completed FPS={v["fps"]}, p95={v["latency_ms"]["perception_ms"]["p95"]}; {v["camera_cadence_status"]}.',f'Actual source metadata: `{json.dumps(v["frame_metadata"])}`.']
    lines += ['', '## Interpretation and limits', '',
      ('V3 crossed the compute screen: native host execution makes the frozen compute path feasible on this device. This supports the host-execution hypothesis for this implementation; it does not prove intrinsic JVM limitations or accuracy.' if results.get('V3',{}).get('screen_pass') else 'V3 did not establish a passing compute path. Native speed differences must not be described as successful runtime rescue without both frozen conditions.'),
      '', 'Memory/PSS and thermal are sampled every5seconds, not continuous peak guarantees. No formal memory ceiling exists. Thermal protocol requires sampled NONE; non-NONE invalidates, no tuning/retry. Errors, completion logs and partition evidence are retained per run. Camera capture-minus-analyzer differences are only overwrite estimates, not exact internal CameraX counts.',
      '', 'Parity validates implementation equivalence on synthetic fixtures, not landmark/identity quality, calibrated confidence, recognition, S5 behavior or production readiness. Outputs remain POLICY_UNCONFIGURED. No D10, protected replay, pristine data, teacher extraction, training or Family B. Imprint records are confined to these new artifacts. The native compile is manual with the exact pinned command; no third-party native subsystem or provider was added.',
      '',f'Recommended next gate: **{next_gate}**. Next gate executed: NO. Production authorized: NO. No P7D-R3 is automatically authorized.']
    (OUT/'P7DR2_NATIVE_HOST_PATH_FEASIBILITY_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (OUT/'P7DR2_SOURCE_OF_TRUTH_INDEX.md').write_text('''# P7DR2 source of truth

Read report, decision and canonical state first. Frozen reference identities preserve prior findings.

| Claim | Source | Status |
|---|---|---|
| Frozen preprocessing/readout | P7C p7c_input_preprocessing_contract.json and p7c_native_readout_contract.json | Immutable |
| R1 reference | android/app/src/debug/java/com/example/apphear/p7dr1/P7dr1Math.kt | Unchanged, hashed |
| Native implementation | android/app/src/debug/cpp/p7dr2.cpp | Candidate identity frozen |
| Coarse JNI and variant dispatch | android/app/src/debug/java/com/example/apphear/p7dr2/P7dr2Native.kt | Candidate identity frozen |
| Parity corpus | same directory/P7dr2Parity.kt; parity_result.json | Untimed physical tests |
| Timing/gates | same directory/P7dr2RuntimeActivity.kt; p7dr2_benchmark_protocol.json | Frozen before timing |
| Model/runtime identities | p7dr2_reference_identity.json, p7dr2_candidate_identity.json, p7dr2_build_identity.json | SHA256 |
| Variant results | V0_result.json through V3_result.json and p7dr2_v*_result.json | Measured only when present |
| Actual delegation | logcat_*_ready.txt; p7dr2_provider_partitioning.json | Not inferred from enable flag |
| Component effects | p7dr2_component_delta_summary.json | Same-session, fixed-order descriptive |
| Governance | p7dr2_integrity.json; p7dr2_android_changes_manifest.json | Before/after hashes |
| Evidence calculations | model/p7dr2_evidence.py | Frozen before timing |

External primary references inspected: [Android JNI guidance](https://developer.android.com/ndk/guides/jni-tips), [Android native packaging/build](https://developer.android.com/studio/projects/gradle-external-native-builds), [Clang floating-point behavior](https://clang.llvm.org/docs/UsersManual.html#controlling-floating-point-behavior). These support implementation choices, not device performance claims.
''',encoding='utf-8')
    save('artifact_hash_manifest.json',{'self_excluded':True,'algorithm':'SHA256','artifacts':[
        {'path':p.relative_to(OUT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='artifact_hash_manifest.json']})
    print(json.dumps(decision,indent=2))

if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='bootstrap':bootstrap()
    elif sys.argv[1]=='freeze':freeze()
    elif sys.argv[1]=='authorize':authorize(sys.argv[2])
    elif sys.argv[1]=='go':go(sys.argv[2])
    elif sys.argv[1]=='collect':collect(sys.argv[2])
    elif sys.argv[1]=='finalize':finalize()
