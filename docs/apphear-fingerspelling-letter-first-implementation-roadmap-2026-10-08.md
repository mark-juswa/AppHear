# AppHear letter-first solution and implementation roadmap

2026-10-08. Applies only to the isolated fingerspelling system. No new branch, model experiment, dataset expansion, Android change or WORD change.

## Current decision after V2.1 — 2026-10-08

V2.1 epoch034 passed the frozen letter-discrimination review. The conditional
failure branch below was not triggered. The supervisor confirmed no qualified
fingerspelling reviewer is available; supervised appearance training is paused.
Follow `docs/apphear-fingerspelling-post-v2-1-roadmap-2026-10-08.md`: transfer the
supported main-only candidate through FP32/device parity, preserve epoch038
rollback, then separately gate the exact no-usable-input safeguard. No new
geometry/appearance training, automatic model install or WORD change.

The rest of this document records the earlier pre-result plan and preparation.
Its waiting-for-V2.1 language is historical, not the current execution state.

## Technical decision and delivery scope

Preserve the current data/perception/feature/decoder/session pipeline. Complete the already-running V2.1 correction as the sole geometry-learning intervention. In parallel prepare input observability safeguards and trustworthy local handshape supervision from existing RGB. Recognition weights/configuration must not change during the active run.

The immediate delivery remains bounded continuous spelling with confirmation. Reliable single-letter identification is an additional requirement that needs direct evidence, not a claim inferred from phrase CER. J/Z need temporal motion; a static image classifier alone cannot cover the full requirement. Do not add a second UI mode now.

Terms:

- Letter discrimination: correct aligned A–Z symbols, substitutions and letter precision/recall; distinct from SPACE gains and merely longer output.
- Missing input: delivered real observations lacking accepted usable hand geometry; distinct from padding.
- Human letter evidence: an identified competent reviewer confirms an actual A–Z shape/motion in source RGB and an acceptable Candidate01 crop. Not transcript timing or CTC pseudo-labels.
- Safe input refusal: declining unsupported output when there is zero accepted usable hand geometry. It does not recognize the right letter and is not an accuracy improvement.

## Evidence that determines the order

V2 improves phone-like full CER to43.48%/42.71%, but pooled letter recall only59.17%→60.16%;126 of189 extra matches are SPACE. S recall69.12%→44.12%; pooled42 single-word examples worsen48.69%→49.88%CER. Exact phone strings remain4/512. Missingness stress is better but not solved. Geometry and Android parity are already verified for the installed epoch038. The precise physical cause of letter confusion has not been proven.

The four-thousand TRAIN manifest has zero isolated-letter clips, with phrase-level CTC supervision and no per-letter timing. Geometry contains XY/masks/timing, not hand pixels or thumb-contact labels. These facts justify local supervision first; they do not prove geometry can never suffice. V2.1 tests that narrower hypothesis.

## Workstream 1 — finish the authorized correction, without a parallel run

Already implemented and running: V2.1 local letters-only CTC after block4, fixed lambda0.5, unchanged full28-logit head, same4096TRAIN/cadence/missingness. Equal native/phone full/no-SPACE DEV-A selection is frozen. DEV-B is post-lock confirmation only. No changes to optimizer, loss weights, decoder, thresholds, sampling or training duration while waiting.

An important implementation limitation: the auxiliary receptive field is61 observations (30earlier/30later), not61milliseconds or one linguistic letter. Saved phone-like DEV sequences have length<=61 in254/256DEV-A and255/256DEV-B;158/177 respectively have length<=31, for which the nominal receptive support can cover the full valid sequence at every timestep. Near clip edges context is truncated, and effective learned use is unmeasured. The auxiliary head still learns letters-only sequence CTC, not directly reviewed per-letter positions. This does not invalidate the run, but it prevents presenting it as proof of isolated/local-letter supervision. Keep its fixed configuration and evaluate actual discrimination rather than retuning it on this observation.

When final evaluation is available, review its already-implemented pooled letter/single-word/signer safeguards. A lower full CER alone cannot promote it. Require a meaningful pattern of lower phone no-SPACE error, better letters/precision, lower substitution burden and broad signer benefit without the common-character failure pattern. Preserve epoch038 and V2 rollback identities.

If the result is mixed, keep the strongest validated candidate rather than start a V2.2 loop. If the local objective fails materially, close further geometry-only encoder experiments. This roadmap does not predeclare that outcome or change the frozen quality decision.

