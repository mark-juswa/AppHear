# 02 — Data Pipeline

*Deliverable §8.2: the end-to-end data pipeline, with a concrete method for each
normalization / gating stage in §4 (signing-detection, dead-time trimming, scale /
orientation / handedness / duration normalization, and the quality gate).*

---

## Why the pipeline *is* the work

v2's data path was effectively `video → extract landmarks → 30 frames → train`. That bakes
in every distributional inconsistency: variable framing, signer scale, orientation,
handedness, duration, and dead time. The model then spends capacity absorbing noise instead
of meaning, and it "works for me" but not cross-signer ([lesson c](docs/05-v2-lessons-map.md)).

**Goal:** every sample entering the model has ≈ the same statistical distribution — same
framing, scale, orientation, handedness convention, temporal length, and a quality floor.
Each stage below maps directly to a v2 failure mode; none is speculative.

```
video (ASL Citizen clip, or ASLRecorder2 capture)
  ↓ E   extract landmarks        (MediaPipe hand + pose, face off)
  ↓ D1  detect signing           (find the real span)
  ↓ D2  trim dead time           (onset → release only)
  ↓ N1  normalize scale          (body-size / distance invariant)
  ↓ N2  normalize orientation    (roll/yaw canonical)
  ↓ N3  normalize handedness     (mirror to a single convention)
  ↓ N4  normalize duration       (resample to common length — isolated path only)
  ↓ Q   quality check            (reject low-coverage / low-confidence)
  ↓ F   feature extraction       (→ versioned contract, doc 06)
  ↓     training / eval
```

> **The offline↔online mirror.** Stages N1–N3 and F run **identically** at runtime in
> [S4](docs/01-system-architecture.md). N4 (duration resample) and D1/D2 (span finding) are
> handled differently online: at runtime the [S5 gating stage](docs/01-system-architecture.md)
> does span detection live, and the streaming model handles duration without resampling
> (see doc 03). Any math that differs between offline and online is train/serve skew and is
> banned unless explicitly justified and tested.

---

## E — Landmark extraction

- MediaPipe Tasks **hand** landmarker (2 hands) + **pose** landmarker. Face **off**
  ([lesson a](docs/05-v2-lessons-map.md)).
- Output per frame: hands `2 × 21 × 3`, pose `33 × {x,y,z,visibility}`, plus per-landmark
  presence/visibility scores (carried forward — the quality gate needs them).
- Extract at the **video's native frame rate** offline (we are not fps-bound here), so we
  have maximum temporal resolution to resample *down* from. This is the one place we get
  frames the on-device runtime cannot.

---

## D1 — Signing detection (find the real span)

**Problem:** ASL Citizen clips are isolated citation form but still contain lead-in
(hand rising into frame) and lead-out (hand dropping). ASLRecorder2 captures have rest
padding. Idle frames must not enter the model.

