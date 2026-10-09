# Current working AppHear baseline — 2026-10-05

## Identity and future-work rule

- Preservation branch: `baseline/apphear-text-to-asl-context-assist-ui-2026-10-05`.
- Annotated preservation tag: `apphear-text-to-asl-context-assist-ui-2026-10-05`.
- Last application change: `ec340344ab8381d600ad6d84ff15e22cc7b3dcae`.
- Parent working baseline: `cee71d9f181695847936eb5f3605ea37eab82a95`, preserved under the October 4 branch/tag.
- Protected recognition baseline remains `76d93cecd85bf9f76064d320aa4a5791b5f0704a`; older Text-to-ASL and recognition refs remain fixed.

This is the current user-reviewed working application baseline. The preservation commit adds documentation only to the reviewed application source. Start future work on a new branch/worktree from the October 5 tag. Keep its preservation branch and tag fixed; do not develop directly on them.

## Included functionality

- Text-to-ASL ready/text/talk redesign: tapping “Ready when you are” opens Text by default; the supplied chat/microphone icons, larger control labels, and modestly roomier bottom sheet follow the reviewed mockups.
- Existing typed submission, speech auto-submit and Google speech dialog, local avatar playback, Clear, replay, Reply and TTS. Talk-mode Sign It replays the already submitted speech plan without recording another Hearing turn.
- Existing Conversation-Aware Phrase Assistance: asynchronous Gemini predictions, separate raw sentence, compact full-text prediction strip, read-only Top-5 evidence and conservative context-supported advisory output.
- Existing recognizer, segmentation, feature/model/vocabulary contracts, SentenceBuilder and raw Hear/TTS.

## Verification and binary rollback

- Final JVM suite: 150 tests, zero failures/errors. Debug, release and Android-test APK builds passed.
- The Xiaomi M2101K7AG user confirmed the ready-title Text entry, roomier Text/Talk controls, typed HELLO avatar signing and existing Google speech dialog.
- Final installed private debug APK SHA-256: `0B3890F4F18F6DF4D2A3D672542E900879ABF0C029C94162DCB27387EDD3E9AE`; host/device hashes matched.
- A preserved copy is in ignored `android/build/stable-context-assist-ui-20261005/app-debug-reviewed.apk` in the UI worktree. The pre-test phone APK remains in ignored `android/build/text-to-asl-ui-device-20261005/original-apphear.apk`, SHA-256 `25616ECA50832C43098CA7DC1C3EDCC8467DC38DC3AA1D1F940F305F58ADB2B0`.
- These APKs may embed local development configuration. Keep them private and outside Git. Rebuilding from source requires the existing local flags/configuration; use the October 4 configuration description and current Gradle definitions.
- Release Context Assist and Text-to-ASL pilot flags retain their existing hard-disabled configuration. This preservation does not change release settings.

This is a working integration baseline. Broad F22, controlled performance checks, cross-signer accuracy and continuous signing validation remain open. The Android-test APK was built; the latest UI was reviewed through user-assisted phone checks, not a newly executed connected instrumentation suite.

## Ongoing experiments are retained

Read [the experiment handoff](ongoing-experiments-2026-10-05.md) before resuming experimental work. The new baseline does not close the fingerspelling experiment or erase Context Assist's deferred issues. Existing experiment worktrees, uncommitted source, artifacts, datasets and running preparation jobs must be inspected and preserved before integration.

The fingerspelling Android integration still starts at the October 4 baseline. Any later migration to this October 5 UI should be an explicit integration task after its current work is preserved; do not automatically reset/rebase its dirty worktree.
