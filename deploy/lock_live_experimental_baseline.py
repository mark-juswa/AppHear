"""Lock (or verify) the live-tested Android recognition baseline of 2026-10-17.

The baseline is the debug app that was installed with ``adb install -r`` and verified live with both
engines: STABLE (S2-R2 + production lifecycle) and EXPERIMENTAL (S2-R3 Arm A e10 + confirm-boundary
0.7), sharing Candidate01, the materializer, the frozen Recognition V2 236-class WORD model and
SentenceBuilder. The source changes were uncommitted on top of e2444ebb when it was tested.

``--write`` records, in ``docs/audit/baselines/live_experimental_2026-10-17.json``:
  * git HEAD/branch and the sha256 of every changed or untracked source file it depends on;
  * sha256/size of the debug and androidTest APKs and of every recognition asset inside the APK,
    each cross-checked against the same file in the source tree;
  * the two engine definitions and the build command (blank credentials, no gradle.properties keys);
  * the device evidence (logcat of the live session, copied next to the archive).
It also copies the APKs, the logcat and a zip snapshot of the changed files to
``<data root>/artifacts/live_baselines/experimental_live_20261017/`` (ignored by git), so the exact
build survives later rebuilds of ``android/app/build``.

``--verify`` recomputes everything that still exists and reports any drift (exit 1 on drift).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path("F:/ASL DATASET/5. Apphear3")
MANIFEST = ROOT / "docs/audit/baselines/live_experimental_2026-10-17.json"
ARCHIVE = DATA_ROOT / "artifacts/live_baselines/experimental_live_20261017"
APK = ROOT / "android/app/build/outputs/apk/debug/app-debug.apk"
TEST_APK = ROOT / "android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"
BASE_COMMIT = "e2444ebb7910a8e17de22b3b17678fecfaf8f5be"
# Files outside the baseline (local preview config of another session).
EXCLUDED = {".claude/launch.json"}
# Recognition assets the live path loads (S2 packages, Candidate01, WORD); hashed inside the APK.
ASSET_PREFIXES = (
    "assets/phone_causal_recognition_01/",
    "assets/perception_vnext/",
    "assets/phase4a_gate4a1_live/",
    "assets/phase4a_gate2_recognizer_parity/manifest.json",
    "assets/phase4a_gate2_recognizer_parity/ordinary_v2_tcn_fp32.tflite",
    "assets/vocab.json",
    "assets/recognition_config.json",
    "assets/recognition_coordination_policy.json",
    "assets/context_phrase_assist_policy.json",
)
SOURCE_ASSET_DIRS = (ROOT / "android/app/src/main", ROOT / "android/app/src/debug")
ENGINES = {
    "STABLE": {
        "default": True,
        "s2_package": "S2_R2_CANDIDATE (BuildConfig.APP_PHONE_S2_PACKAGE, debug default)",
        "decoder": "PhoneDecoderConfig(rearm=PRE_OR_POST_EXPERIMENTAL, admission=PASS_THROUGH, "
        "confirmBoundaryPostPeak=null)",
    },
    "EXPERIMENTAL": {
        "default": False,
        "debug_only": True,
        "s2_package": "ARM_A_E10_CANDIDATE (debug asset s2_r3_arm_a_e10_candidate)",
        "decoder": "PhoneDecoderConfig(rearm=PRE_OR_POST_EXPERIMENTAL, admission=PASS_THROUGH, "
        "confirmBoundaryPostPeak=0.7)",
        "fallback": "load failure -> STABLE (fallbackReason set, logged)",
    },
    "shared": [
        "Candidate01 (DWPose-T + MediaPipe hand refiner, presence>=0.50, >=18 joints)",
        "decoder timings minActive 133.308 / preGapReset 133.308 / postConfirm 266.616 / "
        "rearm 399.924 ms",
        "Recognition Window Materializer +/-250 ms",
        "Recognition V2 [96,350] -> ordinary_v2_tcn_fp32.tflite, 236 classes (sha 1ccf0afa...)",
        "SentenceBuilder, Context Assist and FINGERSPELL unchanged",
    ],
    "selection": "debug Settings 'Recognition engine (debug)'; "
    "SharedPreferences recognition_engine/selected; "
    "read once per ASL Recognition screen open (one PhoneProductionSession)",
}
BUILD = {
    "working_directory": "android/ (PowerShell; Bash cannot run gradlew.bat with the space "
    "in the path)",
    "tasks": ["testDebugUnitTest", "assembleDebug", "assembleDebugAndroidTest", "--continue"],
    "properties": [
        "-Pandroid.useAndroidX=true",
        "-Pfingerspell=true",
        "-PfingerspellContinuous=true",
        "-PfingerspellArtifactDir=<data root>/packages/fingerspelling_continuous_v2_1_01",
        "-PrecognitionRearCamera=true",
        "-PrecognitionCoordination=true",
        "-PcontextPhraseAssist=true",
        "-PcontextPhraseAssistProvider=fake",
        "-PaslAssetPilot=true",
        "-PaslSharedCharacter=true",
        "-PaslMoreWords=true",
        "-PaslCharacterSelection=true",
        "-PaslNewIdle=true",
        "-PaslAlphabetFallback=true",
        "-PaslOriginalWords=true",
        "-PperceptionVNext=true",
        "-PphoneCausalRecognition=true",
        "-PrecognitionV3ParallelHands=false",
        "-PrecognitionV3Profile=false",
    ],
    "blank_credentials": [
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "APPHEAR_SUPABASE_URL",
        "APPHEAR_SUPABASE_ANON_KEY",
        "APPHEAR_ELEVENLABS_MODEL_ID",
        "APPHEAR_ELEVENLABS_VOICE_ID",
        "APPHEAR_ELEVENLABS_API_KEY",
        "APPHEAR_CONTEXT_ASSIST_API_KEY",
        "APPHEAR_GEMINI_API_KEY",
    ],
    "note": "every credential is passed as -P<name>= (blank); the worktree gradle.properties "
    "holds no keys",
}
DEVICE = {
    "device": "Xiaomi M2101K7AG (serial 3ab64582), Android 12 / SDK 31",
    "install": "adb install -r app-debug.apk and app-debug-androidTest.apk; "
    "firstInstallTime 2026-10-15 20:28:05 "
    "unchanged, lastUpdateTime 2026-10-17 22:54:11; shared_prefs kept",
    "instrumented": "am instrument PhoneS2ParityInstrumentedTest: OK (4 tests) incl. "
    "armAE10PhonePrefixMatchesKeras...",
    "live_stable": "configuration=STABLE package=S2_R2_CANDIDATE fallback=false; "
    "2 commits (HELLO, HELLO), 6-8 fps",
    "live_experimental": "configuration=EXPERIMENTAL package=ARM_A_E10_CANDIDATE "
    "fallback=false; 10 commits, "
    "event ids restart at 1; 5-7.6 fps",
    "not_verified": [
        "SPLIT_CONFIRM_BOUNDARY never fired live (JVM parity only)",
        "forced Experimental load failure on device",
        "accuracy (developer signer, unblinded)",
    ],
    "user_feedback_2026-10-17": "Experimental substantially more responsive and easier to sign "
    "quickly; word accuracy inconsistent",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True
    ).stdout


def changed_files() -> list[str]:
    """Tracked changes against BASE_COMMIT plus untracked files, minus the manifest outputs."""
    tracked = git("diff", "--name-only", BASE_COMMIT).split()
    untracked = git("ls-files", "--others", "--exclude-standard").split()
    own = {
        MANIFEST.relative_to(ROOT).as_posix(),
        Path(__file__).resolve().relative_to(ROOT).as_posix(),
    }
    return sorted({p for p in tracked + untracked if p not in EXCLUDED and p not in own})


def apk_assets(apk: Path) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    with zipfile.ZipFile(apk) as z:
        for info in z.infolist():
            if info.filename.startswith(ASSET_PREFIXES):
                out[info.filename] = {"sha256": sha256_bytes(z.read(info)), "bytes": info.file_size}
    return out


def source_asset(name: str) -> Path | None:
    rel = name.removeprefix("assets/")
    hits = [d / "assets" / rel for d in SOURCE_ASSET_DIRS if (d / "assets" / rel).is_file()]
    return hits[0] if len(hits) == 1 else None


BASELINE_ID = "LIVE_EXPERIMENTAL_2026-10-17"
LOGCAT_NAME = "live_logcat_2026-10-17.txt"
BLEND_ENGINE = {
    "default": False,
    "debug_only": True,
    "s2_package": "ARM_A_E10_CANDIDATE (identical to EXPERIMENTAL)",
    "decoder": "identical to EXPERIMENTAL (confirmBoundaryPostPeak=0.7)",
    "word": "WORD_BLEND_01 (debug asset word_blend_candidate_01, model bc8a6c91...) displayed and "
    "committed; frozen GATE2 runs on the identical view and is logged only",
    "fallback": "load failure -> STABLE",
}
# Later live-tested builds lock alongside the first one; the 2026-10-17 lock stays untouched.
PROFILES = {
    "2026-10-17": {},
    "2026-10-18-blend": {
        "MANIFEST": ROOT / "docs/audit/baselines/live_word_blend_2026-10-18.json",
        "ARCHIVE": DATA_ROOT / "artifacts/live_baselines/word_blend_live_20261018",
        "BASELINE_ID": "LIVE_WORD_BLEND_2026-10-18",
        "LOGCAT_NAME": "live_logcat_2026-10-18.txt",
        "ASSET_PREFIXES": (*ASSET_PREFIXES, "assets/word_blend_candidate_01/"),
        "ENGINES": {**ENGINES, "EXPERIMENTAL_WORD_BLEND": BLEND_ENGINE},
        "DEVICE": {
            "device": "Xiaomi M2101K7AG (serial 3ab64582), Android 12 / SDK 31",
            "install": "adb install -r 2026-10-18 09:04:48; firstInstallTime 2026-10-15 20:28:05 "
            "unchanged; shared_prefs kept",
            "instrumented": "am instrument: WordBlendParity, PhoneS2Parity (4), WordV2ShadowParity "
            "OK (6 tests); blend max_abs 3.0e-7 vs Keras",
            "word_ms_isolated": "blend median 5.83 ms (p95 6.08), frozen 1.58 ms (p95 1.71)",
            "live_word_blend": "configuration=EXPERIMENTAL_WORD_BLEND word=WORD_BLEND_01 "
            "paired=GATE2_FROZEN fallback=false; 28 commits; in-app wordMs median 10.2 "
            "(max 12.8), pairedMs 2.8; observation fps median 5.0",
            "not_verified": [
                "intended-sign accuracy of the live session (labels not available)",
                "Stable/Experimental re-check after this install (unchanged code paths)",
            ],
            "user_feedback_2026-10-18": "substantially better; PLEASE and SORRY still hard; "
            "lighting and setup not ideal",
        },
    },
}


PROFILES["2026-10-18-blend02"] = {
    **PROFILES["2026-10-18-blend"],
    "MANIFEST": ROOT / "docs/audit/baselines/debug_word_blend02_2026-10-18.json",
    "ARCHIVE": DATA_ROOT / "artifacts/live_baselines/word_blend02_debug_20261018",
    "BASELINE_ID": "DEBUG_WORD_BLEND_02_2026-10-18",
    "LOGCAT_NAME": "parity_logcat_2026-10-18.txt",
    "ASSET_PREFIXES": (
        *ASSET_PREFIXES,
        "assets/word_blend_candidate_01/",
        "assets/word_blend_candidate_02/",
    ),
    "ENGINES": {
        **ENGINES,
        "EXPERIMENTAL_WORD_BLEND": BLEND_ENGINE,
        "EXPERIMENTAL_WORD_BLEND_02": {
            **BLEND_ENGINE,
            "word": "WORD_BLEND_02 (debug asset word_blend_candidate_02, model 40533bc3...) "
            "displayed and committed; WORD_BLEND_01 runs on the identical view and is logged only",
        },
    },
    "DEVICE": {
        "device": "Xiaomi M2101K7AG (serial 3ab64582), Android 12 / SDK 31",
        "install": "adb install -r 2026-10-18 12:13:17; firstInstallTime 2026-10-15 20:28:05 "
        "unchanged; shared_prefs kept (selection EXPERIMENTAL_WORD_BLEND unchanged); "
        "on-device base.apk sha256 equals the local APK",
        "instrumented": "am instrument: WordBlendParity (01 and 02), PhoneS2Parity (4), "
        "WordV2ShadowParity OK (7 tests); WORD_BLEND_02 max_abs 2.4e-7 vs Keras",
        "word_ms_isolated": "WORD_BLEND_02 median 5.79 ms (p95 6.19); frozen 1.57 ms",
        "not_verified": [
            "EXPERIMENTAL_WORD_BLEND_02 selected and run live on the recognition screen "
            "(ADB input injection is blocked on this MIUI device; needs the user)",
            "intended-sign accuracy on the phone",
        ],
    },
}


def use_profile(name: str) -> None:
    for key, value in PROFILES[name].items():
        globals()[key] = value


def build_manifest() -> dict[str, object]:
    files = changed_files()
    assets = apk_assets(APK)
    for name, entry in assets.items():
        src = source_asset(name)
        entry["source"] = src.relative_to(ROOT).as_posix() if src else None
        entry["source_matches"] = bool(src) and sha256_file(src) == entry["sha256"]
    return {
        "schema": "apphear.live_baseline_lock.v1",
        "baseline_id": BASELINE_ID,
        "git": {
            "base_commit": BASE_COMMIT,
            "branch": git("branch", "--show-current").strip(),
            "head_at_lock": git("rev-parse", "HEAD").strip(),
            "state": "uncommitted working tree on base_commit (commit awaits approval)",
        },
        "engines": ENGINES,
        "build": BUILD,
        "apk": {
            "debug": {"sha256": sha256_file(APK), "bytes": APK.stat().st_size},
            "android_test": {"sha256": sha256_file(TEST_APK), "bytes": TEST_APK.stat().st_size},
        },
        "apk_recognition_assets": assets,
        "source_files": {p: sha256_file(ROOT / p) for p in files if (ROOT / p).is_file()},
        "device_evidence": DEVICE,
        "archive": {
            "directory": str(ARCHIVE).replace("\\", "/"),
            "contents": [
                "app-debug.apk",
                "app-debug-androidTest.apk",
                "source_snapshot.zip",
                LOGCAT_NAME,
            ],
        },
    }


def write(logcat: Path) -> None:
    manifest = build_manifest()
    assert all(a["source_matches"] for a in manifest["apk_recognition_assets"].values()), (
        "APK asset differs from source"
    )
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(APK, ARCHIVE / "app-debug.apk")
    shutil.copy2(TEST_APK, ARCHIVE / "app-debug-androidTest.apk")
    shutil.copy2(logcat, ARCHIVE / LOGCAT_NAME)
    with zipfile.ZipFile(ARCHIVE / "source_snapshot.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in manifest["source_files"]:
            z.write(ROOT / p, p)
    manifest["archive"]["sha256"] = {
        name: sha256_file(ARCHIVE / name) for name in manifest["archive"]["contents"]
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        MANIFEST,
        len(manifest["source_files"]),
        "source files,",
        len(manifest["apk_recognition_assets"]),
        "assets",
    )


def verify() -> int:
    locked = json.loads(MANIFEST.read_text(encoding="utf-8"))
    drift: list[str] = []
    for p, sha in locked["source_files"].items():
        path = ROOT / p
        if not path.is_file() or sha256_file(path) != sha:
            drift.append(f"source {p}")
    for entry in locked["apk_recognition_assets"].values():
        src = entry.get("source")
        if src and (not (ROOT / src).is_file() or sha256_file(ROOT / src) != entry["sha256"]):
            drift.append(f"asset source {src}")
    for name, sha in locked["archive"]["sha256"].items():
        path = ARCHIVE / name
        if not path.is_file() or sha256_file(path) != sha:
            drift.append(f"archive {name}")
    if APK.is_file() and sha256_file(APK) != locked["apk"]["debug"]["sha256"]:
        print(
            "note: android/app/build APK was rebuilt since the lock (archive copy is the baseline)"
        )
    for line in drift:
        print("DRIFT", line)
    print("baseline", locked["baseline_id"], "OK" if not drift else f"{len(drift)} drifted")
    return 1 if drift else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--write", type=Path, metavar="LOGCAT", help="lock using this live-session logcat"
    )
    group.add_argument("--verify", action="store_true")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="2026-10-17")
    args = parser.parse_args()
    use_profile(args.profile)
    if args.write:
        write(args.write)
    else:
        sys.exit(verify())


if __name__ == "__main__":
    main()
