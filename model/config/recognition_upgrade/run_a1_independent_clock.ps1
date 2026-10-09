param(
    [ValidateSet('Benchmark', 'Check')]
    [string]$Command = 'Benchmark',
    [ValidateRange(60, 300)]
    [int]$SecondsPerMode = 120,
    [ValidateRange(10, 60)]
    [int]$WarmupSeconds = 20,
    [ValidateRange(2, 15)]
    [int]$SampleEverySeconds = 5
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$android = Join-Path $root 'android'
$run = Join-Path $root 'artifacts\recognition_upgrade\a1_independent_clock\device_benchmark_02'
$python = Join-Path $root '.venv\Scripts\python.exe'
$evaluator = Join-Path $root 'eval\runtime_diagnostics\a1_phone_benchmark.py'
$apk = Join-Path $android 'app\build\outputs\apk\debug\app-debug.apk'
$finalSummary = Join-Path $run 'a1_device_benchmark_summary.json'

function Invoke-Summarize([string]$Name) {
    $log = Join-Path $run "$Name.log"
    $memory = Join-Path $run "$Name.memory.csv"
    $summary = Join-Path $run "$Name`_summary.json"
    $measuredSeconds = $SecondsPerMode - $WarmupSeconds
    & $python $evaluator summarize --log $log --memory $memory --warmup-seconds $WarmupSeconds --expected-seconds $measuredSeconds --output $summary | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "A1 summary failed for ${Name}" }
    return $summary
}

function Invoke-Check {
    & $python $evaluator compare --run-dir $run --output $finalSummary | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'A1 comparison failed.' }
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

New-Item -ItemType Directory -Force -Path $run | Out-Null
Push-Location -LiteralPath $android
try {
    & '.\gradlew.bat' testDebugUnitTest assembleDebug '-Pa1IndependentClock=true' '-PruD1=false' '--console=plain' '--no-daemon' '--max-workers=2'
    if ($LASTEXITCODE -ne 0) { throw 'A1 instrumented build failed.' }
} finally {
    Pop-Location
}
Copy-Item -LiteralPath $apk -Destination (Join-Path $run 'A1_INSTRUMENTED.apk') -Force
Get-FileHash -Algorithm SHA256 -LiteralPath $apk | Select-Object Algorithm, Hash, Path | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $run 'apk_sha256.json')
# Some Xiaomi/MIUI builds deny both `pm grant` and PackageInstaller's `-g` flag to the ADB
# shell user. Install normally, then verify permission and use the explicit on-phone prompt below.
& $adb install -r $apk | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'ADB install failed.' }

function Test-CameraPermission {
    $packageState = (& $adb shell dumpsys package com.example.apphear) -join "`n"
    return $packageState -match 'android\.permission\.CAMERA:\s+granted=true'
}

if (-not (Test-CameraPermission)) {
    Write-Host 'This phone blocks ADB from granting runtime permissions.' -ForegroundColor Yellow
    Write-Host 'The app will open once. On the phone, tap Allow for the camera permission.' -ForegroundColor Yellow
    & $adb shell am force-stop com.example.apphear
    & $adb shell am start -n 'com.example.apphear/.A1BenchmarkActivity' --es a1_mode BASELINE --es a1_run_id PERMISSION_SETUP | Out-Host
    Read-Host 'After tapping Allow on the phone, press Enter here to continue'
    if (-not (Test-CameraPermission)) {
        throw 'Camera permission is still denied. Enable Camera under Settings > Apps > AppHear > Permissions, then rerun.'
    }
    & $adb shell am force-stop com.example.apphear
}

