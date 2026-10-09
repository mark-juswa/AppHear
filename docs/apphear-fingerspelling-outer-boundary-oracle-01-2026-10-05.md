# APPHEAR_FINGERSPELLING_OUTER_BOUNDARY_ORACLE_01

Date: 2026-10-05. Offline paired inference only.

**Decision: OUTER_BOUNDARY_NOT_SUPPORTED.** Publisher-window trimming reduces insertions but loses correctly aligned characters and increases deletions. Both frozen B2 and residual references worsen overall. Do not build a fingerspelling segmenter from this result.

## State and scope

Research branch: codex/current-working-text-to-asl-baseline-2026-09-29. HEAD: cc1f3949114d0ed1dab38d4428191151b37df358. Correct application baseline: cee71d9f181695847936eb5f3605ea37eab82a95, baseline/apphear-text-to-asl-context-assist-ui-2026-10-04. Historical protected WORD baseline: 76d93cecd85bf9f76064d320aa4a5791b5f0704a. Existing dirty/untracked work is retained in repository_before.json; no reset, switch, merge, staging or commit.

Original governed DEV-A256 only,15 official signers, all DAUN. No TRAIN inference, DEV-B evaluation, TEST metadata/payload access, RGB acquisition, Candidate01 extraction, training or device action. This is development-exposed whole-sequence held-out-signer evidence, not fresh confirmation or product accuracy.

Frozen manifest: 6b4f152c6bd51eae7af697a58c88c6e20cb0b5e537e272a1a84a897aec54ae6e. B2 epoch076: 64f425358ef30e21a4aca18795226854f7aa44a34c3bc3e54a8c06366cb61397. Residual epoch035: f87be3236196c8ab8321a3b6f7bb9d6398d048e257630a38546e8a8d00143251. Adapter.v1 order/config/implementation, frozen MobileNetV3Small, visual quality/deduplication, blank27 penalty0.5 and beam10 are unchanged. No decoder/model search.

## Timing mapping and validity

The cached official clipping helper defines annotation/clip times relative to the original first packet treated as time zero. fullVideoFirstPtsTimeS is added only to compare with absolute original PTS; it cancels for clip-relative annotation times. Released clip timestamps start at zero.

    local_start_ms = 1000 * (annotationStartTimeS - clipStartTimeS)
    local_end_ms   = 1000 * (annotationEndTimeS - clipStartTimeS)
    retain iff local_start_ms <= raw.timestamp_ms <= local_end_ms

Closed endpoints; no extra PTS offset, padding, clamping, snapping or transcript-dependent boundary. Float64 metadata/timestamps are used as stored. Publisher windows are approximate whole-phrase annotations, not character boundaries. A contradictory isolated prose comment about annotation/end ordering in the cached helper is not adopted: actual metadata and cutting code establish containment.

All256 manifest and feature-receipt metadata rows exactly match pinned official v13 DAUN-validation metadata SHA d306aac4c80e7052492ebffdd01f2e8242d09755ff7243824e866360fb609648. metadata_verification.json records the cached timing source and its hash. No new provenance search.

**256 usable;0 invalid;0 outside the decoded observation extent;0 ambiguous timelines.** Receipts declare whole-source extraction, consecutive frame indices from0 and CONTAINER_POS_MSEC. Raw timestamps start at0 and are strictly chronological. Decoded span differs from metadata clip extent by at most10.45ms, median approximately minus0.0011ms. Every annotation window lies inside actual observations. Invalid records would be inventoried and stop inference; none was discarded.

Example ALENA BURKE (fsboard-v13-validation-0092c5e7f247930e71d9): annotation720.4–724.7s, clip720.230378–725.224157s, local annotation169.622–4469.622ms. Original first PTS0.082s is not added again. Exact selected source indices/timestamps are saved for all sequences.

## Transformation and parity

Each full/oracle input is independently inferred from its sequence start; causal state resets. Native trim retains real raw observations and reruns Adapter.v1: first dt/motion becomes zero and subsequent motion uses retained frames. No logit slicing as a substitute for model inference; no forward fill, interpolation, fake frames, letter boundaries or transition labels. Original data archives are never rewritten.

Visual embeddings remain keyed to original raw frame identity. Quality and duplicate suppression are current-frame-only; recomputed quality after trimming exactly matches original retained scores for all256. Geometry and appearance index the same source observations. No RGB/appearance rematerialization is needed. Geometry remains405; residual packed input remains1559.

