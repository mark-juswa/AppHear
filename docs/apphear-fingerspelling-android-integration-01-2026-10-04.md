# APPHEAR_FINGERSPELLING_ANDROID_INTEGRATION_01

**Baseline alignment correction after user review:** the implementation below was built
on September29 HEAD cc1f394, not the newer application baseline
`baseline/apphear-text-to-asl-context-assist-ui-2026-10-04` at
`cee71d9f181695847936eb5f3605ea37eab82a95`. That baseline includes Context Assist,
recognition UI, application wiring and session callback changes absent from this checkout.
The initial preflight missed this newer ref. Stop live testing this APK as the current
unified app. Model/export parity remains valid; application integration must be adapted
and revalidated against cee71d9 while preserving both worktrees' existing work. Do not
reset/overwrite this checkout or claim the latest application baseline was preserved.

## Implemented

Experimental manual WORD/FINGERSPELL routing, bounded Start/Done session, separate
preview/confirmed buffer, Use/Retry/Clear, Adapter v1, quality/dedup/crop, two FP32
TFLite models and fixed CTC decoder. CPU2threads, no new detector or training.
Default/release disabled; model assets appear only in the explicit debug build.

Branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`. Protected WORD ref
`baseline/apphear-s2-r2-integration-complete-2026-09-26`, SHA
`76d93cecd85bf9f76064d320aa4a5791b5f0704a`. This is the historical WORD baseline;
the newer application baseline above must govern the resumed integration.
Existing dirty reports/context/memory and untracked research/data were preserved.

The user expressly selected residual epoch035 for development despite its earlier
failed promotion criterion. That result and B2 checkpoints are preserved. This is a
faithful-integration result, not model-quality promotion.

## Exact models

- B2 epoch076 SHA64f425358ef30e21a4aca18795226854f7aa44a34c3bc3e54a8c06366cb61397.
- Residual epoch035 SHAf87be3236196c8ab8321a3b6f7bb9d6398d048e257630a38546e8a8d00143251.
- MobileNet weights SHA002803a73df2ab65425267ee2082d1ec213b6aa9716f19ac1a1ed5361239c5f6.
- Export package4,630,816bytes total two FP32 graphs; no Flex ops/delegates.
- Android manifest SHA09680096117f4d34eb86e0b71fc8681bfe3d4101082c4e0db2c8f7e9b1a1e57b.

## Numerical parity

Host six actual sequences (three sources ×native/phone), decoder equality and actual
frozen-B2 zero-visual fallback passed. One real source crop matches the encoder.
Actual Xiaomi M2101K7AG Android12, installed TensorFlowLite2.16.1:

| Check | Result |
|---|---|
| 523 geometry observations | Max absolute error0 |
| Quality/dedup/rejection decisions | Decisions exact; score max5.96e−8 |
| Real normalized crop | Max error0 |
| Appearance embedding | Max1.60e−5 |
| Six native/phone sequence logits | Max9.06e−6; strings equal |
| Six causal prefixes | Passed |
| Six zero-visual actual B2 references | Passed |
| Rotation/stride/buffer-position unit test | Passed |

A pinned Java dynamic-shape cache issue was found and resolved through output-buffer
handling only, after `/recover` classified it as an isolated component failure.
See official [Interpreter dynamic-output documentation](https://developers.google.com/edge/api/tflite/java/org/tensorflow/lite/Interpreter)
and [2.16.1 wrapper source](https://github.com/tensorflow/tensorflow/blob/v2.16.1/tensorflow/lite/java/src/main/java/org/tensorflow/lite/NativeInterpreterWrapper.java).

## Protection/build checks

Original 652 source/assets/checkpoint identities checked. Only intentional existing
source changes: RecognitionActivity wiring/controls and Candidate01FrameAnalyzer owner
hook. Candidate01 math/preprocessor/models, raw-v1, S2/378/lifecycle/admission/materializer,
RecognitionV2/236recognizer, PhoneProductionSession, SentenceBuilder, ContextAssist and
Hear implementation remain untouched. Gradle adds debug flag/conditional asset path.

Default-off and experimental builds pass. Default APK verified to contain no
assets/fingerspelling models. Existing WORD/unit suite plus new session/rotation tests
pass (136tests). Python tooling Ruff/mypy pass. No TEST payload was accessed.
No profile/dev-session text has been added to training datasets.

## Live validation status

Experimental APK installed; full numerical test is complete. Camera permission is
ungranted at the last checked state. No live session report exists yet. Therefore actual
Candidate01 cadence with appearance, encoder/crop p50/p95, finishing latency, heap,
observation loss and controlled recognition results are **UNMEASURED** in this phase.
Historical6.23observations/s is only the preceding WORD measurement.

The requested four live attempts are MARK, BELLA, JAZZ, PARIS, each separately
Start→Done; inspect unconfirmed preview, Use one, Retry/Clear another. Additional longer
name and second-signer attempts should follow before interpreting phone quality.
No character boundaries, language correction or accuracy inference from fixture logits.

## Exact commands and evidence

Build/install the opt-in candidate (PowerShell):

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3\android'
& .\gradlew.bat :app:assembleDebug :app:assembleDebugAndroidTest :app:testDebugUnitTest -Pfingerspell=true --console=plain
& 'D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe' install -r '.\app\build\outputs\apk\debug\app-debug.apk'
& 'D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe' install -r '.\app\build\outputs\apk\androidTest\debug\app-debug-androidTest.apk'
& 'D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe' shell am instrument -w -e class com.example.apphear.fingerspelling.FingerspellParityInstrumentedTest com.example.apphear.test/androidx.test.runner.AndroidJUnitRunner
```

Use normal AppHear launcher→Sign-to-Text; camera permission must be granted through
Android's normal dialog. RecognitionActivity is non-exported. No permission bypass.
Manual installation/instrumentation retains APKs; Gradle managed connected-test runs may
remove their installed packages. Do not use managed installation for normal live sessions.

After signing attempts:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.android_evidence pull
& .\.venv\Scripts\python.exe -m tools.fingerspelling.android_evidence preservation
```

Only experiment-specific private JSON is read; scripts do not read unrelated phone
files. Reports contain raw predictions, observation count/timing, crop availability and
latency. Expected transcripts/retries and signer identity must be reviewed, not inferred.
No camera video is saved.

Rollback to default WORD build:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3\android'
& .\gradlew.bat :app:assembleDebug -Pfingerspell=false --console=plain
& 'D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe' install -r '.\app\build\outputs\apk\debug\app-debug.apk'
```

## Review and remaining gates

Plan/contract parity: PASS. Protected system/source integrity: PASS. Runtime production
readiness: NOT SIGNED OFF. No remaining host parity/model-export blocker. Genuine
remaining external gates: camera permission and live signing; then profile visual cost,
WORD manual/F22 regression and lifecycle interactions. Device parity is not a substitute
for these. Existing15FPS product target is not met by a historical6.23FPS measurement.
No additional backbone/decoder/data/TCN development is authorized by this result.

FINGERSPELL_ANDROID_MODEL_PARITY_PASSED_APPLICATION_BASELINE_ALIGNMENT_REQUIRED
