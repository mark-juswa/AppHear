# AppHear fingerspelling: next quality decision

Decision: **2. Move to governed TRAIN-4096 preparation/training.**

This is a technical investment decision under the deadline, not proof that4096 is a
necessary minimum, that1K can never improve, or that expansion guarantees success.
The user requested a choice after reviewing the completed1K finishing check. No
acquisition, extraction, training, Android change or WORD change is executed here.

## Diagnosis and why this is the next intervention

The verified bottleneck is inadequate learned character discrimination and generalization.
The strongest actionable explanation is limited effective supervision of character
shapes/transitions across signing instances. This is an inference from the evidence,
not an identified unique physical cause. No demonstrated CTC/Adapter/Android defect
explains the remaining error, and numerical parity is already established.

The1K reference has18,377 target characters across117 TRAIN humans, approximately5–14
clips/person. Frozen B2 beam inference on all1024 TRAIN examples gives39.07% native and
42.43% phone-like CER, versus50.19%/52.70% on held-out DEV. TRAIN is a fitting diagnostic,
not accuracy. Within DAUN, TRAIN41.65%/42.33% is also better than DEV50.19%/52.70%; this
gap is not just the MacKenzie/DAUN composition difference.

There is insufficient evidence to call the problem pure overfitting: TRAIN fitting is
also weak. There is equally insufficient evidence to claim a hard geometry information
ceiling. The model can learn some characters and smaller repeated subsets; high-hand-
coverage TRAIN still has32.15%/35.98% CER. Missing observations contribute but do not
explain every error. More data cannot reconstruct missing observations.

The decisive pattern is that stronger fitting has not transferred reliably:

- B4 later TRAIN fitting improved while DEV worsened. Its lowest balanced TRAIN64
  diagnostic occurred at49, but DEV balanced CER there was57.62%; the selected epoch40
  had better DEV. Increasing capacity did not improve sparse correct-character count.
- The lower-rate1K check used all1024 samples for one complete requested cadence cycle.
  Loss fell to roughly27–28, but native/phone DEV CER was49.23%/53.05%, versus current
  residual49.52%/52.16%. Phone gained4 correct characters with70 more substitutions
  and35 more insertions. Do not promote it or override its failed continuation gate.
- Canonicalization, visual alternatives and publisher-window trimming did not establish
  a broad improvement. Cadence correction and fixed beam decoding already addressed
  their demonstrated problems and remain unchanged.

Three finishing epochs do not rule out every longer schedule. However, falling loss
alone was already shown to be an unreliable quality signal, and another same-data
schedule has no demonstrated advantage on held-out discrimination. Under the deadline,
adding supervised instances is better supported than another same-data architecture,
representation, boundary, decoder or optimization cycle. That is the basis for option2;
it is not a claim that a mathematically exhaustive1K search has been performed.

## What the expansion specifically addresses

Counts below were recomputed from the actual frozen manifests, independent of model
predictions or Candidate01 success. All original1024 complete rows remain included exactly.

| Quantity | TRAIN-1024 | TRAIN-4096 |
|---|---:|---:|
| Unique selected clip IDs |1024|4096|
| Official humans |117|117|
| Target characters including SPACE |18,377|76,985|
| DAUN / MacKenzie clips |512 /512|2048 /2048|
| Median clips/person |7|28|
| Q occurrences / humans with Q |20 /17|105 /71|
| X occurrences / humans with X |28 /24|132 /78|
| V occurrences / humans with V |173 /80|691 /115|
| M occurrences / humans with M |380 /108|1646 /117|
| U occurrences / humans with U |498 /110|2026 /117|

The benefit sought is more real handshape/motion examples, character contexts and
within-person variation. It does **not** add new TRAIN humans. Not every person's
count becomes large: one human still has only5 eligible clips. Q/X remain relatively
rare, and common-letter errors remain important. These counts support a supervision
intervention; they are not an accuracy prediction or proof of condition diversity.

## Concrete execution choice and verification

Use the already implemented, separate expanded-data loader/trainer; do not develop
another model or data pipeline. Reuse the original1K sources/raw/features unchanged;
materialize only3072 additions and256 confirmation DEV-B sequences on
`I:/AppHearData/FSboard_TRAIN4096_01`. Existing48/72-test preparation/training evidence
and engineering smoke remain available. No new code change is required for this decision.

Train one immutable copy of B2 epoch076: same193116-parameter causal TCN, Adapter.v1
`[T,405]`, real-observation cadence views, masks, CTC vocabulary and fixed beam10/penalty0.5.
The existing expanded trainer uses freshAdam0.0003 and historical raw-greedy balanced
DEV-A checkpoint selection; its final comparisons use the fixed deployed beam. Thus it
is a warm-start expanded-supervision experiment, **not a pure from-scratch data-size
ablation**. No new optimizer, decoder or checkpoint-selection tuning is introduced here.

The old residual is tied to the old frozen B2 state; do not attach it to updated B2
weights. Keep the current residual candidate/app intact. Compare new geometry to frozen
B2 for the data intervention and to the actual residual+beam candidate before promotion.
DEV-A remains256; DEV-B is256 fresh sequences for final confirmation only, with the same
15 official DEV signers. DEV-B is not an independent new-human TEST. TEST stays sealed.

The required verification is the trained result, not another preliminary model search:
full TRAIN fitting plus native/phone DEV CER, correct aligned characters, S/D/I, precision,
exact strings, character recall and signer spread. A gain in output length is insufficient.
The existing final-confirmation lock and broad discrimination checks remain unchanged.
If more examples again only trade deletions for substitutions/insertions, keep the old
model and stop; do not automatically expand further. No Android model is replaced here.

Preparation is still pending: no additional feature receipts were found onI:. This decision
does not claim that expanded data are training-ready. Commands and strict success guards
are in `docs/apphear-fingerspelling-quality-resolution-01-2026-10-05.md`; the managed
preparation entry point is `tools.fingerspelling.prepare_expansion`, followed by
`model.fingerspelling_train4096 preflight`, `train`, and final `evaluate`. The user executes
long operations locally; none is launched automatically.

## Preserved state

Branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`. Application baseline remains
`baseline/apphear-text-to-asl-context-assist-ui-2026-10-04` at
`cee71d9f181695847936eb5f3605ea37eab82a95`.

Only this decision report, new evidence and appended progress/memory notes are added.
WORD, Candidate01, Android, Adapter, checkpoints, existing datasets/runs, Context Assist
and decoder remain unchanged. No reset, merge, branch switch or deletion.
All11506 protected files were freshly rehashed with zero differences/missing files.
Evidence: `artifacts/fingerspelling_next_quality_decision_01/decision.json` and
`preservation.json`. No tests were rerun because no implementation changed; the previous
36-test finishing gate,72-test expanded trainer validation and engineering smoke are
existing evidence, not newly measured recognition results.

MOVE_TO_TRAIN4096_SUPERVISION_INTERVENTION
