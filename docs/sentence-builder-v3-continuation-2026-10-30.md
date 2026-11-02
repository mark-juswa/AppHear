# Sentence-builder v3 continuation — 2026-10-30

Status: implementation built locally; provider comparison and device acceptance pending.
Worktree `I:/AppHear-Conversation-Claude/worktree`, branch `claude/conversation-flow-ux`.
Continues the five improvements approved in the Claude handoff; original 16 dirty files were
preserved before editing. No branch switch, reset, merge, training or model replacement.

## Behavior

- In visible sentence-assist mode, RECOGNIZED shows plain English immediately, then the
  validator-accepted sentence. The signed glosses remain below it. Use signed words / Use sentence
  selects the wording both displayed and spoken. A late rendering cannot change text during TTS.
- Auto-say observes the existing 3.5-second stillness and 3-second countdown policy. It waits while
  the current sentence is pending; failures/timeouts release the plain fallback. Choosing signed
  words bypasses AI waiting. WAIT, new signing, lifecycle stop and spelling rules remain intact.
- Prompt v3 receives the last four actual dialogue lines (two exchanges when complete), each
  capped at 200 characters. Current unsaid drafts and predicted responses are excluded. No history
  yet falls back to the latest hearing message. Context supplies neither new signed content nor
  instructions. The v2 asset is retained; validator, lexicon and substitution limits are unchanged.
- Tapping an underlined gloss in Signed opens Remove/Cancel. Auto-say pauses while this dialog is
  open. Removal runs through the sentence owner on its analysis executor and requires the exact
  reviewed phrase; changed phrases reject the edit. The store is synchronized across legacy/A1
  ownership. Old Top-5 evidence is invalidated, preventing substitutions on misaligned indices.
  Remaining words are re-rendered; removing the final word empties the sentence. FINGERSPELL keeps
  its original confirmation path and does not expose word removal.
- All changes remain under the existing debug conversationFlowV2 / sentenceAssist / conversationAutoSay
  flags. Default/release conversation behavior is off. No S4/F feature math, schema, perception,
  recognition model, decoder threshold, camera configuration or avatar asset changes.

## Measured baseline

Claude's saved v2 run contains all 163 distinct cases: 162 provider responses and one HTTP error.
The shipped Kotlin validator accepts 136, rejects 26, and falls back for the unavailable response.
Clean-category acceptance is 54/59 = 91.53%, clearing the registered 90% gate. Accepted substitutions:
helped 0, harmed 0, neutral 0, with 51 protected correct-Top1 opportunities. Harm gate passes;
this does not demonstrate useful correction, since none of 12 proposed replacements was accepted.
Provider latency p50/p95 is 1030/1421 ms (162 successful HTTP responses).

These are sentence-rendering diagnostics, not cross-signer end-to-end ASL accuracy. Lexical
validator acceptance cannot establish that word order, pronouns or meaning are right; human review
columns in review.csv remain unfilled. No meaning-preservation or invention-rate claim is made.

## Prompt v3 comparison

The original 163-case population is unchanged. Eight separately authored dialogue cases cover
history, misleading context, explicit negation and an instruction-like hearing message. They are
stored in eval/sentence_assist/cases_context_v3.jsonl. The Kotlin harness exports exact prompts
from the same renderer used by the app. Scores retain each run's own prompt version.

No v3 requests have been sent. Automatic approval review rejected the Gemini call because it
requires explicit authorization to send the evaluation text to that external destination.
Do not bypass the rejection. The exact 171-request payload and hashes are prepared locally in
F:/ASL DATASET/5. Apphear3/artifacts/sentence_assist_continuation_20261030/evaluation_payload/.
Destination: https://generativelanguage.googleapis.com/v1beta/interactions, store=false.
Payload: glosses/allowed alternatives, hearing-context test text, eight authored dialogue fixtures,
instructions and response schema. No images, videos, landmark arrays or model weights. Existing
private Gemini key is read in memory and sent only as the request header, never logged.

After explicit approval, run the prepared run_v3_eval.py once (163 + 8 requests). Score with
SentenceAssistEvalTest; compare clean acceptance, harmful/helpful substitutions and p50/p95 to v2.
Keep raw responses. Do not retry/tune away failures or relax the validator to manufacture a pass.

## Validation and rollout

Build receipts, test counts, package identity and protected-asset checks are recorded in
evidence/sentence_assist_continuation_20261030/validation.json after final local builds.
Credential-free flag-on JVM/debug/test-APK build passed before final race-guard refinements.
Final flag-off/release and private flag-on build receipts supersede that intermediate check.
No phone installation is performed while provider/semantic acceptance remains pending.

