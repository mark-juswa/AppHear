param(
  [string]$PreparedRoot = "work\prepared_local\AppHearDataset",
  [string]$DerivedRoot = "F:\ASL DATASET\ASL CITIZEN\derived\apphear3"
)
$ErrorActionPreference = "Stop"
$PackageRoot = $PSScriptRoot
$PipelineRoot = Join-Path $PackageRoot "apphear3_pipeline"
$PreparedAbs = Resolve-Path (Join-Path $PackageRoot $PreparedRoot)
$RecordedOut = Join-Path $DerivedRoot "features_streaming_recorded_local"
$MergedOut = Join-Path $DerivedRoot "features_streaming_conversational_plus"
$MergedFpsOut = Join-Path $DerivedRoot "features_streaming_conversational_plus_fps"
$BaseVocab = Join-Path $DerivedRoot "features_conversational\vocab.json"
$ExpandedVocabDir = Join-Path $DerivedRoot "features_conversational_plus_experimental"
$Vocab = Join-Path $ExpandedVocabDir "vocab.json"
$ConvClean = Join-Path $DerivedRoot "features_streaming_conversational"
$TrainConfig = Join-Path $PackageRoot "config\train_streaming_local_plus_tcn_rtx3050.yaml"
$Log = Join-Path $PackageRoot "logs\train_local_plus_tcn_rtx3050.log"

Set-Location $PipelineRoot
$python = Join-Path $PipelineRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Write-Host "Step 1/5: build expanded experimental vocab"
& $python ..\scripts\build_experimental_vocab.py --base-vocab $BaseVocab --out-dir $ExpandedVocabDir --experimental-includes ..\config\include_experimental_labels.json

Write-Host "Step 2/5: ingest local videos through AppHear 3 pipeline"
& $python -m pipeline.ingest.run --recorded-root $PreparedAbs --out $RecordedOut --vocab $Vocab

Write-Host "Step 3/5: merge local clips into TRAIN only"
& $python -m pipeline.ingest.merge --recorded (Join-Path $RecordedOut "recorded.npz") --mode supplement --conv-dir $ConvClean --out $MergedOut --vocab $Vocab

Write-Host "Step 4/5: create FPS-augmented training features"
& $python -m pipeline.features.fps_augment --mode expand --in-dir $MergedOut --out-dir $MergedFpsOut --n-copies 3 --kmax 10 --min-frames 4

Write-Host "Step 5/5: train TCN with RTX 3050 4GB-safe config"
& $python -m model.train_streaming --config $TrainConfig 2>&1 | Tee-Object -FilePath $Log
Write-Host "Training complete or stopped. Log: $Log"


