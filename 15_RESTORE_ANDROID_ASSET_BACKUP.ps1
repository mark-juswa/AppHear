param(
  [string]$ProjectRoot = "F:\ASL DATASET\5. Apphear3",
  [string]$BackupDir = "",
  [switch]$SkipBuild
)
$ErrorActionPreference = "Stop"

$AndroidAssets = Join-Path $ProjectRoot "android\app\src\main\assets"
$Required = @("streaming.tflite", "model_manifest.json", "vocab.json", "recognition_config.json")

if ([string]::IsNullOrWhiteSpace($BackupDir)) {
  $latest = Get-ChildItem -Path $AndroidAssets -Directory -Filter "_backup_before_targeted_v3_ab_*" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if ($null -eq $latest) { throw "No targeted v3 A/B backup found under $AndroidAssets" }
  $BackupDir = $latest.FullName
}

foreach ($name in $Required) {
  $path = Join-Path $BackupDir $name
  if (-not (Test-Path $path)) { throw "Backup is missing required asset: $path" }
}

foreach ($name in $Required) {
  Copy-Item -Force (Join-Path $BackupDir $name) (Join-Path $AndroidAssets $name)
}

Write-Host "Restored Android assets from:"
Write-Host "  $BackupDir"

if (-not $SkipBuild) {
  Push-Location (Join-Path $ProjectRoot "android")
  try {
    .\gradlew.bat assembleDebug
    if ($LASTEXITCODE -ne 0) { throw "Android build failed after restoring backup." }
  } finally {
    Pop-Location
  }
  Write-Host "APK:"
  Write-Host "  $ProjectRoot\android\app\build\outputs\apk\debug\app-debug.apk"
}

