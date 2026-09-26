param(
    [ValidateSet('Audit', 'Check', 'Evaluate')]
    [string]$Command = 'Check',
    [switch]$RequireResult
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$config = Join-Path $projectRoot 'model\config\recognition_upgrade\a2_recovery.json'
$output = Join-Path $projectRoot 'artifacts\recognition_upgrade\a2_landmark_continuity\a2_2r_one_observation_01'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python environment was not found: $python"
}

Set-Location -LiteralPath $projectRoot
$arguments = @(
    '-m',
    'eval.runtime_diagnostics.a2_recovery_experiment',
    $Command.ToLowerInvariant(),
    '--config',
    $config,
    '--output-dir',
    $output
)
if ($RequireResult) {
    $arguments += '--require-result'
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "A2-2R $Command failed."
}
