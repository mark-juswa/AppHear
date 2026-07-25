---
name: recover
description: When something goes wrong during an AppHear 3 build, diagnose which type of failure it is before deciding how to respond. Run when a problem persists after one corrective prompt. The worst move when something is broken is to keep doing the same thing faster.
---

Something is broken and one corrective attempt has already failed. Before trying anything
else, diagnose **which failure mode** you are in — the right response differs completely
between them.

## Step 1 — Describe the problem precisely

Get specifics: what was expected, what happened, the exact error or wrong output, how many
fix attempts so far, and which stage/file (S0–S8 / D1–D2 / N1–N4 / Q / F / model / eval).
Vague symptoms lead to the wrong recovery.

## Step 2 — Identify the failure mode, then respond

### Mode 1 — Specific component broken
**Signs:** isolated, first/second fix attempt, a clear error message.
Examples here: a MediaPipe config mismatch, a NumPy shape error in a normalization stage, a
TFLite converter op error, a bad threshold in `config/`.
**Response — targeted fix:** find the root cause precisely, propose one surgical change,
verify it before applying. Do not broaden scope.

### Mode 2 — Session degradation
**Signs:** many failed attempts, code getting tangled, the original issue is now unclear,
changes are piling on changes.
**Response — hard reset:** stop. Extract the lessons into a short reset note (what was tried,
what to avoid), then **end the session and start fresh** rather than compound the damage. Use
`/remember save` to preserve the note. Starting clean beats debugging a mess.

### Mode 3 — Architectural misalignment
**Signs:** the code runs but does the *wrong thing* — a core assumption was wrong.
Examples here: numbers look great but the eval was single-signer or per-window (not
cross-signer end-to-end — the exact v2 trap); `android/features` silently diverged from
`pipeline/features` (train/serve skew); confirmation "works" because it commits everything;
a fixed window crept back in.
**Response — rethink:** name the faulty assumption, check it against
`context/eval-protocol.md` / `runtime-constraints.md` / `feature-schema.md`, propose the
correct approach, and get the developer's agreement **before** rebuilding. No amount of
faster iteration fixes a wrong assumption.

## Core principle

Accurate diagnosis decides whether you need precision (Mode 1), a restart (Mode 2), or a
strategic rethink (Mode 3). Do not keep repeating a failing approach faster.
