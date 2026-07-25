# AppHear 3 Local Supplementary 236-Class Run

Use this path to test whether `F:\ASL DATASET\local` improves the current deployable 236-class Android vocabulary.

This is separate from the 248-class experimental workflow. It does not include:

- BE
- DO
- EXCUSE_ME
- LISTEN
- LOOK
- ME
- MY
- NAME
- OKAY
- STOP
- THANKYOU
- WAKE

Those labels remain useful for a later 248-class experiment, but they are excluded here so this run can be compared directly against the current deployed 236-class model.

## Outputs

This run writes to new folders only:

```text
F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_recorded_local_pc_236
F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236
F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236_fps
F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30
```

The training log writes to:

```text
classmate_supplementary_dataset_package\logs\train_local_plus_tcn_236_rtx3050.log
```

## Commands

Open PowerShell in:

```text
F:\ASL DATASET\5. Apphear3\classmate_supplementary_dataset_package
```

Then run:

```powershell
.\00_SETUP_ENV.ps1
.\04_AUDIT_DATASETS_236.ps1
.\05_PREPARE_DATASETS_236.ps1
.\06_INGEST_MERGE_TRAIN_TCN_236_RTX3050.ps1
```

If hardlink preparation fails, run:

```powershell
.\05_PREPARE_DATASETS_236.ps1 -Mode copy
```

If your dataset is not at `F:\ASL DATASET\local`, pass the path:

```powershell
.\04_AUDIT_DATASETS_236.ps1 -LocalDataset "D:\path\to\local"
.\05_PREPARE_DATASETS_236.ps1 -LocalDataset "D:\path\to\local"
```

## After Training

Send back or inspect:

```text
reports\audit_236\audit_report.md
reports\audit_236\audit_manifest.csv
logs\train_local_plus_tcn_236_rtx3050.log
F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30
```

Do not copy the Keras model into Android assets. It must be evaluated on normal and low-FPS test sets, exported to TFLite, and checked against the manifest/parity gates first.
