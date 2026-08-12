# E6 Existing Negative-Source Search Result

**Purpose:** Exhaust the useful existing raw-data sources for the remaining E6 no-sign, OOV, and
transition coverage before requesting new recordings.

**Scope:** Existing-source discovery, raw-video lineage, deterministic OOV selection, decode/hash
validation, and coverage accounting only. No feature extraction, model training, schema change,
TFLite export, Android change, or production recognizer replacement was performed.

**Current status:** COMPLETE / OOV DEVELOPMENT TARGET FILLED / NEW CONTEXT DATA STILL REQUIRED.

**Last updated:** 2026-08-05.

## Verified Outputs

- Utility: `pipeline/rgb/e6_existing_negative_source_search.py`.
- Tests: `tests/test_e6_existing_negative_source_search.py`.
- Run: `artifacts/recognition_upgrade/product_core_data_readiness/e6_existing_negative_source_search_01`.
- ASL Citizen source: `F:/ASL DATASET/ASL CITIZEN/ASL_Citizen`.
- Prior P1 result: `E6_NEGATIVE_REUSE_AUDIT_RESULT.md`.

## ASL Citizen OOV Result

The ASL Citizen official training split contains 40,035 available raw clips whose normalized gloss
is outside the eight-sign product core. The audit selected a deterministic signer-balanced subset:

- 200 raw videos;
- 200 distinct non-core glosses;
- 35 official training participants;
- 200 unique SHA-256 hashes;
- 200/200 successful first/middle/last decode probes;
- no fresh-evaluation credit because ASL Citizen was already used throughout E1-E5.

Exact OOV labels are retained for lineage but are not proposed as model output classes. They are
development evidence that real signing outside the product vocabulary must be rejected.

## Coverage After All Verified Existing Reuse

| Subtype | Target | Historical development credit | Remaining volume gap | Fresh evaluation |
|---|---:|---:|---:|---|
| `N0_NO_HAND` | 150 | 150 | 0 | Missing |
| `P1_IDLE_HANDS` | 200 | 143 | 57 | Missing |
| `P1_FACE_ADJACENT` | 200 | 54 | 146 | Missing |
| `P1_ACCIDENTAL_MOTION` | 150 | 0 | 150 | Missing |
| `OOV_SIGN` | 200 | 200 | 0 | Missing |
| `TRANSITION_PARTIAL` | 100 | 0 | 100 | Missing |
| **Total** | **1,000** | **547** | **453** | **Missing for every subtype** |

## Sources Rejected For Additional Credit

- E4-AG: duplicate aliases of the canonical P1 videos, already counted once.
- Existing isolated positive clips: may contain onset/release frames, but no verified temporal
  boundaries exist; do not relabel them as transitions by assumption.
- Existing P1 clips: may contain accidental motion, but prior annotations do not identify that
  temporal subtype; do not infer it from a center image.
- Local supplementary sign clips: useful positive/OOV lineage, but not no-sign or accidental-motion
  evidence and already used in E4/E5.
- E2e Android fixture: recognition/tracking fixture, not an independent negative-context corpus.

No other independent raw negative-context corpus is present in the audited workspace.

## Irreducible Volume Checklist

Before the 1,000-window engineering volume gate can pass, acquire or explicitly revise the target
for:

- 57 idle visible-hand windows;
- 146 face-adjacent non-sign windows;
- 150 accidental-motion windows;
- 100 transition/partial-sign windows.

This is 453 additional verified windows. N0 and OOV development volume do not need more collection.
However, every subtype still needs a genuinely fresh signer/device evaluation slice; the existing
target files do not define a verified minimum size for that slice. Any proposed fresh-test count is
therefore an engineering decision requiring explicit approval, not an experimentally proven number.

## Positive Vocabulary Decision

The negative-source search does not change positive readiness. The fastest trustworthy first
baseline is the five-sign bounded core `GOOD`, `HELLO`, `SORRY`, `HAVE`, and `KNOW`, with the existing
documented HAVE signer exception. `THINK`, `TAKE`, and `SELL` should be deferred from this first
baseline rather than blocking all progress; they remain expansion candidates after their signer and
fresh-test gaps are repaired.

This is an engineering recommendation, not yet an approved production-vocabulary change.

## Decision And Next Action

Existing data cannot fully satisfy readiness. The existing-source search is exhausted and must not
be repeated under another experiment name. The next decision is whether to approve:

1. the five-sign bounded baseline vocabulary; and
2. a lean, explicit fresh-evaluation/453-window collection protocol.

Only after those decisions and resulting data validation may the clean schema-v3.0 `[96,258]`
baseline extraction/training experiment begin.

## Source-Of-Truth Files

- `asl_citizen_oov_manifest.csv`
- `coverage_after_existing_sources.csv`
- `source_search_summary.json`

## Related Context

- `E6_NEGATIVE_REUSE_AUDIT_RESULT.md`
- `E6_COLLECTION_INTEGRATION_RESULT.md`
- `E6_TARGETED_COLLECTION_RUNBOOK.md`
- `../../PRODUCT_CORE_DATA_READINESS_PACKAGE.md`
- `../../../progress-tracker.md`

