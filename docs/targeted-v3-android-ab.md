# Targeted v3 Android A/B Test

Purpose: test the targeted v3 236-class model on Android without making it the permanent baseline.

Do not run this until the full 236-class regression audit has been reviewed. v3 improves several
problem words but regresses some other signs, so this is an experiment only.

## 1. Export v3 Android assets

From PowerShell:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\13_EXPORT_TARGETED_V3_ANDROID_CANDIDATE.ps1
```

This creates:

```text
F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v3\android_candidate_assets
```

If the export gate fails, stop. Do not stage or install v3.

## 2. Stage v3 into Android and build

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\14_STAGE_TARGETED_V3_ANDROID_AB.ps1
```

The script backs up the current Android model assets first, then builds:

```text
F:\ASL DATASET\5. Apphear3\android\app\build\outputs\apk\debug\app-debug.apk
```

## 3. Controlled signs to test

Test each sign three times and write the observed commits:

```text
CUT:
IMPORTANT:
SELL:
WANT:
KNOW:
FAMILY:
TEACH:
PUT:
WE:
```

Also test regression-risk signs:

```text
SHOP:
WAIT:
STREET:
SIT:
HEAR:
TIME:
THEN:
```

Keep the phone state consistent: same lighting, same distance, same camera, battery saver off,
and note the processed FPS from logcat.

## 4. Roll back

To restore the latest targeted-v3 backup:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\15_RESTORE_ANDROID_ASSET_BACKUP.ps1
```

Or restore a specific backup shown by the staging script:

```powershell
.\15_RESTORE_ANDROID_ASSET_BACKUP.ps1 -BackupDir "F:\ASL DATASET\5. Apphear3\android\app\src\main\assets\_backup_before_targeted_v3_ab_YYYYMMDD-HHMMSS"
```

## Decision rule

Keep v3 as a candidate only if it improves `SELL`, `WANT`, and `KNOW` on-device without causing
major regressions in `SHOP`, `WAIT`, `STREET`, `SIT`, `HEAR`, `TIME`, or `THEN`.
