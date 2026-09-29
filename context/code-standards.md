# Code Standards

Implementation rules for the whole project — Python (offline) and Kotlin (runtime). Follow
these every session without exception; they prevent pattern drift.

---

## Engineering Mindset

- **Think before implementing.** Read the context files; never assume. Use `/architect` for
  anything complex.
- **The system, not the model.** Recognition is one stage of nine. A change is only "done"
  when its stage metric AND the end-to-end metric are measured (see [`eval-protocol.md`](eval-protocol.md)).
- **Scope is sacred.** Build only what the current feature requires.
- **Reproducibility over cleverness.** Seed everything; a run must be repeatable.
- **One feature at a time.** Complete and validate offline before the next.
- **Failures are expected.** Landmarker dropouts and missing data are normal — handle them
  per the missing-data convention, never crash the pipeline.

---

## Python (offline pipeline, model, eval)

- Python **3.11+**, type hints on every function signature (params + return). Run `mypy` clean.
- Format with **black**; lint with **ruff**. No unused imports, no dead code.
- **Determinism:** set and log seeds (`random`, `numpy`, `tf`) at every entrypoint. Any
  nondeterministic op is flagged and justified.
- **No magic numbers.** Every threshold (θ_on, θ_off, min-span, quality floors, operating
  points, `T`) lives in `pipeline/config/` or `model/config/` — never inline.
- **Pure transforms.** Pipeline stages are pure functions `landmarks → landmarks/features`
  with no hidden I/O; caching is explicit.
- **NumPy vectorized**, not Python loops, on the per-frame hot path.
- Each stage emits a small **stats record** (counts, rejection reasons) for the dataset-health
  report — never silently drop samples.
- Never fetch data at import time. Data paths come from config.

## Kotlin (Android runtime)

- Kotlin, coroutines for async. **Model load and inference never block the main thread**
  (v2 lessons g, h).
- **One folder per stage** (`capture/`, `landmark/`, … `sentence/`); a stage exposes an
  interface + a feature flag + a fallback.
- **No hardcoded thresholds** — operating points and gates load from a config asset shipped
  with the model artifact (same values as offline).
- `android/features` (S4) is a **verified port** of `pipeline/features` (F). Any change to one
  requires updating the other + re-running the skew test. This is the single most important
  Kotlin rule.
- Explicit nullability; landmarker dropouts modeled as absent, not zero.
- Report per-frame latency as **p50 + p95**.

---

## Feature-Flag & Eval-Gate Discipline (project-wide)

- Every behavioral change ships behind a flag with a documented fallback.
- **flag → offline eval → device smoke test → rollout / rollback.** Nothing skips the gate.
- Ablation is a supported mode: toggling any stage flag must leave the system runnable.

---

## Naming & Structure

- Python files/modules: `snake_case` (`normalize_scale.py`, `signer_split.py`).
- Python classes: `PascalCase`; functions/vars: `snake_case`; constants: `UPPER_SNAKE`.
- Kotlin files/classes: `PascalCase` (`HandLandmarkerSource.kt`); functions/vars: `camelCase`.
- Stage code references stages by their canonical id (S0–S8, D1/D2, N1–N4, Q, F).
- One responsibility per file. No barrel/god modules.

---

## Error Handling

- No empty catches. Log with a context prefix: `[normalize/scale]`, `[android/recognition]`.
- User-facing errors are human-readable; raw errors never surface to the UI.
- Pipeline stage failures are logged to the dataset-health report and the sample is quarantined,
  never silently kept or crashed on.

---

## Comments

- Comment the **why** (a non-obvious threshold, a v2-lesson-driven choice), never the what.
- No `TODO`s in committed code — track work in [`build-plan.md`](build-plan.md) /
  [`progress-tracker.md`](progress-tracker.md).

---

## Dependencies

Before adding a package, check: does TF/Keras, NumPy, MediaPipe, or the Android SDK already
provide it? Approved core set:

- Python: `tensorflow`, `numpy`, `mediapipe`, `opencv-python` (I/O only), `pytest`,
  `black`, `ruff`, `mypy`.
- Android: `mediapipe-tasks-vision`, TFLite runtime, CameraX, Kotlin coroutines.

Adding anything else requires updating this list first and a one-line justification.

Offline Text-to-ASL asset pilot only (2026-09-28): `@gltf-transform/core`,
`@gltf-transform/extensions`, `@gltf-transform/functions`, `sharp`, `meshoptimizer`, and
`gltf-validator` are permitted in a separate generated tools package to create validated
optimized GLB derivatives locally. They are not app or recognition-pipeline dependencies.
