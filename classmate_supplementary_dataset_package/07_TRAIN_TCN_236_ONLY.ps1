param(
  [string]$DerivedRoot = "F:\ASL DATASET\ASL CITIZEN\derived\apphear3"
)
$ErrorActionPreference = "Stop"
$PackageRoot = $PSScriptRoot
$PipelineRoot = Join-Path $PackageRoot "apphear3_pipeline"
$TrainConfig = Join-Path $PackageRoot "config\train_streaming_local_plus_tcn_236_rtx3050.yaml"
$Log = Join-Path $PackageRoot "logs\train_local_plus_tcn_236_rtx3050.log"
$FeaturesDir = Join-Path $DerivedRoot "features_streaming_conversational_plus_pc_236_fps"

if (-not (Test-Path (Join-Path $FeaturesDir "train.npz"))) {
  throw "Missing FPS-augmented train features: $FeaturesDir\train.npz"
}
if (-not (Test-Path (Join-Path $FeaturesDir "val.npz"))) {
  throw "Missing FPS-augmented val features: $FeaturesDir\val.npz"
}

Set-Location $PipelineRoot
$python = Join-Path $PipelineRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Write-Host "Training 236-class TCN only, using existing features:"
Write-Host "  $FeaturesDir"
Write-Host "Log:"
Write-Host "  $Log"

$oldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
  & $python -m model.train_streaming --config $TrainConfig 2>&1 | Tee-Object -FilePath $Log
  $exitCode = $LASTEXITCODE
} finally {
  $ErrorActionPreference = $oldErrorActionPreference
}
if ($exitCode -ne 0) {
  throw "Training failed with exit code $exitCode. See log: $Log"
}
Write-Host "Training complete. Log: $Log"
