"""Port the reviewed additive integration onto the October 4 application baseline."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DEST = Path(r"C:\Users\Gigabyte\.codex\worktrees\fingerspell-oct04-integration\5. Apphear3")
OUT = ROOT / "artifacts/fingerspelling_android_01/oct04"
BASE = "cc1f3949114d0ed1dab38d4428191151b37df358"
TARGET = "cee71d9f181695847936eb5f3605ea37eab82a95"

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=DEST, text=True).strip() == TARGET
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=DEST)
    tracked = subprocess.check_output(["git", "ls-files", "android"], cwd=DEST, text=True).splitlines()
    before = {p: hashlib.sha256((DEST / p).read_bytes()).hexdigest() for p in tracked}
    (OUT / "baseline_hashes.json").write_text(json.dumps(before, indent=2))
    paths = ["android/app/build.gradle.kts", "android/app/src/main/java/com/example/apphear/RecognitionActivity.kt", "android/app/src/main/java/com/example/apphear/perceptionvnext/Candidate01FrameAnalyzer.kt"]
    for index, path in enumerate(paths):
        old = OUT / f"{index}.base"
        ours = OUT / f"{index}.ours"
        theirs = OUT / f"{index}.theirs"
        old.write_bytes(subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT))
        ours.write_bytes((ROOT / path).read_bytes())
        theirs.write_bytes((DEST / path).read_bytes())
        result = subprocess.run(["git", "merge-file", "-p", str(ours), str(old), str(theirs)], capture_output=True)
        (DEST / path).write_bytes(result.stdout)
        print(path, "merge_result", result.returncode)
    for kind in ("main", "test", "androidTest"):
        rel = Path(f"android/app/src/{kind}/java/com/example/apphear/fingerspelling")
        shutil.copytree(ROOT / rel, DEST / rel)
    shutil.copyfile(ROOT / "android/local.properties", DEST / "android/local.properties")
    print("destination", DEST)

if __name__ == "__main__":
    main()
