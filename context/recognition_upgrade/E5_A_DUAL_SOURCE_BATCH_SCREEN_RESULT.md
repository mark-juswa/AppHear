# E5-A Dual-Source Batch Screen Result

**Purpose:** Record the first E5-scale inventory screen after E4-AG recovered the no-sign safety floor.

**Scope:** Offline inventory/tiering only. No training, MediaPipe extraction, Android integration, TFLite export, production recognizer replacement, or source dataset mutation.

**Current status:** COMPLETE / STRUCTURAL PASS / STRICT DUAL-SOURCE SCREEN RECORDED / ASL-LED STRATEGY SUPERSEDES THE STRICT E5-B RECOMMENDATION.

**Last updated:** 2026-08-02.

## Verified Project References

- Runner: `pipeline/rgb/e5_a_dual_source_batch_screen.py`
- Run directory: `artifacts/recognition_upgrade/e5_batch_screening/e5_a_dual_source_batch_screen_01`
- Summary JSON: `artifacts/recognition_upgrade/e5_batch_screening/e5_a_dual_source_batch_screen_01/reports/screen_summary.json`
- Ranked inventory: `artifacts/recognition_upgrade/e5_batch_screening/e5_a_dual_source_batch_screen_01/tables/candidate_inventory_236.csv`
- Recommended next primary candidates: `artifacts/recognition_upgrade/e5_batch_screening/e5_a_dual_source_batch_screen_01/tables/recommended_e5b_primary_candidates.csv`
- Diagnostic candidates: `artifacts/recognition_upgrade/e5_batch_screening/e5_a_dual_source_batch_screen_01/tables/diagnostic_batch_candidates.csv`
- Check report: `artifacts/recognition_upgrade/e5_batch_screening/e5_a_dual_source_batch_screen_01/check_report.json`

## Input Feature Sources

- ASL Citizen features: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational`
- Combined ASL + local feature tensor: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236`
- Local supplementary tensor: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_recorded_local_pc_236\recorded.npz`
- E4-P pressure result: `artifacts/recognition_upgrade/e4_generalization/e4_p_existing_feature_20sign_pressure_01`
- E4-AG no-sign safety result: `artifacts/recognition_upgrade/e4_generalization/e4_ag_low_motion_gate_01`

## Result Summary

E5-A inspected all `236` labels.

Tier counts:

- `A0_primary_proven`: `4`
- `A1_routed_specialist_proven`: `1`
- `A2_candidate_for_e5b_primary_pilot`: `1`
- `B0_batch_candidate_but_unproven`: `1`
- `B1_candidate_needs_more_local_signers`: `50`
- `B2_confusion_group`: `2`
- `C1_data_limited`: `2`
- `C2_blocked_prior_failure`: `6`
- `D0_asl_only_inventory`: `169`

Local-supported labels: `67`.

## Recommended E5-B Primary Candidate

Only one new sign passed the strict dual-source candidate criteria:

| Gloss | Local rows | Local signers | E4-P mean latest | E4-P min latest | Decision |
|---|---:|---:|---:|---:|---|
| `WANT2` | `69` | `2` | `0.7879` | `0.6364` | candidate for next primary pilot |

This does not mean `WANT2` is production-ready. It means it is the only new sign with enough current evidence to justify the next strict training pilot.

## High-Value Diagnostic Queue

Many signs have useful local row counts but only one local signer, so they should not be promoted as production-grade. They can be used for a diagnostic batch or targeted data collection queue.

Top examples:

- `WHAT1`
- `MEET`
- `NICE`
- `GIVE`
- `STAND2`
- `CLOSE`
- `KEEP`
- `START`
- `WASH2`
- `LEAVE`
- `TALK1`
- `CLEAN`
- `COOK`
- `BUY`
- `OPEN`

These are valuable, but they are not yet strong dual-source production candidates because signer diversity is too narrow.

## Interpretation

This is the point of E5-A: it prevents us from pretending that a 50- or 100-word production model is supported by the current data.

The screen found:

- the safety floor is now good enough to proceed beyond no-sign debugging;
- the existing dual-source feature inventory is still too sparse for a large production-grade batch;
- most candidate signs need more local signer diversity or should be treated as diagnostic-only;
- broad training now would likely reproduce E4-P-style collapse.

## Decision

Historical strict interpretation:

```text
Primary controls: GOOD, HELLO, HAVE, KNOW
Routed specialist/control: SORRY
New primary candidate: WANT2
No-sign safety gate: E4-AG gate
```

This remains useful as a conservative production-readiness screen, but it is not the current scaling strategy.

Corrected current strategy after user clarification:

- Use ASL Citizen as the broad main training source.
- Use local supplementary rows where available to strengthen, repair, or validate signs.
- Do not require local support for every ASL Citizen sign before a diagnostic batch.
- Keep known hard/confusion signs out of the primary model until they have specialist or repair evidence.

The immediate next package is E5-B ASL-led 50-class primary diagnostic, documented in `E5_B_ASL_LED_PRIMARY_BATCH_PACKAGE.md`.

## What Not To Do

- Do not train all 236 labels.
- Do not train the 67 local-supported labels as if they are production-ready.
- Do not add `HELP`, `BECOME`, `GET`, `MAKE`, `BYE`, `NO`, `YES`, `THANKYOU`, or `WELCOME2` to the primary model without separate repair/specialist evidence.
- Do not start Android export from E5-A.

## Next Required Action

Run E5-B ASL-led 50-class primary diagnostic:

- primary model starts from `GOOD`, `HELLO`, `HAVE`, and `KNOW` plus high-ranked ASL/local-supported candidates;
- local data supplements where available;
- `SORRY` and known blocked/confusion signs remain excluded from the primary model;
- evaluate per-class test behavior, stable-control retention, collapse risk, and the keep/repair/specialist/defer tiers produced by the batch.


