"""Append approved session/registry facts without overwriting existing context or memory."""
# Embedded Markdown tables follow the existing registry's single-line row convention.
# ruff: noqa: E501
from tools.fingerspelling.continuous_stage import NEW, ROOT

REGISTRY = """

## Automatic held-letter Fingerspell v1 — 2026-10-08

Authoritative app source is the October5-based `fingerspell-continuous-oct05` worktree,
branch `codex/fingerspell-continuous-oct05`; base b48594c4942d9e9ac0d94ff96396e80b9f049c0a.
Contract: research `context/fingerspelling-continuous-v1.md`; Adapter.v1 `[T,405]` unchanged.

| Component | Source | Input -> output | Contract / preservation |
|---|---|---|---|
| Automatic held-letter policy | new app `fingerspelling/HeldLetterPolicy.kt` | independent chronological raw observations -> bounded window/stable unconfirmed letters | apphear.fingerspelling.held_letter_policy.v1; operational timing asset, no confidence claim; same-letter latch/missingness rearm; no fabricated frames |
| Continuous inference owner | new app `fingerspelling/ContinuousFingerspell.kt`, existing runtime delegate | raw window -> fresh frozen Adapter.v1 -> frozen V2.1 logits -> exact singleton CTC | one worker/no backlog; callback on camera executor; generation/epoch guard; WORD transition waits; no protected WORD/perception/model change |
| Persisted recognition mode | new app `data/settings/RecognitionModeSettings.kt`, shared Settings/Profile row | explicit user setting -> exactly one recognition owner | default WORD; debug opt-in continuous; no Start/Done; spelling draft + Use confirmation; no WORD SentenceBuilder use |

169 unit/54 singleton/14 model parity checks,2 Settings/owner Xiaomi tests and3local Context Assist
checks pass. Supervisor confirms automatic flow and WORD restoration, not A–Z accuracy. Tracking
loss can falsely rearm; incorrect letters can stabilize. Manual worktree/APK remain rollback.
Full gate/evidence: research docs/apphear-fingerspelling-continuous-gate-2026-10-08.md and
artifacts/fingerspelling_continuous_01. No training/data/model/decoder tuning.
"""

PROGRESS = """

### 2026-10-08 — automatic held-letter Fingerspell, October5 baseline

Latest application source: C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3
on codex/fingerspell-continuous-oct05, base b48594c4942d9e9ac0d94ff96396e80b9f049c0a.

- [x] Supervisor approved October5 baseline and automatic held-letter flow with confirmation.
- [x] Persistent Settings choice in Settings/Profile; default WORD; Start/Done absent when automatic.
- [x] Bounded real raw windows, fresh Adapter, one async inference worker, stable singleton draft.
- [x] Explicit owner, stale result cancellation, same-letter latch/rearm, Use/Retry/Clear.
- [x]169unit checks,54singleton/14model parity,2device host/owner tests,3Context local regressions.
- [x]626protected baseline files,648manual files and237priorAPK assets preserved.
- [x] Settings crash fixed: shared Profile also needed the new row; both hosts now tested.
- [x] Supervisor confirms automatic flow and return to WORD controls/camera.
- [ ] Reliable all26 / fluent continuous spelling accuracy remains unproven and was not claimed.

Default/release flags off; private continuous build installed. Frozen V2.1 epoch034/Adapter/WORD
unchanged. Same-letter repetitions can rearm through tracking loss; confirmation remains required.
No new training/job. Next action: use/review this experimental interaction; do not automatically
launch another model experiment. Report: docs/apphear-fingerspelling-continuous-gate-2026-10-08.md.
"""

MEMORY = """

# Memory — automatic held-letter Fingerspell (latest session)

Last updated: 2026-10-08

## What was built
October5-based isolated app worktree fingerspell-continuous-oct05, branch
codex/fingerspell-continuous-oct05. Persistent Settings WORD/FINGERSPELL, automatic held-letter
preview without Start/Done, confirmation, one bounded background worker and stable-letter latch.

## Decisions made
Supervisor selected baseline b48594c4942d9e9ac0d94ff96396e80b9f049c0a and automatic held letters.
Use singleton CTC from frozen V2.1 epoch034, not a new model or fluent-spelling claim. Keep WORD
sealed and prior manual worktree/APK intact. Default/release disabled.

## Problems solved
Settings shared renderer also serves Profile: missing row caused NPE; both host layouts now have
the row and device dialog tests. Async startup test now waits for selected owner. Cadence evidence
now resets across pauses/mode changes instead of including inactive time.

## Current state
Experimental build installed;169unit,54singleton,14model/1246Adapter parity,2device owner/Settings
and3Context local checks pass.626baseline protected files,648manual files,237existingAPK assets
unchanged. User: 'Its good and working'; return: 'WORD works'. No exact user preview supplied;
diagnostics still contain wrong/stable letter streams, so no AMY/all26 accuracy claim. Single
captured active episode4.79obs/s, model49.94ms median/singleton5.05ms; no paired cadence claim.
No training/job active. New authoritative app source:
C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3.
Research root remains F:/ASL DATASET/5. Apphear3. Preserve unrelated work.

## Next session starts with
Read the continuous gate report/summary and inspect current app worktree, not the preserved manual
October4 source. Follow user steering; do not automatically train, change decoder/model or WORD.
Build wrapper: tools/fingerspelling/android_continuous_build.ps1.

## Open questions
All26 and proficient-signer reliability unproven; stable wrong predictions and tracking-loss
false rearm remain possible. No qualified reviewer. No additional human attempts requested.
Gate/evidence: docs/apphear-fingerspelling-continuous-gate-2026-10-08.md;
artifacts/fingerspelling_continuous_01/summary.json. Private APK stays local; old manual APK rollback.
"""


def main() -> None:
    for root in (ROOT, NEW):
        for relative, text in (
            ("context/feature-schema.md", REGISTRY),
            ("context/progress-tracker.md", PROGRESS),
            ("memory.md", MEMORY),
        ):
            path = root / relative
            marker = text.strip().splitlines()[0]
            if marker in path.read_text(encoding="utf-8-sig"):
                continue
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
    print("Runtime registry/progress/memory appended in research and active app worktrees; no overwrite.")


if __name__ == "__main__":
    main()
