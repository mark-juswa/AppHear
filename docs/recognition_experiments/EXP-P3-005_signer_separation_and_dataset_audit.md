# EXP-P3-005 — Signer separation and dataset audit

| Field | Value |
|---|---|
| **ID** | EXP-P3-005 |
| **Hypothesis** | Training, calibration and evaluation data are signer-disjoint, and the dataset has no structure that would inflate or hide the reported accuracy. |
| **Dataset / split** | ASL Citizen official split `artifacts/splits.json` (content hash `b992940a3df2078d`); recognizer population tables from `docs/audit/WORD_ACCURACY_236_2026-10-17.md` |
| **Configuration** | `tests/test_recognition_experiments.py::SignerSeparationTest`; training script `model/perception_vnext/recognition_v2_236.py` read (not run); no raw dataset is present in the repo |
| **Training** | none |

## Verified
- **Signer-disjoint splits (COMPUTED):** train 35 signers / 40,154 clips, val 6 / 10,304, test 11 / 32,941; the three sets are pairwise disjoint. The five DEV signers (P5, P12, P21, P26, P39) are all val-split signers; none is a train or test signer.
- **Gate calibration:** calibration signers P5/P12/P21 and validation signers P26/P39 are disjoint (tested).
- **Training-script governance (read):** refuses to run unless `protected_test_access` is false; **forbids a balanced sampler** (`VNEXT_V2_BALANCED_SAMPLER_FORBIDDEN`); trains on dense + sparse views; AdamW; checkpoint chosen on DEV `val_loss` and early stopping on the same → **DEV is selection-exposed for every recognizer.**
- **Train/serve consistency:** the Recognition-v2 feature builder has JVM parity (`RecognitionV2JvmParityTest`, in the 415 passing JVM tests) and device parity (passing instrumented tests above).
- **Class mapping:** 236 classes identical across Android manifests and `vocab.json` (EXP-P3-003).

## Composition (REPO-REPORTED)
Recognizer TRAIN 3,926 clips, 40 signers (35 ASL Citizen, 4 LOCAL, 1 APPHEAR capture), 8–20 clips per class except GOOD / HAVE / HELLO / KNOW / SORRY (120–190). Independent evaluation: DEV 816 clips (5 signers), Sem-Lex EVAL 777 clips (13 signers, 63 classes), phone 29 signs (1 developer, 3 classes).

## Concerns (none blocks the offline numbers; all limit what they prove)
1. **Phone evidence may not be signer-disjoint.** The `APPHEAR_CAPTURE` TRAIN signer (297 clips) *may be* the phone design signer (the repo's own audit says identity is not authoritative). The phone words HELLO (190 clips), HOME, TABLE are also among the best-trained classes. Phone results are therefore optimistic on two counts and are DEV-exposed; Phase 1's phone numbers inherit this.
2. **Class imbalance:** five heavy classes attract 4.4–5.1 % of wrong predictions vs 2.1 % expected (≈ 1.3–1.8 points of accuracy). Balanced sampling was tested and was harmful (`SAMPLING_HARMFUL`), hence forbidden. Not a lever.
3. **Signer diversity per class is thin:** median 13 training signers, 23 classes with < 12; recall correlates with training fit (ρ = 0.53) and weakly with signer count (ρ = 0.24).
4. **Evaluation support is thin:** median 4 independent clips per class; 47 classes meet the repo's RELIABLE tier (≥ 8 clips, ≥ 5 signers).

## Not auditable here (NOT AVAILABLE)
Duplicate clips, incorrect annotations and class-wise label noise: the raw videos and indices are external (`F:` drive artifacts). The only annotation-quality evidence in the repo is that Sem-Lex forms were human-reviewed ("human-accepted forms"). Differences between training and inference features beyond the parity tests were not re-derived.

## Conclusion
Hypothesis supported for signer separation of training / calibration / DEV evaluation, with the phone-set caveat. Dataset quality beyond that cannot be audited without the external data.
