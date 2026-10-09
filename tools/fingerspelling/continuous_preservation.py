"""Verify approved-baseline, manual rollback and frozen package preservation."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from tools.fingerspelling.continuous_stage import NEW, OLD, OUT, ROOT, sha


def main():
    before = json.loads((OUT / "preservation_before.json").read_text())
    allowed = {
        "android/app/build.gradle.kts",
        "android/app/src/main/java/com/example/apphear/RecognitionActivity.kt",
        "android/app/src/main/java/com/example/apphear/perceptionvnext/Candidate01FrameAnalyzer.kt",
        "android/app/src/main/java/com/example/apphear/ui/settings/SettingsContent.kt",
        "android/app/src/main/res/layout/fragment_settings.xml",
        "android/app/src/main/res/layout/fragment_profile.xml",
        "android/app/src/main/java/com/example/apphear/ui/profile/ProfileFragment.kt",
        "android/app/src/main/res/values/strings.xml",
    }
    protected = {p: h for p, h in before["baseline"].items() if p not in allowed}
    changed = [p for p, h in protected.items() if not (NEW / p).is_file() or sha(NEW / p) != h]
    manual_changed = [
        p for p, h in before["manual"].items() if not (OLD / p).is_file() or sha(OLD / p) != h
    ]
    pinned_files = [
        "FeatureAdapterV1.kt",
        "FingerspellModels.kt",
        "FingerspellSingleLetterDecoder.kt",
        "FingerspellCore.kt",
        "FingerspellPrefixBeamDecoder.kt",
        "PhoneFingerspellBridge.kt",
    ]
    finger = Path("android/app/src/main/java/com/example/apphear/fingerspelling")
    drift = [name for name in pinned_files if sha(NEW / finger / name) != sha(OLD / finger / name)]
    analyzer = Path(
        "android/app/src/main/java/com/example/apphear/perceptionvnext/Candidate01FrameAnalyzer.kt"
    )
    if sha(NEW / analyzer) != sha(OLD / analyzer):
        drift.append("Candidate01FrameAnalyzer.kt")
    asset_base = ROOT / "artifacts/fingerspelling_single_letter_01/android_assets"
    assets = {
        str(p.relative_to(asset_base)).replace("\\", "/"): sha(p)
        for p in asset_base.rglob("*")
        if p.is_file()
    }
    asset_drift = [p for p, h in assets.items() if sha(OUT / "android_assets" / p) != h]
    tests = [
        ET.parse(p).getroot().attrib
        for p in (NEW / "android/app/build/test-results/testDebugUnitTest").glob("TEST-*.xml")
    ]
    test_summary = {
        k: sum(int(row[k]) for row in tests) for k in ("tests", "failures", "errors", "skipped")
    }
    result = {
        "schema_version": "apphear.fingerspelling.continuous_preservation.v1",
        "approved_baseline": "b48594c4942d9e9ac0d94ff96396e80b9f049c0a",
        "protected_baseline_files_checked": len(protected),
        "protected_changes": changed,
        "manual_rollback_files_checked": len(before["manual"]),
        "manual_rollback_changes": manual_changed,
        "frozen_integration_drift": drift,
        "model_package_files_checked": len(assets),
        "model_package_drift": asset_drift,
        "unit_tests": test_summary,
        "test_payload_accessed": False,
        "training": False,
        "source_worktree": str(NEW),
        "accuracy_claim": "NONE",
    }
    result["pass"] = not (
        changed
        or manual_changed
        or drift
        or asset_drift
        or test_summary["failures"]
        or test_summary["errors"]
    )
    (OUT / "preservation_after.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
