# Fingerspelling quality decision while V2.1 runs

2026-10-08. Saved pre-V2.1 evidence and implementation inspection only. No model inference, training, acquisition, extraction, Android edits or TEST access. Existing V2.1 execution was not stopped, restarted, reconfigured or evaluated.

## Decision

**The confirmed bottleneck is unreliable local letter discrimination, compounded by intermittent loss of hand evidence. It is not a demonstrated Android, class-index, feature-order, CTC-repeat or decoder implementation fault.** The precise physical cause of each confused letter remains unproven: landmark estimation errors, loss of handshape detail in 2D geometry and insufficient local supervision are not separable with the retained evidence.

Finish the one already-authorized V2.1 local-letter correction. Do not launch a parallel architecture/training/decoder experiment. In the meantime, use the new evidence-only audit to distinguish actual letter improvement from SPACE/context and emission gains. If V2.1 does not materially improve letters and single-word spelling, stop geometry-only encoder iterations. The next justified architecture would be a dedicated handshape-supervised appearance path, rather than another generic ImageNet/global-embedding fusion. This is a conditional direction, not proof that pixels will solve the problem or authorization to train that path now.

## What the previous version did

The 4K epoch038 expansion improved held-out discrimination versus 1K. V2 subsequently added symmetric full-sequence context, per-convolution masking, changed optimization and synthetic missing-evidence training. Its package improved full phone-like CER from 46.98% to 43.48% on DEV-A and 46.24% to 42.71% on DEV-B. These changes cannot be attributed to noncausality alone.

Independent recomputation from saved predictions confirms:

| Pooled phone diagnostic | epoch038 | V2 epoch046 |
|---|---:|---:|
| Correct aligned letters /6316 | 3737 (59.17%) | 3800 (60.16%) |
| Correct SPACE /515 | 232 | 358 |
| Exact full strings /512 | 2 | 4 |
| S correct /340 | 235 (69.12%) | 150 (44.12%) |
| Single-word CER,42 sequences/419 characters | 48.69% | 49.88% |
| Single-word correctly aligned letters | 253 | 242 |
| Single-word substitutions | 111 | 131 |

V2 gains 189 correctly aligned phone symbols: 126 SPACE and 63 letters. No-SPACE CER also improves, so the gain is not exclusively spaces. However, complete spelling and isolated-name improvement remain unsupported. Stress CER improves in all six saved conditions, mostly through fewer deletions; heavy-stress precision worsens. Better sequence survival is not equivalent to better handshape classification.

The model can deliberately overfit a tiny TRAIN subset. That establishes optimization/graph learnability, not cross-signer letter reliability. More training time alone is not a proven repair.

## Why this is still experimental

Epoch038 is already deployed to the private phone as an engineering candidate; V2 is not the installed model. Neither has demonstrated reliable production recognition. About43% phone-like character error and4 exact sequences out of512 are incompatible with a claim of dependable complete spelling. These are held-out FSboard diagnostics, not literal real-phone error rates or per-pose A-Z classifier accuracy.

DEV-A has been repeatedly used for selection. DEV-B is separate by sequence but shares its15 official DEV signers and has already been opened after previous locks. It is confirmation under those policies, not an independent untouched population evaluation.

## What the actual input and supervision contain

`pipeline/fingerspelling/adapter.py` derives XY landmarks, source/wrist-relative scale geometry, real timing, wrist displacement, masks, proposals/ROIs and available body references. There are no source pixels, Z/world coordinates or direct thumb-contact/occlusion labels in the405 columns. Accepted hand observations are not proof of accurate individual finger geometry. Existing two slots can duplicate one physical hand; the failed canonicalization experiment does not justify changing that contract again.

Frozen manifest metadata, independently counted without performance-based selection:

| Role | Sequences | Single-letter transcripts | Single-word transcripts | Transcript length range |
|---|---:|---:|---:|---|
| TRAIN |4096|0|224|3–43|
| DEV-A |256|0|23|4–31|
| DEV-B |256|0|19|6–22|

This is continuous phrase CTC supervision, not an isolated-letter classification dataset. Each transcript supplies ordered letters without frame-level letter labels. That can teach letter recognition but does not guarantee stable identification of a pose held for several seconds. The requested single-letter use case is not directly measured. J/Z also require temporal motion; a static-only classifier would not cover the entire alphabet.

TRAIN imbalance is real: E7799 versus Q105/X132; S nevertheless has3911 occurrences. Rare-letter exposure is an issue, but does not explain the common S regression by itself. No class-specific weighting or correction is justified from these counts alone.

The existing TRAIN mask audit reports native21/4096 sequences with no accepted hands, phone41/4096, median phone any-hand availability67.80%, and6137 internal phone missing runs (median1, p95 5 observations). Completely missing sequences are about1% of phone TRAIN, so their presence cannot alone explain the broad quality deficit. Aggregate availability also includes setup/release: it does not locate loss inside each specific letter. The training cache retains real missing observations with time-valid=1 and the complete transcript; it does not relabel missing time as padding or invent coordinates. That makes robustness training valid but cannot restore fine detail that was never observed.

## Why an AMY attempt can produce wrong or repeated letters

The phone does not independently recognize A, then M, then Y. It gives all session observations to a sequence model, which assigns28 logits per timestep. Prefix beam sums plausible CTC alignment paths, then returns the highest-scoring spelling. It has no ground truth, dictionary or linguistic correction. A time-valid mask denotes a delivered observation, not a trustworthy handshape; missing-hand timesteps may receive nonblank predictions from context.

