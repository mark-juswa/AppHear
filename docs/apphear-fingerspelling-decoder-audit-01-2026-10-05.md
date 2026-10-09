# AppHear fingerspelling CTC decoder audit 01 — 2026-10-05

## State and preservation

Inference-only audit; no new baseline, training, TEST access, downloads or Android/UI changes.
F: remains on `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`, with existing dirty/untracked work preserved.
The isolated integration remains at the October 4 application baseline
`cee71d9f181695847936eb5f3605ea37eab82a95`.
A before/after hash inventory covers 1,429 existing source/config/model/history files
across both checkouts: zero changed. Candidate01, raw-v1, Adapter.v1, crop/quality/dedup,
visual encoder, fusion, WORD and Context Assist remain untouched.

B2 epoch076 SHA: `64f425358ef30e21a4aca18795226854f7aa44a34c3bc3e54a8c06366cb61397`.
Residual epoch035 SHA: `f87be3236196c8ab8321a3b6f7bb9d6398d048e257630a38546e8a8d00143251`.
B2 remains the formal research reference; this audit does not revise the residual
visual experiment's historical rejection or promote the application.

## Decoder and inference contract

`model/fingerspelling_metrics.py:greedy_decode()` collapses adjacent equal timestep
labels, removing blank27; an intervening blank preserves legitimate repeated letters.
`model/fingerspelling_emission.py:score_logits()` copies float32 logits and subtracts
float32 **0.5 from column27 before argmax**. Residual `evaluate()` uses this fixed B2
penalty. Android uses the same subtraction. Those implementations are unchanged.

New `model/fingerspelling_prefix_beam.py` applies exactly the same subtraction once,
then stable float64 log-softmax. Prefix search separately accumulates blank-ending
and nonblank-ending alignment masses. An identical new character requires an
alignment ending blank. It merges all symbol expansions before pruning prefixes.
Literal spaces remain unchanged, including leading/trailing spaces.

Frozen before results: **width10, return5**, all28 symbols, no token threshold,
length normalization, insertion bonus, LM, lexicon, dictionary, name database or
character rule. Width10 gives headroom over five returned paths without a large
search. Actual native lengths31–391 (median151), sparse7–79 (median31) make this
bounded reference implementation practical. No width/configuration sweep.
Rank is approximate CTC alignment mass after prefix pruning, with deterministic
lexicographic token-ID ties. Scores are not calibrated candidate confidence or
a guarantee of the global unpruned Top-5.

The audit is a separate opt-in entry point; greedy remains the application/trainer
default. No feature schema or train/serve computation changed. This reference
Python beam decoder has no Android parity claim.

## Data and recovered logits

Exactly256 governed DEV sequences from15 held-out signers, both established
native and 6.231166-Hz sparse views. All DEV examples are DAUN under the frozen
tranche; no MacKenzie DEV generalization is established. The existing1,024 TRAIN
inventory, split separation, phrase-overlap policy, adapter and residual run/code
identities were verified. TRAIN was not inferred or used to select the decoder.
TEST remains sealed.

The historical residual final evaluation saves predictions/metrics but no full
logits; no `.npz`/`.npy` logit archive existed in that run. Frozen inference was run
once using existing `ResidualSteps`/`ResidualCache`, verified raw/geometry and
precomputed frozen appearance artifacts. No RGB decoding or Candidate01 rerun.
Separate unpenalized float32 logit archives now retain offsets, per-sequence
metadata/lengths and hashed identity receipts. A final cached pass after lint/type
cleanup and added diagnostic reporting reused these verified logits.
All512 historical greedy strings and sample/reference/signer links match exactly.
Historical evaluations/checkpoints were not overwritten.

Native38,777 timesteps; sparse8,031. Both structurally CTC-infeasible sparse views
remain evaluated, as in the original evaluation; no fabricated timesteps or silent
exclusions. Native has zero infeasible views. Candidate records retain headroom.

## Complete DEV comparison

CER uses total character edit distance /3,457 reference characters per view,
including spaces. These are held-out sequence diagnostics, not production
end-to-end conversation accuracy.

| View | Greedy CER | Beam Top-1 CER | Exact greedy / beam | Top-3 exact inclusion | Top-5 exact inclusion | Top-3 oracle CER | Top-5 oracle CER |
|---|---:|---:|---:|---:|---:|---:|---:|
| native | 53.86% | 49.52% | 0/256 / 0/256 | 0/256 | 1/256 | 46.43% | 44.66% |
| phone | 53.69% | 52.16% | 0/256 / 0/256 | 0/256 | 0/256 | 48.71% | 47.30% |

**Oracle chooses the lowest-edit candidate using the known reference independently
for each sequence. It is not achievable automatic accuracy or a UI success estimate.**
Top-5 includes Top-3/Top-1, but need not include greedy.
Balanced CER: **53.77% →50.84%** (2.94 points); native improves4.34 points, sparse1.53.
Neither Top-1 decoder produces an exact reference in either view.

