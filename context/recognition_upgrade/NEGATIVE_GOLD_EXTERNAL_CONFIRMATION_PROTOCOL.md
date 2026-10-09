# NEGATIVE_GOLD_V1 external confirmation protocol

Status: frozen before second-pass review.

This is a human evidence-governance pass, not a perception experiment. It uses only the
completed Open Images first-pass artifacts and the frozen 76-frame NEGATIVE_GOLD_V1 seed.
No detector, landmark model, classifier, training code, Android runtime, or new download is
permitted.

## Eligibility and selection

1. Preserve the completed first-pass package byte-for-byte.
2. Start from canonical first-pass `ZERO_HAND` rows only.
3. Exclude every canonical image implicated in a first-pass hidden-repeat binary
   `ZERO_HAND`/non-`ZERO_HAND` disagreement.
4. Verify source bytes, recorded SHA-256, and 64-bit dHash.
5. Enforce the frozen near-duplicate rule: Hamming distance `<=4` is a conflict, both within
   the confirmation set and against the existing 76-frame seed.
6. Select 160 canonical candidates using source metadata and visual-fingerprint diversity
   only. Model output must not be used.
7. Insert 20 concealed, byte-identical repeats with frozen randomized order and repeat map.

## Human question

The reviewer sees only the image, progress, optional notes, and this question:

> Is ANY part of a human hand visible anywhere in this image?

Allowed labels are `ZERO_HAND`, `HAND_VISIBLE`, and `UNCERTAIN`. `ZERO_HAND` means absolutely
no fingertip, finger, palm, partial/cropped/blurred/lap/tiny/edge-clipped hand is visible.
`UNCERTAIN` can never qualify as benchmark truth. First-pass labels, Open Images metadata,
discovery category, model output, QC state, and repeat identity remain hidden.

## Frozen QC and promotion gates

- The 20 repeat pairs are diagnostic for three-class exact agreement.
- Hard gate: zero binary `ZERO_HAND` versus non-`ZERO_HAND` repeat disagreements.
- Overall exact repeat agreement must meet the existing project threshold of `>=0.92`.
- A canonical image is eligible only when first pass and second pass both equal `ZERO_HAND`.
- After review, the frozen exact/dHash rules are reapplied within the confirmed set and
  against the 76-frame seed. Thresholds cannot be loosened to reach 200.
- If at least 124 eligible diversity-clean images survive, select exactly 124, freeze
  NEGATIVE_GOLD_V1 at 200, and place any surplus in NEGATIVE_GOLD_RESERVE.
- If any hard QC gate fails, preserve the evidence and stop without silent correction.

