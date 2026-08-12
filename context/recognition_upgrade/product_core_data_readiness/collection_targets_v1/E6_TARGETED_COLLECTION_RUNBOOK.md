# E6 Targeted Product-Core Collection Runbook

**Purpose:** Define the exact recordings needed after product-core review and provide commands to validate new raw videos.

**Scope:** Collection and raw-video validation only. Do not extract features, train models, change schema, export TFLite, or modify Android from this step.

**Current status:** Historical target contract / integration, review, and existing-source search complete.

**Last updated:** 2026-08-05.

Current result: E6_COLLECTION_INTEGRATION_RESULT.md. Do not infer signer identity or completion from folder counts alone: recorder filename IDs and cross-manifest hashes found 60 copied rows under P_NEW04 that are not new signer evidence.
## Current Superseding State

Read E6_NEGATIVE_REUSE_AUDIT_RESULT.md and E6_EXISTING_NEGATIVE_SOURCE_SEARCH_RESULT.md before
recording. The original targets below are historical pre-integration targets.

Verified current state:

- Positive strict gaps remain only for THINK (23 clips, two local signer slots), TAKE (21 clips,
  two local signer slots and no fresh-test assignment), and SELL (one local signer slot).
- The recommended bounded first baseline defers those three signs and uses
  GOOD/HELLO/SORRY/HAVE/KNOW; this requires explicit approval.
- Existing N0, P1, and ASL Citizen OOV reuse provides 547/1,000 historical development windows.
- Irreducible volume gap: 57 idle-hand, 146 face-adjacent, 150 accidental-motion, and 100
  transition/partial windows (453 total).
- Fresh evaluation remains missing for every negative subtype.
- Do not collect more N0 or development OOV merely to satisfy the original volume table.
- Do not count E4-AG P03/P04 aliases as new participants or videos.

## Targets

Machine-readable targets:

- `context/recognition_upgrade/product_core_data_readiness/collection_targets_v1/positive_collection_targets.csv`
- `context/recognition_upgrade/product_core_data_readiness/collection_targets_v1/nosign_oov_transition_targets.csv`
- `context/recognition_upgrade/product_core_data_readiness/collection_targets_v1/collection_target_summary.json`

Current required collection:

- Positive selected-sign clips from fresh local/app-domain signers: `605`
- Local signer slots: `25`
- No-sign/OOV/transition reviewed windows: `1000`

## Positive Clip Targets

Collect from fresh local signers. Prefer distributing each sign across the required new signer count rather than recording all clips from one person.

| Sign | New local clips | New local signer slots | Minimum clips per new signer |
|---|---:|---:|---:|
| `GOOD` | 69 | 3 | 23 |
| `HELLO` | 20 | 2 | 10 |
| `SORRY` | 69 | 2 | 35 |
| `HAVE` | 70 | 3 | 24 |
| `KNOW` | 76 | 3 | 26 |
| `THINK` | 99 | 4 | 25 |
| `TAKE` | 101 | 4 | 26 |
| `SELL` | 101 | 4 | 26 |

## No-Sign/OOV/Transition Targets

| Kind | Target windows | Recommended video minutes | Examples |
|---|---:|---:|---|
| `N0_NO_HAND` | 150 | 15 | No hands visible, person absent, hands outside frame |
| `P1_IDLE_HANDS` | 200 | 20 | Hands visible but not signing |
| `P1_FACE_ADJACENT` | 200 | 20 | Hands near face/hair/glasses/phone, not signing |
| `P1_ACCIDENTAL_MOTION` | 150 | 15 | Reaching, typing, holding objects, adjusting camera |
| `OOV_SIGN` | 200 | 20 | Real signs outside selected vocabulary |
| `TRANSITION_PARTIAL` | 100 | 10 | Rest-to-sign, sign-to-rest, between signs, partial/aborted signs |

## Folder Structure

Place positive videos here:

```text
scratchpad/e6_product_core_collection/raw/positive/<SIGN>/<PARTICIPANT>/<DEVICE>/<ENVIRONMENT>/<front-or-back>/<video>.mp4
```

Place no-sign videos here:

```text
scratchpad/e6_product_core_collection/raw/nosign/<SUBTYPE>/<PARTICIPANT>/<DEVICE>/<ENVIRONMENT>/<front-or-back>/<video>.mp4
```

Place OOV videos here:

```text
scratchpad/e6_product_core_collection/raw/oov/<OOV_LABEL>/<PARTICIPANT>/<DEVICE>/<ENVIRONMENT>/<front-or-back>/<video>.mp4
```

Place transition/partial videos here:

```text
scratchpad/e6_product_core_collection/raw/transition/<SIGN_OR_PAIR>/<PARTICIPANT>/<DEVICE>/<ENVIRONMENT>/<front-or-back>/<video>.mp4
```

Participant IDs should be stable, for example `P07`, `P08`, `P09`. Do not reuse old local signer IDs for fresh held-out signers.

## Commands

Initialize/scaffold folders:

```powershell
cd "F:\ASL DATASET. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_collection_validate init `
  --raw-root "scratchpad\e6_product_core_collectionaw"
```

Validate after adding videos:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_collection_validate validate `
  --raw-root "scratchpad\e6_product_core_collectionaw" `
  --output "artifactsecognition_upgrade\product_core_data_readiness\e6_collection_validation_01"
```

Outputs:

- `raw_collection_inventory.csv`
- `positive_collection_progress.csv`
- `nosign_oov_transition_progress.csv`
- `collection_validation_summary.json`

## Recording Rules

- Use front camera first, unless a deliberate back-camera condition is being recorded.
- Keep signer upper body and hands visible.
- Record normal speed, not exaggerated training-only motion.
- Use varied but realistic backgrounds and lighting.
- Avoid cutting off sign onset/release.
- Record from new/fresh participants where possible.
- Do not record all clips for one sign from one signer.
- Do not use the same participant as both train and fresh test later.

## What Happens After Recording

1. Run the raw validator.
2. Fix path/decode/duplicate/folder issues.
3. Build or update a canonical collection manifest.
4. Review questionable clips.
5. Recalculate gaps.
6. Only if data gates pass, prepare a clean v3.0 `[96,258]` baseline extraction/training package.

## While Recordings Are Pending

Work that can proceed without recordings:

- Harden the raw validator and manifest schema.
- Prepare a split-assignment dry-run that refuses signer leakage.
- Prepare the v3.0 baseline experiment design without running extraction/training.
- Prepare no-sign/OOV review taxonomy and acceptance criteria.
- Keep context and memory current.

Work that remains blocked:

- Feature extraction.
- Model training.
- Rejection/specialist/RGB experiments.
- TFLite export.
- Android integration.
