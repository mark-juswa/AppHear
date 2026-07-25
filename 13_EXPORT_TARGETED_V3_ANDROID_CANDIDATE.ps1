param(
  [string]$ProjectRoot = "F:\ASL DATASET\5. Apphear3",
  [string]$DerivedRoot = "F:\ASL DATASET\ASL CITIZEN\derived\apphear3"
)
$ErrorActionPreference = "Stop"

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RunDir = Join-Path $DerivedRoot "runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v3"
$BaselineAssets = Join-Path $DerivedRoot "runs\tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30\android_candidate_assets"
$CandidateAssets = Join-Path $RunDir "android_candidate_assets"
$ExportConfig = Join-Path $ProjectRoot "deploy\config\export_conversational_plus_local_pc_236_targeted_v3.yaml"

if (-not (Test-Path $Python)) { throw "Missing project venv Python: $Python" }
if (-not (Test-Path (Join-Path $RunDir "best.keras"))) { throw "Missing v3 model: $RunDir\best.keras" }
if (-not (Test-Path $ExportConfig)) { throw "Missing export config: $ExportConfig" }
foreach ($name in @("vocab.json", "recognition_config.json")) {
  $path = Join-Path $BaselineAssets $name
  if (-not (Test-Path $path)) { throw "Missing baseline asset to reuse: $path" }
}

Set-Location $ProjectRoot

Write-Host "Exporting targeted v3 candidate to INT8 TFLite"
Write-Host "  model:  $RunDir\best.keras"
Write-Host "  config: $ExportConfig"

& $Python -m deploy.export_tflite --config $ExportConfig
if ($LASTEXITCODE -ne 0) { throw "Targeted v3 TFLite export failed. Do not stage this model to Android." }

New-Item -ItemType Directory -Force -Path $CandidateAssets | Out-Null
Copy-Item -Force (Join-Path $RunDir "streaming.tflite") (Join-Path $CandidateAssets "streaming.tflite")
Copy-Item -Force (Join-Path $RunDir "model_manifest.json") (Join-Path $CandidateAssets "model_manifest.json")
Copy-Item -Force (Join-Path $BaselineAssets "vocab.json") (Join-Path $CandidateAssets "vocab.json")
Copy-Item -Force (Join-Path $BaselineAssets "recognition_config.json") (Join-Path $CandidateAssets "recognition_config.json")

Write-Host "Done. Android candidate assets prepared:"
Write-Host "  $CandidateAssets"
Write-Host "Next, stage with:"
Write-Host "  .\14_STAGE_TARGETED_V3_ANDROID_AB.ps1"
