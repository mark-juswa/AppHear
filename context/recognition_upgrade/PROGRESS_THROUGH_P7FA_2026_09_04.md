# Recognition upgrade — consolidated progress through P7F-A

Recorded 2026-09-04 with explicit user authorization to append context and tracker updates.
This is a documentation catch-up, not a new experiment, approval to train, or production rollout.
Older context entries remain historical records. Their pending/next-step statements must not
restart completed gates. Frozen experiment reports, decisions and contracts remain authoritative
for their own results; none are rewritten by this document.

## Current state — read first

- Latest completed gate: `P7FA_GEOMETRY_READY_IDENTITY_MISSINGNESS_GAPS`.
- One recommended next gate: `PROJECT_LEAD_FAMILY_A_SUPERVISION_CONTRACT_REVIEW`.
  Not executed. Wait for project-lead direction before any training, labeling or extraction.
- Family A is primary. The frozen architecture is `FA_DS_SPATIAL_V1`; Family B is the only
  predeclared output-family fallback and requires separate approval. Family C is unauthorized.
- Family-A runtime weights are random/untrained. No landmark, identity or recognition accuracy
  follows from runtime or parity results. Production replacement remains unauthorized.
- P7D-R2 compute feasibility passed. P7E remains `P7E_INTEGRATED_RUNTIME_BELOW_SCREEN`.
  The remaining runtime debt is parked, not erased or reopened by the supervision audit.
- Leading offline recognizer remains `PFCE_MATCHED + EC_P3`, MODERATE confidence.
  Checkpoint transfer to materially different Family-A features is NOT_ASSUMED.

## P5 research closure: preserve the full causal chain

Source: [D12 synthesis](../../artifacts/recognition_upgrade/p5_representation_v2/p5d12_future_version_evidence_synthesis_01/P5D12_FUTURE_VERSION_EVIDENCE_SYNTHESIS.md)
and its canonical state, handoff, claim matrix, corrections and loop-prevention register.

| Stage | Completed evidence / meaning | Boundary retained |
|---|---|---|
| P5-B migration and baseline | 8,131 native/V2 records across mixed governed roles; short-horizon baseline followed by controlled diagnosis | Never treat all 8,131 as TRAIN |
| RCA-A / RCA-B | Insufficient original training horizon diagnosed; longer governed training demonstrated that the 4x64 causal TCN can learn V2 | Historical checkpoints/results not replaced |
| RCA-C and subsequent synthesis | Historical augmentation transfer rejected as the primary solution | No augmentation/recovery loop restarted |
| D1 | `REPRESENTATION_PARITY_EXPERIMENT_INCONCLUSIVE`, LOW confidence; Legacy258 lacked consistent matched-training advantage | V2 sufficiency was NOT proven |
| D2 | Temporal objective helpful but insufficient; PFCE retained | CLIPCE remains diagnostic, not promoted |
| D3 | Performance continued improving toward full current-distribution coverage | No claim that signer/variant coverage is saturated |
| D4–D6 | External-data/form review and governed Sem-Lex lexical decisions | Lexical acceptance is not landmark/identity truth |
| D7 / D7B | 2,417 successful teacher pairs; 2,415 usable candidates after audit; 65 classes, 32 namespaced signers | Larger pool not automatically authorized for training |
| D8 | Frozen `P3_ONE_PER_SIGNER_CLASS_CLASS_SHARE_67`, 881 selected clips | No new source-cap policy |
| D9B | Naive P3 helped supplemented65 while unsupplemented171 declined; class share changed20.61%→35.16% | Not pure signer-diversity causality |
| D10A | No pristine final holdout; canonical TEST is secondary-confirmation-only | No untouched-test claim |
| D10B | Secondary confirmation reproduced redistribution and full-vocabulary directional harm | Terminal evidence for that cycle; no test tuning |
| D11A / D11B | Exact baseline class-schedule replay with P3 within-class diversity; all three matched runs verified; signer-balanced delta positive3/3 | New evidence is validation-based, not pristine confirmation |
| D12 | `P5D12_RESEARCH_EVIDENCE_SYNTHESIZED_EC_P3_LEADING_CANDIDATE` | P5 research closed; no automatic D13 |

