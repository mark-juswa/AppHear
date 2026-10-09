param(
    [string]$Adb = "D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe",
    [string]$Serial = "3ab64582"
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$remoteRoot = "/sdcard/Android/data/com.example.apphear/files/phase4a_gate4a1_live_plumbing_validation_01"
$sessionName = (& $Adb -s $Serial shell cat "$remoteRoot/latest_session.txt").Trim()
if (-not $sessionName) { throw "GATE4A1_NO_LATEST_SESSION" }

$hostRoot = Join-Path $repo "artifacts\recognition_upgrade\perception_vnext\recognition_utility_236_01\phase4a_gate4a1_live_plumbing_validation_01"
$hostSession = Join-Path $hostRoot $sessionName
New-Item -ItemType Directory -Path $hostSession -Force | Out-Null

$summaryText = (& $Adb -s $Serial shell cat "$remoteRoot/$sessionName/session_summary.json") -join "`n"
if (-not $summaryText.Contains('"valid_attempts": 5')) {
    throw "GATE4A1_SESSION_NOT_COMPLETE: finish five valid phone attempts before pulling"
}

& $Adb -s $Serial pull "$remoteRoot/$sessionName/." $hostSession
if ($LASTEXITCODE -ne 0) { throw "GATE4A1_ADB_PULL_FAILED" }

$hashes = Get-ChildItem -LiteralPath $hostSession -Recurse -File | Sort-Object FullName | ForEach-Object {
    [PSCustomObject]@{
        path = $_.FullName.Substring($hostSession.Length + 1)
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        bytes = $_.Length
    }
}
$hashPath = Join-Path $hostRoot "host_retained_artifact_hashes.json"
$hashes | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $hashPath -Encoding utf8

Set-Location $repo
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "GATE4A1_PROJECT_PYTHON_NOT_FOUND:$python" }
& $python -m eval.runtime_diagnostics.finalize_phase4a_gate4a1 --session $hostSession --output $hostRoot
if ($LASTEXITCODE -ne 0) { throw "GATE4A1_OFFLINE_REPLAY_FAILED" }

Write-Host "GATE4A1_HOST_EVIDENCE_RETAINED=$hostSession"
Write-Host "GATE4A1_HASH_MANIFEST=$hashPath"
Write-Host "No uninstall, cleanup, or reinstall was performed by this script."
