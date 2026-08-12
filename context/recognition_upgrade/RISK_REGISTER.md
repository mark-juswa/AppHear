# Risk Register

**Purpose:** Track upgrade failure modes and their gates.
**Status:** ACTIVE / DUAL-SOURCE SCREENING RISKS NEXT. **Last updated:** 2026-07-30.

| Risk | P/I | Early warning | Mitigation | Fallback / gate |
|---|---|---|---|---|
| Insufficient signer diversity | High/Critical | train rises, held-out/worst signer stalls | 30-signer pilot, learning curves | reduce vocabulary; E8 |
| Label/variant inconsistency | High/Critical | bimodal class clusters, asymmetric confusions | fluent review, variant field, adjudication | merge/split/drop class |
| Signer/session leakage | Medium/Critical | implausible gains, duplicate hashes | signer-first split, identity/session dedupe | invalidate run; E0 |
| RGB overfit/background shortcut | High/High | RGB train gain, cross-signer/environment loss | crop jitter, background variation, masks | landmark-only; E3 |
| Landmark/RGB desync | Medium/High | fusion worse than both streams | timestamp joins, skew assertions | late fusion; E3 |
| Crop failure/occlusion | High/High | low crop coverage/blur | ROI expansion/prediction, quality gates | landmark-only frame; E2 |
| Sole MediaPipe ROI failure | High/Critical | corrected instance recall 66.30%; blur 58.33%; edge 25.81% | independent single-class detector screening, dedicated negatives, detector-agnostic ROI manager | defer hybrid if E2e-C0 cannot approach 95% recall at <=2% false ROI and mobile cost |
| Missing hand/pose | High/High | false release or zero-pattern prediction | explicit masks, modality dropout | S5/degraded mode; E5 |
| Mobile compute | High/Critical | <12 FPS/p95 >80 ms | smaller CNN, cadence, quantization | landmark-only or no-go; E7 |
| Quantization loss | Medium/High | >1 point or calibration shift | representative data, QAT, refit calibration | FP16/float CPU if viable; E7 |
| Battery/thermal | High/High | >20% throughput decay | cadence, duty cycling, smaller model | degraded/offline-only; E7 |
| Calibration shift | High/Critical | ECE/false commits rise by signer/device | val calibration, OOV/no-sign data | reject more; release no-go |
| Unknown-sign false positives | High/Critical | >1 commit/30 min | outlier exposure, boundary+unknown head | restricted push-to-sign mode |
| Boundary errors | High/Critical | insertion/drop/early wrong commits | labels, prefix/negative training | S5 fallback; E5 |
| Continuous scope expansion | High/High | isolated concatenation called translation | separate RU9 approval | remain isolated |
| Dependency/export ops | Medium/High | Select TF Ops/failed INT8 | supported primitives, export smoke first | alternative encoder |
| Research non-reproduction | Medium/High | paper gap persists | exact protocol, sanity tests, seeds | document negative result |
| Privacy/rights | Medium/Critical | missing consent/license | provenance audit, access controls | exclude data |
| Source/provenance shortcut | High/Critical | model separates ASL Citizen vs local instead of signs | source-aware splits, cross-source transfer tests, provenance-stratified metrics | reject blind merge; screen sources separately |
| Manual one-word expansion churn | High/High | repeated single-candidate no-go loops | batch candidate screening with ranked outputs | stop expansion and collect/review data first |
| Validation-only optimism | High/Critical | train/val perfect but held-out signer collapses | fixed test signer gates, latest-policy stability, per-class minimums | reject candidate even if validation is perfect |
| E5 threshold-loop stagnation | High/High | repeated no-go runs only changing thresholds, class subsets, or accept heads | E6 baseline/data/representation audit before more rejector variants | stop E5-style experiments; return to E6-0/E6-1 |
| Underpowered open-set negatives | High/Critical | accepted precision falls when unsupported/no-sign rows change | collect/source-diverse OOV and real no-sign sessions; report false commits per source | restrict vocabulary or reject more |
| Premature richer-schema adoption | Medium/High | feature width grows without routed-system gain or Kotlin parity | v3.0 control on identical splits, schema manifest, parity gate | keep v3.0 |
| Prototype/rejection overfit | Medium/High | distance/rejector works only on current unsupported set | held-out unsupported signs, source splits, fresh negatives | discard rejector or collect better negatives |
| E6-2 repeats E3-B6/B7 | Medium/High | candidate consists mainly of naive velocity, acceleration, or the prior 20 relations | enforce `E6_2_RICHER_LANDMARK_CONTROL_PLAN.md`; one geometry candidate only | stop E6-2 and retain v3.0 |
| E6-2 wider-input confound | Medium/High | candidate starts from different encoder behavior or gains only training fit | zero-extension warm start, matched head, pretraining-logit parity within `1e-6` | reject comparison |
| E6-2 mirror/anchor drift | Medium/Critical | canonical left/right or face-anchor fixtures disagree | mirror-equivalence smoke and future Python/Kotlin golden vectors | block training or Android promotion |

