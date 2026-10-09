param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Collect', 'Pull', 'MakeAnnotations', 'Replay', 'Check')]
    [string]$Command,

    [string]$SignerId = 'withheld_phone_01',
    [string]$SessionId = 'ru_d7_phone_bc_01',
    [ValidateRange(1, 26)]
    [int]$StartAt = 1
)

$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $workspace '.venv\Scripts\python.exe'
$queue = Join-Path $workspace 'context\recognition_upgrade\ru_d7_phone_bc_queue.csv'
$runDir = Join-Path $workspace 'artifacts\recognition_upgrade\ru_d7\phone_bc_01'
$pullDir = Join-Path $runDir 'phone_bundles'
$annotations = Join-Path $runDir 'annotations.csv'
$localProperties = Join-Path $workspace 'android\local.properties'
$sdkLine = Get-Content -LiteralPath $localProperties | Where-Object { $_ -like 'sdk.dir=*' } | Select-Object -First 1
if (-not $sdkLine) { throw 'android/local.properties has no sdk.dir' }
$sdkPath = $sdkLine.Substring('sdk.dir='.Length).Replace('\:', ':').Replace('\\', '\')
$adb = Join-Path $sdkPath 'platform-tools\adb.exe'
if (-not (Test-Path -LiteralPath $adb -PathType Leaf)) { throw "adb.exe not found: $adb" }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Python not found: $python" }
Set-Location -LiteralPath $workspace
$env:TF_ENABLE_ONEDNN_OPTS = '0'

switch ($Command) {
    'Install' {
        Push-Location (Join-Path $workspace 'android')
        try {
            & '.\gradlew.bat' assembleDebug '-PruD1=true'
            if ($LASTEXITCODE -ne 0) { throw "RU-D1 diagnostic build failed: $LASTEXITCODE" }
        } finally { Pop-Location }
        & $adb install -r (Join-Path $workspace 'android\app\build\outputs\apk\debug\app-debug.apk')
        if ($LASTEXITCODE -ne 0) { throw "APK install failed: $LASTEXITCODE" }
        Write-Host 'INSTALL COMPLETE - production behavior is unchanged; RU diagnostics are debug-only.'
    }
    'Collect' {
        & (Join-Path $workspace 'eval\runtime_diagnostics\run_ru_d1_batch.ps1') `
            -SignerId $SignerId -SessionId $SessionId -QueuePath $queue -StartAt $StartAt
        if ($LASTEXITCODE -ne 0) { throw "Collection launcher failed: $LASTEXITCODE" }
    }
    'Pull' {
        New-Item -ItemType Directory -Force -Path $pullDir | Out-Null
        & $adb pull '/sdcard/Android/data/com.example.apphear/files/ru_d1/.' $pullDir
        if ($LASTEXITCODE -ne 0) { throw "ADB pull failed: $LASTEXITCODE" }
        Write-Host "PULL COMPLETE: $pullDir"
    }
    'MakeAnnotations' {
        & $python -m eval.runtime_diagnostics.ru_d7_phone_bc annotations $pullDir --run-dir $runDir --output $annotations
        if ($LASTEXITCODE -ne 0) { throw "Annotation template failed: $LASTEXITCODE" }
        Write-Host "Review bounded evidence and complete: $annotations"
    }
    'Replay' {
        & $python -m eval.runtime_diagnostics.ru_d7_phone_bc replay $pullDir $annotations --run-dir $runDir
        if ($LASTEXITCODE -ne 0) { throw "B/C replay failed: $LASTEXITCODE" }
        & $python -m eval.runtime_diagnostics.ru_d7_phone_bc check --run-dir $runDir --require-results
        if ($LASTEXITCODE -ne 0) { throw "RU-D7 result check failed: $LASTEXITCODE" }
        Write-Host "RU-D7 REPLAY COMPLETE: $runDir\reports\ru_d7_phone_bc_report.json"
    }
    'Check' {
        & $python -m eval.runtime_diagnostics.ru_d7_phone_bc check --run-dir $runDir
        if ($LASTEXITCODE -ne 0) { throw "RU-D7 preflight failed: $LASTEXITCODE" }
    }
}