D11 median signer-balanced Top1 improved about1.739 percentage points. Clip NLL worsened3/3,
per-frame accuracy declined2/3, Top5 was mixed, only five validation signer groups were available,
and all signer-block intervals crossed zero. Confidence remains MODERATE. The residual gain is
not proof of pure signer-diversity causality. No deployment seed was selected.

## P6 runtime compatibility and the mobile transition

| Gate | Formal result | Interpretation |
|---|---|---|
| P6-A | `P6A_CURRENT_RUNTIME_NOT_EXACTLY_V2_COMPATIBLE` | MediaPipe/legacy semantics cannot be relabeled V2 by matching shape; score, validity, observed and slot meanings matter |
| P6-B | `P6B_SEMANTIC_PARITY_FAILED` | Original full133 numeric gate failed on unused face point42; effective V2 passed; formal failure remains |
| P6B-R1 | `P6BR1_V2_DEPENDENCY_PARITY_NOT_CONFIRMED` | New60-fixture raw hand-coordinate excursion remained a failure; affected hand was unobserved/zeroed and final V2 passed |
| Project-lead transition | Desktop effective V2 evidence deemed sufficient for Android feasibility | Neither earlier failure reclassified; further desktop parity runs closed |
| P6-C | `P6C_ANDROID_V2_DEVICE_BELOW_TARGET` | Android semantic parity60/60 passed; CPU live pipeline about1FPS, well below15 |
| P6C-P1 | `P6CP1_FROZEN_DWPOSE_ACCELERATION_TARGET_NOT_MET` | XNNPACK semantic parity passed but backend1.861052FPS; NNAPI executed partitions but failed semantic parity, so no NNAPI performance run |

The exact DWPose-L FP32 flip-test path is closed as the direct mobile production backend on
Xiaomi M2101K7AG / SM6150 / Android12. It is retained as OFFLINE_REFERENCE_TEACHER; V2 remains
the offline reference representation, not the mandatory future production ABI. No QNN, provider
sweep, quantization, new resolution, DWPose variant or automatic alternative model was authorized.

## P7 architecture, runtime and supervision

| Gate | Formal result | What was established |
|---|---|---|
| P7-A | `P7A_ARCHITECTURE_DECISION_EVIDENCE_READY` | Audited downstream requirements, teacher/source assets and runtime-first architecture decision space; no model selected at that gate |
| P7-B | `P7B_FAMILY_A_CONTRACT_READY` | Explicit21-point anatomical hands + eight body joints;202-float frame ABI and uncertainty boundaries |
| P7-C | `P7C_PRIMARY_MOBILE_ARCHITECTURE_SELECTED` | One exact `FA_DS_SPATIAL_V1` random-weight runtime hypothesis; no accuracy claim |
| P7-D | `P7D_PRIMARY_RUNTIME_SKELETON_BELOW_SCREEN` | Exact FP32 graph exported/loaded; host preprocessing/decoder dominated; complete p95≈284.973ms and4.05556FPS |
| P7D-R1 | `P7DR1_RUNTIME_PATH_REMEDIATION_BELOW_SCREEN` | Optimized JVM path preserved parity but compute p95≈96.97ms and10.33loops/sec; no camera/integrated follow-on |
| P7D-R2 | `P7DR2_NATIVE_HOST_COMPUTE_SCREEN_PASS` | Native preprocessing/decoder preserved semantics; V3 compute p95=25.133427ms,40.733333loops/sec; real camera remained≈10FPS |
| P7E | `P7E_INTEGRATED_RUNTIME_BELOW_SCREEN` | Fixed[15,15] AE camera-only passed; integrated capture15FPS but analyzer/completed14.883333FPS, despite p95=48.6157707ms |
| P7F-A | `P7FA_GEOMETRY_READY_IDENTITY_MISSINGNESS_GAPS` | Base TRAIN geometry pseudo-supervision supports contract design; assignment/missingness targets and Sem-Lex alignment remain unresolved |

