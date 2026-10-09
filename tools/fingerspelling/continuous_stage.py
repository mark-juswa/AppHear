"""Stage the validated manual integration onto the approved October 5 baseline."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(r"F:\ASL DATASET\5. Apphear3")
OLD = Path(r"C:\Users\Gigabyte\.codex\worktrees\fingerspell-oct04-integration\5. Apphear3")
NEW = Path(r"C:\Users\Gigabyte\.codex\worktrees\fingerspell-continuous-oct05\5. Apphear3")
OUT = ROOT / "artifacts/fingerspelling_continuous_01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "preservation_before.json").exists():
        raise RuntimeError(
            "Already staged: preserve the original inventory and use the build wrapper."
        )
    inventory = {}
    for label, root in (("baseline", NEW), ("manual", OLD)):
        inventory[label] = {
            str(p.relative_to(root)).replace("\\", "/"): sha(p)
            for folder in ("android/app/src", "android/app/build.gradle.kts")
            for p in ([root / folder] if (root / folder).is_file() else (root / folder).rglob("*"))
            if p.is_file()
        }
    (OUT / "preservation_before.json").write_text(json.dumps(inventory, indent=2))
    files = [
        "android/app/build.gradle.kts",
        "android/local.properties",
        "android/app/src/main/java/com/example/apphear/RecognitionActivity.kt",
        "android/app/src/main/java/com/example/apphear/perceptionvnext/Candidate01FrameAnalyzer.kt",
    ]
    folders = [
        "android/app/src/main/java/com/example/apphear/fingerspelling",
        "android/app/src/test/java/com/example/apphear/fingerspelling",
        "android/app/src/androidTest/java/com/example/apphear/fingerspelling",
        "android/app/src/test/resources/fingerspell_beam",
    ]
    for relative in files:
        target = NEW / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OLD / relative, target)
    for relative in folders:
        shutil.copytree(OLD / relative, NEW / relative, dirs_exist_ok=True)
    assets = ROOT / "artifacts/fingerspelling_single_letter_01"
    for relative in ("android_assets", "parity_assets"):
        shutil.copytree(assets / relative, OUT / relative, dirs_exist_ok=True)
    print(
        json.dumps(
            {
                "target": str(NEW),
                "baseline": "b48594c4942d9e9ac0d94ff96396e80b9f049c0a",
                "staged_manual_integration": True,
                "models_changed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