function Invoke-Mode([string]$Name, [string]$Mode, [long]$MaxPoseAgeMs) {
    $logPath = Join-Path $run "$Name.log"
    $logErrorPath = Join-Path $run "$Name.logcat.stderr.txt"
    $memoryPath = Join-Path $run "$Name.memory.csv"
    Set-Content -Encoding ascii -LiteralPath $memoryPath -Value 'elapsed_s,pss_kb,thermal_status'
    & $adb logcat -c
    $logcat = Start-Process -FilePath $adb `
        -ArgumentList @('logcat', '-v', 'threadtime', 'AppHearA1:I', 'AppHearRecog:I', 'AndroidRuntime:E', 'ActivityManager:E', 'libc:F', '*:S') `
        -RedirectStandardOutput $logPath `
        -RedirectStandardError $logErrorPath `
        -WindowStyle Hidden `
        -PassThru
    try {
        & $adb shell am force-stop com.example.apphear
        $launch = @('shell', 'am', 'start', '-n', 'com.example.apphear/.A1BenchmarkActivity', '--es', 'a1_mode', $Mode, '--es', 'a1_run_id', $Name)
        if ($Mode -eq 'A1') { $launch += @('--el', 'a1_max_pose_age_ms', $MaxPoseAgeMs.ToString()) }
        & $adb @launch | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "Activity launch failed for $Name" }
        Write-Host "[$Name] ${Mode}: $WarmupSeconds s warm-up + $($SecondsPerMode - $WarmupSeconds) s measured; keep the phone stationary with no hands visible."
        $elapsed = 0
        while ($elapsed -lt $SecondsPerMode) {
            Start-Sleep -Seconds $SampleEverySeconds
            $elapsed += $SampleEverySeconds
            $mem = (& $adb shell dumpsys meminfo com.example.apphear) -join "`n"
            $pss = ''
            if ($mem -match 'TOTAL PSS:\s+(\d+)') { $pss = $Matches[1] }
            elseif ($mem -match '(?m)^\s*TOTAL\s+(\d+)') { $pss = $Matches[1] }
            $thermalRaw = (& $adb shell cmd thermalservice get-status 2>$null) -join ''
            $thermal = if ($thermalRaw -match '-?\d+') { $Matches[0] } else { '' }
            Add-Content -Encoding ascii -LiteralPath $memoryPath -Value "$elapsed,$pss,$thermal"
            Write-Progress -Activity 'A1 no-sign benchmark' -Status "${Name}: $elapsed / $SecondsPerMode seconds" -PercentComplete ([math]::Min(100, 100 * $elapsed / $SecondsPerMode))
        }
    } finally {
        & $adb shell am force-stop com.example.apphear
        Start-Sleep -Seconds 1
        if (-not $logcat.HasExited) {
            Stop-Process -Id $logcat.Id -ErrorAction SilentlyContinue
        }
        Wait-Process -Id $logcat.Id -ErrorAction SilentlyContinue
    }
    return Invoke-Summarize $Name
}

Write-Host 'A1 ORDER-BALANCED NO-SIGN BENCHMARK: BASELINE_1 -> A1_1 -> A1_2 -> BASELINE_2'
Write-Host 'The A1 pose-age ceiling is frozen from BASELINE_1 before either A1 run.'
$baseline1Summary = Invoke-Mode 'BASELINE_1' 'BASELINE' 0
$baseline1 = Get-Content -Raw -LiteralPath $baseline1Summary | ConvertFrom-Json
$maxPoseAgeMs = [math]::Ceiling($baseline1.pose_age_ms.p95 + $baseline1.inter_hand_publication_gap_ms.p95)
if ($maxPoseAgeMs -le 0) { throw 'Could not derive a positive max pose age from BASELINE_1.' }
Set-Content -Encoding ascii -LiteralPath (Join-Path $run 'preregistered_pose_age_ms.txt') -Value $maxPoseAgeMs
Write-Host "Frozen A1 maximum pose age: $maxPoseAgeMs ms"

Invoke-Mode 'A1_1' 'A1' $maxPoseAgeMs | Out-Null
Invoke-Mode 'A1_2' 'A1' $maxPoseAgeMs | Out-Null
Invoke-Mode 'BASELINE_2' 'BASELINE' 0 | Out-Null
Set-Location -LiteralPath $root
Invoke-Check
Write-Host 'A1 DEVICE BENCHMARK COMPLETE'
Write-Host "Summary: $finalSummary"
Write-Host 'If decision is REJECT_A1_HARD_STOP, do not run the signing sentinel.'
