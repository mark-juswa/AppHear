# Experimental bounded Fingerspell Android v1

Application alignment pending: initial integration was built on cc1f394 (September29).
User identified the newer application baseline cee71d9,
`baseline/apphear-text-to-asl-context-assist-ui-2026-10-04`. Its Context Assist/UI/session
callback additions must be preserved when porting this work. Host/device model parity
stands, but the current APK does not establish integration with that newer baseline.

Authority: user Android-integration request 2026-10-04. This supersedes the restriction
on further visual development only for faithful integration/testing of the existing
candidate. The residual experiment remains `NOT_SUPPORTED` by its research promotion
rule. No accuracy improvement or release promotion is implied.

`-Pfingerspell=true` enables debug-only controls/assets; default/release false. No
automatic routing. Candidate01 runs once; its raw observation and borrowed current
CameraX RGBA image are routed before WORD `consume()`. Existing PhoneProductionSession,
SentenceBuilder, S2, lifecycle math, RecognitionV2, word assets and Context Assist stay
unchanged. Analyzer changes only optional ownership routing/result presentation.

## Contract

- Adapter v1 405 columns copied from the previously parity-tested JVM reference;
  runtime manifest pins config/implementation/column identities before model loading.
- Current-frame quality/dedup/crop copied semantically from residual v1. Both geometry
  slots remain untouched. Appearance only is suppressed when quality is zero/duplicate.
- Upright RGBA addressing equals Candidate01 inverse rotations 0/90/180/270, preserves
  row/pixel strides and buffer position, never reflects source pixels.
- Expanded square ROI ×1.1, 128 RGB, float32 endpoint-aligned zero-border bilinear,
  RGB/127.5−1. No bitmap resize, interpolation of observations, or forward-fill.
- Frozen MobileNetV3Small FP32 →576 each trusted slot. Sequence packed width1559 is
  geometry405 + two embeddings576 + two quality values. Mask is a separate [1,T,1].
- Frozen residual epoch035 →28 logits, dynamic stride1 T. Alphabet A–Z, SPACE26,
  blank27; subtract fixed0.5 blank penalty then standard greedy collapse/removal.
- Separate 512-observation/60-second *resource guards*. No fixed training window or
  padding/duplication. Over-limit capture is refused visibly and must be retried.
- One Start/Done = one CTC sequence. Keep preview separate from confirmed text. Use
  commits only to FingerspellBuffer. Confirmed spelling can use existing speech player;
  no spelling enters SentenceBuilder. WORD text survives mode switches independently.

## Ownership/threading

Single CameraX executor owns mode, session, Adapter state and both TFLite interpreters.
Model construction happens off-main before binding; geometry/crop/appearance happen on
the camera worker; one sequence invocation occurs on Done on that worker. This simple
initial implementation must be profiled: encoder cost may reduce delivered cadence.
No second camera, detector, Candidate01 run, delegate or speculative optimization.

Mode transitions cancel partial spelling and call the existing WORD temporal reset;
they never clear WORD sentence text. FINGERSPELL Ready/Capturing/Preview/Error all
withhold WORD consumption, not just UI display. Start/Done/Use/Retry/Clear actions enter
the same executor. Lifecycle cancellation invalidates pending session tokens; UI rejects
stale snapshots. Existing shutdown joins the worker before closing native resources.

## Evidence and gates

Host FP32 export parity: six real native/phone sequences from TRAIN DAUN, TRAIN
MacKenzie and governed DEV; decoder and zero-quality B2 parity passed. Xiaomi actual
Android:523 observations feature error0, crop error0, quality max error5.96e−8,
embedding1.60e−5, logits9.06e−6. Six causal-prefix and six actual-checkpoint zero-visual
fallback checks also passed. Input math does not use handedness/Z/world coordinates.

Pinned Android TFLite2.16.1 has a dynamic-output Java shape cache: let `run` perform
allocation after resize, request no Java output array, and retrieve output tensor buffer
after invocation. Calling allocateTensors explicitly before run left stale output shape.
This targeted buffer-handling correction does not change the graph or learned weights.

Live capture/latency/WORD F22 interaction and cross-signer phone recognition remain
separate gates. Numerical fixture parity is not end-to-end signer-independent accuracy.
Reports under artifacts/fingerspelling_android_01; device JSON under application-private
files/fingerspelling_sessions. No RGB video/raw landmarks retained by this integration.


## Decoder-only amendment — 2026-10-05

