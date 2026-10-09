# Experimental one-letter Fingerspell inference

Date: 2026-10-08. Supervisor explicitly approved one capture per letter with
confirmation. This supersedes whole-sequence interaction only while its internal
flag is enabled for frozen V2.1 epoch034. It is not a new alphabet-trained model.

Contract: unadjusted finite [T,28] logits → exact singleton CTC log masses for
A–Z; empty/singleton SPACE are refusal competitors. Blank27 penalty0.5 exactly
once in float32; stable float64 scoring; no dictionary, length bonus, priors,
class heuristics, confidence cutoff or Top-N suggestions. Best letter wins only
if greater than both refusal masses; A–Z order breaks letter ties. Scores do not
estimate correctness. The older greedy and prefix-beam10 decoders remain intact.

State flow: Start → show one letter → Done → preview → Use/Retry. Use appends
one A–Z symbol without spaces; confirmed repeated letters survive. Retry keeps
confirmed letters, Clear removes the isolated spelling. J/Z require motion
within that one capture. No automatic commit into WORD sentence state.

Input evidence: accepted hand AND at least one valid joint in the same slot.
Zero usable evidence refuses before inference. Partial missingness remains
eligible; no percentage threshold, timestamp deletion, filling or fabricated
coordinates. Adapter/raw/masks/model weights unchanged. Current-frame evidence
feedback reports observability, not whether a pose is the intended letter.

Flag: FingerspellCapturePolicy.SINGLE_LETTER_ENABLED and candidate identity
SEQUENCE_V2_1_EPOCH034_GEOMETRY_ONLY. Disable flag or install preserved V2.1 APK
for whole-sequence rollback. New private artifacts: fingerspelling_single_letter_01.

Audit storage: one completed session retains bounded unadjusted logits,
timestamp/usable flags, old greedy/beam strings, constrained preview and costs.
No RGB, landmarks or training admission. This allows exact offline reproduction
of new phone outputs; previous AMY captures without logits remain unrecoverable.

Implementation: model/fingerspelling_single_letter.py; authoritative October4
worktree FingerspellSingleLetterDecoder.kt, FingerspellCore.confirmLetter,
FingerspellRuntime. Research Kotlin templates/port are reviewed transfer sources.
No Candidate01, Adapter v1, WORD code, Android Activity/resources or Context
Assist changes. [T,405] feature schema unchanged.

Gates:66Python tests,161Android host tests,54Python/JVM/Xiaomi fixtures exact,
existing14-case model parity and ownership/exclusion checks,3local Context
Assist checks.1756existingfile hashes and237APK asset checks pass. Physical
letter identification remains a separate bounded gate; no all26-letter accuracy
claim. Detailed evidence/report: docs/apphear-fingerspelling-single-letter-gate-2026-10-08.md.

Physical gate completed: supervisor confirmed separate A/M/Y captures with
matching A/M/Y previews. Same logits old beam:AAAA/EMME/Y; singleton:A/M/Y.
All3 phone logits reproduce in Python; singleton6.41–9.96ms, total179–459ms.
Decision:SINGLE_LETTER_FLOW_RETAIN_EXPERIMENTAL. No all26 reliability claim;
bounded nonexpert check only. Use explicit confirmation, one letter per capture.
