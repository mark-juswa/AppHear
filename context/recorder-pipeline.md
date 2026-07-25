# ASL Recorder → Pipeline (secondary data capture)

*How the rebuilt ASL Recorder (`asl recorder/ASLRecorder2/`) feeds the AppHear 3 pipeline. Its job:
let local **ASL** signers record clips for **data-poor or missing glosses** so we can supplement (or
replace) ASL Citizen's clips for those signs and retrain. Rebuilt 2026-07-10 from the AppHear 2
recorder, which was fundamentally incompatible (VIDEO mode + face + baked 258 vector).*

## The one principle: capture RAW (video), decide OFFLINE

ASL Citizen is a **video** dataset; its landmarks were made by `pipeline/extract` (MediaPipe IMAGE
mode, face-off). So the recorder is **video-primary**: it saves the ASL video as the dataset
artifact, and the SAME `pipeline/extract` re-extracts it → **guaranteed identical landmark dialect**,
by construction. The recorder does NO normalization, NO feature-baking, NO trimming, NO destructive
quality gate — all of that is the offline pipeline's job (D1/D2 → N1–N4 → F). On-device MediaPipe
runs only for the live overlay + an advisory hand/pose-coverage hint.

Consequence: because parity is enforced at re-extraction, the recorder's on-device models do **not**
need to be byte-identical to the pipeline's. That removes the whole train/serve-dialect risk.

## What the recorder outputs

`AppHearDataset/samples/signs/<word>/` holds paired files per attempt:
- **`<clip>.mp4`** — upright, ~3s (RecordingStateMachine `RECORDING_DURATION_MS`), native fps. THE
  dataset artifact.
- **`<clip>.json`** — Stage-E sidecar: `word`, mapped **`gloss`** (canonical ASL Citizen gloss from
  `labels.json`), `source:"aslrecorder2"`, `signer_id`, `native_fps` (nominal — ingest reads the real
  fps from the mp4), dims, and advisory `hand_hit_rate`/`pose_hit_rate`. NO baked features.

Non-destructive: every clip is kept (`accepted:true`); the offline Q stage + human review are the gate.

`labels.json` = the **250 everyday words**, each mapped to its ASL Citizen gloss (built + verified by
the ingest against `features/vocab.json`): 227 mappable, 53 data-poor (≤12 clips, prime targets), 12
pointing-only (`gloss:null` — record indexing or skip), 21 not-in-ASL-Citizen (would form NEW classes).

## Ingest → merge → retrain (Python, `.venv`)

1. Copy `AppHearDataset/` off the phone to the PC.
2. **Ingest** — re-extract + build v3.0 streaming features mapped to the conversational 236 vocab
   (composes the SAME extract → detect → `clip_features_realtimed` clip functions; skips glosses not
   in the target vocab and clips with no valid signing span):
   ```
   python -m pipeline.ingest.run --recorded-root "<...>/AppHearDataset" \
       --out "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/features_streaming_recorded"
   ```
3. **Merge** into the conversational feature set (recorded clips go to TRAIN only — val/test stay
   pure ASL Citizen so cross-signer eval still measures generalization):
   ```
   python -m pipeline.ingest.merge --recorded "<...>/features_streaming_recorded/recorded.npz" --mode supplement
   ```
   `supplement` = add alongside ASL Citizen (default; best for data-poor glosses). `replace` = swap a
   gloss's ASL Citizen clips for the recorded ones (only when the ASL Citizen clips are genuinely
   wrong — **risks cross-signer generalization** if few local signers). Writes to
   `features_streaming_conversational_plus/` (or `_replaced/`).
4. **Retrain** — clone `train_streaming_conversational.yaml` (or the GCN config), point `features_dir`
   at the merged dir, new `output_dir`, train in `.venv`; eval native/k4/k8; deploy with backup.

## Honest limits (what recording CAN and CANNOT fix)

- **CAN**: data-poor glosses (add clips → the biggest lever for WHERE·8, ASK·9, HELLO·11), missing
  signs (new classes), signer diversity (more signers >> more reps — a few signers × many reps
  **overfits** that class).
- **CANNOT**: confusable near-synonyms (SIT↔CHAIR are the same handshape — more data won't separate
  them; only dropping one will), or the architecture limit (that's the ST-GCN work, `encoder-upgrade.md`).
- **ASL only.** FSL versions of a gloss are a *different sign* under the same English label →
  catastrophic label noise if mixed. FSL would be a separate dataset + model.

## Safety net
Everything writes to NEW dirs (`features_streaming_recorded`, `features_streaming_conversational_plus`);
ASL Citizen data, `features_streaming_conversational`, and the deployed model are never touched. Retrains
go to new run dirs. The recorder is a copy — the original AppHear 2 recorder elsewhere is untouched.

## Recorder app internals (for whoever maintains it)
Java/CameraX. Video-primary rewrite: `MediaPipeRecorderHelper` (IMAGE mode, hand+pose, face removed),
`SampleData` (Stage-E sidecar), `RecordingActivity` (video capture + advisory coverage),
`RecordingStateMachine` (timer-based clip end), `DatasetFileManager` (flat non-destructive layout),
`LabelsRepository` (word→gloss). The 3 `ml/` classes (KeypointExtractor/LandmarkFrameBuffer/
SampleQualityAnalyzer) are emptied placeholders — safe to delete the files. **Developer TODO:** delete
`app/src/main/assets/face_landmarker.task` (unused); build in Android Studio (agent can't compile it).