CTC collapses consecutive equal labels, but equal labels separated by a blank remain separate: `A,A,blank,A` becomes `AA`. Alternation between wrong letters and blank can produce multiple wrong letters. Beam may prefer a repeated-letter prefix because its accumulated alignment probability exceeds a shorter prefix. It does not manufacture an unrelated spelling after otherwise correct logits. Penalty0.5 lowers blank logits exactly once, favoring emission relative to blank; its saved benefit does not establish it as the cause of this specific attempt or justify retuning now.

The verified epoch038 AMY engineering session had51 observations,21 with any accepted hand, cadence6.3007/s, greedy `AESEYI`, beam/preview `AAESEYI`. This was a nonexpert attempt with no linguistic validation. Earlier `SASOMEMEEIY` was a different old-candidate session. The user's illustrative `ASSAAA` is not a saved session diagnosed here. Full per-timestep logits, handshape video and letter timing were not recorded for the epoch038 session, so we cannot assign its individual wrong letters to a particular frame, signing mistake, missing run or decoder transition.

## Confirmed versus uncertain

Confirmed: weak letters/complete strings, common-character regressions, missing observations, no isolated-letter coverage, supervision/selection that rewards full phrases, rare-letter imbalance, and correct export/Android/decoder parity. V2's full-CER objective can accept a letter regression when other symbols improve; this is a measured selection limitation, not proof that SPACE gradients caused S loss.

Strongly supported interpretation: local discrimination is insufficiently constrained by the existing geometry/phrase objectives. V2.1 is the focused test of that interpretation: local letters-only CTC, plus letter-sensitive checkpoint selection, without new data or geometry changes.

Uncertain: whether a reliable landmark stream could distinguish every confused handshape, the relative role of supervision versus geometry information loss, true per-letter boundaries/visibility, trained V2 on-phone behavior, and proficient-signer phone accuracy. Numerical train/serve parity proves equivalent computation, not correct hand detection or recognition.

Publisher outer-window trimming was a negative result for the tested B2/residual models: residual phone CER52.16%→53.60%, fewer insertions but more deletions/lost correct characters; the phase-locked control was also negative. This does not prove boundaries never matter on a long phone attempt or on V2, but gives no basis for making segmentation the next primary fix. Do not borrow WORD S2-R2.

Generic frozen ImageNet appearance and naive fusion did not generalize; the quality-gated residual gave modest real signal but failed its acceptance pattern. Those results do not rule out handshape-supervised appearance, and do not justify repeating the same backbone/fusion exercise.

## Useful work now and the next decision

Completed now: an inexpensive repeatable evidence packet that verifies saved metrics, counts transcript-task coverage, pools all-letter outcomes/confusions, preserves the exact phone example and verifies1598 protected hashes. It uses no TensorFlow, raw/RGB reads or model inference and leaves the ongoing V2.1 identity unchanged. The audit is evidence preparation, not a new accuracy improvement claim.

For V2.1 use its already-frozen independent letter-sensitive evaluation. Require actual improvement in phone no-SPACE error, letter recall/precision, single-word behavior, substitutions, signer spread and the common-letter safeguards while retaining context/robustness gains. Do not relax the rule after seeing full CER. No changes to its data,lambda,decoder or selection mid-run.

Separately, a future isolated FINGERSPELL input-quality safeguard could refuse a completed capture with zero accepted hand evidence and warn about loss of visibility. This would prevent unsupported output in an unobservable case, not recover the correct letters or solve high-coverage confusions. No broad hand-percentage threshold is validated; no timestep deletion, automatic trimming, repeat collapsing or uncalibrated confidence threshold is implemented here.

If V2.1 fails, the smallest necessary prerequisite to a handshape branch is a bounded TRAIN-only audit/annotation of existing RGB that establishes true letter identity and usable hand crops where assessable. Whole transcripts and CTC peaks are not frame labels; ambiguous frames must remain unknown. It requires competent annotation, not asking the supervisor to generate a custom A–Z corpus. Do not train another appearance model before defining trustworthy supervision and a signer-held-out letter-first evaluation. A dedicated isolated-letter mode also needs its own evaluated contract; it cannot be claimed from this phrase dataset alone.

## Preservation and repeatability

Research HEAD `cc1f3949114d0ed1dab38d4428191151b37df358`; branch `codex/current-working-text-to-asl-baseline-2026-09-29`. Authoritative Android source is the separate October4 C: worktree; neither Android tree was edited. Existing dirty/untracked files were preserved.

Created only:

- `tools/fingerspelling/pre_v2_1_quality_audit.py`
- `artifacts/fingerspelling_pre_v2_1_quality_audit_01/audit.json`
- this report.

The new audit recomputes all eight normal frozen cohort/view/model edit totals exactly and compares1598 protected input hashes: zero changes. All source evidence SHA identities are retained and checked again after reading. No WORD, Context Assist, Candidate01, Adapter, existing model, V2.1 configuration/trainer or Android behavior change. No new device/regression/accuracy claim.

Repeat from the project root:

```powershell
& .\.venv\Scripts\python.exe -m tools.fingerspelling.pre_v2_1_quality_audit
```

Primary sources: `runs/fingerspelling_sequence_v2_01/final_evaluation.json`; `artifacts/fingerspelling_sequence_v2_review_01/analysis.json`; `artifacts/fingerspelling_sequence_v2_gate_01/train_missingness_evidence.json`; the frozen TRAIN/DEV manifests; `docs/apphear-fingerspelling-train4096-epoch038-android-2026-10-07.md`; visual, residual and outer-boundary reports; actual Python Adapter/encoder/beam/cache and C: FingerspellRuntime/Core implementation.

**Recommendation: finish the focused local-letter correction; do not start a parallel geometry, decoder or generic-visual experiment. Judge letters first. If it fails, change the supervision/input strategy toward a dedicated handshape path instead of another TCN iteration.**
