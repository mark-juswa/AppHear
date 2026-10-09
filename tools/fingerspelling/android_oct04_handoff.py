"""Save a private local binary and credential-free source recovery snapshot."""
import hashlib
import json
import shutil
import subprocess
import zipfile
from tools.fingerspelling.android_oct04_port import DEST, OUT

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    target=OUT/"handoff_2026-10-05"; target.mkdir(exist_ok=True)
    artifacts={}
    for origin,name in [
        (DEST/"android/app/build/outputs/apk/debug/app-debug.apk","app-debug-private-capture-clarity.apk"),
        (DEST/"android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk","app-debug-androidTest.apk"),
    ]:
        dest=target/name
        if not dest.exists() or digest(origin)!=digest(dest): shutil.copyfile(origin,dest)
        artifacts[name]={"sha256":digest(dest),"bytes":dest.stat().st_size}
    patch=subprocess.check_output(["git","diff","--binary","HEAD","--","android","context/feature-schema.md","context/progress-tracker.md"],cwd=DEST)
    (target/"integration.patch").write_bytes(patch)
    paths=[]
    for kind in ("main","test","androidTest"):
        paths.extend((DEST/f"android/app/src/{kind}/java/com/example/apphear/fingerspelling").glob("*.kt"))
    paths.extend(DEST/p for p in ["android/app/build.gradle.kts","android/app/src/main/java/com/example/apphear/RecognitionActivity.kt","android/app/src/main/java/com/example/apphear/perceptionvnext/Candidate01FrameAnalyzer.kt","context/feature-schema.md","context/progress-tracker.md","docs/apphear-fingerspelling-android-oct04-integration-2026-10-04.md","docs/apphear-fingerspelling-next-session-handoff-2026-10-05.md"])
    source_identity={}
    with zipfile.ZipFile(target/"source_snapshot.zip","w",zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            name=path.relative_to(DEST).as_posix(); archive.write(path,name); source_identity[name]=digest(path)
    report={"schema_version":"apphear.fingerspelling.next_session_handoff.v1","application_baseline":"cee71d9f181695847936eb5f3605ea37eab82a95","source_worktree":str(DEST),"private_apks_local_only":True,"revised_apk_installed":False,"artifacts":artifacts,"source_sha256":source_identity,"source_snapshot_sha256":digest(target/"source_snapshot.zip"),"patch_sha256":digest(target/"integration.patch"),"completed_live_sessions":0,"prior_live_attempt":"OPEN_CAPTURE_RESOURCE_LIMIT_ABORT","signing_quality":"USER_SELF_REPORTED_IMPERFECT_NOT_ACCURACY_BENCHMARK"}
    (target/"handoff_manifest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"handoff":str(target),"artifacts":artifacts,"source_files":len(source_identity)},indent=2))

if __name__=="__main__": main()