| View / decoder | Substitutions | Deletions | Insertions | Correct aligned chars | Predicted chars | Correct/predicted precision |
|---|---:|---:|---:|---:|---:|---:|
| native / greedy | 591 | 1156 | 115 | 1710 | 2416 | 70.78% |
| native / beam_top1 | 679 | 824 | 209 | 1954 | 2842 | 68.75% |
| phone / greedy | 962 | 716 | 178 | 1779 | 2919 | 60.95% |
| phone / beam_top1 | 920 | 739 | 144 | 1798 | 2862 | 62.82% |

Native recovers244 aligned characters but increases substitutions/insertions and
lowers precision2.02 points. Sparse recovers19 aligned characters, lowers substitutions42
and insertions34, increases deletions23 and raises precision1.88 points. Sparse gain
is not merely greater emission.

| View | Different Top-1 strings | Improved | Regressed | Neutral edit distance |
|---|---:|---:|---:|---:|
| native | 229 | 127 | 33 | 69 |
| phone | 185 | 73 | 43 | 69 |

Counts above cover changed strings only:27 native and71 sparse are unchanged.
Neutral means a different string with equal edit distance.

## Signers

| Signer | n | Native greedy → beam CER | Sparse greedy → beam CER | Top-5 exact native / sparse |
|---|---:|---:|---:|---:|
| 001e | 18 | 56.65% → 51.07% | 55.79% → 52.36% | 0 / 0 |
| 1c15 | 17 | 49.56% → 45.58% | 53.54% → 52.65% | 0 / 0 |
| 28d4 | 17 | 48.84% → 51.16% | 49.77% → 45.58% | 0 / 0 |
| 2b19 | 17 | 69.00% → 62.45% | 65.07% → 60.26% | 0 / 0 |
| 4e6b | 17 | 55.11% → 51.56% | 54.67% → 53.78% | 0 / 0 |
| 5ce0 | 17 | 51.61% → 48.39% | 58.47% → 58.87% | 0 / 0 |
| 661f | 17 | 41.10% → 36.02% | 37.29% → 36.02% | 0 / 0 |
| a459 | 17 | 47.58% → 42.73% | 44.49% → 42.73% | 0 / 0 |
| aeed | 17 | 49.79% → 44.77% | 51.46% → 52.72% | 0 / 0 |
| c28d | 17 | 77.88% → 71.43% | 72.35% → 70.51% | 0 / 0 |
| c6e5 | 17 | 69.84% → 65.08% | 66.67% → 61.90% | 0 / 0 |
| d516 | 17 | 51.75% → 46.05% | 52.19% → 53.07% | 0 / 0 |
| d5fd | 17 | 52.42% → 47.58% | 46.70% → 45.37% | 0 / 0 |
| ebdb | 17 | 47.77% → 41.52% | 53.12% → 50.89% | 0 / 0 |
| f896 | 17 | 38.96% → 37.66% | 43.29% → 45.02% | 1 / 0 |

Native improves14/15 signers;28d4 regresses. Sparse improves11/15;5ce0,aeed,d516,f896
regress. Balanced signer CER improves14/15;f896 regresses0.22 points. The benefit
is broad but not uniform or an independent unseen-population guarantee.

## J, Z and repeated-letter sequences

| View / subgroup | n | Greedy CER | Beam CER | Top-3 / Top-5 exact | Top-3 / Top-5 oracle CER | Changed improved / regressed / neutral |
|---|---:|---:|---:|---:|---:|---:|
| native / J | 59 | 54.80% | 51.60% | 0 / 0 | 49.07% / 46.40% | 28 / 8 / 16 |
| native / Z | 52 | 54.48% | 49.93% | 0 / 1 | 47.03% / 45.52% | 25 / 8 / 16 |
| native / REPEATED_LETTERS | 109 | 52.92% | 49.67% | 0 / 0 | 46.95% / 44.96% | 48 / 14 / 30 |
| phone / J | 59 | 53.20% | 53.07% | 0 / 0 | 48.67% / 47.20% | 11 / 10 / 18 |
| phone / Z | 52 | 54.07% | 52.97% | 0 / 0 | 50.07% / 48.69% | 15 / 8 / 15 |
| phone / REPEATED_LETTERS | 109 | 53.51% | 51.19% | 0 / 0 | 48.21% / 46.75% | 35 / 13 / 31 |

Subgroups overlap. J/Z score their whole sequences, not invented letter boundaries.
All subgroup counts exceed the existing10-sequence diagnostic floor. Complete
subgroup/signer S/D/I, Top-N and change metrics are in `comparison.json`.

## Top-N usefulness