P7E camera-only measured900 captures/60s=15FPS and901 analyzer callbacks/60s≈15.016667FPS.
Integrated measured2700 captures,2679 analyzer/completed frames over180s. Do not round
14.883333 upward or infer delivered FPS from reciprocal latency. No crashes/OOM/runtime errors
were recorded in the successful measurement; sampled thermal status remained NONE. The current
closed gate remains a failure of the full screen, not a neural-compute or recognition-accuracy failure.

The skeleton screen is complete perception p95≤62.7532812ms AND completed processing≥15FPS;
it is only a conditional engineering screen, not proof of full S5/S6/S7/UI product cadence.
Memory is observational; no formal memory ceiling has been frozen. No follow-up runtime tuning,
30FPS camera trial, Family-B activation or production migration is automatic.

## Frozen contract and implementation boundaries

| Lane | Contract | Status |
|---|---|---|
| Production | Schema3.0 legacy MediaPipe S4, [96,258] recognizer input | Not replaced by P5/P6/P7 research |
| Offline research | `DWPOSE_REPRESENTATION_V2_238`, [96,238],4x64 causal TCN/PFCE+EC_P3 | Frozen offline candidate; not drop-in Android-compatible |
| Family-A frame ABI | `APPHEAR_FAMILY_A_FRAME_V1`,202float32 + metadata | Deterministic adapter interface, NOT native neural training targets |
| Family-A neural output | Input[1,384,384,3]; heatmaps[1,96,96,50]; assignment logits[1,1,1,2] | Untrained FP32 skeleton, TFLite2.16.1/XNNPACK2threads |

Model SHA: `d8617516aa08b4827c7a75276c5de5c0d76a07620a07d212d323992c188ee42e`.
Actual skeleton delegation:44/44 nodes, one partition, zero graph fallback nodes.
Decoder: `P7C_NATIVE_HEATMAP_LOCAL3_V1`; preprocess: `P7C_RGB_LETTERBOX384_V1`.
No usable payload goes to S5/recognizer/S7 while policy is `POLICY_UNCONFIGURED`.

Family-A anatomy: LH channels0..20 ↔ DWPose91..111; RH21..41 ↔112..132;
BODY42..49 ↔5..12: bilateral shoulders, elbows, wrists and hips. Body and hand wrists
remain distinct estimates. Body validity never depends on hand-observed states. Anatomical
identity is not screen side, detector order or dominance. Unknown identity is explicit, not guessed.
No Z, carry-forward, interpolation, extrapolation or opposite-hand copying is introduced.

## P7F-A label/data findings

| Population | Candidate clips | Source-aware signers | Classes | Lineage-check ready |
|---|---:|---:|---:|---:|
| ASL Citizen TRAIN | 3309 | 35 | 236 | 3309 |
| AppHear/local TRAIN combined | 617 | 5 | 5 | 617 |
| Frozen Sem-Lex P3 | 881 | 32 | 65 | 83;798 pending frame-alignment checks |

All4807 raw/native pairs match governed hashes and were unchanged on recheck. Base membership
is3926, not8131. Local617=297 APPHEAR_CAPTURE+320 LOCAL, not additional populations.
No raw pixels were decoded or new labels generated during this audit.

- Geometry readiness is **pseudo-supervision contract-design support**, not verified physical
  localization. Finite/in-bounds diagnostics do not establish correctness. Many hip estimates
  are finite but out of source bounds; do not clamp or turn zeros into absence targets.
- Existing P4 development counts/ownership and prior identity reviews are partial evidence,
  not complete Family-A assignment-support labels. Crossing/contact adequacy is insufficient.
- Physical missingness labels remain partial. Teacher invalidity/low confidence does not
  distinguish absence, occlusion, out-of-frame, visible teacher failure or subject ambiguity.
- Direct DWPose-score regression is NOT_SUPPORTED. FA sigmoid peak evidence is uncalibrated;
  teacher scores may inform descriptive quality/eligibility review, not automatic probability targets.
