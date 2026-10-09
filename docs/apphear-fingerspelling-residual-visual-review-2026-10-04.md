# Residual visual implementation review — 2026-10-04

Scope: review the separate opt-in residual implementation against the resolved plan
and project context. This review reports findings; it makes no further implementation changes.

| Layer | Result | Evidence |
|---|---|---|
| Plan alignment | PASS for implementation/handoff | Quality/dedup/audit first; actual frozen B2; near-zero small residual; no performance probe or full run; user-run1280 sequence workflow |
| System integrity | PASS | Adapter405 and original cadence/CTC code reused; only6adapter variables train; original checkpoint/WORD/Android unchanged;2057oldfiles hash verification; official roles and TEST protections inherited |
| Offline engineering readiness | PASS |18tests, seven-module mypy/lint, crop review, fresh RGB path and final3-update checkpoint/resume/zero fallback smoke |
| Production/accuracy readiness | NOT REQUESTED / NOT PROVEN | Full residual data/training/DEV comparison pending; no Android implementation/parity/export/device latency, no production enablement |

Critical issues:0. Important implementation issues requiring a fix:0.
Minor/remaining research limitations:3.

1. The12retained-crop visual review is bounded and nonrandom. It excludes obvious nuisance
   proposals but cannot establish a corpus-wide contamination rate; face/background context
   and blur persist. Full materialization reports group coverage and rejections explicitly.
2. Audited DEV crop coverage44.44% is lower than TRAIN DAUN49.88%/MacKenzie62.99%.
   Strict quality removes some valid hands. The current-frame quality score is not a
   calibrated probability and duplicate suppression is only an obvious-proxy heuristic.
3. The frozen generic ImageNet representation may remain signer/session-specific. Only
   the forthcoming full signer-disjoint residual experiment can answer usefulness. Sparse
   views remain a phone approximation, and full cache memory is severalGB.

Recommendation: **run the single governed offline user experiment**, after full residual
materialization validates. Do not ship or integrate it into Android. Selection/decoder/
support rules are frozen before the full run. If emission rises without actual aligned
character/substitution/precision/CER improvement, close this visual path and keep B2.

Imprint completed in `context/feature-schema.md` and
`context/fingerspelling-residual-visual-v1.md`. Equal1559width does not imply compatibility
with the previous boolean-validity visual contract; distinct schema/identity checks apply.
The original405 feature contract and its existing Python/JVM parity are unchanged.
New crop/quality/appearance Android parity is explicitly deferred, not silently assumed.
