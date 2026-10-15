param(
    [ValidateSet('baseline','v3')][string]$Arm = 'v3',
    [string]$AdbPath = 'adb',
    [string]$Serial,
    [switch]$CheckOnly,
    [switch]$IncludeUiRegression
)
$ErrorActionPreference = 'Stop'
$gateRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$gateArtifacts = Join-Path $gateRoot 'artifacts/recognition_v3_stage1'
$gateManifest = Get-Content -LiteralPath (Join-Path $gateRoot `
    'evidence/recognition_v3_stage1_20261015/delivery_manifest.json') -Raw | ConvertFrom-Json
foreach ($gateName in @("app-debug-$Arm.apk", "app-debug-$Arm-androidTest.apk")) {
    $gateFile = Join-Path $gateArtifacts $gateName
    $gateExpected = $gateManifest.apks.PSObject.Properties[$gateName].Value.sha256
    if ((Get-FileHash -LiteralPath $gateFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $gateExpected) {
        throw "APK hash mismatch: $gateName. This gate targets the saved Stage 1 pair."
    }
}
if ($CheckOnly) {
    Write-Output "APK_HASH_PREFLIGHT_PASS arm=$Arm; no device operation or Android test performed."
    return
}
$gateList = & $AdbPath devices
if ($LASTEXITCODE -ne 0) { throw 'ADB device discovery failed.' }
$gateDevices = @($gateList | ForEach-Object {
    if ($_ -match '^(\S+)\s+device$') { $Matches[1] }
})
if ($Serial) {
    if ($Serial -notin $gateDevices) { throw 'Requested device is absent, offline or unauthorized.' }
} elseif ($gateDevices.Count -eq 1) {
    $Serial = $gateDevices[0]
} else {
    throw 'Connect one authorized Android phone, or specify -Serial. No install/test was attempted.'
}

function Invoke-GateAdb {
    param([string[]]$GateArguments)
    $gateOutput = & $AdbPath -s $Serial @GateArguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw ($gateOutput -join "`n") }
    return ($gateOutput -join "`n")
}

$gateStamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$gateOut = Join-Path $gateRoot "artifacts/recognition_v3_validation/device_${gateStamp}_$Arm"
New-Item -ItemType Directory -Path $gateOut | Out-Null
$gateDevice = [ordered]@{
    arm = $Arm
    model = Invoke-GateAdb -GateArguments @('shell','getprop','ro.product.model')
    sdk = Invoke-GateAdb -GateArguments @('shell','getprop','ro.build.version.sdk')
    abi = Invoke-GateAdb -GateArguments @('shell','getprop','ro.product.cpu.abi')
    fingerprint = Invoke-GateAdb -GateArguments @('shell','getprop','ro.build.fingerprint')
    apk_hashes = $gateManifest.apks.PSObject.Properties | Where-Object Name -In @(
        "app-debug-$Arm.apk", "app-debug-$Arm-androidTest.apk") | ForEach-Object {
            [ordered]@{ name=$_.Name; sha256=$_.Value.sha256 }
        }
}
$gateDevice | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $gateOut 'identity.json') -Encoding utf8
# Same package/debug signing key. Keep user data, models, settings and history intact.
foreach ($gateName in @("app-debug-$Arm.apk", "app-debug-$Arm-androidTest.apk")) {
    Write-Output (Invoke-GateAdb -GateArguments @('install','-r',(Join-Path $gateArtifacts $gateName)))
}
$gateClasses = @(
    'com.example.apphear.perceptionvnext.ParallelHandRefinerInstrumentedTest',
    'com.example.apphear.camera.CameraInputInstrumentedTest',
    'com.example.apphear.perceptionvnext.PhoneS2ParityInstrumentedTest',
    'com.example.apphear.perceptionvnext.RecognitionV2EndToEndReplayInstrumentedTest',
    'com.example.apphear.fingerspelling.SequenceV21ParityInstrumentedTest',
    # Legacy confirmationRefusalAndWordIsolation targets manual Start/Done, not this continuous build.
    'com.example.apphear.fingerspelling.FingerspellSingleLetterInstrumentedTest#exactPythonParity'
)
if ($IncludeUiRegression) {
    # Run UI tests separately to avoid the previously observed combined activity-focus timeout.
    $gateClasses += 'com.example.apphear.fingerspelling.ContinuousFingerspellInstrumentedTest'
    $gateClasses += 'com.example.apphear.coordination.RecognitionCoordinationInstrumentedTest#actualOwnerAutomaticEntryConfirmedSpellingAndWordPreservation'
}
foreach ($gateClass in $gateClasses) {
    $gateResult = Invoke-GateAdb -GateArguments @('shell','am','instrument','-w','-r','-e','class',$gateClass,
        'com.example.apphear.test/androidx.test.runner.AndroidJUnitRunner')
    $gateLabel = ($gateClass -split '\.')[-1].Replace('#','_')
    $gateResult | Set-Content -LiteralPath (Join-Path $gateOut "$gateLabel.txt") -Encoding utf8
    if ($gateResult -match 'FAILURES!!!|INSTRUMENTATION_FAILED|Process crashed|shortMsg=|INSTRUMENTATION_STATUS_CODE: -3' `
        -or $gateResult -notmatch '\bOK \([1-9][0-9]* tests?\)') {
        throw "Android gate did not pass: $gateClass. Evidence: $gateOut. Stop before live measurements."
    }
    Write-Output "PASS $gateClass"
}
$gateParity = Invoke-GateAdb -GateArguments @('shell','run-as','com.example.apphear','cat',
    'files/recognition_v3_recorded_parity.json')
$gateParity | Set-Content -LiteralPath (Join-Path $gateOut 'recorded_parity.json') -Encoding utf8
if (($gateParity | ConvertFrom-Json).status -ne 'PASS') { throw 'Recorded-pixel parity result missing.' }
Write-Output "ANDROID_ENGINEERING_GATE_PASS arm=$Arm evidence=$gateOut"
Write-Output 'Live delivered FPS, front/rear scenes, CPU/PSS/thermal and recognition accuracy remain separate tests.'
