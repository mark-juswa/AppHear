# AppHear team handoff — 2026-10-09 (Asia/Manila)

This is the continuation entry point for groupmates and their coding AI. Read this before historical plans.
The shared review branch is **codex/team-handoff-2026-10-09**. The working application reference is
**apphear-word-fingerspell-context-assist-2026-10-09**, commit
`34f24ab6d7aea8179decb1688a82fc5734f6d370`. The new Original Character extension is commit `5cf2807`.
Main was still `1e215aebd69a173dd198aa5598a89600072d22fe` when inspected; it does not contain the latest app.
Do not start implementation from main until the handoff pull request is reviewed/merged.

## Read in this order

1. [Verified current state and boundaries](context/team-current-state-2026-10-09.md).
2. [Setup/build/validation/workflow](docs/team-setup-and-workflow.md).
3. [Findings, decisions, limitations and next work](docs/team-research-findings.md).
4. [External artifacts and transfer limitations](docs/team-external-artifacts.md).
5. AGENTS.md and its operational-contract reading order; `.agents/skills/` and `.claude/skills/` are included.
6. Relevant component context linked below; read old proposals as dated evidence, not automatic authorization.

## What is included

Verified Android implementation, model/runtime assets and fixtures, local avatar viewer and catalogs,
Context Assist providers/coordinator, research Python source/configuration/tests, governed manifest metadata,
selected Keras research checkpoints, final evaluations, aggregate training histories, dated experiment reviews,
and a hash-verification script. No system is rebuilt in this handoff.

The GitHub repository is PUBLIC. No service credentials, SDK paths, private APKs, keystores,
phone recordings, bulk RGB/raw/features, optimizer state or all full epoch predictions are published.
Their locations and transfer requirements are documented; this is not a claim that GitHub contains every
external training payload. Private debug service configuration must be provisioned separately.

## Resume now

Clone the shared branch; run `python tools/handoff/verify_shared_state.py`; use the fake build command
in the setup guide; review the evidence and known issues before changing code. Create a feature branch.
The first practical task is group review of Original Character vocabulary/playback and mixed-avatar appearance,
followed by a controlled qualified-signer evaluation if recognition quality will be claimed.
Do not automatically launch another training experiment or modify the protected WORD path.

## Source authority

The original C: worktree supplied Android; the original F: workspace supplied nonconflicting research source.
Its stale Android edits were NOT merged. New teammates use their clone, not those absolute paths.
Frozen tags/branches must stay fixed. The handoff is published by review branch/PR; no force push or main reset.
Current-state documentation supersedes older descriptions of what is installed, not their scientific evidence.

## Publication validation

Fresh shared-code fake build:186 JVM tests passed, debug/test APK build succeeded.
53 focused decoder tests passed. Hash checker verifies581 contracts;345 imported research blobs match
the original source hashes in the staged Git index. Source scan found no credential-pattern or known-local-key
matches in1878text files; no prohibited private/generated files or individual files over100MB are tracked.
This is a bounded source audit, not an exhaustive binary/history secret guarantee. See
[evidence/team_handoff_20261009/validation.json](evidence/team_handoff_20261009/validation.json).
No new training, TEST payload access or Android recognition changes were performed in this handoff.

## Shared GitHub review

[Pull request #1](https://github.com/mark-juswa/AppHear/pull/1) is the review/merge point. Main and frozen refs are unchanged.
