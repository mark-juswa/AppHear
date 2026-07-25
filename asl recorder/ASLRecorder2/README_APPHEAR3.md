# ASL Recorder — AppHear 3 (Stage-E video capture)

Rebuilt 2026-07-10 from the AppHear 2 recorder to feed the **AppHear 3** pipeline. It records **ASL**
video clips for the 250 everyday words (especially data-poor / missing glosses) so they can
supplement or replace ASL Citizen's clips for those signs, then retrain.

**Full contract, ingest usage, and honest limits:** `context/recorder-pipeline.md` in the AppHear 3
repo. Read that first.

## What it does now (vs the old AppHear 2 recorder)
- **Records VIDEO** (upright, ~3s, native fps) as the dataset artifact + a Stage-E metadata sidecar.
  The offline pipeline re-extracts landmarks from the video with the SAME extractor as ASL Citizen →
  identical landmark dialect. No baked features, no fixed 30-frame window, no on-device normalization.
- **MediaPipe IMAGE mode, hand+pose, face removed** (matches AppHear 3). On-device landmarks drive the
  live overlay + advisory coverage only — not the dataset.
- **Non-destructive**: every clip is kept; the offline Q stage + review decide what trains.
- **`labels.json`** = the 250 words, each mapped to its canonical ASL Citizen `gloss`.

Output: `AppHearDataset/samples/signs/<word>/<clip>.mp4` + `<clip>.json`.

## Developer TODO (agent could not do in-tool)
1. **Build in Android Studio** (the agent can't compile Android; same as the main app).
2. **Delete** `app/src/main/assets/face_landmarker.task` — unused now (face removed).
3. *(optional)* copy AppHear 3's exact `hand_landmarker.task` + `pose_landmarker_lite.task` into
   `app/src/main/assets/` — not required for parity (video re-extraction guarantees it), only so the
   live overlay matches the runtime.
4. The 3 emptied `app/.../ml/` classes (KeypointExtractor, LandmarkFrameBuffer, SampleQualityAnalyzer)
   are placeholders — safe to delete the files.

## Ingest (on the PC, in the AppHear 3 `.venv`)
```
python -m pipeline.ingest.run   --recorded-root "<...>/AppHearDataset" --out ".../features_streaming_recorded"
python -m pipeline.ingest.merge --recorded ".../features_streaming_recorded/recorded.npz" --mode supplement
# then retrain on the merged dir (see context/recorder-pipeline.md)
```
