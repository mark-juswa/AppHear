# E4-Z Signing/No-Sign Gate Result

**Purpose:** Test whether a lightweight signing/no-sign gate can run before the E4-S primary + E4-V GOOD/SORRY routed recognizer to prevent the real N0/P1 false commits found in E4-Y.
**Scope:** Offline diagnostic only. No Android integration, TFLite export, production asset replacement, dataset mutation, or production recognizer change is authorized.
**Current status:** COMPLETE / STRUCTURAL CHECK PASSED / GATE FAILED.
**Last updated:** 2026-08-02.

## Verified Project References

- Runner: `pipeline/rgb/e4_z_signing_gate.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_z_signing_gate_01`
- Positive source: E4-S active + withheld SORRY feature tensors
- Negative source: E4-Y real MediaPipe N0/P1 feature tensor
- Routed policy source: E4-X primary confidence `0.95`, specialist confidence `0.50`
- Metrics: `artifacts/recognition_upgrade/e4_generalization/e4_z_signing_gate_01/metrics/signing_gate_metrics.json`
- Threshold grid: `artifacts/recognition_upgrade/e4_generalization/e4_z_signing_gate_01/metrics/gate_threshold_grid.csv`
- Structural check: passed with `--require-metrics`.

## Experiment Design

E4-Z compared two gate families before the routed recognizer commits a gloss:

1. Rule-based gates using summary features from `[96,258]` windows:
   - `combined_motion`
   - `presence_motion`
   - `hand_motion`
   - `hand_nonzero`
2. Tiny learned summary-feature MLP using the same summary features.

Summary features included hand/pose magnitude, nonzero proportions, hand/pose motion, frame coverage, and combined motion scores.

Dataset:

- total rows: `319`
- train rows: `116` positive-only rows
- validation rows: `53`
- test rows: `150`
- sources: `221` E4-S active, `50` E4-S withheld SORRY, `24` N0, `24` P1

Important limitation: the learned gate used E4-Y validation no-sign rows for training because a true no-sign training split does not yet exist.

## Results

The gate did not pass the system criteria.

Best branch selected by the script: `rule_combined_motion`.

Rule gates:

- eliminated real N0/P1 false commits: max no-sign false-commit rate `0.0000`
- but positive coverage collapsed to about `0.32` to `0.40`
- `SORRY` recall collapsed to `0.0000`
- `HELLO` recall also collapsed badly under motion-only thresholds

Learned summary MLP:

- minimum accepted precision: `0.9500`
- mean positive coverage: `0.5169`
- maximum no-sign false-commit rate: `0.09375`
- GOOD recall: `0.9667`
- SORRY recall: mean `0.1111`, minimum `0.0000`

## Interpretation

E4-Z confirms the key tradeoff:

- A strict motion/presence gate can stop false commits, but it rejects many real signs, especially low-motion or chest/face-centered signs such as `SORRY`.
- A learned summary gate is more flexible, but with the current tiny no-sign dataset it still fails to preserve `SORRY` and is not reliable enough.

This means the no-sign problem is real and cannot be fixed safely by simply tightening confidence thresholds or using a crude motion gate.

## Architecture Decision

Do not proceed to Android/export. The architecture still needs a signing/no-sign gate, but E4-Z shows the gate must be trained and validated on a larger, better split negative dataset and must preserve low-motion signs.

The current target remains:

`MediaPipe landmarks -> learned/calibrated signing gate -> primary recognizer -> confusion registry/router -> specialist -> calibrated accept/reject -> sentence/UI`

However, the signing gate is now an explicit blocker before runtime integration.

## Open Questions

- How many N0/P1 windows are needed for a true train/validation/test no-sign split?
- Can we collect or extract enough no-sign negatives without manually reviewing hundreds more frames?
- Should `SORRY` and other low-motion signs receive special gate protection or a lower gate threshold after primary/specialist agreement?
- Would a temporal gate trained on longer windows work better than summary features?
- Can a gate use recognizer-logit dynamics plus landmark motion instead of landmark motion alone?

## Risks

- Rule-only gating can make the app appear safe by rejecting most useful signing.
- Learned gating can overfit small no-sign data and fail on new users/devices.
- Low-motion signs are at high risk of being filtered out before recognition.
- Android integration before this is solved would create false translations during idle camera use.

## Next Required Action

Prepare E4-AA no-sign dataset expansion and gate redesign. The next package should:

- extract a larger N0/P1 set using the E4-Y cache pattern;
- create true train/validation/test no-sign splits by participant/device/clip where possible;
- include low-motion positive signs such as `SORRY` in gate training/evaluation;
- compare a temporal binary gate over `[96,258]` windows against summary-feature rules;
- report the routed recognizer after gate, with per-class recall and N0/P1 false commits.

Do not integrate Android, export TFLite, or expand vocabulary until a gate preserves real signs and rejects no-sign windows.
