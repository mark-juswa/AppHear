param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$SignerId,

    [string]$SessionId = "ru_d1_pilot_01",

    [string]$QueuePath = "",

    [ValidateRange(1, 1000)]
    [int]$StartAt = 1,

    [ValidateRange(0, 3600)]
    [int]$AttemptTimeoutSeconds = 0,

    [ValidateRange(0, 5000)]
    [int]$A1MaxPoseAgeMs = 0
)

$ErrorActionPreference = "Stop"
$workspace = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$resolvedQueuePath = if ($QueuePath) {
    (Resolve-Path -LiteralPath $QueuePath).Path
} else {
    Join-Path $workspace "context\recognition_upgrade\ru_d1_batch_pilot_01.csv"
}
$localProperties = Join-Path $workspace "android\local.properties"
$sdkLine = Get-Content -LiteralPath $localProperties | Where-Object { $_ -like "sdk.dir=*" } | Select-Object -First 1
if (-not $sdkLine) { throw "android/local.properties has no sdk.dir" }
$sdkPath = $sdkLine.Substring("sdk.dir=".Length).Replace('\:', ':').Replace('\\', '\')
$adb = Join-Path $sdkPath "platform-tools\adb.exe"
if (-not (Test-Path -LiteralPath $adb)) { throw "adb.exe not found at $adb" }

$devices = & $adb devices | Select-Object -Skip 1 | Where-Object { $_ -match "\sdevice$" }
if ($devices.Count -ne 1) { throw "Expected exactly one authorized device; found $($devices.Count)" }

$allQueue = @(Import-Csv -LiteralPath $resolvedQueuePath | Sort-Object { [int]$_.capture_order })
$totalAttempts = $allQueue.Count
if ($totalAttempts -le 0) { throw "Queue is empty: $resolvedQueuePath" }
if ($StartAt -gt $totalAttempts) { throw "StartAt $StartAt exceeds queue size $totalAttempts" }
$queue = @($allQueue | Where-Object { [int]$_.capture_order -ge $StartAt })
$remoteRoot = "/sdcard/Android/data/com.example.apphear/files/ru_d1"

Write-Host "RU diagnostic batch: $SessionId | signer: $SignerId | attempts remaining: $($queue.Count)/$totalAttempts"
Write-Host "For every attempt: follow the READY instruction, long-press CLEAR, sign once, return to rest, then long-press CLEAR again."

foreach ($row in $queue) {
    $order = [int]$row.capture_order
    $a1Mode = ([string]$row.a1_mode).Trim().ToUpperInvariant()
    if ($a1Mode -and $a1Mode -notin @('BASELINE', 'A1')) {
        throw "Attempt $order has invalid a1_mode '$a1Mode'. Expected BASELINE or A1."
    }
    if ($a1Mode -eq 'A1' -and $A1MaxPoseAgeMs -le 0) {
        throw "Attempt $order requests A1 but -A1MaxPoseAgeMs was not supplied."
    }
    $activity = if ($a1Mode) {
        'com.example.apphear/.A1BenchmarkActivity'
    } else {
        'com.example.apphear/.SplashActivity'
    }
    $attemptSessionId = if ($a1Mode) {
        "${SessionId}_$($a1Mode.ToLowerInvariant())"
    } else {
        $SessionId
    }
    $instructionBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes([string]$row.instruction))
    Write-Host ""
    Write-Host ("[{0:D2}/{1:D2}] {2} {3} | expected hands: {4}" -f $order, $totalAttempts, $row.gloss, $row.repetition_id, $row.expected_hands)
    Write-Host $row.instruction

    $before = @(& $adb shell "find $remoteRoot -mindepth 2 -maxdepth 2 -name capture_complete.json -print 2>/dev/null")
    & $adb shell am force-stop com.example.apphear | Out-Null
    $launch = @(
        'shell', 'am', 'start', '-n', $activity,
        '--es', 'ru_d1_gloss', $row.gloss,
        '--es', 'ru_d1_expected_hands', $row.expected_hands,
        '--es', 'ru_d1_signer_id', $SignerId,
        '--es', 'ru_d1_variant', $row.variant,
        '--es', 'ru_d1_session_id', $attemptSessionId,
        '--es', 'ru_d1_repetition_id', $row.repetition_id,
        '--es', 'ru_d1_instruction_b64', $instructionBase64,
        '--ei', 'ru_d1_capture_order', $order.ToString(),
        '--ei', 'ru_d1_total_attempts', $totalAttempts.ToString()
    )
    if ($a1Mode) {
        $launch += @('--es', 'a1_mode', $a1Mode, '--es', 'a1_run_id', "SIGNING_$order")
    }
    if ($a1Mode -eq 'A1') {
        $launch += @('--el', 'a1_max_pose_age_ms', $A1MaxPoseAgeMs.ToString())
    }
    & $adb @launch | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Activity launch failed for attempt $order." }

    $deadline = if ($AttemptTimeoutSeconds -gt 0) {
        (Get-Date).AddSeconds($AttemptTimeoutSeconds)
    } else {
        $null
    }
    $saved = $null
    while ($null -eq $deadline -or (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 750
        $deviceState = (& $adb get-state 2>$null | Select-Object -First 1).Trim()
        if ($deviceState -ne "device") {
            throw "Device disconnected during attempt $order ($($row.gloss) $($row.repetition_id)). Resume with -StartAt $order after reconnecting."
        }
        $after = @(& $adb shell "find $remoteRoot -mindepth 2 -maxdepth 2 -name capture_complete.json -print 2>/dev/null")
        $saved = $after | Where-Object { $_ -notin $before } | Select-Object -First 1
        if ($saved) { break }
    }
    if (-not $saved) {
        throw "Attempt $order ($($row.gloss) $($row.repetition_id)) was not saved within the optional $AttemptTimeoutSeconds-second limit. Resume with -StartAt $order."
    }
    $captureCompleteText = (& $adb shell "cat '$saved'") -join "`n"
    $captureComplete = $captureCompleteText | ConvertFrom-Json
    if ([int]$captureComplete.trace_rows -le 0 -or [int]$captureComplete.evidence_frames -le 0) {
        throw "Attempt $order saved an incomplete bundle (trace_rows=$($captureComplete.trace_rows), evidence_frames=$($captureComplete.evidence_frames)). Stop collection and inspect it."
    }
    Write-Host "Saved $($row.gloss) $($row.repetition_id). Preparing the next attempt..."
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "All $totalAttempts diagnostic attempts are saved. Leave the device connected for the batch pull."
