# Findings and decisions for the next team

This is a concise index, not another experiment proposal. Detailed dated reports are preserved under docs,
final metrics/predictions under evidence/fingerspelling, selected checkpoints under packages/research_checkpoints.

| Stage | Confirmed result | Decision / limit |
|---|---|---|
| B1 | Dense-only training collapsed at sparse phone cadence; deletions/empty output dominated | Keep realistic cadence-aware TRAIN views |
| B2 | Cadence correction largely fixed catastrophic sparse under-emission; residual character confusion remained | Preserve real observations/Adapter.v1/CTC; formal1K reference |
| B3 | Canonical geometry did not improve overall fit/discrimination | Do not continue canonicalization or Adapter.v2 as primary |
| B4 | More causal TCN capacity did not improve sparse correctly aligned letters materially | Not justification for another width sweep |
| Naive visual gate | Strong TRAIN signal but overfitting/duplicate nuisance crops | Generic ImageNet fusion not established as solution |
| Residual visual | Combined CER54.76→53.77%, decision NOT_SUPPORTED_STOP_VISUAL_PATH | Preserve evidence; old residual not on current V2.1 geometry candidate |
| Decoder audit | Fixed open-vocabulary beam10 improved residual balanced CER53.77→50.84%; phone53.69→52.16% | Beam Top1 accepted for bounded sequences; Top-N UI rejected |
| Outer-window oracle | Publisher trim reduced insertions but increased deletions/lost correct chars; overall worse | OUTER_BOUNDARY_NOT_SUPPORTED; do not build segmenter from it |
| 4K epoch038 | Broad letter/substitution/precision improvement with expanded signer/sequence exposure | Proven useful data diversity, not complete recognition |
| V2 epoch046 | Full phone CER improved, much of aligned-symbol gain from SPACE; S recall and single-word behavior regressed | Full-CER-only selection insufficient |
| V2.1 epoch034 | Letter auxiliary objective/selection correction improved actual letters and single-word CER | Retain geometry-only experimental model; not reliable all26/names |
| Held-letter UI | Supervisor confirmed separate A/M/Y then automatic accumulation/controls | Engineering evidence only, no expert signer or held-out all26 benchmark |

## Exact recent offline comparison (fixed beam10/blank penalty0.5)

| Cohort/view | 4K epoch038 | V2 epoch046 | V2.1 epoch034 |
|---|---:|---:|---:|
| DEV-A native CER |42.75%|40.27%|37.84%|
| DEV-A phone CER |46.98%|43.48%|41.91%|
| DEV-B native CER |41.88%|37.61%|35.36%|
| DEV-B phone CER |46.24%|42.71%|40.01%|
| Pooled phone no-SPACE CER |44.87%|42.69%|40.23%|
| Original-alignment letters correct /6316 |3737|3800|3989|
| Letter recall |59.17%|60.16%|63.16%|
| Exact full strings /512 |2|4|6|
| Frozen42 single-word phone CER |48.69%|49.88%|44.63%|

Evidence: `docs/apphear-fingerspelling-sequence-v2-1-result-review-2026-10-08.md` and matching final evaluations.
V2.1 adds training-only Dense64->27 letters-only CTC after block4 (1755 params), fixedlambda0.5;
main inference remains292956 params, RF1021, eight symmetric masked dilation blocks. Selection used equal-weight
DEV-A native/phone full/no-SPACE raw-greedy CER. The auxiliary head is not exported. Epoch034 selected among49;
V2.1 warm-start/auxiliary supervision/selection changed together, so separate causal effects are unidentified.
No common-character >10pp regression versus epoch038 flagged under the frozen >=100reference safeguard;
versus V2 some letters still regress (e.g.M), rare Q/X/F remain weak/uncertain. Read full per-letter table.

## What we know / believe / cannot identify

Known: delivered missing evidence exists; substitution/deletion burdens persist; successful export/parity rules
out demonstrated train/serve class-order/logit/decoder mismatch; larger data and letter-focused supervision helped.
Belief supported by errors: local handshape discrimination/generalization is the main unresolved recognition limit.
Not identified: exact physical source of each wrong letter (signing proficiency, landmark error, geometric
information loss, transition timing and supervision are not separated). Context coordination does not repair letters.

DEV-A repeatedly selected checkpoints. DEV-B was opened after earlier locks and shares15 official DEV signers;
it is post-lock confirmation under that policy, not a fresh unseen-signer population or future tuning target.
FSboard is continuous spelling/phrase supervision, not a labeled isolated26-pose dataset. Raw user phone attempts
were nonexpert engineering smokes, not training examples or accuracy measurements. TEST stays sealed.

## Known product issues and practical next work

- Held-letter stability may accept a consistently wrong letter; tracking loss can trigger repeated-letter rearm.
- A prior two-letter plateau was not fully attributable from retained trace; later UI tests display104 characters,
  no hard two-/three-letter cap; additive acceptance diagnostics exist. Do not repeat layout fixes without evidence.
- Context routing is six full-match English rules, not broad Gemini-based mode understanding; unknown/compound
  questions retain owner. No automatic completion timeout; explicit confirmation returns to WORD.
- Original ZIP clips and old retained avatar clips differ visually. All171sign meanings/framing are not reviewed.
- New Original catalog full integrity check took5.1s offUI on Xiaomi; payload737MiB; APK789MiB. Performance/size
  work is justified only by a measured product problem and must preserve semantics.
- Public production builds cannot safely distribute local embedded service keys. Service access/security needs
  separate provisioning/review; fake provider is only a deterministic test fallback.

Next: group review of actual app flow and Original mappings; qualified-signer evaluation of controlled held letters
and transition/repeat behavior before accuracy claims; report observable failures with diagnostics. No automatic
retraining, thresholds, RGB backbone sweep or fundamental WORD change. Dedicated reviewed handshape supervision
is a conditional future direction; no qualified reviewer was available, and no verified letter annotations were
created in the16-clip packet. Model labels/transcript positions must never masquerade as human frame annotations.
