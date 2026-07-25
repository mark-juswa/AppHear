param(
  [string]$ProjectRoot = "F:\ASL DATASET\5. Apphear3",
  [string]$DerivedRoot = "F:\ASL DATASET\ASL CITIZEN\derived\apphear3"
)
$ErrorActionPreference = "Stop"

$TrainConfig = Join-Path $ProjectRoot "model\config\train_streaming_conversational_plus_local_pc_236_targeted_v3.yaml"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "artifacts\targeted_confusion_audit_20260722"
$TrainLog = Join-Path $LogDir "train_targeted_236_v3_cpu.log"
$NormalFeatures = Join-Path $DerivedRoot "features_streaming_conversational_plus_pc_236"
$FpsFeatures = Join-Path $DerivedRoot "features_streaming_conversational_plus_pc_236_fps"
$OutDir = Join-Path $DerivedRoot "runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v3"
$AuditOut = Join-Path $ProjectRoot "artifacts\targeted_confusion_audit_20260722\targeted_v3"

if (-not (Test-Path $Python)) { throw "Missing project venv Python: $Python" }
if (-not (Test-Path $TrainConfig)) { throw "Missing training config: $TrainConfig" }
if (-not (Test-Path (Join-Path $FpsFeatures "train.npz"))) { throw "Missing FPS train features: $FpsFeatures" }
if (-not (Test-Path (Join-Path $FpsFeatures "val.npz"))) { throw "Missing FPS val features: $FpsFeatures" }
if (-not (Test-Path (Join-Path $NormalFeatures "test.npz"))) { throw "Missing held-out test features: $NormalFeatures" }

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $ProjectRoot

Write-Host "Training targeted 236-class low-FPS experiment v3"
Write-Host "  config: $TrainConfig"
Write-Host "  output: $OutDir"
Write-Host "  log:    $TrainLog"

$oldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
  & $Python -m model.train_streaming --config $TrainConfig 2>&1 | Tee-Object -FilePath $TrainLog
  $exitCode = $LASTEXITCODE
} finally {
  $ErrorActionPreference = $oldErrorActionPreference
}
if ($exitCode -ne 0) {
  throw "Training failed with exit code $exitCode. See log: $TrainLog"
}

Write-Host "Running targeted confusion audit for v3"
& $Python -m eval.targeted_confusion `
  --config $TrainConfig `
  --features-dir $NormalFeatures `
  --fps-features-dir $FpsFeatures `
  --out-dir $AuditOut
if ($LASTEXITCODE -ne 0) {
  throw "Targeted audit failed."
}

Write-Host "Done. Review:"
Write-Host "  $AuditOut\targeted_confusion_audit.md"
Write-Host "Do not deploy this model until v3 is compared against baseline, v1, and v2."