## Decisions, Assumptions, Open Questions, Next Action

- **Decision:** critical risks are release blockers, not warnings.
- **Assumption:** probabilities are qualitative until RU0 risk review.
- **Open question:** who owns linguistic annotation and consent review.
- **Next action:** include E4-L failure modes in the dual-source candidate-screening gates before any larger training, RGB fusion retry, or Android integration.

### C0-B0 Targeted Top-Up Risks - 2026-08-10

| Risk | Probability / impact | Early warning | Mitigation | Fallback / gate |
|---|---|---|---|---|
| Mining proxies are mistaken for annotation truth | medium / high | proxy label is copied into gold condition fields without review | keep proxies in `mining_selection.csv`; require the existing box/condition GUI for every row | quarantine ambiguous rows; do not train |
| Frozen negative fixtures leak into detector training | high / critical | N0/P1/OOV path or hash appears in a training package | block protected registry, base-run paths/hashes, and audit all negative manifests | reject source; collect independent negatives |
| Local domain is underrepresented | medium / high | scan or selected package is dominated by ASL Citizen | alternate sources before rotating signers in both scan and selection | increase independent local inventory; never reuse held-out local signers |
| Scan-relative thresholds are overinterpreted | medium / medium | Q20 blur or Q25 area is described as a universal quality threshold | label values as ranking cutoffs only; report raw scores and human conditions | re-rank under a new independent scan; no runtime threshold adoption |
| Hard-negative gap remains hidden | high / high | top-up contains only sign-video zero-proposal frames | explicitly record that all 547 old negatives overlap protected evaluation lineage | Stage 2 remains blocked until independent negatives exist |
| Interrupted scan corrupts selection | low / medium | duplicate candidate IDs or partial CSV rows | append one completed row at a time, resume by candidate ID, check unique rows before package build | restart into a new run directory if the manifest is malformed |
| ASL Citizen model is treated as a production asset | high / critical | research detector is proposed for app distribution | enforce installed `use.txt`: non-commercial research only and no data/modification distribution | obtain separate permission or retrain on production-cleared data |
| Local recordings lack documented release/consent | high / critical | local frames enter a distributable model without provenance | require signer consent/release registry before production training | restrict to internal research or exclude local source |
| Repeating weak condition proxies wastes review effort | high / medium | another identical miner yields no partial/edge cases | freeze observed proxy yield; use explicit collection or a different validated selection method | proceed only with research pilot or collect targeted conditions |
| Stage 2 learning curve is overinterpreted | high / high | development AP is described as a production or Android result | label every artifact research-only; retain frozen P0/N0/P1 and production baseline | stop after the registered learning curve and review evidence |
| Sparse Stage 2 subgroups imply false certainty | high / high | claims are made from one partial, eight near-face, or eleven edge cases overall | report numerators and denominators; keep sparse subgroup results diagnostic | collect targeted independent cases before subgroup claims |
| Nested subset composition confounds the curve | medium / medium | smaller subsets lose a source, signer, hand-count bucket, or all negatives | deterministic source/signer/hand-count round-robin; publish subset counts | reject and rebuild package before training |
| Model Maker deprecation breaks reproducibility | medium / high | pinned Docker build/export stops working | retain pinned Linux/Python 3.10 image and prior export/reload smoke | stop; evaluate a maintained trainer under a separate parity plan |
| Research-only assets drift toward production | high / critical | model is copied into Android assets or distributed | explicit authorization manifest; separate output path; no production asset write | delete proposed integration and restore frozen baseline |


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-018 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.
### E3-B4 Landmark-Temporal Follow-Up Risks - 2026-07-28

