# AppHear fingerspelling — apply the earlier roadmap after V2.1

2026-10-08. Supersedes the earlier waiting-for-V2.1 decision branches, without
rewriting the historical plan or changing the completed experiment.

## Technical decision

Retain the V2.1 epoch034 geometry-only candidate. Transfer the improvement already
demonstrated before starting any new learning experiment. Prepare the exact
no-usable-hand safeguard as a separate isolated runtime change. Park supervised
appearance development: the supervisor confirmed that no qualified ASL
fingerspelling reviewer is available, and there are zero verified letter labels.

The earlier appearance proposal was conditional on the local objective failing
to materially improve letter discrimination. That condition did not occur:
pooled phone letter recall60.16→63.16%, single-word CER49.88→44.63%, no-SPACE
CER42.69→40.23%; +189 letters/-50 SPACE versus V2. No common-character safeguard
fails. The result is supported, not production reliable: exact phone strings6/512,
several per-letter regressions, no isolated-letter or proficient-signer live test.

Do not reinterpret those limitations as proof that the conditional appearance
architecture will succeed, or as permission to launch another geometry run.

Canonical evidence:
`docs/apphear-fingerspelling-sequence-v2-1-result-review-2026-10-08.md` and
`artifacts/fingerspelling_sequence_v2_1_review_01/analysis.json`.

## Next implementation — transfer epoch034, preserving its semantics

1. Create a separate explicit FP32 geometry-only V2.1 package. Use the main-only
   `runs/fingerspelling_sequence_v2_1_01/best_candidates/epoch_034.keras`, SHA256
   `3f92287c5ee82b2e0de1d396c4d27fe3b0efaed8af23b79b878740a56f1af638`.
   Exclude the auxiliary head, MobileNet and old residual weights. Preserve
   `[1,T,405]`/mask→`[1,T,28]`, blank27, penalty0.5, beam10 Top-1.
2. Reuse geometry/raw/decoder fixtures and the existing TFLite conversion helper.
   Adapt only the new export and isolated package identity; do not overwrite the
   epoch038 exporter, model, manifest, parity evidence or Android rollback package.
3. **Required export correction identified from code:**
   `tools/fingerspelling/android_train4096_export.py` is pinned to epoch038 and
   asserts prefix-invariance, appropriate to its causal encoder. V2.1 is symmetric
   and non-causal. Do not run the old exporter unchanged or merely replace its
   checkpoint constant. Use full-sequence numerical parity, time-mask/padding
   invariance and identical greedy/beam outputs. Future observations may
   legitimately change earlier logits. Retain the old causal assertions for old
   packages; do not weaken parity tolerances to hide an export error.
4. Verify Keras→FP32 TFLite on native/phone, short/long, repeats/SPACE and missing
   evidence fixtures. Require exact decoded text agreement and report logit
   tolerances/errors. Smoke-check the trained graph, not the old architecture
   smoke model. No quantization, decoder retuning or retraining.
5. Use the authoritative October4 Android worktree. Its isolated
   `FingerspellModels.logits` already receives the completed session sequence;
   preserve bounded Done-time execution rather than introducing streaming
   prefix inference. Add only an explicit experimental V2.1 package identity.
   Perform device numerical/text parity and timing before retention. Do not edit
   `PhoneProductionSession`, WORD ownership semantics or sentence storage.
6. Keep epoch038 installed until these gates pass. Then use bounded engineering
   smoke and WORD preservation checks. With no proficient signer, live attempts
   establish input/model/preview wiring only, never A–Z accuracy.

This document does not claim that epoch034 was exported or installed. The current
session only inspected the transfer seam and updated the roadmap. No build or
device action was performed.

## Separate small safeguard — complete absence of usable hand evidence

The tested offline `pipeline/fingerspelling/input_evidence.py` is already built.
Its runtime counterpart belongs only inside FINGERSPELL capture/Done handling.
Count a real observation as usable when an accepted slot has at least one valid
joint. Do not infer two physical hands from the two slots.

At Done, if every observation lacks accepted usable hand geometry, refuse an
unsupported spelling and provide Retry. Distinguish no accepted hand from accepted
flags without valid joints. If any usable hand evidence exists, retain the entire
sequence and unchanged inference. No invented percentage threshold, confidence
score, frame deletion, interpolation, forward-fill or repeated-letter suppression.
The21/51 example remains eligible. This prevents unsupported output; it does not
repair A/S/M confusion or increase measured letter accuracy by itself.

Keep this change independently flagged and independently tested after the model
transfer, so package parity cannot be confused with rejection behavior. Check
zero-hand/all-invalid/partial/both-slot evidence, session reset/cancel, repeated
letters, WORD ownership and sentence preservation. No WORD logic is reused.

## Handshape supervision — prepared, but paused

The preserved packet is
`artifacts/fingerspelling_letter_review_01/review_request.json`:
16existing TRAIN clips,16signers,8DAUN/8MacKenzie, about88seconds of original RGB.
Transcripts cover A–Z; this is not verified handshape coverage. Revalidated:
16PENDING, zero labels, `training_admitted=false`.

No qualified reviewer is available as confirmed by the supervisor in this session.
Do not replace qualified human RGB review with transcript-position fractions,
CTC peaks, decoded predictions, this agent's unverified visual guesses, or the
supervisor's nonexpert phone attempts. Such pseudo labels would turn current
errors into training targets. Do not train another frozen-ImageNet fusion branch.

No new crop-preview/annotation workflow was retained after this prerequisite was
confirmed absent. The existing request, validator and instructions are preserved
for a future competent review; human records were not overwritten.

If competent review later becomes available, first check actual hand/crop/letter
and J/Z motion feasibility in the existing packet. Only then freeze one
signer-separated handshape-supervision gate. Do not promise that16clips suffice
for training or reliable A–Z recognition. This is deferred research, not the
current delivery path and not an automatic consequence of a weak phone attempt.

## Preservation and status

-1598protected hashes unchanged; epoch034 selected hash verified.
- Existing WORD, Candidate01, raw-v1, Adapter v1, Context Assist, Android behavior,
  old models and rollback packages remain unchanged.
- No source download, perception extraction, inference, training or TEST access.
- No feature-width/schema change. Existing input assessment remains unused in
  training and Android until its separate integration gate.
- The temporary preview-code draft was removed; no untested component remains.

Immediate next phase: **V2.1 export/parity/isolated engineering transfer**. Follow
with the exact no-input safeguard; defer supervised appearance until its real
annotation prerequisite exists. Recognition remains experimental and
confirmation-based throughout.
