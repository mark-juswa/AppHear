# One-letter Fingerspell inference gate — 2026-10-08

The supervisor explicitly accepts one short capture per letter with confirmation.
This is an inference/interaction constraint using frozen V2.1 epoch034, not a new
letter-trained model or an accuracy guarantee. WORD is sealed.

## Evidence and scope

V2.1 pooled phone letter recall is 63.16%; phone exact strings are 6/512.
M recall is 47.37% and Y recall 42.11%. It improves the research reference but
does not establish reliable A–Z recognition. The 4K corpus contains no isolated
single-letter transcripts. The local training head is letters-only sequence CTC,
not human-verified frame/letter supervision. Export/Android parity passes.
Phone AMY captures have partial hand evidence and extra/wrong characters, but
the signing and per-letter timing are not verified. No cause is assigned from
those masks alone. No qualified reviewer or isolated-letter benchmark exists.

## Approved implementation

1. Exact single-label CTC scoring for A–Z, with the existing float32 blank27
   penalty0.5 and all28-symbol log-softmax. Score all alignments collapsing to
   exactly one letter. Compare the best letter with the empty CTC sequence;
   return empty when empty or the singleton SPACE has greater/equal mass. SPACE
   is a refusal competitor, never an accepted letter. No language prior,
   model change, confidence threshold, length normalization or repeated-letter
   heuristic. Scores are conditional diagnostics, not calibrated correctness.
2. Python/Kotlin reference parity and exhaustive small-path correctness tests.
3. Refuse only captures with zero accepted usable hand geometry. Partial
   missingness remains eligible; do not remove or manufacture observations.
4. One Start→Done previews at most one letter. Use explicitly appends it without
   spaces; confirmed repeated letters remain intact. Retry preserves confirmed
   letters; Clear removes the isolated spelling. Old whole-sequence Fingerspell
   path remains behind an internal rollback flag. No WORD UI/state/code edits.
5. Show actual current hand-evidence feedback, save constrained/greedy/beam
   results and bounded logits for this experimental path. No RGB/landmarks or
   training data. No automatic commit, Top-N UI or guessed class confidence.

## Gates and stop condition

Host mathematical/padding/input/buffer tests and Python/Kotlin parity precede
device installation. Use only a bounded individual A/M/Y phone engineering
check after install, explicitly acknowledging nonexpert signing. Do not infer
cross-signer accuracy from it. If it still selects wrong letters, document that
the constraint fixes excess output but cannot repair learned discrimination;
do not keep tuning it or claim that all26 letters are reliable.

Snapshot protected source/model/package hashes before edits. Only Fingerspell
decoder, buffer, runtime and isolated tests may change. Candidate01, Adapter v1,
WORD, Context Assist, old model/checkpoint/export/APK identities stay unchanged.
New artifacts: artifacts/fingerspelling_single_letter_01. No retraining, new
dataset, frame pseudo labels or Android model export is authorized/needed.