Developer phone checklist after offline approval: plain → improving → accepted sentence; exactly
the displayed wording spoken by SAY IT/auto-say; signed-word toggle; Remove/Cancel/last word;
new sign while a removal dialog is open; provider timeout/offline fallback; WAIT; stop/resume;
unchanged spelling confirmation; listening/typed replies/history/avatar. Apply context/device-smoke.md
and record actual device FPS p50/p95. No phone or cross-signer result is implied by a successful build.

## Review and rollback

Plan alignment: PASS for implemented code; external comparison pending. System integrity: PASS
for bounded sidecar/context, exclusive existing owners, default-off flags and frozen models/features.
Readiness: PENDING. Important open gates: v3 provider comparison + human semantic review; developer
UI/F22 device acceptance. No critical code finding remains in the local review. Recommendation:
retain as a local Lab candidate until these gates pass.

Rollback: use existing Use signed words; or build with conversationFlowV2=false and sentenceAssist=off.
For the prior prompt alone, point policy_v1.json at retained prompt_v2.json. Prior APKs and Claude's
pre-continuation patch/files remain preserved; do not reset the entire worktree or touch other experiments.

## Final local build receipts

- Private flag-on Lab: 399/399 JVM tests, debug APK and Android-test APK PASS.
- Flag-off fake: 399/399 JVM tests, debug APK and unsigned release APK PASS (release lint-vital included).
- Release flags inspected: conversation flow false, auto-say false, sentence assist OFF.
- Protected tracked assets/models/features: 620 checked, zero mismatches. Git diff --check PASS.
- Two focused rendering/link/spelling instrumentation checks compile; they have NOT run on a phone.
- Private APK: I:/AppHear-Conversation-Claude/apks/codex-sentence-builder-v3-20261030-private.apk.
- Companion: I:/AppHear-Conversation-Claude/apks/codex-sentence-builder-v3-20261030-androidTest.apk.
- No Gemini v3 requests sent and no APK installed. Source remains uncommitted for review.


## Wireless installation — 2026-10-30T12:46:30+08:00

User explicitly requested installing the built Lab candidate while the v3 provider comparison
remains pending. Updated only com.example.apphear.conversationlab on Xiaomi M2101K7AG over
wireless ADB using install -r. No uninstall or app-data clear. Installed base.apk SHA-256 matches
the saved private APK; SplashActivity launch verified. Provider comparison, human semantic review
and the full developer UI/F22 smoke remain pending. This supersedes earlier not-installed status.

## Prompt v3 comparison result — 2026-11-02 (Claude)

The user approved the 163-case v2-vs-v3 eval ("Build all five", item 5). Ran the prepared payload once
(hashes matched the manifest) with a 4.5 s pause between requests: 162 ok + 1 timeout on the 163 cases,
8/8 ok on the dialogue cases. Scored with SentenceAssistEvalTest and the shipped validator.

| Metric | v2 baseline | v3 (context) |
|---|---|---|
| Accepted / rejected / unavailable | 136 / 26 / 1 | 138 / 24 / 1 |
| Clean acceptance (gate >= 90%) | 54/59 = 91.5% PASS | 51/59 = 86.4% FAIL |
| Accepted substitutions helped / harmed | 0 / 0 | 6 / 4 |
| Harm gate (<= 2%) | PASS | FAIL |
| Latency p50 / p95 | 1030 / 1421 ms | 1031 / 1702 ms |
| Dialogue cases accepted | n/a | 7/8 |

The v3 swaps that were accepted but wrong replaced correct signs: WHERE to WHEN, HOUSE to HOME, WORK to HOME,
FRIEND to FAMILY. v3 also rejects more long sentences (62.5% vs 87.5%).

Decision: prompt v3 fails two registered gates, so it is not shipped and was not tuned to pass.
`policy_v1.json` points back at `prompt_v2.json`. The context plumbing stays in the code; with prompt v2,
`conversationLines` is 0, so no dialogue context is sent. The other four improvements (sentence first in
RECOGNIZED, auto-say waits for it, tap a signed word to remove it, signed/sentence toggle) are unchanged.
Raw runs: `eval/sentence_assist/runs/` (gitignored). Scores: `android/app/build/sentence_assist_eval/`.

Rebuilt the private Lab app (399/399 JVM tests, APK asset checked: prompt_v2) and installed it on the
Xiaomi with `install -r` (sha256 dcdaffea...). Device acceptance by the user remains pending.
