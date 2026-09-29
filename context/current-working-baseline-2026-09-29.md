# Current working AppHear baseline — 2026-09-29

## Identity and scope

- Preservation branch: `codex/current-working-text-to-asl-baseline-2026-09-29`.
- Preservation tag: `apphear-text-to-asl-working-alphabet-2026-09-29` (annotated on the branch's preservation commit).
- Parent before preservation: `f5a6cb4eb0d6387340ce891d97f1976656eb44c6`, the committed continuous-transition diagnostic handoff. That parent includes debug-only recognition diagnostics, not a recognition behavior promotion. The older recognition baseline `apphear-s2-r2-integration-complete-2026-09-26` remains at `76d93cecd85bf9f76064d320aa4a5791b5f0704a` and is not retagged or replaced.
- The new baseline records the **tested Text-to-ASL alphabet pilot source** plus its Profile/Settings character selection and account UI dependencies. Its seven pilot flags remain off by default and in release. The user's last tested phone version is the flagged APK with SHA-256 `82c5298f218efb3c5184b3923672787f46843267e913aeb7c00d517a2829c5d5`; the ordinary all-flags-off rollback APK has SHA-256 `a61c09d0b254753d44d992739734467c5a7e8d1f0363f317ad96b9b5dc57a3b7`.

## Included source and validation

- Android Text-to-ASL catalog, planner, player and fragment changes; character choice, profile/account UI and persistence needed by the tested pilot; corresponding unit/device tests and resources.
- Separate versioned `aslPilot`, `aslShared`, `aslWords`, `aslIdle` and `aslAlphabet` asset source sets. The final shared alphabet GLB is 61,791,300 bytes, SHA-256 `645da29f5e8a24dc7da2f4b6e23ca2e87fb91254958f5053ba0281080ec0a524`. All 102 Original GLBs match the pre-pilot assets in both APKs.
- The repeatable `tools/text_to_asl_assets` source and focused Text-to-ASL/Profile plans and results. The tested pilot/default builds each passed 132 JVM tests; 12 player tests passed; two targeted device catalog/preference tests passed. The user confirmed immediate submission and Replay, cold-load leave/reopen followed by C-A-T, and visually accepted A-Z. The scoped phone log records 26 letter completions, New idle return, and no playback failures.
- The exact tested APKs and verification evidence are saved outside Git under `I:\3d Characters\optimized_apphear3_alphabet_20260929` with `delivery-checksums.json`; all 16 copied files passed SHA-256 recheck. APKs and generated evidence are intentionally ignored by Git. The source tag and these hashes identify the tested binary; rebuilding requires the same local, ignored app service configuration.

## Excluded and isolated work

- The context-aware assistant is **not in this baseline**. Its clean separate worktree/branch is `feature/conversation-phrase-assist-mvp` at `24f0684360332b25d34a70f445e245733982976a`, forked from `76d93ce`. Do not merge or cherry-pick it into this tag. A later integration must reconcile at least `android/app/build.gradle.kts` and `TextToAslFragment.kt`, plus shared context files if selected; neither branch currently has a merge conflict because no merge was attempted.
- Ongoing continuous-transition report edits, local phone captures, `.codex_tmp`, and the recognition-upgrade sentinel CSV remain outside the preservation commit. These are separate local work, not part of the Text-to-ASL baseline. No secrets, local Gradle properties, downloaded media, APKs or raw device captures belong in Git.

## Operational limits

- This is a **known-working Text-to-ASL pilot**, not a production/release promotion or a claim that the full recognition pipeline has passed a new device gate. The first New-character GLB load took about 7.3–12 seconds in diagnostic runs. Controlled cold-load p50/p95, frame pacing, low-RAM/thermal behavior and broad F22 smoke remain open. Original has only A/B letter assets; unknown words needing C-Z are reported unsupported as whole tokens under the pilot flag.
- The phone was disconnected during this preservation audit, so its presently installed package could not be rehashed. The last installed/tested APK is identified by the saved artifact and prior device validation. Recheck `adb` package hash when the phone is available if exact current-device identity matters.

## Restore and next-work rule

Check out the annotated tag for an immutable source snapshot, or branch from it for new work. Use the saved pilot APK to return the handset to the exact tested binary with `adb install -r`; use the saved ordinary APK for all-flags-off rollback. Keep new experiments on separate branches/worktrees. Integrate the context-aware assistant only by an explicit reviewed merge/rebase with fresh app tests and a new phone check; the baseline tag itself must not move.
