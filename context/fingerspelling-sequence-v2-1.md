# Fingerspell V2.1 — training-only local-letter objective

Authorized 2026-10-08. Separate opt-in research runner; no Android or WORD changes.

## Frozen graph and semantics

Reuse the original V2 graph, initialized from epoch046 SHA
`88a92131eb07ce97b18f2ad4b9ea8d927858c1582177b5a04105a361e071c96a`.
Fresh Adam; unchanged V2 LR0.001, clip5, dropout0.1, CPU2, batch8, seed20261007.
No warm-start optimizer reuse and no weight/learning-rate sweep.

Main path: symmetric masked TCN64, two kernel3 convolutions per residual block,
dilations1/2/4/8/16/32/64/128, stride1, RF1021, 292956 parameters.
Input `[B,T,405]` plus real-observation time mask `[B,T,1]`; main logits `[B,T,28]`.

Auxiliary tap: `v2_block3_mask` (after the fourth residual block), RF61 observations
(30 earlier/30 later). Dense64→27 plus existing time mask,1755 extra parameters.
Auxiliary blank26; letters0–25. No SPACE output. Remove only token26 from valid
authoritative targets; padded target storage must not count as real A labels.
Repeated letters retained, including repeats newly adjacent after SPACE removal.
No pseudo boundaries or predictions as targets.

Loss: mean main CTC(blank27) +0.5×mean local CTC(blank26). Report main, local and
total separately. Lambda frozen from TRAIN-only engineering; no DEV selection.
Both use the same real timestep count. Space removal cannot increase required
CTC length beyond the original target, even when it joins equal letters.

Dual-output training checkpoint is separate from the main-only inference view.
The main-only Keras graph removes all auxiliary operations and retains exactly
the original V2 layer topology and28 logits. No TFLite export/Android install in
this phase; smoke reload/topology checks are not trained-model device parity.

## Data and selection

Original4096 TRAIN /256 DEV-A, same governed receipts/roles. Frozen V2 raw-derived
missingness and four-regime rotation/fallback reused. No acquisition/extraction.
Early stopping max90/min30/patience15/anchor improvement0.002 remains unchanged.

Selection uses uncalibrated greedy main-head outputs, consistent with the prior
trainer, and the equal mean of native-full, phone-full, native-no-SPACE and
phone-no-SPACE DEV-A CER. No-SPACE scoring removes spaces from both reference
and main decoded prediction before edit alignment. It never uses the local head
to select or decode. First strict minimum, first tie; no stress/DEV-B selection.

Final inference uses unchanged main head, beam10,blank27,penalty0.5,Top-1. No tuning.
DEV-B opens only after selected checkpoint/config/completion lock, and must never
become a tuning loop. TEST sealed.

## Final diagnosis and decision

Paired evaluation: V2.1, frozen V2 epoch046 and epoch038 on original native/phone
and identical moderate/heavy/contiguous stress inputs. Preserve original full
transcript metrics, spaces-removed re-alignment, original-alignment letter recall,
SPACE correct, single-word membership (same42 IDs as V2 review), signer and J/Z/
repeat groups. These quantities are different and must not be conflated.

Uniform safeguard: any A–Z letter with ≥100 pooled DEV-A+DEV-B phone references
and recall regression >10 absolute percentage points versus epoch038 is flagged
as an important failure. No letter-specific training/decoder correction.

Final quality outcome requires review of actual saved results. Lower full CER or
the tiny overfit gate alone does not establish success. If letter discrimination
does not materially improve, stop geometry-only encoder experiments; do not
automatically introduce V2.2/V3. No automatic appearance work or Android rollout.

## Components

- `model/fingerspelling_sequence_v2_1_encoder.py`: shared graph, local tap, inference view.
- `model/fingerspelling_sequence_v2_1_execution.py`: dual CTC and compiled gradient steps.
- `model/fingerspelling_sequence_v2_1.py`: frozen-governed training, resume, selection, final lock.
- `model/fingerspelling_sequence_v2_1_review.py`: final pooled metrics and uniform safeguards.
- `tools/fingerspelling/sequence_v2_1_smoke.py`: TRAIN-only dual overfit/padding/locality gate.
- `tools/fingerspelling/sequence_v2_1_validate.py`: TRAIN-only regime/resume gate.
- `model/config/fingerspelling_sequence_v2_1_01.json`: frozen config.

Run: `runs/fingerspelling_sequence_v2_1_01`; engineering runs use `_smoke` suffixes.
Gate: `artifacts/fingerspelling_sequence_v2_1_gate_01`.

CLI: `python -u -m model.fingerspelling_sequence_v2_1 preflight|train|status|evaluate`.
Same train command resumes a committed epoch; interrupted epoch repeats. Different
config/code/receipt identity refuses resume. Once confirmation lock exists, fitting
is prohibited. Old runs, Candidate01, Adapter, Android and WORD remain protected.
