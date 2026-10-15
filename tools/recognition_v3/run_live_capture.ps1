param(
    [Parameter(Mandatory)][ValidateSet('baseline','v3')][string]$Arm,
    [Parameter(Mandatory)][ValidateSet('WORD','FINGERSPELL')][string]$Owner,
    [Parameter(Mandatory)][ValidateSet('front','rear')][string]$Lens,
    [Parameter(Mandatory)][ValidatePattern('^[a-zA-Z0-9_-]+$')][string]$Label,
    [Parameter(Mandatory)][string]$Serial,
    [string]$AdbPath = 'adb',
    [Parameter(Mandatory)][string]$Python,
    [switch]$InstallApp
)
$ErrorActionPreference = 'Stop'
$liveRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$liveOut = Join-Path $liveRoot 'artifacts/recognition_v3_validation'
if (Test-Path -LiteralPath (Join-Path $liveOut "$Label-test.txt")) { throw 'Use a unique capture label.' }
$liveManifest = Get-Content -LiteralPath (Join-Path $liveRoot `
    'evidence/recognition_v3_stage1_20261015/delivery_manifest.json') -Raw | ConvertFrom-Json
$liveName = "app-debug-$Arm.apk"
$liveApp = Join-Path $liveRoot "artifacts/recognition_v3_stage1/$liveName"
if ((Get-FileHash -LiteralPath $liveApp -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    $liveManifest.apks.PSObject.Properties[$liveName].Value.sha256) { throw 'Saved app hash drift.' }
function Invoke-LiveAdb {
    param([string[]]$LiveArguments)
    $liveOutput = & $AdbPath -s $Serial @LiveArguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw ($liveOutput -join "`n") }
    return ($liveOutput -join "`n")
}
if ($InstallApp) { Write-Output (Invoke-LiveAdb -LiveArguments @('install','-r',$liveApp)) }
Write-Output (Invoke-LiveAdb -LiveArguments @('install','-r',(Join-Path $liveOut 'live-androidTest.apk')))
Invoke-LiveAdb -LiveArguments @('shell','dumpsys','thermalservice') |
    Set-Content -LiteralPath (Join-Path $liveOut "$Label-thermal-before.txt") -Encoding utf8
$liveResult = Invoke-LiveAdb -LiveArguments @('shell','am','instrument','-w','-r','-e','class',
    'com.example.apphear.perceptionvnext.LivePerceptionCaptureInstrumentedTest',
    '-e','owner',$Owner,'-e','lens',$Lens,'-e','label',$Label,
    'com.example.apphear.test/androidx.test.runner.AndroidJUnitRunner')
$liveResult | Set-Content -LiteralPath (Join-Path $liveOut "$Label-test.txt") -Encoding utf8
if ($liveResult -notmatch '\bOK \(1 test\)' -or $liveResult -match 'FAILURES!!!|shortMsg=') {
    throw "Live capture did not complete: $Label. Preserve failure and stop."
}
$liveLog = Invoke-LiveAdb -LiveArguments @('logcat','-d','-v','threadtime','-s',
    'AppHearV3:I','AppHearV3Capture:I','*:S')
$liveLog | Set-Content -LiteralPath (Join-Path $liveOut "$Label-all.log") -Encoding utf8
$liveSelected = [System.Collections.Generic.List[string]]::new()
$liveActive = $false
$liveEnded = $false
foreach ($liveLine in ($liveLog -split "`n")) {
    if ($liveLine.Contains("BEGIN label=$Label ")) { $liveActive = $true }
    if ($liveActive) { $liveSelected.Add($liveLine) }
    if ($liveActive -and $liveLine.Contains("END label=$Label ")) { $liveEnded=$true; break }
}
if (-not $liveEnded) { throw 'Log capture boundaries missing; no partial FPS summary allowed.' }
$liveTrace = Join-Path $liveOut "$Label.log"
$liveSelected | Set-Content -LiteralPath $liveTrace -Encoding utf8
Invoke-LiveAdb -LiveArguments @('shell','run-as','com.example.apphear','cat',"files/v3_live_$Label.json") |
    Set-Content -LiteralPath (Join-Path $liveOut "$Label-ui.json") -Encoding utf8
foreach ($liveService in @('cpuinfo','thermalservice')) {
    Invoke-LiveAdb -LiveArguments @('shell','dumpsys',$liveService) |
        Set-Content -LiteralPath (Join-Path $liveOut "$Label-$liveService-after.txt") -Encoding utf8
}
$liveSummary = & $Python (Join-Path $PSScriptRoot 'summarize_trace.py') $liveTrace --skip-warmup 20
if ($LASTEXITCODE -ne 0) { throw 'Trace integrity failed.' }
$liveParsed = ($liveSummary -join "`n") | ConvertFrom-Json
if ($liveParsed.owner -ne $Owner -or $liveParsed.v3_parallel_hands -ne ($Arm -eq 'v3')) {
    throw 'Actual runtime owner/arm does not match the requested comparison.'
}
$liveSummary | Set-Content -LiteralPath (Join-Path $liveOut "$Label-summary.json") -Encoding utf8
Write-Output ($liveSummary -join "`n")
