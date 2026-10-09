param(
    [ValidateSet('Prepare', 'CorrectColorUi', 'Review', 'Check', 'Evaluate')]
    [string]$Command = 'Check',
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$config = Join-Path $projectRoot 'model\config\recognition_upgrade\a2_identity.json'
$defaultOutput = Join-Path $projectRoot 'artifacts\recognition_upgrade\a2_landmark_continuity\a2_0_identity_01'
$output = if ($OutputDirectory) { $OutputDirectory } else { $defaultOutput }

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python environment was not found: $python"
}

Set-Location -LiteralPath $projectRoot
$moduleCommand = if ($Command -eq 'CorrectColorUi') { 'correct-color-ui' } else {
    $Command.ToLowerInvariant()
}
$arguments = @(
    '-m',
    'eval.runtime_diagnostics.a2_identity_experiment',
    $moduleCommand,
    '--config',
    $config,
    '--output-dir',
    $output
)
if ($Command -eq 'Check') {
    $arguments += '--require-complete'
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "A2 $Command failed. Read the JSON report above for the evidence or annotation gate."
}
