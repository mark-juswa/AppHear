# Recognition V3 Stage2 — connected-phone compact validation

2026-10-16, Asia/Manila (capture began October15; UTC session20261015T155027Z).
Status: ANDROID_ENGINEERING_GATES_AND_CAPTURE_PASS; PHYSICAL_REVIEW_PENDING.

## Verified starting point

The clean isolated codex/recognition-v3-stage2 branch is based on6dbb2d3, following
1422cad → e196a8d →5d73b412 → canonical4c99ac24. The canonical integrated checkout
remains clean at4c99ac24; protected76d93cec is unchanged. This is the integrated
WORD/continuous FINGERSPELL/coordination/Context Assist/Hear/Text-to-ASL application,
including the Original catalog and current UI. No production source was changed in this
validation. Stage1 concurrent refinement remains disabled; its code and evidence are retained.
All581 protected shared-state hashes pass again. The compact build's465 original packaged
asset/native entries already matched the serial baseline; its only extra asset is the protocol.

## Actual device work

One authorized Xiaomi M2101K7AG was connected over USB. Read-only preflight saved uptime,
boot reason, AppHear exit-info, crash buffer, thermal/battery and memory evidence before testing.
Battery66%,34.4°C initially;64%,37.1°C after capture. Thermal status0, but HAL Ready=false:
limited sensor visibility, not proof of absent thermal effects. Uptime increased10425.32→10779.26s;
no reboot/disconnection was observed during this bounded test period. A retained init SIGABRT
at20:54 and generic reboot boot reason do not establish the cause of the previous phone closure.
Post-test AppHear exits say USER REQUESTED / finished inst, consistent with deliberate test-process
termination. No crash was observed in this capture. This is not a sustained stability certification.

Installed the saved compact app and test APKs with install-r; no uninstall, data clear, settings
change, model download or rebuild. SHA256s:

- App:846ad345cdb061bef11858ef95151c0d35abdadbd67a5dbb1f9401abf7f6f6fc
- Android test:45d5faaad3ae5e87308d1d25e4ad0ba029bc9f4d19691deb5350eb5a0689fd15

**11 Android tests passed**, each selector run separately:

| Gate | Tests |
|---|---:|
| Actual packaged compact-protocol parser |1|
| Camera input |1|
| Frozen phone S2 parity |3|
| RecognitionV2 end-to-end replay |1|
| SequenceV2.1 parity |1|
| Single-letter exact Python parity |1|
| Continuous FINGERSPELL |2|
| Actual WORD/FINGERSPELL ownership/confirmation preservation |1|

The old51-frame concurrent-refiner pixel gate was not rerun: its fixtures are absent from this
test APK. The obsolete manual-start single-letter UI case was not counted as applicable to the
integrated continuous build. Earlier141 host/200 JVM tests are prior build evidence, not fresh
runs in this phone continuation. External service credentials remain unprovisioned in this
fake-service build; these checks do not validate live cloud services or all user-facing features.

## Completed capture and integrity

The user explicitly attested NONEXPERT_ENGINEERING_SMOKE. They completed all five blocks:
hands-down HELLO/HOME, hands-up HELLO/HOME, two HELLO executions, HELLO then hold, ordinary movement.
Markers bracket whole sequences, never reset the recognizer and are not physical sign labels.

The first copy was taken before final-save ran. It had buffered binary files and no final manifest;
the audit correctly refused it. The phone denied remote INJECT_EVENTS; the human pressed the
existing FINALIZE & SAVE EVIDENCE control. A fresh directory then received a complete finalized
snapshot. No signs were repeated, binaries repaired or missing frames fabricated. Both snapshots
are preserved, with the first explicitly unsuitable for evaluation.

Final session:
F:/ASL DATASET/5. Apphear3/artifacts/recognition_v3_stage2_compact_device/finalized/session_20261015T155027Z

-757 chronological genuine processed observations,757 verified original source JPEGs.
-1981 original capture files /43,375,481bytes, including event diagnostic images and exact tensors.
-All five BEGIN/COMPLETE marker pairs; final visual and exact-recorder drains verified.
-All four full-session event identities, every lifecycle state/re-arm transition and recognition
 window index reproduce with the unchanged reference decoder/materializer; diagnostic UI delivery
 identities are linked. Four full-session events are not four correct signs.
-Raw-to378 features and normalization match Android exactly: maximum absolute error0.
-Frozen host TFLite replay versus Android: probability max error4.76837158203125e-7,
 zero state argmax mismatches across all757 observations. No train/serve serialization skew found
 for these saved inputs. This does not validate perception truth or learned state semantics.

## Measured delivery and timing

These are **front-camera diagnostic-recorder** measurements, with full evidence capture and
serial hand refinement. There is no new matched baseline/candidate performance comparison.
They must not be compared with earlier different-scene runs as an optimization speedup.

Whole-session genuine observation delivery is4.696FPS over160.993s, including warmup and idle
outside marked blocks. Formula:(N−1)/(last−first source timestamp). Source spacing p50/p95 is
199.962/266.616ms. The633.207ms maximum is between observations0/1 during startup. Another gap,
533.232032ms in blockB, exceeds the533.232ms continuity cutoff by only0.000032ms; do not call it
a second large runtime stall. Source IDs enumerate processed observations, not every sensor frame.

