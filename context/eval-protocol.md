# Evaluation Protocol

*(This file occupies the `ui-rules.md` slot in the Context System convention. For a web app
that slot defines how the UI must behave to feel like one product. For AppHear 3 it defines
how the system must be **measured** to be trusted — because the whole project exists to close
the gap between flattering numbers and real performance.)*

Deep rationale: [`../docs/05-v2-lessons-map.md`](../docs/05-v2-lessons-map.md),
[`../docs/04-confirmation-and-sentence-builder.md`](../docs/04-confirmation-and-sentence-builder.md).

---

## The One Rule

**Every accuracy claim is cross-signer, end-to-end, on held-out signers.** No exceptions.

- **Cross-signer** — evaluated on signers the model never saw. Single-signer numbers are
  banned as a headline (v2 lesson c: single-signer looked fine, cross-signer broke).
- **End-to-end** — the top-line metric is signed-phrase accuracy out of S8, not per-window
  recognition accuracy out of S6 (v2 lesson f: per-window overstates real performance).
- **Held-out** — splits are by `signer_id`, enforced in the split tooling, never by clip.

---

## Split Discipline

- Partition signers into train / val / test. **A signer appears in exactly one split.**
- Val is used for calibration + operating-point selection; test is touched only for final
  reporting.
- Report per-signer, not just aggregate — a low mean hiding one collapsed signer is a finding.

---

## Metric Per Stage

Every stage has its own metric so it can be ablated independently (via its feature flag) and
the end-to-end number re-measured.

| Stage | Metric | Notes |
|-------|--------|-------|
| S0 Capture | sustained fps + jitter | hard floor ≥ 15 fps |
| S1/S2 Landmarkers | latency (ms), detection-hit rate | ~70% of frame budget |
| S3 Tracking | identity-swap rate; noise-vs-lag | |
| S4 Features | **train/serve skew ≈ 0** | correctness, not accuracy |
| S5 Gating | signing-detection P/R; compute saved vs missed-sign | |
| S6 Recognition | cross-signer per-emission accuracy **+ calibration** | diagnostic only |
| S7 Confirmation | correct-commit rate @ fixed FP rate; **correct-but-dropped rate** | operating curve |
| **S8 Sentence** | **end-to-end phrase accuracy (WER/gloss-error)** | **top-line metric** |

---

## Confirmation Evaluation (so the v2 leak can't recur)

v2 dropped ~50% of *correct* signs as "none" because a single threshold was picked on
training-signer data. Required protocol (see [`../docs/04`](../docs/04-confirmation-and-sentence-builder.md)):

1. **Calibrate** posteriors (temperature scaling) on held-out val — report reliability / ECE.
2. **Sweep the operating curve** on held-out signers: x = false-positive commit rate,
   y = correct-commit rate, and separately track the **correct-but-dropped** rate.
3. **Choose the operating point** that maximizes correct-commit at the target FP rate — never
   hand-pick a threshold constant. It lives in `config/` as `confirm.operating_point`.

---

## The Offline Eval Gate (v2 discipline)

Every change follows: **flag → offline eval → device smoke test → rollout / rollback.**

- Nothing reaches the device until it passes the offline cross-signer eval gate.
- Changes ship behind feature flags with rollback.
- Ablation is a first-class workflow: toggle a stage's flag, re-run end-to-end eval, compare.

---

## Reporting Rules

- Always report the **end-to-end** number alongside (never instead-of by) any per-stage number.
- Latency is reported as **p50 and p95**, never mean.
- A per-window/per-emission number is always labelled *diagnostic*, never headline.
- Phase 0's isolated-classifier accuracy is explicitly labelled the *flattering regime whose
  job is to validate plumbing* — not the product.

## 2026-09-04 — P5–P7 evidence and population-specific boundaries

[Consolidated evidence](recognition_upgrade/PROGRESS_THROUGH_P7FA_2026_09_04.md) distinguishes offline recognition, semantic parity, runtime
feasibility and supervision adequacy; none substitutes for end-to-end held-out product accuracy.
The current governed recognition evidence concerns isolated/pause-separated signs, not proven
continuous ASL or phrase recognition. D1 representation sufficiency is unproven; D11 confidence
remains MODERATE with NLL/per-frame/Top5 and five-signer uncertainty caveats.

For the Family-A supervision program, the specific current governance takes precedence over
generic validation guidance above: ASL Citizen VAL is EVALUATION_ONLY, not training/threshold
fitting. D10 canonical TEST is development-exposed SECONDARY_CONFIRMATION_ONLY and protected
from further development. Protected replay and pristine data remain excluded.

Teacher structural validity is not physical visibility; teacher slot names are not correct
anatomical assignment labels; teacher scores are not calibrated Family-A targets. P7F-A
geometry readiness is pseudo-supervision design support, not training or accuracy authorization.
No thresholds, loss choices, calibration, protected-data access or new evaluation occurs here.
