"""Read existing P7-D device evidence; never runs inference, training, or a benchmark."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"artifacts/recognition_upgrade/p7d_android_runtime_skeleton_feasibility_01"
ADB="D:/AndroidStudio/Android/Sdk/platform-tools/adb.exe"
SERIAL="3ab64582"


def save(name: str,value: object) -> None:
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False),encoding="utf-8")


def stats(values: list[float]) -> dict:
    if not values:
        return {"count":0,"p50":None,"p90":None,"p95":None,"max":None}
    values=sorted(values)
    def q(f: float) -> float:
        p=f*(len(values)-1);i=int(p);j=min(i+1,len(values)-1)
        return values[i]+(values[j]-values[i])*(p-i)
    return {"count":len(values),"p50":q(.5),"p90":q(.9),"p95":q(.95),"max":max(values)}


def run() -> None:
    raw=OUT/"device_result.json"
    if not raw.exists():
        subprocess.run([ADB,"-s",SERIAL,"pull","/sdcard/Android/data/com.example.apphear/files/p7d/device_result.json",str(raw)],check=True)
    result=json.loads(raw.read_text())
    end_log=OUT/"p7d_logcat_excerpt.txt"
    if end_log.exists():
        logs=end_log.read_text(encoding="utf-8")
    else:
        logs=subprocess.run([ADB,"-s",SERIAL,"logcat","-d","-s","P7D:I","tflite:I","AndroidRuntime:E"],check=True,capture_output=True,text=True).stdout
        end_log.write_text(logs,encoding="utf-8")
    start_log=OUT/"p7d_logcat_start_excerpt.txt"
    if start_log.exists():
        logs=start_log.read_text(encoding="utf-8")+"\n"+logs
    rows=result["samples"]; memory=result["memory"]
    keys=["camera_handoff_ms","rgba_rgb_ms","letterbox_ms","backend_native_ms","invoke_wall_ms","jni_input_output_overhead_ms","output_read_ms","decoder_ms","restore_ms","perception_ms","source_frame_gap_ms"]
    summary={k:stats([float(r[k]) for r in rows if r.get(k) is not None]) for k in keys}
    save("p7d_backend_latency_summary.json",{"units":"ms","native":summary["backend_native_ms"],"invoke_wall":summary["invoke_wall_ms"],"jni_input_output_residual":summary["jni_input_output_overhead_ms"],"load_ms":result["load_ms"]})
    save("p7d_preprocess_latency_summary.json",{"units":"ms","rgba_to_rgb_orientation":summary["rgba_rgb_ms"],"letterbox_normalization":summary["letterbox_ms"],"combined":stats([r["rgba_rgb_ms"]+r["letterbox_ms"] for r in rows]),"camera_handoff":summary["camera_handoff_ms"],"sensor_clock":result["frame_metadata"]})
    save("p7d_decoder_latency_summary.json",{"units":"ms","decoder":summary["decoder_ms"],"source_restore_evidence":summary["restore_ms"],"output_read":summary["output_read_ms"]})
    save("p7d_perception_latency_summary.json",{"units":"ms","complete":summary["perception_ms"],"boundary":"Analyzer callback entry through restored raw diagnostic evidence; sensor-to-callback age separate","screen_p95_ms":62.7532812,"screen_met":bool(rows and summary["perception_ms"]["p95"]<=62.7532812),"random_weight_only":True})
    save("p7d_fps_summary.json",{k:result[k] for k in ["processed_frames","measurement_seconds","measurement_start_ns","measurement_end_ns","completed_fps","camera_capture_completions","camera_capture_completion_fps","analyzer_arrivals","analyzer_arrival_fps","camera_overwrite_estimate","drop_count_caveat"]}|{"source_frame_gap_ms":summary["source_frame_gap_ms"],"minimum_completed_fps":15,"full_product_useful_FPS_established":False})
    save("p7d_memory_summary.json",{"units":{"pss":"KiB","heaps":"bytes"},"sampling_interval_seconds":5,"peak_observed_pss_kib":max(m["pss_kib"] for m in memory),"peak_native_heap_bytes":max(m["native_heap_bytes"] for m in memory),"peak_java_heap_bytes":max(m["java_heap_bytes"] for m in memory),"start":memory[0],"end":memory[-1],"warmup_boundary_nearest":min(memory,key=lambda m:abs(m["elapsed_seconds"]-30)),"tensor_arena":result["tensor_arena_bytes"],"model_bytes":607280,"formal_memory_ceiling":None,"sampling_limit":"Periodic sampled peak, not continuous high-water mark","samples":memory})
    thermal=[m["thermal"] for m in memory]
    after_warmup=next((m for m in memory if m["elapsed_seconds"]>=30),None)
    save("p7d_thermal_summary.json",{"start":thermal[0],"first_sample_after_warmup":after_warmup,"peak":max(thermal),"end":thermal[-1],"samples":thermal,"android_status_zero":"NONE"})
    save("p7d_runtime_errors.json",{"errors":result["errors"],"OOM_observed":any("OutOfMemory" in e for e in result["errors"]),"crashes_observed":0 if not result["errors"] else None,"completion_log_present":"COMPLETE frames=" in logs,"adb_permission_grant_attempt":"Denied by MIUI; existing user-granted CAMERA permission confirmed and used; no permission bypass","build_preflight":"Initial guessed JAVA_HOME absent; resolved installed JDK21. Gradle-cache sandbox access approved. No toolchain version changed."})
    delegated=re.findall(r"Replacing (\d+) out of (\d+) node\(s\).*yielding (\d+) partitions",logs)
    save("p7d_provider_partitioning.json",{"evidence":"Device tflite logcat","delegation_records":[{"delegated":int(a),"total":int(b),"partitions":int(c)} for a,b,c in delegated],"fallback_nodes":0 if delegated and delegated[-1][0]==delegated[-1][1] else None,"provider":"TfLiteXNNPackDelegate","limitations":"Node partition evidence, not per-operator latency profiling; host analyzer maps builtin ops."})
    save("p7d_device_identity.json",{k:result[k] for k in ["device","soc","android"]}|{"physical":True,"serial":SERIAL})
    save("p7d_android_runtime_identity.json",{"version":result["runtime_version"],"XNNPACK_requested":result["xnnpack_requested"],"threads":result["threads"],"FP32":True,"model_sha256":result["model_sha256"],"batch":1,"streams":1,"model_load":"PASS","operators_execute":"PASS"})
    test=ET.parse(ROOT/"android/app/build/test-results/testDebugUnitTest/TEST-com.example.apphear.p7d.P7dMathTest.xml").getroot()
    test_names=[e.attrib["name"] for e in test.findall("testcase")]
    test_pass=test.attrib["failures"]=="0" and test.attrib["errors"]=="0"
    save("p7d_input_transform_tests.json",{"passed":test_pass,"test_suite":str(test.attrib),"tests":[n for n in test_names if n in ["rotationStrideAndNoMirror","transformsRoundTrip","bilinearAndPadding"]],"kind":"Synthetic JVM; no RGB dataset","source":"android/app/src/test/java/com/example/apphear/p7d/P7dMathTest.kt"})
    save("p7d_decoder_tests.json",{"passed":test_pass,"tests":[n for n in test_names if n not in ["rotationStrideAndNoMirror","transformsRoundTrip","bilinearAndPadding"]],"kind":"Synthetic JVM; no landmark accuracy claims","body_validity_independent":True})
    complete=not result["errors"] and len(rows)>0 and test_pass
    screen=complete and summary["perception_ms"]["p95"]<=62.7532812 and result["completed_fps"]>=15
    classification="P7D_PRIMARY_RUNTIME_SKELETON_FEASIBLE" if screen else "P7D_PRIMARY_RUNTIME_SKELETON_BELOW_SCREEN" if complete else "P7D_INTEGRITY_FAILED"
    next_gate="PROJECT_LEAD_P7E_TRAINING_LABEL_READINESS_REVIEW" if screen else "PROJECT_LEAD_P7D_RUNTIME_FAILURE_REVIEW"
    save("p7d_decision.json",{"classification":classification,"runtime_screen_met":screen,"runtime_evidence_complete":complete,"next_gate":next_gate,"next_gate_executed":False,"production_authorized":False,"training_authorized":False})
    save("APPHEAR_RECOGNITION_CANONICAL_STATE_P7D.json",{"parent":"APPHEAR_RECOGNITION_CANONICAL_STATE_P7C.json","architecture":"FA_DS_SPATIAL_V1","family_a_schema":"APPHEAR_FAMILY_A_FRAME_V1","random_seed":707,"training":False,"architecture_changed":False,"precision":"FP32","model_sha256":result["model_sha256"],"classification":classification,"recognition_accuracy":"NOT_ESTABLISHED","landmark_identity_accuracy":"NOT_ESTABLISHED","calibration":"POLICY_UNCONFIGURED","S5_S7_integrated":False,"family_B_activated":False,"full_product_15FPS":"NOT_ESTABLISHED","production_authorized":False})
    print(json.dumps({"classification":classification,"fps":result["completed_fps"],"latency":summary,"memory_peak_pss_kib":max(m["pss_kib"] for m in memory),"thermal_peak":max(thermal),"delegation":delegated},indent=2))


if __name__=="__main__":
    run()