The prior greedy-preview statement above is superseded for the isolated experimental
October4 Android integration. Frozen model/405-feature/crop/quality contracts remain
unchanged. Done now uses validated prefix beam width10 Top-1 with blank27 penalty0.5
once; greedily decoded raw text remains internal diagnostic/reference.
523 Python/JVM/Xiaomi fixtures match exactly, including repeated symbols and SPACE.
Actual preview confirmed by user; Clear/return-to-WORD and preserved sentence ownership
pass. No Top-N or language correction. Full evidence and current private APK identity:
docs/apphear-fingerspelling-android-beam-top1-2026-10-05.md.
ANDROID_BEAM_TOP1_PASS is an integration decision, not new model accuracy evidence.


## Geometry-only epoch038 Android package — 2026-10-07

Experimental candidate is TRAIN4096_EPOCH038_GEOMETRY_ONLY, exact checkpoint
b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886. No feature-schema
change: Adapter.v1 [T,405], mask semantics, chronology and temporal math remain frozen.

| Component | Source | Input -> output | Contract / preservation |
|---|---|---|---|
| Pinned geometry-only export | tools/fingerspelling/android_train4096_export.py | epoch038 Keras -> FP32 builtin TFLite [1,T,405]+mask -> [1,T,28] | separate artifacts/fingerspelling_train4096_android_01; strict checkpoint/package identities; no residual/appearance/quantization |
| Dual pinned isolated package loader | C: October4 integration worktree FingerspellModels/FingerspellRuntime/FingerspellCore | geometry405 or preserved visual1559 -> same bounded session/logits/preview | no visual computation in geometry mode; old manifest/default still loadable; existing debug artifact-directory property; WORD/analyzer/activity unchanged |

Blank27 penalty0.5 once; beam10 Top-1 and diagnostic greedy unchanged. Host14-case
Keras/TFLite max error1.55e-5; Xiaomi14-case Keras/Android1.46e-5, TFLite/Android1.19e-5,
1246-observation Adapter error0, exact strings; 523 beam fixtures pass. Old visual
rollback parity passes separately. Report: docs/apphear-fingerspelling-train4096-epoch038-android-2026-10-07.md.
TRAIN4096_EPOCH038_ANDROID_PASS is engineering transfer only, not phone accuracy.


## V2.1 epoch034 geometry-only transfer — 2026-10-08 (latest candidate)

SEQUENCE_V2_1_EPOCH034_GEOMETRY_ONLY is now the installed experimental package.
Main-only checkpoint SHA3f92287c5ee82b2e0de1d396c4d27fe3b0efaed8af23b79b878740a56f1af638.
TFLite SHAe78de274b967acf0ea9d30bd3f3ac4422a1ef8ebdd95c8676b57dd05fed75c4c;
manifestSHA8edc998728fa41883abacbc8382359d6d61621bc259da78ca7c2ab6f8126d01e.
Old epoch038/residual packages remain preserved rollback/reference paths.

Full-sequence symmetric TCN292956params,[1,T,405]+mask->[1,T,28], no auxiliary
head/appearance/residual. Existing artifact-directory debug flag selects it;
no UI/session/analyzer/owner/WORD change. Do not apply causal-prefix invariance.
Adapter/decoder unchanged: blank27/.5once/beam10Top-1 plus diagnostic greedy.
14numeric/text/maskfixtures,1246Adapterobservations,523beamfixtures pass.157host
regressions and7distinct device tests pass (new parity repeated after test-only
masked-padding decoding correction).235non-fingerspelling APK assets unchanged.

Saved phone-like warm model p50/p957.30/7.72ms,beam17.36/21.98ms,total24.61/29.82ms
(sixcases; floor percentile). Four nonexpert AMY retries5.79–6.44observations/s,
95–480msDone processing,16–21observed-handframes each. ResultsAMSEY/ASEEAY/AEAY/
AMEMEAY remain inaccurate. No live accuracy improvement claim, training record,
new weights, decoder tuning or production promotion.

FINGERSPELL_V2_1_ANDROID_PASS is engineering only. Evidence root:
artifacts/fingerspelling_sequence_v2_1_android_01; report:
docs/apphear-fingerspelling-v2-1-android-transfer-2026-10-08.md.
Exact no-input safeguard not added; it cannot repair partly observable AMY errors.


Final transfer review correction — 2026-10-08: the epoch038 instrumentation test
received only an explicit candidate-applicability assumption; its causal/numerical
checks and fixtures are unchanged. The V2.1 test uses its own candidate guard.
Final1599hash inventory has2intended existing changes (isolated model loader and
old test guard),1597unchanged; all WORD/Candidate01/Adapter/model/rollback files
remain unchanged. Final candidate test:1applicable parity pass/1intentional old
candidate skip. No product/inference changes since the four AMY captures. Main
privateAPK SHA068c744df22acefdc48f44246e2f533127c73d63a332d3e2617f9c52d3b24c4e
unchanged. Exact final test companion identity and latest timing measurements are
in artifact apk_identities.json/runtime_summary.json. No active training/job.
Next: separate exact no-input guard only; cannot fix/refuse these AMY retries.
