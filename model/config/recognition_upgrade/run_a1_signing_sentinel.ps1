param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Collect', 'Pull')]
    [string]$Command,

    [string]$SignerId = 'withheld_phone_01',
    [string]$SessionId = 'a1_signing_sentinel_01',
    [ValidateRange(1, 24)]
    [int]$StartAt = 1
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$android = Join-Path $root 'android'
$run = Join-Path $root 'artifacts\recognition_upgrade\a1_independent_clock\signing_sentinel_01'
$pullDir = Join-Path $run 'phone_bundles'
$queue = Join-Path $root 'context\recognition_upgrade\a1_signing_sentinel_01.csv'
$stage1 = Join-Path $root 'artifacts\recognition_upgrade\a1_independent_clock\device_benchmark_02\a1_device_benchmark_summary.json'
$apk = Join-Path $android 'app\build\outputs\apk\debug\app-debug.apk'
$localProperties = Join-Path $android 'local.properties'

if (-not (Test-Path -LiteralPath $stage1 -PathType Leaf)) { throw "Stage-1 summary not found: $stage1" }
$stage1Summary = Get-Content -Raw -LiteralPath $stage1 | ConvertFrom-Json
if (-not $stage1Summary.passed -or $stage1Summary.decision -ne 'PROCEED_TO_SMALL_SIGNING_SENTINEL') {
    throw "Stage 1 does not authorize the signing sentinel (decision=$($stage1Summary.decision))."
}
$maxPoseAgeMs = [int]$stage1Summary.max_pose_age_ms
if ($maxPoseAgeMs -le 0) { throw 'Stage-1 summary has no valid frozen pose-age ceiling.' }

$sdkLine = Get-Content -LiteralPath $localProperties | Where-Object { $_ -like 'sdk.dir=*' } | Select-Object -First 1
if (-not $sdkLine) { throw 'android/local.properties has no sdk.dir' }
$sdkPath = $sdkLine.Substring('sdk.dir='.Length).Replace('\:', ':').Replace('\\', '\')
$adb = Join-Path $sdkPath 'platform-tools\adb.exe'
if (-not (Test-Path -LiteralPath $adb -PathType Leaf)) { throw "adb.exe not found: $adb" }
$devices = @(& $adb devices | Select-Object -Skip 1 | Where-Object { $_ -match "\tdevice$" })
if ($devices.Count -ne 1) { throw "Expected exactly one authorized device; found $($devices.Count)." }

function Test-CameraPermission {
    $packageState = (& $adb shell dumpsys package com.example.apphear) -join "`n"
    return $packageState -match 'android\.permission\.CAMERA:\s+granted=true'
}

switch ($Command) {
    'Install' {
        New-Item -ItemType Directory -Force -Path $run | Out-Null
        Push-Location -LiteralPath $android
        try {
            & '.\gradlew.bat' testDebugUnitTest assembleDebug '-Pa1IndependentClock=true' '-PruD1=true' '--console=plain' '--no-daemon' '--max-workers=2'
            if ($LASTEXITCODE -ne 0) { throw 'A1 sentinel diagnostic build failed.' }
        } finally { Pop-Location }
        Copy-Item -LiteralPath $apk -Destination (Join-Path $run 'A1_SIGNING_SENTINEL.apk') -Force
        Get-FileHash -Algorithm SHA256 -LiteralPath $apk | Select-Object Algorithm, Hash, Path | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $run 'apk_sha256.json')
        & $adb install -r $apk | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'ADB install failed.' }
        if (-not (Test-CameraPermission)) {
            Write-Host 'On the phone, allow AppHear camera permission.' -ForegroundColor Yellow
            & $adb shell am start -n 'com.example.apphear/.A1BenchmarkActivity' --es a1_mode BASELINE --es a1_run_id PERMISSION_SETUP | Out-Host
            Read-Host 'After tapping Allow, press Enter here to continue'
            if (-not (Test-CameraPermission)) { throw 'Camera permission is still denied.' }
            & $adb shell am force-stop com.example.apphear
        }
        Write-Host "A1 SIGNING SENTINEL INSTALL COMPLETE (frozen max pose age: $maxPoseAgeMs ms)"
    }
    'Collect' {
        & (Join-Path $root 'eval\runtime_diagnostics\run_ru_d1_batch.ps1') `
            -SignerId $SignerId `
            -SessionId $SessionId `
            -QueuePath $queue `
            -StartAt $StartAt `
            -A1MaxPoseAgeMs $maxPoseAgeMs
        if ($LASTEXITCODE -ne 0) { throw "A1 sentinel collection failed: $LASTEXITCODE" }
        Write-Host 'A1 SIGNING SENTINEL COLLECTION COMPLETE'
    }
    'Pull' {
        New-Item -ItemType Directory -Force -Path $pullDir | Out-Null
        & $adb pull '/sdcard/Android/data/com.example.apphear/files/ru_d1/.' $pullDir
        if ($LASTEXITCODE -ne 0) { throw "ADB pull failed: $LASTEXITCODE" }
        Write-Host "A1 SIGNING SENTINEL PULL COMPLETE: $pullDir"
    }
}
