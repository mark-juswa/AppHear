"""Record measured long-spelling UI checks and preserve the negative finding."""
import json
import subprocess
import xml.etree.ElementTree as ET

from tools.fingerspelling.camera_input_port import APP, ROOT, sha
from tools.fingerspelling.long_spelling_check import OUT


def main():
    result = subprocess.run(
        [r"D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe", "-s", "3ab64582",
         "shell", "run-as", "com.example.apphear", "cat", "files/fingerspell_long_text.json"],
        capture_output=True, text=True, check=True,
    )
    layout = json.loads(result.stdout)
    (OUT / "device_layout.json").write_text(json.dumps(layout, indent=2))
    before = json.loads((OUT / "before.json").read_text(encoding="utf-8"))
    changed = [p for p, h in before.items() if sha(APP / p) != h]
    allowed = {
        "android/app/src/androidTest/java/com/example/apphear/fingerspelling/ContinuousFingerspellInstrumentedTest.kt",
        "android/app/src/test/java/com/example/apphear/fingerspelling/HeldLetterPolicyTest.kt",
    }
    assert set(changed) == allowed
    results = list((APP / "android/app/build/test-results/testDebugUnitTest").glob("TEST-*.xml"))
    roots = [ET.parse(p).getroot() for p in results]
    totals = {k: sum(int(r.attrib[k]) for r in roots) for k in ("tests", "failures", "errors")}
    assert totals["tests"] == 171 and totals["failures"] == totals["errors"] == 0
    assert layout["length"] == layout["last_line_end"] == 104
    assert layout["height"] == layout["layout_height"]
    for name, count in (("original_device_checks.log", 2), ("preservation_device_checks.log", 3)):
        payload = (OUT / name).read_bytes()
        encoding = "utf-16" if payload.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        assert f"OK ({count} tests)" in payload.decode(encoding)
    report = {
        "status": "THREE_LETTER_DISPLAY_LIMIT_NOT_REPRODUCED",
        "device": "Xiaomi 3ab64582", "layout": layout, "host_checks": totals,
        "device_checks": 5, "changed": changed,
        "existing_files_unchanged": len(before) - len(changed),
        "production_code_changed": False, "installed_app_changed": False,
        "accuracy_claim": "NONE", "capture_acceptance_issue": "NOT_YET_ISOLATED",
    }
    (OUT / "validation.json").write_text(json.dumps(report, indent=2))
    doc = """# Fingerspelling reported three-letter limit — 2026-10-08

The reported display cap could not be reproduced. No recognition or display code was
changed, and the existing private app remains installed. Two focused regression tests
were added; only the test APK was installed on the Xiaomi.

## Measured result

- The unmodified HeldLetterPolicy accepted 104 letters, exceeding both three characters
  and the 64-observation inference-window bound (which does not bound spelling length).
- The existing RecognitionActivity rendered the same 104-character spelling on the
  Xiaomi: five lines, 770 px text width, 348 px text/layout height; final line ends at
  character 104, no ellipsis. CURRENT SIGN remained Z separately.
- 171 host tests passed, five phone tests passed, including owner/confirmation/clear and
  Context Assist regressions. All 660 other inventoried app source/assets/build files
  were unchanged. Candidate01, models, Adapter, camera and WORD were not edited.

## Actual session evidence and uncertainty

The pre-test diagnostic was preserved in `reported_session.json`: it contains additions
E, E, A, producing EEA. Subsequent events preserve EEA; most decode blank or latched A.
There are also three Y results spanning about 1.0496 seconds which did not append.
That means it would be incorrect to attribute every rejection solely to instability.
The existing diagnostic does not record callback policy epoch, current missing-hand
state or candidate state; stale/absence rejection versus stability rejection cannot
be distinguished from these saved records. No three-letter branch exists in the code.

The supervisor was asked whether CURRENT SIGN shows the fourth letter while RECOGNIZED
stays at three, or is blank/incorrect. This clarification is pending. Recognition
thresholds must not be loosened merely to produce a longer but incorrect spelling.

## Files and evidence

Active checkout: `C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3`.
Added long-spelling checks to `HeldLetterPolicyTest.kt` and
`ContinuousFingerspellInstrumentedTest.kt`. Research orchestration:
`tools/fingerspelling/long_spelling_check.py` and `long_spelling_record.py`.
Evidence: `artifacts/fingerspelling_long_spelling_01/validation.json`,
`device_layout.json`, `before.json`, `reported_session.json`, `build_checks.log`,
`original_device_checks.log`, `preservation_device_checks.log`.

This proves storage/rendering capacity, not real-signing recognition accuracy.
"""
    name = "docs/apphear-fingerspelling-long-spelling-check-2026-10-08.md"
    for base in (ROOT, APP):
        (base / name).write_text(doc, encoding="utf-8")
        for relative in ("context/progress-tracker.md", "memory.md"):
            p = base / relative
            note = """

## 2026-10-08 reported three-letter RECOGNIZED limit

No display/buffer cap reproduced: 104 characters accepted and visible in five lines
on Xiaomi. 171 host/five phone checks passed; production app/model/camera/WORD unchanged.
Only two regression test files changed. See
`docs/apphear-fingerspelling-long-spelling-check-2026-10-08.md` and
`artifacts/fingerspelling_long_spelling_01/validation.json`.
Existing session EEA plateau includes unaccepted Y decisions; saved diagnostics lack
policy/callback state to isolate rejection reason. Clarification pending: does CURRENT
SIGN show the fourth letter while RECOGNIZED stays at three, or remain blank/incorrect?
Next action: identify acceptance condition from that clarification; do not invent a
three-letter UI cap or loosen recognition thresholds without evidence.
"""
            if note not in p.read_text(encoding="utf-8-sig"):
                with p.open("a", encoding="utf-8") as f:
                    f.write(note)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
