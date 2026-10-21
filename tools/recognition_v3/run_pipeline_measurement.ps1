# One live front-camera WORD capture for the pipelined-pose throughput comparison.
# Run ONLY with the user present: they sign/move in front of the phone for -Seconds.
# The user opens the recognition screen; the app's own AppHearV3 timing trace is streamed to the PC.
# (Instrumented launches failed on MIUI: startActivitySync never idles during a live preview,
# background starts and shell key injection are refused, and the activity is not exported.) Installs use `adb install -r` only and check that
# firstInstallTime is unchanged (data kept). Never uninstalls or clears data.
param(
    [Parameter(Mandatory)][ValidateSet('serial','pipelined','emit')][string]$Arm,
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Label,
    [Parameter(Mandatory)][string]$Serial,
    [Parameter(Mandatory)][string]$AppApk,
    [Parameter(Mandatory)][string]$Python,
    [int]$Seconds = 90,
    [int]$WarmupSeconds = 10,
    # Seconds between thermal/battery snapshots during the capture (0 = before/after only).
    [int]$ThermalEverySeconds = 0,
    [string]$AdbPath = 'D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe',
    [switch]$SkipInstall
)
$ErrorActionPreference = 'Stop'
$started = Get-Date
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$out = Join-Path $root 'artifacts/recognition_v3_pipeline/live'
New-Item -ItemType Directory -Force -Path $out | Out-Null
if (Test-Path -LiteralPath (Join-Path $out "$Label-summary.json")) { throw 'Use a unique capture label.' }
$package = 'com.example.apphear'

function Invoke-Adb {
    param([string[]]$AdbArguments)
    # PowerShell 5.1 turns native stderr into terminating errors under 'Stop'; trust the exit code.
    $ErrorActionPreference = 'Continue'
    $text = & $AdbPath -s $Serial @AdbArguments 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw ($text -join "`n") }
    return ($text -join "`n")
}
function Get-FirstInstall {
    $dump = Invoke-Adb @('shell', 'dumpsys', 'package', $package)
    if ($dump -notmatch 'firstInstallTime=(\S+ \S+)') { throw 'firstInstallTime not found' }
    return $Matches[1]
}
function Get-AppPid {
    $appPid = (Invoke-Adb @('shell', 'pidof', $package)).Trim()
    if (-not $appPid) { throw 'App process not running during capture.' }
    return $appPid
}
function Save-ThreadStat([string]$Path) {
    Invoke-Adb @('shell', "cat /proc/$(Get-AppPid)/task/*/stat") | Set-Content -LiteralPath $Path -Encoding utf8
}
function Get-PssKb {
    $meminfo = Invoke-Adb @('shell', 'dumpsys', 'meminfo', $package)
    if ($meminfo -match 'TOTAL PSS:\s+(\d+)') { return [int]$Matches[1] }
    if ($meminfo -match '\n\s+TOTAL\s+(\d+)') { return [int]$Matches[1] }
    return $null
}

$logcat = $null
trap { if ($logcat) { Stop-Process -Id $logcat.Id -ErrorAction SilentlyContinue }; break }
$devices = & $AdbPath devices
if (-not ($devices -match "^$([regex]::Escape($Serial))\s+device$")) { throw 'Device absent or unauthorized.' }
$firstInstall = Get-FirstInstall
if (-not $SkipInstall) {
    Write-Output (Invoke-Adb @('install', '-r', $AppApk))
    if ((Get-FirstInstall) -ne $firstInstall) { throw 'firstInstallTime changed: app data may not be preserved. Stop.' }
}
$installed = ((Invoke-Adb @('shell', 'pm', 'path', $package)) -replace '^package:', '').Trim()
$installedSha = ((Invoke-Adb @('shell', 'sha256sum', $installed)) -split '\s+')[0]
$apkSha = (Get-FileHash -LiteralPath $AppApk -Algorithm SHA256).Hash.ToLowerInvariant()
if ($installedSha -ne $apkSha) { throw "Installed APK $installedSha is not $AppApk." }
# This phone's thermal HAL reports no temperatures; battery temperature is the available proxy.
(Invoke-Adb @('shell', 'dumpsys', 'thermalservice')) + "`n" + (Invoke-Adb @('shell', 'dumpsys', 'battery')) |
    Set-Content -LiteralPath (Join-Path $out "$Label-thermal-before.txt") -Encoding utf8