- Sem-Lex's old provenance blocker was resolved by the P5D8 attestation and P5D9A authorization;
  the881 selected IDs match D11. Lexical review is not per-frame anatomy review. Historical
  exact47 combines human exact45 plus metadata exact2.
- 798 selected Sem-Lex files return invalid negative container frame counts;77 have repeated
  adjacent native timestamps, none decreasing. All881 native index sequences remain exact.
  These are unresolved alignment checks, not proof of corruption or permission to replace P3
  with an83-clip subset. No2415-clip expansion is authorized.
- Source-aware signer namespacing does not independently prove cross-corpus physical identity.
- ASL Citizen raw videos moved to `G:/ASL CITIZEN/ASL CITIZEN/ASL_Citizen/videos`.
  Resolve historical F: paths by governed content hash; do not rewrite manifests or substitute
  by filename alone.

## Governance and open decisions

D10 canonical2620 TEST remains development-exposed SECONDARY_CONFIRMATION_ONLY and protected
from new development/tuning. ASL Citizen VAL is EVALUATION_ONLY, not Family-A training or
threshold-fitting data. Protected replay and pristine signers remain excluded. Do not infer
permission from old general validation/calibration guidance or old pending experiment notes.

- [x] P5 evidence closure through D12 recorded; no automatic new P5 experiment.
- [x] P6 runtime compatibility/acceleration evidence recorded; exact DWPose mobile path closed.
- [x] P7A/B/C design contracts and P7D/R1/R2 runtime evidence recorded.
- [x] P7E fixed15 camera and integrated measurements recorded without rounding/reclassification.
- [x] P7F-A supervision adequacy audit and preservation checks complete.
- [ ] Project-lead supervision-contract review; no execution authorized by this update.
- [ ] Anatomical assignment and missingness target adequacy; bounded reviewed evidence needed.
- [ ] Sem-Lex frame/timestamp revalidation; no teacher rerun or replacement policy authorized.
- [ ] Target/loss-mask and calibration protocol before separately authorized training.
- [ ] Future eight-body normalization and S5/S7 behavior; checkpoint transfer not assumed.
- [ ] Parked integrated runtime debt and complete product validation; not reopened now.

No training, annotation, extraction, calibration, benchmark, model change or production work
is authorized merely by marking these historical gates complete. Continuous ASL, phrase-level
accuracy, calibrated confidence and production readiness remain NOT_ESTABLISHED.

## Source-of-truth entry points

All directories below are under `artifacts/recognition_upgrade/`; read their canonical state,
report, decision, source index and integrity artifact for exact governed detail.

| Scope | Artifact directory |
|---|---|
| P5-B and D1–D12 | `p5_representation_v2/`; closure `p5d12_future_version_evidence_synthesis_01/` |
| P6-A | `p6a_production_runtime_compatibility_audit_01/` |
| P6-B | `p6b_v2_backend_feasibility_prototype_01/` |
| P6B-R1 | `p6br1_v2_dependency_parity_confirmation_01/` |
| P6-C | `p6c_android_v2_device_feasibility_01/` |
| P6C-P1 | `p6cp1_frozen_dwpose_runtime_acceleration_triage_01/` |
| P7-A | `p7a_mobile_native_architecture_transition_audit_01/` |
| P7-B | `p7b_family_a_output_runtime_contract_01/` |
| P7-C | `p7c_mobile_architecture_selection_01/` |
| P7-D | `p7d_android_runtime_skeleton_feasibility_01/` |
| P7D-R1 | `p7dr1_runtime_data_path_remediation_01/` |
| P7D-R2 | `p7dr2_native_host_path_feasibility_01/` |
| P7E | `p7e_camera_cadence_feasibility_01/` |
| P7F-A | `p7fa_family_a_supervision_label_adequacy_audit_01/` |

Historical integrity records describe their own completed time windows. The user-authorized
2026-09-04 context append deliberately creates a new documentation baseline; do not rerun old
finalizers to alter their hashes or call this later authorized update a retroactive experiment failure.
