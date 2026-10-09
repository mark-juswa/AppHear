# Fingerspelling Android integration 01

Correction: current application baseline is
`baseline/apphear-text-to-asl-context-assist-ui-2026-10-04` (`cee71d9f181695847936eb5f3605ea37eab82a95`).
Initial inspection/build mistakenly used September29 checkout. Preserve current work,
adapt the isolated fingerspelling components to the newer application baseline and repeat
integration/WORD/Context Assist tests before continuing live validation. Model choice was
correct: residual epoch035 plus frozen B2, not a B2-only replacement.

User-authorized experimental integration, separate from model promotion. The residual
experiment's failed discrimination gate remains historical evidence; this task does not
relax it or claim production accuracy. B2 epoch076 remains the fallback/reference.

Starting branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`. Protected WORD reference
`baseline/apphear-s2-r2-integration-complete-2026-09-26` (`76d93ce...`). Existing dirty
documentation and untracked research/data are preserved. Context/architecture, evaluation,
device smoke, recognition-upgrade and Android UI contracts reviewed before implementation.

## Locked decisions

- Debug opt-in only; default/release disabled. Manual WORD/FINGERSPELL ownership.
- One Start/Done attempt is one variable-length CTC sequence, never a word event/window.
- Frozen residual epoch035 and MobileNetV3Small; FP32 builtin-only TFLite first.
- Separate encoder and sequence models; no delegate assumption or retraining.
- Adapter v1 405 columns, quality/dedup/crop semantics unchanged. Both slots retained.
- Endpoint-aligned bilinear crop on upright source RGB, no horizontal reflection.
- Separate confirmed spelling buffer; repeated characters survive. No SentenceBuilder edits.
- Mode/lifecycle transitions reset only temporal WORD state through existing public API.
- Source observation routing and session commands serialized on camera executor; models
  loaded off-main, inference off-main. Stale callbacks require generation checks.
- Bounded resources must fail visibly without silently truncating an attempt. Limits are
  resource guards, not a new model training window.

## Ordered gates

1. Pin/check export identities, numerical FP32 embeddings/logits and decoded strings.
2. Android adapter, quality, dedup, crop and decoder fixtures; zero-visual B2 parity.
3. Isolated session and ownership tests, checkpoint assets/hash refusal.
4. Only after parity, wire minimal Start/Done/Use/Retry UI behind debug opt-in.
5. Build WORD/default/experimental, existing WORD tests and preservation checks.
6. Connected phone numerical parity then latency/cadence/lifecycle/WORD regression.
7. Fixed live prompts with expected/raw outputs, repeat/J/Z and multiple signers when
   available. No end-to-end accuracy claim from one signer.

If numerical parity cannot be established, stop before live accuracy testing/UI rollout
and report the exact export/implementation gap. Phone availability is an external gate,
not permission to fabricate measurements. No TEST payload is used.
