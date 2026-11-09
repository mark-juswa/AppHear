# EXP-P3-002 — Commit-gate study (calibration, global vs class-specific thresholds, temporal rule)

| Field | Value |
|---|---|
| **ID** | EXP-P3-002 |
| **Hypotheses** | G1 top-1 probability is *not* a calibrated probability. G2 one global floor is a compromise across signers. G3 a global floor removes proportionally more valid words of hard classes. G4 there is too little independent data for class-specific thresholds. G5 the WORD-v2 candidate changes the precision/recall trade-off at the event level. G6 trimming-stability (a temporal-consistency proxy) is not a better separator than top-1 probability. |
| **Baseline** | Production gate: STABLE floor 0.55, EXPERIMENTAL floor 0.75 (unchanged), frozen recognizer `1ccf0afa…`; WORD v2 candidate `1de85b3c…` |
| **Dataset / split** | Event ledgers `docs/audit/probes/event_reliability/stream_ledger_*.json`: held-out stitched ASL-Citizen streams, 5 DEV signers. Calibration signers P5/P12/P21, validation signers P26/P39 (the repo's pre-registered split). DEV-exposed. |
| **Configuration** | `python -m eval.recognition_experiments.gate_study`; labels as Phase 1 (correct = credited sign with equal top-1; everything else wrong) |
| **Training** | none |
| **Metrics** | reliability bins, ECE, Brier; per-signer Youden optimum; retention (recall of correct events), precision, coverage = committed / events, false-rejection rate, F1; exact McNemar; AUC |
| **Model size / latency** | no model change; the gate costs one comparison per event |

## Results (COMPUTED; production thresholds unchanged)

**G1 Calibration** (ECE of top-1 probability: genuine events / all events; perfect calibration is 0)
| Ledger | frozen | WORD v2 |
|---|---|---|
| STABLE (S2-R2) | 0.227 / 0.268 | 0.182 / 0.228 |
| EXPERIMENTAL (Arm A) | 0.192 / 0.230 | 0.151 / 0.189 |

The recognizer is badly **over-confident on new signers** (ECE 0.15–0.27). Its probability is a ranking score; the floors 0.55 / 0.75 are empirical operating points, which is how the gate already treats them. A temperature fitted on training signers would not fix this (the over-confidence is cross-signer).

**G2 Per-signer optimal floor** (frozen; Youden on that signer alone). STABLE: P12 0.6216 (n=48), P21 0.5751 (n=193), P26 0.6705 (n=173), P39 0.7972 (n=204), P5 0.8033 (n=26). EXPERIMENTAL: P12 0.6718 (n=67), P21 0.5671 (n=254), P26 0.8104 (n=279), P39 0.774 (n=356), P5 0.7888 (n=43). The optimum varies from ≈ 0.57 to ≈ 0.80 even among the three large signers, and small signers are noisy. One global floor is therefore a compromise, but a per-signer floor is not implementable (no signer identity or enrolment at run time) and not estimable (≤ 270 events per signer).

**G3 Global floor by predicted-class group** (fraction of correct events kept / of wrong events kept at the shipped floor)
| Ledger | hard-class events | correct kept | wrong kept | other events | correct kept | wrong kept |
|---|---:|---:|---:|---:|---:|---:|
| S2_R2 baseline (STABLE) | 222 | 0.667 | 0.350 | 422 | 0.800 | 0.420 |
| Arm A + CB70 (EXPERIMENTAL) | 321 | 0.465 | 0.149 | 678 | 0.671 | 0.262 |

Valid words of hard classes are withheld more often because their confidence is lower. That is the expected price of a confidence rule; it is not evidence that a different global value would help.

**G4 Support for class-specific thresholds**
| Ledger | classes seen | median events/class | max | classes ≥ 10 events | ≥ 10 on calibration signers | ≥ 30 events |
|---|---:|---:|---:|---:|---:|---:|
| S2_R2 baseline (STABLE) | 199 | 3 | 16 | 2 | 0 | 0 |
| Arm A + CB70 (EXPERIMENTAL) | 220 | 4 | 22 | 13 | 1 | 0 |

No class has ≥ 30 events and at most one class has ≥ 10 events on the calibration signers: **there is no independent calibration data for class-specific thresholds**, so none were built.

**G5 Frozen vs WORD v2 on identical validation events** (P26, P39; each model calibrated on P5/P12/P21 only)
| Ledger / model | committed correct | committed wrong | precision | retention (recall) | false-rejection | coverage | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| STABLE frozen, ungated | 135 | 242 | 0.358 | 1.000 | 0.000 | 1.000 | 0.527 |
| STABLE frozen, gated at 0.5751 | 98 | 98 | 0.500 | 0.726 | 0.274 | 0.520 | 0.592 |
| STABLE v2, ungated | 138 | 239 | 0.366 | 1.000 | 0.000 | 1.000 | 0.536 |
| STABLE v2, gated at 0.6534 | 86 | 79 | 0.521 | 0.623 | 0.377 | 0.438 | 0.568 |
| EXPERIMENTAL frozen, ungated | 265 | 370 | 0.417 | 1.000 | 0.000 | 1.000 | 0.589 |
| EXPERIMENTAL frozen, gated at 0.6694 | 186 | 123 | 0.602 | 0.702 | 0.298 | 0.487 | 0.648 |
| EXPERIMENTAL v2, ungated | 286 | 349 | 0.450 | 1.000 | 0.000 | 1.000 | 0.621 |
| EXPERIMENTAL v2, gated at 0.6631 | 199 | 109 | 0.646 | 0.696 | 0.304 | 0.485 | 0.670 |

Paired top-1 on genuine validation events (ungated): STABLE both-correct 116, frozen-only 19, v2-only 22 (exact McNemar p = 0.7552); EXPERIMENTAL 240 / 25 / 46 (p = 0.017). On the production segmenter the v2 candidate is **not distinguishable** from the frozen model and its F1 is lower; with Arm A it is better (more correct words, fewer wrong, higher F1, p = 0.017). Mixed, DEV-exposed, and WORD v2 is superseded by the blend candidates, for which no event-level data exists here.

**G6 Temporal consistency proxy** (AUC of "event is a correct word")
| Ledger | stability under trimming | top-1 probability |
|---|---:|---:|
| S2_R2 baseline (STABLE) | 0.6528 | 0.766 |
| Arm A + CB70 (EXPERIMENTAL) | 0.6624 | 0.7601 |

Stability is a weaker separator than the probability already in use and would need three extra recognizer invocations per event. **Not supported; not implemented.** A genuine multi-frame consistency rule would need a per-frame recognizer stream the current event-based architecture does not produce.

**G7 Are the shipped floors well placed?** (frozen model; the ledger's own calibration-signer Youden optimum vs the shipped value)
| Ledger | optimum on P5/P12/P21 | J cal / J validation | shipped floor | J cal / J validation | validation correct / wrong at optimum | at shipped |
|---|---:|---|---:|---|---|---|
| S2_R2 baseline (STABLE) | 0.5751 | 0.475 / 0.321 | 0.55 | 0.459 / 0.327 | 98 / 98 | 101 / 102 |
| Arm A + CB70 (EXPERIMENTAL) | 0.6694 | 0.440 / 0.369 | 0.75 | 0.422 / 0.388 | 186 / 123 | 173 / 98 |

The EXPERIMENTAL optimum on this ledger is 0.669, not the shipped 0.75 (the repo selected 0.75 with its own pooling of both stream modes and its own labelling; I could not reproduce 0.75 as a Youden optimum from this ledger). It does not matter much: validation J is slightly *higher* at the shipped floors, and the calibration-set differences (≤ 0.02) are far inside sampling noise. Both points lie on the same flat part of the trade-off curve (0.669 keeps more correct words and more wrong ones; 0.75 the reverse). **No change to either floor is justified.**

## Conclusion
Keep the existing global-floor gate. (1) The probability is uncalibrated, so floors stay empirical dials. (2) Per-signer or per-class floors are neither implementable nor supported by data. (3) No temporal rule helps in this evidence. (4) The one open gate question is the blend candidates, which have **no** calibrated floor and no event-level data in this repository (needs external artifacts or a Phase 1.1 shadow study). Limits: DEV-exposed signers, 5 signers, stitched ASL-Citizen clips rather than phone video, and a small calibration set.