Full regenerated inputs exactly match existing ResidualCache for all256 in both views. All512 full residual logit arrays are reused unchanged from the frozen decoder audit. Fresh model inference on two sequences per view matches those logits exactly, maximum absolute error0.

Initial phone condition: trim then the existing6.231166Hz causal real-frame gate, starting at the first oracle frame. This resets sampling phase as a bounded session would. One clearly labeled post-audit phase-locked control intersects the original full-phone grid with the oracle window, then recomputes Adapter.v1, isolating outer removal from changed interior frame choices. Initial results are retained; no cadence/window/decoder sweep.

## Full versus oracle metrics

Every row:256 sequences,3,457 reference characters. S/D/I use the established deterministic Levenshtein alignment; Correct means matched reference characters. Exact/Empty are sequence counts. Phone is an offline cadence approximation.

| Model / view / input | CER | S | D | I | Correct | Predicted | Pred/ref | Exact | Empty | Macro signer CER |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| b2 / native / full | 50.19% | 687 | 854 | 194 | 1916 | 2797 | 0.809 | 0 | 0 | 50.20% |
| b2 / native / oracle | 50.91% | 669 | 903 | 188 | 1885 | 2742 | 0.793 | 0 | 0 | 50.92% |
| b2 / phone / full | 52.70% | 937 | 745 | 140 | 1775 | 2852 | 0.825 | 0 | 0 | 52.67% |
| b2 / phone / oracle | 53.89% | 876 | 872 | 115 | 1709 | 2700 | 0.781 | 0 | 0 | 53.84% |
| residual / native / full | 49.52% | 679 | 824 | 209 | 1954 | 2842 | 0.822 | 0 | 0 | 49.54% |
| residual / native / oracle | 50.13% | 674 | 863 | 196 | 1920 | 2790 | 0.807 | 0 | 0 | 50.15% |
| residual / phone / full | 52.16% | 920 | 739 | 144 | 1798 | 2862 | 0.828 | 0 | 0 | 52.12% |
| residual / phone / oracle | 53.60% | 843 | 888 | 122 | 1726 | 2691 | 0.778 | 0 | 0 | 53.54% |
| b2 / phone / phase-locked oracle | 54.09% | 880 | 884 | 106 | 1693 | 2679 | 0.775 | 0 | 0 | 54.03% |
| residual / phone / phase-locked oracle | 53.43% | 836 | 893 | 118 | 1728 | 2682 | 0.776 | 0 | 0 | 53.37% |

Residual balanced CER: **50.84%→51.87%** with session-reset sampling; **51.78%** combining oracle native with phase-locked phone. Not a new model baseline or selection decision.

## Sequence, signer and CTC effects

| Model/view | Improve | Regress | Unchanged | Signers improve/regress/tie | CTC infeasible full→oracle |
|---|---:|---:|---:|---|---|
| b2/native | 46 | 57 | 153 | 4/8/3 | 0→0 |
| b2/phone | 93 | 100 | 63 | 7/7/1 | 2→21 |
| residual/native | 54 | 67 | 135 | 6/8/1 | 0→0 |
| residual/phone | 85 | 99 | 72 | 5/10/0 | 2→21 |
| b2/phone-locked | 65 | 87 | 104 | 5/9/1 | 2→27 |
| residual/phone-locked | 62 | 86 | 108 | 5/8/2 | 2→27 |

All infeasible sequences remain in decoding/CER; only undefined CTC loss is omitted. No denser fallback or fabricated observation. Oracle trimming raises sparse structural impossibility from2/256 to21/256 reset-phone or27/256 locked-phone sequences. Native stays256/256 feasible.

Residual per-signer CER;17 sequences each except001e18. Complete B2 signer tables remain in the JSON report.

