# E5-G Clean 7-Class Primary Result

**Last updated:** 2026-08-03

## Purpose
Record the completed E5-G clean 7-class primary landmark retrain after E5-F showed that replaying the E5-D 15-class model with post-hoc rejection was not sufficient.

## Scope
Offline experiment only. No Android export, production recognizer replacement, feature-schema change, extraction change, or dataset mutation was authorized.

## Verified Project References
- Runner: `pipeline/rgb/e5_g_clean_7_primary.py`
- Run directory: `artifacts/recognition_upgrade/e5_batch_screening/e5_g_clean_7_primary_01`
- Input schema: v3.0 `[96,258]`
- Source decision: `context/recognition_upgrade/E5_E_REDUCED_PRIMARY_DECISION_RESULT.md`
- Prior failure: `context/recognition_upgrade/E5_F_REDUCED_PRIMARY_ROUTED_SIM_RESULT.md`

## Dataset
- Classes: `WASH2`, `THINK`, `TAKE`, `MEET`, `GOOD`, `SELL`, `STAND2`
- Rows: `344`
- Split counts: train `252`, val `20`, test `72`
- Source counts: ASL Citizen `190`, local `154`

## Result Summary
E5-G passed structural checks and completed three-seed Conv1D training.

Latest checkpoint aggregate:
- mean validation accuracy: `0.8000`
- mean test accuracy: `0.8472`
- min/max test accuracy: `0.8194` / `0.8750`

Best-by-validation checkpoint aggregate:
- mean validation accuracy: `0.8667`
- mean test accuracy: `0.8194`
- min test accuracy: `0.7917`

Latest per-class test recall across seeds:
- `WASH2`: mean `1.0000`, min `1.0000`
- `THINK`: mean `1.0000`, min `1.0000`
- `TAKE`: mean `0.9333`, min `0.9000`
- `SELL`: mean `0.9091`, min `0.8182`
- `GOOD`: mean `0.7778`, min `0.6667`
- `MEET`: mean `0.6667`, min `0.4444`
- `STAND2`: mean `0.6061`, min `0.4545`

Top latest confusions:
- `STAND2 -> MEET`: `6`
- `MEET -> WASH2`: `5`
- `STAND2 -> GOOD`: `5`
- `MEET -> TAKE`: `3`
- `GOOD -> THINK`: `3`
- `GOOD -> TAKE`: `3`

## Decision
E5-G is a useful closed-set improvement over E5-D/E5-F, but it is not production-ready by itself. It authorizes routed/no-sign/OOV simulation only.

## Architecture Decisions
- Keep `WASH2`, `THINK`, and `TAKE` as strong primary candidates.
- Treat `MEET` and `STAND2` as unstable until routed-system evidence improves.
- Do not export the E5-G model to Android without routed safety validation.

## Assumptions
- Closed-set signer-disjoint performance is necessary but not sufficient for silent translation.
- The E5-G model must be evaluated with no-sign and unsupported-sign pressure before runtime use.

## Open Questions
- Can explicit OOV/no-sign training improve rejection without destroying positive recall?
- Are `MEET` and `STAND2` fixable with better data or should they be deferred?

## Risks
- Closed-set accuracy can overstate real app safety.
- Softmax confidence may be poorly calibrated for unsupported signs.
- Small validation counts can distort threshold selection.

## Next Required Action
Run E5-H routed simulation with E5-G plus the E4-AG no-sign gate and unsupported-sign pressure rows.
