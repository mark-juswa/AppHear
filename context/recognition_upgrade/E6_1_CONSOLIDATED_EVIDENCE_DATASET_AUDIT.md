# E6-1 Consolidated Evidence And Dataset Audit

**Purpose:** Consolidate E1-E5 evidence so AppHear does not repeat failed recognition experiments under new names.

**Scope:** Audit and planning only. No training, feature extraction, model export, Android integration, production recognizer replacement, schema mutation, source dataset mutation, or label rewriting was performed.

**Current status:** COMPLETE / DATA INSUFFICIENT FOR NEXT MODELING STEP.

**Last updated:** 2026-08-03.

## Output Tables

The complete machine-readable audit tables are in `context/recognition_upgrade/e6_audit_tables/`:

| Table | Purpose |
|---|---|
| `e1_to_e5_experiment_inventory.csv` | Complete table of 103 E1-E5 context/package/result docs with purpose, scope, inputs, status, and result/decision excerpts. |
| `per_sign_feature_counts.csv` | Per-sign counts by feature source, split, signer count, schema, label-variant availability, and raw-video availability status. |
| `per_sign_aggregate_counts.csv` | Aggregate per-sign counts across ASL Citizen features, combined ASL+local features, and local recorded features. |
| `nosign_oov_coverage_notes.csv` | Source notes for N0/P1/no-sign/OOV coverage from prior context docs. |

These CSVs are the required complete tables. This Markdown file is the decision summary and no-repeat policy.

## Verified Dataset Inventory

Current feature tensors audited:

| Feature Inventory | Verified Rows | Schema | Notes |
|---|---:|---|---|
| ASL Citizen streaming conversational train/val/test | `3309/913/2764` | `3.0` | 236 labels represented; about 20-32 rows/sign in this derived subset. |
| Combined ASL + local streaming train/val/test | `4242/913/2764` | `3.0` | Same 236-label vocabulary plus local rows in train-like inventory. |
| Local recorded tensor | `933` | `3.0` | 67 labels have any local recorded feature rows. |

Aggregate count facts from `per_sign_aggregate_counts.csv`:

- Total vocabulary labels: `236`.
- Labels with any ASL Citizen feature rows: `236`.
- Labels with any local recorded rows: `67`.
- Labels with at least `50` local recorded rows: `3`.
- Labels with at least `100` local recorded rows: `0`.
- Labels with at least `50` ASL feature rows in the current derived subset: `0`.
- Label variants are not versioned in the feature tensors.
- Raw video availability is not verified per feature row in the audited tensors.

Representative sign counts:

| Gloss | ASL Feature Rows | Local Recorded Rows | Combined Rows | Prior Interpretation |
|---|---:|---:|---:|---|
| `WASH2` | 30 | 13 | 43 | Strong E5-G class, but data still small. |
| `THINK` | 29 | 2 | 31 | Strong E5-G class, little local support. |
| `TAKE` | 27 | 5 | 32 | Strong E5-G class, little local support. |
| `SELL` | 26 | 10 | 36 | Strong E5-G class, still small. |
| `GOOD` | 25 | 70 | 95 | Useful but confusion-sensitive with MAKE/GET and routed SORRY evidence. |
| `MEET` | 24 | 36 | 60 | E5-G recall weak/unstable. |
| `STAND2` | 29 | 18 | 47 | E5-G recall weak/unstable. |
| `HELLO` | 24 | 13 | 37 | Regressed in E5-B as `SEEM`; no-sign false commits historically HELLO-like. |
| `KNOW` | 27 | 11 | 38 | Regressed in E5-B as `SEEM`. |
| `SORRY` | 28 | 14 | 42 | Routed/specialist evidence mixed; not primary-stable. |
| `USE` | 30 | 9 | 39 | Weak/confused in E5-D. |
| `WORK` | 29 | 7 | 36 | Weak/confused in E5-D. |
| `DRIVE` | 27 | 1 | 28 | Weak/confused in E5-D. |
| `WANT2` | 29 | 69 | 98 | Local support but E5-D weak/confused. |

## E1-E5 Evidence Summary

### E1

- Corrected GCN capacity was proven on a small sanity slice, but full matched GCN-vs-TCN training was not completed because CPU-only runtime was too expensive.
- Do not use the old failed slim GCN as proof graphs cannot work.
- Do not start heavy graph training before data sufficiency and GPU plan are resolved.

### E2/C0

- MediaPipe/crop reliability work showed direct upper-body/RGB assumptions are unsafe.
- E2/E2b/E2c/E2d failed ROI/crop gates; E2e corrected all-hand audit and C0 capture created useful gold/no-sign evidence.
- HaGRID smoke passed structurally but was not promoted.
- Do not repeat MediaPipe mode/threshold tuning as the main solution.