- **Small-split optimism:** probability high, impact high. Warning sign: one or two clips change the apparent winner. Mitigation: larger signer-disjoint validation with multiple seeds. Fallback: retain current landmark baseline until replicated.
- **Mask-aware pooling overfit:** probability medium, impact medium. Warning sign: `tcn_masked_pool` wins only on the 7-class split but not at larger scale. Mitigation: compare against `conv1d_baseline` and `tcn_pool` under identical splits/seeds. Fallback: use the simplest validated landmark head.
- **Premature Android integration:** probability medium, impact high. Warning sign: treating E3-B4 `0.6429/0.6429` as production evidence. Mitigation: keep Android and production recognizer changes blocked until larger offline gates pass. Fallback: preserve production v3.0 recognizer unchanged.


### E4-A Landmark/Data Generalization Risks - 2026-07-29

- **Overfitting conclusions to the reused 50-class frozen split:** probability medium, impact high. Warning sign: recommendations depend only on one test metric. Mitigation: require seed/branch stability, validation/test comparison, and uncertainty labels. Fallback: mark class decisions provisional and collect more evidence.
- **Mistaking label/variant ambiguity for model weakness:** probability high, impact high. Warning sign: stable asymmetric confusions or semantically close glosses. Mitigation: require label/variant review targets in E4-A outputs. Fallback: merge, split, defer, or adjudicate classes before retraining.
- **Generic data-collection advice:** probability medium, impact high. Warning sign: recommendations say only "collect more data". Mitigation: E4-A must name exact glosses, signers, repetitions, and variation targets. Fallback: block E4-B retrain until targets are concrete.
- **Missing per-clip or per-signer evidence:** probability medium, impact medium. Warning sign: metrics files lack predictions needed for signer audit. Mitigation: report tooling gap and regenerate predictions from saved checkpoints only if required. Fallback: limit E4-A claims to class/branch evidence.
- **Premature production simplification:** probability medium, impact critical. Warning sign: reliable subset is treated as production-ready. Mitigation: E4-A can recommend a retrain only; release gates still require calibration, no-sign/OOV, boundary, device, and user testing. Fallback: keep production v3.0 frozen.



### Dynamic Mixed Recognition Risks - 2026-07-31

- **Router false confidence:** probability high, impact critical. Warning sign: primary model routes a hard sign as stable and commits without resolver evidence. Mitigation: top-k confusion registry, margin/entropy checks, calibrated thresholds, no-sign/OOV tests. Fallback: reject more or keep sign deferred.
- **Specialist sprawl:** probability medium, impact high. Warning sign: every failing sign gets a custom model. Mitigation: only registered recurring confusion groups can receive specialists; require group-level gates. Fallback: data repair or defer signs.
- **Stable-vocabulary overclaim:** probability high, impact critical. Warning sign: E4-N-style small-batch success is described as general translator readiness. Mitigation: publish exact vocabulary, per-class gates, accepted coverage. Fallback: smaller release scope.
- **Derived-feature distraction:** probability medium, impact medium. Warning sign: `[96,728]` is pushed to Android after E4-Q despite failing `SORRY`. Mitigation: keep v3.0 primary; require parity only for passed specialist schemas. Fallback: discard derived features for this group.
- **RGB specialist cost creep:** probability medium, impact high. Warning sign: crop resolver must run every frame or for too many groups. Mitigation: conditional routing, cadence limits, device profiling. Fallback: reject/defer hard group.
- **User-confirmation mismatch:** probability high, impact critical. Warning sign: product assumes a non-signing user can confirm correctness. Mitigation: algorithmic calibration/rejection only. Fallback: do not commit uncertain translations.

### E6-3 Frozen-Embedding Rejection Risks - 2026-08-09