## Workstream 2 — input observability, implemented now but unused

New pure utility: `pipeline/fingerspelling/input_evidence.py`.

Input: a validated raw-v1 sequence. Output: separate `apphear.fingerspelling.input_evidence.v1` diagnostic including total observations, any accepted/usable hand counts, usable fraction, longest missing run and timestamp span. Geometry is usable when a slot is observed and has a valid joint; this is availability, not proof of a correct handshape.

Exact refusal recommendations:

1. No accepted observations: `NO_ACCEPTED_HAND_OBSERVATIONS`.
2. Accepted flags but no valid joint geometry: `NO_VALID_HAND_GEOMETRY`.

No guessed observed-percentage threshold. The21/51 example remains eligible. No timestep is removed, filled, mirrored or relabeled. No scores are treated as calibrated recognition confidence. The utility is not imported by a trainer or Android.

Future integration, only after its offline/device gate: apply the equivalent assessment inside FingerspellSession at Done before invoking the alphabet recognizer; if completely unobservable, show a retry message. Keep existing owner/generation protections, session flow and WORD storage unchanged. Candidate01 and PhoneProductionSession must not be edited. More detailed live hand-visibility guidance needs parity and runtime evidence; it is not implemented by this offline utility.

This protects against false certainty in an unobservable capture. It does not correct S/M/A confusions, and it is not the main quality solution.

## Workstream 3 — trustworthy handshape supervision, prepared now

New tool: `tools/fingerspelling/letter_evidence_review.py`.
Policy: `pipeline/config/fingerspelling_letter_review_01.json`.
Packet: `artifacts/fingerspelling_letter_review_01/review_request.json`.
Human records: `artifacts/fingerspelling_letter_review_01/human_reviews.json`.

The first bounded review request contains16 existing foundation TRAIN videos,16 official TRAIN signers,8DAUN/8MacKenzie; total source material about88.12seconds, already cached92,111,694bytes. No download, copying of RGB, Candidate01 inference, crop/embedding generation or model fitting occurs. Selection is deterministic from frozen TRAIN metadata, signer diversity and alphabet coverage; it does not consult model/perception results. Transcripts contain all26letters, including Q/X/J/Z. This is not a claim that every letter has a clean visible frame.

Each row binds source path/SHA, raw path/SHA, feature receipt SHA, official signer/stratum/transcript, actual source-frame indices/timestamps, reflection policy and input assessment. Existing size/MD5/source/raw/Candidate01 lineage verifiers are reused. No foundational artifact changes.

The competent reviewer watches the original RGB, uses actual indexed observations, and records only clearly assessable letter spans. Candidate slot is a slot identifier, not physical handedness. A trustworthy crop must contain the actual hand and required fingers; face/background or uncertain labels cannot become supervised examples. No letter is assigned just because it occurs in the transcript. J/Z need reviewed motion spans. Static letters can use a clear frame or short reviewed span. Repeated letters remain separate when both are identifiable.

Pending/unknown/unassessable records remain explicit. The template contains zero automatic labels. Validation refuses DEV/TEST role, unknown/missing/duplicate source identity, invented frame index, overlapping spans, static-only J/Z, non-human label sources, untrusted crops and unlabeled reviewer identity. Qualification is a recorded reviewer attestation, not cryptographic proof of competence or label accuracy. Human labels do not automatically authorize training.

This packet is a small supervision feasibility check, not an adequate new training corpus. A human review is required before claiming any useful handshape labels. No proficient reviewer is currently confirmed; that is an external dependency for the conditional appearance direction, not a blocker to finishing V2.1. Do not ask the supervisor to create a custom A–Z dataset or treat their phone smoke as accurate labels.

## Conditional implementation if V2.1 fails

Use one dedicated handshape-supervised visual path, only if reviewed existing RGB actually yields usable labels. Do not repeat the old frozen generic ImageNet embedding experiment.

Reuse existing Candidate01 crops, their quality/deduplication, raw-to-frame alignment, MobileNetV3Small code/weights and geometry/session/CTC evaluation infrastructure. Fine-tuning to reviewed letter evidence would create a new appearance identity; old ImageNet/residual packages remain intact. Do not train a new detector or search backbones.

Static letters need local handshape supervision; J/Z need reviewed short motion evidence. A per-image26-class head cannot by itself prove dynamic-letter recognition. The narrow initial supervised task may use per-frame static labels plus the existing short-context CTC mechanism on reviewed dynamic spans, with masks and real observations. Exact label counts, identifiable motion spans and signer coverage must be known before freezing this training contract. Claiming a fully specified successful visual model before that would be another unsupported guess.

