# 05 — v2 Lessons → Design Decisions Map

*Deliverable §8.5: flag every place a v2 lesson (brief §6) forces a specific AppHear 3
design decision, so nothing is rediscovered the hard way.*

Each lesson was **measured on-device or via offline ablation** in v2 — treat as ground
truth, design around it, do not re-derive.

---

## a — Latency is compute-bound and hardware-floored

> ~70% of every frame's time is the hand + pose landmarker models. Parallelizing pose+hands
> and disabling face got 4.37 → 8.10 fps (+85%) — roughly the software ceiling.

**Forces:**
- [S1/S2](docs/01-system-architecture.md): landmarkers run in parallel; **face off**;
  landmarker backend is **swappable** (`landmarker.backend`) because it *is* the floor.
- No "optimize the code" performance plan anywhere in the project. Levers are lighter models,
  asymmetric **pose cadence** (`pose.cadence`), or different hardware — all named explicitly.
- [S0](docs/01-system-architecture.md): a **≥15 fps floor** is a hard requirement, and the
  app reports *degraded mode* rather than pretend when it can't be met.

## b — Pose and hands are both load-bearing

> Ablating pose collapsed accuracy 35–83 points. Feature reduction is not a free latency lever.

**Forces:**
- [Doc 06](docs/06-feature-schema-contract.md): pose stays in the contract; **you may not
  drop feature blocks to save compute.**
- The only pose-side latency idea allowed is **temporal subsampling (cadence), not feature
  removal** — and even that is A/B-gated ([S1/S2](docs/01-system-architecture.md)), because
  this lesson makes pose sacred on the *feature* axis.

## c — Cross-signer generalization is the real test (where v2 broke)

> Single-signer eval looked fine; cross-signer streaming exposed the gap.

**Forces:**
- **Every** metric in every doc is specified cross-signer, held-out.
- [Doc 02](docs/02-data-pipeline.md): **splits are by signer, not clip** — enforced in
  tooling.
- [Doc 02](docs/02-data-pipeline.md): the entire normalization stack (N1 scale, N2
  orientation, N3 handedness) exists specifically to remove cross-signer variance.
- [Brief §3](../README.md): ASL Citizen chosen *because* it maximizes signer diversity.

## d — The temporal window is the dominant remaining latency (~4× the sign)

> 30 frames @ ~8 fps ≈ 3.7 s ≈ 4× a sign. `MIN_FRAMES` can't just be lowered — confidence
> doesn't stabilize before ~frame 15.

**Forces:**
- [S6](docs/01-system-architecture.md) + [Doc 03](docs/03-model-architecture.md): a
  **streaming, incremental** emitter (causal TCN) from day one — the model emits *within* the
  sign's ~1 s lifetime. The sliding-window state machine is **not** rebuilt.
- [Doc 03](docs/03-model-architecture.md) Phase 1: N4 duration-resample turned **off** so the
  model handles real timing and can emit early.
- [Anchor #3](../README.md): this is the quantified justification for dead-time trimming and
  duration normalization, not a nice-to-have.

## e — Recognition can be right while the system is wrong (confirmation leaks)

> v2's confirmation dropped ~50% of *correct* signs as "none" (~42% confirmed).

**Forces the entire [S7 confirmation design](docs/04-confirmation-and-sentence-builder.md):**
- Posterior **calibration** (temperature scaling) on held-out signers.
- **Evidence accumulation** + **margin** + **stability** gate instead of a single threshold.
- Operating point **tuned on the held-out operating curve**, exposed as
  `confirm.operating_point`.
- The **"correct-but-dropped" rate is a tracked, first-class metric** — the exact v2 failure,
  now visible.
- CTC's **blank** symbol (Phase 2) replaces the hand-tuned "none" threshold entirely.

## f — Per-window and end-to-end accuracy diverge; don't trust the flattering one

> Offline per-window numbers overstate real performance.

**Forces:**
- [S8](docs/01-system-architecture.md): **end-to-end phrase-level accuracy is the top-line
  metric**; per-window/per-emission accuracy is diagnostic only.
- [Doc 03](docs/03-model-architecture.md) Phase 0 is explicitly labelled the *flattering
  regime whose job is to validate plumbing*, not to be the product.

## g — Some "obvious" optimizations are traps (validate device assumptions)

> GPU delegate caused an ANR (blocking `createFromOptions` on main thread), removed. CameraX
> rotation offload didn't engage on the device.

**Forces:**
- [Doc 03](docs/03-model-architecture.md): **CPU/XNNPACK INT8 baseline; GPU delegate not
  assumed** — any revisit is flagged, off-main-thread, and device-measured.
- [S0](docs/01-system-architecture.md): capture/rotation behaviour is **measured on the
  device**, not assumed from the API contract.
- Project-wide: the discipline is **flag → offline eval → device smoke test → rollout /
  rollback** (§7), so device-level assumptions are validated before anything is built on
  them.

## h — Startup latency is real and separate

> Model loading cost ~1 s in `onCreate`.

**Forces:**
- [Doc 03](docs/03-model-architecture.md): **async model load off the critical path**; UI
  comes up "warming up" and the recognizer attaches when ready.

---

## One-line summary table

| Lesson | Single most important design decision it forces |
|--------|--------------------------------------------------|
| a | Landmarkers are the floor → swappable backend + fps floor + no "optimize code" plan |
| b | Never drop pose/hand feature blocks; cadence is the only allowed pose lever |
| c | Signer-level splits; whole normalization stack; cross-signer everything |
| d | Streaming causal TCN from day one; kill the 3.7 s window |
| e | Confirmation = calibrated, accumulated, margin-gated, curve-tuned component |
| f | End-to-end phrase accuracy is the metric; per-window is diagnostic |
| g | CPU/INT8 baseline, GPU not assumed; validate on-device before building |
| h | Async model load off the critical path |
