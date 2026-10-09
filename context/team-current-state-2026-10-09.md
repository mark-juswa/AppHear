# Verified team state — 2026-10-09

## Actual current architecture

- Native Kotlin/CameraX app; launcher SplashActivity, app shell MainActivity, recognition RecognitionActivity.
- Camera input is adapted upright at input layer; front behavior is the reference; rear path/smoother preview
  was device-checked. Candidate01 remains the frozen shared observation producer.
- WORD: existing `perceptionvnext/PhoneProductionSession.kt`, S2-R2 PRE/ACTIVE/POST + admission,
  recognition-v2 materialization/frozen 236-class model, existing sentence storage/Hear. Do not replace it
  with the old normalized-258 path from July docs. WORD segmentation uses a separate 378-feature contract;
  recognition-v2 is a separate input contract. Verify manifests instead of conflating them with fingerspelling405.
- FINGERSPELL: frozen V2.1 **epoch034**, symmetric masked TCN, Adapter.v1 `[T,405]`, FP32 28 logits.
  Geometry-only; old MobileNet/residual is not attached. Current automatic held-letter path uses exact
  singleton CTC scoring, a 4-second bounded genuine-observation window, stability checks and hand-lowering
  rearm for repeating a letter. Not unrestricted fluent continuous fingerspelling.
- Bounded-session diagnostic decoding retains prefix beam10, blank27, penalty0.5. Do not confuse this
  with the singleton held-letter decoder actually accumulating letters on the camera screen.
- Context: `contextassist/ConversationPhraseAssist` owns hearing turns/provider suggestions;
  `coordination/RecognitionCoordinationBridge` consumes actual hearing text and the frozen six full-match
  English name/place/spell rules. Temporary automatic routing occurs before response activity, with WORD idle
  and no usable hand. It cannot derive recognized letters from a predicted response. It is not an arbitrary
  semantic orchestrator. Model confidence is not compared across the two recognition owners.
- Exactly one recognition owner consumes each observation through the existing ownsObservation seam.
  Stale asynchronous results are generation/epoch guarded. WORD and fingerspelling buffers remain separate.
- Text-to-ASL question -> Sign It -> Reply is the primary context flow. CURRENT SIGN is tentative detection;
  RECOGNIZED is stabilized constructed spelling/WORD sentence. Top status pill hugs Word/Fingerspell text.
  No Start/Done or on-screen chooser. Settings remains manual fallback. Top Hear reviews/confirm spelling;
  confirmation records actual text and returns to WORD. Bottom SPEAK receives hearing input.
- Text-to-ASL: Original now273 entries (235 word entries,35 phrases,A/B,idle), 32 ZIP substitutions+171 additions,
  one of each duplicated ZIP sign, STAND excluded/idle retained. New remains122 entries with its alphabet fallback.
  Mixed old/new avatar rigs are retained; linguistic correctness of all animation labels was not established.

## Exact model identities

V2.1 epoch034 Keras SHA `3f92287c5ee82b2e0de1d396c4d27fe3b0efaed8af23b79b878740a56f1af638`.
TFLite SHA `e78de274b967acf0ea9d30bd3f3ac4422a1ef8ebdd95c8676b57dd05fed75c4c`.
Model manifest SHA `8edc998728fa41883abacbc8382359d6d61621bc259da78ca7c2ab6f8126d01e`.
Package `packages/fingerspelling_continuous_v2_1_01`, including runtime policy and parity fixtures.
Prior epoch038 hash `b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886`;
old B2 and residual remain historical references, not current live appearance fallback.

## Engineering evidence versus accuracy

186 JVM tests passed for the vocabulary build; Xiaomi seven sample clips loaded/finished,
2 catalog/playback tests passed, unchanged ownership regression passed separately after a combined focus timeout.
All239 previously packaged assets were byte-identical, all203 new GLB hashes passed.
Model/Adapter/decoder parity and owner/Settings/camera/UI tests were established before this vocabulary task.
Successful supervisor AMY held-letter checks prove wiring only; signer proficiency was not established.
All-26 accuracy, reliable live names and fluent recognition remain unproven. Neither model is production-reliable.

## Completed / unfinished / future

Completed: bounded/offline research, 4K acquisition/extraction/training, V2/V2.1 run/evaluation,
V2.1 export/Xiaomi parity, held-letter interaction, context ownership coordination,
camera controls and Original vocabulary technical integration. All are experimental debug features.
Unfinished: qualified-signer live reliability evaluation, trustworthy per-letter/handshape annotations,
all-animation linguistic review/consistent avatar appearance, service provisioning on teammates' machines,
bulk data/optimizer transfer, release/security architecture for remote-service credentials.
Future options are conditional on evidence and separately authorized; no V2.2, new appearance backbone,
dataset expansion, threshold sweep or WORD redesign is scheduled automatically.

## Protection and document drift

Do not change Candidate01 assets/semantics, WORD378, S2-R2 lifecycle/recovery/admission/CONFIG01,
WORD materializer/Recognition V2/frozen236 model, PhoneProductionSession, SentenceBuilder,
WORD sentence/Hear/TTS/Context behavior as a side effect of fingerspelling/UI experiments.
Keep fingerspelling Adapter.v1/policy/weights frozen unless a separately approved task requires a versioned gate.

README July status, September15 phase maps and Android-redesign initial inventories were outdated for the installed
app; they are preserved as history and now carry current-state notices. V2.1 result review describes its PRE-export
state at that date; later transfer/continuous/baseline reports supersede installation status. The F: research Android
copy was stale and remains local. The correct shared source is this branch, not any personal absolute path.

Component contracts: [baseline](current-working-baseline-2026-10-09.md),
[fingerspell](fingerspelling-continuous-v1.md), [coordination](recognition-coordination-v1.md),
[Original words](text-to-asl-original-words-v1.md), [research findings](../docs/team-research-findings.md).