| Risk | Probability / impact | Early warning | Mitigation | Fallback / gate |
|---|---|---|---|---|
| Frozen closed-set embedding has no usable open-set geometry | high / high | Mahalanobis has no valid development operating point | freeze classifier, use all three seeds, compare with MSP/energy | E6-3 no-go; no automatic rejector tuning |
| One-signer fresh negatives overstate quality | high / high | development/fresh gap or subtype-perfect result | keep claim diagnostic and report signer/subtype separately | require untouched negative signers before production |
| Rejection hides a supported-class failure | medium / high | low or zero accepted recall for any class | enforce per-class accepted-recall gates | no-go regardless of aggregate precision |
| Stress `KNOW` lies inside `HELLO` distribution | high / high | accepted false commits fall less than `70%` | publish embedding-distance evidence | preserve for E6-4/E6-5; rejection cannot fix it |
| Negative windows are reconstructed inconsistently | medium / high | missing timestamp, noncausal frames, extraction mismatch | fail closed and preserve source frame/window lineage | repair extraction before scoring |
| Reused diagnostic sets become tuning sets | high / high | method/threshold changes after fresh or stress inspection | fit only on repaired val plus historical development negatives | invalidate the run |

See `E6_3_OPEN_SET_REJECTION_PLAN.md` for the complete contract.

### E6-5 KNOW/HELLO Specialist Risks - 2026-08-09

| Risk | Probability / impact | Early warning | Mitigation | Fallback / gate |
|---|---|---|---|---|
| Specialist repeats E4-V without new evidence | medium / high | only a from-scratch small Conv1D is tested | use production-style TCN, seed-matched E6 warm starts, and repaired multi-view data | invalidate package if controls or lineage differ |
| Reused diagnostic signers overstate success | high / critical | fresh/stress pass but no untouched signer exists | label any pass provisional; require new signer before production | do not export or integrate |
| Binary resolver destroys true HELLO | medium / critical | KNOW improves while HELLO recall falls | preregister HELLO recall floors on fresh/stress/historical views | reject branch |
| Geometry adds complexity without benefit | medium / high | geometry ties v3 or wins only one view | require at least `0.03` worst-view gain with historical preservation | select v3 or reject both |
| Local source concentration drives result | high / high | validation is near-perfect while AppHear stress remains weak | require stress, fresh, historical, all-seed gates | recollect/defer KNOW |
| Specialist encourages premature routing | medium / critical | E6-5 pass is treated as system safety | keep E6-6 separate and keep E6-3 no-go visible | no routing/Android change |

E6-5 outcome: no specialist passed. The dominant observed warnings were AppHear stress `KNOW`
collapse and geometry seed instability. Mitigations now become fixed decisions: defer `KNOW`, do
not select a favorable seed, and block E6-6/E6-7.

### Post-E6 C0-B0 Hand-ROI Risks - 2026-08-09

| Risk | Probability / impact | Early warning | Mitigation | Fallback / gate |
|---|---|---|---|---|
| Training/evaluation leakage | high / critical | any P0/N0/P1 source hash occurs in training | hash-lock source videos and fail closed before annotation/training | invalidate package |
| Insufficient detector diversity | high / high | few signers/devices or missing blur/edge/two-hand cases | inventory attributes before setting training scope; nested learning curve | stop and report exact data gap |
| Deprecated Model Maker toolchain | low-medium / high | pinned Docker rebuild or export/reload regresses | freeze the passing Python 3.10 lock and rerun the smoke before later training | architecture amendment or no-go |
| False ROI remains coupled to recall | high / critical | no development threshold controls no-hand errors without missed hands | explicit hard negatives and locked threshold protocol | C0-B0 no-go; no post-test tuning |
| INT8 degradation | medium / high | float passes but INT8 misses subgroup gates | evaluate both with identical preprocessing | reject INT8 branch; no Android work |
| Detector cost breaks runtime budget | medium / critical | CPU projection already consumes cadence/thermal budget | 256 branch first; record size/latency/memory | no device benchmark or integration |
| Reliable crops do not improve recognition | medium / high | later hand-RGB branch does not beat landmark control | keep detector gate separate from recognition claim | preserve v3.0; do not fuse |

The toolchain risk probability was reduced only because `c0b_toolchain_smoke_03` passed. The
deprecated dependency remains high-impact. New immediate risks are annotation fatigue and proposal
bias: MediaPipe boxes are editable suggestions, selection must remain detector-independent, and no
proposal becomes gold without human review.

The 300-frame review confirmed proposal bias is condition-specific: non-blurred recall is high,
but blur, edge, occlusion, and complete two-hand recall are weak. Random expansion would mostly add
easy duplicates. Mitigation is one bounded automated hard-condition mining/top-up pass with source,
signer, video, and hash independence enforced before review.