The sole exact Top-5 recovery is native `ERIN CORTEZ`, signer f896, at rank4:
`ZERIN CORTE Z`, `ERIN CORTE Z`, `ZERIN CORTEZ`, `ERIN CORTEZ`, `ZERIN CORTE ZZ`.
Greedy was `ZERIN CORTEZ`. This is one real alternative, not a broad recovery pattern.
Top-5 has a candidate within one edit for only7/256 native sequences across7 signers,
and8/256 sparse across6 signers. Top-3 has6 native and5 sparse. These are oracle diagnostics.
Even oracle Top-5 CER remains44.66% native/47.30% sparse. The tested list does not
recover enough useful complete strings. This does not prove references are absent
from every possible alignment or wider beam; no other configuration was tested.

## Runtime

Host CPU Python decoder only, excluding model inference and metric/report work.
No Android beam performance measurement.

| View | Greedy median / p95 ms | Beam median / p95 ms | Beam total for256 |
|---|---:|---:|---:|
| native | 0.087 / 0.120 | 23.899 / 39.403 | 6.311s |
| phone | 0.045 / 0.077 | 4.769 / 8.303 | 1.289s |

First inference/validated-input construction plus logit writing took78.99s native
(including model initialization) and8.73s sparse. First-pass beam median/p95 was
40.00/71.59ms native and9.47/15.52ms sparse; the final cached pass shown above was
faster. Initial/final timings remain saved. Host run variation prevents a phone
latency forecast. Work is bounded by T,10 prefixes and28 symbols, with Python
sorting/prefix-copy overhead; greedy remains much cheaper.

## Phone evidence

AMY `session_1791162234888.json` and BELLA `session_1791162509867.json` retain raw
`SAAME Y`/`BELD DA` strings and aggregate diagnostics, not timestep logits or
reconstructible observation/model inputs. Previously recorded source hashes still
match. No candidates can be recovered, no phone attempt was requested, and none
were guessed.

## Tests and review

26 focused tests pass:14 new decoder/report tests plus12 existing B2 tests.
Coverage includes exhaustive tiny CTC alignment sums, marginal-best versus best-path,
blank-separated repeated labels, spaces, all-blank/empty sequences, extreme finite
logits, immutability, deterministic unique ranks, invalid inputs, unchanged greedy
penalty semantics, oracle separation and improved/regressed/neutral accounting.
Ruff and mypy (both new source modules) pass; Black in-memory checks pass.
Black multi-file CLI stalled at Windows `NamedTemporaryFile`, including the single-worker
corrective attempt. The recover skill classified an isolated development-tool issue;
a stack trace located the stall. Pure in-memory formatting avoided that path without
changing dependencies or the recognition system. No model-related recovery was needed.

Review: plan alignment PASS; protected-system integrity PASS; offline audit PASS.
Critical findings0. Important limits: no exact Top-1 references, modest sparse gain,
some signer regressions, worse native precision, reused model-selection DEV,
no Android beam parity/cost evidence. Minor: host timing varies. This is not an
independent TEST result or production promotion.

## Decision

**USE_BEAM_TOP1** for a subsequent controlled experimental decoder change.
Both views improve,14/15 balanced signer scores improve, and sparse substitutions/
insertions fall while aligned correctness/precision rise. Keep greedy fallback and
the fixed0.5 penalty/width10 policy. The gain is incremental, not a recognition fix.
Android remains unchanged; a later authorized port needs parity and device cost checks.

**Do not ENABLE_TOPN_SUGGESTIONS.** Sparse Top-5 recovers0/256 complete references;
native recovers1/256. Near-reference recovery is scarce and oracle CER remains high.
Do not show mostly incorrect suggestions or tune wider beams/priors for a pass here.

## Files and reproduction

New files:
- `model/fingerspelling_prefix_beam.py`
- `model/config/fingerspelling_decoder_audit_01.json`
- `tools/fingerspelling/decoder_audit.py`
- `tests/test_fingerspelling_prefix_beam.py`
- `docs/apphear-fingerspelling-decoder-audit-01-2026-10-05.md`

Separate evidence directory: `artifacts/fingerspelling_decoder_audit_01/`.
Key artifacts: `comparison.json`, `native_candidates.json`, `phone_candidates.json`,
`native_logits.npz`, `phone_logits.npz`, their receipts, `audit_identity.json`,
`initial_inference_runtime.json`, `validation.json`, `preservation_before.json`,
`decision.json`. Original models/features/history are unchanged.

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m pytest tests/test_fingerspelling_prefix_beam.py tests/test_fingerspelling_baseline2.py -q
& .\.venv\Scripts\python.exe -u -m tools.fingerspelling.decoder_audit run
```

The audit reuses matching hashed logits, never trains, and fails closed on model,
input or historical-greedy mismatch. No UI or runtime change follows automatically.

DECODER_AUDIT_COMPLETE — USE_BEAM_TOP1; TOPN_SUGGESTIONS_NOT_SUPPORTED
