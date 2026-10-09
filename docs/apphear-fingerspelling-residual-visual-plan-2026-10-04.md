# Quality-gated residual visual correction — frozen implementation plan

Separate opt-in offline fingerspelling experiment, explicitly authorized by the user.
Prior failed fusion remains unchanged. Operational context/skills reviewed; actual
WORD/Candidate01/Android/Context Assist remain protected. No new detector/backbone/split.

Terms: quality is current-frame proposal/refiner reliability, not letter correctness;
dedup affects appearance only; fallback means actual B2 logits, not a new geometry
control; readiness means user-run offline experiment, not product acceptance.

1. CropQualityFilter.v1: require proposal + accepted refiner, presence≥.9, ≥18valid
   joints, ≥15proposal-supported joints(score≥.1), expanded crop/source area≥.8,
   valid landmark containment≥.95. Reuse previous128crop/1.10expansion, no resize tuning.
   Score=presence×joint-fraction×support-fraction×source-intersection×containment;
   hard rejection score0. No body requirement, inference changes or temporal carry.
2. VisualDuplicateSuppressor.v1: both eligible, ROI IoU≥.75, center distance≤.15shorter
   side, median common-joint separation≤.08shorter side, side ratio≤1.25 and ≥18common
   joints. Keep larger quality; exact ties keep slot0. No geometry mutation or physical
   handedness inference. Strong current-frame evidence only, no tracking.
3. Audit 12retained and representative rejected/deduplicated crops spanning existing
   TRAIN strata/DEV/low coverage/refiner failures. No transcript-dependent quality.
   Record human-visible classifications; stop/fix before training if nuisance remains
   common(>10% in this bounded retained audit). This is not a statistical purity claim.
4. Actual frozen B2 epoch76 checkpoint SHA pinned; expose final64-dimensional pre-head
   state and original logits together, **call with training=False**, freeze all B2
   weights including head. Frozen/trainable are distinct in Keras: dropout must stay
   in inference mode ([official guide](https://keras.io/guides/transfer_learning/)).
5. Shared576→16visual projection; quality-weighted pooling of retained slots; gate
   sigmoid from visual16+B2state64, initial bias−2;16→64tanh residual output initialized
   exactly zero, bounded coordinate magnitude.25, quality-gated and padded-mask zero.
   Reuse original frozen CTC head on corrected state. Explicit quality0 selects original
   B2 logits, even after updates. About10.4k trainable parameters, no new temporal layers.
6. Separate1559input uses unchanged405geometry + two576embeddings + twofloat quality
   scores. Native/intermediate/phone indices align; original adapter recomputes dt/motion.
   Store quality/rejection/dedup/ROI/crop hashes/raw-frame identities; reuse existing81
   encoder outputs only after exact lineage checks. Others decode local RGB/encode only
   trusted slots; serial/resumable user-run bulk, no downloads or perception inference.
7. Engineering smoke only here: zero residual/missing-crop B2 parity, causal prefix,
   intended gradients/frozen weights, finite CTC, metadata/frame alignment, save/load,
   epoch/Adam resume and both DEV views. No new64/17 performance gate.
8. Full user-run1024TRAIN/256DEV, three cadence regimes, CTC feasible fallback unchanged.
   One residual adapter, frozen B2/appearance. Max60/min10epochs, patience12/.002;
   select mean native/sparse DEV CER using **fixed B2 penalty.5**. Keep raw metrics too;
   no recalibration. Compare every evaluation with actual B2, not retrained control.
9. Final support requires both fixed-penalty CERs lower, both correct-character counts
   higher, both substitutions lower, mean precision not lower and ≥8/15DEV signers
   improve balanced CER. Retain individual raw/fixed scores; rule frozen before full
   training. Otherwise preserve B2 and close this visual direction, no automatic sweep.

Implementation/config identities separate; existing405 and prior visual contracts intact.
Model/crop Android parity and CPU/cadence remain later gates. No product rollout authorized.
