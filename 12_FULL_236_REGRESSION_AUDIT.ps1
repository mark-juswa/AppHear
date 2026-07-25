param(
  [string]$ProjectRoot = "F:\ASL DATASET\5. Apphear3",
  [string]$DerivedRoot = "F:\ASL DATASET\ASL CITIZEN\derived\apphear3"
)
$ErrorActionPreference = "Stop"

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Features = Join-Path $DerivedRoot "features_streaming_conversational_plus_pc_236"
$FpsFeatures = Join-Path $DerivedRoot "features_streaming_conversational_plus_pc_236_fps"
$Runs = Join-Path $DerivedRoot "runs"
$BaselineRun = Join-Path $Runs "tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30"
$OutDir = Join-Path $ProjectRoot "artifacts\targeted_confusion_audit_20260722\full_236_regression"
$Vocab = Join-Path $BaselineRun "android_candidate_assets\vocab.json"

if (-not (Test-Path $Python)) { throw "Missing project venv Python: $Python" }
if (-not (Test-Path (Join-Path $Features "test.npz"))) { throw "Missing held-out test features: $Features" }
if (-not (Test-Path (Join-Path $FpsFeatures "val.npz"))) { throw "Missing FPS val features: $FpsFeatures" }
if (-not (Test-Path $Vocab)) { throw "Missing vocab: $Vocab" }

Set-Location $ProjectRoot
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

& $Python -m eval.full_regression `
  --features-dir $Features `
  --fps-features-dir $FpsFeatures `
  --vocab $Vocab `
  --out-dir $OutDir `
  --model "baseline=$BaselineRun\best.keras" `
  --model "v1=$Runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v1\best.keras" `
  --model "v2=$Runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v2\best.keras" `
  --model "v3=$Runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v3\best.keras" `
  --model "v4=$Runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v4\best.keras"

if ($LASTEXITCODE -ne 0) { throw "Full 236-class regression audit failed." }

Write-Host "Done. Review:"
Write-Host "  $OutDir\full_regression_audit.md"
