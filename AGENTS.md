# AppHear 3 â€” Agent Operating Guide

AppHear 3 is a **re-architecture** (not a retrain) of a real-time, on-device ASL
recognition system: an **Android runtime** (Kotlin + CameraX + MediaPipe Tasks + TFLite) fed
by an **offline training/data pipeline** (Python + TensorFlow/Keras). Recognition is one
stage of nine. The system metric is **end-to-end signed-phrase accuracy, cross-signer, under
streaming conditions** â€” never per-window accuracy on a training signer.

---

## Read Before Anything Else

Read in this exact order before any implementation. Do not skip. Confirm once read.

1. `context/project-overview.md` â€” what we're building, scope, the four anchor numbers
2. `context/architecture.md` â€” stack, folder structure, boundaries, data flow
3. `context/runtime-constraints.md` â€” the fixed on-device numbers no code may violate
4. `context/eval-protocol.md` â€” how every claim is measured (cross-signer, end-to-end)
5. `context/feature-schema.md` â€” the versioned feature contract (living document)
6. `context/code-standards.md` â€” Python + Kotlin conventions, train/serve parity
7. `context/library-docs.md` â€” project-specific usage of MediaPipe, TFLite, Keras, CameraX
8. `context/build-plan.md` â€” phased build order, feature by feature
9. `context/progress-tracker.md` â€” where we are, decisions made, what's next
10. `context/recognition-accuracy.md` â€” why on-device detection is hard (the fps/temporal
    train-serve mismatch) + the accuracy levers; the plan has no dedicated accuracy feature
11. `context/device-smoke.md` â€” the repeatable developer-run device validation + rollback
    checklist (F22); run on every build that changes the runtime
12. `context/encoder-upgrade.md` â€” the PLANNED S6 encoder-swap experiment (ST-GCN / small
    transformer): verified evidence, frozen I/O contract, gates, and the revert procedure.
    Read BEFORE any accuracy/model work so the plan isn't re-derived or hallucinated
13. `context/recorder-pipeline.md` â€” the rebuilt ASL Recorder (`asl recorder/`) â†’ pipeline data
    path (video-primary Stage-E capture, `pipeline.ingest` merge/replace). Read before touching
    the recorder or ingesting secondary/local-signer data
14. `context/react-native-prototype.md` - the PLANNED separate React Native / iPhone experiment
    under `apphear-react/`: scope, non-goals, native-vs-RN boundaries, phases, benchmark gates,
    and fallback plan. Read before touching `apphear-react/` or proposing iOS/RN work

15. `context/android-app-redesign.md` - the native Android full-application redesign entry point:
    verified AppHear3/AppHear2 inventory, screen mapping, target UI/navigation boundaries, design
    system, phased migration gates, testing, and rollback. Read it and its linked Android documents
    before changing Android UI, navigation, app-shell resources, or migrating AppHear2 features
Deeper design rationale (the Â§8 deliverables) lives in `docs/` and `README.md`. The
`context/` files are the operational contracts; `docs/` explains *why*. If they ever
disagree, `context/` wins and you flag the drift.

---

## Rules That Never Change

- **All accuracy claims are cross-signer, end-to-end, on held-out signers.** Never report or
  optimize per-window accuracy on a training signer. (v2 lesson c, f)
- **Never drop pose or hand feature blocks to save compute.** Feature reduction is not a
  latency lever. Cadence/subsampling is the only allowed pose-side lever, and only A/B-gated.
  (v2 lesson b)
- **Offline feature math (pipeline stage F) and on-device feature math (runtime stage S4)
  must be byte-for-byte equivalent.** Train/serve skew is banned; any divergence needs an
  explicit skew test. (S4)
- **Every change ships behind a feature flag and passes an offline eval gate before device
  rollout.** No exceptions. (Â§7 discipline)
- **Never read a feature vector without checking `schema_version`.** A model refuses to load
  against a mismatched contract. (feature-schema.md)
- **No GPU delegate is assumed.** CPU / XNNPACK / INT8 is the baseline. Any GPU work is
  flagged, off-main-thread, and device-measured first. (v2 lesson g)
- **Model loading is async, off the critical path.** (v2 lesson h)
- **Update `progress-tracker.md` after every completed feature.** Update
  `feature-schema.md` whenever the feature contract changes.
- **Before using any third-party library** â€” load its installed skill first, then read
  `context/library-docs.md` for project-specific rules.
- **If the same problem persists after one corrective prompt â€” stop immediately and run
  `/recover`.**
- **Never touch the AppHear v2 project** (`../AppHear`). It is reference only, and only if
  explicitly authorized.

---

## Available Skills

Adapted from the JS-Mastery Context System to AppHear 3. Defined in `.claude/skills/<name>/SKILL.md`.

- `/architect` â€” before any complex feature (a data-pipeline stage, the model, the
  confirmation policy). Reads context, surfaces undecided questions one at a time, produces a
  plan you confirm before any code.
- `/imprint` â€” after changing the feature contract or any reusable pipeline/runtime
  component. Captures the pattern into `feature-schema.md` (and the component registry) and
  flags inconsistencies. *(Adapted from UI-registry imprint â†’ feature/contract imprint.)*
- `/review` â€” after a feature is built. Checks plan alignment, architecture-boundary +
  eval-protocol compliance, and production readiness. Reports by severity
  (critical / important / minor). Never auto-fixes.
- `/recover` â€” when something breaks after one failed correction. Diagnoses the failure mode
  (isolated bug / session degradation / architectural misalignment) before responding.
- `/remember save` â€” at the end of a session. `/remember restore` â€” at the start.
  Persists decisions, state, and next action to project memory so nothing is re-explained.

---

## The Loop

1. Start of session â†’ `/remember restore`, then read AGENTS.md order and confirm.
2. Before a complex feature â†’ `/architect`.
3. Implement one feature fully. Validate offline (eval gate) before any device step.
4. After a contract/component change â†’ `/imprint`. After a complex feature â†’ `/review`.
5. When stuck after one failed fix â†’ `/recover`.
6. End of session â†’ `/remember save`.