$streamed = Join-Path $out "$Label-stream.log"
$logcat = Start-Process -FilePath $AdbPath -NoNewWindow -PassThru -RedirectStandardOutput $streamed `
    -ArgumentList @('-s', $Serial, 'logcat', '-v', 'threadtime', '-T', '1', '-s',
        'AppHearV3:I', 'AppHearPhone:I', 'AndroidRuntime:E')
# The user opens ASL Recognition by hand: the activity is not exported, and MIUI blocks both
# background starts and shell key injection.
Write-Output 'WAITING: open ASL Recognition (WORD) on the phone now.'
$deadline = (Get-Date).AddSeconds(180)
while (-not ((Get-Content -LiteralPath $streamed -Raw -ErrorAction SilentlyContinue) -match 'perception_v3_timing')) {
    if ((Get-Date) -gt $deadline) { throw 'No timing trace within 180 s (screen not opened? profile build?).' }
    Start-Sleep -Milliseconds 500
}
Start-Sleep -Seconds $WarmupSeconds
$cpuStart = Get-Date
Save-ThreadStat (Join-Path $out "$Label-proc-before.txt")
$pss = [System.Collections.Generic.List[object]]::new()
$thermal = [System.Collections.Generic.List[object]]::new()
$nextThermal = 0
while (((Get-Date) - $cpuStart).TotalSeconds -lt $Seconds) {
    $elapsed = [Math]::Round(((Get-Date) - $cpuStart).TotalSeconds, 1)
    $pss.Add(@{ t_s = $elapsed; pss_kb = Get-PssKb })
    if ($ThermalEverySeconds -gt 0 -and $elapsed -ge $nextThermal) {
        $battery = Invoke-Adb @('shell', 'dumpsys', 'battery')
        $status = Invoke-Adb @('shell', 'dumpsys', 'thermalservice')
        $thermal.Add(@{ t_s = $elapsed
            battery_temp_c = if ($battery -match 'temperature: (\d+)') { [int]$Matches[1] / 10.0 } else { $null }
            thermal_status = if ($status -match 'Thermal Status: (\d+)') { [int]$Matches[1] } else { $null } })
        $nextThermal += $ThermalEverySeconds
    }
    Start-Sleep -Seconds 10
}
Save-ThreadStat (Join-Path $out "$Label-proc-after.txt")
$cpuWall = ((Get-Date) - $cpuStart).TotalSeconds
(Invoke-Adb @('shell', 'dumpsys', 'thermalservice')) + "`n" + (Invoke-Adb @('shell', 'dumpsys', 'battery')) |
    Set-Content -LiteralPath (Join-Path $out "$Label-thermal-after.txt") -Encoding utf8
Start-Sleep -Seconds 2
Stop-Process -Id $logcat.Id -ErrorAction SilentlyContinue  # a USB reset may already have ended it
$logcat = $null

@{ arm = $Arm; label = $Label; serial = $Serial; seconds = $Seconds; warmup_seconds = $WarmupSeconds
   first_install_time = $firstInstall; app_apk_sha256 = $apkSha; cpu_wall_seconds = $cpuWall
   pss_samples = $pss; thermal_samples = $thermal; finished_local = (Get-Date).ToString('o') } | ConvertTo-Json -Depth 4 |
    Set-Content -LiteralPath (Join-Path $out "$Label-run.json") -Encoding utf8
$summary = & $Python (Join-Path $PSScriptRoot 'summarize_pipeline_trace.py') $streamed `
    --longest-segment --skip-warmup 40 `
    --proc-before (Join-Path $out "$Label-proc-before.txt") --proc-after (Join-Path $out "$Label-proc-after.txt") `
    --wall-seconds $cpuWall
if ($LASTEXITCODE -ne 0) { throw 'Trace integrity failed.' }
$parsed = ($summary -join "`n") | ConvertFrom-Json
if ($parsed.pipelined_pose -ne ($Arm -ne 'serial') -or $parsed.emit_on_hands -ne ($Arm -eq 'emit')) {
    throw 'Installed runtime arm does not match -Arm.'
}
$summary | Set-Content -LiteralPath (Join-Path $out "$Label-summary.json") -Encoding utf8
Write-Output ($summary -join "`n")
