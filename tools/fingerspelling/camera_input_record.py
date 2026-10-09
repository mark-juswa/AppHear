"""Append verified camera contract/progress and safe session continuity."""
# Markdown registry tables and handoff literals keep the project's existing layout.
# ruff: noqa: E501

from tools.fingerspelling.camera_input_port import APP, ROOT

REGISTRY = """

## Shared front/rear camera input — 2026-10-08

Active app: October5 `fingerspell-continuous-oct05` checkout, baseline b48594c.
Input remains `UPRIGHT_UNMIRRORED_SOURCE_RGB`; Adapter.v1 [T,405] and WORD contracts unchanged.

| Component | Source | Input -> output | Contract / preservation |
|---|---|---|---|
| Shared camera binding | RecognitionActivity.bindPhoneCamera | either CameraX lens RGBA + rotation/strides -> existing Candidate01 analyzer | same native rotation/pose/ROI math; front baseline untouched; no horizontal pixel flip; generation reset/drain and stale UI guard |
| Lens-aware overlay presentation | ui/OverlayView, PerceptionVNextOverlayRenderer | unchanged source XY -> lens preview coordinates | front mirror display unchanged; rear natural display; no reflection fed to model |
| Bounded camera diagnostics | camera/CameraTimingProbe | capture/analysis clocks -> timing JSON | no pixel/model/feature modifications; sensor FPS differs from actual screen presentation FPS |

Debug opt-in `recognitionRearCamera=true`; default/release front-only. Front AE range remains15/15;
rear requests30/30 only when advertised, otherwise15/15; KEEP_ONLY_LATEST unchanged. Genuine
observation timestamps drive existing Adapter timing/motion; recognition is not forced to30Hz.
Xiaomi front270/rear90 rotations both yield480x640 source from640x480 raw. Eight native asymmetric
rotation/stride cases byte-identical.169host/7device tests pass; WORD nonempty sentence preserved.
Supervisor confirms both work and rear is smoother after measured15.1->29.6FPS; front unchanged.
Report docs/apphear-front-back-camera-input-2026-10-08.md; artifacts/camera_input_01/summary.json.
"""

PROGRESS = """

### 2026-10-08 — Front/rear camera common input completed

- [x] Inspected actual front RGBA/native rotation/pose/ROI preprocessing; no source reflection.
- [x] Re-enabled rear behind debug flag; same recognition owner, analyzer/models and source contract.
- [x] Camera generation drains/resets/stale guards; lens-aware presentation only; front unchanged.
- [x]169host/7device checks,8byte-identical rotation/stride cases,654protected existing files intact.
- [x] Nonempty WORD sentence survives front/back/front; Settings/owner/Context Assist regressions pass.
- [x] Previous RECOGNIZED UI cleanup installed and device-tested; prior pending item is closed.
- [x] Supervisor: both cameras work; rear video smoothing confirmed and front unchanged.

Measured rear capture15.1->29.6FPS after supported30/30 rear-only AE request. Front remains15/15.
Neither model inference nor feature math changed; KEEP_ONLY_LATEST and genuine timing remain.
Private camera APK installed; previous APKs preserved. No training, dataset, TEST or model work.
No all-letter/back-domain accuracy claim. Report docs/apphear-front-back-camera-input-2026-10-08.md.
"""

MEMORY = """

## 2026-10-08 continuation — Camera input completed

Active app checkout remains `C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3`
on approved October5 baseline b48594c. Camera build is installed; supervisor confirms both lenses
work, rear video is smoother, front unchanged. Previous RECOGNIZED UI cleanup is now installed
and its device gate passed. WORD, Candidate01, Adapter, models/decoders/Context Assist unchanged.

Rear debug flag `recognitionRearCamera`; rebuild via research
`tools/fingerspelling/android_continuous_build.ps1 -RearCamera`. Front capture15FPS unchanged;
rear30FPS only if advertised. Input upright/unmirrored both; preview mirror is display-only.
169host/7device tests,8rotation/stride byte parity and654protected hashes pass. Preserve existing
rollback APKs. Evidence/report: `artifacts/camera_input_01/summary.json` and
`docs/apphear-front-back-camera-input-2026-10-08.md`. No new training or background job authorized.
Next session: restore this installed experimental state and follow the next explicit user request;
do not restart model research. Accurate all26/fluent spelling still not established by camera work.
"""


def append_once(path, text, marker):
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker not in original:
        path.write_text(original + text, encoding="utf-8")


def main():
    for checkout in (ROOT, APP):
        append_once(
            checkout / "context/feature-schema.md",
            REGISTRY,
            "## Shared front/rear camera input — 2026-10-08",
        )
        append_once(
            checkout / "context/progress-tracker.md",
            PROGRESS,
            "### 2026-10-08 — Front/rear camera common input completed",
        )
        append_once(
            checkout / "memory.md", MEMORY, "## 2026-10-08 continuation — Camera input completed"
        )
    (APP / "docs/apphear-front-back-camera-input-2026-10-08.md").write_bytes(
        (ROOT / "docs/apphear-front-back-camera-input-2026-10-08.md").read_bytes()
    )


if __name__ == "__main__":
    main()
