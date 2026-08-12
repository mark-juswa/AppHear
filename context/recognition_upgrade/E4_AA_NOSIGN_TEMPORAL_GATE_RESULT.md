# E4-AA No-Sign Temporal Gate Result

Last updated: 2026-08-02

## Purpose

Record the full E4-AA result after the package run. E4-AA tested whether a temporal binary signing/no-sign gate over real MediaPipe schema v3.0 `[96,258]` windows can prevent no-sign false commits before the E4-S/E4-V routed recognizer.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_aa_nosign_temporal_gate.py`
- Run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_aa_nosign_temporal_gate_01`
- Metrics: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_aa_nosign_temporal_gate_01\metrics\temporal_gate_metrics.json`
- Check report: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_aa_nosign_temporal_gate_01\check_report.json`

## Dataset

- No-sign rows: `288`
- Shape: `[288,96,258]`
- Split counts: train `166`, validation `54`, test `68`
- Source counts: N0 `180`, P1 `108`
- Mean hand-hit rate: N0 `0.0277`, P1 `0.7068`
- Mean pose-hit rate: N0 `0.9984`, P1 `0.9997`
- Schema version: `3.0`

## Result Summary

- Structural check passed.
- Experiment gate failed.
- Mean accepted precision: `0.9690`
- Minimum accepted precision: `0.9630`
- Mean positive coverage: `0.7345`
- Minimum positive coverage: `0.6780`
- Maximum no-sign false commit rate: `0.0147`
- Mean/min GOOD recall: `0.9667` / `0.9667`
- Mean/min SORRY recall: `0.1222` / `0.0000`

## Interpretation

E4-AA largely solved the real no-sign false-commit problem, reducing false commits to `0.0147`. However, the binary temporal gate over-rejected low-motion real signs, especially `SORRY`. This makes it unsafe for silent translation because it would miss real signs even while avoiding no-sign hallucinations.

## Decision

No Android export, no production integration, no vocabulary expansion. The next step is to test a conservative or uncertainty-aware gate policy that explicitly protects low-motion signs before concluding a new gate architecture or more training data is required.
