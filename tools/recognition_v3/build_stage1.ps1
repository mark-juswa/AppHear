param(
    [ValidateSet('baseline','v3')][string]$Arm = 'v3'
)
$ErrorActionPreference = 'Stop'
$v3Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$v3Out = Join-Path $v3Root 'artifacts/recognition_v3_stage1'
New-Item -ItemType Directory -Force -Path $v3Out | Out-Null
$v3Fixtures = Join-Path $v3Out 'android_fixtures'
if (-not (Test-Path -LiteralPath (Join-Path $v3Fixtures 'v3/manifest.json'))) {
    throw 'Run compare_hand_scheduling.py first to create the recorded-pixel Android parity fixtures.'
}
$v3Tasks = @('testDebugUnitTest','assembleDebug','assembleDebugAndroidTest',
    "-PrecognitionV3ParallelHands=$($Arm -eq 'v3')", '-PrecognitionV3Profile=true',
    "-PrecognitionV3FixtureDir=$v3Fixtures")
# Same integrated app flags and hash-checked frozen packages in both arms; fake services, no credentials.
& (Join-Path $v3Root 'tools/android/build_working_baseline.ps1') -Configuration fake -OriginalWords -Tasks $v3Tasks
Copy-Item -LiteralPath (Join-Path $v3Root 'android/app/build/outputs/apk/debug/app-debug.apk') `
    -Destination (Join-Path $v3Out "app-debug-$Arm.apk")
Copy-Item -LiteralPath (Join-Path $v3Root 'android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk') `
    -Destination (Join-Path $v3Out "app-debug-$Arm-androidTest.apk")
$v3TestOut = Join-Path $v3Out "tests-$Arm"
New-Item -ItemType Directory -Force -Path $v3TestOut | Out-Null
Copy-Item -Path (Join-Path $v3Root 'android/app/build/test-results/testDebugUnitTest/*.xml') `
    -Destination $v3TestOut -Force
Get-FileHash -LiteralPath (Join-Path $v3Out "app-debug-$Arm.apk") -Algorithm SHA256
