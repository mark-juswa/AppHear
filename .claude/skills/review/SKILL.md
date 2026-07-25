---
name: review
description: After building an AppHear 3 feature, verify it matches what was planned, respects the architecture boundaries and evaluation protocol, and is ready to pass the offline eval gate. Reports issues by severity (critical / important / minor). Never auto-fixes — you decide what matters.
---

You are reviewing a just-built AppHear 3 feature. You report what you find; you do not fix it.
The developer owns quality decisions. Read the relevant `context/` files first, then review
across three layers.

## Layer 1 — Plan alignment

Compare the implementation against the plan (from `/architect`) and its `build-plan.md` entry.
- Does it do everything the feature required — no missing pieces?
- Did it stay in scope — no unplanned stages, no scope creep?
- If it touched the feature contract, was `schema_version` bumped and `/imprint` run?

## Layer 2 — System integrity

Check against the project's own laws:
- **Architecture boundaries** (`architecture.md`): pipeline/model/eval/android boundaries
  respected; `android/features` (S4) still a faithful port of `pipeline/features` (F);
  thresholds in `config/`, not inline; no face landmarker; splits by `signer_id`.
- **Runtime constraints** (`runtime-constraints.md`): no pose/hand feature block dropped; no
  fixed multi-second window; nothing blocks the main thread; CPU/INT8 (no GPU delegate);
  ≥15 fps floor respected.
- **Eval protocol** (`eval-protocol.md`): any accuracy claim is cross-signer + end-to-end +
  held-out; per-window numbers labelled diagnostic; latency reported p50 **and** p95;
  confirmation changes tuned on the operating curve, correct-but-dropped tracked.
- **Code standards** (`code-standards.md`): typing, determinism/seeds, naming, error prefixes,
  no magic numbers, no TODOs.

## Layer 3 — Production / eval-gate readiness

- Is there a **feature flag with a documented fallback**?
- Does it pass (or is it wired to pass) the **offline cross-signer eval gate** before any
  device step?
- For contract/feature work: does the **train/serve skew test** pass?
- For runtime work: is model load async? is per-frame latency measured?
- Edge cases: missing landmarks handled per the missing-data convention? empty/idle spans?
  degraded-mode path?

## Severity classification

- **Critical** — architecture-boundary violation, silent failure, a per-window number
  presented as headline, S4↔F divergence / train/serve skew, GPU delegate or main-thread
  block, missing planned functionality.
- **Important** — eval-protocol drift, code-standard violations, an unflagged behavioral
  change, an untuned confirmation threshold, unhandled edge case.
- **Minor** — naming, missing p95, small optimization gaps, style.

## Report

Produce a formatted report: pass/fail per layer, the specific issues under each severity, a
total count, and a clear recommendation (ship / fix-then-ship / rework). **Do not fix
anything** — report and let the developer decide what matters.
