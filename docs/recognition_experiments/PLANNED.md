# Planned experiments (NOT RUN)

These are the experiments the evidence calls for. None was run in Phase 3 because each needs data, humans or a device that this
environment does not have. Each states its decision rule before any result exists.

| ID | Hypothesis | Baseline | Data / split | Primary metrics | Decision rule (pre-stated) | Needs |
|---|---|---|---|---|---|---|
| EXP-P3-101 | WORD_BLEND_02 matches or beats the frozen recognizer on live phone input | STABLE + frozen | ≥ 5 new signers, signer-disjoint from the registry; the repo's 12-sign stratified protocol (`phone_test_subset.py`) plus the Phase 1.1 protocol | sign recall, precision, FPR (non-sign), false-rejection, latency | adopt only if sign recall is not lower and precision is higher with non-overlapping intervals; per-class regressions (MOUTH, TODAY, TOOMUCH, CITY2) reported | physical phone, signers, blind annotators |
| EXP-P3-102 | A calibrated confidence floor exists for WORD_BLEND_02 | no floor (structural rule only) | held-out streams re-scored with the blend recognizer; calibrate on P5/P12/P21, validate on others | retention, precision, coverage at the calibrated floor | ship a floor only if retention ≥ the frozen model's at equal or better precision on validation signers | external artifacts to run `eval/runtime_diagnostics/event_reliability.py` with the blend; or a shadow study |
| EXP-P3-103 | Lower S2 thread count (or a thread budget) raises delivered fps without changing outputs | S2 4 threads | same-pixel replay + live front/rear, owner/lens gates | frame_total p50/p95, fps, parity | keep only with exact parity and p95 improvement on the phone | physical phone (the Phase 2 diagnostics read the result) |
| EXP-P3-104 | Reviewed Sem-Lex package 03 + the same enrichment/blend rule improves the ~16 reviewable hard classes | WORD_BLEND_02 | review package 03 (30 classes); EVAL-role signers untouched | per-class recall on EVAL signers | adopt only if the reviewed classes improve on untouched signers without regressing others | human form review, GPU training environment |
| EXP-P3-105 | Arm A + confirm-boundary delivers more correct words than S2-R2 on a phone | S2-R2 | phone sessions, signer-disjoint | correct words, non-sign events, merged events | adopt only with a calibrated gate and ≥ 30 non-sign events | physical phone, Phase 1.1 study |

Explicitly **not planned** (evidence says no): class-specific thresholds (EXP-P3-002 G4), a trimming-stability or other temporal rule
(G6), larger or additional networks (information-limited, EXP-P3-001), class rebalancing (harmful), sparse-only or contrastive
training (measured negative in earlier audits).
