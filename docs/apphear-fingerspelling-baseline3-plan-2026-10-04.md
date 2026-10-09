# Baseline 3 frozen implementation plan

User-authorized offline stable-hand experiment; no production changes. The prior generic
pose/hand ablation prohibition is not an objection to this explicitly authorized separate
alphabet representation: keep body reference and compact distinct-secondary evidence;
reduce duplicated hand geometry to address identity ambiguity, not latency.

Evidence before implementation: 217221 raw frames; 70863 both observed; 50577 substantial
ROI overlap, 43309 overlap/near-wrist duplicate proxies; 467 conservative continuous
single-slot changes. Physical identity is not proven. B2 epoch76 metadata-fixed 64 TRAIN
diagnostic: native CER48.24%, sparse43.12%; DEV58.43%/54.82%. TRAIN also poor, so capacity
increase is permissible but not compelled: keep64 channels to isolate representation.

Definitions: primary is one causal heuristic identity, not certified dominant/signing hand;
duplicate is spatial evidence, not a two-hand ground truth label; continuity is an observed
spatial association, not interpolated geometry; parity means isolated JVM math, not deployed
Android; success means a useful controlled research comparison, not product accuracy.

Canonicalizer v1: observed hand, valid wrist and >=5 valid joints forms a candidate. Quality
is 0.5 valid-joint fraction +0.3 finite-clamped presence +0.2 mean finite-clamped proposal
support; scores are heuristic, not calibrated confidence. Associate closest wrist to last
observed primary only with same dimensions, gap<=1s, distance<=0.25 short-side units.
Choose nearest spatial candidate; without association choose highest quality then wrist x/y.
Coordinate ties use slot index only for indistinguishable evidence; input never contains
slot ID. Flag close competing association distances (<0.03) as ambiguous for distinct hands.
Duplicate: both valid, ROI IoU>=0.6 and wrist distance<=0.08 short side. Otherwise simultaneous
candidates are potentially distinct, not proven distinct. Preserve only their coarse context.
No handedness, transcript, future state or model prediction. A remembered wrist associates
through short gaps but is never emitted as a current observation. Motion requires adjacent
selected primary observations and accepted spatial continuity; no motion across missing,
long gap, distant identity reacquisition or resolution change.

Adapter v2 [T,255]: time2 + primary181 (same current-hand geometry/support/masks as v1)
+ body41 + canonical state8 + secondary context8 + five fingertip displacements/masks15.
Reuse v1 common float math on remapped actual slot evidence; no v1 edits. Body is retained,
no full-body gate. Secondary full joints absent; distinct-context fields remain. Canonical
state: valid, quality, continuous, ambiguous, duplicate, potentially_distinct, reset,
candidate_count/2. Neither selected slot nor slot-change indicator is input. Secondary:
observed, presence, presence_valid, ROI x/y/side, ROI_valid, context_valid. Tip motion is
source-short-side-normalized displacement, not velocity. Invalid numerics zero+mask.

Temporal views unchanged: first select real raw observations; canonicalize and derive each
view independently after selection. Native/intermediate/phone all run same state machine.
Separate v2 NPZ/receipts pin original manifest/raw/source and new code/config/column hashes;
do not change frozen foundation or source roles. No re-extraction/redownload, TEST sealed.
Generate compact features from existing caches; serial resumable preparation. Agent may
materialize this inexpensive raw-to-feature transform, never long training.

Isolated Kotlin reference outside Android mirrors common evidence, canonical decisions,
float arithmetic and feature order. Golden tests exercise slot swaps, duplicates, partial
validity, missing/gaps/resolution and real native/sparse sequences. No production caller.

Same causal TCN layers/dilations/64channels/Adam/batch/seed as B2, variable255 input. New
versioned cache/runner reuses B2 regime schedule, CTC loss and emission evaluation/calibration
without editing B2's pinned trainer. Select mean raw native/sparse DEV CER, same90/30/15/0.002
policy and fixed calibration guards. Add full per-character alignment confusion/recall metrics.
Short engineering smoke including weights/Adam/resume; no smoke quality claim. Full run user-only.

Readiness gates: deterministic/causal/slot-permutation invariant fixtures (excluding identical
coordinate/quality ties with different unobserved finger details, explicitly uncertain), JVM
parity, raw-to-features hashes, all1280 official identities, finite masks/time, CTC fallback,
smoke/resume. Stop on actual correctness/parity failure. Imprint new contract and preserve old.
Future B3 result must compare raw CER/substitutions/character recall/signer spread/exact strings
with B2; no capacity or decoder-family sweep, language prior or automatic Android rollout.