| Recorded stage/interval | p50 ms | p95 ms |
|---|---:|---:|
| Native preprocessing |2.642|8.530|
| DWPose inference |86.871|108.283|
| DWPose decode |0.530|0.898|
| Candidate perception path |200.037|246.910|
| Feature construction |0.381|0.867|
| Frozen S2 inference |7.146|23.796|
| Source capture to S2/decoder decision |351.296|406.490|

Candidate total is analyzer entry through perception completion, including diagnostic pixel
capture. It excludes subsequent S2/event/classifier/evidence work and ImageProxy close; **full
analyzer p50/p95 was not recorded**. Source-to-decision includes camera delivery/backlog and is
not analyzer duration. Separate hand-refinement wall time and diagnostic overhead are absent;
do not infer them by subtracting independently computed percentiles. DWPose is a substantial
measured component, while feature math/S2 are smaller; the strongest remaining CPU bottleneck
cannot be uniquely assigned from these fields. Median S2 prefix length eventually61 observations
can span many seconds at this cadence, but the earlier unconditional prefix-reset candidate failed.

| Whole marked block | Rows | Delivered FPS | Any accepted hand | Body available |
|---|---:|---:|---:|---:|
| A hands down |32|4.116|5|3|
| B hands up |25|3.131|17|0|
| C repeat |34|4.232|22|0|
| D sign then hold |54|4.099|39|0|
| E ordinary movement |37|4.350|18|11|

These availability counts describe whole marked blocks, including neutral tails, and cannot be
substituted for per-sign validity. Saved live screen inspection shows close head/upper-torso
framing; body_available requires six valid points. Poor body coverage and intermittent hand
acceptance are confounds, not proof of a particular detector/refiner defect. A shorter transition
can fall between observed frames; no dense sensor recording exists to prove such a miss here.
Camera-completion/analyzed counters in attempt metadata span drain as well as marked duration;
no matched source-ID sensor-drop count is claimed. No rear-camera capture ran in this continuation.

Idle app PSS after camera finalization was205135KiB (~200.3MiB). This is neither peak live memory
nor a matched resource delta. Sustained CPU contention, peak memory and A/B resource impact were
not measured. Stage1's previous mixed live FPS/memory findings remain the relevant comparison.

## Recognition interpretation and next decision

Physical source-boundary review is pending; the first downloaded draft was blank. No automatic
labels were filled from button markers, S2 states or classifier outputs. Consequently there is
no new count of genuine correct, missing, duplicate, merged or wrong-class signs yet, and no
new claim of ASL or continuous-recognition accuracy. The diagnostic Activity is also not the
normal app SentenceBuilder; repeated-word sentence delivery remains a separate production gate.

Whole-block traces already constrain the re-arm hypothesis: A/B/D contain only IDLE-before
observations and no ACTIVE, so a global400ms WAIT lock does not account for their entire duration.
Whether valid physical signs were missed, which observations supplied usable evidence, and why
ACTIVE was absent require the blinded review and better-qualified signing evidence. The reviewed
historical capture remains stronger: six/seven confident signs had no ACTIVE, while hands-up HOME
had13 IDLE observations with accepted hands. The rejected reset raised reviewed non-sign events4→9.

Retain Stage1 disabled. Do not shorten timers or deploy the rejected history reset. Finish the
current physical review; then distinguish accepted-evidence loss, absent ACTIVE acquisition,
completion/re-arm collisions and classifier errors on those exact spans. If lexical execution or
coverage is uncertain, the smallest decisive follow-up is one qualified design signer repeating
this same compact profile with full upper-body and hand visibility, same camera/lighting/distance,
and no prediction-driven waits. Inspect visibility before START, not by changing inference rules.
No new model, Stage3, fingerspelling policy or unrelated UI change is justified by this smoke test.

## Evidence, reproduction and rollback

Small hash-bound results and all eight selector receipts:
evidence/recognition_v3_stage2_device_20261015/. The delivery manifest links both APKs, unchanged
implementation/baseline commits, original capture inventory, raw preflight receipts and methods.
Raw images/binaries remain private local artifacts; they are not added to Git.

Reproduce the source audit with the existing tool:

```powershell
& 'F:/ASL DATASET/5. Apphear3/.venv/Scripts/python.exe' -m eval.runtime_diagnostics.continuous_transition_diagnostics prepare --session 'F:/ASL DATASET/5. Apphear3/artifacts/recognition_v3_stage2_compact_device/finalized/session_20261015T155027Z'
```

After a complete human review is saved as transition_review/human_boundaries.json, use the same
command with analyze instead of prepare. Same-observation S2 replay uses the existing
recognition_v3_stage2_audit.verify_s2(session) helper, not the legacy Phase7 six-attempt CLI.

No runtime recognition policy was changed. Omit recognition_v3_stage2_diagnostics for the legacy
diagnostic profile, or leave diagnostics for the normal integrated app. The saved serial baseline
APK can be restored with install-r using the same signing key and without clearing storage;
canonical/protected checkouts, all weights/data and earlier APKs/evidence remain intact.