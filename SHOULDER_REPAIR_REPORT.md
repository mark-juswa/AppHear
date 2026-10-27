# Combined vocabulary and shoulder calibration — 25 October 2026

## Scope and inventory

Only Text-to-Sign motion assets, their integrity constants, development tools and
tests changed. The resident human avatar, player/controller, A–Z, neutral motion,
mesh, skin, screen layouts and navigation are unchanged. No remote push.

The complete inventory is in COMBINED_NEW_VOCABULARY.md and
COMBINED_NEW_VOCABULARY.csv: 743 registered entries, 742 distinct active lexical
actions, 875 explicit English forms, 821 packaged actions including the alphabet,
neutral and inactive alternatives. There are 511 additions over the 232-entry
integration base: 26 from the working version, 404 unique external entries and
81 subsequent 3D-LEX additions. Aliases and automatic spelling are not new signs.
The latest batch added 32 motion-backed previews, not linguistically validated
signs. Zero qualified ASL validations and zero validated complete sentences.

## Confirmed cause and correction

The imported motion cores contain a constant elevated clavicle baseline relative
to this avatar's relaxed neutral. Synthetic boundary padding already matches the
same neutral rig. Baseline Android repeated-sequence tests recovered that neutral
without accumulated drift: the observed bias is inside recorded motion rather
than an accumulating idle-controller transform.

485 imported motions were screened. For 465 with a stable arms-down preroll,
the local clavicle rotation is calibrated by
`neutral * inverse(initial source rotation) * source rotation(t)`.
Relative clavicle motion remains animated. A two-bone arm solve retains the
original wrist targets and elbow bend side; wrist compensation retains the
original world hand orientation. Only Left/Right Shoulder, Arm, ForeArm and Hand
rotation outputs change. No generic joint clamp or shoulder lock is applied.
Every finger-local track, clock, animation name, synthetic padding and original
284 working-version actions remain unchanged. No player changes were required.

20 motions lack a safely identifiable neutral preroll and remain intact:
ARM, DOUBT, FLUTE, GRASS, MEMBER, REFUSE, SECRETARY, SILLY, SOFA, TORNADO, TWO,
WORSE, AGAINST, BUTTERFLY, END, SOAP, LECTURE, PAST, SHARE, TRAFFIC.
They require individual review, not a guessed correction.

## Offline verification

Independent verification passed across all 465 corrected actions: 84,129 sampled
poses including all keys and 41,832 inter-key midpoints. 53,480 finger tracks are
byte-identical. Maximum wrist position deviation: 0.000474 m at midpoints;
maximum orientation deviation: 0.280 degrees at midpoints. At recorded keys,
position error is below 0.000000066 m. Maximum elbow displacement is 0.0405 m;
this remains a visual/collision review concern rather than proof of anatomy.
All 356 unaffected actions remain intact. The GLB rig/skin/geometry/JSON and
alphabet are unchanged. Five meaningful arm-solve tests passed.

The full catalog integrity check passed: 743 mappings and 4,162,046 normalized,
finite quaternion keys. All original 284 working-version actions are preserved.
Source retarget hashes retain their original meaning; the separately recorded
shoulderCalibration block pins the postprocessed bundle and lists all exceptions.

## Build and Android evidence

Universal debug build and test APK built successfully. 368 JVM tests passed with
zero failures, errors or skips. APK v2 signature verified. Comparison with Update
8 found 1,665 unchanged non-code entries, unchanged resources and manifest, and
only four changed Text-to-Sign assets. DEX is checked separately against the
installed test package; it is not claimed byte-identical to the older version.

On the existing Medium Phone API 36 emulator, the new shoulder test passed all
30 sequences (10 inputs, three rounds) in 383.017 seconds. The baseline test had
passed the same 30 inputs in 304.235 seconds. The after-test additionally asserts
actual native-request/action ordering against the planner. Every sampled frame
uses one resident human, each sequence completes, and one neutral action owns the
skeleton afterward. Recovered shoulder drift was zero in both versions.

Actual ADULT preroll arm-root height above neutral changed from 16.65/20.54 mm
(left/right) to -2.42/-0.55 mm. Unmodified same-camera before/after screenshots
were visually inspected: the shoulder silhouette is lower, without a camera or
layout redesign. This is a representative technical check, not full-motion ASL
validation of 465 signs. 2,618 after-test frames and 4,625 baseline frames were
sampled; sample count varies with emulator rendering speed.