### E3

- E3-B5/B6/B7 showed landmark temporal/derived feature tweaks produce modest or unstable gains.
- Full derived `[96,728]` improved some test results but did not pass promotion gates and later failed E4-Q for SORRY.
- E3-C upper-body RGB and naive fusion failed badly; fusion was worse than landmark-only.
- Do not rerun upper-body frozen-MobileNet RGB/fusion.

### E4

- E4 local/supplementary work showed small closed-set wins but poor broader generalization.
- E4-L MAKE and E4-O GET/WELCOME2 failed expansion and collapsed into GOOD-like predictions.
- E4-Q landmark/derived confusion resolver for `GOOD/SORRY/HELP/BECOME` failed.
- E4-V/E4-W showed a narrow GOOD/SORRY landmark specialist can work, but this was small and not production proof.
- E4-Y through E4-AG proved real MediaPipe no-sign windows must be included; zero-landmark no-sign tests were misleading.

### E5

- E5-A/E5-C/E5-E already performed repeated tiering and confusion mining.
- E5-B 50-class ASL-led diagnostic learned signal but was not exportable: mean latest test `0.4897`.
- E5-D 15-sign reduced primary improved to mean latest test `0.6933`, but weak signs remained.
- E5-G 7-sign closed-set improved to mean latest test `0.8472`, but `MEET` and `STAND2` were weak.
- E5-H confidence-only routed rejection failed.
- E5-I shared accept/reject head improved coverage but failed accepted-precision/coverage/per-class recall gates.

## Strict DO NOT REPEAT List

Do not repeat these unless the meaningful difference is explicitly documented and approved:

1. **Upper-body frozen-MobileNet RGB/fusion** from E3-C. It overfit and damaged landmark signal.
2. **Naive concat fusion** where a weak RGB stream can overpower landmarks.
3. **Small handcrafted landmark feature engineering** that resembles E3-B6/E3-B7 without new data or open-set metrics.
4. **Derived `[96,728]` promotion** after E4-Q; it failed the important SORRY group and must not be ported to Android.
5. **MediaPipe IMAGE/VIDEO/LIVE_STREAM or threshold tuning as the main ROI fix** after E2c/E2d no-go.
6. **One-word expansion loops** such as MAKE or GET without batch/data sufficiency evidence.
7. **Training all 236 labels** or all local-supported labels as a production candidate.
8. **Treating aggregate closed-set accuracy as production evidence** after E5-B/E5-D/E5-G showed routed/open-set failures.
9. **Softmax confidence-only routing** after E4-T/E5-H no-go.
10. **Shared global accept/reject head as the assumed fix** after E5-I no-go.
11. **Zero-landmark no-sign validation** as a proxy for real runtime no-sign after E4-Y disproved it.
12. **Naive hard-negative upweighting** after E4-AE worsened minimum precision.
13. **Android export/integration before offline routed no-sign/OOV gates**.
14. **User confirmation as a safety mechanism** for silent translation; acceptance must be algorithmic.

## Leakage, Source-Confound, Label, And Test-Reuse Risks

| Risk | Evidence | Consequence |
|---|---|---|
| Source/provenance shortcut | E4-B failed under mixed provenance; E4-D same-provenance improved collapse. | Blind ASL+local merging can make source cues look like sign cues. |
| Insufficient signer diversity | Local recorded tensor has 67 labels with any local support, only 3 labels with >=50 local rows, no label has >=100 local rows. | Production claims would be underpowered. |
| Label/variant ambiguity | E4-E found relabel needs; feature tensors do not version label variants. | Some ?model errors? may be label/variant errors. |
| Reused test artifacts | E3-E5 repeatedly used the same derived tensors and test splits. | Future promotions need fresh or stricter held-out validation. |
| Raw video lineage incomplete per row | Current audited `.npz` files do not expose per-row raw video paths. | RGB/crop or label-review claims require manifest repair. |
| Open-set negatives underpowered | E5-H/E5-I used unsupported rows and 404 no-sign rows, but still failed. | Rejection methods may overfit current negative examples. |

## No-Sign, OOV, And Unsupported Coverage

Verified no-sign/OOV evidence:

- E4-Y: real MediaPipe N0/P1 features caused severe false commits; zero-landmark negatives were not representative.
- E4-AG: HELLO-like no-sign expansion produced `404` no-sign rows in the working gate context and passed the small safety floor.
- E5-H/E5-I: unsupported-sign pressure was used, but rejection still failed product-style gates.

Current gap:

- No-sign/OOV coverage is useful for research but still too small and too targeted for production silent translation.
- Need longer ordinary non-signing sessions and broader unsupported-sign coverage before open-set release claims.

## Stable Confusion Groups Already Proven

| Group | Evidence | Status |
|---|---|---|
| `SORRY/BECOME/HELP` | E4-P/E4-Q | Landmark-only broad resolver failed; requires data/variant repair or new evidence. |
| `GOOD/MAKE/GET` | E4-L/E4-O | MAKE/GET collapsed toward GOOD; keep out of primary. |
| `BYE/NO/YES` | E4-G/E4-H | Local separability failed; defer or collect/repair. |
| `THANKYOU` variants | E4-E/E4-F | Label/variant issues found; requires cleanup. |
| `HELLO/KNOW/SEEM` | E5-C | HELLO and KNOW regressed in 50-class context. |
| `USE/WORK` | E5-D/E5-E | Repeated confusion; defer or repair. |
| `DRIVE/HAVE/WANT2` | E5-D/E5-E | Repeated confusion; defer or repair. |
| `SLEEP/USE/MORNING` | E5-D/E5-E | Repeated confusion; defer or repair. |
| `RUN2/WASH2` | E5-D/E5-E | Repeated confusion; monitor if WASH2 promoted. |

## Learning-Curve And Dataset Sufficiency Assessment

The current derived feature inventory is insufficient for production-grade silent translation.

Reasoning from verified AppHear evidence:

- Strongest E5-G classes have only about `31-43` combined feature rows except `GOOD`.
- E5-G closed-set mean latest test reached `0.8472`, but routed/open-set safety immediately failed in E5-H/E5-I.
- E5-I full 7-sign accepted precision/coverage was only `0.8985/0.2778` mean and `0.8333/0.2083` minimum.
- The model is data-limited and open-set-limited; more threshold variants are unlikely to solve it.

External scale comparison recorded in E6 plan:

- PopSign reports about `700` valid examples/sign across `47` Deaf adult signers for a 250-sign smartphone dataset baseline.
- AppHear's current E5 feature subset is usually tens of examples per sign, not hundreds.

## Product-Core Vocabulary Supported By Evidence

No sign is production-ready for silent translation yet because no sign has passed the full combination of closed-set, open-set, no-sign/OOV, calibration, and Android gates.

Research-only strongest candidates for a future product-core audit:

- `WASH2`
- `THINK`
- `TAKE`
- `SELL`

Guarded candidates requiring more data or routed validation:

- `GOOD`
- `MEET`
- `STAND2`
- `HAVE`
- `MORNING`

Must be repaired/deferred before primary inclusion:

- `HELLO`, `KNOW`, `SORRY`, `USE`, `WORK`, `DRIVE`, `WANT2`, `SLEEP`, `RUN2`, `BYE`, `NO`, `YES`, `THANKYOU`, `GET`, `MAKE`, `BECOME`, `HELP`.

## Required Data Or Repair Before More Modeling

For any intended product-core sign, collect or extract a dataset package with:

- raw video preserved and linked per feature row;
- signer id, source, device, environment, camera-facing, handedness when known;
- train/validation/test split by signer;
- label variant field, with variant consistency reviewed for ambiguous signs;
- no-sign/OOV rows from real MediaPipe extraction, not zero vectors;
- enough held-out examples for per-class recall and accepted-precision gates.

Minimum practical next target before another model experiment:

- Select `10-20` product-priority signs, not 236.
- For each selected sign, use the full available ASL Citizen/raw inventory if legally available, not only the current small derived subset.
- Add local/app-domain data for signs with weak transfer or product importance.
- Prioritize at least `10+` signer-disjoint test signers where possible; if unavailable, mark the sign research-only.
- Add ordinary no-sign/OOV sessions covering hands visible, hands near face, phone/camera variation, and non-sign gestures.

## E6-1 Decision

**Decision: Data insufficient. Stop modeling.**

The current data is sufficient for research diagnostics and for choosing what to collect or repair. It is not sufficient to justify E6-2 richer features, E6-3 rejection methods, E6-5 specialists/RGB, E6-6 routed simulation, or E6-7 Android shadow mode.

The next action is not another recognition model. The next action is a data-readiness package that repairs lineage and expands the product-core dataset for a bounded vocabulary. Once that package exists, exactly one next experiment can be chosen against the closest previous baseline.

## Closest Previous Experiment Rule

Every future proposal must include:

1. closest previous experiment;
2. result and failure mode;
3. meaningful difference from that prior work;
4. why the difference is enough to justify running;
5. expected gate and fallback.

If this cannot be answered, the experiment is rejected before implementation.
