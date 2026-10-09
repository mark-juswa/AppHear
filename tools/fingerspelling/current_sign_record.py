"""Record corrected UI mapping, installed artifact and protected-state verification."""

import json
import shutil

from tools.fingerspelling.camera_input_port import APP, ROOT, sha
from tools.fingerspelling.current_sign_restore import OUT


def main():
    result = json.loads((OUT / "validation.json").read_text())
    result["device_tests_pass"] = "OK (5 tests)" in (OUT / "device_tests.log").read_text()
    assert result["device_tests_pass"] and not result["unexpected_changes"]
    assert result["unit_tests"]["failures"] == result["unit_tests"]["errors"] == 0
    dest = OUT / "private_apks/app-debug-private-current-sign.apk"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(APP / "android/app/build/outputs/apk/debug/app-debug.apk", dest)
    result.update(
        {
            "apk_sha256": sha(dest),
            "status": "CURRENT_SIGN_RECOGNIZED_UI_PASS",
            "model_or_recognition_policy_changed": False,
            "accuracy_claim": "NONE",
        }
    )
    (OUT / "validation.json").write_text(json.dumps(result, indent=2))
    text = """

### 2026-10-08 — CURRENT SIGN clarification implemented

Supervisor clarified CURRENT SIGN must remain visible for the live detected letter; RECOGNIZED
constructs spelling. Prior hidden-column cleanup was a misunderstanding and is superseded.
Presentation-only currentLetter exposed; tentative letters do not append until the existing stable
policy accepts them. Missing/empty/reset clears current display; stale results ignored. Controls
remain hidden, Hear confirmation retained.170host/5Xiaomi UI-owner-Context tests pass;655protected
files unchanged. Private update installed, rear30/front15 retained.
No model, decoder, stabilization,
WORD, Context Assist or camera changes.
Report: docs/apphear-fingerspelling-current-sign-restored-2026-10-08.md.
"""
    registry = """

## Fingerspell presentation clarification — 2026-10-08

CURRENT SIGN = presentation-only latest valid singleton decode (`currentLetter`); RECOGNIZED =
confirmed + stabilized draft spelling. Tentative letter does not change accumulation. No new feature
schema, threshold or decoding policy. Missing/empty/reset clears current display; stale results
cannot overwrite it. This supersedes earlier hiding of CURRENT SIGN. Controls remain hidden.
Source: HeldLetterPolicy / FingerspellSnapshot / ContinuousFingerspell.emit / Activity renderer,
active October5 checkout.170host and5Xiaomi checks pass. WORD/model/camera contracts unchanged.
"""
    for checkout in (ROOT, APP):
        for name, content, marker in (
            ("context/progress-tracker.md", text, "CURRENT SIGN clarification implemented"),
            ("context/feature-schema.md", registry, "Fingerspell presentation clarification"),
            (
                "context/fingerspelling-continuous-v1.md",
                registry,
                "Fingerspell presentation clarification",
            ),
            ("memory.md", text, "CURRENT SIGN clarification implemented"),
        ):
            p = checkout / name
            if not p.exists():
                p.write_bytes((ROOT / name).read_bytes())
            original = p.read_text(encoding="utf-8")
            if marker not in original:
                p.write_text(original + content, encoding="utf-8")
    name = "docs/apphear-fingerspelling-current-sign-restored-2026-10-08.md"
    (APP / name).write_bytes((ROOT / name).read_bytes())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