| Signer | Native full | Native oracle | Phone full | Phone oracle | Phone locked oracle |
|---|---:|---:|---:|---:|---:|
| 001e | 51.07% | 51.50% | 52.36% | 51.07% | 50.64% |
| 1c15 | 45.58% | 46.46% | 52.65% | 51.33% | 51.77% |
| 28d4 | 51.16% | 50.70% | 45.58% | 44.19% | 44.65% |
| 2b19 | 62.45% | 62.01% | 60.26% | 62.45% | 61.57% |
| 4e6b | 51.56% | 50.67% | 53.78% | 54.67% | 50.67% |
| 5ce0 | 48.39% | 51.61% | 58.87% | 60.89% | 64.11% |
| 661f | 36.02% | 37.29% | 36.02% | 39.83% | 37.29% |
| a459 | 42.73% | 41.85% | 42.73% | 51.54% | 48.46% |
| aeed | 44.77% | 41.42% | 52.72% | 51.46% | 52.72% |
| c28d | 71.43% | 75.12% | 70.51% | 66.82% | 69.12% |
| c6e5 | 65.08% | 65.08% | 61.90% | 63.89% | 62.30% |
| d516 | 46.05% | 43.42% | 53.07% | 54.82% | 57.02% |
| d5fd | 47.58% | 50.22% | 45.37% | 50.66% | 48.90% |
| ebdb | 41.52% | 45.09% | 50.89% | 53.57% | 56.25% |
| f896 | 37.66% | 39.83% | 45.02% | 45.89% | 45.02% |

No broad signer gain: residual native6 improve/8 regress/1 tie; reset-phone5/10/0; locked-phone5/8/2. Signer-cluster bootstrap (2,000 draws,seed20261005; positive delta is worse): residual native+0.61pp,95% interval−0.44…+1.62pp; reset-phone+1.45pp,+0.03…+3.00pp; locked-phone+1.27pp,−0.15…+2.65pp. These15-signer development-exposed intervals are descriptive, not proof that boundaries never matter.

## J, Z and repeated letters

| Model/view | J59 full→oracle CER | Z52 full→oracle CER | Repeated109 full→oracle CER |
|---|---|---|---|
| b2/native | 51.60%→50.67% | 52.14%→51.86% | 49.34%→50.66% |
| b2/phone | 53.33%→53.87% | 54.21%→54.34% | 51.99%→53.25% |
| residual/native | 51.60%→50.27% | 49.93%→50.21% | 49.67%→50.13% |
| residual/phone | 53.07%→53.87% | 52.97%→54.48% | 51.19%→52.59% |
| b2/phone-locked | 53.33%→53.47% | 54.21%→56.55% | 51.99%→52.65% |
| residual/phone-locked | 53.07%→53.47% | 52.97%→54.34% | 51.19%→52.45% |

Residual native J improves slightly; native Z/repeats and all residual phone-like subgroups do not. No character-specific rule.

## Emission and boundary analysis

- Native residual: insertions209→196, deletions824→863, correct1954→1920, predicted2842→2790, output/reference0.822→0.807.
- Reset-phone residual: insertions144→122, deletions739→888, correct1798→1726, predicted2862→2691, output/reference0.828→0.778.
- Locked-phone residual: insertions144→118, deletions739→893, correct1798→1728, predicted2862→2682, output/reference0.828→0.776.
- Output longer than reference: native52→51, reset-phone39→35, locked-phone39→32. Excessive emission declines somewhat, but lost true characters dominate. Full DEV is already under-emitting overall, unlike the motivating AMY example. Exact/empty counts remain zero everywhere.

Native observations38,777→30,350:8,427 removed(21.73%),4,165 leading and4,262 trailing. Mean per-sequence removal11.76% leading/11.70% trailing; unweighted percentages differ from pooled removal. Median full span5.002s→oracle3.730s; p95 spans7.999s→6.860s. Publisher median duration3.761s differs from selected-frame span.

6,579/8,427 removed observations(78.07%) lack both accepted hand slots. Mean per-sequence missing-hand fraction outside77.75%,inside24.88%. Mask absence does not prove inactivity or explain a perception failure. Removing mostly missing-hand evidence still gives no broad recognition gain.

Pearson association with per-sequence CER gain, ordered leading%,trailing%,full duration,outside missing-hand fraction: residual native0.077/−0.031/0.123/0.007; reset-phone−0.013/−0.096/0.021/0.093; locked-phone−0.160/0.010/0.120/0.100. Weak/mixed correlations are not causal evidence. B2 is likewise inconsistent; all distributions/correlations are retained.

## Representative help/harm

Largest edit improvements/regressions, then sample-ID tie order; illustrative only, not hand-annotated character timing.

