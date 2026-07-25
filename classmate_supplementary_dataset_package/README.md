# AppHear 3 Supplementary Dataset Package

This folder is a clean handoff package for running the local/classmate supplementary dataset workflow without learning the full AppHear 3 repository first.

It supports all three downloaded dataset folders under:

```text
F:\ASL DATASET\local\1
F:\ASL DATASET\local\2
F:\ASL DATASET\local\3
```

The local data is treated as **supplementary TRAIN-only data**. It does not replace ASL Citizen. Validation/test stay ASL Citizen-only so the result still measures held-out signer generalization.


## Experimental Expanded Vocabulary Mode

This package now includes the developer-requested test labels that are not part of the current deployed 236-class app vocabulary:

```text
STOP, NAME, OKAY, WAKE, LOOK, LISTEN, ME, MY, THANKYOU, EXCUSE_ME, BE, DO
```

These are controlled by:

```text
config\include_experimental_labels.json
```

Because these labels expand the vocabulary from 236 to 248 classes, any model trained with this package is an **experimental test model**, not a drop-in deployed app model until it is evaluated and exported with the matching expanded vocab/manifest. This is intentional for testing only.
## Hardware Target

Classmate machine: RTX 3050 with **4 GB VRAM**.

The included training config uses a conservative TCN batch size of **32**:

```text
config\train_streaming_local_plus_tcn_rtx3050.yaml
```

If CUDA reports out-of-memory, open that file and change:

```yaml
batch_size: 32
```

to:

```yaml
batch_size: 16
```

Do not start with the GCN/ST-GCN experiment on a 4 GB card. This package is for the safer supplementary-data TCN retrain first.

## What This Package Contains

```text
apphear3_pipeline\      Minimal copy of the working AppHear 3 pipeline/model/eval/export code
assets\mediapipe\      Hand and pose MediaPipe task files inside apphear3_pipeline
config\labels.json     Word-to-ASL-Citizen gloss mapping
config\deployed_vocab.json
scripts\               Dataset audit and preparation helpers
work\                  Prepared local dataset output goes here
reports\               Audit report output goes here
logs\                  Training logs go here
```

## Important Rules

1. Do not train directly from old baked `frames` in JSON files.
2. Always re-extract from `.mp4` videos through the AppHear 3 pipeline.
3. Local/classmate clips go to TRAIN only.
4. ASL Citizen validation/test must remain unchanged.
5. Unsupported labels are skipped unless explicitly remapped later.
6. Keep the current v3.0 258-feature contract unchanged.

## Expected External Data

This package assumes these folders exist on the machine:

```text
F:\ASL DATASET\local
F:\ASL DATASET\ASL CITIZEN\derived\apphear3
```

The ASL Citizen derived folder must already contain at least:

```text
features_conversational\vocab.json
features_streaming_conversational\train.npz
features_streaming_conversational\val.npz
features_streaming_conversational\test.npz
runs\tcn_streaming_conversational_fps_v30\best.keras
```

## Step 0 - Set Up Python Environment

Open PowerShell in this package folder and run:

```powershell
.\00_SETUP_ENV.ps1
```

If `py -3.11` is not installed, install Python 3.11 first. Use the created virtual environment under `apphear3_pipeline\.venv` for the workflow.

## Step 1 - Audit Dataset 1, 2, and 3

```powershell
.\01_AUDIT_DATASETS.ps1
```

Outputs:

```text
reports\audit_report.md
reports\audit_manifest.csv
```

Read `audit_report.md` before continuing. The known local audit result from the developer machine was:

- 4,035 JSON sidecars parsed
- 4,055 videos found
- 3,654 clips usable after mapping to the target vocabulary
- 381 clips skipped/manual-review
- Safe remaps include `GOODBYE -> BYE`, `WANT -> WANT2`, `WHAT -> WHAT1`, and `THANK_YOU -> THANKYOU`

## Step 2 - Prepare a Clean Recorder-Style Dataset

```powershell
.\02_PREPARE_DATASETS.ps1
```

Default mode is `hardlink`, which avoids duplicating gigabytes of video. If hardlink fails on another drive, run:

```powershell
.\02_PREPARE_DATASETS.ps1 -Mode copy
```

Output:

```text
work\prepared_local\AppHearDataset
```

This folder is what the real AppHear ingest step consumes.

## Step 3 - Ingest, Merge, FPS-Augment, and Train

This is the long step. It re-extracts MediaPipe landmarks from the local videos, merges usable local clips into TRAIN only, creates FPS-augmented features, and trains a new TCN run.

```powershell
.\03_INGEST_MERGE_TRAIN_TCN_RTX3050.ps1
```

Outputs are written under:

```text
F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_recorded_local
F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus
F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_fps
F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_rtx3050_v30
```

Training log:

```text
logs\train_local_plus_tcn_rtx3050.log
```

## What Success Looks Like

The training step should create:

```text
best.keras
final.keras
history.csv
```

inside:

```text
F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_rtx3050_v30
```

After that, send the run folder and log back to the developer for evaluation/export/deployment. Do not manually replace Android app assets. This run uses an expanded 248-class test vocabulary.

## If Something Fails

- If setup fails: confirm Python 3.11 is installed.
- If MediaPipe import fails: rerun `00_SETUP_ENV.ps1`.
- If the ingest says many clips have no valid span: send the log back; do not lower thresholds manually.
- If GPU OOM occurs: set batch size to 16 in `config\train_streaming_local_plus_tcn_rtx3050.yaml`.
- If training is slow: CPU fallback may be happening. It can still run, but will be much slower than GPU.

## Do Not Do These

- Do not replace ASL Citizen with local data.
- Do not put local/classmate clips into val/test.
- Do not use the failed ST-GCN result.
- Do not change the 258 feature schema.
- Do not train from old JSON `frames` arrays.
- Do not manually copy model files into Android assets without eval/export approval, especially because this package can train a 248-class experimental vocabulary.


