# Recognition V3 Stage2 — connected-phone compact validation

2026-10-16, Asia/Manila (capture began October15; UTC session20261015T155027Z).
Status: ANDROID_ENGINEERING_CAPTURE_AND_NONEXPERT_REVIEW_COMPLETE; STAGE2_OBJECTIVE_UNRESOLVED.

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

The user supplied a revised review identifying four positive HELLO intervals and one confirmed
ordinary-movement interval. Two HOME intervals, the second repeated HELLO and the separate hold
interval remain UNCERTAIN. The export omitted all whole-block checkmarks. In response to the
specific completion question the user replied “All five signs done” and supplied the revised
file covering all five blocks. This human attestation supplies only reviewed_blocks metadata;
the original export is preserved byte-exact, and every boundary, judgment, reviewer and blinding
field is unchanged. The final derived labels pass the existing validator and full evaluator.
Source export, derived labels and exact attestation are retained separately with hashes.

| Human-marked positive interval | Rows | Any accepted hand | IDLE-before rows | S2 ACTIVE | Associated event |
|---|---:|---:|---:|---:|---|
| A HELLO195–201 |7|5|7|0|None|
| B HELLO229–238 |10|7|10|0|None|
| C first HELLO279–286 |8|8|1|3|Event2, HELLO|
| D HELLO318–354 |37|37|37|0|None|

Three marked positive intervals lacked ACTIVE acquisition despite an already ready decoder;
there were no Admission rejections in these spans. For those observed non-activations, a recovery
WAIT lock, downstream materializer, classifier or UI drop is not the blocking stage: no candidate
opened to reach them. A/B have intermittent accepted hands; D has accepted hands/motion on all37
rows yet no ACTIVE. D spans8.732s and its separate hold boundary is uncertain, so it must not be
interpreted as a precisely isolated lexical sign. Body availability/framing, execution quality,
sparse observations and S2 learned behavior remain confounded. No specific refiner/model defect
or universal cause is established by this nonexpert capture.

Event2 opened at279, emitted at284 and reached the diagnostic UI once. Its six-source-observation
window was compatible with RecognitionV2, which returned HELLO0.99298495. This is one observed
matching event, not held-out-signer accuracy or two successful repeats. The reviewed interval ends
after commit, so its negative end-to-commit value is retained as boundary information and must
not be described as negative processing latency. The reviewer’s second HELLO is uncertain: the
evaluator’s adjacent_repeat_has_two_distinct_events=false means not demonstrated, not a measured
second-sign miss. All three pair-transition metrics remain UNCERTAIN; no A/B transition advantage
or recovery-timer change is supported.

The human-confirmed ordinary-movement interval391–427 contains event3 entirely (logical399–401,
commit404), classified WASH2 with0.23730668 probability. This is one bounded non-sign activation
in the diagnostic stream. It is not a product false-positive rate or a demonstrated false word in
the normal app sentence. The separate held-position negative remains unlabelled/uncertain;
no hold-duplicate safety claim is possible. The diagnostic Activity bypasses normal SentenceBuilder
presentation, so consecutive repeated-word sentence behavior remains a separate production gate.

These findings support the previous reviewed historical evidence against treating the400ms
requirement as the sole cause. That capture had six/seven confident signs with no ACTIVE and
hands-up HOME with13 IDLE observations despite accepted hands. The rejected context reset raised
reviewed non-sign events4→9. Current same-input parity rules out a serialization/host-state replay
mismatch for these saved inputs, not perception or model semantic errors.

Retain Stage1 disabled. Do not shorten timers or deploy the rejected history reset. Prioritize evidence availability and ACTIVE acquisition; a timer-only change cannot create
missing state evidence and risks extra non-sign activations. Existing HOME/repeat-second/hold
labels remain uncertain. The smallest decisive follow-up is one qualified design signer repeating
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

The validated human review is now saved as transition_review/human_boundaries.json; use the same
command with analyze instead of prepare to reproduce the completed boundary analysis. Same-observation S2 replay uses the existing
recognition_v3_stage2_audit.verify_s2(session) helper, not the legacy Phase7 six-attempt CLI.

No runtime recognition policy was changed. Omit recognition_v3_stage2_diagnostics for the legacy
diagnostic profile, or leave diagnostics for the normal integrated app. The saved serial baseline
APK can be restored with install-r using the same signing key and without clearing storage;
canonical/protected checkouts, all weights/data and earlier APKs/evidence remain intact.