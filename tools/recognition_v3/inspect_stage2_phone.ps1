param(
    [string]$AdbPath = 'D:/AndroidStudio/Android/Sdk/platform-tools/adb.exe',
    [string]$Serial,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
# This command never installs/launches apps, clears logs/data, or changes phone settings.
if ($CheckOnly) {
    Write-Output 'READ_ONLY_PREFLIGHT_SCRIPT_CHECK; no device operation performed.'
    return
}
$preflightRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$preflightStamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$preflightOut = Join-Path $preflightRoot "artifacts/recognition_v3_stage2_compact/phone_preflight_$preflightStamp"
New-Item -ItemType Directory -Path $preflightOut | Out-Null
$preflightDevices = & $AdbPath devices -l 2>&1
if ($LASTEXITCODE -ne 0) { throw 'ADB discovery failed; no app action attempted.' }
$preflightDevices | Set-Content -LiteralPath (Join-Path $preflightOut 'devices.txt') -Encoding utf8
$preflightAuthorized = @($preflightDevices | ForEach-Object {
    if ($_ -match '^(\S+)\s+device(?:\s|$)') { $Matches[1] }
})
if ($Serial) {
    if ($Serial -notin $preflightAuthorized) { throw 'Requested phone is absent or unauthorized.' }
} elseif ($preflightAuthorized.Count -eq 1) {
    $Serial = $preflightAuthorized[0]
} else {
    throw 'No single authorized phone; specify -Serial after reconnecting. No app action attempted.'
}
$preflightCommands = [ordered]@{
    model = @('shell','getprop','ro.product.model')
    android = @('shell','getprop','ro.build.version.release')
    uptime = @('shell','cat','/proc/uptime')
    boot_reason = @('shell','getprop','ro.boot.bootreason')
    system_boot_reason = @('shell','getprop','sys.boot.reason')
    app_exit_info = @('shell','dumpsys','activity','exit-info','com.example.apphear')
    thermal = @('shell','dumpsys','thermalservice')
    battery = @('shell','dumpsys','battery')
    memory = @('shell','cat','/proc/meminfo')
    recent_crashes = @('logcat','-d','-b','crash','-t','200')
}
$preflightStatuses = [ordered]@{}
foreach ($preflightName in $preflightCommands.Keys) {
    $preflightArguments = $preflightCommands[$preflightName]
    $preflightText = & $AdbPath -s $Serial @preflightArguments 2>&1
    $preflightStatuses[$preflightName] = $LASTEXITCODE
    $preflightText | Set-Content -LiteralPath (Join-Path $preflightOut "$preflightName.txt") -Encoding utf8
}
[ordered]@{
    schema_version = 'apphear.stage2.read_only_device_preflight.v1'
    command_exit_codes = $preflightStatuses
    stability_certified = $false
    app_installed_or_launched = $false
    logs_or_data_cleared = $false
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $preflightOut 'summary.json') -Encoding utf8
Write-Output "READ_ONLY_PREFLIGHT_SAVED $preflightOut"
Write-Output 'Review exit/boot/thermal records and actual phone stability before any capture; this is not a stability pass.'
