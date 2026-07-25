# 06 — Feature / Schema Contract

*Supports §8.1 and the §7 non-negotiable: "Maintain a clear feature/schema contract (v2 used
258-float / 10-field; 3 may redesign it, but the contract must be explicit and versioned)."*

---

## Why this is its own document

The feature vector is the **contract between perception (S1–S4) and the model (S6).** If it
drifts silently between training and runtime, everything downstream is invalid and the bug is
nearly invisible (train/serve skew). So the contract is **explicit, versioned, and identical
offline and on-device.**

---

## v2 baseline (for reference / migration)

- **258 floats per frame**, over a 30-frame window.
- Decomposition (the v2 layout AppHear 3 inherits and re-bases):
  - Hands: `2 hands × 21 landmarks × 3 (x,y,z)` = **126**
  - Pose: `33 landmarks × 4 (x,y,z,visibility)` = **132**
  - Face: **off** (lesson a) → 0
  - Total = **258**
- Sidecar: 10-field JSON sample schema (ASLRecorder2).

Both pose and hands are load-bearing ([lesson b](docs/05-v2-lessons-map.md)) — the v3
contract **keeps every one of these blocks.**

---

## AppHear 3 contract — `schema_version` field is mandatory

Every stored sample and every on-device feature frame carries `schema_version`. Nothing reads
a feature vector without checking it. Versions are additive/explicit; a model is pinned to the
schema version it trained on (`features.schema_version` flag).

### v3.0 — "normalized 258" (Phase 0 baseline)
Same **258 float** layout as v2, but the floats are **post-normalization** (N1 scale, N2 roll,
N3 handedness from [doc 02](docs/02-data-pipeline.md)) instead of raw. Chosen as v3.0 so we
can **isolate the effect of normalization alone** against v2's raw-258 numbers, holding the
layout constant. This is the ablation that proves the pipeline redesign earns its keep.

| Block | Dims | Notes |
|-------|------|-------|
| Hands | 126 | `2 × 21 × 3`, normalized coords |
| Pose | 132 | `33 × 4`, normalized coords + visibility |
| **Total** | **258** | identical layout to v2, normalized values |

### v3.1 — "kinematic" (adds derived motion channels)
Adds per-landmark **velocity** (and optionally acceleration) — first differences of the
normalized coordinates over normalized time. Rationale: sign identity lives in *motion*, and
handing the model velocity explicitly (rather than making it re-derive differences through the
receptive field) is cheap and helps short signs. Also carries the **native span duration** as
a scalar side feature (so even the duration-resampled Phase-0 path isn't fully speed-blind —
see [doc 02 §N4](docs/02-data-pipeline.md)).

| Block | Dims | Notes |
|-------|------|-------|
| Position (as v3.0) | 258 | normalized coords |
| Hand velocity | 126 | Δ of hand coords |
| Pose velocity | 99 | Δ of pose x,y,z (visibility not differenced) |
| Duration scalar | 1 | native span length (pre-resample) |
| **Total** | **484** | superset of v3.0 |

**Tradeoff:** v3.1 nearly doubles input width → more compute per frame (competes with the
S1/S2 budget, [lesson a](docs/05-v2-lessons-map.md)) and more room to overfit noise. So v3.1
ships **only if** it beats v3.0 on the **cross-signer** end-to-end metric by enough to justify
the cost — decided by ablation, not assumption. v3.0 stays the safe default.

---

## Missing-data convention (explicit, versioned)

Landmarker dropouts are normal on a budget SoC. The contract defines exactly one behaviour so
offline and online agree:
- Missing hand/pose landmark coordinates → filled by [S3 tracking](docs/01-system-architecture.md)
  gap-fill where possible; if still missing, written as a **sentinel** with the corresponding
  **visibility/presence set to 0**, never as a bare 0 that looks like the origin.
- Quality gate ([doc 02 §Q](docs/02-data-pipeline.md)) rejects samples that exceed the
  missing-data budget, so the model rarely trains on sentinels — but the convention is fixed
  so it *can't* be interpreted two different ways.

---

## Storage schema (ASLRecorder2 lineage)

The per-sample JSON sidecar (v2's 10-field schema) is carried forward and versioned alongside.
Required fields (superset, explicit):

| Field | Purpose |
|-------|---------|
| `schema_version` | pin features + parsing |
| `gloss` | label |
| `signer_id` | **required** — signer-level splits depend on it ([lesson c](docs/05-v2-lessons-map.md)) |
| `source` | `asl_citizen` \| `aslrecorder2` |
| `native_fps` | quality gate + duration handling |
| `span` | trimmed `[onset, release]` (frames) after [D2](docs/02-data-pipeline.md) |
| `normalization` | which N-stages applied + their params (scale ref, roll angle, mirrored?) |
| `quality` | gate outcomes + coverage/confidence stats |
| `dominant_hand` | from [N3](docs/02-data-pipeline.md); `mirrored` flag |
| `mirror_exempt` | true for handedness-lexical glosses ([doc 02 §N3](docs/02-data-pipeline.md)) |

Recording `normalization` params per sample is what lets us **reproduce or invert** any
normalization later and guarantees the on-device S4 can apply the identical transform — the
train/serve-skew guard ([S4](docs/01-system-architecture.md)).

---

## Contract rules (non-negotiable)

1. No code reads features without checking `schema_version`.
2. Offline extraction (F) and on-device extraction (S4) share **one implementation** of the
   normalization + feature math (or a byte-exact port with a skew test).
3. Adding channels = a **new version**, never a silent reshape.
4. A model records the exact `schema_version` it was trained on; the runtime refuses to load a
   model against a mismatched contract.
