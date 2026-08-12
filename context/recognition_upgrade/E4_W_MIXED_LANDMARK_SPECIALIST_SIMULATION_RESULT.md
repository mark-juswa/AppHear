# E4-W Mixed Landmark Specialist Simulation Result

**Purpose:** Record whether the E4-S stable primary recognizer can be combined with the passing E4-V GOOD/SORRY landmark specialist without harming stable signs.
**Scope:** Offline window-level simulation only. No Android integration, TFLite export, production asset replacement, dataset mutation, or new training is authorized.
**Current status:** COMPLETE / PASSED AS A SMALL OFFLINE PROOF.
**Last updated:** 2026-08-02.

## Verified Project References

- Runner: `pipeline/rgb/e4_w_mixed_landmark_specialist_simulation.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_w_mixed_landmark_specialist_simulation_01`
- Primary source run: `artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01`
- Specialist source run: `artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01`
- Metrics: `artifacts/recognition_upgrade/e4_generalization/e4_w_mixed_landmark_specialist_simulation_01/metrics/mixed_router_metrics.json`
- Prediction CSVs: `artifacts/recognition_upgrade/e4_generalization/e4_w_mixed_landmark_specialist_simulation_01/predictions/seed_*_mixed_predictions.csv`
- Structural check: passed with `--require-metrics --require-predictions`.

## Experiment Design

E4-W simulates this decision path:

`E4-S primary [GOOD, HELLO, HAVE, KNOW] -> if primary top1 is GOOD, route to E4-V GOOD/SORRY landmark specialist -> final class [GOOD, HELLO, HAVE, KNOW, SORRY]`

The simulation uses the E4-S test set:

- active known-sign rows: `88`
- withheld OOV/confusion `SORRY` rows: `30`
- total rows: `118`
- seeds: `101`, `202`, `303`

This deliberately tests the exact failure from E4-S/E4-T: the primary model predicts withheld `SORRY` as `GOOD` with high confidence, so threshold-only routing failed.

## Results

Primary-alone baseline on the combined 5-class evaluation:

- mean primary accuracy: `0.7345`
- `SORRY` recall: `0.0000`
- failure mode: all 30 held-out `SORRY` test rows were committed as `GOOD` in every seed.

Mixed primary + landmark specialist:

- mean mixed accuracy: `0.9718`
- minimum mixed accuracy across seeds: `0.9661`
- mean active-known accuracy: `0.9735`
- minimum active-known accuracy: `0.9659`
- mean/min `GOOD` recall: `0.9667`
- mean/min `SORRY` recall: `0.9667`
- mean/min accuracy gain over primary: `0.2373`
- maximum false `GOOD -> SORRY` specialist correction rate: `0.0333`
- gate result: passed.

Per-seed mixed accuracy:

- seed `101`: `0.9746`
- seed `202`: `0.9746`
- seed `303`: `0.9661`

## Interpretation

This is the first positive system-level evidence for the dynamic mixed architecture. The result shows that the current `[96,258]` landmark representation did not fail because `GOOD` and `SORRY` are impossible to separate. It failed in E4-S because `SORRY` was outside the primary vocabulary and the primary model had no reject/specialist path.

The passing E4-V landmark specialist fixed most `SORRY -> GOOD` false commits while preserving true `GOOD` well enough for this small offline gate. Current upper-body RGB remains no-go for this group because E4-V showed it was unstable and collapsed to all `GOOD` in one seed.

## Architecture Decision

Use a lightweight landmark specialist as the first resolver type for the `GOOD/SORRY` group in offline simulations. RGB should remain available for later specialist research, but it is not justified for this group yet.

The approved research direction remains:

`CameraX + MediaPipe landmarks -> stable primary [96,258] recognizer -> confusion registry/router -> landmark specialist OR reject -> sentence/UI`

This result does not authorize Android deployment. It authorizes a broader offline routed-system validation with more signs, no-sign/OOV data, and stricter source/signer checks.

## Assumptions

- E4-S and E4-V latest fixed-epoch checkpoints are the intended policy for this simulation.
- Matching seed-to-seed primary/specialist pairing is sufficient for this first proof.
- The E4-S withheld `SORRY` rows and E4-V specialist rows come from related local evidence, so the result may overstate generalization.

## Open Questions

- Does the same routed approach hold on ASL Citizen or a source-disjoint GOOD/SORRY validation set?
- Can the router safely decide when to invoke this specialist outside a perfect offline rule of "primary top1 is GOOD"?
- What happens when additional GOOD-like signs are added?
- How should specialist confidence be calibrated before Android?
- What is the false-commit rate with N0/no-sign windows included?

## Risks

- Same-source leakage risk: this proof is small and local; it must not be treated as production generalization.
- Route overuse risk: routing every primary `GOOD` prediction adds work and can turn a few true `GOOD` rows into `SORRY`.
- Registry complexity risk: specialist rules must stay centralized and versioned, not scattered through runtime code.
- Product-risk: a high-accuracy 5-class offline simulation is still far from silent real-time translation.

## Next Required Action

Prepare the next offline routed-system validation, not Android integration. It should combine:

- E4-S primary signs: `GOOD`, `HELLO`, `HAVE`, `KNOW`
- the passing E4-V GOOD/SORRY landmark specialist
- no-sign/N0 windows from E2e-C0
- any available source-disjoint GOOD/SORRY evidence
- explicit router accept/reject rules and calibrated confidence reporting

The next gate must test accepted precision, coverage, false commits on no-sign/OOV, and per-class recall before any production export is discussed.
