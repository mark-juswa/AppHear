"""Record the protected FINGERSPELL baseline and prove which files the practical v1 change touched.

Every git-tracked file under android/app/src and packages/fingerspelling_continuous_v2_1_01 is
hashed at the base commit (git blob) and in the working tree. The record lists the changed
files; every other file (all WORD/S2/Candidate01/materializer/SentenceBuilder/asset files)
must be byte-identical.

    python -m tools.fingerspelling.practical_baseline_record --base 098f3682 --out <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOTS = (
    "android/app/src",
    "android/app/build.gradle.kts",
    "packages/fingerspelling_continuous_v2_1_01",
)
# Shared files whose edits are FINGERSPELL-only by construction (line-level reasons: audit report).
ALLOWED_SHARED = {
    "android/app/build.gradle.kts",
    "android/app/src/main/java/com/example/apphear/RecognitionActivity.kt",
    "android/app/src/main/java/com/example/apphear/coordination/RecognitionCoordinationBridge.kt",
    # Portrait lock for the shared recognition screen (user decision; behind -PrecognitionPortrait).
    "android/app/src/main/AndroidManifest.xml",
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    base = git("rev-parse", args.base).strip()
    tracked = {}
    for line in git("ls-tree", "-r", base, "--", *ROOTS).splitlines():
        meta, path = line.split("\t", 1)
        tracked[path] = meta.split()[2]
    missing = [path for path in sorted(tracked) if not Path(path).exists()]
    # git's own comparison (refreshes the stat cache, applies the repository's eol/LFS filters).
    git("update-index", "-q", "--really-refresh")
    changed = sorted(git("diff", "--name-only", base, "--", *ROOTS).split())
    # Packaged assets must also be byte-identical to the committed blobs (not just eol-equivalent).
    asset_bytes_differ, asset_eol_only = [], []
    for path, sha in sorted(tracked.items()):
        if "/assets/" in path and path not in changed and Path(path).exists():
            blob_bytes = subprocess.run(
                ["git", "cat-file", "blob", sha], check=True, capture_output=True
            ).stdout
            data = Path(path).read_bytes()
            if data != blob_bytes:
                crlf, lf = b"\r\n", b"\n"
                eol_only = data.replace(crlf, lf) == blob_bytes.replace(crlf, lf)
                (asset_eol_only if eol_only else asset_bytes_differ).append(path)
    added = sorted(
        line[3:]
        for line in git("status", "--porcelain", "--untracked-files=all", "--", *ROOTS).splitlines()
        if line.startswith("??")
    )
    fingerspell_only = all("/fingerspelling/" in c or c in ALLOWED_SHARED for c in changed)
    package = Path("packages/fingerspelling_continuous_v2_1_01/android_assets/fingerspelling")
    record = {
        "schema": "apphear.fingerspelling.practical_baseline_record.v1",
        "base_commit": base,
        "protected_baseline": {
            "fingerspell_package": "packages/fingerspelling_continuous_v2_1_01",
            "package_sha256": {
                f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                for f in sorted(package.iterdir())
            },
            "candidate_id": json.loads((package / "model_manifest.json").read_text())[
                "candidate_id"
            ],
            "policy": json.loads((package / "continuous_policy.json").read_text()),
            "decoder": "apphear.fingerspelling.single_letter_ctc.v1 (blank27 penalty 0.5)",
            "build_flags": "-Pfingerspell -PfingerspellContinuous + locked WORD_BLEND_02 set",
            "phone_app_preserved": "previous debug build app sha 0469d1b8... (not reinstalled)",
        },
        "tracked_files_checked": len(tracked),
        "changed_files": changed,
        "missing_files": missing,
        "added_files": added,
        "unchanged_files": len(tracked) - len(changed) - len(missing),
        "packaged_asset_content_differs_from_commit": asset_bytes_differ,
        "packaged_asset_checkout_eol_only": asset_eol_only,
        "changes_fingerspell_only_or_justified_shared": fingerspell_only
        and not missing
        and not asset_bytes_differ,
        "package_unchanged": not any(c.startswith("packages/") for c in changed),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: v for k, v in record.items() if k != "protected_baseline"}, indent=1))


if __name__ == "__main__":
    main()
