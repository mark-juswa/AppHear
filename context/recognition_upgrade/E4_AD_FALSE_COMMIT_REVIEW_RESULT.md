# E4-AD False-Commit Review And Hard-Negative Mining Result

Last updated: 2026-08-02

## Purpose

E4-AD analyzes the residual errors from the best E4-AC signing/no-sign gate. It creates review panels and separates diagnostic test false commits from train/validation hard-negative candidates so the next gate iteration does not leak test rows into training.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_ad_false_commit_review.py`
- Run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ad_false_commit_review_01`
- False-commit manifest: `review\false_commit_manifest.csv`
- Hard-negative manifest: `review\hard_negative_candidates.csv`
- Review queue: `review\review_queue.csv`
- Panels: `panels\*.jpg`
- Contact sheets: `contact_sheets\false_commits.jpg`, `contact_sheets\hard_negative_candidates.jpg`

## Result Summary

- Structural check passed with required panels.
- False-commit rows: `28`
- Hard-negative candidate rows: `23`
- Review queue rows: `51`
- Panel count: `51`

False commit counts:

- `test:N0 -> HELLO`: `2`
- `test:P1 -> HELLO`: `7`
- `train:P1 -> HELLO`: `3`
- `train:P1 -> KNOW`: `1`
- `val:P1 -> HELLO`: `15`

Hard-negative candidate counts:

- `train:N0`: `6`
- `train:P1`: `13`
- `val:N0`: `2`
- `val:P1`: `2`

## Interpretation

The residual failure is concentrated: no-sign windows are mostly being falsely committed as `HELLO`, especially P1 ordinary-hand windows with high hand-hit rates. This is no longer a broad sign/no-sign problem; it is a `HELLO`-like no-sign hard-negative problem.

Test false commits are diagnostic only. Train/validation hard-negative candidates may be used for the next training iteration, but test rows must remain held out.

## Decision

E4-AD is an evidence package, not a production gate. It supports a targeted hard-negative experiment, but does not authorize Android export or production integration.