The first two after-test attempts failed before playback because WebView could
not initialize a GL context (max_texture_units 0, minimum 8) and the emulator
rendered black even on its home screen. Waking its display alone did not fix it.
Restarting the same AVD with -gpu swiftshader restored rendering, without a wipe,
new virtual device or application-code change. Both failure logs are preserved.
The successful run used the same saved APK code and assets: all 22 inspected DEX,
player, dictionary and motion files match the universal APK. AppHear data was
backed up before the previously approved AppHear-only keep-data reinstall.

The full alphabet/mixed-input after-test passed 91 inputs in 473.864 seconds,
including A–Z, NICOLE, NAME, ANNA, JAZZ, ACTION, LOVE, HELP, mixed lexical/spelling
sequences, normalization, action selection/order, resident viewer reuse and rapid
replacement cancellation. Technical playback completion is verified; this test
does not assert qualified recognition of every rendered handshape. The emulator's
original keep-awake setting was restored afterward.

The latest 32 motions had also passed individual Android selection, 320 rendered
pose samples and 109 input cases before shoulder calibration. They were not all
individually visually reinspected after calibration; full offline key/midpoint
checks cover every corrected action, while the after Android tests cover the
representative cross-source sequences and 91 regressions described above.

## Changed files

- COMBINED_NEW_VOCABULARY.md: identify the preserved inventory checkpoint.
- SHOULDER_REPAIR_REPORT.md: diagnosis, procedure, evidence and limitations.
- android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb: calibrated 465 imported motion cores.
- Same folder/fingerspelling-avatar.json and integration-manifest.json: bundle hashes and full calibration provenance, affected IDs and exceptions.
- Same folder/3DLEX_ATTRIBUTION.md: derivative calibration attribution.
- android/app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt: bundle integrity hash only.
- Same package/AslIntegratedVocabulary.kt: manifest integrity hash only.
- android/app/src/androidTest/java/com/example/apphear/AslShoulderTransitionInstrumentedTest.kt: actual resident-avatar pose sampling, ordered queue observation and neutral recovery across three rounds.
- android/tools/correct-imported-shoulder-baselines.py: conservative staging and hand-preserving arm solve.
- android/tools/verify-shoulder-calibration.py: independent full-clip key/midpoint checks and binary preservation checks.
- android/tools/apply-shoulder-calibration.py: apply only to the exact checkpoint after verification.
- android/tools/test-shoulder-calibration.py: reachable/ambiguous arm and rigid-swing cases.
- android/tools/verify-integrated-vocabulary.py: only report an exact source-preservation comparison when its source argument was actually supplied.

## Reproduce and rollback

Pre-repair checkpoint: f649e891015cee2e72f0e0d5fc706aa6f7283e3f,
tag checkpoint/before-combined-shoulder-repair-20261024. Preserve current work
before any rollback; do not reset the user's working tree. The original source
model, original motions and previous exported APKs are retained.

From this worktree, the portable build helper is:

```powershell
./android/tools/build-integrated-preview.ps1
```

The actual local build used JDK 17, the existing SDK and .tmp/build-integration.ps1
with -OriginalWords and tasks testDebugUnitTest, assembleDebug,
assembleDebugAndroidTest, -Dorg.gradle.jvmargs=-Xmx2048m,
-Pkotlin.compiler.execution.strategy=in-process, the existing verified-onnx
init script and tools/text-to-sign-test-memory.init.gradle. The emulator build
adds the existing x86_64 ABI init script; the delivered APK is universal.

The new native test is run with:

```text
adb -s emulator-5554 shell am instrument -w -e class com.example.apphear.AslShoulderTransitionInstrumentedTest -e shoulderPhase after com.example.apphear.test/androidx.test.runner.AndroidJUnitRunner
```

## Remaining limits

These are technically tested previews. The correction preserves existing hand
poses; it does not repair inaccurate source handshapes or establish linguistic
accuracy. Qualified ASL review, full-motion visual assessment of every imported
sign, intentional body-contact review and physical-device testing remain needed.
NAME still shares CALL-SOMEONE'S-NAME motion and needs meaning review. Existing
LOVE/ME/WHY wrist/contact concerns are not declared resolved by this calibration.
The 20 exceptions are unchanged. No full collision guarantee or universal ASL
grammar translation is claimed. The catalog remains 743 entries, 257 short of
1,000; rejected, duplicate or unusable source data is not replaced with fake signs.
No unrelated feature was modified; live account/voice/network services were not
tested using private credentials. Previous APKs, source trees and data are kept.
