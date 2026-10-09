param(
    [ValidateSet('Benchmark', 'Check')]
    [string]$Command = 'Benchmark',
    [ValidateRange(30, 120)]
    [int]$SecondsPerMode = 45
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$android = Join-Path $root 'android'
$run = Join-Path $root 'artifacts\recognition_upgrade\ru_d10\device_benchmark_01'
$logs = Join-Path $run 'logs'
$apks = Join-Path $run 'apks'
$python = Join-Path $root '.venv\Scripts\python.exe'

function Invoke-Check {
    & $python -m eval.runtime_diagnostics.ru_d10_phone_benchmark --run-dir $run
    if ($LASTEXITCODE -ne 0) { throw "RU-D10 benchmark check failed with exit code $LASTEXITCODE" }
}

if ($Command -eq 'Check') {
    Set-Location -LiteralPath $root
    Invoke-Check
    exit 0
}

$adbCandidates = @(
    'D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe',
    (Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe')
)
$adb = $adbCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $adb) { throw 'ADB was not found in the known Android SDK locations.' }
$deviceLines = & $adb devices | Select-Object -Skip 1 | Where-Object { $_ -match "\tdevice$" }
if (@($deviceLines).Count -ne 1) { throw "Expected exactly one authorized device; found $(@($deviceLines).Count)." }

New-Item -ItemType Directory -Force -Path $logs, $apks | Out-Null
$modes = @(
    @{ Name = 'BASELINE'; A = 'false'; B = 'false' },
    @{ Name = 'A_ONLY'; A = 'true'; B = 'false' },
    @{ Name = 'B_ONLY'; A = 'false'; B = 'true' },
    @{ Name = 'A_PLUS_B'; A = 'true'; B = 'true' }
)

Write-Host 'RU-D10 FOUR-MODE DEVICE BENCHMARK'
Write-Host "Each mode runs the unchanged recognition screen for $SecondsPerMode seconds."
Write-Host 'Keep the phone stationary with no hands in view and do not interact during each mode.'
Write-Host 'This does not collect training data or change production/release flags.'

foreach ($mode in $modes) {
    Write-Host "[$($mode.Name)] building A=$($mode.A) B=$($mode.B)"
    Push-Location -LiteralPath $android
    try {
        & '.\gradlew.bat' assembleDebug "-PruD10A=$($mode.A)" "-PruD10B=$($mode.B)" '-PruD1=false' '--console=plain' '--no-daemon' '--max-workers=2'
        if ($LASTEXITCODE -ne 0) { throw "Gradle failed for $($mode.Name)" }
    } finally {
        Pop-Location
    }
    $builtApk = Join-Path $android 'app\build\outputs\apk\debug\app-debug.apk'
    $savedApk = Join-Path $apks "$($mode.Name).apk"
    Copy-Item -LiteralPath $builtApk -Destination $savedApk -Force
    & $adb install -r $savedApk
    if ($LASTEXITCODE -ne 0) { throw "ADB install failed for $($mode.Name)" }
    & $adb logcat -c
    & $adb shell am force-stop com.example.apphear
    & $adb shell am start -n 'com.example.apphear/.RuD10BenchmarkActivity'
    if ($LASTEXITCODE -ne 0) { throw "Activity launch failed for $($mode.Name)" }
    Write-Host "[$($mode.Name)] measuring for $SecondsPerMode seconds; keep no hands in view"
    Start-Sleep -Seconds $SecondsPerMode
    $allLogs = & $adb logcat -d -v threadtime
    [IO.File]::WriteAllLines((Join-Path $logs "$($mode.Name).log"), $allLogs, [Text.UTF8Encoding]::new($false))
    & $adb shell am force-stop com.example.apphear
}

Set-Location -LiteralPath $root
Invoke-Check
Write-Host 'RU-D10 DEVICE BENCHMARK COMPLETE'
Write-Host "Timing CSV: $run\ru_d10_device_timing.csv"
Write-Host "Summary: $run\ru_d10_device_benchmark_summary.json"