**Mechanism — motion-energy + spatial gate with hysteresis:**
1. Compute per-frame **hand motion energy** `m[t]` = mean speed of wrist + fingertip
   landmarks between consecutive frames, in **body-normalized units** (divide by shoulder
   width, so it's distance-invariant *before* thresholding).
2. Compute a **signing-space gate** `g[t]` = are the hands within the plausible signing
   volume (roughly: above the hips, within ~1.5 shoulder-widths of torso centre)?
3. Two-state label with **hysteresis** to prevent chatter:
   - idle → signing when `m[t] > θ_on` **and** `g[t]` for `≥ k_on` consecutive frames,
   - signing → idle when `m[t] < θ_off` (`θ_off < θ_on`) for `≥ k_off` frames.

Thresholds `θ_on, θ_off, k_on, k_off` are **fit on a labelled subset** (a few hundred clips
with hand-annotated onset/release) by maximizing span IoU, not hand-picked.

**Tradeoff:** motion-energy gating can clip the *hold* of a low-motion sign (a static
handshape held still). Mitigation: once in the `signing` state, the spatial gate `g[t]`
alone keeps it alive even if motion drops — motion is required to *enter*, presence to
*stay*.

---

## D2 — Dead-time trimming (onset → release)

Given the D1 signing state, the active span is `[onset, release]`:
- **onset** = first frame of the signing run (optionally back off `−δ` frames to catch the
  very start of the movement, which precedes the threshold crossing),
- **release** = last frame before the fall to idle (`+δ` forward similarly).
- Enforce a **minimum span length**; spans shorter than the shortest real sign
  (~170 ms → at native fps a floor of e.g. 5 frames) are flagged for the quality gate, not
  silently kept.

**Why (anchor #3):** v2's window was ~4× a sign, so ~75% non-sign. Trimming to onset→release
is the single biggest distribution fix — it removes the transition/rest frames that the
model was otherwise forced to learn around.

---

## N1 — Scale normalization (distance / body-size invariant)

**Reference length = shoulder width** `s = ‖pose[L_shoulder] − pose[R_shoulder]‖`
(robust, present in nearly every frame, and directly proportional to apparent signer size /
camera distance). Fallbacks if a shoulder is occluded: torso diagonal (shoulder↔opposite
hip), then a running median of `s` over the span.

For every landmark `p`:
```
p_norm = (p − origin) / s
```
where `origin` = torso centre (midpoint of shoulders, or shoulder/hip centroid).

**Effect:** a signer 1 m from the camera and one 3 m away, or a child and an adult, produce
the same normalized coordinates. Directly attacks the signer-scale variance in
[lesson c](docs/05-v2-lessons-map.md).

**Tradeoff:** dividing by a per-frame `s` injects noise if `s` itself is jittery → use the
**span-median `s`** (one scalar per clip) rather than per-frame, since the signer's size
doesn't change within a clip. At runtime, use a slow running median.

---

## N2 — Orientation normalization

**Roll (in-plane rotation) — fully correctable from 2D:** compute the shoulder-line angle
`φ = atan2(Δy, Δx)` of the shoulder vector and rotate *all* landmarks by `−φ` about the
origin, so the shoulder line is horizontal. Removes camera-tilt and lean.

**Yaw (turned torso) — partially correctable, needs 3D:** use MediaPipe pose **world
landmarks** (metric 3D) to estimate torso yaw and de-rotate about the vertical axis.

**Tradeoff:** 2D image landmarks alone cannot recover yaw; world-landmark yaw correction is
noisier than roll. Ship **roll correction as default-on** (cheap, reliable) and **yaw as a
flagged experiment** (`normalize.yaw`), A/B'd on the cross-signer set before it's trusted —
because a bad yaw estimate is worse than none.

---

## N3 — Handedness normalization (mirror to one convention)

**Convention:** canonicalize every sample to a single dominant-hand convention (e.g. "as if
right-handed").

1. **Detect the dominant hand** over the span = the hand carrying more accumulated motion
   energy during the active sign (for one-handed signs it's obvious; for two-handed signs
   the dominant/active hand still dominates motion in most lexicon signs).
2. If the signer is left-dominant, **mirror the entire body** across the vertical axis
   (`x → −x` after centring, and swap L/R landmark indices for both hands and pose).
   Mirroring *everything* keeps two-handed spatial relationships intact.

**Effect:** left- and right-handed signers collapse onto one distribution instead of the
model needing to learn both — a real cross-signer variance source.

**Tradeoffs (named):**
- A handful of signs are **handedness-lexical** (the choice of hand or asymmetry carries
  meaning) — for those, mirroring is information-destroying. These are rare in ASL Citizen's
  vocabulary; flag them per-gloss in a `mirror_exempt` list rather than blanket-mirroring.
- Dominant-hand detection can be wrong on symmetric two-handed signs (both hands move
  equally). Mitigation: for near-symmetric motion, skip mirroring (it's a no-op either way)
  and fall back to a stable rule (e.g. right-hand-as-dominant).

---

## N4 — Duration normalization (resample to common length)

**Isolated-recognition path only** (Phase 0 of doc 03). Resample the trimmed span's landmark
trajectories to a fixed length `T` by **per-landmark cubic (or linear) interpolation over
normalized time**:
```
for each landmark channel c:  x_c'(i) = interp(x_c, t_i)   for i in 0..T-1
```
This lets a single model see FOUR (~4 native frames) and a slow two-handed sign at the same
tensor length (anchor #4 / brief §4).

**Tradeoff — this destroys absolute speed:** two signs that differ only by tempo become
identical after resampling. For **isolated citation-form recognition** that's a *feature*
(robustness to signing speed). For **streaming / CTC** (doc 03) it's *wrong* — speed and
order carry meaning and the model must observe real timing. Therefore:
- **Phase 0 (isolated classifier):** N4 on, `T` fixed.
- **Phase 1+ (streaming / CTC):** **N4 off** — feed real-timed sequences; the model learns
  duration. This is the explicit fork in the pipeline.

Optionally retain the pre-resample native duration as a **scalar side feature** so even the
isolated model isn't fully speed-blind.

---

## Q — Quality gate

Reject samples that would teach the model noise. Concrete, individually-logged gates:

| Gate | Reject if | Rationale |
|------|-----------|-----------|
| Coverage | > X% of span frames missing a required hand | occlusion / out-of-frame |
| Confidence | mean landmark presence/visibility < θ_conf | unreliable detections |
| Span length | trimmed span < min real-sign length | D2 mis-fire / partial sign |
| Dominant-hand presence | active hand absent for > Y consecutive frames | mid-sign dropout |
| Frame-rate (capture source) | source clip fps below resolution floor for short glosses | can't resolve the sign |

Rejections are **counted per-gloss and per-signer**, because a gloss or signer that gets
disproportionately rejected is itself a finding (e.g. a sign that leaves signing-space, or a
signer the landmarker struggles with). The gate produces a *dataset health report*, not just
a filtered set.

**Tradeoff:** an aggressive gate improves per-sample quality but can bias the vocabulary
(drop hard-but-valid signs) and shrink signer diversity — the exact thing ASL Citizen was
chosen to provide ([brief §3](../README.md)). So gate thresholds are tuned to protect
**signer coverage** first; a gloss losing too many signers triggers review, not silent drop.

---

## F — Feature extraction

Emits the versioned per-frame feature vector defined in
[doc 06 — Feature/Schema Contract](docs/06-feature-schema-contract.md). Because N1–N3 already
ran, F operates on normalized landmarks and may additionally compute **derived kinematic
channels** (velocities/accelerations) — decided and versioned in doc 06, not here.

---

## Datasets & split discipline

- **Primary corpus: ASL Citizen** — largest, most signer-diverse; signer diversity is
  exactly where v2 broke ([lesson c](docs/05-v2-lessons-map.md)).
- **ASLRecorder2** — custom / targeted / schema-controlled captures (258-float / 10-field
  JSON), used for gap-filling vocabulary and for on-device-matched captures.
- **Splits are by signer, not by clip.** All eval is on **held-out signers** the model never
  saw. A clip-level split would leak signer identity and reproduce v2's flattering
  single-signer numbers ([lessons c, f](docs/05-v2-lessons-map.md)). This is non-negotiable
  and enforced in the split tooling, not by convention.
