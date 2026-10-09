"""Read only fingerspelling diagnostics and verify the October 4 preservation gate."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from tools.fingerspelling.android_oct04_port import DEST, OUT

def command(adb, *args):
    return subprocess.check_output([adb, *args], text=True).strip()

def preservation():
    before=json.loads((OUT / "baseline_hashes.json").read_text())
    changed=[p for p,h in before.items() if hashlib.sha256((DEST/p).read_bytes()).hexdigest()!=h]
    allowed={"android/app/build.gradle.kts", "android/app/src/main/java/com/example/apphear/RecognitionActivity.kt", "android/app/src/main/java/com/example/apphear/perceptionvnext/Candidate01FrameAnalyzer.kt"}
    report={"baseline":"cee71d9f181695847936eb5f3605ea37eab82a95", "files_checked":len(before), "changed_existing_files":changed, "unexpected":sorted(set(changed)-allowed)}
    (OUT/"preservation.json").write_text(json.dumps(report,indent=2))
    assert not report["unexpected"], report
    print(json.dumps(report,indent=2))

def pull(adb):
    devices=[s.split()[0] for s in command(adb,"devices").splitlines()[1:] if "\tdevice" in s]
    wireless=[s for s in devices if s.startswith("adb-3ab64582-")]
    serial="3ab64582" if "3ab64582" in devices else (wireless[0] if len(wireless)==1 else None)
    assert serial, "Connect/authorize the known Xiaomi; no other phone is selected"
    def phone(*args): return command(adb,"-s",serial,*args)
    dest=OUT/"phone"; dest.mkdir(exist_ok=True)
    for name in ("fingerspell_parity.json","fingerspell_word_cadence.json"):
        result=subprocess.run([adb,"-s",serial,"shell","run-as","com.example.apphear","cat",f"files/{name}"],capture_output=True,text=True)
        if result.returncode==0:
            (dest/name).write_text(json.dumps(json.loads(result.stdout),indent=2))
    listing=subprocess.run([adb,"-s",serial,"shell","run-as","com.example.apphear","ls","files/fingerspelling_sessions"],capture_output=True,text=True)
    sessions=[]; failures=[]
    for name in sorted(listing.stdout.splitlines()):
        if not re.fullmatch(r"(?:failed_)?session_\d+\.json",name): continue
        report=json.loads(phone("shell","run-as","com.example.apphear","cat",f"files/fingerspelling_sessions/{name}"))
        (dest/name).write_text(json.dumps(report,indent=2))
        if name.startswith("failed_"):
            failures.append({"file":name, **report}); continue
        sessions.append({"file":name,"observations":report["observations"],"cadence":report["observations_per_second"],"raw_prediction":report["raw_prediction"],"finish_ms":report["finish_ms"],"retained_slots":report["retained_slots"],"expected_transcript":"REQUIRES_HUMAN_SESSION_LINKAGE"})
    summary={"schema_version":"apphear.fingerspelling.android_live_inventory.v1", "sessions":sessions, "failed_sessions":failures, "live_accuracy_claim":"NONE", "test_payload_accessed":False}
    (dest/"summary.json").write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2))

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("action",choices=["preservation","pull"])
    parser.add_argument("--adb",default=r"D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe")
    args=parser.parse_args()
    if args.action=="preservation": preservation()
    else: pull(args.adb)

if __name__=="__main__": main()
