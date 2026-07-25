---
name: imprint
description: After changing the feature contract or building a reusable pipeline/runtime component, capture the pattern into context/feature-schema.md so future work matches it instead of drifting. The AppHear 3 analogue of UI-registry imprint — here the "design system" is the versioned feature contract and the shared normalization/stage components. Also runs in audit mode to find train/serve skew and duplicated implementations.
---

UI consistency does not happen by accident; neither does feature-contract consistency. In
AppHear 3 the thing that must stay coherent across sessions is the **versioned feature
contract** and the **reusable components** (normalization stages, the shared TCN encoder,
stage interfaces). This skill keeps `context/feature-schema.md` the single source of truth.

## Step 1 — Identify what changed

Read recently modified files (or take a given path). Determine whether the change touched:
- the **feature contract** (channels, dims, `schema_version`, missing-data convention,
  sidecar fields), or
- a **reusable component** (a normalization stage N1–N4, D1/D2, Q, F, the encoder, a stage
  interface). Ask if it's unclear which.

## Step 2 — Extract the contract-relevant facts

Capture only what future work must match — not incidental detail:
- For a **contract** change: the new/updated `schema_version`, block layout + dims, the
  reason it's a new version, and which models are pinned to it.
- For a **component**: name, path, purpose, inputs → outputs, the config keys/thresholds it
  reads, and the `schema_version` it targets.
- **Parity note:** if the component exists on both sides (`pipeline/features` F and
  `android/features` S4), record that both were updated and the skew test re-run.

Exclude tuning noise, one-off experiment values, and anything already obvious from the code.

## Step 3 — Document to feature-schema.md

Update `context/feature-schema.md`:
- New contract version → add/adjust its version section; mark the current version clearly.
- Component → append/update its entry in the **Component Registry** section (name, path,
  purpose, I/O, targeted version).
Match the existing table/section style exactly.

## Step 4 — Confirm and flag

Report what was documented and flag any inconsistency you noticed, especially:
- a feature vector read somewhere **without** a `schema_version` check,
- a model pinned to a version that no longer matches,
- two implementations of the same normalization (drift risk),
- a component whose I/O contradicts an existing registry entry.

## Audit mode (`/imprint audit`)

When contract/parity coherence is uncertain, scan the whole project to establish a baseline:

1. **Scan** `pipeline/features`, `android/features`, `model/`, and every normalization stage.
2. **Identify conflicts** — layout/version mismatches, S4↔F divergence (train/serve skew),
   duplicated or contradictory normalization math, unchecked `schema_version` reads.
3. **Present recommendations** without changing anything.
4. On approval, **write the confirmed baseline** into `feature-schema.md`.
5. **List the components/files** that deviate and need fixing (hand off to `/review` or a
   normal fix — imprint never edits implementation code, only the registry doc).

Never invent a new contract version to paper over drift — surface the drift and let the
developer decide.
