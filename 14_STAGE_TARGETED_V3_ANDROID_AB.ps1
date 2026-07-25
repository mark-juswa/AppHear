param(
  [string]$ProjectRoot = "F:\ASL DATASET\5. Apphear3",
  [string]$DerivedRoot = "F:\ASL DATASET\ASL CITIZEN\derived\apphear3",
  [switch]$SkipBuild
)
$ErrorActionPreference = "Stop"

$CandidateAssets = Join-Path $DerivedRoot "runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v3\android_candidate_assets"
$AndroidAssets = Join-Path $ProjectRoot "android\app\src\main\assets"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupDir = Join-Path $AndroidAssets "_backup_before_targeted_v3_ab_$Stamp"
$Required = @("streaming.tflite", "model_manifest.json", "vocab.json", "recognition_config.json")

foreach ($name in $Required) {
  $path = Join-Path $CandidateAssets $name
  if (-not (Test-Path $path)) { throw "Missing v3 candidate asset: $path. Run .\13_EXPORT_TARGETED_V3_ANDROID_CANDIDATE.ps1 first." }
}
foreach ($name in $Required) {
  $path = Join-Path $AndroidAssets $name
  if (-not (Test-Path $path)) { throw "Missing current Android asset to back up: $path" }
}

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
foreach ($name in $Required) {
  Copy-Item -Force (Join-Path $AndroidAssets $name) (Join-Path $BackupDir $name)
}

foreach ($name in $Required) {
  Copy-Item -Force (Join-Path $CandidateAssets $name) (Join-Path $AndroidAssets $name)
}

Write-Host "Staged targeted v3 Android A/B assets."
Write-Host "Backup created:"
Write-Host "  $BackupDir"

if (-not $SkipBuild) {
  Push-Location (Join-Path $ProjectRoot "android")
  try {
    .\gradlew.bat assembleDebug
    if ($LASTEXITCODE -ne 0) { throw "Android build failed after staging v3 assets. Restore with .\15_RESTORE_ANDROID_ASSET_BACKUP.ps1 from the project root." }
  } finally {
    Pop-Location
  }
  Write-Host "APK:"
  Write-Host "  $ProjectRoot\android\app\build\outputs\apk\debug\app-debug.apk"
}

Write-Host "Rollback command:"
Write-Host "  cd `"$ProjectRoot`""
Write-Host "  .\15_RESTORE_ANDROID_ASSET_BACKUP.ps1 -BackupDir `"$BackupDir`""