| View | Reference | Full beam | Oracle beam | Errors full→oracle |
|---|---|---|---|
| native/improve | LUXEVAKANTIEHUISZEELAND | LRRXGERRANIE HHRRIISZEEELANY | LRXGERRNIEHHURIISZEELANY | 14→11 |
| native/improve | JAKE HUFF | JJOKKEEHF | JKEEHUFE | 6→3 |
| native/regress | WAYLON ZUNIGA | WALZENI | ZENNI | 7→10 |
| native/regress | ROLAND HERNANDEZ | ROYADOERN NDE | DOERN NDE | 6→9 |
| phone/improve | LAS CRUCES NEW MEXICO | ASCDCESNENZ  | SASCRESNENZICO | 13→10 |
| phone/improve | BAMBI BARNETT | BABYARS T | BAMBIARNE  | 7→4 |
| phone/regress | BRIDGEPORT CONNECTICUT | BFID EPORTCONECTICERTS | BI PRAEONCTIOERTS | 7→14 |
| phone/regress | ELIZABETH NEW JERSEY | MLSAAPTEWIJOSE | MSA MLHTMWOO | 12→17 |

Some oracle predictions lose recognizable prefixes. Lost causal context, approximate annotations and full-clip training distribution are possible explanations; none is proven. No boundary padding or retraining is tried to force a positive result.

## Files, tests and preservation

Created code/config:

- model/config/fingerspelling_outer_boundary_oracle_01.json
- tools/fingerspelling/outer_boundary_oracle.py
- tools/fingerspelling/outer_boundary_phase_control.py
- tests/test_fingerspelling_outer_boundary_oracle.py

Created this report and artifacts/fingerspelling_outer_boundary_oracle_01/. Documentation-only appends: context/feature-schema.md,context/progress-tracker.md,memory.md. No existing pipeline/model/decoder source, dataset, weights or Android file was edited. Minor static-check corrections were confined to new helpers. The exact executed phase-control source is archived; its sole subsequent difference is a static dictionary type annotation, documented in implementation_note.json; numeric/runtime logic unchanged.

**37 focused tests pass**:11 oracle invariants plus existing beam/B2 regression checks. Ruff and mypy pass. Native/full input parity, source MD5/SHA, raw/feature/visual receipts, masks/chronology, deterministic real indices and no NaN/Inf checks pass. No optimizer/update is constructed. Helpers import fingerspelling inference/contracts and common raw schema, not WORD lifecycle/recognition code.

**11,506 inventoried existing files are hash-identical;0 changed,0 missing.** Covers original foundation source/raw/features, full residual visual package, frozen runs/audits, Candidate01 math/assets, both Android source/assets trees and protected WORD/Context Assist files. Existing dirty files are compared with starting bytes; the older F: app is not falsely claimed identical to the October4 worktree. No device build/deployment/release action.

Review: plan alignment PASS; preservation/boundaries PASS; offline diagnostic correctness PASS. No critical/important implementation issue remains. Oracle assistance is not a deployable accuracy gain. Host inference+decoding/cache retrieval sums to about117s for eight main conditions, excluding preflight,source hashing and model loading; control timings are recorded separately. No Android latency claim.

## Evidence and final recommendation

Exact evidence root: F:/ASL DATASET/5. Apphear3/artifacts/fingerspelling_outer_boundary_oracle_01/.

- repository_before.json;preservation_before.json;preservation_extra_before.json;preservation.json: state and protection.
- metadata_verification.json;timing_alignment.json: official timing/frame identities,removals and lineage.
- identity.json;paired_evaluation.json;eight logit NPZs/receipts: full/native/phone paired B2 and residual; historical greedy/beam audit unchanged.
- phase_locked_control/: original-grid alignment,two oracle logits/receipts,paired evaluation,identity and executed source.
- analysis_summary.json;sequence_error_composition.json: subgroup/signer/CTC/overlength/bootstrap/correlation results and per-sequence S/D/I.
- tests.xml;inspect.log;run.log;phase_control.log;decision.json;evidence_index.json: validation/execution/decision.

Keep the frozen recognizer and Android behavior. **Stop the learned outer-boundary direction on this evidence.** Individual examples can benefit, but the fixed publisher windows do not explain most DEV errors and worsen correct-character retention overall. This does not establish the correct boundary for the13.68s AMY session or rule out its specific setup/release problem: no oracle phone annotation or new phone attempt was made.

No next architecture,training,UI change or segmenter is automatically authorized.

OUTER_BOUNDARY_NOT_SUPPORTED