The intended end-to-end integration is quality-gated handshape evidence correcting the best retained geometry recognizer, with the geometry-only result reproduced when visual contribution is zero. Preserve the main28-output head/beam semantics. Do not attach old B2 residual weights to a new geometry state. Do not increase TCN width again.

Only one bounded, signer-separated local supervised validation may authorize a full visual run. Existing official TRAIN roles stay TRAIN; an internal development holdout must be grouped by signer and labeled a diagnostic, not a new official DEV role. Every measured class needs held-out support; no guessing accuracy for absent classes. The full existing DEV-A/DEV-B sequence policies remain unchanged. Separate held-out local-letter annotation/evaluation is required before claiming reliable single-letter behavior. Never fabricate frame labels from CTC peaks to avoid that prerequisite.

If crop/label feasibility or held-out local discrimination fails, stop the appearance path before full training. No backbone/fusion/crop-size sweep follows. The existing experimental recognizer remains available, but reliable letter recognition cannot honestly be guaranteed under the deadline without the necessary evidence.

## Workstream 4 — transfer only the justified candidate

After actual quality passes, reuse the existing FP32 export, `[T,405]+mask→[T,28]`, greedy/beam fixtures and Xiaomi parity/runtime pipeline for a geometry candidate. Do not rebuild the app or redo perception research. An appearance extension would add only its separately verified crop/encoder parity requirements.

Private FINGERSPELL selection only; manual ownership and Start/Done/Preview/Use/Retry/Clear remain. No automatic switch, Top-N suggestions, dictionary, LM, Gemini correction or repeat suppression. Proficient-signer validation is needed for a live accuracy claim; nonexpert smoke establishes only engineering behavior.

## Deadline and stop discipline

Now: complete the unused assessment, review packet and focused tests; freeze the roadmap. No extra training runs or branches. Completed during this session.

Next result: one saved V2.1 review using its pre-existing metrics. No retuning to obtain a pass. If supported, proceed to the already-working isolated transfer process; if not, use the prepared review packet to determine whether supervised handshape work is feasible.

Review material is only88seconds, but annotation duration depends on reviewer competence and ambiguity and has not been measured. No promised hours-to-accuracy or guaranteed delivery date. Appearance labeling/training may not fit the deadline; if it does not, retain confirmation-based experimental behavior and state the limitation rather than silently present it as reliable.

No extra full-data extraction/embedding generation occurs before supervised evidence supports it. Long jobs remain user-run/resumable. No model automatically exports, installs or promotes from the new tools.

## Validation and exact commands

27 focused checks passed:13 new assessment/review boundary tests and14 unchanged prefix-beam tests. Ruff passes; mypy passes for both new production modules. Repeating packet preparation produces the identical request SHA and does not overwrite human review records.

Packet SHA256: `52feb432e46d8648f373683a870cf84f0253c2563dbaa52c97fa2f86a6d85e5a`.
Current label inventory:16PENDING,0reviewed letter labels,`training_admitted=false`.

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.letter_evidence_review validate
& .\.venv\Scripts\python.exe -m pytest -q tests/test_fingerspelling_letter_readiness.py tests/test_fingerspelling_prefix_beam.py
```

No need to rerun preparation; to reproduce its deterministic request and lineage checks:

```powershell
& .\.venv\Scripts\python.exe -m tools.fingerspelling.letter_evidence_review prepare
```

This is not a training command. If the request already exists and differs, preparation refuses to overwrite it. Existing human records remain preserved.

## Protection and review

No WORD code/dependency is introduced. PhoneProductionSession, SentenceBuilder, S2-R2, PRE/ACTIVE/POST, Admission, materializer, RecognitionV2,236-class model, Context Assist, Hear/TTS, WORD UI, Candidate01, Adapter.v1, Android, existing model packages and V2.1 code/configuration remain untouched. No TEST reads. New utility imports raw schema only, never the WORD recognizer. No new branch, reset, merge or rewrite.

Architect decisions are captured here. Imprint records the separate diagnostic/review contracts without changing405features. Review recommendation: host preparation PASS; recognition improvement NOT YET ESTABLISHED; Android delivery NOT AUTHORIZED by this preparation; supervised appearance training BLOCKED until competent human review and a separately frozen supervised gate.
